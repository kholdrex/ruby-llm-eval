from pathlib import Path

import pytest

from ruby_llm_eval.config import (
    find_config_dir,
    find_sandbox_dir,
    load_pricing,
    load_providers,
    load_rubocop_config,
)

CONFIG_DIR = Path(__file__).resolve().parent.parent / "configs"


def _write_custom_config_dir(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "providers.yaml").write_text("providers:\n  stub:\n    type: stub\n", encoding="utf-8")
    (root / "pricing.yaml").write_text(
        "models:\n  stub:\n    input: 0.0\n    output: 0.0\n", encoding="utf-8"
    )


def test_providers_include_stub_and_anthropic():
    providers = load_providers(CONFIG_DIR)
    assert providers["stub"]["type"] == "stub"
    assert providers["anthropic"]["type"] == "anthropic"


def test_pricing_has_stub_zero():
    pricing = load_pricing(CONFIG_DIR)
    assert pricing["stub"]["input"] == 0.0
    assert pricing["stub"]["output"] == 0.0


def test_rubocop_config_loads():
    text = load_rubocop_config(CONFIG_DIR)
    assert text is not None
    assert "TargetRubyVersion" in text


def test_rubocop_config_absent_returns_none(tmp_path):
    assert load_rubocop_config(tmp_path) is None


def test_find_config_dir_locates_repo_configs():
    # From the repo, the walked-up configs dir must contain providers.yaml.
    found = find_config_dir()
    assert (found / "providers.yaml").is_file()


def test_find_config_dir_uses_explicit_path_when_marker_exists(tmp_path, monkeypatch):
    custom = tmp_path / "explicit-config"
    _write_custom_config_dir(custom)

    env_config = tmp_path / "env-config"
    _write_custom_config_dir(env_config)
    monkeypatch.setenv("RUBY_LLM_EVAL_CONFIG_DIR", str(env_config))

    found = find_config_dir(explicit=str(custom))

    assert found == custom


def test_find_config_dir_explicit_path_without_marker_raises(tmp_path):
    bad = tmp_path / "bad-config"
    bad.mkdir()

    with pytest.raises(FileNotFoundError) as exc_info:
        find_config_dir(explicit=str(bad))

    message = str(exc_info.value)
    assert str(bad) in message
    assert "providers.yaml" in message


def test_find_config_dir_explicit_path_without_marker_never_falls_back(tmp_path, monkeypatch):
    bad = tmp_path / "bad-config"
    bad.mkdir()
    env_config = tmp_path / "env-config"
    _write_custom_config_dir(env_config)
    monkeypatch.setenv("RUBY_LLM_EVAL_CONFIG_DIR", str(env_config))

    with pytest.raises(FileNotFoundError) as exc_info:
        find_config_dir(explicit=str(bad))

    message = str(exc_info.value)
    assert str(bad) in message
    assert "providers.yaml" in message


def test_find_sandbox_dir_with_nonexistent_explicit_path_falls_back_to_env(tmp_path, monkeypatch):
    explicit = tmp_path / "does-not-exist"
    root = tmp_path / "repo"
    sandbox = root / "sandbox"
    sandbox.mkdir(parents=True)
    (sandbox / "Dockerfile").write_text("FROM python:3.11-slim\n", encoding="utf-8")
    monkeypatch.chdir(root)

    found = find_sandbox_dir(explicit=str(explicit))

    assert found == sandbox
