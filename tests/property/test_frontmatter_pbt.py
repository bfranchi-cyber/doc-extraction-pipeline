"""Property-based tests for pipeline.frontmatter YAML serialization round-trips.

PBT scope (partial): pure functions + serialization round-trips.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from pipeline.frontmatter import read_frontmatter, write_frontmatter

# Strategy for generating valid tag strings (printable text, no leading/trailing whitespace)
_tag_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_"),
    min_size=1,
    max_size=30,
)


@given(
    summary=st.text(min_size=1, max_size=200),
    tags=st.lists(_tag_strategy, min_size=3, max_size=5),
    confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_frontmatter_write_then_read_round_trip(
    tmp_path: Path, summary: str, tags: list[str], confidence: float
) -> None:
    """write_frontmatter then read_frontmatter always returns the original data."""
    md_file = tmp_path / "doc.md"
    md_file.write_text("original body content", encoding="utf-8")

    data = {"summary": summary, "tags": tags, "confidence": confidence}
    write_frontmatter(md_file, data)

    result = read_frontmatter(md_file)

    assert result is not None
    assert result["summary"] == summary
    assert result["tags"] == tags
    assert abs(result["confidence"] - confidence) < 1e-9


@given(
    summary=st.text(min_size=1, max_size=200),
    tags=st.lists(_tag_strategy, min_size=3, max_size=5),
    confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_write_preserves_original_body(
    tmp_path: Path, summary: str, tags: list[str], confidence: float
) -> None:
    """write_frontmatter must not destroy the existing file body."""
    original_body = "This is the original document body."
    md_file = tmp_path / "doc.md"
    md_file.write_text(original_body, encoding="utf-8")

    write_frontmatter(md_file, {"summary": summary, "tags": tags, "confidence": confidence})

    file_text = md_file.read_text(encoding="utf-8")
    assert original_body in file_text


@given(content=st.text())
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_read_frontmatter_never_raises_on_arbitrary_content(
    tmp_path: Path, content: str
) -> None:
    """read_frontmatter must never raise regardless of file content."""
    md_file = tmp_path / "arbitrary.md"
    md_file.write_text(content, encoding="utf-8")

    result = read_frontmatter(md_file)
    assert result is None or isinstance(result, dict)
