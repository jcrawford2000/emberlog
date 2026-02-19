# emberlog/versioning.py
from __future__ import annotations

import os
import subprocess
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version

PKG_NAME = "emberlog"


def get_app_version() -> str:

    # 1) If we're in a Git repo, use the tag (best for dev runs)
    try:
        desc = (
            subprocess.check_output(
                ["git", "describe", "--tags", "--dirty", "--always"],
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
        # Optional: drop leading "v" if you tag like v0.1.1
        return desc[1:] if desc.startswith("v") else desc
    except Exception:
        pass

    # 2) If installed as a package, use metadata (works for wheels/sdists)
    try:
        return pkg_version(PKG_NAME)
    except PackageNotFoundError:
        pass

    # 3) Last‑ditch: allow CI/containers to inject via env
    return os.getenv("EMBERLOG_VERSION", "0.0.0+unknown")
