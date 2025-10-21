"""
Token estimation utility for VFP code processing.
Provides accurate token counting for determining processing strategy.
"""

import re
from typing import Dict, List, Tuple


class TokenEstimator:
    """Estimates tokens for VFP code content and prompts."""

    def __init__(self):
        # Rough estimation: 4 characters per token for English text
        # VFP code tends to be more dense, so we use 3.5 chars per token
        self.CHARS_PER_TOKEN = 3.5

        # Prompt overhead estimation
        self.SYSTEM_PROMPT_TOKENS = 200
        self.USER_PROMPT_OVERHEAD = 150
        self.CHUNKED_PROMPT_OVERHEAD = 80

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for given text.

        Args:
            text: Input text to estimate

        Returns:
            Estimated token count
        """
        if not text:
            return 0

        # Clean whitespace and count characters
        clean_text = re.sub(r'\s+', ' ', text.strip())
        char_count = len(clean_text)

        # Convert to estimated tokens
        return int(char_count / self.CHARS_PER_TOKEN)

    def estimate_file_processing_tokens(self, content: str, use_chunked_prompt: bool = False) -> Dict[str, int]:
        """
        Estimate total tokens needed for processing a file.

        Args:
            content: File content
            use_chunked_prompt: Whether to use chunked prompt template

        Returns:
            Dict with token breakdown
        """
        content_tokens = self.estimate_tokens(content)

        if use_chunked_prompt:
            prompt_overhead = self.CHUNKED_PROMPT_OVERHEAD
        else:
            prompt_overhead = self.USER_PROMPT_OVERHEAD

        total_tokens = (
            self.SYSTEM_PROMPT_TOKENS +
            prompt_overhead +
            content_tokens
        )

        return {
            'content_tokens': content_tokens,
            'system_prompt_tokens': self.SYSTEM_PROMPT_TOKENS,
            'prompt_overhead_tokens': prompt_overhead,
            'total_input_tokens': total_tokens,
            'estimated_output_tokens': int(content_tokens * 1.5),  # Estimated 50% increase with comments
            'total_estimated_tokens': total_tokens + int(content_tokens * 1.5)
        }

    def determine_processing_strategy(self, file_size: int, content: str,
                                    size_small: int = 5000,
                                    size_medium: int = 15000,
                                    max_context: int = 32768) -> Dict[str, any]:
        """
        Determine the best processing strategy based on file size and token count.

        Args:
            file_size: File size in bytes
            content: File content
            size_small: Small file threshold in bytes
            size_medium: Medium file threshold in bytes
            max_context: Maximum context length in tokens

        Returns:
            Dict with strategy information
        """
        token_info = self.estimate_file_processing_tokens(content, use_chunked_prompt=False)

        if file_size <= size_small:
            strategy = 'small'
            timeout = 120
            needs_chunking = False
        elif file_size <= size_medium:
            strategy = 'medium'
            timeout = 300
            needs_chunking = token_info['total_estimated_tokens'] > max_context * 0.8
        else:
            strategy = 'large'
            timeout = 900
            needs_chunking = True

        # Override with chunking if tokens exceed limit
        if token_info['total_estimated_tokens'] > max_context * 0.8:
            needs_chunking = True
            if strategy != 'large':
                strategy = 'medium'  # Upgrade to medium processing
                timeout = 300

        return {
            'strategy': strategy,
            'needs_chunking': needs_chunking,
            'timeout': timeout,
            'file_size': file_size,
            'token_info': token_info,
            'recommended_chunk_size': 3000 if needs_chunking else None
        }


class VFPChunker:
    """Intelligently chunks VFP code files at logical boundaries with context awareness."""

    def __init__(self, target_chunk_size: int = 3000, overlap_lines: int = 5):
        self.target_chunk_size = target_chunk_size
        self.overlap_lines = overlap_lines
        self.token_estimator = TokenEstimator()

    def find_vfp_boundaries(self, lines: List[str]) -> List[int]:
        """
        Find logical boundaries in VFP code for splitting.

        Args:
            lines: List of code lines

        Returns:
            List of line numbers that are good split points
        """
        boundaries = [0]  # Always start at beginning

        for i, line in enumerate(lines):
            line_upper = line.strip().upper()

            # Major VFP constructs that are good split points
            if (line_upper.startswith('PROCEDURE ') or
                line_upper.startswith('FUNCTION ') or
                line_upper.startswith('DEFINE CLASS ') or
                line_upper.startswith('* ============') or  # Major comment blocks
                line_upper.startswith('* ------------') or
                line_upper.startswith('*!* ') or
                (line_upper.startswith('*') and len(line.strip()) > 50)):  # Long comment lines
                boundaries.append(i)

        # Add the end
        boundaries.append(len(lines))

        # Remove duplicates and sort
        return sorted(list(set(boundaries)))

    def generate_file_overview(self, content: str, filename: str) -> str:
        """
        Generate a comprehensive file overview for context.

        Args:
            content: Full file content
            filename: Name of the file

        Returns:
            String containing file overview
        """
        lines = content.split('\n')

        # Extract procedures and functions
        procedures = []
        functions = []
        classes = []

        for line in lines:
            line_upper = line.strip().upper()
            if line_upper.startswith('PROCEDURE '):
                proc_name = line.strip().split()[1] if len(line.strip().split()) > 1 else "Unknown"
                procedures.append(proc_name)
            elif line_upper.startswith('FUNCTION '):
                func_name = line.strip().split()[1] if len(line.strip().split()) > 1 else "Unknown"
                functions.append(func_name)
            elif line_upper.startswith('DEFINE CLASS '):
                class_name = line.strip().split()[2] if len(line.strip().split()) > 2 else "Unknown"
                classes.append(class_name)

        # Generate overview - DESCRIPTIVE not prescriptive
        overview_parts = [
            f"File: {filename}",
            f"Total Lines: {len(lines)}",
            f"Estimated Tokens: {self.token_estimator.estimate_tokens(content)}"
        ]

        # Identify main file purpose from first significant comment block
        purpose = "VFP program file"
        for line in lines[:20]:  # Check first 20 lines
            if line.strip().startswith('*') and len(line.strip()) > 10:
                purpose = f"VFP program: {line.strip()[1:].strip()}"
                break

        overview_parts.insert(1, f"Purpose: {purpose}")

        # Add general structure info WITHOUT listing specific names
        structure_info = []
        if procedures:
            structure_info.append(f"contains {len(procedures)} procedure(s)")
        if functions:
            structure_info.append(f"contains {len(functions)} function(s)")
        if classes:
            structure_info.append(f"contains {len(classes)} class(es)")

        if structure_info:
            overview_parts.append(f"Structure: {', '.join(structure_info)}")
        else:
            overview_parts.append("Structure: main program code")

        return " | ".join(overview_parts)

    def get_context_info(self, all_chunks: List[Dict], current_index: int, context_lines: int = 3) -> Dict[str, str]:
        """
        Get context information for a specific chunk.

        Args:
            all_chunks: List of all chunks
            current_index: Index of current chunk
            context_lines: Number of context lines to include

        Returns:
            Dict with previous_context, current_context, next_context
        """
        context = {
            'previous_context': "",
            'current_context': "",
            'next_context': ""
        }

        # Previous context
        if current_index > 0:
            prev_chunk = all_chunks[current_index - 1]
            prev_lines = prev_chunk['content'].split('\n')
            # Get last few lines of previous chunk
            context_start = max(0, len(prev_lines) - context_lines)
            prev_context_lines = prev_lines[context_start:]
            context['previous_context'] = '\n'.join(prev_context_lines).strip()

        # Current chunk procedure context
        current_chunk = all_chunks[current_index]
        current_lines = current_chunk['content'].split('\n')

        # Find if we're in the middle of a procedure/function
        proc_context = []
        for line in current_lines[:5]:  # Check first few lines
            line_upper = line.strip().upper()
            if (line_upper.startswith('PROCEDURE ') or
                line_upper.startswith('FUNCTION ') or
                line_upper.startswith('DEFINE CLASS ')):
                proc_context.append(f"Starting: {line.strip()}")
                break

        # Check if this continues from previous chunk
        if current_index > 0 and not proc_context:
            prev_chunk = all_chunks[current_index - 1]
            prev_lines = prev_chunk['content'].split('\n')
            for line in reversed(prev_lines[-10:]):  # Check last 10 lines of prev chunk
                line_upper = line.strip().upper()
                if (line_upper.startswith('PROCEDURE ') or
                    line_upper.startswith('FUNCTION ') or
                    line_upper.startswith('DEFINE CLASS ')):
                    proc_context.append(f"Continuing: {line.strip()}")
                    break

        context['current_context'] = ' | '.join(proc_context) if proc_context else "Code block"

        # Next context
        if current_index < len(all_chunks) - 1:
            next_chunk = all_chunks[current_index + 1]
            next_lines = next_chunk['content'].split('\n')
            # Get first few lines of next chunk
            next_context_lines = next_lines[:context_lines]
            context['next_context'] = '\n'.join(next_context_lines).strip()

        return context

    def create_chunks(self, content: str) -> List[Dict[str, any]]:
        """
        Split VFP content into logical chunks.

        Args:
            content: Full file content

        Returns:
            List of chunk dictionaries
        """
        lines = content.split('\n')
        boundaries = self.find_vfp_boundaries(lines)
        chunks = []

        i = 0
        chunk_num = 1

        while i < len(boundaries) - 1:
            start_line = boundaries[i]
            end_line = boundaries[i + 1]

            # Get initial chunk
            chunk_lines = lines[start_line:end_line]
            chunk_content = '\n'.join(chunk_lines)
            chunk_tokens = self.token_estimator.estimate_tokens(chunk_content)

            # If chunk is too large, try to split further
            if chunk_tokens > self.target_chunk_size and len(chunk_lines) > 10:
                # Split at smaller boundaries (like individual procedures)
                sub_boundaries = []
                for j, line in enumerate(chunk_lines):
                    if (line.strip().upper().startswith('PROCEDURE ') or
                        line.strip().upper().startswith('FUNCTION ')):
                        sub_boundaries.append(j)

                if len(sub_boundaries) > 1:
                    # Create smaller chunks from procedures
                    for k in range(len(sub_boundaries)):
                        sub_start = sub_boundaries[k]
                        sub_end = sub_boundaries[k + 1] if k + 1 < len(sub_boundaries) else len(chunk_lines)

                        sub_chunk_lines = chunk_lines[sub_start:sub_end]
                        sub_chunk_content = '\n'.join(sub_chunk_lines)

                        chunks.append({
                            'content': sub_chunk_content,
                            'chunk_num': chunk_num,
                            'start_line': start_line + sub_start,
                            'end_line': start_line + sub_end,
                            'estimated_tokens': self.token_estimator.estimate_tokens(sub_chunk_content),
                            'line_count': len(sub_chunk_lines)
                        })
                        chunk_num += 1
                    i += 1
                    continue

            # Standard chunk creation
            chunks.append({
                'content': chunk_content,
                'chunk_num': chunk_num,
                'start_line': start_line,
                'end_line': end_line,
                'estimated_tokens': chunk_tokens,
                'line_count': len(chunk_lines)
            })

            chunk_num += 1
            i += 1

        return chunks

    def create_context_aware_chunks(self, content: str, filename: str) -> List[Dict[str, any]]:
        """
        Create chunks with full context awareness for each chunk.

        Args:
            content: Full file content
            filename: Name of the file

        Returns:
            List of context-aware chunk dictionaries
        """
        # First, create basic chunks
        base_chunks = self.create_chunks(content)

        # Generate file overview once
        file_overview = self.generate_file_overview(content, filename)

        # Enhance each chunk with context
        context_aware_chunks = []
        for i, chunk in enumerate(base_chunks):
            # Get context for this chunk
            context_info = self.get_context_info(base_chunks, i)

            # Create enhanced chunk
            enhanced_chunk = {
                **chunk,  # Include all original chunk data
                'file_overview': file_overview,
                'previous_context': context_info['previous_context'],
                'current_context': context_info['current_context'],
                'next_context': context_info['next_context'],
                'total_chunks': len(base_chunks),
                'filename': filename
            }

            context_aware_chunks.append(enhanced_chunk)

        return context_aware_chunks

    def reassemble_chunks(self, chunk_results: List[Dict[str, any]], original_structure: str) -> str:
        """
        Intelligently reassemble chunks back into a single file, handling failed chunks.

        Args:
            chunk_results: List of chunk result dictionaries with success/failure info
            original_structure: Original file structure for reference

        Returns:
            Reassembled file content with proper structure preservation
        """
        try:
            original_lines = original_structure.split('\n')
            reassembled_lines = []

            # Track which lines have been processed
            processed_lines = set()

            # Sort chunk results by start line to maintain order
            sorted_chunks = sorted(chunk_results, key=lambda x: x.get('start_line', 0))

            for chunk_result in sorted_chunks:
                start_line = chunk_result.get('start_line', 0)
                end_line = chunk_result.get('end_line', len(original_lines))
                chunk_content = chunk_result.get('content', '')
                success = chunk_result.get('success', False)
                commented_content = chunk_result.get('commented_content', '')

                # Handle the gap between previous chunk and current chunk
                if reassembled_lines:
                    last_processed = max(processed_lines) if processed_lines else -1
                    for line_idx in range(last_processed + 1, start_line):
                        if line_idx < len(original_lines) and line_idx not in processed_lines:
                            reassembled_lines.append(original_lines[line_idx])
                            processed_lines.add(line_idx)

                # Add chunk content (commented if successful, original if failed)
                if success and commented_content:
                    # Use the commented version
                    chunk_lines = commented_content.split('\n')
                    reassembled_lines.extend(chunk_lines)
                else:
                    # Use original content for failed chunks
                    for line_idx in range(start_line, min(end_line, len(original_lines))):
                        if line_idx not in processed_lines:
                            reassembled_lines.append(original_lines[line_idx])

                # Mark these lines as processed
                for line_idx in range(start_line, min(end_line, len(original_lines))):
                    processed_lines.add(line_idx)

            # Add any remaining unprocessed lines at the end
            last_processed = max(processed_lines) if processed_lines else -1
            for line_idx in range(last_processed + 1, len(original_lines)):
                if line_idx not in processed_lines:
                    reassembled_lines.append(original_lines[line_idx])

            return '\n'.join(reassembled_lines)

        except Exception as e:
            # Fallback: Use original structure with selective chunk replacement
            print(f"Error in sophisticated reassembly, using safer fallback: {e}")

            try:
                # Safer fallback: start with original and selectively replace successful chunks
                result_lines = original_structure.split('\n')

                for chunk_result in chunk_results:
                    if chunk_result.get('success', False) and chunk_result.get('commented_content'):
                        start_line = chunk_result.get('start_line', 0)
                        end_line = chunk_result.get('end_line', len(result_lines))

                        # Replace only the specific chunk section with commented version
                        if start_line < len(result_lines) and end_line <= len(result_lines):
                            commented_lines = chunk_result['commented_content'].split('\n')
                            result_lines[start_line:end_line] = commented_lines

                return '\n'.join(result_lines)

            except Exception as e2:
                # Ultimate fallback: return original structure unchanged
                print(f"Even safer fallback failed, returning original: {e2}")
                return original_structure


def test_token_estimation():
    """Test the token estimation functionality."""
    estimator = TokenEstimator()

    # Test with sample VFP code
    sample_code = """
    PROCEDURE TestProc
        LOCAL lcVar
        lcVar = "Hello World"

        IF !EMPTY(lcVar)
            MESSAGEBOX(lcVar)
        ENDIF
    ENDPROC
    """

    tokens = estimator.estimate_tokens(sample_code)
    strategy_info = estimator.determine_processing_strategy(len(sample_code), sample_code)

    print(f"Sample code tokens: {tokens}")
    print(f"Strategy: {strategy_info}")


if __name__ == "__main__":
    test_token_estimation()