import json

import anyio
import pytest
from fastapi import FastAPI

from emberlog_api.app.api.v1.routers import sse

sse_app = FastAPI()
sse_app.include_router(sse.router, prefix="/api/v1")


@pytest.fixture(autouse=True)
def clear_sse_state():
    sse.incident_subscribers.clear()
    sse.event_subscribers.clear()
    yield
    sse.incident_subscribers.clear()
    sse.event_subscribers.clear()


@pytest.fixture
def app():
    return sse_app


def _event_fixture(*, event_type: str, system: str, site: str) -> dict:
    return {
        "event_id": "7f006c17-df7e-4978-b606-66c9ca69f7f7",
        "event_type": event_type,
        "schema_version": "1.0.0",
        "timestamp": "2026-03-04T12:00:00Z",
        "source": {
            "module": "emberlog-api",
            "instance": "trunk-recorder",
            "system": system,
        },
        "payload": {
            "system": system,
            "site": site,
            "call_id": "1_4499_1771215827",
        },
    }


class _FakeRequest:
    def __init__(self) -> None:
        self.disconnected = False

    async def is_disconnected(self) -> bool:
        return self.disconnected


async def _read_one_sse_event(response, timeout_s: float = 1.5) -> tuple[str, str]:
    with anyio.fail_after(timeout_s):
        chunk = await anext(response.body_iterator)
    decoded = chunk.decode("utf-8").strip().splitlines()
    if len(decoded) < 2:
        raise AssertionError(f"unexpected sse chunk: {decoded}")
    return decoded[0], decoded[1]


async def _open_stream(*, domain=None, event_type=None, system=None, site=None):
    request = _FakeRequest()
    response = await sse.stream_events(
        request=request,
        domain=domain,
        event_type=event_type,
        system=system,
        site=site,
    )
    return request, response


async def _close_stream(request: _FakeRequest) -> None:
    request.disconnected = True
    await anyio.sleep(0)


@pytest.mark.anyio
async def test_sse_route_returns_event_and_data_lines():
    event = _event_fixture(
        event_type="traffic.call.started", system="PRWC", site="J"
    )
    request, response = await _open_stream()
    await sse.publish_event(event)
    event_line, data_line = await _read_one_sse_event(response)
    await _close_stream(request)

    assert event_line == "event: traffic.call.started"
    assert data_line.startswith("data: ")
    body = json.loads(data_line.removeprefix("data: "))
    assert body["event_id"] == event["event_id"]


@pytest.mark.anyio
async def test_sse_filter_by_domain():
    event = _event_fixture(
        event_type="system.site.decode_rate.updated", system="PRWC", site="J"
    )
    request, response = await _open_stream(domain="system")
    await sse.publish_event(event)
    event_line, _ = await _read_one_sse_event(response)
    await _close_stream(request)

    assert event_line == "event: system.site.decode_rate.updated"


@pytest.mark.anyio
async def test_sse_filter_by_event_type():
    event = _event_fixture(
        event_type="traffic.call.ended", system="PRWC", site="J"
    )
    request, response = await _open_stream(event_type="traffic.call.ended")
    await sse.publish_event(event)
    event_line, _ = await _read_one_sse_event(response)
    await _close_stream(request)

    assert event_line == "event: traffic.call.ended"


@pytest.mark.anyio
async def test_multiple_subscribers_receive_same_event():
    event = _event_fixture(
        event_type="traffic.call.started", system="PRWC", site="J"
    )
    request_one, response_one = await _open_stream()
    request_two, response_two = await _open_stream()
    await sse.publish_event(event)
    event_line_one, _ = await _read_one_sse_event(response_one)
    event_line_two, _ = await _read_one_sse_event(response_two)
    await _close_stream(request_one)
    await _close_stream(request_two)

    assert event_line_one == "event: traffic.call.started"
    assert event_line_two == "event: traffic.call.started"


@pytest.mark.anyio
async def test_invalid_filter_returns_400(async_client):
    response = await async_client.get("/api/v1/sse", params={"domain": "invalid"})
    assert response.status_code == 400
