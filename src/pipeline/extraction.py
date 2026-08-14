from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import anthropic
from anthropic.lib.tools.mcp import async_mcp_tool
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client

from pipeline.exceptions import PipelineError
from pipeline.models import CompactArtifact
from pipeline.scratchpad import Scratchpad
from pipeline.extraction_server import make_extraction_app

_EXTRACTION_MODEL = "claude-haiku-4-5-20251001"


class ExtractionAgent:
    def __init__(self, scratchpad: Scratchpad) -> None:
        self._scratchpad = scratchpad
        self._client = anthropic.AsyncAnthropic()

    async def process(self, docx_path: Path) -> CompactArtifact:
        """Extract text from a .docx file via Claude + MCP tools.

        Returns a CompactArtifact with document_name and extracted_text.
        Raises PipelineError on unrecoverable failure.
        """
        app = make_extraction_app(self._scratchpad)

        async with _mcp_session(app) as mcp_session:
            tools_result = await mcp_session.list_tools()
            tools = [async_mcp_tool(t, mcp_session) for t in tools_result.tools]

            task_prompt = _build_prompt(docx_path)

            try:
                runner = self._client.beta.messages.tool_runner(
                    model=_EXTRACTION_MODEL,
                    max_tokens=4096,
                    messages=[{"role": "user", "content": task_prompt}],
                    tools=tools,
                )
                final_message = await runner.until_done()
            except anthropic.RateLimitError as exc:
                retry_after = int(getattr(exc, "retry_after", None) or 60)
                await asyncio.sleep(retry_after)
                try:
                    runner = self._client.beta.messages.tool_runner(
                        model=_EXTRACTION_MODEL,
                        max_tokens=4096,
                        messages=[{"role": "user", "content": task_prompt}],
                        tools=tools,
                    )
                    final_message = await runner.until_done()
                except anthropic.RateLimitError as exc2:
                    raise PipelineError(
                        error_type="transient",
                        text="Rate-limited by Claude API after retry",
                        is_retriable=True,
                        suggestion="Wait and re-run the pipeline.",
                    ) from exc2
                except anthropic.APIStatusError as exc2:
                    if exc2.status_code >= 500:
                        raise PipelineError(
                            error_type="transient",
                            text=f"Claude API server error: {exc2.status_code}",
                            is_retriable=True,
                            suggestion="Re-run the pipeline.",
                        ) from exc2
                    raise PipelineError(
                        error_type="validation",
                        text=f"Claude API client error: {exc2.status_code}",
                        is_retriable=False,
                        suggestion="Check the request configuration.",
                    ) from exc2
            except anthropic.APIStatusError as exc:
                if exc.status_code >= 500:
                    raise PipelineError(
                        error_type="transient",
                        text=f"Claude API server error: {exc.status_code}",
                        is_retriable=True,
                        suggestion="Re-run the pipeline.",
                    ) from exc
                raise PipelineError(
                    error_type="validation",
                    text=f"Claude API client error: {exc.status_code}",
                    is_retriable=False,
                    suggestion="Check the request configuration.",
                ) from exc

        return _parse_final_message(final_message, docx_path)


@asynccontextmanager
async def _mcp_session(app) -> AsyncIterator[ClientSession]:
    async with stdio_client(app) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


def _build_prompt(docx_path: Path) -> str:
    return (
        f"You are a document extraction assistant. Extract all text from the file below.\n\n"
        f"File: {docx_path.name}\n"
        f"File path on disk: {docx_path}\n\n"
        f"Steps:\n"
        f"1. Call parse_document with file_path=\"{docx_path}\".\n"
        f"2. Return ONLY a JSON object (no prose) in this exact shape:\n"
        f'   {{"extracted_text": "<verbatim text from parse_document>"}}\n\n'
        f"Rules:\n"
        f"- Reproduce all text verbatim — no summarization or paraphrasing.\n"
        f"- Do not add any commentary, headers, or explanation outside the JSON object.\n"
    )


def _parse_final_message(message, docx_path: Path) -> CompactArtifact:
    raw_text = ""
    for block in message.content:
        if hasattr(block, "text"):
            raw_text = block.text
            break

    try:
        payload = json.loads(raw_text)
        extracted_text = payload["extracted_text"]
    except (json.JSONDecodeError, KeyError):
        import re
        match = re.search(r'\{[^{}]*"extracted_text"[^{}]*\}', raw_text, re.DOTALL)
        if match:
            payload = json.loads(match.group())
            extracted_text = payload["extracted_text"]
        else:
            raise PipelineError(
                error_type="validation",
                text=f"Claude returned non-JSON response for {docx_path.name}",
                is_retriable=False,
                suggestion="Check the extraction prompt or model configuration.",
            )

    return CompactArtifact(
        document_name=docx_path.name,
        extracted_text=extracted_text,
    )
