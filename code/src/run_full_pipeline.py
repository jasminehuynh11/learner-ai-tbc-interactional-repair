"""
Unified pipeline for processing new student data.
Handles: text extraction -> dialogue processing -> repair detection

================================================================================
CODE ORGANIZATION - FOR NON-CODING USERS
================================================================================

This pipeline uses a modular structure where code is organized in the 'scripts/'
directory. This organization makes the code easier to maintain and understand.

MODULE STRUCTURE:
-----------------
The pipeline code is split into several modules, each with a specific purpose:

1. scripts/document_extractor.py
   - Extracts text from Word (.docx) and PDF files
   - Handles different file formats and encoding
   - Main functions: extract_text_from_docx(), extract_text_from_pdf()

2. scripts/dialogue_parser.py
   - Parses extracted text into structured dialogue turns
   - Identifies learner and bot turns using pattern matching
   - Main class: DialogueParser

3. scripts/preprocessing_pipeline.py
   - Orchestrates the entire preprocessing workflow
   - Coordinates text extraction and dialogue parsing
   - Handles configuration and file organization
   - Main function: run_pipeline()

4. scripts/repair_detector_gpt.py
   - Detects repair sequences using OpenAI GPT-4o
   - Implements the repair detection codebook framework
   - Main functions: detect_repairs_gpt(), validate_repair_annotation(), save_repair_annotations()

6. generate_all_repairs_json.py (root directory)
   - Consolidates all repair data into a single JSON file
   - Creates the final all_repairs.json dataset
   - Main function: generate_all_repairs_json()

HOW THE PIPELINE WORKS:
-----------------------
1. Text Extraction: Raw Word/PDF files → Plain text files
2. Dialogue Processing: Plain text → Structured JSON dialogues
3. Repair Detection: Dialogues → Repair annotations (JSON)
4. Consolidation: All repair files → Single all_repairs.json file

WHERE TO FIND FUNCTIONALITY:
----------------------------
- Text extraction: scripts/document_extractor.py
- Dialogue parsing: scripts/dialogue_parser.py
- Full preprocessing workflow: scripts/preprocessing_pipeline.py
- Repair detection: scripts/repair_detector_gpt.py
- Data consolidation: generate_all_repairs_json.py

This main file (run_full_pipeline.py) imports and orchestrates all these modules
to provide a simple command-line interface for processing student data.

================================================================================

Usage:
    # Process specific students and weeks
    python run_full_pipeline.py --student 18 26 32 36 --week 1 2 3 4
    
    # Process all new files (auto-discover from config)
    python run_full_pipeline.py --all
    
    # Process with force (reprocess existing files)
    python run_full_pipeline.py --student 18 --week 2 --force
    
    # Skip repair detection (only preprocessing)
    python run_full_pipeline.py --student 18 --week 2 --skip-repairs
"""
import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

# Configure output encoding for Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = Path(__file__).parent.parent  # Go up one level from src/ to project root

# Add scripts to path
sys.path.insert(0, str(PROJECT_ROOT / 'scripts'))
sys.path.insert(0, str(PROJECT_ROOT))

from path_utils import get_data_root
from preprocessing_pipeline import run_pipeline as run_preprocessing
from repair_detector_gpt import detect_repairs_gpt, get_openai_client, save_repair_annotations, validate_repair_annotation
from openai import OpenAI

# Import consolidation function
try:
    from generate_all_repairs_json import generate_all_repairs_json
except ImportError:
    generate_all_repairs_json = None
DATA_ROOT = get_data_root()
PROCESSED_DIR = DATA_ROOT / "processed"
REPAIRS_DIR = DATA_ROOT / "repairs"

