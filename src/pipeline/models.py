from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TypedDict

from dataclasses_json import dataclass_json

# Re-exported for backwards compatibility — new code should import from pipeline.exceptions directly.
from pipeline.exceptions import (  # noqa: F401
    ConfigError,
    CredentialsError,
    ExtractionPipelineError,
    ManifestCorruptionError,
    PipelineError,
)


# ---------------------------------------------------------------------------
# Domain data types
# ---------------------------------------------------------------------------

@dataclass
class DriveFileMetadata:
    """A file discovered in Google Drive that is eligible for processing."""

    file_id: str
    name: str
    mime_type: str
    last_modified: datetime
    download_url: str


@dataclass
class ImageMetadata:
    """Lightweight metadata for a single image extracted from a document."""

    image_id: str
    alt_text: str
    staged_path: Path


class CompactArtifact(TypedDict):
    """Structured output of the Extraction stage, passed to the Analysis stage.

    Image binary data is never included — only metadata.
    """

    file_id: str
    document_name: str
    extracted_text: str
    category: str
    images: list[ImageMetadata]


@dataclass
class EnrichedDocument:
    """Output of the Analysis stage — complete Markdown with YAML frontmatter and abstract."""

    file_id: str
    document_name: str
    category: str
    markdown: str


@dataclass_json
@dataclass
class ManifestRecord:
    """Persisted state for a single Drive document.

    Serialized to JSON by dataclasses-json; one file per document in manifest_dir/.
    status is exactly "success" or "failed" — no other values are valid.
    error holds the JSON-serialized PipelineError payload when status == "failed".
    """

    file_id: str
    name: str
    status: str
    processed_at: str
    error: str | None


@dataclass
class RunSummary:
    """Aggregated statistics for a single pipeline run.

    Invariant: eligible == processed + failed + skipped
    """

    eligible: int
    processed: int
    failed: int
    skipped: int


@dataclass
class ExportResult:
    """Return value of ExportAgent.export() — outcome for one document."""

    file_id: str
    status: str
    vault_path: Path | None
    error: str | None
