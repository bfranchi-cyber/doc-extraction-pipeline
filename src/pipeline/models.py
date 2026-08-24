from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

from pipeline.exceptions import ExtractionPipelineError, PipelineError  # noqa: F401


class CompactArtifact(TypedDict):
    """Structured output of the Extraction stage."""

    document_name: str
    extracted_text: str


class AnalysisResult(TypedDict):
    """Structured output of the Analysis stage — LLM-generated document metadata."""

    summary: str
    tags: list[str]  # 3-5 strings, enforced by tool-use schema
    confidence: float  # 0.0 – 1.0


@dataclass
class EnrichedDocument:
    """Output of the Analysis stage — complete Markdown with YAML frontmatter and abstract."""

    document_name: str
    markdown: str
