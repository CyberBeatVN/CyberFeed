"""Tests for the extractive summarizer."""

import pytest

from cyberfeed.summarizer.extractive import ExtractiveSummarizer


@pytest.mark.asyncio
async def test_empty_text():
    s = ExtractiveSummarizer()
    result = await s.summarize("")
    assert result.summary == ""
    assert result.method == "extractive"


@pytest.mark.asyncio
async def test_short_text():
    s = ExtractiveSummarizer()
    text = "A brief article about security."
    result = await s.summarize(text)
    assert result.summary == text
    assert result.method == "extractive"


@pytest.mark.asyncio
async def test_long_text_truncated():
    s = ExtractiveSummarizer()
    # 300 words
    text = " ".join([f"word{i}" for i in range(300)]) + "."
    result = await s.summarize(text, max_length=50)
    word_count = len(result.summary.split())
    assert word_count <= 55  # some slack for trailing "..."
    assert result.method == "extractive"


@pytest.mark.asyncio
async def test_max_three_sentences():
    s = ExtractiveSummarizer()
    text = "First sentence. Second sentence. Third sentence. Fourth sentence. Fifth sentence."
    result = await s.summarize(text)
    # Should take at most 3 sentences
    assert result.summary.count(".") <= 3
