from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Union


@dataclass
class LocalSink:
    base_dir: Union[str, Path]

    def write_json(self, relpath: Union[str, Path], obj: dict) -> Path:
        base = Path(self.base_dir)
        out = base / Path(relpath)
        out.parent.mkdir(parents=True, exist_ok=True)

        # atomic write
        with tempfile.NamedTemporaryFile(
            "w", dir=out.parent, delete=False, encoding="utf-8"
        ) as tmp:
            json.dump(obj, tmp, ensure_ascii=False, indent=2, default=str)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_path = Path(tmp.name)
        os.replace(tmp_path, out)
        return out
