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


def test_interrupted_generation_preserves_raw_completed_response(tmp_path):
    import json
    from types import SimpleNamespace

    import pytest

    from ruby_llm_eval.generate import generate_for_task

    class InterruptedClient:
        calls = 0

        def complete(self, prompt, **kwargs):
            self.calls += 1
            if self.calls == 2:
                raise KeyboardInterrupt
            assert kwargs["max_tokens"] == 2048
            return {
                "text": "A solution:\n```ruby\ndef add; 1; end\n```",
                "input_tokens": 20,
                "output_tokens": 10,
                "metadata": {"finish_reason": "stop"},
            }

    task = SimpleNamespace(id="task", prompt="Implement add")
    with pytest.raises(KeyboardInterrupt):
        generate_for_task(
            InterruptedClient(),
            task,
            n=2,
            temperature=0.2,
            out_dir=tmp_path,
            max_tokens=2048,
        )
    saved = json.loads((tmp_path / "task/samples.json").read_text())
    assert len(saved) == 1
    assert saved[0]["raw_text"].startswith("A solution:")
    assert saved[0]["code"] == "def add; 1; end\n"
    assert saved[0]["metadata"]["finish_reason"] == "stop"
