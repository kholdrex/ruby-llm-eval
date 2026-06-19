<!-- Thanks for contributing! Keep PRs focused and small. -->

## What does this PR do?

Briefly describe the change and why.

## Type of change

- [ ] New task(s)
- [ ] New provider / model adapter
- [ ] Bug fix
- [ ] Docs
- [ ] Other:

## Checklist

- [ ] `ruff check .` and `ruff format --check .` pass
- [ ] `pytest -q` passes
- [ ] If adding a task: the reference solution passes its own suite
      (`ruby test.rb` / `rspec spec.rb` against `solution_ref.rb`) and the
      tests are deterministic
- [ ] If adding a provider: documented in `configs/providers.yaml`,
      `.env.example`, and (optionally) `configs/pricing.yaml`
- [ ] No secrets committed (`.env` and `results/` stay gitignored)
