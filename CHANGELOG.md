# Changelog

## Unreleased

- Add installed-wheel coverage verifying bundled configs, sandbox assets, and task files are discoverable outside a source checkout.
- Add Rails-aware tasks: ActiveRecord scopes, validations, and associations run
  against in-memory SQLite in the sandbox (`activerecord` + `sqlite3` are
  preinstalled). Task set bumped to v0.3.0 (19 tasks).
- Add CI coverage for selecting a private task with the stub provider.
- Improve selected custom-task diagnostics so malformed task directories requested by id report missing `prompt.md` directly instead of looking like unknown task ids.

## 0.2.0

- Add `pass@k` for `k > 1` via the `-k` flag (unbiased HumanEval estimator);
  reports now record `k` and use `pass_at_k` / `overall_pass_at_k` keys.
- Add RSpec support: a task may ship `spec.rb` instead of `test.rb`; the
  framework is auto-detected and RSpec is preinstalled in the sandbox image.
- Add 6 seed tasks (caesar cipher, binary search, merge intervals, matrix
  transpose, longest common prefix, and an RSpec stack); 16 tasks total.
- Add `--jobs` to evaluate samples in parallel containers (default: 1).
- Add a `list-tasks` command that lists tasks and their test framework.
- Bundle default configs, sandbox, and seed tasks in installed wheels so the CLI
  can discover them outside a source checkout.
- Add `--style`: lint each candidate with RuboCop in the sandbox and report a
  `clean` (offence-free) rate alongside pass@k. Ruleset in `configs/rubocop.yml`.
- Validate that required task files exist and are non-empty, with clear
  diagnostics naming the offending file(s).
- Add issue/PR templates and document `pass@k` + RSpec in the README.

## 0.1.0

- Initial release: Ruby-first, API-first `pass@1` harness with a Docker
  sandbox, OpenAI-compatible + Anthropic adapters, and 10 seed tasks.
