"""Unit tests for pipeline.extraction and pipeline.extraction_server."""
from __future__ import annotations

import asyncio
import json
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp.server.fastmcp.exceptions import ToolError

from pipeline.exceptions import PipelineError
from pipeline.extraction import ExtractionAgent, _build_prompt, _parse_final_message
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
# Tests — ExtractionAgent.process() with mocked tool_runner
# ---------------------------------------------------------------------------


def _make_final_message(extracted_text: str):
    payload = json.dumps({"extracted_text": extracted_text})
    text_block = MagicMock()
    text_block.text = payload
    text_block.type = "text"
    msg = MagicMock()
    msg.content = [text_block]
    return msg


class TestExtractionAgentProcess:
    def _run_with_mock_runner(self, agent, docx_path, final_message):
        mock_runner = MagicMock()
        mock_runner.until_done = AsyncMock(return_value=final_message)

        with patch.object(agent._client.beta.messages, "tool_runner", return_value=mock_runner):
            with patch("pipeline.extraction.stdio_client") as mock_stdio:
                mock_stdio.return_value.__aenter__ = AsyncMock(return_value=(AsyncMock(), AsyncMock()))
                mock_stdio.return_value.__aexit__ = AsyncMock(return_value=False)
                with patch("pipeline.extraction.ClientSession") as mock_session_cls:
                    mock_session = AsyncMock()
                    mock_session.list_tools = AsyncMock(return_value=MagicMock(tools=[]))
                    mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                    mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
                    return asyncio.run(agent.process(docx_path))

    def test_happy_path_returns_compact_artifact(self, tmp_path: Path) -> None:
        agent = ExtractionAgent(_make_scratchpad(tmp_path))
        docx_path = tmp_path / "report.docx"
        docx_path.write_bytes(b"")
        final_msg = _make_final_message("Extracted content here")

        artifact = self._run_with_mock_runner(agent, docx_path, final_msg)

        assert isinstance(artifact, dict)
        assert artifact["document_name"] == "report.docx"
        assert artifact["extracted_text"] == "Extracted content here"

    def test_rate_limit_then_success(self, tmp_path: Path) -> None:
        import anthropic as _anthropic

        agent = ExtractionAgent(_make_scratchpad(tmp_path))
        docx_path = tmp_path / "report.docx"
        docx_path.write_bytes(b"")
        final_msg = _make_final_message("Content")

        mock_runner_fail = MagicMock()
        mock_runner_fail.until_done = AsyncMock(
            side_effect=_anthropic.RateLimitError.__new__(_anthropic.RateLimitError)
        )
        mock_runner_ok = MagicMock()
        mock_runner_ok.until_done = AsyncMock(return_value=final_msg)
        call_count = {"n": 0}

        def tool_runner_factory(**kwargs):
            call_count["n"] += 1
            return mock_runner_fail if call_count["n"] == 1 else mock_runner_ok

        with patch.object(agent._client.beta.messages, "tool_runner", side_effect=tool_runner_factory):
            with patch("pipeline.extraction.stdio_client") as mock_stdio:
                mock_stdio.return_value.__aenter__ = AsyncMock(return_value=(AsyncMock(), AsyncMock()))
                mock_stdio.return_value.__aexit__ = AsyncMock(return_value=False)
                with patch("pipeline.extraction.ClientSession") as mock_session_cls:
                    mock_session = AsyncMock()
                    mock_session.list_tools = AsyncMock(return_value=MagicMock(tools=[]))
                    mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                    mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
                    with patch("pipeline.extraction.asyncio.sleep", new_callable=AsyncMock):
                        artifact = asyncio.run(agent.process(docx_path))

        assert artifact["extracted_text"] == "Content"

    def test_rate_limit_twice_raises_transient(self, tmp_path: Path) -> None:
        import anthropic as _anthropic

        agent = ExtractionAgent(_make_scratchpad(tmp_path))
        docx_path = tmp_path / "report.docx"
        docx_path.write_bytes(b"")

        mock_runner = MagicMock()
        mock_runner.until_done = AsyncMock(
            side_effect=_anthropic.RateLimitError.__new__(_anthropic.RateLimitError)
        )

        with patch.object(agent._client.beta.messages, "tool_runner", return_value=mock_runner):
            with patch("pipeline.extraction.stdio_client") as mock_stdio:
                mock_stdio.return_value.__aenter__ = AsyncMock(return_value=(AsyncMock(), AsyncMock()))
                mock_stdio.return_value.__aexit__ = AsyncMock(return_value=False)
                with patch("pipeline.extraction.ClientSession") as mock_session_cls:
                    mock_session = AsyncMock()
                    mock_session.list_tools = AsyncMock(return_value=MagicMock(tools=[]))
                    mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                    mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
                    with patch("pipeline.extraction.asyncio.sleep", new_callable=AsyncMock):
                        with pytest.raises(PipelineError) as exc_info:
                            asyncio.run(agent.process(docx_path))

        assert exc_info.value.error_type == "transient"
        assert exc_info.value.is_retriable is True
