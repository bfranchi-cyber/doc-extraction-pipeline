from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from pipeline.exceptions import PipelineError
from pipeline.scratchpad import Scratchpad

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def make_extraction_app(scratchpad: Scratchpad) -> FastMCP:
    """Return a fresh FastMCP app with a parse_document tool.

    A new instance is created per ExtractionAgent.process() call so concurrent
    agents never share mutable state.
    """
    app = FastMCP("extraction-server")

    @app.tool()
    async def parse_document(file_path: str) -> str:
        """Parse a .docx file and return its text in document reading order."""
        path = Path(file_path)
        try:
            import mammoth

            with open(path, "rb") as f:
                result = mammoth.extract_raw_text(f)
            return result.value.strip()
        except Exception as exc:
            raise PipelineError(
                error_type="business",
                text=f"Corrupted or unreadable file: {path.name}",
                is_retriable=False,
                suggestion="Check that the file is a valid .docx document.",
            ) from exc

    return app
