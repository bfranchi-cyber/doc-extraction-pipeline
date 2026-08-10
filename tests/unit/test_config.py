"""Unit tests for pipeline.config.Config and Config.from_toml()."""
from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from pipeline.models import ConfigError, CredentialsError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_toml(tmp_path: Path, overrides: dict | None = None) -> Path:
    """Write a valid config.toml to tmp_path, applying any field overrides."""
    vault      = tmp_path / "vault";      vault.mkdir()
    images     = tmp_path / "images";     images.mkdir()
    manifests  = tmp_path / "manifests";  manifests.mkdir()
    staging    = tmp_path / "staging";    staging.mkdir()
    creds_file = tmp_path / "credentials.json"
    creds_file.write_text(json.dumps({"type": "authorized_user"}), encoding="utf-8")

    defaults = {
        "vault_path":       str(vault),
        "images_path":      str(images),
        "manifest_dir":     str(manifests),
        "staging_dir":      str(staging),
        "scratchpad_path":  str(tmp_path / "scratchpad.log"),
        "credentials_path": str(creds_file),
        "folder_id":        "FAKE_DRIVE_ID",
        "eligibility_days": 5,
        "extraction_model": "claude-haiku-4-5-20251001",
        "analysis_model":   "claude-sonnet-4-5-20251001",
        "categories":       '["Work", "Research"]',
    }
    if overrides:
        defaults.update(overrides)

    toml_text = textwrap.dedent(f"""
        [paths]
        vault_path       = "{defaults['vault_path']}"
        images_path      = "{defaults['images_path']}"
        manifest_dir     = "{defaults['manifest_dir']}"
        staging_dir      = "{defaults['staging_dir']}"
        scratchpad_path  = "{defaults['scratchpad_path']}"
        credentials_path = "{defaults['credentials_path']}"

        [drive]
        folder_id = "{defaults['folder_id']}"

        [pipeline]
        eligibility_days  = {defaults['eligibility_days']}
        extraction_model  = "{defaults['extraction_model']}"
        analysis_model    = "{defaults['analysis_model']}"

        [categories]
        list = {defaults['categories']}
    """).strip()

    config_path = tmp_path / "config.toml"
    config_path.write_text(toml_text, encoding="utf-8")
    return config_path


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_from_toml_loads_successfully(tmp_path):
    from pipeline.config import Config
    config_path = _write_toml(tmp_path)
    cfg = Config.from_toml(config_path)
    assert cfg.drive_folder_id == "FAKE_DRIVE_ID"
    assert cfg.eligibility_days == 5
    assert "Work" in cfg.categories
    assert "Research" in cfg.categories


def test_config_is_frozen(tmp_path):
    from pipeline.config import Config
    cfg = Config.from_toml(_write_toml(tmp_path))
    with pytest.raises((AttributeError, TypeError)):
        cfg.eligibility_days = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Missing required fields
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("section,key", [
    ("paths",    "vault_path"),
    ("drive",    "folder_id"),
    ("pipeline", "eligibility_days"),
    ("pipeline", "extraction_model"),
    ("categories", "list"),
])
def test_missing_field_raises_config_error(tmp_path, section, key):
    from pipeline.config import Config
    config_path = _write_toml(tmp_path)
    text = config_path.read_text(encoding="utf-8")
    # Remove the line containing the key
    filtered = "\n".join(
        line for line in text.splitlines()
        if not line.strip().startswith(key)
    )
    config_path.write_text(filtered, encoding="utf-8")
    with pytest.raises(ConfigError):
        Config.from_toml(config_path)


# ---------------------------------------------------------------------------
# Path validation
# ---------------------------------------------------------------------------

def test_nonexistent_vault_path_raises_config_error(tmp_path):
    from pipeline.config import Config
    config_path = _write_toml(tmp_path, overrides={"vault_path": str(tmp_path / "no_such_dir")})
    with pytest.raises(ConfigError, match="vault_path"):
        Config.from_toml(config_path)


def test_nonexistent_manifest_dir_raises_config_error(tmp_path):
    from pipeline.config import Config
    config_path = _write_toml(tmp_path, overrides={"manifest_dir": str(tmp_path / "no_such_dir")})
    with pytest.raises(ConfigError, match="manifest_dir"):
        Config.from_toml(config_path)


# ---------------------------------------------------------------------------
# Credentials validation
# ---------------------------------------------------------------------------

def test_missing_credentials_file_raises_config_error(tmp_path):
    from pipeline.config import Config
    config_path = _write_toml(tmp_path, overrides={"credentials_path": str(tmp_path / "missing.json")})
    with pytest.raises(ConfigError):
        Config.from_toml(config_path)


def test_invalid_credentials_json_raises_credentials_error(tmp_path):
    from pipeline.config import Config
    creds = tmp_path / "bad_creds.json"
    creds.write_text("NOT JSON", encoding="utf-8")
    config_path = _write_toml(tmp_path, overrides={"credentials_path": str(creds)})
    with pytest.raises(CredentialsError):
        Config.from_toml(config_path)


def test_credentials_missing_type_field_raises_credentials_error(tmp_path):
    from pipeline.config import Config
    creds = tmp_path / "no_type.json"
    creds.write_text(json.dumps({"client_id": "abc"}), encoding="utf-8")
    config_path = _write_toml(tmp_path, overrides={"credentials_path": str(creds)})
    with pytest.raises(CredentialsError):
        Config.from_toml(config_path)


# ---------------------------------------------------------------------------
# Category drift warning
# ---------------------------------------------------------------------------

def test_category_mismatch_emits_warning_not_raises(tmp_path):
    from pipeline.config import Config
    from pipeline.scratchpad import Scratchpad
    scratchpad_path = tmp_path / "scratchpad.log"
    sp = Scratchpad(scratchpad_path)
    # "Research" exists in vault, "Unknown" does not
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    (vault / "Research").mkdir()
    config_path = _write_toml(tmp_path, overrides={
        "vault_path": str(vault),
        "categories": '["Research", "Unknown"]',
    })
    cfg = Config.from_toml(config_path, scratchpad=sp)
    assert "Unknown" in cfg.categories
    log_lines = scratchpad_path.read_text(encoding="utf-8").strip().splitlines()
    assert any("Unknown" in line and "WARN" in line for line in log_lines)


# ---------------------------------------------------------------------------
# eligibility_days validation
# ---------------------------------------------------------------------------

def test_zero_eligibility_days_raises_config_error(tmp_path):
    from pipeline.config import Config
    config_path = _write_toml(tmp_path, overrides={"eligibility_days": 0})
    with pytest.raises(ConfigError, match="eligibility_days"):
        Config.from_toml(config_path)
