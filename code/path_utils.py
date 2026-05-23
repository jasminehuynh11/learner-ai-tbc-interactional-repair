"""
Shared path helpers for repair workflow scripts.

Canonical runtime data location is repository-root data/.
"""
from __future__ import annotations

import os
from pathlib import Path


CODE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = CODE_ROOT.parent

CANONICAL_DATA_ROOT = REPO_ROOT / "data"


def get_data_root() -> Path:
    """
    Resolve runtime data root.

    Priority:
    1) LAR_DATA_ROOT environment override
    2) Canonical repository-root data/
    """
    env_override = os.getenv("LAR_DATA_ROOT")
    if env_override:
        return Path(env_override).expanduser().resolve()

    return CANONICAL_DATA_ROOT


def resolve_data_subpath(relative_path: str) -> Path:
    """
    Resolve a path under the active data root.

    Supports config values like "data/processed" or "processed".
    """
    normalized = relative_path.replace("\\", "/").strip()
    if normalized.startswith("data/"):
        normalized = normalized[len("data/"):]
    return get_data_root() / normalized
