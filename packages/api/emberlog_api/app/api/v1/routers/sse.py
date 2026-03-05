import asyncio
import json
import logging
import os
import re
from typing import Any, AsyncIterator

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from emberlog_api.models.incident import IncidentOut

log = logging.getLogger("emberlog_api.v1.routers.sse")

_HEARTBEAT_SECONDS = 15
_ALLOWED_DOMAINS = {"traffic", "system", "dispatch"}
_EVENT_TYPE_RE = re.compile(r"^[a-z]+(?:\.[a-z_]+){2,}$")

router = APIRouter(prefix="/sse", tags=["sse"])

incident_subscribers: set[asyncio.Queue[str]] = set()
event_subscribers: dict[asyncio.Queue[dict[str, Any]], dict[str, str | None]] = {}


def _validate_filters(
    *, domain: str | None, event_type: str | None, system: str | None, site: str | None
) -> dict[str, str | None]:
    if domain is not None and domain not in _ALLOWED_DOMAINS:
        raise HTTPException(status_code=400, detail="Invalid domain filter")
    if event_type is not None and not _EVENT_TYPE_RE.fullmatch(event_type):
        raise HTTPException(status_code=400, detail="Invalid event_type filter")
    if system is not None and not system.strip():
        raise HTTPException(status_code=400, detail="Invalid system filter")
    if site is not None and not site.strip():
        raise HTTPException(status_code=400, detail="Invalid site filter")
    return {"domain": domain, "event_type": event_type, "system": system, "site": site}


def _event_matches_filters(
    event: dict[str, Any], filters: dict[str, str | None]
) -> bool:
    event_type = str(event.get("event_type", ""))
    payload = event.get("payload")
    source = event.get("source")
    payload_dict = payload if isinstance(payload, dict) else {}
    source_dict = source if isinstance(source, dict) else {}

    domain = filters["domain"]
    if domain is not None and not event_type.startswith(f"{domain}."):
        return False

    requested_event_type = filters["event_type"]
    if requested_event_type is not None and event_type != requested_event_type:
        return False

    requested_system = filters["system"]
    if requested_system is not None:
        payload_system = payload_dict.get("system")
        source_system = source_dict.get("system")
        if payload_system != requested_system and source_system != requested_system:
            return False

    requested_site = filters["site"]
    if requested_site is not None and payload_dict.get("site") != requested_site:
        return False

    return True


async def _event_generator(queue: asyncio.Queue[dict[str, Any]]) -> AsyncIterator[bytes]:
    # Heartbeat so intermediaries keep the connection open.
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT_SECONDS)
                event_type = str(event.get("event_type", "event"))
                data = json.dumps(event, separators=(",", ":"))
                yield f"event: {event_type}\ndata: {data}\n\n".encode("utf-8")
            except asyncio.TimeoutError:
                yield b"event: ping\ndata: {}\n\n"
    except asyncio.CancelledError:
        pass


async def _incident_event_generator(queue: asyncio.Queue[str]) -> AsyncIterator[bytes]:
    # Legacy incident-only stream retained for backward compatibility.
    try:
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT_SECONDS)
                log.debug("SSE: New Incident")
                yield f"event: incident\ndata: {msg}\n\n".encode("utf-8")
            except asyncio.TimeoutError:
                yield b"event: ping\ndata: {}\n\n"
    except asyncio.CancelledError:
        pass


async def publish_event(event: dict[str, Any]) -> None:
    if "event_type" not in event:
        return

    for queue, filters in list(event_subscribers.items()):
        if not _event_matches_filters(event, filters):
            continue
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            # Slow clients should reconnect and dedupe via event_id.
            pass


async def publish_incident(incident: IncidentOut):
    log.debug(
        "Publishing: pid=%s subscribers_id=%s size=%d",
        os.getpid(),
        id(incident_subscribers),
        len(incident_subscribers),
    )
    payload = incident.model_dump_json()
    for queue in list(incident_subscribers):
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            # Slow clients should reconnect and recover.
            pass


@router.get("")
async def stream_events(
    request: Request,
    domain: str | None = Query(None),
    event_type: str | None = Query(None),
    system: str | None = Query(None),
    site: str | None = Query(None),
):
    filters = _validate_filters(
        domain=domain, event_type=event_type, system=system, site=site
    )
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    event_subscribers[queue] = filters

    async def close_when_client_disconnects() -> None:
        try:
            while True:
                if await request.is_disconnected():
                    break
                await asyncio.sleep(1)
        finally:
            event_subscribers.pop(queue, None)

    asyncio.create_task(close_when_client_disconnects())
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(
        _event_generator(queue), media_type="text/event-stream", headers=headers
    )


@router.get("/incidents")
async def stream_incidents(request: Request):
    queue: asyncio.Queue[str] = asyncio.Queue()
    incident_subscribers.add(queue)

    async def close_when_client_disconnects() -> None:
        try:
            while True:
                if await request.is_disconnected():
                    break
                await asyncio.sleep(1)
        finally:
            incident_subscribers.discard(queue)

    asyncio.create_task(close_when_client_disconnects())
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(
        _incident_event_generator(queue), media_type="text/event-stream", headers=headers
    )
