"""Unit tests for pipeline.classification.ClassificationAgent."""
from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from pipeline.classification import VALID_CATEGORIES, ClassificationAgent
from pipeline.scratchpad import Scratchpad


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
    for cat in VALID_CATEGORIES:
        (vault / cat).mkdir()
    return vault


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestClassificationAgent:
    def test_valid_category_moves_file(self, tmp_path: Path, vault_root: Path, scratchpad: Scratchpad) -> None:
        md_file = _make_md_file(tmp_path, "report.md", "Architecture content")
        agent = _make_agent(vault_root, scratchpad)

        with patch.object(agent._client.messages, "create", return_value=_mock_response("Architecture")):
            result = asyncio.run(agent.classify(md_file))

        assert result is True
        assert (vault_root / "Architecture" / "report.md").exists()
        assert not md_file.exists()

    @pytest.mark.parametrize("category", sorted(VALID_CATEGORIES))
    def test_each_valid_category_moves_file(
        self, tmp_path: Path, vault_root: Path, scratchpad: Scratchpad, category: str
    ) -> None:
        md_file = _make_md_file(tmp_path, "doc.md", f"Content about {category}")
        agent = _make_agent(vault_root, scratchpad)

        with patch.object(agent._client.messages, "create", return_value=_mock_response(category)):
            result = asyncio.run(agent.classify(md_file))

        assert result is True
        assert (vault_root / category / "doc.md").exists()

    def test_unknown_response_leaves_file_in_place(
        self, tmp_path: Path, vault_root: Path, scratchpad: Scratchpad
    ) -> None:
        md_file = _make_md_file(tmp_path, "mystery.md")
        agent = _make_agent(vault_root, scratchpad)

        with patch.object(agent._client.messages, "create", return_value=_mock_response("unknown")):
            result = asyncio.run(agent.classify(md_file))

        assert result is False
        assert md_file.exists()

    def test_malformed_response_leaves_file_in_place(
        self, tmp_path: Path, vault_root: Path, scratchpad: Scratchpad
    ) -> None:
        md_file = _make_md_file(tmp_path, "weird.md")
        agent = _make_agent(vault_root, scratchpad)

        with patch.object(agent._client.messages, "create", return_value=_mock_response("NotACategory")):
            result = asyncio.run(agent.classify(md_file))

        assert result is False
        assert md_file.exists()

    def test_missing_vault_folder_leaves_file_in_place(
        self, tmp_path: Path, scratchpad: Scratchpad
    ) -> None:
        vault_root = tmp_path / "empty_vault"
        vault_root.mkdir()
        md_file = _make_md_file(tmp_path, "cloud.md")
        agent = _make_agent(vault_root, scratchpad)

        with patch.object(agent._client.messages, "create", return_value=_mock_response("Cloud")):
            result = asyncio.run(agent.classify(md_file))

        assert result is False
        assert md_file.exists()

    def test_api_error_leaves_file_in_place(
        self, tmp_path: Path, vault_root: Path, scratchpad: Scratchpad
    ) -> None:
        md_file = _make_md_file(tmp_path, "fail.md")
        agent = _make_agent(vault_root, scratchpad)

        with patch.object(agent._client.messages, "create", side_effect=RuntimeError("API down")):
            result = asyncio.run(agent.classify(md_file))

        assert result is False
        assert md_file.exists()


# ---------------------------------------------------------------------------
# Property-based tests (PBT-02, PBT-07)
# ---------------------------------------------------------------------------


class TestClassificationAgentPBT:
    @given(category=st.sampled_from(sorted(VALID_CATEGORIES)))
    @settings(max_examples=25, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_pbt_any_valid_category_succeeds(self, category: str) -> None:
        """PBT-07: for any element of VALID_CATEGORIES as model response, file is moved."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            scratchpad = _make_scratchpad(tmp_path)
            vault_root = tmp_path / "vault"
            vault_root.mkdir()
            (vault_root / category).mkdir()

            md_file = tmp_path / "test.md"
            md_file.write_text("content", encoding="utf-8")

            agent = _make_agent(vault_root, scratchpad)
            with patch.object(agent._client.messages, "create", return_value=_mock_response(category)):
                result = asyncio.run(agent.classify(md_file))

            assert result is True
            assert (vault_root / category / "test.md").exists()

    @given(response=st.text(min_size=1).filter(lambda s: s.strip() not in VALID_CATEGORIES and s.strip() != "unknown"))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_pbt_invalid_response_never_moves(self, response: str) -> None:
        """PBT-02: any string outside the valid enum never triggers a file move."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            scratchpad = _make_scratchpad(tmp_path)
            vault_root = tmp_path / "vault"
            vault_root.mkdir()

            md_file = tmp_path / "nodoc.md"
            md_file.write_text("content", encoding="utf-8")

            agent = _make_agent(vault_root, scratchpad)
            with patch.object(agent._client.messages, "create", return_value=_mock_response(response)):
                result = asyncio.run(agent.classify(md_file))

            assert result is False
            assert md_file.exists()
