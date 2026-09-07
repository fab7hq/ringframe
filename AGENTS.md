# RingFrame agent instructions

## Setup

~~~sh
uv sync
~~~

Python ≥ 3.11, standard library plus PyYAML (authored configuration is YAML) at runtime. `pytest` is the only dev
dependency.

## Commands

~~~sh
uv run pytest                      # full suite, no model calls
uv run python -m ringframe --help  # the CLI from this checkout
uv build                           # wheel + sdist into dist/
~~~

## Layout

~~~text
core/ringframe/     package: ids, digest, workspace, store, schema, profiles, sessions, ask, evaluate, seal, cli
core/ringframe/profiles/   host capability profiles (JSON)
core/tests/         pytest
plugins/claude/     the `rf` Claude Code plugin: skills/, hooks/
.claude-plugin/     marketplace manifest pointing at plugins/claude
docs/               product authority and architecture notes
~~~

## Rules

- This repository holds source only. Never create `.fab7/` here, never commit
  a ledger, a run, a plan, a changelog, a dated note, or a task id.
- Every guarantee lives in the CLI and its tests. Skills shape behaviour; they
  do not enforce it and never write the ledger.
- Finalized artifacts and ledger lines are immutable. Fix forward with new
  records and typed links.
- Do not claim host behaviour that a retained qualification does not show.
  Host tuples are cited by qualification id.
- Commit with the configured Git identity; never override `user.email`.

## Conventions

- Public JSON keys and exit codes (`0` ok, `1` usage, `2` refused, `3` needs
  input, `4` internal) are a contract from `0.0.1`; add keys, never remove.
- Tests before code. A behaviour without a test in `core/tests/` does not exist.
- Keep modules small and flat; no frameworks, no plugins to the plugin.

## Gotchas

- `--json`, `--workspace`, `--actor`, `--authority` may appear anywhere on the
  command line; the CLI hoists them.
- Hook scripts must always exit 0. A RingFrame failure must never block a
  Claude Code turn.
- `source_verified` is `exact` only when a `UserPromptSubmit` capture exists
  for the same session; the Agent SDK surface may not run plugin hooks.
