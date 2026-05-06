"""
Reusable preprocessing pipeline for learner-AI dialogues.

This module can be imported (e.g., from notebooks/01_phase1_preprocessing.ipynb)
or executed as a standalone script:

    python scripts/preprocessing_pipeline.py --student 18 --week 1
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from document_extractor import (
    extract_text,
    extract_text_with_colors_from_pdf,
    save_extracted_text,
)
from dialogue_parser import DialogueParser


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "preprocessing_config.json"
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
EXTRACTED_TEXT_DIR = PROJECT_ROOT / "data" / "extracted_text"

DOC_PATTERN = re.compile(r"#(\d+)\.\s*Week\s*(\d+)", re.IGNORECASE)
SUPPORTED_SUFFIXES = {".docx", ".pdf"}


@dataclass
class DocumentRecord:
    student_id: str
    week: str
    path: Path
    suffix: str
    label_set: str
    expected_tasks: int
    notes: Optional[str] = None
    config: Dict[str, Any] = field(default_factory=dict)


def load_config(config_path: Path = CONFIG_PATH) -> Dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(
            f"Preprocessing config not found at {config_path}. "
            "Please run the setup step to create the metadata file."
        )
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def discover_documents(config: Dict[str, Any]) -> List[DocumentRecord]:
    """Scan data/raw for dialogue documents and attach metadata."""
    documents: Dict[Tuple[str, str], DocumentRecord] = {}
    label_sets = config.get("label_sets", {})
    defaults = config.get("defaults", {})
    default_label_set = defaults.get("label_set", "english_standard")
    default_tasks = defaults.get("tasks_per_week", 3)

    for file_path in RAW_DATA_DIR.rglob("*"):
        if not file_path.is_file():
            continue
        suffix = file_path.suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            continue

        match = DOC_PATTERN.search(file_path.name)
        if not match:
            continue

        student_id, week = match.group(1), match.group(2)
        student_config = config.get("students", {}).get(student_id, {})
        week_config = student_config.get("weeks", {}).get(week, {})

        # Check for week-level label_set override, then student-level, then default
        label_set = week_config.get("label_set") or student_config.get("label_set", default_label_set)
        if label_set not in label_sets:
            label_set = default_label_set

        expected_tasks = week_config.get("tasks", default_tasks)
        notes = week_config.get("notes") or student_config.get("notes")

        record = DocumentRecord(
            student_id=student_id,
            week=week,
            path=file_path,
            suffix=suffix,
            label_set=label_set,
            expected_tasks=expected_tasks,
            notes=notes,
            config=week_config,
        )

        key = (student_id, week)
        existing = documents.get(key)
        if not existing:
            documents[key] = record
            continue

        # Prefer DOCX over PDF; otherwise keep the most recent file
        if existing.suffix == ".pdf" and record.suffix == ".docx":
            documents[key] = record
        elif existing.suffix == record.suffix:
            existing_mtime = existing.path.stat().st_mtime
            new_mtime = record.path.stat().st_mtime
            if new_mtime > existing_mtime:
                documents[key] = record

    # Sort by student_id then week for deterministic processing
    sorted_docs = sorted(
        documents.values(),
        key=lambda rec: (int(rec.student_id), int(rec.week)),
    )
    return sorted_docs


def normalize_labels(text: str, learner_labels: List[str], bot_labels: List[str]) -> str:
    """Replace alternate speaker labels with the canonical ones used by the parser."""

    def replace_labels(content: str, labels: List[str], canonical: str) -> str:
        for label in labels:
            if not label:
                continue
            pattern = re.compile(re.escape(label), re.IGNORECASE)
            content = pattern.sub(canonical, content)
        return content

    text = replace_labels(text, learner_labels, "You said:")
    text = replace_labels(text, bot_labels, "English Conversational Partner said:")
    return text


def filter_skip_sections(text: str, skip_keywords: List[str]) -> Tuple[str, List[str]]:
    """
    Filter out sections containing skip keywords instead of skipping entire document.
    
    Returns:
        Tuple of (filtered_text, list_of_removed_sections_info)
    """
    if not skip_keywords:
        return text, []
    
    removed_sections = []
    filtered_text = text
    lines = text.split('\n')
    filtered_lines = []
    skip_mode = False
    skip_start_idx = None
    
    for i, line in enumerate(lines):
        line_lower = line.lower()
        contains_skip = any(keyword and keyword.lower() in line_lower for keyword in skip_keywords)
        
        if contains_skip and not skip_mode:
            # Start of skip section
            skip_mode = True
            skip_start_idx = i
            # Keep the line that contains the keyword (for context) but mark it
            removed_sections.append(f"Line {i+1}: {line[:100]}...")
        elif skip_mode:
            # Check if we should end skip mode
            # End skip mode if we find a clear dialogue marker (new task, speaker label, etc.)
            has_dialogue_marker = any(marker in line for marker in [
                'You said:', 'English Conversational Partner said:', 'Task', 'Week'
            ])
            
            if has_dialogue_marker and not any(kw.lower() in line_lower for kw in skip_keywords):
                skip_mode = False
                filtered_lines.append(line)
                removed_sections[-1] += f" -> ended at line {i+1}"
        else:
            # Normal line, keep it
            filtered_lines.append(line)
    
    # If we ended in skip mode, note it
    if skip_mode:
        removed_sections[-1] += f" -> end of document"
    
    filtered_text = '\n'.join(filtered_lines)
    return filtered_text, removed_sections


def ensure_processed_dir(config: Dict[str, Any]) -> Path:
    processed_dir = config.get("naming", {}).get("processed_dir", "data/processed")
    processed_path = (PROJECT_ROOT / processed_dir).resolve()
    processed_path.mkdir(parents=True, exist_ok=True)
    return processed_path


def should_skip_output(output_file: Path, source_file: Path, force: bool) -> bool:
    if force:
        return False
    if not output_file.exists():
        return False
    return output_file.stat().st_mtime >= source_file.stat().st_mtime


def parse_tasks_for_document(
    parser: DialogueParser,
    record: DocumentRecord,
    text: str,
    is_pdf: bool,
) -> List[Tuple[str, str]]:
    tasks = parser.split_into_tasks(
        text,
        week_num=int(record.week),
        expected_tasks=record.expected_tasks,
    )

    if tasks:
        return tasks

    # Fall back to single task if splitting failed
    return [(f"T1", text)]


def parse_turns_for_task(
    parser: DialogueParser,
    task_text: str,
    is_pdf: bool,
    pdf_color_data: Optional[List[Any]] = None,
) -> List[Dict[str, Any]]:
    if is_pdf:
        # Color data is not segmented per task, but passing it can still help detect speaker colors.
        return parser.parse_week4_pdf(task_text, color_data=pdf_color_data)

    return parser.parse_week1_week2(task_text)


def format_dialogue_metadata(
    record: DocumentRecord,
    task_idx: int,
    task_label: str,
) -> Dict[str, Any]:
    dialogue_id = f"S{record.student_id}_W{record.week}_T{task_idx}"
    return {
        "student_id": int(record.student_id),
        "week": int(record.week),
        "task": task_idx,
        "task_label": task_label,
        "dialogue_id": dialogue_id,
        "source_file": str(record.path.relative_to(PROJECT_ROOT)),
    }


def run_pipeline(
    selected_students: Optional[List[int]] = None,
    selected_weeks: Optional[List[int]] = None,
    force: bool = False,
    dry_run: bool = False,
    verbose: bool = True,
) -> Dict[str, Any]:
    """
    Run preprocessing for the requested subset (or all documents by default).
    
    Returns a summary dictionary with processed/skipped/error counts.
    """
    config = load_config()
    processed_dir = ensure_processed_dir(config)
    parser = DialogueParser()
    label_sets = config.get("label_sets", {})
    defaults = config.get("defaults", {})
    skip_keywords = defaults.get("skip_keywords", [])

    student_filter = {str(s) for s in selected_students} if selected_students else None
    week_filter = {str(w) for w in selected_weeks} if selected_weeks else None

    documents = discover_documents(config)

    summary = {
        "processed": [],
        "skipped": [],
        "errors": [],
    }

    if verbose:
        print("=" * 70)
        print("PREPROCESSING PIPELINE")
        print("=" * 70)
        print(f"Discovered {len(documents)} documents in data/raw")

    for record in documents:
        if student_filter and record.student_id not in student_filter:
            continue
        if week_filter and record.week not in week_filter:
            continue

        if verbose:
            print(f"\nStudent {record.student_id} - Week {record.week}")
            print(f"  Source: {record.path.relative_to(PROJECT_ROOT)}")

        try:
            raw_text = extract_text(str(record.path))
        except Exception as exc:
            summary["errors"].append(
                {
                    "student_id": record.student_id,
                    "week": record.week,
                    "error": f"Failed to extract text: {exc}",
                }
            )
            if verbose:
                print(f"  [ERROR] Failed extraction: {exc}")
            continue

        # Filter out sections with skip keywords instead of skipping entire document
        filtered_text, removed_sections = filter_skip_sections(raw_text, skip_keywords)
        if removed_sections:
            if verbose:
                print(f"  [INFO] Filtered {len(removed_sections)} section(s) containing skip keywords")
                for section_info in removed_sections[:3]:  # Show first 3
                    print(f"    - {section_info}")
                if len(removed_sections) > 3:
                    print(f"    ... and {len(removed_sections) - 3} more")
        
        # Use filtered text for processing
        raw_text = filtered_text
        
        # Skip if no content remains after filtering
        if not raw_text.strip() or len(raw_text.strip()) < 50:
            summary["skipped"].append(
                {
                    "student_id": record.student_id,
                    "week": record.week,
                    "reason": "No content remaining after filtering skip sections",
                }
            )
            if verbose:
                print(f"  [SKIP] No content remaining after filtering")
            continue

        # Save extracted plain text for reference
        extracted_filename = f"S{record.student_id}_W{record.week}.txt"
        extracted_path = EXTRACTED_TEXT_DIR / extracted_filename
        save_extracted_text(raw_text, str(extracted_path))

        label_set = label_sets.get(record.label_set, {})
        learner_labels = label_set.get("learner", [])
        bot_labels = label_set.get("bot", [])
        normalized_text = normalize_labels(raw_text, learner_labels, bot_labels)

        tasks = parse_tasks_for_document(
            parser=parser,
            record=record,
            text=normalized_text,
            is_pdf=record.suffix == ".pdf",
        )

        if verbose:
            print(f"  Tasks identified: {len(tasks)} (expected {record.expected_tasks})")

        pdf_color_data = None
        if record.suffix == ".pdf":
            try:
                pdf_color_data = extract_text_with_colors_from_pdf(str(record.path))
            except Exception:
                pdf_color_data = None

        for task_idx, (task_label, task_text) in enumerate(tasks, start=1):
            output_filename = f"S{record.student_id}_W{record.week}_T{task_idx}.json"
            output_path = processed_dir / output_filename

            if should_skip_output(output_path, record.path, force):
                summary["skipped"].append(
                    {
                        "student_id": record.student_id,
                        "week": record.week,
                        "task": task_idx,
                        "reason": "Up-to-date",
                    }
                )
                if verbose:
                    print(f"    [SKIP] {output_filename} is already up-to-date")
                continue

            turns = parse_turns_for_task(
                parser=parser,
                task_text=task_text,
                is_pdf=record.suffix == ".pdf",
                pdf_color_data=pdf_color_data,
            )

            if not turns:
                summary["errors"].append(
                    {
                        "student_id": record.student_id,
                        "week": record.week,
                        "task": task_idx,
                        "error": "No turns parsed",
                    }
                )
                if verbose:
                    print(f"    [WARN] No turns parsed for task {task_idx}")
                continue

            metadata = format_dialogue_metadata(record, task_idx, task_label)

            if dry_run:
                if verbose:
                    print(
                        f"    [DRY-RUN] Would save {output_filename} "
                        f"({len(turns)} turns)"
                    )
            else:
                parser.save_dialogue_json(
                    turns,
                    str(output_path),
                    metadata=metadata,
                )
                summary["processed"].append(
                    {
                        "student_id": record.student_id,
                        "week": record.week,
                        "task": task_idx,
                        "file": output_filename,
                        "turns": len(turns),
                    }
                )
                if verbose:
                    print(f"    [OK] Saved {output_filename} ({len(turns)} turns)")

    if verbose:
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Processed files : {len(summary['processed'])}")
        print(f"Skipped files   : {len(summary['skipped'])}")
        print(f"Errors          : {len(summary['errors'])}")

    return summary


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dialogue preprocessing pipeline")
    parser.add_argument(
        "--student",
        type=int,
        nargs="*",
        help="Student ID(s) to process (default: all)",
    )
    parser.add_argument(
        "--week",
        type=int,
        nargs="*",
        help="Week number(s) to process (default: all)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocess files even if outputs are newer than sources",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log actions without writing output files",
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    run_pipeline(
        selected_students=args.student,
        selected_weeks=args.week,
        force=args.force,
        dry_run=args.dry_run,
        verbose=True,
    )


if __name__ == "__main__":
    main()

