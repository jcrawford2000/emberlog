from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from emberlog.api.client import EmberlogAPIClient, IncidentIn
from emberlog.config.config import get_settings

from .base import Sink, SinkResult

logger = logging.getLogger("emberlog.io.db_sink")
settings = get_settings()


@dataclass
class ApiSink(Sink):
    api_base_url = settings.api_base_url

    async def process(
        self, *, transcript, incident, audio_path: Path, out_dir: Path, context=None
    ) -> SinkResult:
        result = await self.write_api(incident)
        return SinkResult(
            ok=True, extra={"inserted": "true", "rowid": "xx", "sha": "xx"}
        )

    async def write_api(self, obj: dict[str, Any]) -> dict[str, Any]:
        api = EmberlogAPIClient(base_url=self.api_base_url, api_key="")
        incident = IncidentIn(
            dispatched_at=obj["dispatched_at"],
            source_audio=obj["source_audio"],
            special_call=obj["special_call"],
            units=obj["units"],
            channel=obj["channel"],
            incident_type=obj["incident_type"],
            address=obj["address"],
            original_text=obj["cleaned_text"],
            transcript=obj["cleaned_text"],
            parsed={},
        )
        result = await api.create_incident(payload=incident)
        await api.close()
        return result.model_dump()
