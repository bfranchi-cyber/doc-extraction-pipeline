from __future__ import annotations

from pathlib import Path

import yaml


def read_frontmatter(md_path: Path) -> dict | None:
    """Return the parsed YAML frontmatter dict from *md_path*, or None if absent.

    Never raises — absence of a frontmatter block is not an error.
    """
    try:
        text = md_path.read_text(encoding="utf-8")
    except OSError:
        return None

    if not text.startswith("---\n"):
        return None

    end = text.find("\n---\n", 4)
    if end == -1:
        return None

    yaml_block = text[4:end]
    try:
        parsed = yaml.safe_load(yaml_block)
    except yaml.YAMLError:
        return None

    return parsed if isinstance(parsed, dict) else None


def write_frontmatter(md_path: Path, data: dict) -> None:
    """Prepend a YAML frontmatter block to *md_path*.

    Reads existing content and writes ``---\\n<yaml>\\n---\\n\\n<original>`` back.
    """
    existing = md_path.read_text(encoding="utf-8")
    yaml_text = yaml.dump(data, allow_unicode=True, default_flow_style=False)
    md_path.write_text(f"---\n{yaml_text}---\n\n{existing}", encoding="utf-8")
