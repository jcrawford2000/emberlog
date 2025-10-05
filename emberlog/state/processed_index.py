from __future__ import annotations

import hashlib
import logging
import shutil
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
        self.logger.debug("[%s] Getting Fingerprint for %s", path.stem, path)
        fp = self.fingerprint(path)
        self.logger.debug("[%s] Checking if already processed", path.stem)
        cur = self.db.execute("SELECT 1 FROM processed WHERE fingerprint=?", (fp,))
        result = cur.fetchone() is not None
        self.logger.debug("[%s] Result:%s", path.stem, result)
        if result:
            PROCESSED_PATH = Path("/data/emberlog/processed")
            PROCESSED_PATH.mkdir(parents=True, exist_ok=True)
            dest = PROCESSED_PATH / path.name
            shutil.move(str(path), str(dest))
            self.logger.debug("[%s] Moved %s to processed folder", path.stem, path.name)
        return result

    def mark_processed(self, path: Path) -> None:
        self.logger.debug("[%s] Marking %s as processed", path.stem, path)
        st = path.stat()
        self.logger.debug("[%s] Generating fingerprint", path.stem)
        fp = self.fingerprint(path)
        self.logger.debug("[%s] Adding to db", path.stem)
        self.db.execute(
            "INSERT OR REPLACE INTO processed(fingerprint, path, size, mtime_ns, processed_at) VALUES (?,?,?,?,strftime('%s','now'))",
            (fp, str(path), st.st_size, st.st_mtime_ns),
        )
        self.db.commit()
        PROCESSED_PATH = Path("/data/emberlog/processed")
        PROCESSED_PATH.mkdir(parents=True, exist_ok=True)
        dest = PROCESSED_PATH / path.name
        shutil.move(str(path), str(dest))
        self.logger.debug("[%s] Moved %s to processed folder", path.stem, path.name)

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
