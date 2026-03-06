from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, TypedDict


class DecodeSiteProjection(TypedDict):
    group: str
    sys_num: int
    sys_name: str
    decode_rate_pct: float
    control_channel_mhz: float | None
    interval_s: float | None
    updated_at: str | None
    status: str


def _to_iso_z(value: datetime | None) -> str | None:
    if value is None:
        return None
    dt = value.astimezone(UTC)
    return dt.isoformat().replace("+00:00", "Z")


def _group_from_sys_name(sys_name: str) -> str:
    return sys_name.split("-", 1)[0] if sys_name else ""


def _decode_status(decode_rate_pct: float) -> str:
    if decode_rate_pct >= 90.0:
        return "ok"
    if decode_rate_pct >= 70.0:
        return "warn"
    return "bad"


def normalize_decode_site_projection(
    *,
    sys_num: int,
    sys_name: str,
    decode_rate_pct: float,
    control_channel_hz: int | None,
    interval_s: float | None,
    updated_at: datetime | None,
) -> DecodeSiteProjection:
    return {
        "group": _group_from_sys_name(sys_name),
        "sys_num": sys_num,
        "sys_name": sys_name,
        "decode_rate_pct": decode_rate_pct,
        "control_channel_mhz": (
            float(control_channel_hz) / 1_000_000.0
            if control_channel_hz is not None
            else None
        ),
        "interval_s": interval_s,
        "updated_at": _to_iso_z(updated_at),
        "status": _decode_status(decode_rate_pct),
    }


def normalize_decode_site_row(row: dict[str, Any]) -> DecodeSiteProjection:
    updated_at = row.get("updated_at")
    return normalize_decode_site_projection(
        sys_num=int(row["sys_num"]),
        sys_name=str(row["sys_name"]),
        decode_rate_pct=float(row["decoderate_pct"]),
        control_channel_hz=(
            int(row["control_channel_hz"])
            if row.get("control_channel_hz") is not None
            else None
        ),
        interval_s=(
            float(row["decoderate_interval_s"])
            if row.get("decoderate_interval_s") is not None
            else None
        ),
        updated_at=updated_at if isinstance(updated_at, datetime) else None,
    )
