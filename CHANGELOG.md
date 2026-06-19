# Changelog

## 0.2.0

- Add `pass@k` for `k > 1` via the `-k` flag (unbiased HumanEval estimator);
  reports now record `k` and use `pass_at_k` / `overall_pass_at_k` keys.
- Add RSpec support: a task may ship `spec.rb` instead of `test.rb`; the
  framework is auto-detected and RSpec is preinstalled in the sandbox image.
- Add 6 seed tasks (caesar cipher, binary search, merge intervals, matrix
  transpose, longest common prefix, and an RSpec stack); 16 tasks total.
- Validate that required task files exist and are non-empty, with clear
  diagnostics naming the offending file(s).
- Add issue/PR templates and document `pass@k` + RSpec in the README.

## 0.1.0

- Initial release: Ruby-first, API-first `pass@1` harness with a Docker
  sandbox, OpenAI-compatible + Anthropic adapters, and 10 seed tasks.
