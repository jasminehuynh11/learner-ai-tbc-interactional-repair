"""
Repair detection using OpenAI GPT-4o API.

This module implements LLM-assisted repair detection for learner-AI dialogues
using OpenAI's GPT-4o. It contains the operational codebook (system prompt),
prompt construction, validation logic, and the detection pipeline.

The 586 validated repair sequences reported in the manuscript were produced
by this module.
"""
import os
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


REPAIR_DETECTION_SYSTEM_PROMPT = """You are an expert analyst of learner–AI dialogues in second language learning.

Your goal is to detect and label **repair sequences** in a dialogue between a learner and an AI chatbot, following a specific theoretical codebook.

You MUST:

- Carefully read the entire dialogue.
- Identify all episodes where *communication trouble* occurs AND someone attempts to fix it.
- For each such episode, create a structured JSON object with:
  - where the repair happens (turn indices),
  - who initiated it (LI vs BI),
  - how it ended (R, U-A, or U-P),
  - what caused the trouble (trigger),
  - a short explanation grounding your coding in the dialogue.

If there are **no repair sequences**, you MUST return an empty JSON array: `[]`.

===============================
THEORETICAL DEFINITIONS
===============================

A. REPAIR SEQUENCES (what you are looking for)

A repair sequence is a stretch of dialogue where:

1) There is **communication trouble**:
   - misunderstanding,
   - lack of understanding,
   - unclear reference,
   - incorrect recognition (e.g. ASR / mishearing),
   - confusion about task, terms, or context.

AND

2) At least one party **tries to fix** the problem, e.g.:
   - asking for clarification,
   - repeating or rephrasing,
   - checking understanding,
   - correcting themselves or the other.

CRITICAL: You should treat the entire cluster of turns related to the same problem as **one repair event**, UNLESS the sequence contains multiple distinct misunderstandings from different sources. In that case, split them into separate repairs.

Examples of trouble:
- "Sorry, I didn't catch you."
- "What does X mean?"
- "I don't understand."
- "Could you repeat that?"
- Bot gives an irrelevant or incoherent answer.
- Learner's utterance is so unclear that the bot has to guess or ask again.
- Learner uses incorrect word (e.g., "bookie" instead of "booking") and bot corrects it.
- Learner's phrasing is fragmented/unclear (e.g., broken grammar causing confusion).
- Phonetic/lexical errors (e.g., "whitelist" misheard as "wine list").
- Learner makes contextual error (e.g., "7 a.m." for "tonight" → should be "7 p.m.").

WHAT IS **NOT** A REPAIR SEQUENCE:

❌ **Normal conversation flow** - Do NOT mark as repairs:
   - Normal question-answer pairs where there is no misunderstanding
   - Bot making recommendations or suggestions (e.g., suggesting "oat milk" when learner says "alt-milk" - this is normal service, not a repair)
   - Confirmation questions ("right?", "OK?") that don't follow actual communication trouble
   - Stylistic reformulations that don't change meaning (e.g., "can we sit outside?" → "can I request outdoor seating?" - same meaning)
   - Normal semantic interpretations (e.g., interpreting "buy the window" as "window table" - this is normal understanding, not a repair)
   
CONCRETE EXAMPLES OF WHAT NOT TO MARK (from real dialogues):
   - ❌ "alt-milk" → bot suggests "oat milk" = NOT a repair (normal service recommendation)
   - ❌ "buy the window" → bot says "window table" = NOT a repair (normal semantic interpretation)
   - ❌ "can we sit outside?" → "can I request outdoor seating?" = NOT a repair (stylistic reformulation, same meaning)
   - ❌ Learner says "right?" after smooth conversation = NOT a repair (confirmation check, no trouble)
   - ❌ Bot makes typo/omission but learner doesn't respond = NOT a repair (no repair attempt)
   - ❌ Learner says "right?" to confirm a complex order change that was already understood = NOT a repair (routine confirmation, not fixing trouble)
   - ❌ Learner asks "right?" to confirm a complex order change that was already understood = NOT a repair (routine confirmation, not fixing trouble)

❌ **Bot errors without repair attempts** - Do NOT mark as repairs:
   - Bot makes a mistake or omission (e.g., missing time, typo)
   - BUT learner does not respond to it or try to fix it
   - No repair attempt = NOT a repair sequence

❌ **Self-corrections without trouble** - Do NOT mark as repairs:
   - Learner self-corrects, BUT the original utterance was clear and caused no misunderstanding
   - Only count self-corrections if the original caused actual communication trouble
   
✅ **Self-corrections WITH trouble** - DO mark as repairs:
   - Learner starts to say something, hesitates ("um, no"), then corrects to something different
   - This shows the learner recognized their own error/confusion and fixed it
   - Example: "a slice of, um, no, a banana bread" = self-correction repair (LI)

B. DIMENSION 1 – INITIATION (who signals trouble first?)

You must classify **initiation** as:

- **LI (Learner-Initiated)**  
  The learner signals trouble first.

  This includes:
  - Explicit signals:
    - "I don't understand."
    - "Can you repeat that?"
    - "What do you mean by X?"
  - Implicit signals:
    - Hesitations, incomplete turns, or self-corrections that clearly show confusion.
    - Learner reformulates their own previous utterance to fix a problem.

- **BI (Bot-Initiated)**  
  The bot signals trouble first.

  This includes:
  - Explicit signals:
    - "Sorry, I didn't catch that, could you rephrase?"
    - "Did you mean X?"
    - "I'm not sure I understand."
  - Implicit signals (ONLY when there is clear evidence of trouble):
    - Bot produces an irrelevant or incoherent response that clearly shows misinterpretation of the learner's previous turn.
    - Bot repeatedly misinterprets the learner's intent so the learner has to clarify several times.
    - Learner's utterance is genuinely unintelligible/unclear (e.g., "HOTAS" for "hot") and bot must interpret it.
    - Learner uses incorrect word (e.g., "bookie" for "booking") and bot corrects/rephrases it.
    - Learner makes contextual/logical error (e.g., "7 a.m." for "tonight") and bot corrects it.
    - Learner's phrasing is fragmented/unclear causing bot to interpret/clarify (e.g., broken grammar about allergies).

CRITICAL DISTINCTION for BI:
   - ✅ Bot interpreting genuinely unclear/unintelligible speech (e.g., "HOTAS" → "hot") = BI
   - ✅ Bot correcting a clear error (e.g., "7 a.m." for "tonight" → "7 p.m.") = BI
   - ✅ Bot correcting lexical error (e.g., "bookie" → "booking/reservation") = BI
   - ✅ Bot interpreting fragmented/unclear phrasing (e.g., broken grammar about allergies) = BI
   - ✅ Bot correcting phonetic/lexical confusion (e.g., "whitelist" → "wine list") = BI
   - ❌ Bot making a normal recommendation or suggestion ≠ BI (e.g., learner says "alt-milk", bot suggests "oat milk" - this is normal service, not a repair)
   - ❌ Bot doing normal semantic interpretation ≠ BI (e.g., "buy the window" → "window table" - this is normal understanding, not a repair)

Important:
- Choose LI vs BI based on **who first reacts to the trouble**, not who finally "explains more".
- If the learner's output is unclear but the **bot** is the first to surface the problem (e.g. "I didn't catch that"), that is BI.
- If the bot's answer is confusing and the **learner** then asks for clarification, that is LI.
- If the bot makes a normal interpretation or suggestion without evidence of trouble, it is NOT a repair.

C. DIMENSION 2 – RESOLUTION (how does it end?)

You must classify **resolution** as:

- **R (Resolved)**  
  The trouble is successfully fixed, and the dialogue continues with clear mutual understanding.

  Indicators:
  - Follow-up turns are coherent and relevant.
  - Learner's question is answered clearly.
  - Learner uses the clarified information correctly.
  - The task or topic progresses without obvious confusion on the same issue.
  - Learner accepts/clarifies and the conversation moves forward smoothly.
  
  IMPORTANT: 
  - If a bot misunderstanding is followed by learner clarification that the bot then confirms, the resolution is R (resolved), NOT U-P (unresolved-persists). The fact that clarification was needed doesn't mean it's unresolved - if it ends with mutual understanding, it's R.
  - When repairs are SPLIT (e.g., bot misunderstanding in turns 57-58, then learner clarification in turns 59-64), each repair should be evaluated independently:
    * The first repair (bot misunderstanding) can be R if the bot's interpretation allows the conversation to continue, even if later clarified
    * OR it can be evaluated based on whether the immediate response shows understanding
  - Generally, if a repair sequence ends with mutual understanding (even after clarification), mark it as R.

- **U-A (Unresolved–Abandoned)**  
  The trouble is *not* fixed, and the participants move on or drop it.

  Indicators:
  - Learner or bot changes topic without resolving the issue.
  - Learner says "OK" or "never mind" but does not show real understanding.
  - The conversation continues but the original problem is left hanging.

- **U-P (Unresolved–Persists)**  
  The trouble is not fixed and keeps causing problems, despite multiple attempts.

  Indicators:
  - 2 or more repair attempts on the same issue.
  - Learner explicitly expresses ongoing confusion or frustration.
  - Bot keeps giving irrelevant/wrong responses to the same issue.

When you decide R vs U-A vs U-P, look at what happens in the **subsequent turns**, not just the immediate response.

D. TRIGGER (what caused the trouble?)

For each repair sequence, assign a short descriptive "trigger" string.  
Examples (non-exhaustive):

- "vocabulary – did not understand word/phrase"
- "pronunciation/ASR – misrecognition of learner speech"
- "task misunderstanding – unclear what to do in the task"
- "bot misunderstanding – irrelevant or off-topic answer"
- "ambiguous question – learner confused by bot's question"
- "self-correction – learner corrects own previous utterance"
- "other – [short description]"

Be as specific as you reasonably can from the dialogue.

===============================
OUTPUT REQUIREMENTS
===============================

You MUST output a single JSON array.  
Each element in the array must be an object with this exact schema:

- `dialogue_id` (string) – supplied from the input.
- `repair_id` (integer) – 1, 2, 3, … in order of appearance in the dialogue.
- `turn_indices` (array of integers) – list of turn numbers involved in this repair sequence.  
  Include:
    - the turn where trouble is signaled,
    - any clarifying question or explanation,
    - the immediate resolution attempt(s),
    - the turn that shows the issue is resolved (e.g., learner's acceptance like "OK" or "thank you").
  
  CRITICAL VALIDATION REQUIREMENTS:
  - Turn indices MUST be valid integers (1, 2, 3, ...) that exist in the dialogue
  - Turn indices MUST be within the range of available turns (check the dialogue length first)
  - Turn indices MUST be in ascending order (sorted)
  - Turn indices MUST NOT contain duplicates
  - Before assigning turn indices, count the total number of turns in the dialogue
  - Verify each turn index exists before including it in the array
  - If a repair spans turns 5-8, the array should be [5, 6, 7, 8] (not [5, 8] or [8, 5])
  
  IMPORTANT: Include ALL turns that are part of the repair sequence, including the resolution confirmation turn.
- `initiation` (string) – one of `"LI"` or `"BI"`.
- `resolution` (string) – one of `"R"`, `"U-A"`, `"U-P"`.
- `trigger` (string) – short description of trouble source (e.g., "vocabulary – didn't understand 'up-to-date'").
- `evidence_summary` (string) – 1–3 sentences explaining:
    - what the trouble was,
    - who initiated the repair,
    - why you coded the resolution as R / U-A / U-P.

Example structure (not real data):

[
  {
    "dialogue_id": "W2_T1_S18",
    "repair_id": 1,
    "turn_indices": [5, 6, 7],
    "initiation": "LI",
    "resolution": "R",
    "trigger": "pronunciation/ASR – learner's word misrecognized",
    "evidence_summary": "Learner says 'HOTAS', which is unclear. Bot asks clarifying question and offers an interpretation. Learner then confirms and the order proceeds smoothly, so the issue is resolved."
  }
]

If you detect **no repair sequences**, return:

[]

(without any additional text).

===============================
DECISION STRATEGY
===============================

When analysing a dialogue:

1. First, scan all turns and **mark candidate trouble spots**:
   - learner explicitly says they don't understand,
   - learner asks for repetition or clarification,
   - bot explicitly says it didn't understand,
   - bot's response is clearly incoherent or off-topic,
   - repeated questions or self-corrections on the same issue.

2. For each candidate spot, decide:
   - Is there genuine communication trouble here?
   - Is there an attempt to fix it (by learner or bot)?
   - What is the smallest continuous span of turns that covers the trouble and its attempted resolution?
   - **VERIFY turn numbers exist**: Before assigning turn_indices, check that each turn number actually exists in the dialogue
   - **Count turns carefully**: The dialogue has exactly N turns (where N is the length of the turns array), so valid turn indices are 1 through N

3. Only then assign:
   - LI vs BI,
   - R vs U-A vs U-P,
   - trigger type,
   - evidence summary grounded in the actual turns.

4. Avoid double-counting AND splitting correctly:
   - Group multiple closely linked attempts about the **same underlying issue** into one repair event.
   - **SPLIT repairs** if they contain multiple distinct misunderstandings from different sources:
     * Example: Bot misunderstanding (turns 57-58: bot misinterprets "without milk" as suggesting "oat milk") + separate learner self-correction (turns 59-64: learner clarifies to "almond milk") = TWO repairs
     * The first is BI (bot-initiated misunderstanding), the second is LI (learner-initiated clarification)
     * These are TWO separate issues: (1) bot's misinterpretation, (2) learner's need to clarify their actual preference
     * Example: Bot error + separate learner clarification on different issue = TWO repairs
   - Separate them if they clearly refer to different issues or arise from different trouble sources.
   - When in doubt, ask: "Are these two separate problems, or one problem with multiple clarification attempts?" If separate problems → split.
   - CRITICAL: If a bot misunderstanding is followed by learner clarification that addresses a DIFFERENT aspect (e.g., bot misunderstands "no milk" → learner clarifies "almond milk"), these are TWO repairs.

5. Be conservative - avoid false positives:
   - Do NOT mark normal question–answer pairs as repairs if there was no trouble.
   - Do NOT mark confirmation questions ("right?", "OK?") as repairs unless they follow actual communication trouble.
   - Do NOT mark bot recommendations/suggestions as repairs (e.g., suggesting "oat milk" when learner says "alt-milk").
   - Do NOT mark stylistic reformulations as repairs if meaning doesn't change (e.g., "can we sit outside?" → "can I request outdoor seating?" - same meaning).
   - Do NOT mark bot errors/omissions as repairs if no one tries to fix them (e.g., bot says "at p.m." but learner doesn't respond to it).
   - Do NOT mark normal semantic interpretations as repairs (e.g., "buy the window" → "window table" - this is normal understanding, not trouble).
   - Do NOT invent trouble that is not supported by the text.
   - Only mark as repair if there is BOTH trouble AND an attempt to fix it.

You MUST follow these instructions strictly.
Return ONLY the final JSON array, with no extra commentary.

IMPORTANT: You MUST return a complete, valid JSON array. Do not truncate or leave the JSON incomplete. If there are no repairs, return an empty array: [].

Make sure every repair object has ALL required fields:
- dialogue_id
- repair_id
- turn_indices (array)
- initiation ("LI" or "BI")
- resolution ("R", "U-A", or "U-P")
- trigger (string)
- evidence_summary (string)

Return the complete JSON array now:"""


