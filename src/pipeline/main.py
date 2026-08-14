from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from pipeline.classification import ClassificationAgent
from pipeline.exceptions import PipelineError
from pipeline.extraction import Extractor
from pipeline.scratchpad import Scratchpad


def _resolve_vault_root(scratchpad: Scratchpad) -> Path | None:
    vault_path = os.environ.get("OBSIDIAN_VAULT_PATH", "").strip()
    if not vault_path:
        scratchpad.warn("OBSIDIAN_VAULT_PATH not set — classification skipped")
        return None
    return Path(vault_path)


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
    extractor = Extractor(scratchpad)
    vault_root = _resolve_vault_root(scratchpad)
    classifier = ClassificationAgent(vault_root, scratchpad) if vault_root else None

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
                artifact = await extractor.process(docx_path)
                output_path.write_text(artifact["extracted_text"], encoding="utf-8")
                scratchpad.info(f"Extracted: {relative}", context={"output": str(output_path)})
                print(f"  -> {output_path.relative_to(output_root)}")
            except PipelineError as exc:
                scratchpad.error(f"Failed: {relative}: {exc}", context=exc.to_dict())
                print(f"  ERROR: {exc}", file=sys.stderr)
                continue

            if classifier:
                await classifier.classify(output_path)

    asyncio.run(run_all())
    print("Done.")


if __name__ == "__main__":
    main()
