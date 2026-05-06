# Validation Package Requirements

This folder is for two-human validation traceability.

## Required Files

- `coder1_annotations.csv`
- `coder2_annotations.csv`
- `adjudication_log.csv`
- `reliability_summary.csv`
- `validation_protocol.md`

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

