"""Configuration loading.

All assumptions live in ``config/default.toml``. A *profile* (``quick``, ``full``,
``smoke``) overrides individual keys. The result is exposed as a :class:`Settings`
object with attribute access (``settings.time.speed_kmh``) and a ``root`` path
against which relative paths in the config are resolved.
"""

from __future__ import annotations

import copy
import tomllib
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "config" / "default.toml"


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _to_namespace(obj: Any) -> Any:
    if isinstance(obj, dict):
        return SimpleNamespace(**{k: _to_namespace(v) for k, v in obj.items()})
    if isinstance(obj, list):
        return [_to_namespace(v) for v in obj]
    return obj


@dataclass
class Settings:
    """Resolved configuration for one run."""

    raw: dict[str, Any]
    profile: str
    root: Path = REPO_ROOT

    def __getattr__(self, name: str) -> Any:  # section access: settings.time
        try:
            return _to_namespace(self.raw[name])
        except KeyError as exc:  # pragma: no cover - programming error
            raise AttributeError(name) from exc

    def path(self, relative: str | Path) -> Path:
        """Resolve a path from the config relative to the repository root."""
        p = Path(relative)
        return p if p.is_absolute() else self.root / p

    @property
    def results_dir(self) -> Path:
        return self.path(self.raw["output"]["results_dir"])

    def override(self, section: str, **values: Any) -> "Settings":
        """Return a copy with some keys of one section replaced (used in tests)."""
        raw = _deep_merge(self.raw, {section: values})
        return Settings(raw=raw, profile=self.profile, root=self.root)


def load_settings(profile: str = "quick", config_file: Path | None = None) -> Settings:
    """Load the TOML config and apply a profile's overrides."""
    config_file = config_file or DEFAULT_CONFIG
    with open(config_file, "rb") as fh:
        raw = tomllib.load(fh)
    profiles = raw.pop("profiles", {})
    if profile not in profiles:
        raise ValueError(f"Unknown profile {profile!r}; choose from {sorted(profiles)}")
    raw = _deep_merge(raw, profiles[profile])
    return Settings(raw=raw, profile=profile)
