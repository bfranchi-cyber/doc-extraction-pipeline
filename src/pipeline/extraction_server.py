from __future__ import annotations

from pathlib import Path
from typing import Protocol

from mcp.server.fastmcp import FastMCP

from pipeline.exceptions import PipelineError
from pipeline.scratchpad import Scratchpad

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PDF_MIME = "application/pdf"


class ImageClient(Protocol):
    def list_images(self, file_id: str) -> list[dict]: ...
    def download_image(self, image_id: str, destination: Path) -> None: ...


def make_extraction_app(image_client: ImageClient, scratchpad: Scratchpad) -> FastMCP:
    """Return a fresh FastMCP app with parse_document and stage_images tools.

    A new instance is created per ExtractionAgent.process() call so concurrent
    agents never share mutable state (BR-E-09).
    """
    app = FastMCP("extraction-server")

    @app.tool()
    async def parse_document(file_path: str, mime_type: str) -> str:
        """Parse a .docx or .pdf file and return its text in document reading order."""
        path = Path(file_path)
        if mime_type == DOCX_MIME:
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
                    suggestion="Re-download or remove the file from Drive.",
                ) from exc

        if mime_type == PDF_MIME:
            try:
                import pypdf

                reader = pypdf.PdfReader(str(path))
                pages = [page.extract_text() or "" for page in reader.pages]
                return "\n".join(pages).strip()
            except Exception as exc:
                raise PipelineError(
                    error_type="business",
                    text=f"Corrupted or unreadable file: {path.name}",
                    is_retriable=False,
                    suggestion="Re-download or remove the file from Drive.",
                ) from exc

        raise PipelineError(
            error_type="validation",
            text=f"Unsupported MIME type: {mime_type}",
            is_retriable=False,
            suggestion="Only .docx and .pdf files are supported.",
        )

    @app.tool()
    async def stage_images(
        file_id: str, document_name: str, staging_dir: str
    ) -> list[dict]:
        """Download images for a document to a local staging directory.

        Returns a list of dicts with keys image_id, alt_text, staged_path.
        Individual download failures are skipped with a warning (BR-E-06).
        """
        results: list[dict] = []
        try:
            items = image_client.list_images(file_id)
        except Exception as exc:
            scratchpad.warn(
                f"ExtractionAgent: failed to list images for {document_name}: {exc}",
                context={"file_id": file_id},
            )
            return results

        dest_dir = Path(staging_dir) / Path(document_name).stem
        dest_dir.mkdir(parents=True, exist_ok=True)

        for item in items:
            image_id = item["id"]
            original_filename = item.get("filename", image_id)
            filename = _resolve_image_filename(dest_dir, image_id, original_filename)
            dest = dest_dir / filename
            try:
                image_client.download_image(image_id, dest)
            except Exception as exc:
                scratchpad.warn(
                    f"ExtractionAgent: failed to stage image {image_id} for {document_name}: {exc}",
                    context={"file_id": file_id, "image_id": image_id},
                )
                continue
            results.append(
                {
                    "image_id": image_id,
                    "alt_text": item.get("alt_text", ""),
                    "staged_path": str(dest),
                }
            )

        return results

    return app


def _resolve_image_filename(dest_dir: Path, image_id: str, original_filename: str) -> str:
    """Return a collision-safe filename: {image_id}_{original_filename}[_(N)]."""
    base = f"{image_id}_{original_filename}"
    candidate = base
    n = 2
    while (dest_dir / candidate).exists():
        stem = Path(base).stem
        suffix = Path(base).suffix
        candidate = f"{stem}_({n}){suffix}"
        n += 1
    return candidate
