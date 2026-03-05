from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from psycopg_pool import AsyncConnectionPool

from emberlog_api.app.api.v1.routers.sse import publish_event
from emberlog_api.app.core.settings import settings
from emberlog_api.app.db.repositories import traffic as traffic_repo

log = logging.getLogger("emberlog_api.services.mqtt_consumer")

_active_calls_by_instance: dict[str, dict[str, dict[str, Any]]] = {}


def _topic(topic_suffix: str) -> str:
    return f"{settings.mqtt_topic_prefix}/{topic_suffix}"


def _updated_at_from_timestamp(timestamp: Any) -> datetime:
    return datetime.fromtimestamp(float(timestamp), tz=timezone.utc)


def _decode_rate_pct(decoderate: float) -> float:
    decode_pct = (decoderate / settings.max_decoderate) * 100.0 if settings.max_decoderate > 1.0 else decoderate
    return decode_pct


def _isoformat_utc(timestamp: datetime) -> str:
    return timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _site_from_sys_num(sys_num: Any) -> str:
    if sys_num is None:
        return "default"
    return str(sys_num)


def _build_event_envelope(
    *,
    event_type: str,
    timestamp: datetime,
    payload: dict[str, Any],
    instance_id: str,
    system: str | None = None,
) -> dict[str, Any]:
    source: dict[str, Any] = {
        "module": "emberlog-api",
        "instance": instance_id,
    }
    if system is not None:
        source["system"] = system
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "schema_version": "1.0.0",
        "timestamp": _isoformat_utc(timestamp),
        "source": source,
        "payload": payload,
    }


def _build_call_payload(call: dict[str, Any]) -> dict[str, Any] | None:
    call_id = call.get("id")
    sys_name_raw = call.get("sys_name")
    if call_id is None or sys_name_raw is None:
        return None

    sys_name = str(sys_name_raw)
    payload: dict[str, Any] = {
        "system": sys_name,
        "site": _site_from_sys_num(call.get("sys_num")),
        "call_id": str(call_id),
    }

    talkgroup = call.get("talkgroup")
    if talkgroup is not None:
        payload["trunkgroup_id"] = talkgroup

    talkgroup_label = call.get("talkgroup_alpha_tag")
    if talkgroup_label is not None:
        payload["trunkgroup_label"] = str(talkgroup_label)

    frequency = call.get("freq")
    if frequency is not None:
        payload["frequency"] = float(frequency)

    return payload


async def handle_rates_message(pool: AsyncConnectionPool, payload: dict[str, Any]) -> None:
    """Process a rates payload and upsert latest per-system decode rates."""
    instance_id = str(payload["instance_id"])
    updated_at = _updated_at_from_timestamp(payload["timestamp"])
    rates = payload.get("rates")
    if not isinstance(rates, list):
        log.error("rates payload missing list field", extra={"instance_id": instance_id})
        return

    for item in rates:
        if not isinstance(item, dict):
            log.error("rates item is not an object", extra={"instance_id": instance_id})
            continue

        try:
            decoderate_raw = float(item["decoderate"])
            decoderate_pct = _decode_rate_pct(decoderate_raw)
            control_channel = item.get("control_channel")
            control_channel_hz = (
                int(control_channel) if control_channel is not None else None
            )

            await traffic_repo.upsert_decode_rate(
                pool,
                instance_id=instance_id,
                sys_num=int(item["sys_num"]),
                sys_name=str(item["sys_name"]),
                decoderate_raw=decoderate_raw,
                decoderate_pct=decoderate_pct,
                decoderate_interval_s=(
                    float(item["decoderate_interval"])
                    if item.get("decoderate_interval") is not None
                    else None
                ),
                control_channel_hz=control_channel_hz,
                updated_at=updated_at,
            )
            system_name = str(item["sys_name"])
            site_name = _site_from_sys_num(item.get("sys_num"))
            decode_event = _build_event_envelope(
                event_type="system.site.decode_rate.updated",
                timestamp=updated_at,
                instance_id=instance_id,
                system=system_name,
                payload={
                    "system": system_name,
                    "site": site_name,
                    "decode_rate": decoderate_raw,
                    "control_channel_frequency": control_channel_hz,
                },
            )
            await publish_event(decode_event)
            log.debug(
                "processed rates message",
                extra={
                    "instance_id": instance_id,
                    "sys_name": str(item["sys_name"]),
                    "decode_rate_pct": decoderate_pct,
                },
            )
        except Exception:
            log.exception(
                "failed to upsert decode rate",
                extra={"instance_id": instance_id, "rate_item": item},
            )


async def handle_recorders_message(
    pool: AsyncConnectionPool, payload: dict[str, Any]
) -> None:
    """Process a recorders payload and upsert latest recorder snapshot."""
    instance_id = str(payload["instance_id"])
    updated_at = _updated_at_from_timestamp(payload["timestamp"])
    recorders = payload.get("recorders")
    if not isinstance(recorders, list):
        log.error(
            "recorders payload missing list field", extra={"instance_id": instance_id}
        )
        return

    total_count = len(recorders)
    recording_count = sum(
        1
        for rec in recorders
        if isinstance(rec, dict) and rec.get("rec_state_type") == "RECORDING"
    )
    idle_count = sum(
        1
        for rec in recorders
        if isinstance(rec, dict) and rec.get("rec_state_type") == "IDLE"
    )
    available_count = sum(
        1
        for rec in recorders
        if isinstance(rec, dict) and rec.get("rec_state_type") == "AVAILABLE"
    )

    try:
        await traffic_repo.upsert_recorders_snapshot(
            pool,
            instance_id=instance_id,
            recorders_json=payload,
            total_count=total_count,
            recording_count=recording_count,
            idle_count=idle_count,
            available_count=available_count,
            updated_at=updated_at,
        )
        log.debug(
            "processed recorders message",
            extra={"instance_id": instance_id, "total_count": total_count},
        )
    except Exception:
        log.exception("failed to upsert recorders snapshot", extra={"instance_id": instance_id})


