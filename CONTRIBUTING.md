# Contributing

Thanks for helping make `ruby-llm-eval` better. The two highest-value
contributions are **new tasks** and **new providers**, and both are designed to
take only a few minutes. This guide walks through each with copy-paste examples.

## Dev setup

```bash
git clone https://github.com/kholdrex/ruby-llm-eval.git
cd ruby-llm-eval
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Sanity check (no API key needed): runs the seed tasks against the stub model.
ruby-llm-eval run --provider stub --model stub
```

Before opening a PR:

```bash
ruff check .            # lint
ruff format .           # auto-format
pytest -q               # harness unit tests
```

When changing built-in `tasks/`, `configs/`, or `sandbox/` assets, sync the packaged copies before running tests:

```bash
python - <<'PY'
from pathlib import Path
import shutil
root = Path.cwd()
for name in ("configs", "sandbox", "tasks"):
    dest = root / "ruby_llm_eval" / "assets" / name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(root / name, dest)
PY
```

CI runs the same checks plus a full pipeline against the stub model.

## Adding a task

A task is a directory under `tasks/` named `NNN_short_name`. It contains
exactly three files. Here is a complete example you can copy.

**1. Create the folder:**

```bash
mkdir tasks/011_sum_even
```

**2. `tasks/011_sum_even/prompt.md`** — the description and the *exact* Ruby
signature. Be precise about return types and edge cases; the model only sees
this file.

````markdown
# Sum of even numbers

Implement a method with this exact signature:

```ruby
def sum_even(numbers)
end
```

Return the sum of the even integers in `numbers`. Return `0` for an empty array.

Example:

```ruby
sum_even([1, 2, 3, 4]) # => 6
```
````

**3. `tasks/011_sum_even/test.rb`** — a Minitest suite. It must
`require_relative "solution"` (the harness saves the model's answer as
`solution.rb` next to it). Keep assertions **deterministic** — no randomness,
no clocks, no network, no ordering ambiguity.

```ruby
require "minitest/autorun"
require_relative "solution"

class SumEvenTest < Minitest::Test
  def test_basic
    assert_equal(6, sum_even([1, 2, 3, 4]))
  end

  def test_empty
    assert_equal(0, sum_even([]))
  end

  def test_all_odd
    assert_equal(0, sum_even([1, 3, 5]))
  end

  def test_negatives
    assert_equal(-6, sum_even([-2, -4, 1]))
  end
end
```

**4. `tasks/011_sum_even/solution_ref.rb`** — a correct reference solution. It is
**never shown to the model**; its only job is to prove the tests are valid and
deterministic.

```ruby
def sum_even(numbers)
  numbers.select(&:even?).sum
end
```

**5. Verify the test passes against the reference**, exactly as the sandbox
will run it:

```bash
tmp=$(mktemp -d)
cp tasks/011_sum_even/test.rb "$tmp/test.rb"
cp tasks/011_sum_even/solution_ref.rb "$tmp/solution.rb"
( cd "$tmp" && ruby test.rb )   # expect: 0 failures, 0 errors
rm -rf "$tmp"
```

**6. Run it through the real pipeline** with the stub model (which uses the
reference), to confirm the harness picks it up:

```bash
ruby-llm-eval run --provider stub --model stub --task 011_sum_even
```

That's the whole contribution surface — no registry to edit, no code to touch.

### Task guidelines

- **Deterministic only.** Same input must always give the same result. Avoid
  `rand`, time, hashes-as-ordered-output, or file/network access.
- **Pin ambiguous ordering.** If a result could come back in any order, specify
  a sort in `prompt.md` and assert the sorted form (see `006_anagram_groups`).
- **Self-contained.** Standard library only. The sandbox has no Bundler and no
  network.
- **Exact signature.** State the method/class signature precisely so a correct
  model isn't failed on a naming guess.
- **Mind the difficulty mix.** A range from warm-ups to genuinely tricky tasks
  makes the score more informative.

### Using RSpec instead of Minitest

A task may ship an RSpec suite instead of a Minitest one: name the file
`spec.rb` (rather than `test.rb`) and the framework is auto-detected. Include
exactly one of the two. The convention is otherwise identical — the spec must
`require_relative "solution"`. See `tasks/016_stack` for a complete example:

```ruby
require_relative "solution"

RSpec.describe Stack do
  it "pushes and pops in LIFO order" do
    stack = Stack.new
    stack.push(1)
    stack.push(2)
    expect(stack.pop).to eq 2
  end
end
```

RSpec is preinstalled in the sandbox image, so no Bundler or Gemfile is needed.

### Using private / external tasks

You don't have to add tasks to this repo at all. Keep them anywhere (ideally a
private repo, to avoid training-data contamination) and point the tool at them:

```bash
ruby-llm-eval run --provider anthropic --model claude-sonnet-4-6 \
  --tasks /path/to/my_private_tasks
```

The directory just needs task folders in the same three-file format. An
optional `VERSION` file there is recorded in every report for reproducibility.

## Adding a provider

### Case 1: an OpenAI-compatible or Anthropic-compatible endpoint (no code)

Most providers speak the OpenAI Chat Completions protocol. Adding one is a
single entry in [`configs/providers.yaml`](configs/providers.yaml):

```yaml
providers:
  fireworks:
    type: openai                          # reuse the OpenAI adapter
    base_url: https://api.fireworks.ai/inference/v1
    api_key_env: FIREWORKS_API_KEY        # read from this env var
```

Add the variable to [`.env.example`](.env.example), then:

```bash
export FIREWORKS_API_KEY=...
ruby-llm-eval run --provider fireworks --model accounts/fireworks/models/llama-v3
```

Use `type: anthropic` for endpoints that speak the Anthropic Messages API.

### Case 2: a genuinely different API shape (one small adapter)

If a provider's request/response format isn't OpenAI- or Anthropic-compatible,
add a small adapter class in
[`ruby_llm_eval/model_client.py`](ruby_llm_eval/model_client.py). Implement one
method and register the type:

```python
class MyProviderClient(ModelClient):
    """Adapter for MyProvider's completion API."""

    def complete(self, prompt, *, temperature=0.2, max_tokens=DEFAULT_MAX_TOKENS):
        url = f"{self.base_url.rstrip('/')}/generate"
        headers = {"Content-Type": "application/json", "x-api-key": self.api_key}
        payload = {"model": self.model, "prompt": prompt, "temperature": temperature}
        body = _post_json(url, headers, payload)
        return {
            "text": body["output"],
            "input_tokens": body["usage"]["prompt"],
            "output_tokens": body["usage"]["completion"],
        }


# Register it so configs/providers.yaml can use `type: myprovider`:
_CLIENT_TYPES["myprovider"] = MyProviderClient
```

The contract is the whole interface:

```python
complete(prompt) -> {"text": str, "input_tokens": int, "output_tokens": int}
```

Then add the provider to `configs/providers.yaml` with `type: myprovider`, add
its pricing to [`configs/pricing.yaml`](configs/pricing.yaml) (optional — runs
without it, cost just shows as `n/a`), and update `.env.example`.

## Pull requests

- Keep changes focused and small.
- Run lint, format, and tests locally first.
- For new tasks, confirm the reference passes (step 5 above).
- Never commit secrets. `.env` and `results/` are gitignored; keep it that way.

By contributing you agree your work is licensed under the project's
[MIT License](LICENSE).
