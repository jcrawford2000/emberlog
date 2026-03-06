from datetime import datetime, timezone

import pytest

from emberlog_api.app.services import mqtt_consumer
from emberlog_api.app.services.decode_sites import normalize_decode_site_row


@pytest.mark.anyio
async def test_handle_rates_message_calls_repo_upsert(monkeypatch):
    calls: list[dict] = []

    async def fake_upsert_decode_rate(pool, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(
        mqtt_consumer.traffic_repo, "upsert_decode_rate", fake_upsert_decode_rate
    )

    payload = {
        "type": "rates",
        "rates": [
            {
                "sys_num": 1,
                "sys_name": "PRWC-J",
                "decoderate": 0.41,
                "decoderate_interval": 3.0,
                "control_channel": 769118750.0,
            }
        ],
        "timestamp": 1771215501,
        "instance_id": "trunk-recorder",
    }

    await mqtt_consumer.handle_rates_message(pool=None, payload=payload)

    assert len(calls) == 1
    assert calls[0]["instance_id"] == "trunk-recorder"
    assert calls[0]["sys_num"] == 1
    assert calls[0]["sys_name"] == "PRWC-J"
    assert calls[0]["decoderate_raw"] == 0.41
    assert calls[0]["decoderate_pct"] == mqtt_consumer._decode_rate_pct(0.41)
    assert calls[0]["decoderate_interval_s"] == 3.0
    assert calls[0]["control_channel_hz"] == 769118750
    assert calls[0]["updated_at"] == datetime.fromtimestamp(1771215501, tz=timezone.utc)


@pytest.mark.anyio
async def test_handle_rates_message_publishes_decode_rate_event(monkeypatch):
    events: list[dict] = []

    async def fake_upsert_decode_rate(pool, **kwargs):
        return None

    async def fake_publish_event(event):
        events.append(event)

    monkeypatch.setattr(
        mqtt_consumer.traffic_repo, "upsert_decode_rate", fake_upsert_decode_rate
    )
    monkeypatch.setattr(mqtt_consumer, "publish_event", fake_publish_event)

    payload = {
        "type": "rates",
        "rates": [
            {
                "sys_num": 1,
                "sys_name": "PRWC-J",
                "decoderate": 0.41,
                "decoderate_interval": 3.0,
                "control_channel": 769118750.0,
            }
        ],
        "timestamp": 1771215501,
        "instance_id": "trunk-recorder",
    }

    await mqtt_consumer.handle_rates_message(pool=None, payload=payload)

    assert len(events) == 1
    event = events[0]
    assert event["event_type"] == "system.site.decode_rate.updated"
    assert event["schema_version"] == "1.0.0"
    assert event["source"]["module"] == "emberlog-api"
    assert event["source"]["instance"] == "trunk-recorder"
    assert event["source"]["system"] == "PRWC-J"
    assert event["payload"] == {
        "group": "PRWC",
        "sys_num": 1,
        "sys_name": "PRWC-J",
        "decode_rate_pct": mqtt_consumer._decode_rate_pct(0.41),
        "control_channel_mhz": 769.11875,
        "interval_s": 3.0,
        "updated_at": "2026-02-16T04:18:21Z",
        "status": "bad",
    }
    assert "decode_rate" not in event["payload"]
    assert "site" not in event["payload"]
    assert "control_channel_frequency" not in event["payload"]


@pytest.mark.anyio
async def test_decode_site_projection_is_consistent_between_rest_and_sse_paths(monkeypatch):
    events: list[dict] = []
    upserted_rows: list[dict] = []

    async def fake_upsert_decode_rate(pool, **kwargs):
        upserted_rows.append(kwargs)
        return None

    async def fake_publish_event(event):
        events.append(event)

    monkeypatch.setattr(
        mqtt_consumer.traffic_repo, "upsert_decode_rate", fake_upsert_decode_rate
    )
    monkeypatch.setattr(mqtt_consumer, "publish_event", fake_publish_event)

    payload = {
        "type": "rates",
        "rates": [
            {
                "sys_num": 3,
                "sys_name": "DPS-WT",
                "decoderate": 0.41,
                "decoderate_interval": 3.0,
                "control_channel": 774293750.0,
            }
        ],
        "timestamp": 1771215501,
        "instance_id": "trunk-recorder",
    }

    await mqtt_consumer.handle_rates_message(pool=None, payload=payload)

    assert len(upserted_rows) == 1
    assert len(events) == 1
    rest_projection = normalize_decode_site_row(
        {
            "sys_num": upserted_rows[0]["sys_num"],
            "sys_name": upserted_rows[0]["sys_name"],
            "decoderate_pct": upserted_rows[0]["decoderate_pct"],
            "decoderate_interval_s": upserted_rows[0]["decoderate_interval_s"],
            "control_channel_hz": upserted_rows[0]["control_channel_hz"],
            "updated_at": upserted_rows[0]["updated_at"],
        }
    )
    assert rest_projection == events[0]["payload"]


@pytest.mark.anyio
async def test_handle_calls_active_message_publishes_started_and_ended(monkeypatch):
    events: list[dict] = []
    mqtt_consumer._active_calls_by_instance.clear()

    async def fake_upsert_calls_active_snapshot(pool, **kwargs):
        return None

    async def fake_publish_event(event):
        events.append(event)

    monkeypatch.setattr(
        mqtt_consumer.traffic_repo,
        "upsert_calls_active_snapshot",
        fake_upsert_calls_active_snapshot,
    )
    monkeypatch.setattr(mqtt_consumer, "publish_event", fake_publish_event)

    first_payload = {
        "timestamp": 1771215827,
        "instance_id": "trunk-recorder",
        "calls": [
            {
                "id": "1_4499_1771215827",
                "sys_name": "PRWC-J",
                "talkgroup": 4499,
                "talkgroup_alpha_tag": "Avondale PD A01",
                "freq": 770118750.0,
                "elapsed": 4,
            }
        ],
    }

    second_payload = {
        "timestamp": 1771215831,
        "instance_id": "trunk-recorder",
        "calls": [],
    }

    await mqtt_consumer.handle_calls_active_message(pool=None, payload=first_payload)
    await mqtt_consumer.handle_calls_active_message(pool=None, payload=second_payload)

    assert [event["event_type"] for event in events] == [
        "traffic.call.started",
        "traffic.call.ended",
    ]
    assert events[0]["payload"]["call_id"] == "1_4499_1771215827"
    assert events[0]["payload"]["system"] == "PRWC-J"
    assert events[0]["payload"]["site"] == "default"
    assert events[1]["payload"]["duration_seconds"] == 4.0
