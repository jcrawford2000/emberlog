import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any, AsyncIterator, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from emberlog_api.models.incident import IncidentOut

_HEARTBEAT_SECONDS = 15
_ALLOWED_DOMAINS = {"traffic", "system", "dispatch"}
_EVENT_TYPE_RE = re.compile(r"^[a-z]+(?:\.[a-z_]+){2,}$")

router = APIRouter(prefix="/sse", tags=["sse"])


@dataclass(slots=True)
class _Subscriber:
    queue: asyncio.Queue[Any]
    stream: Literal["events", "incidents"]
    filters: dict[str, str | tuple[str, ...] | None] | None = None


subscribers: dict[asyncio.Queue[Any], _Subscriber] = {}


def _validate_filters(
    *,
    domain: str | None,
    event_type: list[str] | None,
    system: str | None,
    site: str | None,
) -> dict[str, str | tuple[str, ...] | None]:
    if domain is not None and domain not in _ALLOWED_DOMAINS:
        raise HTTPException(status_code=400, detail="Invalid domain filter")
    if event_type is not None:
        for requested_event_type in event_type:
            if not _EVENT_TYPE_RE.fullmatch(requested_event_type):
                raise HTTPException(status_code=400, detail="Invalid event_type filter")
    if system is not None and not system.strip():
        raise HTTPException(status_code=400, detail="Invalid system filter")
    if site is not None and not site.strip():
        raise HTTPException(status_code=400, detail="Invalid site filter")
    event_types = tuple(dict.fromkeys(event_type)) if event_type else None
    return {"domain": domain, "event_types": event_types, "system": system, "site": site}


def _event_matches_filters(
    event: dict[str, Any], filters: dict[str, str | tuple[str, ...] | None]
) -> bool:
    event_type = str(event.get("event_type", ""))
    payload = event.get("payload")
    source = event.get("source")
    payload_dict = payload if isinstance(payload, dict) else {}
    source_dict = source if isinstance(source, dict) else {}

    domain = filters["domain"]
    if domain is not None and not event_type.startswith(f"{domain}."):
        return False

    requested_event_types = filters["event_types"]
    if requested_event_types is not None and event_type not in requested_event_types:
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


def _sse_headers() -> dict[str, str]:
    return {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }


async def _event_generator(queue: asyncio.Queue[dict[str, Any]]) -> AsyncIterator[bytes]:
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
        return


async def _incident_event_generator(queue: asyncio.Queue[str]) -> AsyncIterator[bytes]:
    try:
        while True:
            try:
                incident = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT_SECONDS)
                yield f"event: incident\ndata: {incident}\n\n".encode("utf-8")
            except asyncio.TimeoutError:
                yield b"event: ping\ndata: {}\n\n"
    except asyncio.CancelledError:
        return


async def _cleanup_on_disconnect(request: Request, queue: asyncio.Queue[Any]) -> None:
    try:
        while True:
            if await request.is_disconnected():
                break
            await asyncio.sleep(1)
    finally:
        subscribers.pop(queue, None)


async def publish_event(event: dict[str, Any]) -> None:
    event_type = event.get("event_type")
    if not isinstance(event_type, str):
        return

    for subscriber in list(subscribers.values()):
        if subscriber.stream != "events" or subscriber.filters is None:
            continue
        if not _event_matches_filters(event, subscriber.filters):
            continue
        try:
            cast_queue: asyncio.Queue[dict[str, Any]] = subscriber.queue
            cast_queue.put_nowait(event)
        except asyncio.QueueFull:
            pass


async def publish_incident(incident: IncidentOut) -> None:
    payload = incident.model_dump_json()
    for subscriber in list(subscribers.values()):
        if subscriber.stream != "incidents":
            continue
        try:
            cast_queue: asyncio.Queue[str] = subscriber.queue
            cast_queue.put_nowait(payload)
        except asyncio.QueueFull:
            pass


@router.get("")
async def stream_events(
    request: Request,
    domain: str | None = Query(None),
    event_type: list[str] | None = Query(None),
    system: str | None = Query(None),
    site: str | None = Query(None),
):
    filters = _validate_filters(
        domain=domain, event_type=event_type, system=system, site=site
    )
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    subscribers[queue] = _Subscriber(queue=queue, stream="events", filters=filters)
    asyncio.create_task(_cleanup_on_disconnect(request, queue))
    return StreamingResponse(
        _event_generator(queue), media_type="text/event-stream", headers=_sse_headers()
    )


@router.get("/incidents")
async def stream_incidents(request: Request):
    queue: asyncio.Queue[str] = asyncio.Queue()
    subscribers[queue] = _Subscriber(queue=queue, stream="incidents")
    asyncio.create_task(_cleanup_on_disconnect(request, queue))
    return StreamingResponse(
        _incident_event_generator(queue),
        media_type="text/event-stream",
        headers=_sse_headers(),
    )
