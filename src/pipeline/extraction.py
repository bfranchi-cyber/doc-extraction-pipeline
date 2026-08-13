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

from pipeline.config import Config
from pipeline.exceptions import PipelineError
from pipeline.models import CompactArtifact, DriveFileMetadata, ImageMetadata
from pipeline.scratchpad import Scratchpad
from pipeline.extraction_server import ImageClient, make_extraction_app


class ExtractionAgent:
    def __init__(
        self,
        config: Config,
        image_client: ImageClient,
        scratchpad: Scratchpad,
    ) -> None:
        self._config = config
        self._image_client = image_client
        self._scratchpad = scratchpad
        self._client = anthropic.AsyncAnthropic()

    async def process(
        self, file_metadata: DriveFileMetadata, staging_path: Path
    ) -> CompactArtifact:
        """Run the full extraction pipeline for one file via Claude + MCP tools.

        Raises PipelineError on unrecoverable failure.
        """
        app = make_extraction_app(self._image_client, self._scratchpad)

        async with _mcp_session(app) as mcp_session:
            tools_result = await mcp_session.list_tools()
            tools = [async_mcp_tool(t, mcp_session) for t in tools_result.tools]

            task_prompt = _build_prompt(file_metadata, staging_path, self._config)

            try:
                runner = self._client.beta.messages.tool_runner(
                    model=self._config.extraction_model,
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
                        model=self._config.extraction_model,
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

        return _parse_final_message(final_message, file_metadata, self._config, self._scratchpad)


@asynccontextmanager
async def _mcp_session(app) -> AsyncIterator[ClientSession]:
    async with stdio_client(app) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


def _build_prompt(
    file_metadata: DriveFileMetadata, staging_path: Path, config: Config
) -> str:
    categories_list = "\n".join(f"- {c}" for c in config.categories)
    return (
        f"You are a document extraction assistant. Process the file below using the available tools.\n\n"
        f"File: {file_metadata.name}\n"
        f"MIME type: {file_metadata.mime_type}\n"
        f"File path on disk: {staging_path}\n"
        f"File ID: {file_metadata.file_id}\n"
        f"Staging directory: {config.staging_dir}\n\n"
        f"Steps:\n"
        f"1. Call parse_document with file_path=\"{staging_path}\" and mime_type=\"{file_metadata.mime_type}\".\n"
        f"2. Select the single best-fit category for this document from the list below. "
        f"You must return exactly one of these values:\n{categories_list}\n"
        f"3. Call stage_images with file_id=\"{file_metadata.file_id}\", "
        f"document_name=\"{file_metadata.name}\", staging_dir=\"{config.staging_dir}\".\n"
        f"4. Return ONLY a JSON object (no prose) in this exact shape:\n"
        f'   {{"extracted_text": "<verbatim text from parse_document>", "category": "<chosen category>"}}\n\n'
        f"Rules:\n"
        f"- Reproduce all text verbatim — no summarization or paraphrasing.\n"
        f"- Never include image bytes or base64 data in your response.\n"
        f"- The category field must be one of the values listed above.\n"
    )


def _parse_final_message(
    message,
    file_metadata: DriveFileMetadata,
    config: Config,
    scratchpad: Scratchpad,
) -> CompactArtifact:
    raw_text = ""
    for block in message.content:
        if hasattr(block, "text"):
            raw_text = block.text
            break

    try:
        payload = json.loads(raw_text)
        extracted_text = payload["extracted_text"]
        returned_category = payload["category"]
    except (json.JSONDecodeError, KeyError):
        # Attempt to extract JSON embedded in prose
        import re
        match = re.search(r'\{[^{}]*"extracted_text"[^{}]*\}', raw_text, re.DOTALL)
        if match:
            payload = json.loads(match.group())
            extracted_text = payload["extracted_text"]
            returned_category = payload["category"]
        else:
            raise PipelineError(
                error_type="validation",
                text=f"Claude returned non-JSON response for {file_metadata.name}",
                is_retriable=False,
                suggestion="Check the extraction prompt or model configuration.",
            )

    category = _apply_category_validation(returned_category, config.categories, scratchpad, file_metadata.name)

    images: list[ImageMetadata] = []
    for block in message.content:
        block_type = getattr(block, "type", None)
        if block_type == "tool_result" or (hasattr(block, "name") and getattr(block, "name", "") == "stage_images"):
            content = getattr(block, "content", None) or getattr(block, "output", None)
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and "image_id" in item:
                        images.append(
                            ImageMetadata(
                                image_id=item["image_id"],
                                alt_text=item.get("alt_text", ""),
                                staged_path=Path(item["staged_path"]),
                            )
                        )

    return CompactArtifact(
        file_id=file_metadata.file_id,
        document_name=file_metadata.name,
        extracted_text=extracted_text,
        category=category,
        images=images,
    )


def _apply_category_validation(
    returned: str,
    categories: tuple[str, ...],
    scratchpad: Scratchpad,
    document_name: str,
) -> str:
    """Validate and normalise a category returned by Claude (BR-E-04).

    1. Exact match → accept.
    2. Case-insensitive match → use canonical casing.
    3. No match → fallback to categories[0], log warning.
    """
    if returned in categories:
        return returned
    lower_map = {c.lower(): c for c in categories}
    if returned.lower() in lower_map:
        return lower_map[returned.lower()]
    fallback = categories[0]
    scratchpad.warn(
        f"ExtractionAgent: model returned unknown category '{returned}'; "
        f"defaulting to '{fallback}' for file {document_name}",
        context={"returned": returned, "fallback": fallback, "document": document_name},
    )
    return fallback
