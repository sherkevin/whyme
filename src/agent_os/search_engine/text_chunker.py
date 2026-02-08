"""Text Chunker - Splits text into manageable chunks.

This module provides functionality for:
- Splitting text into chunks with overlap
- Preserving sentence and paragraph boundaries
- Handling Markdown and code blocks
"""

import logging
import re
from typing import List, Tuple

logger = logging.getLogger(__name__)


class TextChunker:
    """Text chunker for splitting content."""

    def __init__(
        self,
        chunk_size: int = 1000,
        overlap: int = 200,
        separators: List[str] = None
    ):
        """Initialize text chunker.

        Args:
            chunk_size: Target chunk size in characters
            overlap: Overlap between chunks in characters
            separators: Preferred split separators (in priority order)
        """
        self.chunk_size = chunk_size
        self.overlap = overlap

        # Default separators in priority order
        if separators is None:
            self.separators = [
                '\n\n',  # Paragraph breaks
                '\n',    # Line breaks
                '. ',    # Sentence endings
                '! ',    # Exclamation sentences
                '? ',    # Question sentences
                '; ',    # Semicolons
                ', ',    # Commas
                ' ',     # Spaces
                ''       # No separator (character level)
            ]
        else:
            self.separators = separators

    def chunk_text(
        self,
        text: str,
        chunk_size: int = None,
        overlap: int = None
    ) -> List[str]:
        """Split text into chunks.

        Args:
            text: Text to chunk
            chunk_size: Override default chunk size
            overlap: Override default overlap

        Returns:
            List of text chunks
        """
        chunk_size = chunk_size or self.chunk_size
        overlap = overlap or self.overlap

        if not text or not text.strip():
            return []

        # Handle short text
        if len(text) <= chunk_size:
            return [text.strip()]

        # Use recursive chunking for better boundary preservation
        return self._recursive_chunk(text, chunk_size, overlap)

    def _recursive_chunk(
        self,
        text: str,
        chunk_size: int,
        overlap: int
    ) -> List[str]:
        """Recursively chunk text while preserving boundaries.

        Args:
            text: Text to chunk
            chunk_size: Target chunk size
            overlap: Overlap between chunks

        Returns:
            List of chunks
        """
        chunks = []
        remaining = text

        while len(remaining) > chunk_size:
            # Find best split point
            split_index = self._find_split_index(remaining[:chunk_size])

            # Extract chunk
            chunk = remaining[:split_index].strip()
            if chunk:
                chunks.append(chunk)

            # Calculate remaining with overlap
            remaining = remaining[max(0, split_index - overlap):]

        # Add final chunk
        if remaining.strip():
            chunks.append(remaining.strip())

        return chunks

    def _find_split_index(self, text: str) -> int:
        """Find best split point in text.

        Args:
            text: Text to find split in

        Returns:
            Index to split at
        """
        # Try each separator in priority order
        for separator in self.separators:
            if not separator:
                # Last resort: split at exact chunk_size
                return len(text)

            # Find last occurrence of separator
            index = text.rfind(separator)

            if index != -1:
                # Found separator, split after it
                return index + len(separator)

        # No separator found, split at chunk size
        return len(text)

    def chunk_markdown(self, text: str, chunk_size: int = None) -> List[str]:
        """Chunk Markdown content while preserving structure.

        Args:
            text: Markdown text
            chunk_size: Target chunk size

        Returns:
            List of chunks
        """
        chunk_size = chunk_size or self.chunk_size

        # Split by headers first to preserve sections
        sections = self._split_markdown_sections(text)

        chunks = []
        current_chunk = ""

        for section in sections:
            # If section alone is too large, chunk it normally
            if len(section) > chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""

                section_chunks = self.chunk_text(section, chunk_size, self.overlap)
                chunks.extend(section_chunks)
            elif len(current_chunk) + len(section) > chunk_size:
                # Adding section would exceed limit, save current chunk
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = section
            else:
                # Add to current chunk
                current_chunk += "\n\n" + section if current_chunk else section

        # Add final chunk
        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks

    def _split_markdown_sections(self, text: str) -> List[str]:
        """Split markdown by headers.

        Args:
            text: Markdown text

        Returns:
            List of sections
        """
        # Split by ATX-style headers (# ## ###)
        sections = re.split(r'\n(?=#{1,6}\s)', text)

        # Filter out empty sections
        return [s.strip() for s in sections if s.strip()]

    def chunk_code(self, text: str, language: str = None) -> List[str]:
        """Chunk code content while preserving logic.

        Args:
            text: Code text
            language: Programming language (for syntax awareness)

        Returns:
            List of chunks
        """
        # For code, try to split at logical boundaries
        # This is a simplified version - production would use AST-based splitting

        # Split by function/class definitions
        if language in ['python', 'py']:
            # Split by function/class definitions
            pattern = r'\n(?:def |class )'
        elif language in ['javascript', 'js', 'typescript', 'ts']:
            # Split by function/class definitions
            pattern = r'\n(?:function |class |const \w+ = |\w+:\s*\(.*?\)\s*=>)'
        else:
            # Default: split by double newlines
            pattern = r'\n\n'

        # Split and merge to meet chunk size
        raw_chunks = re.split(pattern, text)

        chunks = []
        current = ""

        for chunk in raw_chunks:
            if len(current) + len(chunk) > self.chunk_size:
                if current:
                    chunks.append(current.strip())
                current = chunk
            else:
                current += ("\n" if current else "") + chunk

        if current.strip():
            chunks.append(current.strip())

        return chunks

    def get_chunk_metadata(self, chunk: str, chunk_index: int, total_chunks: int) -> dict:
        """Get metadata for a chunk.

        Args:
            chunk: Chunk text
            chunk_index: Index of chunk (0-based)
            total_chunks: Total number of chunks

        Returns:
            Metadata dictionary
        """
        return {
            "chunk_index": chunk_index,
            "total_chunks": total_chunks,
            "char_count": len(chunk),
            "word_count": len(chunk.split()),
            "line_count": len(chunk.split('\n')),
            "starts_with_sentence": chunk[0:1].isupper() if chunk else False,
            "ends_with_sentence": any(chunk.rstrip().endswith(end) for end in ['.', '!', '?', '...']) if chunk else False
        }

    def merge_chunks(self, chunks: List[str], overlap: int = None) -> str:
        """Merge chunks back into text.

        Args:
            chunks: List of chunks
            overlap: Overlap to preserve when merging

        Returns:
            Merged text
        """
        if not chunks:
            return ""

        overlap = overlap or self.overlap

        if len(chunks) == 1:
            return chunks[0]

        result = [chunks[0]]

        for i in range(1, len(chunks)):
            prev = result[-1]
            curr = chunks[i]

            # Find overlap point
            if overlap > 0 and len(prev) > overlap:
                # Check if end of prev matches start of curr
                prev_end = prev[-overlap:]
                if curr.startswith(prev_end):
                    # Remove overlap from current
                    curr = curr[overlap:]

            result.append(curr)

        return "\n\n".join(result)


class ChunkResult:
    """Result of chunking operation."""

    def __init__(
        self,
        chunks: List[str],
        original_length: int,
        chunk_count: int,
        metadata: dict = None
    ):
        self.chunks = chunks
        self.original_length = original_length
        self.chunk_count = chunk_count
        self.metadata = metadata or {}

    def __repr__(self):
        return f"<ChunkResult(chunks={self.chunk_count}, original_length={self.original_length})>"

    def get_stats(self) -> dict:
        """Get statistics about chunking results.

        Returns:
            Statistics dictionary
        """
        if not self.chunks:
            return {
                "chunk_count": 0,
                "avg_chunk_size": 0,
                "min_chunk_size": 0,
                "max_chunk_size": 0
            }

        chunk_sizes = [len(c) for c in self.chunks]

        return {
            "chunk_count": len(self.chunks),
            "original_length": self.original_length,
            "avg_chunk_size": sum(chunk_sizes) / len(chunk_sizes),
            "min_chunk_size": min(chunk_sizes),
            "max_chunk_size": max(chunk_sizes),
            "total_chars": sum(chunk_sizes)
        }
