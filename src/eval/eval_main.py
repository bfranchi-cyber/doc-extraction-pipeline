from __future__ import annotations

import asyncio
import os
import sys

from eval.eval_agent import EvalAgent


def main() -> None:
    phoenix_host = os.environ.get("PHOENIX_HOST", "localhost:6006")

    try:
        agent = EvalAgent()
        summary = asyncio.run(agent.run_evals())
    except Exception as exc:
        print(f"Error: Could not connect to Phoenix at {phoenix_host}: {exc}", file=sys.stderr)
        sys.exit(1)

    evaluated = summary["evaluated"]
    correct = summary["correct"]
    incorrect = summary["incorrect"]
    print(f"Evaluated {evaluated} spans — correct: {correct}, incorrect: {incorrect}")
