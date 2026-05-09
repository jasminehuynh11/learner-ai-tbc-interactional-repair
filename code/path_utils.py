"""
Shared path helpers for repair workflow scripts.

Canonical runtime data location is repository-root data/.
Legacy code/data is still supported for backward compatibility.
"""
from __future__ import annotations

import os
from pathlib import Path


CODE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = CODE_ROOT.parent

CANONICAL_DATA_ROOT = REPO_ROOT / "data"
LEGACY_DATA_ROOT = CODE_ROOT / "data"
RUNTIME_SUBDIRS = ("raw", "extracted_text", "processed", "repairs")


def _has_runtime_data(data_root: Path) -> bool:
    """Return True when runtime directories exist under the given root."""
    return any((data_root / subdir).exists() for subdir in RUNTIME_SUBDIRS)


def get_data_root() -> Path:
    """
    Resolve runtime data root.

    Priority:
    1) LAR_DATA_ROOT environment override
    2) Canonical repository-root data/ when it has runtime data
    3) Legacy code/data when canonical data/ only has publication docs
    4) Canonical repository-root data/ as default
    """
    env_override = os.getenv("LAR_DATA_ROOT")
    if env_override:
        return Path(env_override).expanduser().resolve()

    canonical_has_runtime_data = _has_runtime_data(CANONICAL_DATA_ROOT)
    legacy_has_runtime_data = _has_runtime_data(LEGACY_DATA_ROOT)

    if canonical_has_runtime_data:
        return CANONICAL_DATA_ROOT

    if legacy_has_runtime_data:
        print(
            "[WARN] Using legacy data path at code/data/. "
            "Please migrate runtime files to repository-root data/."
        )
        return LEGACY_DATA_ROOT

    return CANONICAL_DATA_ROOT


def resolve_data_subpath(relative_path: str) -> Path:
    """
    Resolve a path under the active data root.

    Supports both legacy config values like "data/processed" and canonical
    values like "processed".
    """
    normalized = relative_path.replace("\\", "/").strip()
    if normalized.startswith("data/"):
        normalized = normalized[len("data/"):]
    return get_data_root() / normalized
