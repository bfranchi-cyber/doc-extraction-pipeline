"""Unit tests for pipeline.extraction and pipeline.extraction_server."""
from __future__ import annotations

import asyncio
import zipfile
from pathlib import Path

import pytest

from mcp.server.fastmcp.exceptions import ToolError

from pipeline.exceptions import PipelineError
from pipeline.extraction import ExtractionAgent
from pipeline.extraction_server import DOCX_MIME, make_extraction_app
from pipeline.models import CompactArtifact
from pipeline.scratchpad import Scratchpad


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_scratchpad(tmp_path: Path) -> Scratchpad:
    return Scratchpad(tmp_path / "scratchpad.jsonl")


def _write_minimal_docx(path: Path, paragraphs: list[str]) -> None:
    """Write a valid .docx using only stdlib (zipfile + xml)."""
    body_xml = "".join(
        f'<w:p><w:r><w:t xml:space="preserve">{p}</w:t></w:r></w:p>'
        for p in paragraphs
    )
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body_xml}<w:sectPr/></w:body></w:document>"
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>'
    )
    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml"'
        ' ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    word_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>'
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types_xml)
        z.writestr("_rels/.rels", rels_xml)
        z.writestr("word/_rels/document.xml.rels", word_rels_xml)
        z.writestr("word/document.xml", document_xml)


# ---------------------------------------------------------------------------
# Tests — parse_document tool
# ---------------------------------------------------------------------------


class TestParseDocument:
    def test_docx_returns_paragraph_text(self, tmp_path: Path) -> None:
        path = tmp_path / "doc.docx"
        _write_minimal_docx(path, ["First paragraph", "Second paragraph"])
        app = make_extraction_app(_make_scratchpad(tmp_path))
        result = asyncio.run(
            app._tool_manager.call_tool("parse_document", {"file_path": str(path)})
        )
        assert "First paragraph" in str(result)
        assert "Second paragraph" in str(result)

    def test_docx_text_order_preserved(self, tmp_path: Path) -> None:
        path = tmp_path / "order.docx"
        _write_minimal_docx(path, ["Alpha", "Beta"])
        app = make_extraction_app(_make_scratchpad(tmp_path))
        result = asyncio.run(
            app._tool_manager.call_tool("parse_document", {"file_path": str(path)})
        )
        text = str(result)
        assert text.index("Alpha") < text.index("Beta")

    def test_corrupted_docx_raises_pipeline_error(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.docx"
        path.write_bytes(b"not a docx")
        app = make_extraction_app(_make_scratchpad(tmp_path))
        with pytest.raises(ToolError) as exc_info:
            asyncio.run(
                app._tool_manager.call_tool("parse_document", {"file_path": str(path)})
            )
        assert isinstance(exc_info.value.__cause__, PipelineError)
        assert exc_info.value.__cause__.error_type == "business"


# ---------------------------------------------------------------------------
# Tests — ExtractionAgent.process() via mammoth (no mocking needed)
# ---------------------------------------------------------------------------


class TestExtractionAgentProcess:
    def test_happy_path_returns_compact_artifact(self, tmp_path: Path) -> None:
        path = tmp_path / "report.docx"
        _write_minimal_docx(path, ["Hello world"])
        agent = ExtractionAgent(_make_scratchpad(tmp_path))

        artifact = asyncio.run(agent.process(path))

        assert isinstance(artifact, dict)
        assert artifact["document_name"] == "report.docx"
        assert "Hello world" in artifact["extracted_text"]

    def test_extracted_text_contains_all_paragraphs(self, tmp_path: Path) -> None:
        path = tmp_path / "multi.docx"
        _write_minimal_docx(path, ["Paragraph one", "Paragraph two", "Paragraph three"])
        agent = ExtractionAgent(_make_scratchpad(tmp_path))

        artifact = asyncio.run(agent.process(path))

        assert "Paragraph one" in artifact["extracted_text"]
        assert "Paragraph two" in artifact["extracted_text"]
        assert "Paragraph three" in artifact["extracted_text"]

    def test_corrupted_file_raises_pipeline_error(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.docx"
        path.write_bytes(b"not a docx")
        agent = ExtractionAgent(_make_scratchpad(tmp_path))

        with pytest.raises(PipelineError) as exc_info:
            asyncio.run(agent.process(path))

        assert exc_info.value.error_type == "business"
        assert exc_info.value.is_retriable is False

    def test_document_name_matches_filename(self, tmp_path: Path) -> None:
        path = tmp_path / "my_report.docx"
        _write_minimal_docx(path, ["Content"])
        agent = ExtractionAgent(_make_scratchpad(tmp_path))

        artifact = asyncio.run(agent.process(path))

        assert artifact["document_name"] == "my_report.docx"
