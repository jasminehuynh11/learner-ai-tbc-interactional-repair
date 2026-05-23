# LLM Use Disclosure (Detailed Draft for Appendix/Zenodo)

This document provides a detailed transparency write-up for AI-assisted methods.

## Confirmed Statement on AI-Assisted Technologies

We used OpenAI's GPT-5 via the Custom GPT interface to develop the customised AI chatbot for data collection, and OpenAI's GPT-4o to assist with automated detection and coding of repair sequences in the dialogue corpus. All LLM-generated outputs were subsequently reviewed and validated by two members of the research team. The authors take full responsibility for the content of the published article.

## Expanded Technical Description

### 1) Model roles by stage

- Data collection stage: GPT-5 (Custom GPT interface) as the conversational chatbot.
- Coding stage: GPT-4o in the coding pipeline for candidate repair annotation.

### 2) Prompting and codebook operationalisation

The coding stage uses a structured system prompt to operationalise the repair codebook into explicit decision rules, inclusion/exclusion boundaries, and constrained JSON output format.

Repository pointers:
- `code/scripts/repair_detector_gpt.py` (the 586 validated repair sequences reported in the manuscript were produced by this module using GPT-4o)
- `code/config/few_shot_examples.txt` (reference artifact illustrating coding criteria; not loaded at runtime)

### 3) Output constraints and programmatic checks

Candidate outputs are parsed and checked for:
- required schema fields,
- allowed category labels,
- turn-index validity and bounds.

Low-temperature settings are used for response consistency (`temperature = 0.1` in coding scripts).

### 4) Human validation and accountability

LLM outputs are treated as candidate coding rather than final ground truth. Final coding decisions are human-validated and adjudicated by research team members. Validation artifacts and metadata (including dates) are maintained in `validation/`.

### 5) Reproducibility note

Model outputs can vary across time and API/model updates. For auditability, this repository includes frozen derived outputs and coding workflow files.

