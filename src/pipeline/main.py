from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from pipeline.exceptions import PipelineError
from pipeline.extraction import ExtractionAgent
from pipeline.scratchpad import Scratchpad


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract text from .docx files and write .md files."
    )
    parser.add_argument("--input", required=True, type=Path, help="Root folder to scan for .docx files (recursive)")
    parser.add_argument("--output", required=True, type=Path, help="Root folder for output .md files (mirrored structure)")
    args = parser.parse_args()

    input_root: Path = args.input.resolve()
    output_root: Path = args.output.resolve()

    if not input_root.is_dir():
        print(f"Error: --input path does not exist or is not a directory: {input_root}", file=sys.stderr)
        sys.exit(1)

    output_root.mkdir(parents=True, exist_ok=True)

    scratchpad = Scratchpad(output_root / "scratchpad.jsonl")
    agent = ExtractionAgent(scratchpad)

    docx_files = sorted(input_root.rglob("*.docx"))
    if not docx_files:
        print(f"No .docx files found under {input_root}")
        return

    print(f"Found {len(docx_files)} .docx file(s). Extracting...")

    async def run_all() -> None:
        for docx_path in docx_files:
            relative = docx_path.relative_to(input_root)
            output_path = output_root / relative.with_suffix(".md")
            output_path.parent.mkdir(parents=True, exist_ok=True)

            print(f"  Processing: {relative}")
            try:
                artifact = await agent.process(docx_path)
                output_path.write_text(artifact["extracted_text"], encoding="utf-8")
                scratchpad.info(f"Extracted: {relative}", context={"output": str(output_path)})
                print(f"  -> {output_path.relative_to(output_root)}")
            except PipelineError as exc:
                scratchpad.error(f"Failed: {relative}: {exc}", context=exc.to_dict())
                print(f"  ERROR: {exc}", file=sys.stderr)

    asyncio.run(run_all())
    print("Done.")


if __name__ == "__main__":
    main()
