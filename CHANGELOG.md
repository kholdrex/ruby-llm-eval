# Changelog

## Unreleased

- Reject non-string optional task `meta.yml` category values with task/file-specific diagnostics, and treat explicit null categories as the default `general` category.
- Improve optional task `meta.yml` validation diagnostics for malformed private/BYO task files.
- Add explicit `--offline-stub` mode for provider-free, no-Docker private task selection smoke checks; reports are marked as non-sandboxed offline stub output.
- Retry provider requests without `temperature` when a model rejects it (e.g.
  Claude Opus 4.8 and reasoning models return 400), instead of failing the run.
- Add 8 more Rails tasks (has_many :through, enum, strong params, custom
  as_json, conditional validation, parameterized scope, service object, update
  action) and a per-category report breakdown. Task set v0.6.0 (35 tasks, 14 rails).
- Reject selected task ids with leading or trailing whitespace before discovery with clearer invalid-id diagnostics.
- Add regression coverage for selected malformed tasks missing `solution_ref.rb`, missing a test file, or shipping both `test.rb` and `spec.rb`.
- Reject blank or whitespace-only selected task ids before discovery so CLI diagnostics do not collapse into unclear unknown-task errors.
- Add 5 harder tasks (string-to-integer with 32-bit clamp, bijective spreadsheet
  columns, a precedence/parentheses calculator with truncating division,
  integer-to-words, and full text justification). Task set bumped to v0.5.0
  (27 tasks); these break the pass@1 ceiling — claude-sonnet-4-6 and gpt-4o
  each fail at least one.
- Verify TLS using certifi's CA bundle, fixing `CERTIFICATE_VERIFY_FAILED`
  errors when calling provider APIs from a Python without system certificates
  (common on macOS). Adds a `certifi` dependency.
- Reject path-like selected task ids before task discovery with clearer directory-name diagnostics.
- Clean up evaluation sandbox scratch directories even when a task run fails before report generation.
- Expand Rails coverage: add ActiveRecord callbacks (020), a migration (021),
  and a JSON controller driven by rack-test (022). The sandbox now also installs
  `actionpack` + `rack-test`. Task set bumped to v0.4.0 (22 tasks).
- Report selected task ids that point at files as task/file-specific validation errors instead of generic unknown ids.
- Reject duplicate selected task ids before discovering task suites for runs or listings.
- Add installed-wheel coverage verifying bundled configs, sandbox assets, and task files are discoverable outside a source checkout.
- Add Rails-aware tasks: ActiveRecord scopes, validations, and associations run
  against in-memory SQLite in the sandbox (`activerecord` + `sqlite3` are
  preinstalled). Task set bumped to v0.3.0 (19 tasks).
- Add CI coverage for selecting a private task with the stub provider.
- Improve selected custom-task diagnostics so malformed task directories requested by id report missing `prompt.md` directly instead of looking like unknown task ids.
- Report invalid UTF-8 in required task files as task/file-specific validation errors instead of leaking raw decode failures.

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
