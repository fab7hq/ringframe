# RingFrame

RingFrame is the explicit intent, evaluation, and decision layer inside native
AI harnesses.

> **Ask** turns intent into one confirmed native prompt. **Eval** checks one
> exact result against it. **Seal** records the decision someone is willing to
> rely on.

The harness owns the conversation, model, tools, permissions, and execution.
RingFrame owns the exact intent, the one generated prompt, a truthful record
of delivery, an independent evaluation, and the decision receipt. Everything
it writes goes to `.fab7/rf/` in your worktree, ignored by Git by default.

## Install

Install the CLI first, then the plugin for your harness.

~~~sh
uv tool install ringframe

# Claude Code
claude plugin marketplace add fab7hq/ringframe
claude plugin install rf@ringframe

# Codex (handoff: RingFrame compiles and confirms, you submit the prompt)
codex features enable default_mode_request_user_input
codex plugin marketplace add fab7hq/ringframe
codex plugin add rf@ringframe
~~~

The plugin's skills and hooks call `ringframe`; without it they do nothing.

## Use

~~~text
/rf:ask add an authenticated GET /health/details endpoint with tests
~~~

RingFrame classifies the intent, selects one native capability (Plan mode or
direct execution on Claude Code), compiles the smallest useful prompt, and
asks you to proceed, revise, or cancel in Claude Code's own chooser. On
proceed it persists the intent and prompt, enters Plan mode, and Claude Code
takes over.

~~~text
/rf:eval            evaluate the current commit against the Ask's obligations
/rf:seal accepted   record the decision once the Eval is fresh and the subject unchanged
~~~

`ringframe ask show`, `ringframe ledger verify`, and `ringframe seal check`
read the records back. Run `ringframe --help` for the full command line.

## What it does not do

RingFrame keeps no project memory, imposes no workflow, never retries the
harness, and never merges, publishes, or deploys. Native acceptance of a
prompt proves nothing about completion; that is what Eval is for. An accepted
Seal is a recorded decision, not a promise of correctness.

## Develop

~~~sh
uv sync
uv run pytest
~~~

Tests never call a model. Host behaviour is qualified separately in the
Fab7 HostLab sandbox and cited by qualification id in the docs.

See [docs/README.md](docs/README.md).
