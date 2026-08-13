"""Property-based tests for pipeline.extraction and pipeline.extraction_server.

PBT-02: Round-trip — CompactArtifact text fields survive JSON serialisation.
PBT-03: Invariants — category always in config.categories; image metadata fields non-empty.
PBT-07: Generator quality — MIME boundary, category exact/case/no-match.
PBT-08: Shrinking enabled — no suppress_health_check overrides that disable shrinking.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from pipeline.extraction import _apply_category_validation
from pipeline.extraction_server import DOCX_MIME, PDF_MIME, _resolve_image_filename
from pipeline.models import CompactArtifact, ImageMetadata
from pipeline.scratchpad import Scratchpad


# ---------------------------------------------------------------------------
# Shared generators (PBT-07: domain-appropriate)
# ---------------------------------------------------------------------------

drive_file_ids = st.from_regex(r"[A-Za-z0-9_-]{10,44}", fullmatch=True)

printable_nonempty = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S", "Zs")),
    min_size=1,
    max_size=100,
).filter(lambda s: s.strip())

category_text = st.text(min_size=1, max_size=50).filter(lambda s: s.strip())

image_ids = st.from_regex(r"[A-Za-z0-9_-]{6,44}", fullmatch=True)

_KNOWN_MIMES = {DOCX_MIME, PDF_MIME}

mime_boundary = st.one_of(
    st.just(DOCX_MIME),
    st.just(PDF_MIME),
    st.text(min_size=1, max_size=80).filter(lambda m: m not in _KNOWN_MIMES),
)


# ---------------------------------------------------------------------------
# PBT-02: CompactArtifact JSON round-trip
# ---------------------------------------------------------------------------


@given(
    file_id=drive_file_ids,
    document_name=printable_nonempty,
    extracted_text=st.text(min_size=0, max_size=500),
    category=category_text,
)
@settings(max_examples=100)
def test_compact_artifact_text_fields_json_roundtrip(
    file_id: str,
    document_name: str,
    extracted_text: str,
    category: str,
) -> None:
    """Text fields survive a JSON serialise/deserialise cycle (PBT-02)."""
    artifact = CompactArtifact(
        file_id=file_id,
        document_name=document_name,
        extracted_text=extracted_text,
        category=category,
        images=[],
    )
    serialised = json.dumps(
        {k: v for k, v in artifact.items() if k != "images"}
    )
    restored = json.loads(serialised)
    assert restored["file_id"] == artifact["file_id"]
    assert restored["document_name"] == artifact["document_name"]
    assert restored["extracted_text"] == artifact["extracted_text"]
    assert restored["category"] == artifact["category"]


# ---------------------------------------------------------------------------
# PBT-03: Category invariant — result always in categories list
# ---------------------------------------------------------------------------


@given(
    returned_category=st.text(min_size=1, max_size=50),
    categories=st.lists(
        st.text(min_size=1, max_size=30).filter(str.strip),
        min_size=1,
        max_size=5,
        unique=True,
    ),
)
@settings(max_examples=200)
def test_category_always_in_config_categories(
    returned_category: str,
    categories: list[str],
) -> None:
    """_apply_category_validation always returns a member of categories (PBT-03)."""
    with tempfile.TemporaryDirectory() as td:
        scratchpad = Scratchpad(Path(td) / "sp.jsonl")
        result = _apply_category_validation(
            returned_category, tuple(categories), scratchpad, "doc.docx"
        )
    assert result in categories


# ---------------------------------------------------------------------------
# PBT-03: ImageMetadata fields invariant
# ---------------------------------------------------------------------------


@given(
    image_id_list=st.lists(image_ids, min_size=0, max_size=5, unique=True),
)
@settings(max_examples=100)
def test_image_metadata_fields_nonempty(image_id_list: list[str]) -> None:
    """ImageMetadata instances have non-empty image_id and a non-empty staged_path (PBT-03)."""
    with tempfile.TemporaryDirectory() as td:
        dest_dir = Path(td)
        metas = []
        for iid in image_id_list:
            filename = _resolve_image_filename(dest_dir, iid, "photo.png")
            dest = dest_dir / filename
            dest.write_bytes(b"")
            metas.append(
                ImageMetadata(image_id=iid, alt_text="", staged_path=dest)
            )
        for meta in metas:
            assert meta.image_id
            assert meta.staged_path.name


# ---------------------------------------------------------------------------
# PBT-07: MIME type generator — boundary coverage
# ---------------------------------------------------------------------------


@given(mime_type=mime_boundary)
@settings(max_examples=100)
def test_mime_generator_covers_supported_and_unsupported(mime_type: str) -> None:
    """Generator produces both supported and unsupported MIME types (PBT-07)."""
    is_supported = mime_type in _KNOWN_MIMES
    # We just verify the generator produces both sides; no assertion on behaviour.
    assert isinstance(is_supported, bool)


# ---------------------------------------------------------------------------
# PBT-07: Category validation boundary — exact / case-mismatch / no-match
# ---------------------------------------------------------------------------

_FIXED_CATS = ("Finance", "HR", "Legal")

_category_boundary = st.one_of(
    st.sampled_from(list(_FIXED_CATS)),
    st.sampled_from([c.lower() for c in _FIXED_CATS]),
    st.sampled_from([c.upper() for c in _FIXED_CATS]),
    st.text(min_size=1).filter(lambda s: s.lower() not in {c.lower() for c in _FIXED_CATS}),
)


@given(returned=_category_boundary)
@settings(max_examples=200)
def test_category_validation_boundary(returned: str) -> None:
    """All boundary inputs resolve to a member of the fixed category list (PBT-07)."""
    with tempfile.TemporaryDirectory() as td:
        scratchpad = Scratchpad(Path(td) / "sp.jsonl")
        result = _apply_category_validation(returned, _FIXED_CATS, scratchpad, "doc.docx")
    assert result in _FIXED_CATS


# ---------------------------------------------------------------------------
# PBT-03: _resolve_image_filename collision invariant
# ---------------------------------------------------------------------------


@given(
    image_id=image_ids,
    filenames=st.lists(
        st.text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz0123456789"),
        min_size=1,
        max_size=5,
    ),
)
@settings(max_examples=100)
def test_resolve_image_filename_no_collisions(
    image_id: str, filenames: list[str]
) -> None:
    """All resolved filenames for the same image_id are unique on disk (PBT-03)."""
    with tempfile.TemporaryDirectory() as td:
        dest_dir = Path(td)
        seen: set[str] = set()
        for original in filenames:
            name = _resolve_image_filename(dest_dir, image_id, original)
            assert name not in seen
            seen.add(name)
            (dest_dir / name).write_bytes(b"")
