"""``edctl`` — EasyDeploy server CLI (§9.18). Must run as root on the server."""

from __future__ import annotations

import json
import socket
from typing import Annotated, Any

import typer

from edctl import __version__
from edctl import panel as panel_conf
from edctl.config import paths, read_env, update_env
from edctl.doctor import run_checks
from edctl.i18n import Translator, detect_language
from edctl.system import DEPENDENCIES, UNITS, is_root, manage, run, systemctl, unit_state

app = typer.Typer(
    name="edctl",
    help="EasyDeploy server control (run as root).",
    no_args_is_help=True,
    add_completion=False,
)
state: dict[str, Any] = {"t": Translator("en"), "json": False}

JsonOpt = Annotated[bool, typer.Option("--json", help="Machine-readable output.")]


def t(key: str, **params: object) -> str:
    translator: Translator = state["t"]
    return translator(key, **params)


def out(data: Any, human: str) -> None:
    typer.echo(json.dumps(data, ensure_ascii=False, indent=2) if state["json"] else human)


def require_root() -> None:
    if not is_root():
        typer.echo(t("need_root"), err=True)
        raise typer.Exit(1)


def fail(message: str, detail: str = "") -> None:
    typer.echo(f"{t('failed')}: {message}", err=True)
    if detail:
        typer.echo(detail.strip(), err=True)
    raise typer.Exit(1)


def manage_or_fail(*args: str, input_text: str | None = None) -> str:
    result = manage(*args, input_text=input_text)
    if not result.ok:
        fail(" ".join(args[:1]), result.stderr or result.stdout)
    # Commands print their result last; anything before it is incidental output.
    lines = result.stdout.strip().splitlines()
    return lines[-1].strip() if lines else ""


@app.callback()
def main(
    lang: Annotated[str | None, typer.Option("--lang", help="en or fa")] = None,
) -> None:
    state["t"] = Translator(detect_language(lang))


# ------------------------------------------------------------------ services
@app.command()
def status(json_out: JsonOpt = False) -> None:
    """Show the state of EasyDeploy services and their dependencies."""
    state["json"] = json_out
    states = {unit: unit_state(unit) for unit in (*UNITS, *DEPENDENCIES)}
    lines = [t("status_title")]
    for unit, value in states.items():
        mark = "●" if value == "active" else "○"
        lines.append(f"  {mark} {unit:<20} {value}")
    out(states, "\n".join(lines))
    if any(states[u] != "active" for u in UNITS):
        raise typer.Exit(3)


def _unit_target(unit: str | None) -> str:
    if not unit:
        return "easydeploy.target"
    name = unit if unit.startswith("easydeploy-") else f"easydeploy-{unit}"
    if name not in UNITS:
        fail(f"unknown unit: {unit} (agent, api, worker)")
    return f"{name}.service"


def _service_action(action: str, unit: str | None) -> None:
    require_root()
    result = systemctl(action, _unit_target(unit))
    if not result.ok:
        fail(f"systemctl {action}", result.stderr)
    typer.echo(t("done"))


@app.command()
def start(unit: Annotated[str | None, typer.Argument()] = None) -> None:
    """Start all EasyDeploy services (or one: agent, api, worker)."""
    _service_action("start", unit)


@app.command()
def stop(unit: Annotated[str | None, typer.Argument()] = None) -> None:
    """Stop all EasyDeploy services (or one)."""
    _service_action("stop", unit)


@app.command()
def restart(unit: Annotated[str | None, typer.Argument()] = None) -> None:
    """Restart all EasyDeploy services (or one)."""
    _service_action("restart", unit)


@app.command()
def logs(
    unit: Annotated[str, typer.Argument(help="agent, api or worker")] = "api",
    follow: Annotated[bool, typer.Option("-f", "--follow")] = False,
    lines: Annotated[int, typer.Option("-n", "--lines")] = 200,
) -> None:
    """Show journal logs of a service."""
    require_root()
    argv = ["journalctl", "-u", _unit_target(unit), "-n", str(lines), "--no-pager"]
    if follow:
        argv.append("-f")
        raise typer.Exit(run(argv, timeout=10**9).returncode)
    typer.echo(run(argv).stdout)


# ------------------------------------------------------------------ access recovery
def _local_ips() -> list[str]:
    result = run(["hostname", "-I"], timeout=5)
    ips = [ip for ip in result.stdout.split() if ip] if result.ok else []
    return ips or [socket.gethostbyname(socket.gethostname())]


def _urls(port: str, entrance: str) -> list[str]:
    suffix = f"/{entrance}" if entrance else "/"
    return [
        f"https://[{ip}]:{port}{suffix}" if ":" in ip else f"https://{ip}:{port}{suffix}"
        for ip in _local_ips()
    ]


@app.command("user-info")
def user_info(json_out: JsonOpt = False) -> None:
    """Print the panel URL(s) and admin username (never the password)."""
    require_root()
    state["json"] = json_out
    info = json.loads(manage_or_fail("ed_user_info"))
    port = read_env(paths().env_file).get("ED_PANEL_PORT", "?")
    domain = info.get("bind_domain")
    urls = [f"https://{domain}:{port}/{info['entrance']}"] if domain else []
    urls += _urls(port, info["entrance"])
    data = {"urls": urls, "username": info["username"], "totp_enabled": info["totp_enabled"]}
    human = "\n".join(
        [
            *(f"{t('panel_url')}: {u}" for u in urls),
            f"{t('username')}: {info['username']}",
            t("password_hint"),
        ]
    )
    out(data, human)


