"""
Generate a consolidated JSON file containing all repairs from all students.
This creates a single source of truth for all repair data.
"""
import json
import sys
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

# Configure output encoding for Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

CODE_ROOT = Path(__file__).resolve().parents[1]
if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

from path_utils import get_data_root

DATA_ROOT = get_data_root()
REPAIRS_DIR = DATA_ROOT / "repairs"
OUTPUT_FILE = DATA_ROOT / "all_repairs.json"


def load_repair_file(file_path: Path) -> List[Dict[str, Any]]:
    """Load a single repair JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            repairs = json.load(f)
            # Ensure it's a list
            if not isinstance(repairs, list):
                return []
            return repairs
    except Exception as e:
        print(f"  [WARNING] Failed to load {file_path.name}: {e}")
        return []


def generate_all_repairs_json() -> Dict[str, Any]:
    """
    Generate a consolidated JSON file with all repairs from all students.
    
    Returns:
        Dictionary containing all repairs organized by dialogue
    """
    print("=" * 80)
    print("GENERATING CONSOLIDATED ALL REPAIRS JSON")
    print("=" * 80)
    
    # Get all repair files
    repair_files = sorted(REPAIRS_DIR.glob("*_repairs.json"))
    
    if not repair_files:
        print(f"[ERROR] No repair files found in {REPAIRS_DIR}")
        return {}
    
    print(f"\nFound {len(repair_files)} repair file(s)")
    
    # Collect all repairs
    all_repairs = []
    dialogues_processed = set()
    dialogues_with_repairs = 0
    dialogues_without_repairs = 0
    total_repairs = 0
    
    for repair_file in repair_files:
        repairs = load_repair_file(repair_file)
        
        # Extract dialogue_id from filename (e.g., S31_W1_T1_repairs.json -> S31_W1_T1)
        dialogue_id = repair_file.stem.replace("_repairs", "")
        dialogues_processed.add(dialogue_id)
        
        if repairs:
            dialogues_with_repairs += 1
            total_repairs += len(repairs)
            # Add all repairs from this dialogue
            all_repairs.extend(repairs)
        else:
            dialogues_without_repairs += 1
    
    # Organize by dialogue_id
    repairs_by_dialogue: Dict[str, List[Dict[str, Any]]] = {}
    for repair in all_repairs:
        dialogue_id = repair.get('dialogue_id', 'UNKNOWN')
        if dialogue_id not in repairs_by_dialogue:
            repairs_by_dialogue[dialogue_id] = []
        repairs_by_dialogue[dialogue_id].append(repair)
    
    # Organize by student_id
    import re
    from collections import defaultdict
    repairs_by_student: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        'dialogues': [],
        'repairs': []
    })
    
    for dialogue_id, repairs in repairs_by_dialogue.items():
        match = re.match(r'S(\d+)_', dialogue_id)
        if match:
            student_id = match.group(1)
            repairs_by_student[student_id]['dialogues'].append(dialogue_id)
            repairs_by_student[student_id]['repairs'].extend(repairs)
    
    # Convert defaultdict to regular dict and sort student IDs
    repairs_by_student_dict = {
        student_id: {
            'dialogues': sorted(data['dialogues']),
            'repairs': data['repairs'],
            'total_repairs': len(data['repairs']),
            'total_dialogues': len(data['dialogues'])
        }
        for student_id, data in sorted(repairs_by_student.items(), key=lambda x: int(x[0]))
    }
    
    # Create final structure
    result = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "total_dialogues": len(dialogues_processed),
            "dialogues_with_repairs": dialogues_with_repairs,
            "dialogues_without_repairs": dialogues_without_repairs,
            "total_repairs": total_repairs,
            "total_students": len(repairs_by_student_dict),
            "source_directory": str(REPAIRS_DIR)
        },
        "repairs_by_student": repairs_by_student_dict,
        "repairs_by_dialogue": repairs_by_dialogue,
        "all_repairs": all_repairs
    }
    
    # Save to file
    print(f"\nSaving consolidated repairs to: {OUTPUT_FILE}")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\n[SUCCESS] Successfully generated consolidated repairs file")
    print(f"  Total dialogues: {len(dialogues_processed)}")
    print(f"  Dialogues with repairs: {dialogues_with_repairs}")
    print(f"  Dialogues without repairs: {dialogues_without_repairs}")
    print(f"  Total repairs: {total_repairs}")
    print(f"  Total students: {len(repairs_by_student_dict)}")
    
    return result


if __name__ == "__main__":
    generate_all_repairs_json()

