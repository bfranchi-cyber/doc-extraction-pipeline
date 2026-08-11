from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class ExtractionPipelineError(Exception):
    """Base for all pipeline errors."""


@dataclass
class PipelineError(ExtractionPipelineError):
    """Structured pipeline error carrying type, message, retriability, and operator guidance.

    error_type: "transient" | "business" | "validation" | "permission"
    is_retriable: True only for "transient" errors.
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


class RateLimitError(ExtractionPipelineError):
    """Raised by DriveClient methods when the Drive API returns a rate-limit response."""

    def __init__(self, retry_after: int | None = None) -> None:
        self.retry_after = retry_after
        super().__init__(f"Drive API rate limit exceeded. Retry after: {retry_after}s")


class CredentialsMissingError(ExtractionPipelineError):
    """Raised when authentication cannot proceed without user interaction."""

    def __init__(self, credentials_path: Path, message: str) -> None:
        self.credentials_path = credentials_path
        self.message = message
        super().__init__(message)


class DownloadError(ExtractionPipelineError):
    """Raised by download_file() on non-rate-limit failures.

    error_type: "transient" | "business" | "business_date_eligibility" | "validation" | "permission"
    is_retriable: True only for "transient" errors.
    """

    def __init__(
        self,
        file_id: str,
        name: str,
        error_type: str,
        message: str,
        cause: Exception | None = None,
    ) -> None:
        self.file_id = file_id
        self.name = name
        self.error_type = error_type
        self.is_retriable = error_type == "transient"
        self.message = message
        self.cause = cause
        super().__init__(f"[{error_type}] {message} (file: {name})")
