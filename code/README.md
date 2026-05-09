# Code Folder

This folder contains the repair-analysis workflow components.

- `src/` - orchestration and consolidation scripts.
- `scripts/` - extraction, parsing, and LLM-assisted repair detection modules.
- `config/` - preprocessing configuration and few-shot examples.

Path policy:
- Runtime input/output data uses repository-root `data/`.
- `code/data/` is treated as legacy and only used as a fallback for older local setups.
- Optional override: set `LAR_DATA_ROOT` to point runtime scripts at a custom data location.

Model and prompt details are documented in `../docs/LLM_USE_DISCLOSURE.md`.