# Task topic classification (integrated from task_classifier.py)
TASK_TOPICS = {
    "Ordering Coffee at a Café": [
        "coffee", "café", "cafe", "latte", "espresso", "cappuccino", 
        "matcha", "order", "drink", "barista", "menu"
    ],
    "Booking a Restaurant Table": [
        "restaurant", "table", "reservation", "book", "dinner", 
        "reserve", "seating", "party", "guests"
    ],
    "Returning or Exchanging Clothes": [
        "return", "exchange", "clothes", "clothing", "refund", 
        "store", "policy", "receipt"
    ],
    "Visiting a Medical Clinic": [
        "medical", "clinic", "doctor", "appointment", "toothache", 
        "dentist", "health", "symptom", "pain"
    ],
    "Visiting a Bank": [
        "bank", "banking", "account", "deposit", "withdraw", 
        "balance", "transaction", "card"
    ],
    "Enquiring About a Rental Property": [
        "rental", "property", "apartment", "house", "rent", 
        "inspection", "lease", "landlord"
    ],
    "Reporting an Internet Outage": [
        "internet", "outage", "connection", "wifi", "router", 
        "network", "online", "signal"
    ],
    "Reporting a Lost Item": [
        "lost", "item", "police", "report", "missing", 
        "found", "belongings"
    ],
    "Requesting Maintenance or Repairs": [
        "maintenance", "repair", "fix", "broken", "issue", 
        "problem", "service", "technician"
    ],
    "Seeking Technical Support": [
        "technical", "support", "device", "help", "troubleshoot", 
        "error", "software", "hardware"
    ],
    "Discussing Study or Career Plans": [
        "study", "career", "advisor", "university", "education", 
        "overseas", "abroad", "program", "course"
    ],
    "Participating in Group Decisions": [
        "group", "decision", "negotiate", "discuss", "meeting", 
        "team", "agree", "consensus"
    ],
    "Responding to Feedback": [
        "feedback", "review", "performance", "evaluation", 
        "improve", "suggestions"
    ]
}


def classify_task_topic(dialogue_data: Dict[str, Any]) -> Optional[str]:
    """
    Classify the task topic based on dialogue content.
    
    Args:
        dialogue_data: Dialogue JSON with turns
    
    Returns:
        Task topic string or None if not identifiable
    """
    # Combine all turn text
    all_text = " ".join([
        turn.get('text', '') for turn in dialogue_data.get('turns', [])
    ]).lower()
    
    # Score each topic
    topic_scores = {}
    for topic, keywords in TASK_TOPICS.items():
        score = sum(1 for keyword in keywords if keyword in all_text)
        if score > 0:
            topic_scores[topic] = score
    
    if not topic_scores:
        return None
    
    # Return topic with highest score
    return max(topic_scores.items(), key=lambda x: x[1])[0]


