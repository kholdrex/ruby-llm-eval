"""Locate and load eval resources: tasks, YAML configs, and sandbox Dockerfile.

The tool is normally run from a clone of the repository, so these live in
`./tasks/`, `./configs/`, and `./sandbox/`. We resolve them by walking up from
the current directory, which keeps things working whether you run from the repo
root or a subdirectory. Installed wheels also ship a copy of these defaults under
``ruby_llm_eval/assets/`` so the CLI works outside a source checkout.

``RUBY_LLM_EVAL_CONFIG_DIR`` (or ``--config-dir``) overrides the configs
location for installs that keep configs elsewhere.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

CONFIG_DIR_ENV = "RUBY_LLM_EVAL_CONFIG_DIR"
PACKAGE_ASSETS_DIR = Path(__file__).resolve().parent / "assets"


def _find_dir_containing(
    dir_name: str, marker: str, explicit: str | None = None, env: str | None = None
) -> Path:
    """Find a sibling directory ``dir_name`` that contains ``marker``."""
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    if env and os.environ.get(env):
        candidates.append(Path(os.environ[env]))

    here = Path.cwd()
    for parent in [here, *here.parents]:
        candidates.append(parent / dir_name)

    # Fall back to package data shipped inside installed wheels.
    candidates.append(PACKAGE_ASSETS_DIR / dir_name)

    for candidate in candidates:
        if (candidate / marker).is_file():
            return candidate

    raise FileNotFoundError(
        f"Could not find a '{dir_name}/' directory containing '{marker}'. "
        "Run ruby-llm-eval from a clone of the repository, or pass the matching "
        "--config-dir / --sandbox flag."
    )


def find_config_dir(explicit: str | None = None) -> Path:
    """Return the directory holding providers.yaml and pricing.yaml."""
    return _find_dir_containing("configs", "providers.yaml", explicit, CONFIG_DIR_ENV)


def find_sandbox_dir(explicit: str | None = None) -> Path:
    """Return the directory holding the sandbox Dockerfile."""
    return _find_dir_containing("sandbox", "Dockerfile", explicit)


def find_tasks_dir(explicit: str | None = None) -> Path:
    """Return the directory holding the bundled or user-supplied task set."""
    if explicit:
        return Path(explicit)

    here = Path.cwd()
    for parent in [here, *here.parents]:
        candidate = parent / "tasks"
        if _looks_like_tasks_dir(candidate):
            return candidate

    return _find_dir_containing("tasks", "VERSION")


def _looks_like_tasks_dir(candidate: Path) -> bool:
    if not candidate.is_dir():
        return False
    return (candidate / "VERSION").is_file() or any(
        child.is_dir() and (child / "prompt.md").is_file() for child in candidate.iterdir()
    )


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_providers(config_dir: Path) -> dict:
    """Return the provider registry: {name: {type, base_url, api_key_env}}."""
    return load_yaml(config_dir / "providers.yaml").get("providers", {})


def load_pricing(config_dir: Path) -> dict:
    """Return per-model token prices: {model: {input, output}} in USD / 1M."""
    return load_yaml(config_dir / "pricing.yaml").get("models", {})


def load_rubocop_config(config_dir: Path) -> str | None:
    """Return the RuboCop config text used by ``--style``, or None if absent."""
    path = config_dir / "rubocop.yml"
    return path.read_text(encoding="utf-8") if path.is_file() else None
