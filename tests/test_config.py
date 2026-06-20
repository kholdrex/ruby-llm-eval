from pathlib import Path

from ruby_llm_eval.config import (
    find_config_dir,
    load_pricing,
    load_providers,
    load_rubocop_config,
)

CONFIG_DIR = Path(__file__).resolve().parent.parent / "configs"


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
