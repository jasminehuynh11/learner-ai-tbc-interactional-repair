"""
Dialogue parsing utilities to extract and normalize speaker turns.
"""
import re
import json
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path


class DialogueParser:
    """Parser for extracting and normalizing dialogue turns from text."""
    
    def __init__(self):
        # Patterns for different document formats
        self.patterns = {
            'week1_week2': {
                'learner': re.compile(r'You said:\s*(.+?)(?=\n(?:English Conversational Partner said:|$))', re.DOTALL | re.IGNORECASE),
                'bot': re.compile(r'English Conversational Partner said:\s*(.+?)(?=\n(?:You said:|$))', re.DOTALL | re.IGNORECASE)
            },
            'week3': {
                'learner': re.compile(r'Você disse:\s*(.+?)(?=\n(?:English Conversational Partner disse:|$))', re.DOTALL | re.IGNORECASE),
                'bot': re.compile(r'English Conversational Partner disse:\s*(.+?)(?=\n(?:Você disse:|$))', re.DOTALL | re.IGNORECASE)
            }
        }
    
    def clean_text(self, text: str) -> str:
        """Remove extra whitespace and normalize text."""
        # Remove multiple spaces
        text = re.sub(r'\s+', ' ', text)
        # Remove leading/trailing whitespace
        text = text.strip()
        # Remove timestamps (common patterns)
        text = re.sub(r'\d{1,2}:\d{2}(?::\d{2})?(?:\s*(?:AM|PM))?', '', text)
        return text.strip()
    
    def parse_week1_week2(self, text: str) -> List[Dict[str, any]]:
        """Parse Week1 and Week2 format."""
        turns = []
        
        # Process line by line to maintain order and handle unlabeled statements
        lines = text.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            # First check for unlabeled quoted statements (must come before labeled check)
            # These appear at the start of tasks (e.g., Task 2)
            # Handle both regular quotes (") and Unicode quotes (", ", etc.)
            # Check for any quote-like characters
            has_quoted_content = (('"' in line or '"' in line or '"' in line or '' in line or '' in line) and 
                                 not ('You said' in line or 'English Conversational Partner said' in line or 'ChatGPT said' in line))
            
            if has_quoted_content:
                # Check if this is an unlabeled statement (no "You said" in previous lines)
                has_label_before = False
                for prev_idx in range(max(0, i-5), i):
                    prev_line = lines[prev_idx].strip()
                    if 'You said' in prev_line or 'English Conversational Partner said' in prev_line or 'ChatGPT said' in prev_line:
                        has_label_before = True
                        break
                    # Check if previous line is a task header - if so, this is likely first turn
                    if re.search(r'Task\s+(?:one|two|three)', prev_line, re.IGNORECASE):
                        has_label_before = False
                        break
                
                # If no label before and next line is timestamp or bot response, it's a learner turn
                # Also check if this is the first substantial line (likely start of task)
                is_first_line = (i == 0 or 
                                (i > 0 and not lines[i-1].strip() and 
                                 all(not l.strip() or re.search(r'Task\s+(?:one|two|three)', l, re.IGNORECASE) 
                                     for l in lines[max(0, i-3):i])))
                
                if not has_label_before and i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if (re.match(r'\d{1,2}:\d{2}', next_line) or 
                        'English Conversational Partner said' in next_line or
                        'ChatGPT said' in next_line or
                        is_first_line):
                        # Extract quoted content (handle both regular and Unicode quotes)
                        # Try different quote patterns
                        quote_patterns = [
                            r'"([^"]+)"',  # Regular quotes
                            r'"([^"]+)"',  # Left/right Unicode quotes
                            r'"([^"]+)"',  # Alternative Unicode
                            r'[""]([^""]+)[""]',  # Any quote type
                        ]
                        
                        content = None
                        for pattern in quote_patterns:
                            quote_match = re.search(pattern, line)
                            if quote_match:
                                content = quote_match.group(1).strip()
                                break
                        
                        if not content:
                            # Fallback: remove all quote-like characters
                            content = re.sub(r'^["""]+|["""]+$', '', line).strip()
                            # Remove any leading special characters
                            content = re.sub(r'^[^\w]+', '', content)
                        # Remove trailing period and any remaining quote marks (regular and Unicode)
                        # Remove quotes from both ends
                        quote_chars = ['"', '"', '"', ''', ''']
                        for q in quote_chars:
                            content = content.strip(q)
                        # Remove trailing period
                        content = content.rstrip('.')
                        content = self.clean_text(content)
                        if content:
                            turns.append({
                                'turn': len(turns) + 1,
                                'speaker': 'learner',
                                'text': content,
                                '_pos': i
                            })
                        i += 1
                        continue
            
            # Check for labeled turns (You said:, English Conversational Partner said:, or ChatGPT said:)
            if 'You said' in line or 'English Conversational Partner said' in line or 'ChatGPT said' in line:
                # Extract the label and content
                if 'You said' in line:
                    speaker = 'learner'
                    # Get content after the label
                    label_pattern = r'You said[：:]\s*'
                    content_match = re.search(label_pattern + r'(.*)', line, re.IGNORECASE)
                    if content_match:
                        content = content_match.group(1).strip()
                        # Content might continue on next lines until next label or end
                        j = i + 1
                        while j < len(lines):
                            next_line = lines[j].strip()
                            # Stop if we hit a timestamp, next label, or empty line followed by label
                            if (re.match(r'\d{1,2}:\d{2}', next_line) or
                                'You said' in next_line or
                                'English Conversational Partner said' in next_line or
                                'ChatGPT said' in next_line or
                                (not next_line and j + 1 < len(lines) and 
                                 ('You said' in lines[j+1] or 'English Conversational Partner said' in lines[j+1] or 'ChatGPT said' in lines[j+1]))):
                                break
                            if next_line and not re.match(r'\d{1,2}:\d{2}', next_line):
                                content += " " + next_line
                            j += 1
                        
                        content = self.clean_text(content)
                        if content:
                            turns.append({
                                'turn': len(turns) + 1,
                                'speaker': speaker,
                                'text': content,
                                '_pos': i
                            })
                        i = j
                        continue
                
                elif 'English Conversational Partner said' in line or 'ChatGPT said' in line:
                    speaker = 'bot'
                    # Handle both "English Conversational Partner said:" and "ChatGPT said:"
                    if 'ChatGPT said' in line:
                        label_pattern = r'ChatGPT said[：:]\s*'
                    else:
                        label_pattern = r'English Conversational Partner said[：:]\s*'
                    content_match = re.search(label_pattern + r'(.*)', line, re.IGNORECASE)
                    if content_match:
                        content = content_match.group(1).strip()
                        # Content might continue on next lines
                        j = i + 1
                        while j < len(lines):
                            next_line = lines[j].strip()
                            if (re.match(r'\d{1,2}:\d{2}', next_line) or
                                'You said' in next_line or
                                'English Conversational Partner said' in next_line or
                                (not next_line and j + 1 < len(lines) and 
                                 ('You said' in lines[j+1] or 'English Conversational Partner said' in lines[j+1]))):
                                break
                            if next_line and not re.match(r'\d{1,2}:\d{2}', next_line):
                                content += " " + next_line
                            j += 1
                        
                        content = self.clean_text(content)
                        if content:
                            turns.append({
                                'turn': len(turns) + 1,
                                'speaker': speaker,
                                'text': content,
                                '_pos': i
                            })
                        i = j
                        continue
            
            i += 1
        
        # Sort by position to maintain correct order, then renumber
        turns.sort(key=lambda x: x.get('_pos', 999999))
        for idx, turn in enumerate(turns, 1):
            turn['turn'] = idx
            if '_pos' in turn:
                del turn['_pos']
        
        return turns
    
    def parse_week3(self, text: str) -> List[Dict[str, any]]:
        """Parse Week3 format (Portuguese labels)."""
        turns = []
        turn_num = 1
        
        # Split by both patterns and process in order
        pattern = re.compile(
            r'(Você disse:|English Conversational Partner disse:)\s*(.+?)(?=\n(?:Você disse:|English Conversational Partner disse:|$))',
            re.DOTALL | re.IGNORECASE
        )
        
        matches = list(pattern.finditer(text))
        
        for match in matches:
            speaker_label = match.group(1).strip()
            content = match.group(2).strip()
            
            # Determine speaker
            if 'Você disse' in speaker_label:
                speaker = 'learner'
            elif 'English Conversational Partner disse' in speaker_label:
                speaker = 'bot'
            else:
                continue
            
            # Clean content
            content = self.clean_text(content)
            
            if content:  # Only add non-empty turns
                turns.append({
                    'turn': turn_num,
                    'speaker': speaker,
                    'text': content
                })
                turn_num += 1
        
        return turns
    
    def parse_week4_pdf(self, text: str, color_data: Optional[List] = None) -> List[Dict[str, any]]:
        """
        Parse Week4 format (no labels, alternating learner/bot pattern).
        
        Week4 has no speaker labels - just alternating dialogue blocks separated by blank lines.
        Strategy:
        1. Split by blank lines to get utterance blocks
        2. First block = learner, then alternate learner/bot
        
        Args:
            text: Plain text extracted from PDF
            color_data: Not used for Week4 (ignored)
        
        Returns:
            List of dialogue turns with alternating speakers
        """
        turns = []
        turn_num = 1
        
        # Strategy: Split by lines, merge continuations, then alternate speakers
        # Week4 PDF has each utterance on one or more consecutive lines
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        
        utterance_blocks = []
        current_block = []
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            
            # Skip headers
            if re.search(r'(?:Week4|Task\s*\d+:)', line_stripped, re.IGNORECASE):
                # Save current block before header
                if current_block:
                    block_text = ' '.join(current_block).strip()
                    if block_text and len(block_text) > 5:
                        utterance_blocks.append(block_text)
                    current_block = []
                continue
            
            # Skip all-caps headers
            if line_stripped.isupper() and len(line_stripped) < 50:
                continue
            
            # Check if this line is a continuation of previous
            # Continuation indicators:
            # 1. Line doesn't start with capital letter (likely continuation)
            # 2. Previous line doesn't end with punctuation (incomplete sentence)
            # 3. Line is very short (< 5 words, likely continuation)
            is_continuation = False
            if current_block:
                prev_line = current_block[-1]
                prev_ends_punct = prev_line.rstrip().endswith(('.', '!', '?'))
                starts_capital = line_stripped and line_stripped[0].isupper()
                word_count = len(line_stripped.split())
                
                is_continuation = (
                    (not prev_ends_punct and not starts_capital) or
                    (word_count < 5 and not starts_capital) or
                    (not prev_ends_punct and word_count < 8)
                )
            
            if is_continuation and current_block:
                # Merge with previous block
                current_block.append(line_stripped)
            else:
                # Save previous block and start new one
                if current_block:
                    block_text = ' '.join(current_block).strip()
                    if block_text and len(block_text) > 5:
                        utterance_blocks.append(block_text)
                current_block = [line_stripped]
        
        # Add final block
        if current_block:
            block_text = ' '.join(current_block).strip()
            if block_text and len(block_text) > 5:
                utterance_blocks.append(block_text)
        
        # Assign speakers by alternation
        # Block 0 = learner, Block 1 = bot, Block 2 = learner, etc.
        for i, block_text in enumerate(utterance_blocks):
            cleaned = self.clean_text(block_text)
            if not cleaned or len(cleaned) < 5:
                continue
            
            # Alternate: even index (0, 2, 4...) = learner, odd (1, 3, 5...) = bot
            speaker = 'learner' if i % 2 == 0 else 'bot'
            
            turns.append({
                'turn': turn_num,
                'speaker': speaker,
                'text': cleaned
            })
            turn_num += 1
        
        return turns
    
    def parse_week4_pdf_old(self, text: str, color_data: Optional[List] = None) -> List[Dict[str, any]]:
        """
        Parse Week4 format (red text = human, black text = bot).
        
        Args:
            text: Plain text extracted from PDF
            color_data: Optional list of character data with color information from pdfplumber
        """
        turns = []
        turn_num = 1
        
        if color_data:
            # Use color information to determine speakers
            # Red text (RGB values close to [1, 0, 0] or similar) = learner
            # Black text (RGB values close to [0, 0, 0] or None) = bot
            
            for page_chars in color_data:
                current_text = ""
                current_color = None
                current_speaker = None
                
                for char_info in page_chars:
                    char = char_info.get('text', '')
                    color = char_info.get('color')
                    
                    # Determine if color is red (human/learner)
                    is_red = False
                    if color:
                        # Check if color is red (RGB values)
                        if isinstance(color, (list, tuple)) and len(color) >= 3:
                            r, g, b = color[0], color[1], color[2]
                            # Red if R is significantly higher than G and B
                            is_red = r > 0.5 and g < 0.3 and b < 0.3
                    
                    # Determine speaker based on color
                    speaker = 'learner' if is_red else 'bot'
                    
                    # If speaker changed, save previous turn
                    if current_speaker and speaker != current_speaker and current_text.strip():
                        cleaned = self.clean_text(current_text)
                        if cleaned:
                            turns.append({
                                'turn': turn_num,
                                'speaker': current_speaker,
                                'text': cleaned
                            })
                            turn_num += 1
                        current_text = char
                    else:
                        current_text += char
                    
                    current_speaker = speaker
                
                # Add final turn from page
                if current_text.strip():
                    cleaned = self.clean_text(current_text)
                    if cleaned:
                        turns.append({
                            'turn': turn_num,
                            'speaker': current_speaker or 'bot',
                            'text': cleaned
                        })
                        turn_num += 1
        else:
            # Fallback: Use plain text with heuristics
            # Week4 appears to have alternating speakers without labels
            # The text may be concatenated, so we need to split by sentences
            
            # First, try to split by line breaks
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            
            # Filter out headers/titles more carefully
            filtered_lines = []
            skip_next = False
            for i, line in enumerate(lines):
                # Skip obvious headers (but keep the content after them)
                line_lower = line.lower()
                if any(skip in line_lower for skip in ['week4', 'task 1:', 'task 2:', 'task 3:']):
                    # Skip the header line itself, but don't skip the next line
                    continue
                if len(line) < 3:  # Skip very short lines
                    continue
                # Skip lines that are just headers (all caps, very short)
                if line.isupper() and len(line) < 30:
                    continue
                filtered_lines.append(line)
            
            # Merge lines that are continuations
            # Strategy: Look for sentence boundaries (., !, ?) followed by capital letters
            merged_lines = []
            current_turn = ""
            
            for line in filtered_lines:
                cleaned = self.clean_text(line)
                if not cleaned or len(cleaned) < 3:
                    continue
                
                # Skip headers more aggressively
                if re.search(r'(?:Week4|Task\s*\d+:)', cleaned, re.IGNORECASE):
                    continue
                
                # Check if this is a continuation of previous line
                is_continuation = False
                if current_turn:
                    prev_ends_punct = current_turn.rstrip().endswith(('.', '!', '?'))
                    starts_capital = cleaned and cleaned[0].isupper()
                    word_count = len(cleaned.split())
                    
                    # It's a continuation if:
                    # 1. Previous doesn't end with punctuation AND this doesn't start with capital
                    # 2. OR this is very short (< 4 words) and doesn't start with capital
                    # 3. OR previous ends with lowercase and this starts with lowercase
                    is_continuation = (
                        (not prev_ends_punct and not starts_capital) or
                        (word_count < 4 and not starts_capital) or
                        (not prev_ends_punct and word_count < 6)
                    )
                
                if is_continuation and current_turn:
                    # Merge with previous
                    current_turn += " " + cleaned
                else:
                    # Save previous turn if exists
                    if current_turn:
                        merged_lines.append(current_turn)
                    current_turn = cleaned
            
            # Add last turn
            if current_turn:
                merged_lines.append(current_turn)
            
            # Now parse the merged lines with better heuristics
            for i, line in enumerate(merged_lines):
                cleaned = self.clean_text(line)
                if not cleaned or len(cleaned) < 5:
                    continue
                
                # Determine speaker based on patterns
                is_question = cleaned.strip().endswith('?')
                word_count = len(cleaned.split())
                is_short = word_count < 12  # Reduced threshold for short statements
                starts_with_hi = cleaned.strip().lower().startswith('hi')
                starts_with_yes_no = cleaned.strip().lower().startswith(('yes', 'no', 'ok', 'okay', 'i ', 'i\'', 'i\'m', 'i\'d', 'i\'ll', 'i\'ve'))
                is_long_response = word_count > 20
                has_enthusiasm = any(word in cleaned.lower() for word in ['absolutely', 'great', 'wonderful', 'sure', 'of course', 'definitely', 'that\'s'])
                
                # Heuristics for Week4:
                # - First dialogue turn is always learner (starts with "Hi, I want...")
                # - Questions are usually learners
                # - Short statements (< 12 words) are usually learners  
                # - Statements starting with "I" are usually learners
                # - Long responses (> 20 words) are usually bots
                # - Responses with enthusiasm words are usually bots
                # - Pattern: learner -> bot -> learner -> bot (alternating)
                
                if turn_num == 1:
                    # First turn is always learner
                    speaker = 'learner'
                elif starts_with_hi and is_short:
                    # "Hi, ..." short statements are learners
                    speaker = 'learner'
                elif starts_with_yes_no and is_short:
                    # "Yes, please", "No, I don't" etc. are learners
                    speaker = 'learner'
                elif starts_with_yes_no and word_count < 5:
                    # Very short yes/no responses are learners
                    speaker = 'learner'
                elif is_question and is_short:
                    # Short questions are learners
                    speaker = 'learner'
                elif is_short and (cleaned.strip().lower().startswith('i ') or word_count < 8):
                    # Short "I" statements are learners
                    speaker = 'learner'
                elif is_long_response or has_enthusiasm:
                    # Long responses or enthusiastic responses are bots
                    speaker = 'bot'
                elif turns and turns[-1]['speaker'] == 'learner':
                    # After learner, it's bot (alternating pattern)
                    speaker = 'bot'
                elif turns and turns[-1]['speaker'] == 'bot':
                    # After bot, it's learner (alternating pattern)
                    speaker = 'learner'
                else:
                    # Default: alternate based on previous
                    if turns:
                        speaker = 'bot' if turns[-1]['speaker'] == 'learner' else 'learner'
                    else:
                        speaker = 'learner'
                
                turns.append({
                    'turn': turn_num,
                    'speaker': speaker,
                    'text': cleaned
                })
                turn_num += 1
            else:
                # Text is concatenated - split by sentence patterns
                # Look for sentence endings followed by capital letters
                import re
                # Split by sentence boundaries (., !, ?) followed by capital letter
                sentences = re.split(r'([.!?])\s+([A-Z])', text)
                
                # Reconstruct sentences
                current_sentence = ""
                for i in range(0, len(sentences), 3):
                    if i < len(sentences):
                        part = sentences[i]
                        if i + 1 < len(sentences):
                            part += sentences[i + 1]  # punctuation
                        if i + 2 < len(sentences):
                            part += " " + sentences[i + 2]  # next capital
                        current_sentence += part
                        
                        # Check if we have a complete sentence
                        if part.strip().endswith(('.', '!', '?')):
                            cleaned = self.clean_text(current_sentence)
                            if cleaned and len(cleaned) > 10:
                                # Determine speaker
                                is_question = cleaned.strip().endswith('?')
                                is_short = len(cleaned.split()) < 15
                                
                                if turn_num == 1 or (is_question and is_short):
                                    speaker = 'learner'
                                elif turns and turns[-1]['speaker'] == 'learner':
                                    speaker = 'bot'
                                else:
                                    speaker = 'learner'
                                
                                turns.append({
                                    'turn': turn_num,
                                    'speaker': speaker,
                                    'text': cleaned
                                })
                                turn_num += 1
                            current_sentence = ""
        
        return turns
    
    def split_into_tasks(self, text: str, week_num: int, expected_tasks: Optional[int] = None) -> List[Tuple[str, str]]:
        """
        Split text into separate dialogue tasks.
        Returns list of (task_name, task_text) tuples.
        Each week should have 3 tasks.
        """
        tasks = []
        
        # Look for common task markers - handle multiple formats:
        # - "TASK 1：", "TASK 2：" (full-width colon, uppercase)
        # - "Task 1:", "Task 2:", "Task 3:" (regular colon)
        # - "task 1", "task 2", "task 3" (lowercase, no colon)
        # - "Tasks:", "TASKS:" etc.
        # Pattern handles: Task/TASK/task + number + optional colon (regular or full-width) + optional newline
        # Also handles typos like "TAKS" (missing S)
        task_pattern = re.compile(
            r'(?:Task|TASK|TAKS|Tarefa|Exercise|Exercício|Activity|Atividade|Tasks|TASKS)\s*(?:(\d+)|(one|two|three|1|2|3))[：:\.]?\s*\n?',
            re.IGNORECASE | re.MULTILINE
        )
        
        # Map text numbers to digits
        text_to_num = {'one': '1', 'two': '2', 'three': '3'}
        
        # Find all task markers
        task_matches = list(task_pattern.finditer(text))
        
        target_task_count = expected_tasks or 3

        if len(task_matches) >= target_task_count:
            # We have at least 3 tasks - use them
            split_points = []
            for match in task_matches:
                task_num_str = match.group(1) or match.group(2)
                if task_num_str:
                    # Convert text to number if needed
                    task_num = int(text_to_num.get(task_num_str.lower(), task_num_str))
                    split_points.append((match.start(), task_num))
            
            # Sort by position
            split_points.sort(key=lambda x: x[0])
            
            # Split text at these points
            for i, (pos, task_num) in enumerate(split_points):
                if i == 0:
                    # First task starts from beginning or after any header
                    start_pos = 0
                    # Skip any initial header text
                    header_end = re.search(r'Week\s*\d+|#\d+', text[:pos], re.IGNORECASE)
                    if header_end:
                        start_pos = header_end.end()
                else:
                    start_pos = split_points[i-1][0]
                
                end_pos = pos
                task_text = text[start_pos:end_pos].strip()
                
                # Clean up task text - remove task markers and headers
                task_text = re.sub(r'^(?:Task|Tarefa)\s*(?:one|two|three|\d+)[:\.]?\s*', '', task_text, flags=re.IGNORECASE | re.MULTILINE)
                task_text = re.sub(r'^Week\s*\d+\s*[-–]\s*', '', task_text, flags=re.IGNORECASE | re.MULTILINE)
                task_text = re.sub(r'^Week\d+', '', task_text, flags=re.IGNORECASE | re.MULTILINE)
                # Remove any remaining headers at the start
                task_text = re.sub(r'^[A-Z][a-z]+\s*\d+[:\.]\s*[A-Z][^a-z]*\n', '', task_text, flags=re.MULTILINE)
                
                if len(task_text) > 50:
                    tasks.append((f"T{task_num}", task_text))
            
            # Add final section (last task)
            if split_points:
                last_pos = split_points[-1][0]
                task_text = text[last_pos:].strip()
                # Remove the task marker from the text
                task_text = re.sub(r'^(?:Task|Tarefa)\s*\d+[:\.]?\s*', '', task_text, flags=re.IGNORECASE | re.MULTILINE)
                if len(task_text) > 50:
                    final_task_num = split_points[-1][1] if len(split_points) < target_task_count else target_task_count
                    tasks.append((f"T{final_task_num}", task_text))
        
        elif len(task_matches) > 0:
            # We have some tasks but less than 3 - use what we have
            split_points = [(m.start(), int(m.group(1))) for m in task_matches]
            split_points.sort(key=lambda x: x[0])
            
            for i, (pos, task_num) in enumerate(split_points):
                start_pos = split_points[i-1][0] if i > 0 else 0
                end_pos = split_points[i+1][0] if i < len(split_points) - 1 else len(text)
                task_text = text[start_pos:end_pos].strip()
                task_text = re.sub(r'^(?:Task|Tarefa)\s*\d+[:\.]?\s*', '', task_text, flags=re.IGNORECASE | re.MULTILINE)
                if len(task_text) > 50:
                    tasks.append((f"T{task_num}", task_text))
        else:
            # No clear task markers - try to split by patterns
            # Look for "Task 1", "Task 2", "Task 3" anywhere in text
            alt_pattern = re.compile(
                r'(?:Task|Tarefa)\s*[123][:\.]',
                re.IGNORECASE
            )
            alt_matches = list(alt_pattern.finditer(text))
            
            if len(alt_matches) >= 2:
                # Split by these markers
                for i, match in enumerate(alt_matches):
                    start = match.start() if i == 0 else alt_matches[i-1].start()
                    end = alt_matches[i+1].start() if i < len(alt_matches) - 1 else len(text)
                    task_text = text[start:end].strip()
                    if len(task_text) > 50:
                        tasks.append((f"T{i+1}", task_text))
            else:
                # Last resort: split by major section breaks (double newlines or clear separators)
                # Try to find 3 natural breaks
                sections = re.split(r'\n\s*\n{2,}|\n(?=[A-Z][a-z]{10,})', text)
                sections = [s.strip() for s in sections if len(s.strip()) > 100]
                
                if len(sections) >= 3:
                    # Take first 3 substantial sections
                    for i, section in enumerate(sections[:3], 1):
                        tasks.append((f"T{i}", section))
                elif len(sections) > 0:
                    # Use what we have
                    for i, section in enumerate(sections, 1):
                        tasks.append((f"T{i}", section))
                else:
                    # Single task - but we expect 3, so try to split evenly
                    # This is a fallback
                    text_len = len(text)
                    chunk_size = text_len // 3
                    for i in range(3):
                        start = i * chunk_size
                        end = (i + 1) * chunk_size if i < 2 else text_len
                        task_text = text[start:end].strip()
                        if len(task_text) > 50:
                            tasks.append((f"T{i+1}", task_text))
        
        # Ensure we have exactly 3 tasks
        if len(tasks) > target_task_count:
            # Take first N
            tasks = tasks[:target_task_count]
        elif target_task_count and len(tasks) < target_task_count and len(tasks) > 0:
            # If we have fewer than 3, we'll use what we have
            # But ideally we should have 3
            pass
        
        return tasks
    
    def save_dialogue_json(
        self,
        turns: List[Dict],
        output_path: str,
        student_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Save dialogue turns to JSON file."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Add metadata if student_id is provided
        if metadata:
            output_data = {**metadata, 'turns': turns}
            if student_id and 'student_id' not in output_data:
                output_data['student_id'] = student_id
        elif student_id is not None:
            output_data = {
                'student_id': student_id,
                'turns': turns
            }
        else:
            output_data = turns
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"Saved dialogue to: {output_path} ({len(turns)} turns)")


def parse_dialogue(text: str, week_format: str) -> List[Dict[str, any]]:
    """
    Convenience function to parse dialogue based on week format.
    
    Args:
        text: Raw text content
        week_format: 'week1', 'week2', 'week3', or 'week4'
    
    Returns:
        List of dialogue turns
    """
    parser = DialogueParser()
    
    if week_format in ['week1', 'week2']:
        return parser.parse_week1_week2(text)
    elif week_format == 'week3':
        return parser.parse_week3(text)
    elif week_format == 'week4':
        return parser.parse_week4_pdf(text)
    else:
        raise ValueError(f"Unknown week format: {week_format}")

