"""
Repair detection using OpenAI GPT-4 Turbo API.
Alternative implementation for higher-quality repair detection.
"""
import os
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

# Import the system prompt and utilities from the original repair_detector
try:
    from repair_detector import REPAIR_DETECTION_SYSTEM_PROMPT, create_user_prompt, validate_repair_annotation
    REPAIR_DETECTION_SYSTEM_PROMPT_GPT = REPAIR_DETECTION_SYSTEM_PROMPT
except ImportError:
    # Fallback: define here if import fails
    REPAIR_DETECTION_SYSTEM_PROMPT_GPT = "You are an expert analyst of learner–AI dialogues."
    def create_user_prompt(dialogue_data):
        return json.dumps(dialogue_data)
    def validate_repair_annotation(repair, dialogue_id, dialogue_data=None):
        return True, []


def get_openai_client() -> OpenAI:
    """Get OpenAI client with API key."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in environment variables")
    
    return OpenAI(api_key=api_key)


def detect_repairs_gpt(
    dialogue_data: Dict[str, Any], 
    model: str = "gpt-4o",
    client: Optional[OpenAI] = None,
    max_retries: int = 3
) -> List[Dict[str, Any]]:
    """
    Detect repair sequences using GPT-4 Turbo.
    
    Args:
        dialogue_data: Dialogue JSON with student_id, dialogue_id, and turns
        model: GPT model to use (default: gpt-4-turbo-preview)
        client: Optional OpenAI client (will create one if not provided)
    
    Returns:
        List of repair annotation dictionaries
    """
    if client is None:
        client = get_openai_client()
    
    # Create user prompt
    user_prompt = create_user_prompt(dialogue_data)
    
    dialogue_id = dialogue_data.get('dialogue_id', 'UNKNOWN')
    max_turn = len(dialogue_data.get('turns', []))
    
    # Combine system and user prompts
    system_content = REPAIR_DETECTION_SYSTEM_PROMPT_GPT
    user_content = user_prompt
    
    # Retry logic
    for attempt in range(1, max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": system_content
                    },
                    {
                        "role": "user",
                        "content": user_content
                    }
                ],
                temperature=0.1,  # Low temperature for consistent output
                max_tokens=16384,  # Ensure enough tokens for complete JSON
            )
            
            response_text = response.choices[0].message.content
            
            # Extract JSON from response
            repairs = extract_json_from_response(response_text)
            
            # Validate repairs
            valid_repairs = []
            for repair in repairs:
                is_valid, warnings = validate_repair_annotation(repair, dialogue_id, dialogue_data)
                if is_valid:
                    valid_repairs.append(repair)
                else:
                    # Log warnings for invalid repairs
                    if warnings:
                        print(f"  [WARNING] Invalid repair filtered out:")
                        for warning in warnings:
                            print(f"    - {warning}")
            
            return valid_repairs
            
        except Exception as e:
            if attempt < max_retries:
                print(f"  [RETRY] Error calling OpenAI API (attempt {attempt}/{max_retries}): {e}")
                import time
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                print(f"  [ERROR] Failed to call OpenAI API after {max_retries} attempts: {e}")
                return []
    
    return []


def extract_json_from_response(response_text: str) -> List[Dict[str, Any]]:
    """Extract JSON array from GPT response, handling markdown code blocks."""
    # Remove markdown code blocks if present
    if "```json" in response_text:
        response_text = re.sub(r'```json\s*', '', response_text)
        response_text = re.sub(r'```\s*$', '', response_text)
    elif "```" in response_text:
        response_text = re.sub(r'```\s*', '', response_text)
    
    # Try to find JSON array
    json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
    if json_match:
        response_text = json_match.group(0)
    
    # Parse JSON
    try:
        repairs = json.loads(response_text)
        if not isinstance(repairs, list):
            # If it's a dict with a 'repairs' key, extract that
            if isinstance(repairs, dict) and 'repairs' in repairs:
                repairs = repairs['repairs']
            else:
                return []
        return repairs
    except json.JSONDecodeError as e:
        print(f"Warning: Failed to parse JSON from GPT response: {e}")
        print(f"Response text (first 500 chars): {response_text[:500]}")
        return []


def compare_models(
    dialogue_data: Dict[str, Any],
    gpt_model: str = "gpt-4-turbo-preview"
) -> Dict[str, Any]:
    """
    Compare GPT and Gemini results on the same dialogue.
    Useful for A/B testing.
    """
    from repair_detector import detect_repairs, get_gemini_model
    
    results = {
        "dialogue_id": dialogue_data.get("dialogue_id"),
        "gpt": None,
        "gemini": None,
        "comparison": {}
    }
    
    # Get GPT results
    try:
        client = get_openai_client()
        gpt_repairs = detect_repairs_gpt(dialogue_data, model=gpt_model, client=client)
        results["gpt"] = {
            "count": len(gpt_repairs),
            "repairs": gpt_repairs
        }
    except Exception as e:
        results["gpt"] = {"error": str(e)}
    
    # Get Gemini results
    try:
        gemini_model = get_gemini_model()
        gemini_repairs = detect_repairs(dialogue_data, model=gemini_model)
        results["gemini"] = {
            "count": len(gemini_repairs),
            "repairs": gemini_repairs
        }
    except Exception as e:
        results["gemini"] = {"error": str(e)}
    
    # Compare if both succeeded
    if results["gpt"].get("count") is not None and results["gemini"].get("count") is not None:
        results["comparison"] = {
            "count_difference": results["gpt"]["count"] - results["gemini"]["count"],
            "gpt_only": len([r for r in results["gpt"]["repairs"] if r not in results["gemini"]["repairs"]]),
            "gemini_only": len([r for r in results["gemini"]["repairs"] if r not in results["gpt"]["repairs"]])
        }
    
    return results