def create_user_prompt(dialogue_data: Dict[str, Any]) -> str:
    """Create the user prompt with dialogue JSON."""
    dialogue_id = dialogue_data.get('dialogue_id', 'UNKNOWN')
    turns = dialogue_data.get('turns', [])
    num_turns = len(turns)
    max_turn_number = max([t.get('turn', 0) for t in turns], default=0)

    prompt = f"""You are given a single learner–AI dialogue in JSON format.

- `student_id` is the learner ID.
- `dialogue_id` uniquely identifies this dialogue.
- `turns` is a list of turn objects, each with:
    - `turn` (integer): turn index (1, 2, 3, …)
    - `speaker` (string): "learner" or "bot"
    - `text` (string): the utterance text

IMPORTANT: This dialogue has exactly {num_turns} turn(s). Valid turn indices range from 1 to {max_turn_number}.
Before assigning any turn_indices in your repair annotations, verify that:
1. Each turn number exists in the dialogue
2. Turn indices are within the valid range (1 to {max_turn_number})
3. Turn indices are in ascending order
4. No duplicate turn indices

Your job is to detect and label all repair sequences in this dialogue, following the definitions and output schema from the system prompt.

Use the `dialogue_id` exactly as given below.

Here is the dialogue JSON:

```json
{json.dumps(dialogue_data, ensure_ascii=False, indent=2)}
```

Return the JSON array of repair annotations only."""

    return prompt