def add_task_topic_to_dialogue(dialogue_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add task_topic field to dialogue data.
    
    Args:
        dialogue_data: Dialogue JSON
    
    Returns:
        Dialogue JSON with task_topic added
    """
    dialogue_data = dialogue_data.copy()
    task_topic = classify_task_topic(dialogue_data)
    if task_topic:
        dialogue_data['task_topic'] = task_topic
    return dialogue_data


def load_dialogue_json(file_path: Path) -> Dict[str, Any]:
    """Load a dialogue JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def process_repair_detection(
    dialogue_files: List[Path],
    repairs_dir: Path,
    client: Optional[OpenAI] = None,
    model: str = "gpt-4o",
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Process repair detection for a list of dialogue files using OpenAI GPT.
    
    Returns:
        Summary dictionary with success/failure counts
    """
    if client is None:
        if verbose:
            print("\nInitializing OpenAI API...")
        try:
            client = get_openai_client()
            if verbose:
                print(f"  [OK] Using model: {model}")
        except Exception as e:
            print(f"  [ERROR] Failed to initialize OpenAI API: {e}")
            return {"successful": 0, "failed": len(dialogue_files), "errors": [str(e)]}
    
    successful = 0
    failed = 0
    errors = []
    
    for dialogue_file in dialogue_files:
        if verbose:
            print(f"\nProcessing: {dialogue_file.name}")
        
        try:
            # Load dialogue
            dialogue_data = load_dialogue_json(dialogue_file)
            
            # Add dialogue_id if not present
            if 'dialogue_id' not in dialogue_data:
                filename = dialogue_file.stem
                student_id = dialogue_data.get('student_id', 'UNKNOWN')
                dialogue_data['dialogue_id'] = f"{filename}_S{student_id}"
            
            # Add task_topic
            dialogue_data = add_task_topic_to_dialogue(dialogue_data)
            if verbose and 'task_topic' in dialogue_data:
                print(f"  Task topic: {dialogue_data['task_topic']}")
            
            # Detect repairs using GPT
            if verbose:
                print(f"  Detecting repairs in {len(dialogue_data['turns'])} turns...")
            repairs = detect_repairs_gpt(dialogue_data, model=model, client=client)
            
            # Validate repairs
            dialogue_id = dialogue_data['dialogue_id']
            valid_repairs = []
            for repair in repairs:
                is_valid, warnings = validate_repair_annotation(repair, dialogue_id, dialogue_data)
                if is_valid:
                    valid_repairs.append(repair)
            
            # Save repairs
            repairs_dir.mkdir(parents=True, exist_ok=True)
            output_file = repairs_dir / f"{dialogue_file.stem}_repairs.json"
            save_repair_annotations(valid_repairs, output_file)
            
            if verbose:
                print(f"  Found {len(valid_repairs)} repair sequence(s)")
                print(f"  Saved to: {output_file}")
            
            successful += 1
            
        except Exception as e:
            error_msg = f"Failed to process {dialogue_file.name}: {e}"
            errors.append(error_msg)
            if verbose:
                print(f"  [ERROR] {error_msg}")
            failed += 1
    
    return {
        "successful": successful,
        "failed": failed,
        "errors": errors
    }


def run_full_pipeline(
    selected_students: Optional[List[int]] = None,
    selected_weeks: Optional[List[int]] = None,
    force: bool = False,
    skip_repairs: bool = False,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Run the complete pipeline: preprocessing + repair detection.
    
    Args:
        selected_students: List of student IDs to process (None = all)
        selected_weeks: List of week numbers to process (None = all)
        force: Reprocess files even if outputs are newer
        skip_repairs: Skip repair detection step
        verbose: Print detailed progress
    
    Returns:
        Summary dictionary with processing results
    """
    print("=" * 80)
    print("FULL PIPELINE: PREPROCESSING + REPAIR DETECTION")
    print("=" * 80)
    print(f"Data root: {DATA_ROOT}")
    
    # Step 1: Preprocessing
    print("\n" + "=" * 80)
    print("STEP 1: PREPROCESSING (Text Extraction + Dialogue Processing)")
    print("=" * 80)
    
    preprocessing_summary = run_preprocessing(
        selected_students=selected_students,
        selected_weeks=selected_weeks,
        force=force,
        verbose=verbose
    )
    
    if not skip_repairs:
        # Step 2: Repair Detection
        print("\n" + "=" * 80)
        print("STEP 2: REPAIR DETECTION")
        print("=" * 80)
        
        # Find processed dialogue files
        if selected_students:
            dialogue_files = []
            for student_id in selected_students:
                if selected_weeks:
                    for week in selected_weeks:
                        pattern = f"S{student_id}_W{week}_T*.json"
                        dialogue_files.extend(sorted(PROCESSED_DIR.glob(pattern)))
                else:
                    pattern = f"S{student_id}_W*_T*.json"
                    dialogue_files.extend(sorted(PROCESSED_DIR.glob(pattern)))
            dialogue_files = sorted(set(dialogue_files))
        else:
            # Get all new format files
            dialogue_files = sorted(PROCESSED_DIR.glob('S*_W*_T*.json'))
        
        # Filter by weeks if specified
        if selected_weeks and selected_students is None:
            filtered_files = []
            for week in selected_weeks:
                pattern = f"S*_W{week}_T*.json"
                filtered_files.extend(PROCESSED_DIR.glob(pattern))
            dialogue_files = sorted(set(filtered_files))
        
        # Filter out repair files
        dialogue_files = [f for f in dialogue_files if '_repairs.json' not in f.name]
        
        if not dialogue_files:
            print("\n[WARNING] No dialogue files found to process for repair detection")
            repair_summary = {"successful": 0, "failed": 0, "errors": []}
        else:
            if verbose:
                print(f"\nFound {len(dialogue_files)} dialogue file(s) to process")
            
            repair_summary = process_repair_detection(
                dialogue_files=dialogue_files,
                repairs_dir=REPAIRS_DIR,
                client=None,  # Will be created inside
                model="gpt-4o",  # Using GPT-4o model
                verbose=verbose
            )
    else:
        repair_summary = {"successful": 0, "failed": 0, "errors": [], "skipped": True}
    
    # Step 3: Generate consolidated all repairs JSON
    if not skip_repairs and generate_all_repairs_json is not None:
        print("\n" + "=" * 80)
        print("STEP 3: GENERATING CONSOLIDATED ALL REPAIRS JSON")
        print("=" * 80)
        try:
            generate_all_repairs_json()
        except Exception as e:
            if verbose:
                print(f"  [WARNING] Failed to generate consolidated JSON: {e}")
                import traceback
                traceback.print_exc()
    
    # Final Summary
    print("\n" + "=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)
    print(f"\nPreprocessing:")
    print(f"  Processed files: {len(preprocessing_summary.get('processed', []))}")
    print(f"  Skipped files: {len(preprocessing_summary.get('skipped', []))}")
    print(f"  Errors: {len(preprocessing_summary.get('errors', []))}")
    
    if not skip_repairs:
        print(f"\nRepair Detection:")
        print(f"  Successfully processed: {repair_summary.get('successful', 0)} file(s)")
        print(f"  Failed: {repair_summary.get('failed', 0)} file(s)")
        if repair_summary.get('errors'):
            print(f"  Errors: {len(repair_summary['errors'])}")
    else:
        print(f"\nRepair Detection: SKIPPED")
    
    print("=" * 80)
    
    return {
        "preprocessing": preprocessing_summary,
        "repair_detection": repair_summary
    }


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Unified pipeline for processing student dialogue data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process specific students and weeks
  python run_full_pipeline.py --student 18 26 32 36 --week 1 2 3 4
  
  # Process all new files (auto-discover from config)
  python run_full_pipeline.py --all
  
  # Process with force (reprocess existing files)
  python run_full_pipeline.py --student 18 --week 2 --force
  
  # Skip repair detection (only preprocessing)
  python run_full_pipeline.py --student 18 --week 2 --skip-repairs
        """
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--student',
        type=int,
        nargs='+',
        help='Student ID(s) to process'
    )
    group.add_argument(
        '--all',
        action='store_true',
        help='Process all students and weeks from config'
    )
    
    parser.add_argument(
        '--week',
        type=int,
        nargs='+',
        help='Week number(s) to process (default: all weeks)'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Reprocess files even if outputs are newer than sources'
    )
    
    parser.add_argument(
        '--skip-repairs',
        action='store_true',
        help='Skip repair detection step (only run preprocessing)'
    )
    
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Reduce output verbosity'
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    
    selected_students = None if args.all else args.student
    selected_weeks = args.week
    force = args.force
    skip_repairs = args.skip_repairs
    verbose = not args.quiet
    
    run_full_pipeline(
        selected_students=selected_students,
        selected_weeks=selected_weeks,
        force=force,
        skip_repairs=skip_repairs,
        verbose=verbose
    )


if __name__ == "__main__":
    main()

