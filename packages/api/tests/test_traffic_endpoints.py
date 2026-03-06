from datetime import UTC, datetime

import pytest
from fastapi import FastAPI

from emberlog_api.app.api.v1.routers import traffic
from emberlog_api.app.db.pool import get_pool
from emberlog_api.app.db.repositories import traffic as traffic_repo

traffic_app = FastAPI()
traffic_app.include_router(traffic.router, prefix="/api/v1")


@pytest.fixture(autouse=True)
def override_dependencies():
    async def override_pool():
        return None

    traffic_app.dependency_overrides[get_pool] = override_pool
    yield
    traffic_app.dependency_overrides = {}


@pytest.fixture
def app():
    return traffic_app


@pytest.mark.anyio
async def test_traffic_summary_returns_snapshot_envelope(async_client, monkeypatch):
    decode_rows = [
        {
            "sys_num": 1,
            "sys_name": "PRWC-J",
            "decoderate_pct": 97.5,
            "decoderate_interval_s": 3.0,
            "control_channel_hz": 769118750,
            "updated_at": datetime(2026, 2, 16, 4, 23, 41, tzinfo=UTC),
        },
        {
            "sys_num": 2,
            "sys_name": "MCSO-WT",
            "decoderate_pct": 65.0,
            "decoderate_interval_s": 2.0,
            "control_channel_hz": 770000000,
            "updated_at": datetime(2026, 2, 16, 4, 23, 40, tzinfo=UTC),
        },
    ]

    async def fake_list_decode_rate_latest(pool, *, instance_id):
        assert instance_id == "trunk-recorder"
        return decode_rows

    monkeypatch.setattr(
        traffic_repo, "list_decode_rate_latest", fake_list_decode_rate_latest
    )

    response = await async_client.get("/api/v1/traffic/summary")
    assert response.status_code == 200
    envelope = response.json()

    assert isinstance(envelope["event_id"], str)
    assert envelope["event_type"] == "system.decode_sites.snapshot"
    assert envelope["schema_version"] == "1.0.0"
    assert envelope["timestamp"] == "2026-02-16T04:23:41Z"
    assert envelope["source"] == {
        "module": "emberlog-api",
        "instance": "trunk-recorder",
    }

    decode_sites = envelope["payload"]["decode_sites"]
    assert len(decode_sites) == 2
    assert decode_sites[0]["group"] == "MCSO"
    assert decode_sites[0]["status"] == "bad"
    assert decode_sites[1]["group"] == "PRWC"
    assert decode_sites[1]["status"] == "ok"
    assert decode_sites[1]["control_channel_mhz"] == 769.11875

    first = decode_sites[0]
    assert isinstance(first["group"], str)
    assert isinstance(first["sys_num"], int)
    assert isinstance(first["sys_name"], str)
    assert isinstance(first["decode_rate_pct"], float)
    assert isinstance(first["control_channel_mhz"], float)
    assert isinstance(first["interval_s"], float)
    assert isinstance(first["updated_at"], str)
    assert isinstance(first["status"], str)


@pytest.mark.anyio
async def test_traffic_live_calls_normalization_and_filters(async_client, monkeypatch):
    snapshot_row = {
        "updated_at": datetime(2026, 2, 16, 4, 23, 51, tzinfo=UTC),
        "calls_json": {
            "calls": [
                {
                    "id": "1_4499_1771215827",
                    "start_time": 1771215827,
                    "elapsed": 4,
                    "sys_num": 1,
                    "sys_name": "PRWC-J",
                    "talkgroup": 4499,
                    "talkgroup_alpha_tag": "Avondale PD A01",
                    "talkgroup_description": "A01 Dispatch",
                    "talkgroup_group": "Avondale Police",
                    "talkgroup_tag": "Law Dispatch",
                    "freq": 770118750.0,
                    "encrypted": False,
                    "emergency": False,
                    "phase2_tdma": True,
                    "tdma_slot": 0,
                    "unit": 707004,
                    "src_num": 0,
                    "rec_num": 0,
                },
                {
                    "id": "2_5500_1771215800",
                    "start_time": 1771215800,
                    "elapsed": 15,
                    "sys_num": 1,
                    "sys_name": "PRWC-J",
                    "talkgroup_alpha_tag": "Encrypted",
                    "talkgroup_description": "Dispatch",
                    "encrypted": True,
                    "src_num": 1,
                    "rec_num": 1,
                },
                {
                    "id": "3_6600_1771215900",
                    "start_time": 1771215900,
                    "elapsed": 2,
                    "sys_num": 2,
                    "sys_name": "MCSO-WT",
                    "talkgroup_alpha_tag": "Other",
                    "talkgroup_description": "Ops",
                    "encrypted": False,
                    "src_num": 2,
                    "rec_num": 3,
                },
            ]
        },
    }

    async def fake_select_calls_active_snapshot_latest(pool, *, instance_id):
        assert instance_id == "trunk-recorder"
        return snapshot_row

    monkeypatch.setattr(
        traffic_repo,
        "select_calls_active_snapshot_latest",
        fake_select_calls_active_snapshot_latest,
    )

    response = await async_client.get(
        "/api/v1/traffic/live-calls",
        params={
            "hide_encrypted": "true",
            "q": "dispatch",
            "sys_name": "PRWC-J",
        },
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["instance_id"] == "trunk-recorder"
    assert payload["updated_at"] == "2026-02-16T04:23:51Z"
    assert len(payload["calls"]) == 1

    call = payload["calls"][0]
    assert call["id"] == "1_4499_1771215827"
    assert call["sys_name"] == "PRWC-J"
    assert call["group"] == "PRWC"
    assert call["talkgroup_id"] == 4499
    assert call["talkgroup"] == "Avondale PD A01"
    assert call["description"] == "A01 Dispatch"
    assert call["category"] == "Avondale Police"
    assert call["tag"] == "Law Dispatch"
    assert call["freq_mhz"] == 770.11875
    assert call["started_at"] == "2026-02-16T04:23:47Z"
    assert call["recorder_id"] == "0_0"
    assert call["encrypted"] is False