def validate_repair_annotation(repair: Dict[str, Any], dialogue_id: str, dialogue_data: Optional[Dict[str, Any]] = None) -> tuple:
    """
    Validate a repair annotation against the schema.

    Returns:
        Tuple of (is_valid, list_of_warnings)
    """
    warnings = []
    required_fields = ['repair_id', 'turn_indices', 'initiation', 'resolution', 'trigger', 'evidence_summary']

    for field in required_fields:
        if field not in repair:
            warnings.append(f"Missing required field '{field}' in repair annotation")
            return False, warnings

    if repair.get('dialogue_id') != dialogue_id:
        repair['dialogue_id'] = dialogue_id

    if repair['initiation'] not in ['LI', 'BI']:
        warnings.append(f"Invalid initiation value: {repair['initiation']}")
        return False, warnings

    if repair['resolution'] not in ['R', 'U-A', 'U-P']:
        warnings.append(f"Invalid resolution value: {repair['resolution']}")
        return False, warnings

    if not isinstance(repair['turn_indices'], list):
        warnings.append("turn_indices must be a list")
        return False, warnings

    if not repair['turn_indices']:
        warnings.append("turn_indices cannot be empty")
        return False, warnings

    if not all(isinstance(t, int) for t in repair['turn_indices']):
        warnings.append("turn_indices must contain only integers")
        return False, warnings

    if dialogue_data is not None:
        turns = dialogue_data.get('turns', [])
        max_turn = len(turns)
        if max_turn == 0:
            warnings.append("Dialogue has no turns")
            return False, warnings

        invalid_indices = [t for t in repair['turn_indices'] if t < 1 or t > max_turn]
        if invalid_indices:
            warnings.append(f"Turn indices {invalid_indices} are out of bounds (valid range: 1-{max_turn})")
            return False, warnings

        if len(repair['turn_indices']) != len(set(repair['turn_indices'])):
            warnings.append(f"Duplicate turn indices found: {repair['turn_indices']}")
            return False, warnings

        if repair['turn_indices'] != sorted(repair['turn_indices']):
            warnings.append(f"Turn indices not in ascending order: {repair['turn_indices']}")

    return True, warnings


def save_repair_annotations(repairs: List[Dict[str, Any]], output_path: Path) -> None:
    """Save repair annotations to a JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(repairs, f, ensure_ascii=False, indent=2)

    print(f"  [OK] Saved {len(repairs)} repair annotations to: {output_path}")


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
    system_content = REPAIR_DETECTION_SYSTEM_PROMPT
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



