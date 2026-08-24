"""Unit tests for pipeline.classification.ClassificationAgent."""
from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from pipeline.classification import ClassificationAgent
from pipeline.frontmatter import write_frontmatter
from pipeline.scratchpad import Scratchpad

# Local test category set — avoids coupling tests to runtime vault state
_TEST_CATEGORIES = frozenset({"Architecture", "Cloud", "Coding"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_scratchpad(tmp_path: Path) -> Scratchpad:
    return Scratchpad(tmp_path / "scratchpad.jsonl")


def _make_agent(vault_root: Path, scratchpad: Scratchpad) -> ClassificationAgent:
    with patch.dict(os.environ, {"LIGHT_MODEL": "test-model"}):
        return ClassificationAgent(vault_root, scratchpad)


def _mock_response(text: str) -> MagicMock:
    block = MagicMock()
    block.text = text
    response = MagicMock()
    response.content = [block]
    return response


def _make_md_file(tmp_path: Path, name: str = "document.md", content: str = "Some content") -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def scratchpad(tmp_path: Path) -> Scratchpad:
    return _make_scratchpad(tmp_path)


@pytest.fixture
def vault_root(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    vault.mkdir()
    for cat in _TEST_CATEGORIES:
        (vault / cat).mkdir()
    return vault


# ---------------------------------------------------------------------------
# Dynamic category discovery
# ---------------------------------------------------------------------------


class TestCategoryDiscovery:
    def test_discovers_categories_from_vault_subfolders(self, tmp_path: Path, scratchpad: Scratchpad) -> None:
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "CategoryA").mkdir()
        (vault / "CategoryB").mkdir()
        agent = _make_agent(vault, scratchpad)
        assert agent._valid_categories == frozenset({"CategoryA", "CategoryB"})

    def test_empty_vault_returns_empty_frozenset(self, tmp_path: Path, scratchpad: Scratchpad) -> None:
        vault = tmp_path / "empty_vault"
        vault.mkdir()
        agent = _make_agent(vault, scratchpad)
        assert agent._valid_categories == frozenset()

    def test_files_in_vault_root_not_treated_as_categories(self, tmp_path: Path, scratchpad: Scratchpad) -> None:
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "RealCategory").mkdir()
        (vault / "not_a_category.md").write_text("file", encoding="utf-8")
        agent = _make_agent(vault, scratchpad)
        assert agent._valid_categories == frozenset({"RealCategory"})


# ---------------------------------------------------------------------------
# Classification — raw text path (no frontmatter)
# ---------------------------------------------------------------------------


class TestClassificationAgentRawText:
    def test_valid_category_moves_file(self, tmp_path: Path, vault_root: Path, scratchpad: Scratchpad) -> None:
        md_file = _make_md_file(tmp_path, "report.md", "Architecture content")
        agent = _make_agent(vault_root, scratchpad)

        with patch.object(agent._client.messages, "create", new_callable=AsyncMock, return_value=_mock_response("Architecture")):
            result = asyncio.run(agent.classify(md_file))

        assert result is True
        assert (vault_root / "Architecture" / "report.md").exists()
        assert not md_file.exists()

    @pytest.mark.parametrize("category", sorted(_TEST_CATEGORIES))
    def test_each_valid_category_moves_file(
        self, tmp_path: Path, vault_root: Path, scratchpad: Scratchpad, category: str
    ) -> None:
        md_file = _make_md_file(tmp_path, "doc.md", f"Content about {category}")
        agent = _make_agent(vault_root, scratchpad)

        with patch.object(agent._client.messages, "create", new_callable=AsyncMock, return_value=_mock_response(category)):
            result = asyncio.run(agent.classify(md_file))

        assert result is True
        assert (vault_root / category / "doc.md").exists()

    def test_unknown_response_leaves_file_in_place(
        self, tmp_path: Path, vault_root: Path, scratchpad: Scratchpad
    ) -> None:
        md_file = _make_md_file(tmp_path, "mystery.md")
        agent = _make_agent(vault_root, scratchpad)

        with patch.object(agent._client.messages, "create", new_callable=AsyncMock, return_value=_mock_response("unknown")):
            result = asyncio.run(agent.classify(md_file))

        assert result is False
        assert md_file.exists()

    def test_malformed_response_leaves_file_in_place(
        self, tmp_path: Path, vault_root: Path, scratchpad: Scratchpad
    ) -> None:
        md_file = _make_md_file(tmp_path, "weird.md")
        agent = _make_agent(vault_root, scratchpad)

        with patch.object(agent._client.messages, "create", new_callable=AsyncMock, return_value=_mock_response("NotACategory")):
            result = asyncio.run(agent.classify(md_file))

        assert result is False
        assert md_file.exists()

    def test_api_error_leaves_file_in_place(
        self, tmp_path: Path, vault_root: Path, scratchpad: Scratchpad
    ) -> None:
        md_file = _make_md_file(tmp_path, "fail.md")
        agent = _make_agent(vault_root, scratchpad)

        with patch.object(agent._client.messages, "create", new_callable=AsyncMock, side_effect=RuntimeError("API down")):
            result = asyncio.run(agent.classify(md_file))

        assert result is False
        assert md_file.exists()


# ---------------------------------------------------------------------------
# Classification — frontmatter path
# ---------------------------------------------------------------------------


class TestClassificationAgentFrontmatter:
    def test_classify_uses_frontmatter_summary_when_present(
        self, tmp_path: Path, vault_root: Path, scratchpad: Scratchpad
    ) -> None:
        md_file = _make_md_file(tmp_path, content="Raw content that should not appear in prompt.")
        write_frontmatter(md_file, {
            "summary": "A document about cloud computing services.",
            "tags": ["cloud", "AWS", "infrastructure"],
            "confidence": 0.9,
        })
        agent = _make_agent(vault_root, scratchpad)

        captured_messages: list = []

        async def capture_create(**kwargs):
            captured_messages.append(kwargs.get("messages", []))
            return _mock_response("Cloud")

        with patch.object(agent._client.messages, "create", side_effect=capture_create):
            asyncio.run(agent.classify(md_file))

        assert captured_messages, "LLM was never called"
        user_content = captured_messages[0][0]["content"]
        assert "A document about cloud computing services." in user_content
        assert "Raw content that should not appear in prompt." not in user_content

    def test_classify_falls_back_to_raw_text_when_no_frontmatter(
        self, tmp_path: Path, vault_root: Path, scratchpad: Scratchpad
    ) -> None:
        raw_text = "Raw content about coding practices and algorithms."
        md_file = _make_md_file(tmp_path, content=raw_text)
        agent = _make_agent(vault_root, scratchpad)

        captured_messages: list = []

        async def capture_create(**kwargs):
            captured_messages.append(kwargs.get("messages", []))
            return _mock_response("Coding")

        with patch.object(agent._client.messages, "create", side_effect=capture_create):
            asyncio.run(agent.classify(md_file))

        assert captured_messages, "LLM was never called"
        user_content = captured_messages[0][0]["content"]
        assert raw_text in user_content

    def test_classify_with_frontmatter_still_moves_file(
        self, tmp_path: Path, vault_root: Path, scratchpad: Scratchpad
    ) -> None:
        md_file = _make_md_file(tmp_path, "enriched.md", content="Body content.")
        write_frontmatter(md_file, {
            "summary": "Architecture patterns document.",
            "tags": ["design", "patterns", "software"],
            "confidence": 0.85,
        })
        agent = _make_agent(vault_root, scratchpad)

        with patch.object(agent._client.messages, "create", new_callable=AsyncMock, return_value=_mock_response("Architecture")):
            result = asyncio.run(agent.classify(md_file))

        assert result is True
        assert (vault_root / "Architecture" / "enriched.md").exists()


# ---------------------------------------------------------------------------
# Property-based tests
# ---------------------------------------------------------------------------


class TestClassificationAgentPBT:
    @given(category=st.sampled_from(sorted(_TEST_CATEGORIES)))
    @settings(max_examples=25, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_pbt_any_valid_category_succeeds(self, category: str) -> None:
        """For any category in the vault, a matching LLM response moves the file."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            scratchpad = _make_scratchpad(tmp_path)
            vault_root = tmp_path / "vault"
            vault_root.mkdir()
            (vault_root / category).mkdir()

            md_file = tmp_path / "test.md"
            md_file.write_text("content", encoding="utf-8")

            agent = _make_agent(vault_root, scratchpad)
            with patch.object(agent._client.messages, "create", new_callable=AsyncMock, return_value=_mock_response(category)):
                result = asyncio.run(agent.classify(md_file))

            assert result is True
            assert (vault_root / category / "test.md").exists()

    @given(response=st.text(min_size=1).filter(lambda s: s.strip() not in _TEST_CATEGORIES and s.strip() != "unknown"))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_pbt_invalid_response_never_moves(self, response: str) -> None:
        """Any string outside the discovered vault categories never triggers a file move."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            scratchpad = _make_scratchpad(tmp_path)
            vault_root = tmp_path / "vault"
            vault_root.mkdir()
            for cat in _TEST_CATEGORIES:
                (vault_root / cat).mkdir()

            md_file = tmp_path / "nodoc.md"
            md_file.write_text("content", encoding="utf-8")

            agent = _make_agent(vault_root, scratchpad)
            with patch.object(agent._client.messages, "create", new_callable=AsyncMock, return_value=_mock_response(response)):
                result = asyncio.run(agent.classify(md_file))

            assert result is False
            assert md_file.exists()