async def handle_calls_active_message(
    pool: AsyncConnectionPool, payload: dict[str, Any]
) -> None:
    """Process a calls_active payload and upsert latest active-calls snapshot."""
    instance_id = str(payload["instance_id"])
    updated_at = _updated_at_from_timestamp(payload["timestamp"])
    calls = payload.get("calls")
    if not isinstance(calls, list):
        log.error(
            "calls_active payload missing list field", extra={"instance_id": instance_id}
        )
        return

    active_calls_count = len(calls)

    try:
        await traffic_repo.upsert_calls_active_snapshot(
            pool,
            instance_id=instance_id,
            calls_json=payload,
            active_calls_count=active_calls_count,
            updated_at=updated_at,
        )

        current_calls: dict[str, dict[str, Any]] = {}
        for call in calls:
            if not isinstance(call, dict):
                continue
            call_id = call.get("id")
            if call_id is None:
                continue
            current_calls[str(call_id)] = call

        previous_calls = _active_calls_by_instance.get(instance_id, {})
        started_call_ids = set(current_calls) - set(previous_calls)
        ended_call_ids = set(previous_calls) - set(current_calls)

        for call_id in started_call_ids:
            call = current_calls[call_id]
            call_payload = _build_call_payload(call)
            if call_payload is None:
                continue
            await publish_event(
                _build_event_envelope(
                    event_type="traffic.call.started",
                    timestamp=updated_at,
                    instance_id=instance_id,
                    system=str(call_payload["system"]),
                    payload=call_payload,
                )
            )

        for call_id in ended_call_ids:
            previous_call = previous_calls[call_id]
            call_payload = _build_call_payload(previous_call)
            if call_payload is None:
                continue

            elapsed_seconds = previous_call.get("elapsed")
            if elapsed_seconds is not None:
                call_payload["duration_seconds"] = float(elapsed_seconds)

            await publish_event(
                _build_event_envelope(
                    event_type="traffic.call.ended",
                    timestamp=updated_at,
                    instance_id=instance_id,
                    system=str(call_payload["system"]),
                    payload=call_payload,
                )
            )

        _active_calls_by_instance[instance_id] = current_calls

        log.debug(
            "processed calls_active message",
            extra={
                "instance_id": instance_id,
                "active_calls_count": active_calls_count,
            },
        )
    except Exception:
        log.exception(
            "failed to upsert calls_active snapshot", extra={"instance_id": instance_id}
        )


async def process_mqtt_message(
    pool: AsyncConnectionPool, topic: str, payload_bytes: bytes
) -> None:
    """Parse and dispatch a single MQTT message by topic."""
    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        log.exception("failed to parse mqtt message as JSON", extra={"topic": topic})
        return

    if not isinstance(payload, dict):
        log.error("mqtt payload must be a JSON object", extra={"topic": topic})
        return

    try:
        if topic == _topic(settings.rates_topic_suffix):
            await handle_rates_message(pool, payload)
            return

        if topic == _topic(settings.recorders_topic_suffix):
            await handle_recorders_message(pool, payload)
            return

        if topic == _topic(settings.calls_active_topic_suffix):
            await handle_calls_active_message(pool, payload)
            return

        log.debug("ignoring mqtt message for unsupported topic", extra={"topic": topic})
    except KeyError:
        log.exception("mqtt payload missing required field", extra={"topic": topic})
    except Exception:
        log.exception("failed processing mqtt message", extra={"topic": topic})


async def start_mqtt_consumer(pool: AsyncConnectionPool) -> None:
    """Run a reconnecting MQTT consumer loop for Traffic Monitor topics."""
    try:
        from aiomqtt import Client, MqttError
    except Exception:
        log.exception("aiomqtt is not available; mqtt consumer cannot start")
        return

    reconnect_delay_s = 1.0
    max_reconnect_delay_s = 60.0
    topics = [
        _topic(settings.rates_topic_suffix),
        _topic(settings.recorders_topic_suffix),
        _topic(settings.calls_active_topic_suffix),
    ]

    while True:
        try:
            async with Client(
                hostname=settings.mqtt_host,
                port=settings.mqtt_port,
                username=settings.mqtt_username,
                password=settings.mqtt_password,
            ) as client:
                log.info(
                    "connected to mqtt broker",
                    extra={
                        "host": settings.mqtt_host,
                        "port": settings.mqtt_port,
                        "topic_prefix": settings.mqtt_topic_prefix,
                    },
                )
                reconnect_delay_s = 1.0

                for topic in topics:
                    await client.subscribe(topic)

                async for message in client.messages:
                    await process_mqtt_message(
                        pool,
                        topic=str(message.topic),
                        payload_bytes=bytes(message.payload),
                    )

        except asyncio.CancelledError:
            log.info("mqtt consumer stopped")
            raise
        except MqttError:
            log.exception("mqtt broker connection error")
        except Exception:
            log.exception("unexpected mqtt consumer failure")

        log.info("mqtt reconnect scheduled", extra={"delay_s": reconnect_delay_s})
        await asyncio.sleep(reconnect_delay_s)
        reconnect_delay_s = min(reconnect_delay_s * 2.0, max_reconnect_delay_s)
