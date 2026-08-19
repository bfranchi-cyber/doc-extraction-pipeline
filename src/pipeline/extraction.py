from __future__ import annotations

import asyncio
from pathlib import Path

from pipeline.exceptions import PipelineError
from pipeline.models import CompactArtifact
from pipeline.scratchpad import Scratchpad
from pipeline.tracing import get_tracer

_tracer = get_tracer(__name__)


class Extractor:
    def __init__(self, scratchpad: Scratchpad) -> None:
        self._scratchpad = scratchpad

    async def process(self, docx_path: Path) -> CompactArtifact:
        """Extract text from a .docx file and return a CompactArtifact.

        Raises PipelineError on unrecoverable failure.
        """
        with _tracer.start_as_current_span("extract") as span:
            span.set_attribute("document.name", docx_path.name)
            try:
                import mammoth

                def _extract() -> str:
                    with open(docx_path, "rb") as f:
                        return mammoth.extract_raw_text(f).value.strip()

                extracted_text = await asyncio.to_thread(_extract)
            except Exception as exc:
                raise PipelineError(
                    error_type="business",
                    text=f"Corrupted or unreadable file: {docx_path.name}",
                    is_retriable=False,
                    suggestion="Check that the file is a valid .docx document.",
                ) from exc

            span.set_attribute("extracted_text_length", len(extracted_text))
            return CompactArtifact(
                document_name=docx_path.name,
                extracted_text=extracted_text,
            )
