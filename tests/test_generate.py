from ruby_llm_eval.generate import safe_model_dir, strip_code_fences


def test_strips_ruby_fence():
    text = "Here you go:\n```ruby\ndef f\n  1\nend\n```\nHope that helps!"
    assert strip_code_fences(text) == "def f\n  1\nend\n"


def test_strips_bare_fence():
    assert strip_code_fences("```\nputs 1\n```") == "puts 1\n"


def test_passthrough_when_no_fence():
    assert strip_code_fences("def f\n  1\nend") == "def f\n  1\nend\n"


def test_takes_first_block_only():
    text = "```ruby\ndef a; end\n```\nand\n```ruby\ndef b; end\n```"
    assert strip_code_fences(text) == "def a; end\n"


def test_safe_model_dir_sanitizes_slashes_and_colons():
    assert safe_model_dir("anthropic/claude-sonnet-4-6") == "anthropic_claude-sonnet-4-6"
    assert safe_model_dir("openai:gpt-4o") == "openai_gpt-4o"
    assert safe_model_dir("///") == "model"
