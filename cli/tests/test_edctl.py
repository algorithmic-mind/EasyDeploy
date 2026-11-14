from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from edctl import main as edctl_main
from edctl import panel as edctl_panel
from edctl.config import read_env, update_env
from edctl.system import Result

runner = CliRunner()
TEMPLATE = "server {\n    @LISTEN@\n    ssl_certificate @SSL_CERT@;\n    proxy_pass http://unix:@API_SOCKET@:;\n}\n"


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ED_TEST_ROOT", str(tmp_path))
    (tmp_path / "etc").mkdir()
    (tmp_path / "etc" / "easydeploy.env").write_text(
        "# EasyDeploy\nED_PANEL_PORT=28443\nED_PANEL_LISTEN=ipv4\n", encoding="utf-8"
    )
    tpl = tmp_path / "opt" / "current" / "deploy" / "nginx"
    tpl.mkdir(parents=True)
    (tpl / "panel.conf.template").write_text(TEMPLATE, encoding="utf-8")
    monkeypatch.setattr(edctl_main, "is_root", lambda: True)
    return tmp_path


class FakeRun:
    def __init__(self, responses: dict[str, Result] | None = None) -> None:
        self.calls: list[list[str]] = []
        self.responses = responses or {}

    def __call__(self, argv: Sequence[str], **_kw: Any) -> Result:
        self.calls.append(list(argv))
        key = " ".join(argv[:2])
        return self.responses.get(key, Result(0, "", ""))


def test_requires_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(edctl_main, "is_root", lambda: False)
    result = runner.invoke(edctl_main.app, ["--lang", "en", "reset-2fa"])
    assert result.exit_code == 1
    assert "must run as root" in result.output


def test_status_json_and_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(edctl_main, "unit_state", lambda unit: "active")
    result = runner.invoke(edctl_main.app, ["status", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.output)["easydeploy-api"] == "active"

    monkeypatch.setattr(
        edctl_main, "unit_state", lambda u: "failed" if u == "easydeploy-worker" else "active"
    )
    assert runner.invoke(edctl_main.app, ["status"]).exit_code == 3


def test_status_in_persian(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(edctl_main, "unit_state", lambda unit: "active")
    result = runner.invoke(edctl_main.app, ["--lang", "fa", "status"])
    assert "سرویس‌های ایزی‌دیپلوی" in result.output


def test_reset_password_prints_once(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_manage(*args: str, input_text: str | None = None) -> Result:
        calls.append(args)
        return Result(0, "Generated-Pass-123\n", "")

    monkeypatch.setattr(edctl_main, "manage", fake_manage)
    result = runner.invoke(edctl_main.app, ["--lang", "en", "reset-password"])
    assert result.exit_code == 0
    assert calls == [("ed_reset_password",)]
    assert "Generated-Pass-123" in result.output


def test_reset_entrance_random(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        edctl_main, "manage", lambda *a, input_text=None: calls.append(a) or Result(0, "", "")
    )
    monkeypatch.setattr(edctl_main, "_local_ips", lambda: ["203.0.113.10"])
    result = runner.invoke(edctl_main.app, ["reset-entrance"])
    assert result.exit_code == 0
    cmd, action, key, value = calls[0]
    assert (cmd, action, key) == ("ed_setting", "set", "security.entrance")
    entrance = json.loads(value)
    assert len(entrance) == 12
    assert entrance.isalnum()
    assert f"https://203.0.113.10:28443/{entrance}" in result.output


def test_manage_failure_is_reported(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        edctl_main, "manage", lambda *a, input_text=None: Result(1, "", "admin user not found")
    )
    result = runner.invoke(edctl_main.app, ["--lang", "en", "reset-2fa"])
    assert result.exit_code == 1
    assert "admin user not found" in result.output


def test_set_port_success(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeRun({"ufw status": Result(0, "Status: active\n", "")})
    monkeypatch.setattr(edctl_panel, "run", fake)
    monkeypatch.setattr(edctl_main, "run", fake)
    result = runner.invoke(edctl_main.app, ["--lang", "en", "set-port", "30000"])
    assert result.exit_code == 0, result.output
    assert read_env(root / "etc" / "easydeploy.env")["ED_PANEL_PORT"] == "30000"
    conf = (root / "nginx" / "panel.conf").read_text(encoding="utf-8")
    assert "listen 30000 ssl http2;" in conf
    assert str(root / "run" / "api" / "api.sock") in conf
    assert ["nginx", "-t"] in fake.calls
    assert ["ufw", "allow", "30000/tcp", "comment", "EasyDeploy panel"] in fake.calls
    assert ["ufw", "delete", "allow", "28443/tcp"] in fake.calls


def test_set_port_rolls_back_on_nginx_error(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    conf = root / "nginx" / "panel.conf"
    conf.parent.mkdir(parents=True)
    conf.write_text("old config", encoding="utf-8")
    fake = FakeRun({"nginx -t": Result(1, "", "nginx: [emerg] bad")})
    monkeypatch.setattr(edctl_panel, "run", fake)
    monkeypatch.setattr(edctl_main, "run", fake)
    result = runner.invoke(edctl_main.app, ["--lang", "en", "set-port", "30000"])
    assert result.exit_code == 1
    assert conf.read_text(encoding="utf-8") == "old config"
    assert read_env(root / "etc" / "easydeploy.env")["ED_PANEL_PORT"] == "28443"


@pytest.mark.parametrize("port", ["80", "443", "1023"])
def test_set_port_rejects_bad_ports(root: Path, port: str) -> None:
    assert runner.invoke(edctl_main.app, ["set-port", port]).exit_code == 1


def test_update_env_keeps_comments(tmp_path: Path) -> None:
    env = tmp_path / "x.env"
    env.write_text("# keep me\nA=1\nB=2\n", encoding="utf-8")
    update_env(env, "A", "9")
    update_env(env, "C", "3")
    assert env.read_text(encoding="utf-8") == "# keep me\nA=9\nB=2\nC=3\n"


def test_listen_modes() -> None:
    assert edctl_panel.listen_lines(9000, "dual") == (
        "listen 9000 ssl http2;\n    listen [::]:9000 ssl http2;"
    )
    assert edctl_panel.listen_lines(9000, "ipv6") == "listen [::]:9000 ssl http2;"
