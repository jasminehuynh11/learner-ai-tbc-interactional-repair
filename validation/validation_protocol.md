# Human Validation Protocol

## Project

- Study title: `Interactional Repair in Learner-AI Task-Based Conversations: Patterns of Initiation, Resolution and Participation`
- Codebook basis: Operational repair criteria documented in `code/scripts/repair_detector.py` and study coding documentation
- Validation round: Exclusion-focused data cleaning and confirmation review (2026)

## Personnel

- Coder 1: Yeong-Ju Lee
- Coder 2: Vanessa Enríquez Raído
- Adjudication approach: Consensus confirmation between the two coders for listed exclusion cases (no disagreement recorded)

## Dates

- Coder 1 coding rounds: 2026-02-04 and 2026-02-13
- Coder 2 coding round: 2026-03-04
- Exclusion confirmation date: 2026-03-04
- Reliability computation date: Not included in this public package

## Unit of Analysis

- Repair segment definition: A sequence of turns where (1) an observable communication breakdown occurs and (2) at least one party attempts repair.
- Turn span format: `turn_indices` as integer arrays (for example, `[4,5]`)
- Inclusion criteria:
  1. Observable communication breakdown (misunderstanding, clarification request, or interactional trouble requiring resolution)
  2. At least one repair attempt (for example, reformulation, repetition, explicit clarification)
- Exclusion criteria:
  - No genuine communication trouble
  - No repair attempt
  - Conversation proceeds without interruption
  - Surface-level misalignments that do not impede mutual understanding

## Data Cleaning Procedure for Exclusions

1. Start from candidate repair exports (`repairs_export.xlsx`).
2. Search the `Brief notes` column for indicators:
   - "no genuine communication trouble"
   - "no signs of communication issues"
   - "conversation proceeded without interruption"
   - "no repair attempt"
3. Manually review all flagged cases.
4. Exclude cases that fail the operational repair definition.
5. Record each exclusion and criterion failure in `exclusions_from_human_review.csv`.

## Validation Outcome

- Candidate repairs before exclusions: 591
- Validated repairs after exclusions: 586
- Excluded cases: 5

## Outputs

- `exclusions_from_human_review.csv` (finalized exclusion register)
- `validation_dates_metadata.csv` (dates and personnel metadata)
- `validation_agreement_note.md` (agreement note from email confirmation)
- `coder1_annotations.csv` (coder 1 records for the five exclusion-review cases)
- `coder2_annotations.csv` (coder 2 records for the five exclusion-review cases)
- `adjudication_log.csv` (consensus adjudication records for the five exclusion-review cases)
- `reliability_summary.csv` (agreement metrics for the exclusion subset only)

