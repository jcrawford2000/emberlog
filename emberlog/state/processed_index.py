from __future__ import annotations

import hashlib
import logging
import sqlite3
from pathlib import Path
from typing import Iterable


class ProcessedIndex:
    def __init__(self, state_dir: Path):
        self.logger = logging.getLogger("emberlog.state.ProcessedIndex")
        self.logger.info("ProcessedIndex Initializing")
        self.state_dir = Path(state_dir)
        self.logger.debug(f"State Dir:{self.state_dir}")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.logger.debug("Connecting to sqlite db")
        self.db = sqlite3.connect(self.state_dir / "processed.sqlite")
        self.db.execute(
            """
      CREATE TABLE IF NOT EXISTS processed (
        fingerprint TEXT PRIMARY KEY,
        path TEXT NOT NULL,
        size INTEGER NOT NULL,
        mtime_ns INTEGER NOT NULL,
        processed_at INTEGER NOT NULL
      ) WITHOUT ROWID
    """
        )
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")

    @staticmethod
    def fingerprint(path: Path) -> str:
        st = path.stat()
        h = hashlib.sha1(f"{path}|{st.st_size}|{st.st_mtime_ns}".encode()).hexdigest()
        return h[:16]

    def is_processed(self, path: Path) -> bool:
        self.logger.debug(f"Getting Fingerprint for {path}")
        fp = self.fingerprint(path)
        self.logger.debug(f"Checking if already processed")
        cur = self.db.execute("SELECT 1 FROM processed WHERE fingerprint=?", (fp,))
        result = cur.fetchone() is not None
        self.logger.debug(f"Result:{result}")
        return result

    def mark_processed(self, path: Path) -> None:
        self.logger.debug(f"Marking {path} as processed")
        st = path.stat()
        self.logger.debug("Generating fingerprint")
        fp = self.fingerprint(path)
        self.logger.debug("Adding to db")
        self.db.execute(
            "INSERT OR REPLACE INTO processed(fingerprint, path, size, mtime_ns, processed_at) VALUES (?,?,?,?,strftime('%s','now'))",
            (fp, str(path), st.st_size, st.st_mtime_ns),
        )
        self.db.commit()

    def bulk_mark_processed(self, paths: Iterable[Path]) -> None:
        rows = []
        for p in paths:
            st = p.stat()
            rows.append((self.fingerprint(p), str(p), st.st_size, st.st_mtime_ns))
        self.db.executemany(
            "INSERT OR REPLACE INTO processed(fingerprint, path, size, mtime_ns, processed_at) VALUES (?,?,?,?,strftime('%s','now'))",
            rows,
        )
        self.db.commit()
