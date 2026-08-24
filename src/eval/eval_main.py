from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from eval.eval_agent import EvalAgent


def main() -> None:
    phoenix_host = os.environ.get("PHOENIX_HOST", "localhost:6006")

    vault_path = os.environ.get("OBSIDIAN_VAULT_PATH", "").strip()
    vault_root = Path(vault_path) if vault_path else None

    try:
        agent = EvalAgent(vault_root=vault_root)
        summary = asyncio.run(agent.run_evals())
    except Exception as exc:
        print(f"Error: Could not connect to Phoenix at {phoenix_host}: {exc}", file=sys.stderr)
        sys.exit(1)

    evaluated = summary["evaluated"]
    correct = summary["correct"]
    incorrect = summary["incorrect"]
    print(f"Evaluated {evaluated} spans — correct: {correct}, incorrect: {incorrect}")
