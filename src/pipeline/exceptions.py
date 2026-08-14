from __future__ import annotations

from dataclasses import dataclass


class ExtractionPipelineError(Exception):
    """Base for all pipeline errors."""


@dataclass
class PipelineError(ExtractionPipelineError):
    """Structured pipeline error carrying type, message, retriability, and operator guidance.

    error_type: "transient" | "business" | "validation"
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
