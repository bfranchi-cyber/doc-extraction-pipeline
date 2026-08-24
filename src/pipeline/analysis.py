from __future__ import annotations

import os
import time
from pathlib import Path

import anthropic

from pipeline.frontmatter import write_frontmatter
from pipeline.models import AnalysisResult
from pipeline.scratchpad import Scratchpad
from pipeline.tracing import get_tracer

_tracer = get_tracer(__name__)

_ANALYSIS_TOOL: dict = {
    "name": "record_analysis",
    "description": "Record the structured analysis of the document.",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Concise 1-2 sentence summary of the document.",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 3,
                "maxItems": 5,
                "description": "3 to 5 relevant keyword tags.",
            },
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Confidence in the analysis, between 0.0 and 1.0.",
            },
        },
        "required": ["summary", "tags", "confidence"],
    },
}

_SYSTEM_PROMPT = (
    "You are a technical document analyst. "
    "Read the provided document excerpt and call the record_analysis tool "
    "with a concise summary, 3-5 keyword tags, and your confidence level."
)


class AnalysisAgent:
    def __init__(self, scratchpad: Scratchpad) -> None:
        self._scratchpad = scratchpad
        self._client = anthropic.AsyncAnthropic()
        self._model = os.environ["MEDIUM_MODEL"]

    async def analyze(self, md_path: Path) -> AnalysisResult | None:
        """Enrich *md_path* with YAML frontmatter from LLM analysis.

        Returns the AnalysisResult on success, None on failure.
        The file is side-effected with frontmatter prepended on success.
        Failures are logged to the scratchpad; no exception is raised.
        """
        with _tracer.start_as_current_span("analyze") as span:
            span.set_attribute("document.name", md_path.name)

            text = md_path.read_text(encoding="utf-8").strip()
            user_message = f"Document: {md_path.stem}\n\n{text[:2000]}"

            api_error = False
            confidence = 0.0
            t0 = time.monotonic()
            try:
                response = await self._client.messages.create(
                    model=self._model,
                    max_tokens=512,
                    system=_SYSTEM_PROMPT,
                    tools=[_ANALYSIS_TOOL],
                    tool_choice={"type": "tool", "name": "record_analysis"},
                    messages=[{"role": "user", "content": user_message}],
                )
                tool_block = next(
                    (b for b in response.content if b.type == "tool_use"),
                    None,
                )
                if tool_block is None:
                    raise ValueError("No tool_use block in response")

                result: AnalysisResult = {
                    "summary": tool_block.input["summary"],
                    "tags": tool_block.input["tags"],
                    "confidence": float(tool_block.input["confidence"]),
                }
                confidence = result["confidence"]
            except Exception as exc:
                api_error = True
                latency_ms = (time.monotonic() - t0) * 1000
                span.set_attribute("eval.api_error", True)
                span.set_attribute("eval.latency_ms", latency_ms)
                span.set_attribute("eval.confidence", 0.0)
                self._scratchpad.error(
                    f"Analysis failed for {md_path.name}: {exc}",
                    context={"file": str(md_path)},
                )
                return None

            latency_ms = (time.monotonic() - t0) * 1000
            span.set_attribute("eval.api_error", False)
            span.set_attribute("eval.latency_ms", latency_ms)
            span.set_attribute("eval.confidence", confidence)

            write_frontmatter(md_path, result)
            return result
