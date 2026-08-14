from __future__ import annotations

from pathlib import Path

from pipeline.exceptions import PipelineError
from pipeline.models import CompactArtifact
from pipeline.scratchpad import Scratchpad


class ExtractionAgent:
    def __init__(self, scratchpad: Scratchpad) -> None:
        self._scratchpad = scratchpad

    async def process(self, docx_path: Path) -> CompactArtifact:
        """Extract text from a .docx file and return a CompactArtifact.

        Raises PipelineError on unrecoverable failure.
        """
        try:
            import mammoth

            with open(docx_path, "rb") as f:
                result = mammoth.extract_raw_text(f)
            extracted_text = result.value.strip()
        except Exception as exc:
            raise PipelineError(
                error_type="business",
                text=f"Corrupted or unreadable file: {docx_path.name}",
                is_retriable=False,
                suggestion="Check that the file is a valid .docx document.",
            ) from exc

        return CompactArtifact(
            document_name=docx_path.name,
            extracted_text=extracted_text,
        )
