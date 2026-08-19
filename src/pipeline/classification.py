from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

import anthropic

from pipeline.scratchpad import Scratchpad
from pipeline.tracing import get_tracer

_tracer = get_tracer(__name__)

VALID_CATEGORIES: frozenset[str] = frozenset(
    {"Architecture", "CI&T", "Cloud", "Coding", "ML & AI"}
)
_UNKNOWN = "unknown"

CATEGORY_DESCRIPTIONS: dict[str, str] = {
    "Architecture": "software design, system architecture, patterns, technical diagrams, ADRs",
    "CI&T": "corporate knowledge, internal processes, methodology, organisational guidelines, agile practices",
    "Cloud": "cloud computing, AWS, Azure, GCP, infrastructure as code, DevOps, containers",
    "Coding": "programming, development, algorithms, software engineering, code reviews, debugging",
    "ML & AI": "machine learning, artificial intelligence, data science, neural networks, LLMs, NLP",
    "unknown": "use only when the content genuinely does not fit any category above",
}

_all_names = ", ".join(list(VALID_CATEGORIES) + [_UNKNOWN])
_category_lines = "\n".join(f"- {k}: {v}" for k, v in CATEGORY_DESCRIPTIONS.items())
_SYSTEM_PROMPT = f"""\
You are a document classifier. Given a filename and a short excerpt,
respond with ONLY one of the following category names — nothing else:

{_all_names}

Categories:
{_category_lines}

Output the category name only. No punctuation. No explanation.\
"""


class ClassificationAgent:
    def __init__(self, vault_root: Path, scratchpad: Scratchpad) -> None:
        self._vault_root = vault_root
        self._scratchpad = scratchpad
        self._client = anthropic.AsyncAnthropic()
        self._model = os.environ["LIGHT_MODEL"]

    async def classify(self, md_path: Path) -> bool:
        """Classify one .md file and move it to the matching vault folder.

        Returns True if the file was moved, False otherwise.
        Failures are logged to the scratchpad; no exception is raised.
        """
        with _tracer.start_as_current_span("classify") as span:
            span.set_attribute("document.name", md_path.name)
            content = md_path.read_text(encoding="utf-8").strip()
            user_message = f"Filename: {md_path.stem}\n\n{content[:500]}"

            api_error = False
            t0 = time.monotonic()
            try:
                response = await self._client.messages.create(
                    model=self._model,
                    max_tokens=20,
                    system=_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_message}],
                )
            except Exception as exc:
                api_error = True
                latency_ms = (time.monotonic() - t0) * 1000
                span.set_attribute("eval.api_error", True)
                span.set_attribute("eval.latency_ms", latency_ms)
                span.set_attribute("eval.classified", False)
                self._scratchpad.error(
                    f"Classification API error for {md_path.name}: {exc}",
                    context={"file": str(md_path)},
                )
                return False
            latency_ms = (time.monotonic() - t0) * 1000

            category = response.content[0].text.strip()
            span.set_attribute("eval.category", category)
            span.set_attribute("eval.latency_ms", latency_ms)
            span.set_attribute("eval.api_error", False)

            if category == _UNKNOWN:
                span.set_attribute("eval.classified", False)
                self._scratchpad.warn(
                    f"Unclassifiable: {md_path.name}",
                    context={"file": str(md_path), "response": category},
                )
                return False

            if category not in VALID_CATEGORIES:
                span.set_attribute("eval.classified", False)
                self._scratchpad.warn(
                    f"Unexpected classification response '{category}': {md_path.name}",
                    context={"file": str(md_path), "response": category},
                )
                return False

            moved = self._move_to_vault(md_path, category)
            span.set_attribute("eval.classified", moved)
            return moved

    def _move_to_vault(self, md_path: Path, category: str) -> bool:
        destination_dir = self._vault_root / category
        if not destination_dir.exists():
            self._scratchpad.warn(
                f"Vault folder missing for '{category}': {destination_dir}",
                context={"file": str(md_path), "category": category},
            )
            return False
        shutil.move(str(md_path), str(destination_dir / md_path.name))
        self._scratchpad.info(
            f"Classified -> {category}: {md_path.name}",
            context={
                "file": str(md_path),
                "category": category,
                "destination": str(destination_dir),
            },
        )
        return True
