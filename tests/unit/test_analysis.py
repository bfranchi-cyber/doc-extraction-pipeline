"""Unit tests for pipeline.analysis.AnalysisAgent."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pipeline.analysis import AnalysisAgent
from pipeline.frontmatter import read_frontmatter
from pipeline.scratchpad import Scratchpad


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_scratchpad(tmp_path: Path) -> Scratchpad:
    return Scratchpad(tmp_path / "scratchpad.jsonl")


def _make_agent(scratchpad: Scratchpad) -> AnalysisAgent:
    with patch.dict(os.environ, {"MEDIUM_MODEL": "test-model"}):
        return AnalysisAgent(scratchpad)


def _mock_tool_response(summary: str, tags: list[str], confidence: float) -> MagicMock:
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.input = {"summary": summary, "tags": tags, "confidence": confidence}

    response = MagicMock()
    response.content = [tool_block]
    return response


def _make_md_file(tmp_path: Path, name: str = "document.md", content: str = "Some content") -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def scratchpad(tmp_path: Path) -> Scratchpad:
    return _make_scratchpad(tmp_path)


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestAnalysisAgent:
    def test_analyze_success_writes_frontmatter(self, tmp_path: Path, scratchpad: Scratchpad) -> None:
        md_file = _make_md_file(tmp_path, content="A document about cloud infrastructure.")
        agent = _make_agent(scratchpad)
        mock_response = _mock_tool_response(
            summary="A cloud infrastructure document.",
            tags=["cloud", "AWS", "infrastructure"],
            confidence=0.9,
        )

        with patch.object(agent._client.messages, "create", new_callable=AsyncMock, return_value=mock_response):
            result = asyncio.run(agent.analyze(md_file))

        assert result is not None
        assert result["summary"] == "A cloud infrastructure document."
        assert result["tags"] == ["cloud", "AWS", "infrastructure"]
        assert abs(result["confidence"] - 0.9) < 1e-9

        fm = read_frontmatter(md_file)
        assert fm is not None
        assert fm["summary"] == "A cloud infrastructure document."

    def test_analyze_success_preserves_original_content(self, tmp_path: Path, scratchpad: Scratchpad) -> None:
        original = "Original document content."
        md_file = _make_md_file(tmp_path, content=original)
        agent = _make_agent(scratchpad)
        mock_response = _mock_tool_response("Summary.", ["tag1", "tag2", "tag3"], 0.8)

        with patch.object(agent._client.messages, "create", new_callable=AsyncMock, return_value=mock_response):
            asyncio.run(agent.analyze(md_file))

        file_content = md_file.read_text(encoding="utf-8")
        assert original in file_content

    def test_analyze_api_error_returns_none(self, tmp_path: Path, scratchpad: Scratchpad) -> None:
        md_file = _make_md_file(tmp_path, content="Some content.")
        agent = _make_agent(scratchpad)

        with patch.object(
            agent._client.messages, "create", new_callable=AsyncMock, side_effect=RuntimeError("API down")
        ):
            result = asyncio.run(agent.analyze(md_file))

        assert result is None

    def test_analyze_api_error_leaves_file_unchanged(self, tmp_path: Path, scratchpad: Scratchpad) -> None:
        original = "Original content unchanged."
        md_file = _make_md_file(tmp_path, content=original)
        agent = _make_agent(scratchpad)

        with patch.object(
            agent._client.messages, "create", new_callable=AsyncMock, side_effect=RuntimeError("API down")
        ):
            asyncio.run(agent.analyze(md_file))

        assert md_file.read_text(encoding="utf-8") == original

    def test_analyze_missing_tool_block_returns_none(self, tmp_path: Path, scratchpad: Scratchpad) -> None:
        md_file = _make_md_file(tmp_path)
        agent = _make_agent(scratchpad)

        response = MagicMock()
        response.content = []  # no tool_use block

        with patch.object(agent._client.messages, "create", new_callable=AsyncMock, return_value=response):
            result = asyncio.run(agent.analyze(md_file))

        assert result is None
        assert read_frontmatter(md_file) is None

    def test_analyze_logs_error_on_failure(self, tmp_path: Path, scratchpad: Scratchpad) -> None:
        md_file = _make_md_file(tmp_path)
        agent = _make_agent(scratchpad)

        with patch.object(
            agent._client.messages, "create", new_callable=AsyncMock, side_effect=RuntimeError("boom")
        ):
            asyncio.run(agent.analyze(md_file))

        log = (tmp_path / "scratchpad.jsonl").read_text(encoding="utf-8")
        assert "error" in log.lower() or "Analysis failed" in log
