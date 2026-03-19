"""Extractive summarizer: first N sentences, no LLM required."""

import re

from cyberfeed.summarizer.base import AbstractSummarizer, SummaryResult


class ExtractiveSummarizer(AbstractSummarizer):
    """Simple extractive summarizer using first N sentences."""

    async def summarize(self, text: str, max_length: int = 200) -> SummaryResult:
        """Extract first few sentences up to max_length words."""
        if not text or not text.strip():
            return SummaryResult(summary="", method="extractive")

        # Split into sentences
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())

        # Take sentences until we reach max_length words
        result_sentences = []
        word_count = 0
        for sentence in sentences:
            words = sentence.split()
            if word_count + len(words) > max_length and result_sentences:
                break
            result_sentences.append(sentence)
            word_count += len(words)
            if len(result_sentences) >= 3:
                break

        summary = " ".join(result_sentences)

        # Truncate to max_length words if still too long
        words = summary.split()
        if len(words) > max_length:
            summary = " ".join(words[:max_length]) + "..."

        return SummaryResult(summary=summary, method="extractive")
