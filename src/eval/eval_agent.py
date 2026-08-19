from __future__ import annotations

import os

import asyncio

import anthropic

from pipeline.classification import CATEGORY_DESCRIPTIONS, VALID_CATEGORIES


class EvalAgent:
    def __init__(self) -> None:
        self._model = os.environ["MEDIUM_MODEL"]
        self._phoenix_host = os.environ.get("PHOENIX_HOST", "localhost:6006")
        self._client = anthropic.AsyncAnthropic()

    async def run_evals(self) -> dict:
        """Query Phoenix for unevaluated classify spans and judge each one.

        Returns a summary dict with keys: evaluated, correct, incorrect.
        """
        import phoenix as px

        client = px.Client(endpoint=f"http://{self._phoenix_host}")
        spans = client.get_spans_dataframe(project_name="docs-extraction")

        if spans is None or spans.empty:
            return {"evaluated": 0, "correct": 0, "incorrect": 0}

        classify_spans = spans[
            (spans.get("span_kind", "") == "CHAIN")
            | (spans.index.get_level_values("name") == "classify")
            if hasattr(spans.index, "get_level_values")
            else spans["name"] == "classify"
        ] if "name" in spans.columns else spans

        unevaluated = [
            row
            for _, row in classify_spans.iterrows()
            if "eval.judge_verdict" not in (row.get("attributes") or {})
        ]

        results = {"evaluated": 0, "correct": 0, "incorrect": 0}
        evaluations = []

        verdicts = await asyncio.gather(*[self._judge_span(row) for row in unevaluated])

        for span_row, verdict in zip(unevaluated, verdicts):
            if verdict == "skipped":
                continue
            results["evaluated"] += 1
            results[verdict] += 1
            evaluations.append(
                px.Evaluation(
                    span_id=span_row.name if hasattr(span_row, "name") else str(span_row.get("context.span_id", "")),
                    name="eval.judge_verdict",
                    result=px.EvaluationResult(label=verdict),
                )
            )

        if evaluations:
            client.log_evaluations(*evaluations)

        return results

    async def _judge_span(self, span) -> str:
        """Judge a single classify span as 'correct', 'incorrect', or 'skipped'."""
        try:
            attrs = span.get("attributes") or {}
            document_name = attrs.get("document.name", "unknown")
            category = attrs.get("eval.category", "")
            input_value = span.get("input.value", "")

            category_list = "\n".join(
                f"- {k}: {v}" for k, v in CATEGORY_DESCRIPTIONS.items()
            )
            valid_names = ", ".join(sorted(VALID_CATEGORIES))

            judge_prompt = (
                f"You are evaluating a document classification.\n\n"
                f"Document: {document_name}\n"
                f"Excerpt: {str(input_value)[:500]}\n"
                f"Predicted category: {category}\n\n"
                f"Valid categories and their descriptions:\n{category_list}\n\n"
                f"Is the predicted category correct for this document?\n"
                f"Respond with ONLY 'correct' or 'incorrect'."
            )

            response = await self._client.messages.create(
                model=self._model,
                max_tokens=10,
                messages=[{"role": "user", "content": judge_prompt}],
            )
            verdict = response.content[0].text.strip().lower()
            return verdict if verdict in ("correct", "incorrect") else "skipped"
        except Exception:
            return "skipped"
