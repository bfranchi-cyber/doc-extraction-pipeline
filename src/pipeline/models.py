from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

from pipeline.exceptions import ExtractionPipelineError, PipelineError  # noqa: F401


class CompactArtifact(TypedDict):
    """Structured output of the Extraction stage."""

    document_name: str
    extracted_text: str


@dataclass
class EnrichedDocument:
    """Output of the Analysis stage — complete Markdown with YAML frontmatter and abstract."""

    document_name: str
    markdown: str
