# Interactional Repair in Learner-AI Task-Based Conversations: Replication Package

This repository is the publication package for the repair-focused analyses reported in the manuscript (Methods and Findings sections on interactional repair).

Manuscript title:
- `Interactional Repair in Learner-AI Task-Based Conversations: Patterns of Initiation, Resolution and Participation`

Author order for dataset citation:
1. Yeong-Ju Lee
2. Vanessa Enríquez Raído
3. Mark Dras
4. Michael Proctor
5. Peter Roger

It is curated for Zenodo deposit and includes:

- Reproduction code and configuration used for preprocessing and repair coding.
- Frozen analysis outputs used in the reported findings.
- Human-validation documentation templates and required metadata structure.
- Data governance and access guidance for sensitive materials.

## Scope

Included scope is limited to interactional repair analysis. Out-of-scope analyses (for example, proficiency and self-assessment streams) are excluded from this package.

## Repository Layout

- `code/` - Reproduction code (`src`, `scripts`, `config`) for repair workflow.
- `data/` - Publication-approved de-identified extracted text and coded repair JSON guidance.
- `results/` - Frozen tables and statistics used in manuscript reporting.
- `validation/` - Human validation files (two-coder confirmation plus supplementary batch-pipeline screening).
- `docs/` - Data governance, model disclosure, and journal submission support docs.

## Reproduction Overview

Runtime path policy:
- Canonical runtime data root is repository-level `data/` (for example, `data/raw`, `data/processed`, `data/repairs`).
- Legacy `code/data/` is still supported for backward compatibility, but migration to `data/` is recommended.

1. Install dependencies:
   - `pip install -r requirements.txt`
2. Set environment variables:
   - `OPENAI_API_KEY`
   - `GEMINI_API_KEY` (if Gemini path is used)
3. Run the repair pipeline from `code/src/`:
   - `python run_full_pipeline.py --all`
4. Rebuild consolidated repairs:
   - `python generate_all_repairs_json.py`
5. Use frozen files in `results/` for manuscript-aligned values.

## Migration Note

If your existing workflow writes files under `code/data/`, move runtime folders to repository-root `data/`:

- `code/data/raw` -> `data/raw`
- `code/data/extracted_text` -> `data/extracted_text`
- `code/data/processed` -> `data/processed`
- `code/data/repairs` -> `data/repairs`

## Data Availability and Privacy

This package follows a derived-data-first sharing approach for privacy protection.

- Publicly shareable derived outputs are included in `results/`.
- De-identified extracted text and coded repair JSON should be included under `data/` after identifier removal checks.
- Sensitive conversation-level materials should only be shared if ethics approval and participant consent allow it.
- See `docs/DATA_AVAILABILITY.md` and `docs/ETHICS_AND_PRIVACY.md`.

## LLM Transparency

LLM use, model roles, and disclosure language draft are provided in:

- `docs/LLM_USE_DISCLOSURE.md`

## Human Validation Materials

Validation files and exclusion-audit documentation are in:

- `validation/README.md`
- `validation/data_cleaning_summary.md`
- `validation/exclusions_from_human_review.csv`
- `validation/validation_protocol.md`
- `validation/validation_dates_metadata.csv`
- `validation/validation_agreement_note.md`
- `validation/coder1_annotations.csv`
- `validation/coder2_annotations.csv`
- `validation/coder3_annotations.csv`
- `validation/adjudication_log.csv`
- `validation/reliability_summary.csv`

## Citation

Use `CITATION.cff` for repository citation metadata. Add the minted Zenodo DOI after release.

## Study Compliance Metadata

- Ethics approval: Human Research Ethics Committee of Macquarie University (Review Reference No: `520251951264520`)
- Funding: Data Horizons Research Support Grants 2025, Data Horizons Research Centre, Macquarie University, Australia
- Competing interests: no conflict of interest declared by authors

