"""
Text Chunker

Splits documents into chunks for embedding and vector search.
Supports character-based and sentence-aware chunking.
"""

import re
from typing import Optional
from pydantic import BaseModel, Field


class TextChunk(BaseModel):
    """A chunk of text for embedding."""

    text: str = Field(..., description="Chunk text content")
    start_idx: int = Field(..., description="Start position in original text")
    end_idx: int = Field(..., description="End position in original text")
    metadata: dict = Field(default_factory=dict, description="Additional metadata")


class TextChunker:
    """Chunks text documents for embedding."""

    def __init__(self):
        """Initialize text chunker."""
        # Sentence boundary detection
        self.sentence_end_pattern = re.compile(r'[.!?]\s+')

    def chunk_text(
        self,
        text: str,
        chunk_size: int = 500,
        overlap: int = 50,
        respect_sentences: bool = True
    ) -> list[TextChunk]:
        """Chunk text into overlapping segments.

        Args:
            text: Text to chunk
            chunk_size: Target chunk size in characters
            overlap: Overlap between chunks in characters
            respect_sentences: Try to break at sentence boundaries

        Returns:
            List of text chunks
        """
        if respect_sentences:
            return self._chunk_by_sentences(text, chunk_size, overlap)
        else:
            return self._chunk_by_chars(text, chunk_size, overlap)

    def _chunk_by_chars(
        self,
        text: str,
        chunk_size: int,
        overlap: int
    ) -> list[TextChunk]:
        """Chunk text by character count.

        Args:
            text: Text to chunk
            chunk_size: Target chunk size
            overlap: Overlap size

        Returns:
            List of chunks
        """
        chunks = []
        start = 0

        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk_text = text[start:end]

            chunks.append(TextChunk(
                text=chunk_text,
                start_idx=start,
                end_idx=end
            ))

            # Move to next chunk with overlap
            start = end - overlap
            if start >= len(text):
                break

        return chunks

    def _chunk_by_sentences(
        self,
        text: str,
        chunk_size: int,
        overlap: int
    ) -> list[TextChunk]:
        """Chunk text at sentence boundaries.

        Args:
            text: Text to chunk
            chunk_size: Target chunk size
            overlap: Overlap size

        Returns:
            List of chunks
        """
        # Split into sentences
        sentences = self._split_sentences(text)

        if not sentences:
            return []

        chunks = []
        current_chunk = []
        current_length = 0
        current_start = 0

        for i, sentence in enumerate(sentences):
            sentence_len = len(sentence)

            # Check if adding this sentence exceeds chunk size
            if current_length > 0 and current_length + sentence_len > chunk_size:
                # Create chunk from accumulated sentences
                chunk_text = ' '.join(current_chunk)
                chunk_end = current_start + len(chunk_text)

                chunks.append(TextChunk(
                    text=chunk_text,
                    start_idx=current_start,
                    end_idx=chunk_end
                ))

                # Start new chunk with overlap
                # Include last few sentences for context
                overlap_sentences = []
                overlap_length = 0

                for prev_sentence in reversed(current_chunk):
                    if overlap_length + len(prev_sentence) <= overlap:
                        overlap_sentences.insert(0, prev_sentence)
                        overlap_length += len(prev_sentence)
                    else:
                        break

                current_chunk = overlap_sentences + [sentence]
                current_length = sum(len(s) for s in current_chunk)
                current_start = chunk_end - overlap_length

            else:
                # Add sentence to current chunk
                current_chunk.append(sentence)
                current_length += sentence_len

        # Add final chunk
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            chunks.append(TextChunk(
                text=chunk_text,
                start_idx=current_start,
                end_idx=current_start + len(chunk_text)
            ))

        return chunks

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences.

        Args:
            text: Text to split

        Returns:
            List of sentences
        """
        # Simple sentence splitting
        # More sophisticated methods could use spaCy or NLTK
        sentences = []
        current_pos = 0

        for match in self.sentence_end_pattern.finditer(text):
            sentence = text[current_pos:match.end()].strip()
            if sentence:
                sentences.append(sentence)
            current_pos = match.end()

        # Add remaining text
        if current_pos < len(text):
            remaining = text[current_pos:].strip()
            if remaining:
                sentences.append(remaining)

        return sentences

    def chunk_sections(
        self,
        sections: list[dict],
        chunk_size: int = 500,
        overlap: int = 50
    ) -> list[TextChunk]:
        """Chunk document sections while preserving metadata.

        Args:
            sections: List of section dicts with 'title' and 'content'
            chunk_size: Target chunk size
            overlap: Overlap size

        Returns:
            List of chunks with section metadata
        """
        all_chunks = []

        for section in sections:
            title = section.get('title', '')
            content = section.get('content', '')

            if not content:
                continue

            # Chunk section content
            section_chunks = self.chunk_text(
                content,
                chunk_size=chunk_size,
                overlap=overlap,
                respect_sentences=True
            )

            # Add section metadata
            for chunk in section_chunks:
                chunk.metadata['section_title'] = title
                chunk.metadata['section_pages'] = section.get('page_numbers', [])
                all_chunks.append(chunk)

        return all_chunks

    def merge_small_chunks(
        self,
        chunks: list[TextChunk],
        min_size: int = 100
    ) -> list[TextChunk]:
        """Merge chunks smaller than minimum size.

        Args:
            chunks: List of chunks
            min_size: Minimum chunk size

        Returns:
            List with small chunks merged
        """
        if not chunks:
            return []

        merged = []
        i = 0

        while i < len(chunks):
            current = chunks[i]

            # If current chunk is too small and not last, merge with next
            if len(current.text) < min_size and i < len(chunks) - 1:
                next_chunk = chunks[i + 1]

                # Merge texts
                merged_text = current.text + ' ' + next_chunk.text
                merged_chunk = TextChunk(
                    text=merged_text,
                    start_idx=current.start_idx,
                    end_idx=next_chunk.end_idx,
                    metadata=current.metadata
                )

                merged.append(merged_chunk)
                i += 2  # Skip next chunk since we merged it

            else:
                merged.append(current)
                i += 1

        return merged
