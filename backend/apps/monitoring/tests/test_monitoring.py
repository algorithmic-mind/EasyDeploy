from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from conftest import WebsocketCommunicator
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.agent_client import FakeAgent
from apps.monitoring import services
from apps.monitoring.models import HostSample

pytestmark = pytest.mark.django_db(databases=["default", "monitor"])


def test_rates_from_counters() -> None:
    prev = {
        "timestamp": 100.0,
        "disk_read_bytes": 1000,
        "disk_write_bytes": 0,
        "net": [{"interface": "eth0", "bytes_sent": 0, "bytes_recv": 0}],
    }
    cur = {
        "timestamp": 110.0,
        "disk_read_bytes": 11000,
        "disk_write_bytes": 500,
        "net": [
            {"interface": "eth0", "bytes_sent": 2000, "bytes_recv": 5000},
            {"interface": "eth1", "bytes_sent": 1, "bytes_recv": 1},
        ],
    }
    out = services.with_rates(cur, prev)
    assert out["disk_read_bps"] == 1000.0
    assert out["disk_write_bps"] == 50.0
    assert out["net_rates"] == {"eth0": {"rx_bps": 500.0, "tx_bps": 200.0}}
    assert out["net_rx_bps"] == 500.0
    # Counter reset (reboot) never yields negative rates.
    assert services.with_rates(prev, cur)["disk_read_bps"] == 0.0
    assert services.with_rates(cur, None)["net_rx_bps"] == 0.0


def test_collect_sample(fake_agent: FakeAgent) -> None:
    first = services.collect_sample()
    second = services.collect_sample()
    assert first is not None
    assert second is not None
    assert second.cpu_percent == 12.5
    assert second.disk_percent == 25.0
    assert second.mem_total == 2 * 1024**3
    assert second._state.db == "monitor"
    assert HostSample.objects.count() == 2


def test_collect_disabled(fake_agent: FakeAgent, set_setting: Any) -> None:
    set_setting("monitoring.enabled", False)
    assert services.collect_sample() is None


def _sample(ts: Any, cpu: float, resolution: int = 60) -> HostSample:
    return HostSample.objects.create(ts=ts, cpu_percent=cpu, resolution=resolution)


def test_maintenance_downsamples_and_expires() -> None:
    now = timezone.now()
    base = (now - timedelta(days=8)).replace(second=0, microsecond=0)
    base = base - timedelta(minutes=base.minute % 5)
    for i in range(5):  # one 5-minute bucket of raw samples, 8 days old
        _sample(base + timedelta(minutes=i), cpu=10.0 * (i + 1))
    _sample(now - timedelta(days=40), cpu=99.0)  # beyond the 30-day retention
    _sample(now - timedelta(hours=1), cpu=5.0)  # recent raw sample stays
    result = services.maintenance(now)
    assert result == {"deleted": 1, "downsampled": 5, "buckets": 1}
    down = HostSample.objects.get(resolution=300)
    assert down.cpu_percent == 30.0
    assert HostSample.objects.filter(resolution=60).count() == 1


def test_history_endpoint_and_bucketing(auth_client: APIClient) -> None:
    now = timezone.now()
    for i in range(1500):
        _sample(now - timedelta(seconds=10 * i), cpu=float(i % 10))
    body = auth_client.get("/api/v1/monitoring/history", {"range": "24h"}).json()
    assert body["range"] == "24h"
    assert 0 < len(body["points"]) <= services.MAX_POINTS
    assert {"ts", "cpu_percent", "net_rx_bps"} <= set(body["points"][0])
    bad = auth_client.get("/api/v1/monitoring/history", {"range": "1y"})
    assert bad.status_code == 400


def test_current_endpoint(auth_client: APIClient, fake_agent: FakeAgent) -> None:
    data = auth_client.get("/api/v1/monitoring/current").json()["data"]
    assert data["cpu_percent"] == 12.5
    assert "net_rates" in data


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True, databases=["default", "monitor"])
async def test_live_websocket(auth_client: APIClient, fake_agent: FakeAgent) -> None:
    from easydeploy.asgi import application

    comm = WebsocketCommunicator(
        application,
        "/ws/monitor/live/",
        headers=[
            (b"cookie", f"ed_session={auth_client.cookies['ed_session'].value}".encode()),
            (b"origin", b"http://testserver"),
            (b"host", b"testserver"),
        ],
    )
    connected, _ = await comm.connect()
    assert connected
    frame = await comm.receive_json_from(timeout=5)
    assert frame["type"] == "metrics"
    assert frame["data"]["memory_total"] == 2 * 1024**3
    await comm.disconnect()