@app.command("reset-password")
def reset_password(
    username: Annotated[str | None, typer.Option(help="Admin username")] = None,
    prompt: Annotated[bool, typer.Option("--prompt", help="Type the new password")] = False,
) -> None:
    """Set a new admin password (generated unless --prompt), unlock it, end all sessions."""
    require_root()
    args = ["ed_reset_password"]
    if username:
        args += ["--username", username]
    if prompt:
        password = typer.prompt("Password", hide_input=True, confirmation_prompt=True)
        manage_or_fail(*args, "--password-stdin", input_text=password + "\n")
        typer.echo(t("done"))
        return
    new_password = manage_or_fail(*args)
    typer.echo(f"{t('new_password')}: {new_password}")


@app.command("reset-2fa")
def reset_2fa(username: Annotated[str | None, typer.Option()] = None) -> None:
    """Disable two-factor authentication for the admin."""
    require_root()
    manage_or_fail("ed_reset_2fa", *(["--username", username] if username else []))
    typer.echo(t("twofa_reset"))


@app.command("reset-entrance")
def reset_entrance(
    value: Annotated[
        str | None, typer.Option(help="6-64 letters/digits; random if omitted")
    ] = None,
    disable: Annotated[bool, typer.Option("--disable", help="Remove the entrance")] = False,
) -> None:
    """Generate (or set) a new security entrance path."""
    require_root()
    entrance = "" if disable else (value or panel_conf.new_entrance())
    manage_or_fail("ed_setting", "set", "security.entrance", json.dumps(entrance))
    port = read_env(paths().env_file).get("ED_PANEL_PORT", "?")
    typer.echo(f"{t('entrance_set')}: /{entrance}")
    for url in _urls(port, entrance):
        typer.echo(f"  {url}")


@app.command("reset-allowlist")
def reset_allowlist() -> None:
    """Remove the panel IP allowlist."""
    require_root()
    manage_or_fail("ed_setting", "reset", "security.ip_allowlist")
    typer.echo(t("allowlist_reset"))


@app.command("reset-bind-domain")
def reset_bind_domain() -> None:
    """Remove the panel bind domain."""
    require_root()
    manage_or_fail("ed_setting", "reset", "security.bind_domain")
    typer.echo(t("bind_domain_reset"))


@app.command("set-port")
def set_port(port: Annotated[int, typer.Argument(min=1, max=65535)]) -> None:
    """Move the panel to another port (Nginx validated + reloaded, UFW updated)."""
    require_root()
    if port < 1024 or port in (80, 443):
        fail(t("port_invalid"))
    p = paths()
    env = read_env(p.env_file)
    old = env.get("ED_PANEL_PORT", "")
    if str(port) == old:
        typer.echo(t("done"))
        return
    if panel_conf.port_in_use(port):
        fail(t("port_in_use", port=port))
    result = panel_conf.apply(p, port=port, listen=env.get("ED_PANEL_LISTEN", "ipv4"))
    if not result.ok:
        fail(t("nginx_invalid"), result.stderr)
    update_env(p.env_file, "ED_PANEL_PORT", str(port))
    if "Status: active" in run(["ufw", "status"], timeout=20).stdout:
        run(["ufw", "allow", f"{port}/tcp", "comment", "EasyDeploy panel"], timeout=20)
        if old.isdigit():
            run(["ufw", "delete", "allow", f"{old}/tcp"], timeout=20)
    typer.echo(t("port_changed", port=port))


# ------------------------------------------------------------------ diagnostics
@app.command()
def doctor(json_out: JsonOpt = False) -> None:
    """Check services, sockets, databases, Nginx, Docker, disk, clock and panel health."""
    require_root()
    state["json"] = json_out
    checks = run_checks(paths())
    problems = [c for c in checks if not c.ok and not c.warning]
    lines = [t("doctor_title")]
    for c in checks:
        mark = "✓" if c.ok else ("!" if c.warning else "✗")
        lines.append(f"  {mark} {c.name:<34} {c.detail}")
        if not c.ok and c.fix:
            lines.append(f"      {t('fix')}: {c.fix}")
    lines.append(t("doctor_problems", count=len(problems)) if problems else t("doctor_ok"))
    out([c.__dict__ for c in checks], "\n".join(lines))
    if problems:
        raise typer.Exit(1)


@app.command()
def version(json_out: JsonOpt = False) -> None:
    """Print versions of the panel and edctl."""
    state["json"] = json_out
    vf = paths().version_file
    panel_version = vf.read_text(encoding="utf-8").strip() if vf.exists() else "unknown"
    out(
        {"panel": panel_version, "edctl": __version__},
        f"EasyDeploy {panel_version} (edctl {__version__})",
    )


def run_cli() -> None:
    app()


if __name__ == "__main__":
    run_cli()
