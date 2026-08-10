from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TypedDict

from dataclasses_json import dataclass_json


# ---------------------------------------------------------------------------
# Error hierarchy
# ---------------------------------------------------------------------------

class ExtractionPipelineError(Exception):
    """Base for all pipeline errors."""


@dataclass
class PipelineError(ExtractionPipelineError):
    """Structured pipeline error carrying type, message, retriability, and operator guidance.

    error_type: "transient" | "business" | "validation" | "permission"
    is_retriable: True only for "transient" errors — no manifest record is written.
    """

    error_type: str
    text: str
    is_retriable: bool
    suggestion: str

    def __str__(self) -> str:
        return f"[{self.error_type}] {self.text}"

    def to_dict(self) -> dict:
        return {
            "error_type": self.error_type,
            "text": self.text,
            "is_retriable": self.is_retriable,
            "suggestion": self.suggestion,
        }


class ConfigError(PipelineError):
    """Raised by Config.from_toml() on missing fields, invalid paths, or bad values."""

    def __init__(self, text: str, suggestion: str = "Check config.toml for missing or invalid values.") -> None:
        super().__init__(
            error_type="validation",
            text=text,
            is_retriable=False,
            suggestion=suggestion,
        )


class CredentialsError(PipelineError):
    """Raised by Config.from_toml() when credentials file is missing, unreadable, or malformed."""

    def __init__(self, text: str, suggestion: str = "Ensure credentials.json is a valid OAuth2 credentials file.") -> None:
        super().__init__(
            error_type="permission",
            text=text,
            is_retriable=False,
            suggestion=suggestion,
        )


class ManifestCorruptionError(PipelineError):
    """Raised by ManifestStore.get() when a manifest file contains malformed JSON."""

    def __init__(self, file_id: str) -> None:
        super().__init__(
            error_type="validation",
            text=f"Manifest file for '{file_id}' contains malformed JSON and cannot be read.",
            is_retriable=False,
            suggestion=f"Delete or repair the file at manifest_dir/{file_id}.json and re-run the pipeline.",
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
