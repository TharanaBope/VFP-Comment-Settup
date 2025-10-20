"""
VFP Code Chunker
=================
Intelligently splits VFP code at procedural boundaries (PROCEDURE/FUNCTION)
to maintain logical coherence during two-phase processing.

This module understands VFP code structure and creates chunks that:
- Keep complete procedures/functions together
- Maintain context and readability
- Are sized appropriately for LLM processing
"""

import re
from typing import List, Dict, Tuple
from dataclasses import dataclass

@dataclass
class CodeChunk:
    """Represents a chunk of VFP code with metadata"""
    content: str
    start_line: int
    end_line: int
    chunk_type: str  # 'toplevel', 'procedure', 'function'
    name: str  # Procedure/function name, or 'toplevel' for top-level code

    def __len__(self):
        return len(self.content.split('\n'))

    @property
    def line_count(self):
        return len(self.content.split('\n'))


class VFPChunker:
    """
    Intelligent VFP code chunker that splits at procedural boundaries.

    Features:
    - Identifies PROCEDURE and FUNCTION blocks
    - Keeps complete procedures together
    - Handles top-level code (outside procedures)
    - Case-insensitive keyword matching
    """

    def __init__(self, max_chunk_lines: int = 30):
        """
        Initialize the chunker.

        Args:
            max_chunk_lines: Maximum lines per chunk (default: 30 for optimal LLM processing)
        """
        self.max_chunk_lines = max_chunk_lines

        # VFP keywords for procedure boundaries (case-insensitive)
        self.proc_start_pattern = re.compile(
            r'^\s*(PROCEDURE|FUNCTION)\s+(\w+)',
            re.IGNORECASE | re.MULTILINE
        )
        self.proc_end_pattern = re.compile(
            r'^\s*(ENDPROC|ENDFUNC)',
            re.IGNORECASE | re.MULTILINE
        )

    def chunk_code(self, vfp_code: str) -> List[CodeChunk]:
        """
        Split VFP code into logical chunks at procedural boundaries.

        Args:
            vfp_code: The complete VFP code to chunk

        Returns:
            List of CodeChunk objects
        """
        lines = vfp_code.split('\n')
        chunks = []
        current_line = 0

        # Find all procedure/function starts and ends
        proc_blocks = self._find_procedure_blocks(vfp_code, lines)

        # Handle top-level code (before first procedure)
        if proc_blocks and proc_blocks[0]['start_line'] > 0:
            toplevel_lines = lines[0:proc_blocks[0]['start_line']]
            if any(line.strip() for line in toplevel_lines):  # Only if not empty
                # Sub-chunk if needed
                if len(toplevel_lines) <= self.max_chunk_lines:
                    chunks.append(CodeChunk(
                        content='\n'.join(toplevel_lines),
                        start_line=0,
                        end_line=proc_blocks[0]['start_line'] - 1,
                        chunk_type='toplevel',
                        name='toplevel'
                    ))
                else:
                    # Sub-chunk large toplevel code
                    sub_chunks = self._sub_chunk_procedure(
                        toplevel_lines, 0, 'toplevel', 'toplevel'
                    )
                    chunks.extend(sub_chunks)

        elif not proc_blocks:
            # Entire file is top-level code (no procedures) - sub-chunk if needed
            if len(lines) <= self.max_chunk_lines:
                chunks.append(CodeChunk(
                    content=vfp_code,
                    start_line=0,
                    end_line=len(lines) - 1,
                    chunk_type='toplevel',
                    name='toplevel'
                ))
            else:
                sub_chunks = self._sub_chunk_procedure(
                    lines, 0, 'toplevel', 'toplevel'
                )
                chunks.extend(sub_chunks)
            return chunks

        # Add each procedure/function as a chunk (with sub-chunking if needed)
        for block in proc_blocks:
            proc_lines = lines[block['start_line']:block['end_line'] + 1]
            proc_line_count = len(proc_lines)

            # If procedure fits within max_chunk_lines, add as single chunk
            if proc_line_count <= self.max_chunk_lines:
                proc_code = '\n'.join(proc_lines)
                chunks.append(CodeChunk(
                    content=proc_code,
                    start_line=block['start_line'],
                    end_line=block['end_line'],
                    chunk_type=block['type'],
                    name=block['name']
                ))
            else:
                # Sub-chunk large procedures
                sub_chunks = self._sub_chunk_procedure(
                    proc_lines,
                    block['start_line'],
                    block['name'],
                    block['type']
                )
                chunks.extend(sub_chunks)

        return chunks

    def _find_procedure_blocks(self, vfp_code: str, lines: List[str]) -> List[Dict]:
        """
        Find all procedure/function blocks in the code.

        Returns:
            List of dicts with keys: type, name, start_line, end_line
        """
        blocks = []
        i = 0

        while i < len(lines):
            line = lines[i]

            # Check if this line starts a procedure/function
            match = self.proc_start_pattern.match(line)
            if match:
                keyword = match.group(1).upper()
                name = match.group(2)
                start_line = i

                # Find the matching ENDPROC/ENDFUNC
                end_line = self._find_end_of_procedure(lines, i, keyword)

                if end_line:
                    blocks.append({
                        'type': 'procedure' if keyword == 'PROCEDURE' else 'function',
                        'name': name,
                        'start_line': start_line,
                        'end_line': end_line
                    })
                    i = end_line + 1  # Move past this procedure
                else:
                    # No matching end found - treat rest of file as this procedure
                    blocks.append({
                        'type': 'procedure' if keyword == 'PROCEDURE' else 'function',
                        'name': name,
                        'start_line': start_line,
                        'end_line': len(lines) - 1
                    })
                    break
            else:
                i += 1

        return blocks

    def _find_end_of_procedure(self, lines: List[str], start_line: int, keyword: str) -> int:
        """
        Find the ENDPROC/ENDFUNC that matches a PROCEDURE/FUNCTION.

        Args:
            lines: All lines of code
            start_line: Line where PROCEDURE/FUNCTION starts
            keyword: 'PROCEDURE' or 'FUNCTION'

        Returns:
            Line number of matching end, or None if not found
        """
        # Expected end keyword
        expected_end = 'ENDPROC' if keyword == 'PROCEDURE' else 'ENDFUNC'

        # Track nesting level (in case of nested procedures)
        nesting = 1

        for i in range(start_line + 1, len(lines)):
            line = lines[i].strip().upper()

            # Check for nested procedure/function start
            if line.startswith('PROCEDURE ') or line.startswith('FUNCTION '):
                nesting += 1

            # Check for procedure/function end
            elif line.startswith('ENDPROC') or line.startswith('ENDFUNC'):
                nesting -= 1
                if nesting == 0:
                    return i

        return None

    def _sub_chunk_procedure(
        self,
        proc_lines: List[str],
        start_line: int,
        proc_name: str,
        proc_type: str
    ) -> List[CodeChunk]:
        """
        Split a large procedure into smaller sub-chunks.

        Args:
            proc_lines: Lines of the procedure
            start_line: Starting line number in original file
            proc_name: Name of the procedure
            proc_type: Type ('procedure' or 'function')

        Returns:
            List of sub-chunks
        """
        sub_chunks = []
        current_start = 0

        while current_start < len(proc_lines):
            # Take max_chunk_lines at a time
            current_end = min(current_start + self.max_chunk_lines, len(proc_lines))

            # Create sub-chunk
            chunk_lines = proc_lines[current_start:current_end]
            chunk_content = '\n'.join(chunk_lines)

            sub_chunk_num = len(sub_chunks) + 1
            sub_chunks.append(CodeChunk(
                content=chunk_content,
                start_line=start_line + current_start,
                end_line=start_line + current_end - 1,
                chunk_type=proc_type,
                name=f"{proc_name}_part{sub_chunk_num}"
            ))

            current_start = current_end

        return sub_chunks

    def get_chunk_summary(self, chunks: List[CodeChunk]) -> str:
        """
        Get a human-readable summary of the chunks.

        Args:
            chunks: List of code chunks

        Returns:
            Formatted summary string
        """
        summary = []
        summary.append(f"Total chunks: {len(chunks)}")
        summary.append(f"Total lines: {sum(chunk.line_count for chunk in chunks)}")
        summary.append("\nChunk breakdown:")

        for i, chunk in enumerate(chunks):
            summary.append(
                f"  [{i+1}] {chunk.chunk_type.capitalize()}: {chunk.name} "
                f"(lines {chunk.start_line+1}-{chunk.end_line+1}, "
                f"{chunk.line_count} lines)"
            )

        return '\n'.join(summary)


def test_chunker():
    """Test the chunker with sample VFP code"""
    sample_code = """* Top-level variable declarations
LOCAL lnCount, lcAlias

lcAlias = ALIAS()
lnCount = 0

PROCEDURE GetPatientCount
  * Get count of patients
  SELECT COUNT(*) FROM patients INTO ARRAY laCount
  RETURN laCount[1]
ENDPROC

PROCEDURE UpdatePatientRecord
  LPARAMETERS pnPatientID, pcName
  * Update patient record
  UPDATE patients SET name = pcName WHERE id = pnPatientID
ENDPROC

FUNCTION ValidateData
  * Validate input data
  IF EMPTY(pcName)
    RETURN .F.
  ENDIF
  RETURN .T.
ENDFUNC
"""

    chunker = VFPChunker()
    chunks = chunker.chunk_code(sample_code)

    print("VFP Chunker Test")
    print("=" * 70)
    print(chunker.get_chunk_summary(chunks))
    print("\n" + "=" * 70)

    for i, chunk in enumerate(chunks):
        print(f"\nChunk {i+1}: {chunk.name}")
        print("-" * 70)
        print(chunk.content)


if __name__ == "__main__":
    test_chunker()
