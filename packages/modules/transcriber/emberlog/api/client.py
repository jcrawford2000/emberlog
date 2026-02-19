from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel, ConfigDict, Field

log = logging.getLogger("emberlog.api")


# Models
class LinkTarget(BaseModel):
    url: str = Field(alias="_url")
    model_config = ConfigDict(populate_by_name=True)


class Links(BaseModel):
    self: LinkTarget


class NewIncident(BaseModel):
    id: int
    created_at: datetime
    links: Links


class IncidentIn(BaseModel):
    dispatched_at: datetime
    special_call: bool = False
    units: Optional[List[str]]
    channel: Optional[str]
    incident_type: Optional[str]
    address: Optional[str]
    source_audio: str
    original_text: Optional[str] = None
    transcript: Optional[str]
    parsed: Optional[dict] = None


DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class EmberlogAPIClient:
    def __init__(
        self, base_url: str, api_key: str, *, timeout: httpx.Timeout = DEFAULT_TIMEOUT
    ):
        self._client = httpx.AsyncClient(
            base_url=base_url.strip("/"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-API-Key": api_key,
            },
            timeout=timeout,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def health(self) -> bool:
        try:
            r = await self._client.get("/health")
            r.raise_for_status()
            return True
        except httpx.HTTPError as e:
            log.warning("Health check failed: %s", e)
            return False

    async def create_incident(self, payload: IncidentIn) -> NewIncident:
        log.debug("API Client Creating Incident")
        try:
            log.debug("Posting to API")
            r = await self._client.post(
                "/incidents/", json=payload.model_dump(mode="json")
            )
            r.raise_for_status()
            log.debug(f"Status: {r.status_code}")
        except httpx.HTTPStatusError as e:
            detail = e.response.text
            log.error("API Error %s: %s", e.response.status_code, detail)
            raise
        data = r.json()
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(
                data["created_at"].replace("Z", "+00:00")
            )
        log.debug(f"Resuult:{data}")
        return NewIncident.model_validate(data)
