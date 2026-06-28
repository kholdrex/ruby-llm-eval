# ruby-llm-eval

[![CI](https://github.com/kholdrex/ruby-llm-eval/actions/workflows/ci.yml/badge.svg)](https://github.com/kholdrex/ruby-llm-eval/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

**Point it at any LLM API and get a Ruby `pass@1` score in about five minutes.**

`ruby-llm-eval` measures how well a model writes Ruby. You give it a model
name and an API key; it asks the model to implement a set of Ruby tasks, runs
the model's code against a hidden test suite inside a Docker sandbox, and
reports the fraction that pass. No GPU, no local model weights, no Bundler.

```text
Model: claude-sonnet-4-6  (provider: anthropic)
Tasks: 36 from tasks (v0.7.0)  N=5  k=1  temperature=0.2  timeout=10s

  001_fizzbuzz                 pass@1 100.0%  [✓ ✓ ✓ ✓ ✓]
  002_palindrome               pass@1 100.0%  [✓ ✓ ✓ ✓ ✓]
  003_two_sum                  pass@1  80.0%  [✓ ✓ ✗ ✓ ✓]
  ...
Overall pass@1: 92.0%   tokens: 4120 in / 9876 out   cost: $0.1612
```

## Why this exists (and the contamination problem)

Public coding benchmarks leak. Once a benchmark is on the internet, its tasks
and solutions end up in the next model's training data, and scores drift upward
without the model actually getting better at *your* kind of work. The defense
is simple: **evaluate on tasks the model has never seen.**

`ruby-llm-eval` is built around that idea. Dropping in your own private Ruby
tasks is a first-class feature, not an afterthought:

```bash
ruby-llm-eval run --provider anthropic --model claude-sonnet-4-6 \
  --tasks ./my_private_tasks
```

A task is just a folder with three files. Keep your tasks in a private repo,
point the tool at them, and you get a contamination-free signal that reflects
the Ruby *you* write — internal APIs, your style, your edge cases. See
[Bring your own tasks](#bring-your-own-tasks).

## How this differs from MultiPL-E / bigcode-evaluation-harness

Those projects are excellent, but they solve a different problem.

| | ruby-llm-eval | MultiPL-E / bigcode-harness |
| --- | --- | --- |
| Audience | engineers picking a model for Ruby work | ML researchers benchmarking base models |
| Languages | Ruby only, on purpose | 18+ languages, Ruby is one cell in a grid |
| Models | any hosted **API** (OpenAI-compatible, Anthropic, local servers) | local **weights**, typically on a GPU |
| Setup | `pip install`, add an API key, run | model download, CUDA, inference stack |
| Tasks | drop a folder in; private tasks encouraged | fixed translated benchmark suites |
| Goal | great DX, fast practical answer | reproducible research at scale |

If you want a leaderboard across many languages and open-weight models, use
MultiPL-E. If you want to know "how good is *this* API model at Ruby, on tasks
I trust?" — that is what this tool is for.

## 5-minute quickstart

**Requirements:** Python 3.10+ and Docker (running). That's it. On macOS or
Windows, Docker Desktop is the easiest option.

```bash
# 1. Install
git clone https://github.com/kholdrex/ruby-llm-eval.git
cd ruby-llm-eval
pip install -e .
```

### Start with a private task, safely

For the cleanest signal, keep your evaluation tasks outside this public repo —
usually in a private repo next to it — and point `ruby-llm-eval` at that
directory.

```bash
# Create a private task directory outside this checkout.
# Use your own task slug; this example uses 001_invoice_total.
mkdir -p ../ruby_eval_private_tasks
cp -R tasks/001_fizzbuzz ../ruby_eval_private_tasks/001_invoice_total

# Edit all three files so they describe your real Ruby task:
#   ../ruby_eval_private_tasks/001_invoice_total/prompt.md
#   ../ruby_eval_private_tasks/001_invoice_total/test.rb
#   ../ruby_eval_private_tasks/001_invoice_total/solution_ref.rb
```

Validate discovery before you spend a cent:

```bash
ruby-llm-eval list-tasks --tasks ../ruby_eval_private_tasks
ruby-llm-eval list-tasks --tasks ../ruby_eval_private_tasks --task 001_invoice_total
```

Then run a no-Docker plumbing check with the built-in `stub` provider. It
returns that task's `solution_ref.rb`, skips the sandbox, and writes reports
marked `evaluation_mode: "offline_stub"` / `sandboxed: false` so you can verify
selection without an API key, Docker, or provider spend:

```bash
ruby-llm-eval run \
  --provider stub --model stub \
  --offline-stub \
  --tasks ../ruby_eval_private_tasks \
  --task 001_invoice_total \
  -n 1
```

To exercise the real Docker sandbox with the stub reference solution, run the
same command without `--offline-stub`.

When the stub run is green, add your API key and switch to a real provider. The
first paid run below keeps `-n 1` so you can confirm the path before spending on
a larger sample:

```bash
cp .env.example .env
$EDITOR .env                 # set ANTHROPIC_API_KEY (or OPENAI_API_KEY, ...)
set -a; source .env; set +a  # export the vars into your shell

ruby-llm-eval run \
  --provider anthropic --model claude-sonnet-4-6 \
  --tasks ../ruby_eval_private_tasks \
  --task 001_invoice_total \
  -n 1
```

You'll get a live per-task readout, plus two files in `results/`:

- `run_<timestamp>.json` — full machine-readable report (reproducible).
- `run_<timestamp>.md` — a markdown table you can paste into an issue or README.

### Try the bundled tasks with no API key

The same `stub` provider works against the bundled task set if you want to watch
the Docker-backed pipeline run without provider spend:

```bash
ruby-llm-eval run --provider stub --model stub
```

### Common options

```bash
ruby-llm-eval run \
  --provider openai --model gpt-4o \
  --tasks ./tasks \      # task directory (default: ./tasks)
  -n 5 \                 # completions per task (default: 5)
  -k 1 \                 # the k in pass@k; must be <= n (default: 1)
  --temperature 0.2 \    # sampling temperature (default: 0.2)
  --timeout 10 \         # per-test timeout in seconds (default: 10)
  --jobs 4 \             # evaluate this many samples in parallel (default: 1)
  --style \              # also score idiomatic style with RuboCop (slower)
  --task 003_two_sum     # run a single task (repeatable); default: all
```

List what's available (and each task's test framework) without running anything:

```bash
ruby-llm-eval list-tasks
ruby-llm-eval list-tasks --tasks ../ruby_eval_private_tasks --task 001_invoice_total
```

To estimate **pass@k for k > 1**, sample more completions and raise `-k`, e.g.
`-n 10 -k 5`. pass@1 uses the standard unbiased estimator from the HumanEval
paper, so larger k is statistically sound.

Run `ruby-llm-eval run --help` for the full list.

## Sample results

A real run on the bundled task set (v0.6.0, 35 tasks — 14 Rails, 21 general),
`n=3` per task at temperature 0.2, with `--style`. Reproduce with
`ruby-llm-eval run --provider <provider> --model <model> -n 3 --style`.

| Model | tier | Rails pass@1 | Rails clean | General pass@1 | Overall | $/run |
| --- | --- | --- | --- | --- | --- | --- |
| `gpt-4o-mini` | cheap | 100% | 83% | 87% | 92% | $0.01 |
| `claude-haiku-4-5` | cheap | 100% | 83% | 95% | 97% | $0.12 |
| `gpt-4o` | mid | 100% | 86% | 90% | 94% | $0.19 |
| `claude-sonnet-4-6` | mid | 100% | 93% | 95% | 97% | $0.29 |
| `claude-opus-4-8` | top | 100% | 93% | 100% | 100% | $1.80 |

**Reading it for Rails:** every model — even `gpt-4o-mini` at ~$0.01/run —
solves all 14 Rails tasks (associations, enums, strong params, callbacks,
migrations, controllers). For everyday Rails the cheapest model is
correctness-complete; paying more buys slightly more idiomatic style
(`clean` 83% → 93%) and better results on the harder *general* algorithm tasks
(87% → 100%), not Rails correctness. To genuinely *rank* models on Rails you'd
want harder Rails tasks (a great contribution) — or drop in your own private
ones. The `--style` axis and the per-category breakdown come from running with
`--style`; the task-set version is recorded in every report so runs stay
comparable.

## Bring your own tasks

This is the headline feature. A task is a directory with three files:

```text
my_private_tasks/
└── 001_invoice_total/
    ├── prompt.md        # what to build + the exact Ruby signature
    ├── test.rb          # Minitest suite; `require_relative "solution"`
    └── solution_ref.rb  # reference solution (never shown to the model)
```

Prefer RSpec? Drop a `spec.rb` (instead of `test.rb`) and it's auto-detected —
see `tasks/016_stack` for a worked example.

Point the tool at any directory. A good workflow is: list the tasks, run an
offline stub selection check, run the Docker-backed stub provider when Docker is
available, then switch to the real provider once the harness is green:

```bash
ruby-llm-eval list-tasks --tasks ../my_private_tasks

ruby-llm-eval run --provider stub --model stub --offline-stub \
  --tasks ../my_private_tasks \
  --task 001_invoice_total \
  -n 1

ruby-llm-eval run --provider stub --model stub \
  --tasks ../my_private_tasks \
  --task 001_invoice_total \
  -n 1

ruby-llm-eval run --provider anthropic --model claude-sonnet-4-6 \
  --tasks ../my_private_tasks \
  --task 001_invoice_total \
  -n 1
```

Keeping tasks outside this repo (ideally in a private one) reduces public
exposure and keeps them out of this project's published task corpus. Real
provider runs still send `prompt.md` content to the selected API provider; the
reference solution and tests remain local and are not included in the model
prompt. The full copy-paste walkthrough for authoring a task is in
[CONTRIBUTING.md](CONTRIBUTING.md#adding-a-task).

## Add a provider

Out of the box you can target any **OpenAI-compatible** endpoint (OpenAI,
OpenRouter, Together, Groq, vLLM, Ollama, LM Studio, …) and the **Anthropic**
Messages API. Adding a new one is usually a single entry in
[`configs/providers.yaml`](configs/providers.yaml); a genuinely new API shape
is one small adapter class. See
[CONTRIBUTING.md → Adding a provider](CONTRIBUTING.md#adding-a-provider).

## How it works

```text
  tasks/            model_client.py        generate.py            evaluate.py             report.py
 ┌────────┐  prompt ┌──────────────┐ code ┌───────────┐ samples ┌────────────────────┐ ┌──────────────┐
 │prompt  ├────────►│ provider     ├─────►│ N samples │────────►│ Docker sandbox     ├►│ pass@1 + cost│
 │test    │         │ adapter      │      │ per task  │         │ (network none, ro, │ │ JSON + .md   │
 │ref     │         └──────────────┘      └───────────┘         │  non-root, limits) │ └──────────────┘
 └────────┘                                                     └────────────────────┘
```

- **Generation** — for each task, sample N completions at the chosen
  temperature, strip code fences, and save them under `results/<model>/<task>/`
  with token metadata.
- **Evaluation** — write each candidate as `solution.rb` next to the task's
  `test.rb` (or `spec.rb`) and run it in a throwaway Docker container. Each
  sample gets a status: `passed`, `failed`, `timeout`, or `error`.
- **Scoring** — `pass@1` per task is the fraction of samples that pass all
  assertions; the overall score is the mean across tasks. Cost is computed from
  token counts and [`configs/pricing.yaml`](configs/pricing.yaml).

### Idiomatic-style scoring (`--style`)

Correctness isn't the whole story — two solutions can both pass while one reads
like idiomatic Ruby and the other doesn't. With `--style`, each candidate is
also linted with **RuboCop** inside the same sandbox, and the report gains a
`clean` column: the fraction of samples with **zero** offences.

The ruleset lives in [`configs/rubocop.yml`](configs/rubocop.yml) and targets
idiom (redundant `return`, `== nil`, non-guard clauses, spacing, …) rather than
house style — quote style and the task-mandated short parameter names are not
penalized. Edit it to match your own conventions.

### Safety

Model-generated code is never run on your host. Every sample executes in a
Docker container started with:

- `--network none` — no network access
- a read-only bind mount of the code
- a non-root user inside the image
- `--memory` / `--cpus` / `--pids-limit` caps
- a per-test timeout (default 10s), enforced both inside and outside the container

## Roadmap

Shipped:

- ✅ **RSpec support** — tasks can ship a `spec.rb` instead of `test.rb`.
- ✅ **pass@k for k > 1** — via the `-k` flag (unbiased HumanEval estimator).
- ✅ **RuboCop idiomatic-style scoring** — via `--style` (a `clean` column).
- ✅ **Parallel evaluation** — via `--jobs`.
- ✅ **Rails-aware tasks** — ActiveRecord (scopes, validations, associations,
  callbacks), a migration, and a JSON controller (rack-test request specs), all
  run in the sandbox against in-memory SQLite.

Planned:

- **A shared, versioned public task set** with a community leaderboard.
- **More providers and seed tasks** — contributions welcome.

Contributions toward any of these are very welcome.

## Contributing

New tasks and new providers are the most valuable contributions, and both are
designed to be a few minutes of work. Start with
[CONTRIBUTING.md](CONTRIBUTING.md). Please also read our short
[Code of Conduct](CODE_OF_CONDUCT.md).

## License

[MIT](LICENSE).
