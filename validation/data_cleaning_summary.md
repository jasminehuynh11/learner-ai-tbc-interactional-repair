# Exclusion-Based Data Cleaning Summary

## Final counts

- Candidate repair cases before exclusion review: 591
- Validated repair cases after exclusion review: 586
- Excluded cases: 5

## Operational definition used for inclusion

A sequence is retained as a repair only when both conditions are met:

1. Observable communication breakdown occurred (for example, explicit misunderstanding, clarification request, or interactional trouble requiring resolution).
2. At least one party attempted to address the breakdown (for example, reformulation, repetition, or explicit clarification).

Surface-level misalignments that did not impede mutual understanding were excluded.

## Cleaning procedure (Feb-Mar 2026 review workflow)

1. Search `repairs_export.xlsx` `Brief notes` column for the following markers:
   - `no genuine communication trouble`
   - `no signs of communication issues`
   - `conversation proceeded without interruption`
   - `no repair attempt`
2. Manually review all flagged cases.
3. Exclude any case failing the operational repair definition.

## Five excluded cases and reasoning

| Case code | Why excluded |
|---|---|
| `P2_W1_T1` (`S2_W1_T1`, turns `[4,5]`, proposed `LI-U-A`) | Brief note explicitly flagged no genuine communication trouble. No breakdown occurred, no repair was needed, and conversation continued uninterrupted. Fails criterion 1. |
| `P4_W1_T1` (`S4_W1_T1`, turns `[17,18]`, proposed `None-None`) | No misunderstanding and no repair attempt. Bot responded appropriately. There was nothing to classify for initiation or resolution. Fails criteria 1 and 2. |
| `P17_W1_T1` (`S17_W1_T1`, turns `[26,27]`, proposed `BI-R`) | Bot successfully interpreted learner mispronunciation without observable breakdown. Surface-level misalignment only. Fails criterion 1. |
| `P18_W2_T1` (`S18_W2_T1`, turns `[23,24]`, proposed `None-None`) | Learner utterance was irrelevant but did not constitute communication trouble and no repair sequence followed. Fails criteria 1 and 2. |
| `P43_W1_T1` (`S43_W1_T1`, turns `[20,21]`, proposed `BI-R`) | Bot implicitly corrected without any observable interactional breakdown. No repair action was required to restore understanding. Fails criterion 1. |

## Agreement note

- Coder 1 coding rounds: 2026-02-04 and 2026-02-13.
- Coder 2 coding round: 2026-03-04.
- Both coders reached the same conclusions for all listed exclusion cases.
