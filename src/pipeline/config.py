from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path

from pipeline.models import ConfigError, CredentialsError
from pipeline.scratchpad import Scratchpad


@dataclass(frozen=True)
class Config:
    """Immutable runtime configuration loaded once at startup from config.toml."""

    vault_path: Path
    images_path: Path
    manifest_dir: Path
    staging_dir: Path
    scratchpad_path: Path
    credentials_path: Path
    drive_folder_id: str
    categories: tuple[str, ...]
    extraction_model: str
    analysis_model: str
    eligibility_days: int

    @classmethod
    def from_toml(cls, path: Path, scratchpad: Scratchpad | None = None) -> "Config":
        """Load and validate configuration from a TOML file.

        Raises ConfigError on missing fields, bad paths, or invalid values.
        Raises CredentialsError if credentials_path is missing, unreadable, or not valid OAuth2 JSON.
        Emits warnings via scratchpad (if provided) when config categories don't match vault subfolders.
        """
        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
        except FileNotFoundError:
            raise ConfigError(f"Config file not found: {path}")
        except tomllib.TOMLDecodeError as e:
            raise ConfigError(f"Config file is not valid TOML: {e}")

        # --- Pass 1: structural validation ---

        def _require(section: str, key: str) -> str:
            try:
                return data[section][key]
            except KeyError:
                raise ConfigError(f"Missing required config field: [{section}].{key}")

        vault_path      = _validate_dir(_require("paths", "vault_path"),      "vault_path")
        images_path     = _validate_dir(_require("paths", "images_path"),     "images_path")
        manifest_dir    = _validate_dir(_require("paths", "manifest_dir"),    "manifest_dir")
        staging_dir     = _validate_dir(_require("paths", "staging_dir"),     "staging_dir")
        scratchpad_path = _validate_parent(_require("paths", "scratchpad_path"), "scratchpad_path")
        credentials_path_raw = _require("paths", "credentials_path")

        drive_folder_id  = _require("drive", "folder_id")
        extraction_model = _require("pipeline", "extraction_model")
        analysis_model   = _require("pipeline", "analysis_model")

        try:
            eligibility_days = int(data["pipeline"]["eligibility_days"])
        except KeyError:
            raise ConfigError("Missing required config field: [pipeline].eligibility_days")
        except (ValueError, TypeError):
            raise ConfigError("[pipeline].eligibility_days must be a positive integer")
        if eligibility_days <= 0:
            raise ConfigError("[pipeline].eligibility_days must be a positive integer")

        try:
            categories = list(data["categories"]["list"])
        except KeyError:
            raise ConfigError("Missing required config field: [categories].list")
        if not categories:
            raise ConfigError("[categories].list must not be empty")

        # --- Pass 2: credentials content validation ---
        credentials_path = _validate_file(credentials_path_raw, "credentials_path")
        _validate_credentials(credentials_path)

        # --- Category drift warning (advisory, non-blocking) ---
        if scratchpad is not None:
            vault_subdirs = {p.name for p in vault_path.iterdir() if p.is_dir()}
            for cat in categories:
                if cat not in vault_subdirs:
                    scratchpad.warn(
                        f"Category '{cat}' in config has no matching subfolder in vault",
                        context={"category": cat, "vault_path": str(vault_path)},
                    )

        return cls(
            vault_path=vault_path,
            images_path=images_path,
            manifest_dir=manifest_dir,
            staging_dir=staging_dir,
            scratchpad_path=scratchpad_path,
            credentials_path=credentials_path,
            drive_folder_id=drive_folder_id,
            categories=tuple(categories),
            extraction_model=extraction_model,
            analysis_model=analysis_model,
            eligibility_days=eligibility_days,
        )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _validate_dir(raw: str, field: str) -> Path:
    p = Path(raw)
    if not p.is_dir():
        raise ConfigError(
            f"{field}: path does not exist or is not a directory: {p}",
            suggestion=f"Create the directory or update [{field}] in config.toml.",
        )
    return p


def _validate_file(raw: str, field: str) -> Path:
    p = Path(raw)
    if not p.is_file():
        raise ConfigError(
            f"{field}: file does not exist or is not readable: {p}",
            suggestion=f"Ensure the file exists and update [{field}] in config.toml.",
        )
    return p


def _validate_parent(raw: str, field: str) -> Path:
    p = Path(raw)
    if not p.parent.is_dir():
        raise ConfigError(
            f"{field}: parent directory does not exist: {p.parent}",
            suggestion=f"Create the parent directory or update [{field}] in config.toml.",
        )
    return p


def _validate_credentials(path: Path) -> None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            creds = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise CredentialsError(
            f"credentials_path does not contain valid JSON: {e}",
            suggestion="Download a fresh credentials.json from the Google Cloud Console.",
        )
    if "type" not in creds:
        raise CredentialsError(
            "credentials_path JSON is missing the required 'type' field",
            suggestion="Ensure credentials.json is a valid OAuth2 or service account credentials file.",
        )
