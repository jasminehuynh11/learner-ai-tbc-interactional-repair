# Validation Package Requirements

This folder is for validation traceability.

Release status for this package:
- Exclusion audit files are finalized for publication (`exclusions_from_human_review.csv`, `validation_protocol.md`, `validation_agreement_note.md`, `validation_dates_metadata.csv`).
- Narrative summary of the exclusion pass is provided in `data_cleaning_summary.md`.
- `coder1_annotations.csv`, `coder2_annotations.csv`, and `adjudication_log.csv` contain the five exclusion-review records used to finalize the 591 to 586 validated-repair count.
- `coder3_annotations.csv` contains supplementary coder-3 records from an earlier Nov-Dec 2025 per-batch coding pass (non-overlapping candidate cases for additional review before later coder1/coder2 confirmation rounds). These candidate-screening notes do not modify the finalized five-case exclusion register.
- `reliability_summary.csv` reports exclusion-subset agreement metrics only (full reliability analysis is not released in this package).

## Required Files

- `data_cleaning_summary.md`
- `exclusions_from_human_review.csv`
- `validation_dates_metadata.csv`
- `validation_agreement_note.md`
- `validation_protocol.md`
- `coder1_annotations.csv`
- `coder2_annotations.csv`
- `coder3_annotations.csv`
- `adjudication_log.csv`
- `reliability_summary.csv`

## Minimum Required Fields

For coder annotation files:

- `dialogue_id`
- `repair_segment_id`
- `turn_indices`
- `initiation`
- `resolution`
- `trigger`
- `notes`
- `coder_id`
- `annotation_date`
- `codebook_version`

For adjudication:

- `dialogue_id`
- `repair_segment_id`
- `coder1_initiation`
- `coder2_initiation`
- `coder1_resolution`
- `coder2_resolution`
- `final_decision`
- `adjudicator`
- `adjudication_date`
- `rationale`

For reliability:

- `metric`
- `variable`
- `value`
- `confidence_interval`
- `n_pairs`
- `computed_by`
- `computed_date`

