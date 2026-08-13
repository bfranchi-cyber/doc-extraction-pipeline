"""Unit tests for pipeline.extraction and pipeline.extraction_server."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp.server.fastmcp.exceptions import ToolError

from pipeline.exceptions import PipelineError
from pipeline.extraction import ExtractionAgent, _apply_category_validation, _build_prompt
from pipeline.extraction_server import (
    DOCX_MIME,
    PDF_MIME,
    ImageClient,
    _resolve_image_filename,
    make_extraction_app,
)
from pipeline.models import CompactArtifact, DriveFileMetadata, ImageMetadata
from pipeline.scratchpad import Scratchpad


# ---------------------------------------------------------------------------
# Helpers / factories
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 8, 13, 0, 0, 0, tzinfo=timezone.utc)


def _make_config(tmp_path: Path, categories: tuple[str, ...] = ("Finance", "HR", "Legal")):
    from pipeline.config import Config

    vault = tmp_path / "vault"
    vault.mkdir(parents=True, exist_ok=True)
    images = tmp_path / "images"
    images.mkdir(parents=True, exist_ok=True)
    manifest = tmp_path / "manifest"
    manifest.mkdir(parents=True, exist_ok=True)
    staging = tmp_path / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    creds = tmp_path / "creds.json"
    creds.write_text('{"type": "authorized_user"}', encoding="utf-8")

    return Config(
        vault_path=vault,
        images_path=images,
        manifest_dir=manifest,
        staging_dir=staging,
        scratchpad_path=tmp_path / "scratchpad.jsonl",
        credentials_path=creds,
        drive_folder_id="folder-123",
        categories=categories,
        extraction_model="claude-haiku-4-5-20251001",
        analysis_model="claude-haiku-4-5-20251001",
        eligibility_days=30,
    )


def _make_metadata(
    mime_type: str = DOCX_MIME,
    file_id: str = "file-abc",
    name: str = "report.docx",
) -> DriveFileMetadata:
    return DriveFileMetadata(
        file_id=file_id,
        name=name,
        mime_type=mime_type,
        last_modified=_NOW,
        download_url="https://example.com/download",
    )


def _make_scratchpad(tmp_path: Path) -> Scratchpad:
    return Scratchpad(tmp_path / "scratchpad.jsonl")


class MockImageClient:
    def __init__(self, items: list[dict] | None = None, fail_ids: set[str] | None = None):
        self._items = items or []
        self._fail_ids = fail_ids or set()

    def list_images(self, file_id: str) -> list[dict]:
        return self._items

    def download_image(self, image_id: str, destination: Path) -> None:
        if image_id in self._fail_ids:
            raise OSError(f"download failed for {image_id}")
        destination.write_bytes(b"fake-image-data")


def _write_minimal_docx(path: Path, paragraphs: list[str]) -> None:
    import docx

    doc = docx.Document()
    for text in paragraphs:
        doc.add_paragraph(text)
    doc.save(str(path))


def _write_minimal_pdf(path: Path, text: str = "Hello PDF") -> None:
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(str(path))


# ---------------------------------------------------------------------------
# Tests — extraction_server tools (called directly, no Claude)
# ---------------------------------------------------------------------------


class TestParseDocument:
    def test_docx_returns_paragraph_text(self, tmp_path: Path) -> None:
        path = tmp_path / "doc.docx"
        _write_minimal_docx(path, ["First paragraph", "Second paragraph"])
        app = make_extraction_app(MockImageClient(), _make_scratchpad(tmp_path))
        result = asyncio.run(app._tool_manager.call_tool("parse_document", {"file_path": str(path), "mime_type": DOCX_MIME}))
        assert "First paragraph" in str(result)
        assert "Second paragraph" in str(result)

    def test_pdf_returns_page_text(self, tmp_path: Path) -> None:
        path = tmp_path / "doc.pdf"
        _write_minimal_pdf(path, "Hello PDF content")
        app = make_extraction_app(MockImageClient(), _make_scratchpad(tmp_path))
        result = asyncio.run(app._tool_manager.call_tool("parse_document", {"file_path": str(path), "mime_type": PDF_MIME}))
        assert "Hello PDF" in str(result)

    def test_docx_text_order_preserved(self, tmp_path: Path) -> None:
        path = tmp_path / "order.docx"
        _write_minimal_docx(path, ["Alpha", "Beta"])
        app = make_extraction_app(MockImageClient(), _make_scratchpad(tmp_path))
        result = asyncio.run(app._tool_manager.call_tool("parse_document", {"file_path": str(path), "mime_type": DOCX_MIME}))
        text = str(result)
        assert text.index("Alpha") < text.index("Beta")

    def test_corrupted_docx_raises_pipeline_error(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.docx"
        path.write_bytes(b"not a docx")
        app = make_extraction_app(MockImageClient(), _make_scratchpad(tmp_path))
        with pytest.raises(ToolError) as exc_info:
            asyncio.run(app._tool_manager.call_tool("parse_document", {"file_path": str(path), "mime_type": DOCX_MIME}))
        assert isinstance(exc_info.value.__cause__, PipelineError)
        assert exc_info.value.__cause__.error_type == "business"

    def test_corrupted_pdf_raises_pipeline_error(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.pdf"
        path.write_bytes(b"not a pdf")
        app = make_extraction_app(MockImageClient(), _make_scratchpad(tmp_path))
        with pytest.raises(ToolError) as exc_info:
            asyncio.run(app._tool_manager.call_tool("parse_document", {"file_path": str(path), "mime_type": PDF_MIME}))
        assert isinstance(exc_info.value.__cause__, PipelineError)
        assert exc_info.value.__cause__.error_type == "business"

    def test_unsupported_mime_raises_validation_error(self, tmp_path: Path) -> None:
        path = tmp_path / "file.txt"
        path.write_text("some content")
        app = make_extraction_app(MockImageClient(), _make_scratchpad(tmp_path))
        with pytest.raises(ToolError) as exc_info:
            asyncio.run(app._tool_manager.call_tool("parse_document", {"file_path": str(path), "mime_type": "text/plain"}))
        assert isinstance(exc_info.value.__cause__, PipelineError)
        assert exc_info.value.__cause__.error_type == "validation"


class TestStageImages:
    def test_two_images_downloaded_successfully(self, tmp_path: Path) -> None:
        items = [
            {"id": "img1", "filename": "photo.png", "alt_text": "A photo"},
            {"id": "img2", "filename": "chart.jpg", "alt_text": "A chart"},
        ]
        client = MockImageClient(items=items)
        scratchpad = _make_scratchpad(tmp_path)
        app = make_extraction_app(client, scratchpad)
        result = asyncio.run(app._tool_manager.call_tool(
            "stage_images",
            {"file_id": "file-abc", "document_name": "report.docx", "staging_dir": str(tmp_path)},
        ))
        assert len(result) == 2
        assert result[0]["image_id"] == "img1"
        assert result[1]["image_id"] == "img2"

    def test_one_download_fails_returns_partial(self, tmp_path: Path) -> None:
        items = [
            {"id": "img1", "filename": "ok.png", "alt_text": ""},
            {"id": "img2", "filename": "bad.png", "alt_text": ""},
        ]
        client = MockImageClient(items=items, fail_ids={"img2"})
        scratchpad = _make_scratchpad(tmp_path)
        app = make_extraction_app(client, scratchpad)
        result = asyncio.run(app._tool_manager.call_tool(
            "stage_images",
            {"file_id": "file-abc", "document_name": "report.docx", "staging_dir": str(tmp_path)},
        ))
        assert len(result) == 1
        assert result[0]["image_id"] == "img1"

    def test_all_downloads_fail_returns_empty(self, tmp_path: Path) -> None:
        items = [{"id": "img1", "filename": "x.png", "alt_text": ""}]
        client = MockImageClient(items=items, fail_ids={"img1"})
        app = make_extraction_app(client, _make_scratchpad(tmp_path))
        result = asyncio.run(app._tool_manager.call_tool(
            "stage_images",
            {"file_id": "file-abc", "document_name": "report.docx", "staging_dir": str(tmp_path)},
        ))
        assert result == []

    def test_image_dicts_contain_no_raw_bytes(self, tmp_path: Path) -> None:
        items = [{"id": "img1", "filename": "photo.png", "alt_text": "Alt"}]
        client = MockImageClient(items=items)
        app = make_extraction_app(client, _make_scratchpad(tmp_path))
        result = asyncio.run(app._tool_manager.call_tool(
            "stage_images",
            {"file_id": "file-abc", "document_name": "report.docx", "staging_dir": str(tmp_path)},
        ))
        for item in result:
            assert all(isinstance(v, str) for v in item.values())


class TestResolveImageFilename:
    def test_no_collision_returns_base(self, tmp_path: Path) -> None:
        assert _resolve_image_filename(tmp_path, "abc", "photo.png") == "abc_photo.png"

    def test_collision_appends_suffix(self, tmp_path: Path) -> None:
        (tmp_path / "abc_photo.png").write_bytes(b"")
        assert _resolve_image_filename(tmp_path, "abc", "photo.png") == "abc_photo_(2).png"

    def test_double_collision(self, tmp_path: Path) -> None:
        (tmp_path / "abc_photo.png").write_bytes(b"")
        (tmp_path / "abc_photo_(2).png").write_bytes(b"")
        assert _resolve_image_filename(tmp_path, "abc", "photo.png") == "abc_photo_(3).png"


# ---------------------------------------------------------------------------
# Tests — _apply_category_validation
# ---------------------------------------------------------------------------


class TestApplyCategoryValidation:
    _CATS = ("Finance", "HR", "Legal")

    def _validate(self, returned: str, cats=None, tmp_path=None) -> str:
        import tempfile

        td = tmp_path or Path(tempfile.mkdtemp())
        sp = Scratchpad(td / "sp.jsonl")
        return _apply_category_validation(returned, cats or self._CATS, sp, "doc.docx")

    def test_exact_match(self) -> None:
        assert self._validate("Finance") == "Finance"

    def test_case_insensitive_match(self) -> None:
        assert self._validate("finance") == "Finance"
        assert self._validate("HR") == "HR"
        assert self._validate("LEGAL") == "Legal"

    def test_no_match_fallback_to_first(self, tmp_path: Path) -> None:
        result = self._validate("Unknown", tmp_path=tmp_path)
        assert result == "Finance"
        log = (tmp_path / "sp.jsonl").read_text()
        assert "Unknown" in log
        assert "Finance" in log

    def test_fallback_logs_warning(self, tmp_path: Path) -> None:
        self._validate("Nope", tmp_path=tmp_path)
        log = (tmp_path / "sp.jsonl").read_text()
        assert '"level": "WARN"' in log


# ---------------------------------------------------------------------------
# Tests — ExtractionAgent.process() with mocked tool_runner
# ---------------------------------------------------------------------------


def _make_final_message(extracted_text: str, category: str, images: list[dict] | None = None) -> Any:
    """Build a mock final message that _parse_final_message can consume."""
    payload = json.dumps({"extracted_text": extracted_text, "category": category})

    text_block = MagicMock()
    text_block.text = payload
    text_block.type = "text"

    msg = MagicMock()
    msg.content = [text_block]
    return msg


class TestExtractionAgentProcess:
    def _make_agent(self, tmp_path: Path, image_client=None, categories=("Finance", "HR")):
        config = _make_config(tmp_path, categories=categories)
        scratchpad = _make_scratchpad(tmp_path)
        ic = image_client or MockImageClient()
        return ExtractionAgent(config, ic, scratchpad), config, scratchpad

    def _run_with_mock_runner(self, agent, file_metadata, staging_path, final_message):
        mock_runner = MagicMock()
        mock_runner.until_done = AsyncMock(return_value=final_message)

        with patch.object(agent._client.beta.messages, "tool_runner", return_value=mock_runner):
            with patch("pipeline.extraction.stdio_client") as mock_stdio:
                mock_read = AsyncMock()
                mock_write = AsyncMock()
                mock_stdio.return_value.__aenter__ = AsyncMock(return_value=(mock_read, mock_write))
                mock_stdio.return_value.__aexit__ = AsyncMock(return_value=False)

                with patch("pipeline.extraction.ClientSession") as mock_session_cls:
                    mock_session = AsyncMock()
                    mock_session.list_tools = AsyncMock(return_value=MagicMock(tools=[]))
                    mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                    mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

                    return asyncio.run(agent.process(file_metadata, staging_path))

    def test_happy_path_returns_compact_artifact(self, tmp_path: Path) -> None:
        agent, config, _ = self._make_agent(tmp_path)
        meta = _make_metadata()
        staging = tmp_path / "report.docx"
        staging.write_bytes(b"")
        final_msg = _make_final_message("Extracted content", "Finance")

        artifact = self._run_with_mock_runner(agent, meta, staging, final_msg)

        assert isinstance(artifact, dict)  # CompactArtifact is a TypedDict
        assert artifact["file_id"] == meta.file_id
        assert artifact["document_name"] == meta.name
        assert artifact["category"] == "Finance"
        assert artifact["extracted_text"] == "Extracted content"

    def test_category_fallback_on_unknown(self, tmp_path: Path) -> None:
        agent, _, _ = self._make_agent(tmp_path, categories=("Finance", "HR"))
        meta = _make_metadata()
        staging = tmp_path / "report.docx"
        staging.write_bytes(b"")
        final_msg = _make_final_message("Content", "Unknown")

        artifact = self._run_with_mock_runner(agent, meta, staging, final_msg)
        assert artifact["category"] == "Finance"

    def test_category_case_insensitive_match(self, tmp_path: Path) -> None:
        agent, _, _ = self._make_agent(tmp_path, categories=("Finance", "HR"))
        meta = _make_metadata()
        staging = tmp_path / "report.docx"
        staging.write_bytes(b"")
        final_msg = _make_final_message("Content", "finance")

        artifact = self._run_with_mock_runner(agent, meta, staging, final_msg)
        assert artifact["category"] == "Finance"

    def test_rate_limit_then_success(self, tmp_path: Path) -> None:
        import anthropic as _anthropic

        agent, config, _ = self._make_agent(tmp_path)
        meta = _make_metadata()
        staging = tmp_path / "report.docx"
        staging.write_bytes(b"")
        final_msg = _make_final_message("Content", "HR")

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
                        artifact = asyncio.run(agent.process(meta, staging))

        assert artifact["category"] == "HR"

    def test_rate_limit_twice_raises_transient(self, tmp_path: Path) -> None:
        import anthropic as _anthropic

        agent, _, _ = self._make_agent(tmp_path)
        meta = _make_metadata()
        staging = tmp_path / "report.docx"
        staging.write_bytes(b"")

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
                            asyncio.run(agent.process(meta, staging))

        assert exc_info.value.error_type == "transient"
        assert exc_info.value.is_retriable is True

    def test_concurrent_agents_independent(self, tmp_path: Path) -> None:
        """Two agents with different metadata produce independent results (BR-E-09)."""
        agent1, _, _ = self._make_agent(tmp_path / "a1")
        agent2, _, _ = self._make_agent(tmp_path / "a2")

        meta1 = _make_metadata(file_id="file-1", name="doc1.docx")
        meta2 = _make_metadata(file_id="file-2", name="doc2.docx")
        staging1 = tmp_path / "doc1.docx"
        staging1.write_bytes(b"")
        staging2 = tmp_path / "doc2.docx"
        staging2.write_bytes(b"")

        final1 = _make_final_message("Content one", "Finance")
        final2 = _make_final_message("Content two", "HR")

        def run_agent(agent, meta, staging, final_msg):
            mock_runner = MagicMock()
            mock_runner.until_done = AsyncMock(return_value=final_msg)
            with patch.object(agent._client.beta.messages, "tool_runner", return_value=mock_runner):
                with patch("pipeline.extraction.stdio_client") as mock_stdio:
                    mock_stdio.return_value.__aenter__ = AsyncMock(return_value=(AsyncMock(), AsyncMock()))
                    mock_stdio.return_value.__aexit__ = AsyncMock(return_value=False)
                    with patch("pipeline.extraction.ClientSession") as mock_session_cls:
                        mock_session = AsyncMock()
                        mock_session.list_tools = AsyncMock(return_value=MagicMock(tools=[]))
                        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
                        return asyncio.run(agent.process(meta, staging))

        a1 = run_agent(agent1, meta1, staging1, final1)
        a2 = run_agent(agent2, meta2, staging2, final2)

        assert a1["file_id"] == "file-1"
        assert a2["file_id"] == "file-2"
        assert a1["category"] == "Finance"
        assert a2["category"] == "HR"
