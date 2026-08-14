"""Property-based tests for pipeline.extraction and pipeline.extraction_server.

PBT-02: Round-trip — CompactArtifact text fields survive JSON serialisation.
PBT-07: Generator quality — meaningful text inputs.
PBT-08: Shrinking enabled — no suppress_health_check overrides that disable shrinking.
"""
from __future__ import annotations

import json

from hypothesis import given, settings
from hypothesis import strategies as st

from pipeline.models import CompactArtifact


# ---------------------------------------------------------------------------
# Shared generators (PBT-07: domain-appropriate)
# ---------------------------------------------------------------------------

printable_nonempty = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S", "Zs")),
    min_size=1,
    max_size=100,
).filter(lambda s: s.strip())


# ---------------------------------------------------------------------------
# PBT-02: CompactArtifact JSON round-trip
# ---------------------------------------------------------------------------


@given(
    document_name=printable_nonempty,
    extracted_text=st.text(min_size=0, max_size=500),
)
@settings(max_examples=100)
def test_compact_artifact_text_fields_json_roundtrip(
    document_name: str,
    extracted_text: str,
) -> None:
    """Text fields survive a JSON serialise/deserialise cycle (PBT-02)."""
    artifact = CompactArtifact(
        document_name=document_name,
        extracted_text=extracted_text,
    )
    serialised = json.dumps(dict(artifact))
    restored = json.loads(serialised)
    assert restored["document_name"] == artifact["document_name"]
    assert restored["extracted_text"] == artifact["extracted_text"]
