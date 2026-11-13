from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from easydeploy_agent.validators.domain import validate_domain
from easydeploy_agent.validators.names import validate_unit_name
from easydeploy_agent.validators.path import is_under, normalize_path


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Example.COM", "example.com"),
        ("app.example.com.", "app.example.com"),
        ("bücher.example", "xn--bcher-kva.example"),
        ("مثال.ایران", "xn--mgbh0fb.xn--mgba3a4f16a"),
        ("a-b.example.org", "a-b.example.org"),
    ],
)
def test_valid_domains(raw: str, expected: str) -> None:
    assert validate_domain(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "localhost",
        "-bad.example.com",
        "bad-.example.com",
        "a..b.com",
        "exa mple.com",
        "example.123",
        "x" * 64 + ".com",
        "a.b;rm -rf /",
        "$(id).example.com",
        "*.example.com",
    ],
)
def test_invalid_domains(raw: str) -> None:
    with pytest.raises(ValueError):
        validate_domain(raw)


def test_wildcard_only_when_allowed() -> None:
    assert validate_domain("*.Example.com", allow_wildcard=True) == "*.example.com"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("/etc/nginx/../nginx/nginx.conf", "/etc/nginx/nginx.conf"),
        ("//opt//easydeploy/", "/opt/easydeploy"),
        ("/a/./b", "/a/b"),
        ("/../../etc", "/etc"),
    ],
)
def test_normalize_path(raw: str, expected: str) -> None:
    assert normalize_path(raw) == expected


@pytest.mark.parametrize("raw", ["relative/path", "", "/a\x00b", "C:\\Windows", "/a\\b"])
def test_reject_bad_paths(raw: str) -> None:
    with pytest.raises(ValueError):
        normalize_path(raw)


@given(st.lists(st.sampled_from(["a", "b", "..", ".", "", "etc", "x y"]), max_size=12))
def test_normalized_paths_never_contain_dotdot(parts: list[str]) -> None:
    result = normalize_path("/" + "/".join(parts))
    assert result.startswith("/")
    assert ".." not in result.split("/")
    assert "//" not in result


def test_is_under() -> None:
    assert is_under("/opt/easydeploy/www/site", "/opt/easydeploy/www")
    assert is_under("/opt/easydeploy/www", "/opt/easydeploy/www")
    assert not is_under("/opt/easydeploy/www-evil", "/opt/easydeploy/www")
    assert not is_under("/opt/easydeploy/www/../data", "/opt/easydeploy/www")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("nginx", "nginx.service"),
        ("nginx.service", "nginx.service"),
        ("easydeploy.target", "easydeploy.target"),
        ("getty@tty1.service", "getty@tty1.service"),
        ("redis-server", "redis-server.service"),
    ],
)
def test_unit_names(raw: str, expected: str) -> None:
    assert validate_unit_name(raw) == expected


@pytest.mark.parametrize("raw", ["../etc/passwd", "a/b.service", "nginx; reboot", "-x.service", ""])
def test_bad_unit_names(raw: str) -> None:
    with pytest.raises(ValueError):
        validate_unit_name(raw)
