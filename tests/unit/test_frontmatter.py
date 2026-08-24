"""Unit tests for pipeline.frontmatter utility functions."""
from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.frontmatter import read_frontmatter, write_frontmatter


# ---------------------------------------------------------------------------
# read_frontmatter
# ---------------------------------------------------------------------------


class TestReadFrontmatter:
    def test_returns_none_when_no_frontmatter(self, tmp_path: Path) -> None:
        f = tmp_path / "doc.md"
        f.write_text("Just plain content.", encoding="utf-8")
        assert read_frontmatter(f) is None

    def test_returns_none_for_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.md"
        f.write_text("", encoding="utf-8")
        assert read_frontmatter(f) is None

    def test_returns_none_when_opening_dashes_only(self, tmp_path: Path) -> None:
        f = tmp_path / "partial.md"
        f.write_text("---\nno closing block", encoding="utf-8")
        assert read_frontmatter(f) is None

    def test_parses_simple_frontmatter(self, tmp_path: Path) -> None:
        f = tmp_path / "doc.md"
        f.write_text("---\nkey: value\n---\n\nBody text.", encoding="utf-8")
        result = read_frontmatter(f)
        assert result == {"key": "value"}

    def test_parses_frontmatter_with_list(self, tmp_path: Path) -> None:
        content = "---\ntags:\n- python\n- cloud\n---\n\nContent."
        f = tmp_path / "doc.md"
        f.write_text(content, encoding="utf-8")
        result = read_frontmatter(f)
        assert result is not None
        assert result["tags"] == ["python", "cloud"]

    def test_returns_none_for_nonexistent_file(self, tmp_path: Path) -> None:
        f = tmp_path / "missing.md"
        assert read_frontmatter(f) is None

    def test_body_content_not_included_in_result(self, tmp_path: Path) -> None:
        f = tmp_path / "doc.md"
        f.write_text("---\nsummary: short\n---\n\nLong body text here.", encoding="utf-8")
        result = read_frontmatter(f)
        assert result == {"summary": "short"}


# ---------------------------------------------------------------------------
# write_frontmatter
# ---------------------------------------------------------------------------


class TestWriteFrontmatter:
    def test_prepends_frontmatter_block(self, tmp_path: Path) -> None:
        f = tmp_path / "doc.md"
        f.write_text("Original content.", encoding="utf-8")
        write_frontmatter(f, {"key": "val"})
        text = f.read_text(encoding="utf-8")
        assert text.startswith("---\n")
        assert "Original content." in text

    def test_round_trip_basic(self, tmp_path: Path) -> None:
        f = tmp_path / "doc.md"
        f.write_text("Body.", encoding="utf-8")
        data = {"summary": "A summary.", "tags": ["a", "b", "c"], "confidence": 0.85}
        write_frontmatter(f, data)
        result = read_frontmatter(f)
        assert result is not None
        assert result["summary"] == "A summary."
        assert result["tags"] == ["a", "b", "c"]
        assert abs(result["confidence"] - 0.85) < 1e-9

    def test_preserves_original_content(self, tmp_path: Path) -> None:
        original = "# Heading\n\nParagraph text."
        f = tmp_path / "doc.md"
        f.write_text(original, encoding="utf-8")
        write_frontmatter(f, {"x": 1})
        text = f.read_text(encoding="utf-8")
        assert original in text

    def test_unicode_values_preserved(self, tmp_path: Path) -> None:
        f = tmp_path / "doc.md"
        f.write_text("content", encoding="utf-8")
        data = {"summary": "Résumé avec des accents é à ü", "tags": ["tag1", "tag2", "tag3"], "confidence": 0.7}
        write_frontmatter(f, data)
        result = read_frontmatter(f)
        assert result is not None
        assert result["summary"] == "Résumé avec des accents é à ü"

    def test_write_to_file_with_only_frontmatter(self, tmp_path: Path) -> None:
        f = tmp_path / "doc.md"
        f.write_text("", encoding="utf-8")
        write_frontmatter(f, {"summary": "s", "tags": ["a", "b", "c"], "confidence": 1.0})
        result = read_frontmatter(f)
        assert result is not None
        assert result["summary"] == "s"
