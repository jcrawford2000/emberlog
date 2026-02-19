from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional, Sequence, Tuple

# If you already have a settings module, import its ledger_path.
# Fallback to ./outbox/.state/ledger.sqlite3 if not present.
try:
    from emberlog.config.config import get_settings

    settings = get_settings()
    LEDGER_PATH = Path(settings.ledger_path)
except Exception:
    LEDGER_PATH = Path("outbox/.state/ledger.sqlite3")


@dataclass(frozen=True)
class DispatchRecord:
    id: Optional[int]
    audio_path: str
    out_path: str
    started_s: Optional[float]
    ended_s: Optional[float]
    channel: Optional[str]
    units_json: Optional[str]  # JSON string (list/obj)
    type: Optional[str]
    address: Optional[str]
    written_at: str  # ISO 8601 UTC
    sha256: str


def _normalize_for_hash(
    cleaned_text: str,
    channel: Optional[str],
    address: Optional[str],
    units: Optional[Iterable[str] | dict],
) -> str:
    """
    Build a canonical string to hash: lowercase, trimmed, JSON with sorted keys.
    This ensures re-runs with the same logical content produce the same digest.
    """
    norm = {
        "cleaned_text": (cleaned_text or "").strip().lower(),
        "channel": (channel or "").strip().lower(),
        "address": (address or "").strip().lower(),
        # dump units as canonical JSON (list or dict both supported)
        "units": units if units is not None else [],
    }
    return json.dumps(norm, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def compute_sha256(
    cleaned_text: str,
    channel: Optional[str],
    address: Optional[str],
    units: Optional[Iterable[str] | dict],
) -> str:
    buf = _normalize_for_hash(cleaned_text, channel, address, units)
    return hashlib.sha256(buf.encode("utf-8")).hexdigest()


class Ledger:
    """
    Tiny SQLite wrapper for Emberlog's dispatch ledger.
    - WAL mode for safe concurrent readers (e.g., dashboard) and writer (pipeline).
    - Idempotent inserts via UNIQUE(sha256).
    """

    def __init__(self, db_path: Path | str = LEDGER_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(self.db_path),
            detect_types=sqlite3.PARSE_DECLTYPES,
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        self._configure()
        self._ensure_schema()

    def _configure(self) -> None:
        # Good defaults for a small write-light/read-heavy app
        cur = self._conn.cursor()
        cur.execute("PRAGMA journal_mode = WAL;")
        cur.execute("PRAGMA synchronous = NORMAL;")
        cur.execute("PRAGMA foreign_keys = ON;")
        cur.execute("PRAGMA temp_store = MEMORY;")
        cur.execute("PRAGMA mmap_size = 134217728;")  # 128 MiB
        cur.close()

    def _ensure_schema(self) -> None:
        cur = self._conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS dispatches (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                audio_path  TEXT NOT NULL,
                out_path    TEXT NOT NULL,
                started_s   REAL,
                ended_s     REAL,
                channel     TEXT,
                units_json  TEXT,
                type        TEXT,
                address     TEXT,
                written_at  TEXT NOT NULL,  -- ISO8601 UTC
                sha256      TEXT NOT NULL UNIQUE
            );

            CREATE INDEX IF NOT EXISTS idx_dispatches_written_at ON dispatches(written_at);
            CREATE INDEX IF NOT EXISTS idx_dispatches_channel    ON dispatches(channel);
            CREATE INDEX IF NOT EXISTS idx_dispatches_address    ON dispatches(address);
            """
        )
        self._conn.commit()
        cur.close()

    def close(self) -> None:
        self._conn.close()

    # ---------- Write path ----------

    def insert_dispatch(
        self,
        *,
        audio_path: Path | str,
        out_path: Path | str,
        started_s: Optional[float],
        ended_s: Optional[float],
        channel: Optional[str],
        units: Optional[Iterable[str] | dict],
        type_: Optional[str],
        address: Optional[str],
        written_at: Optional[datetime] = None,
        cleaned_text: str,
    ) -> Tuple[bool, Optional[int], str]:
        """
        Insert after you've successfully written the per-dispatch JSON.

        Returns: (inserted, rowid, sha256)
        - inserted=False when the sha256 already exists (idempotent no-op).
        """
        digest = compute_sha256(cleaned_text, channel, address, units)
        ts = (written_at or datetime.now(timezone.utc)).isoformat()

        units_json = (
            json.dumps(units, ensure_ascii=False, sort_keys=True)
            if units is not None
            else None
        )

        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT OR IGNORE INTO dispatches
            (audio_path, out_path, started_s, ended_s, channel, units_json, type, address, written_at, sha256)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                str(audio_path),
                str(out_path),
                started_s,
                ended_s,
                channel,
                units_json,
                type_,
                address,
                ts,
                digest,
            ),
        )
        self._conn.commit()

        inserted = cur.rowcount == 1
        rowid = cur.lastrowid if inserted else self._get_id_by_hash(digest)
        cur.close()
        return inserted, rowid, digest

    def _get_id_by_hash(self, digest: str) -> Optional[int]:
        cur = self._conn.cursor()
        cur.execute("SELECT id FROM dispatches WHERE sha256 = ?;", (digest,))
        row = cur.fetchone()
        cur.close()
        return int(row["id"]) if row else None

    # ---------- Read paths (for your API/dashboard) ----------

    def get_recent(self, limit: int = 50) -> Sequence[DispatchRecord]:
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT * FROM dispatches
            ORDER BY datetime(written_at) DESC
            LIMIT ?;
            """,
            (limit,),
        )
        rows = cur.fetchall()
        cur.close()
        return [self._row_to_record(r) for r in rows]

    def get_between(self, start_iso: str, end_iso: str) -> Sequence[DispatchRecord]:
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT * FROM dispatches
            WHERE written_at >= ? AND written_at < ?
            ORDER BY datetime(written_at) ASC;
            """,
            (start_iso, end_iso),
        )
        rows = cur.fetchall()
        cur.close()
        return [self._row_to_record(r) for r in rows]

    def find(
        self,
        *,
        channel: Optional[str] = None,
        address_like: Optional[str] = None,
        type_: Optional[str] = None,
        limit: int = 100,
    ) -> Sequence[DispatchRecord]:
        clauses = []
        params = []

        if channel:
            clauses.append("channel = ?")
            params.append(channel)
        if address_like:
            clauses.append("address LIKE ?")
            params.append(address_like.replace("*", "%"))
        if type_:
            clauses.append("type = ?")
            params.append(type_)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"""
            SELECT * FROM dispatches
            {where}
            ORDER BY datetime(written_at) DESC
            LIMIT ?;
        """
        params.append(limit)

        cur = self._conn.cursor()
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
        cur.close()
        return [self._row_to_record(r) for r in rows]

    def stats_by_channel(self) -> Sequence[tuple[str, int]]:
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT channel, COUNT(*) AS n
            FROM dispatches
            GROUP BY channel
            ORDER BY n DESC;
            """
        )
        rows = cur.fetchall()
        cur.close()
        return [(r["channel"], r["n"]) for r in rows]

    # ---------- Helpers ----------

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> DispatchRecord:
        return DispatchRecord(
            id=int(row["id"]),
            audio_path=row["audio_path"],
            out_path=row["out_path"],
            started_s=row["started_s"],
            ended_s=row["ended_s"],
            channel=row["channel"],
            units_json=row["units_json"],
            type=row["type"],
            address=row["address"],
            written_at=row["written_at"],
            sha256=row["sha256"],
        )

    def vacuum_if_needed(self) -> None:
        cur = self._conn.cursor()
        cur.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        cur.execute("VACUUM;")
        self._conn.commit()
        cur.close()
