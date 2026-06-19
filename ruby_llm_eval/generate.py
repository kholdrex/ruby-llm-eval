"""Generate candidate solutions for each task by prompting the model.

For every task we sample ``n`` completions at a fixed temperature, strip any
markdown code fences, and write each candidate plus its token metadata under
``results/<model>/<task>/``.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .model_client import ModelClient, ModelError, StubClient
from .tasks import Task

PROMPT_TEMPLATE = """You are an expert Ruby developer.

Implement the following in Ruby. Your code will be saved as `solution.rb` and
loaded by a hidden test suite with `require_relative "solution"`, so:

- Define exactly the method(s)/class described below, at the top level.
- Do not print anything, read input, or include example usage.
- Do not write any `require` statements for testing frameworks.

--- TASK ---
{prompt}
--- END TASK ---

Respond with the Ruby source for `solution.rb`. A single fenced code block is
fine; any surrounding prose or fences will be stripped.
"""

_FENCE_RE = re.compile(r"```[a-zA-Z0-9_+-]*\n(.*?)```", re.DOTALL)


def build_prompt(task_prompt: str) -> str:
    return PROMPT_TEMPLATE.format(prompt=task_prompt.strip())


def strip_code_fences(text: str) -> str:
    """Return the first fenced code block, or the whole text if unfenced."""
    text = text.strip()
    match = _FENCE_RE.search(text)
    if match:
        text = match.group(1)
    return text.strip() + "\n"


@dataclass
class Sample:
    """One generated candidate solution plus its token accounting."""

    index: int
    code: str
    input_tokens: int
    output_tokens: int
    error: str | None = None


def safe_model_dir(model: str) -> str:
    """Make a model name safe to use as a single path component."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", model).strip("_") or "model"


def generate_for_task(
    client: ModelClient,
    task: Task,
    *,
    n: int,
    temperature: float,
    out_dir: Path,
) -> list[Sample]:
    """Generate ``n`` samples for one task and persist them to ``out_dir``."""
    task_dir = out_dir / task.id
    task_dir.mkdir(parents=True, exist_ok=True)

    prompt = build_prompt(task.prompt)
    samples: list[Sample] = []

    for i in range(n):
        if isinstance(client, StubClient):
            # The stub has no real model; feed back the reference solution so CI
            # can exercise generate -> evaluate -> report without API keys.
            code = task.reference()
            sample = Sample(index=i, code=code, input_tokens=0, output_tokens=0)
        else:
            try:
                result = client.complete(prompt, temperature=temperature)
                sample = Sample(
                    index=i,
                    code=strip_code_fences(result["text"]),
                    input_tokens=result["input_tokens"],
                    output_tokens=result["output_tokens"],
                )
            except ModelError as exc:
                sample = Sample(index=i, code="", input_tokens=0, output_tokens=0, error=str(exc))

        (task_dir / f"sample_{i}.rb").write_text(sample.code, encoding="utf-8")
        samples.append(sample)

    (task_dir / "samples.json").write_text(
        json.dumps([asdict(s) for s in samples], indent=2), encoding="utf-8"
    )
    return samples
