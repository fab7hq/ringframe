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
# then, inside Codex, trust the rf@ringframe hook under /hooks
~~~

The plugin's skills and hooks call `ringframe`; without it they do nothing.
On Codex, RingFrame compiles and confirms; you paste the prompt (see
`docs/architecture/codex.md` for the qualified tuple and its limits).

## Status

Qualified end to end on Claude Code 2.1.263 (Sonnet 5, low effort) at commit
`007ac50` (`ringframe-loop-q05`, 3 of 3) and on Codex 0.153.4 at `5190802`
(`ringframe-loop-codex-q07`, 3 of 3): Ask compiles and confirms a composed
prompt, the model implements, Eval records a verdict on the work, a follow-up
Ask runs the same way, Eval records a second verdict, and Seal writes a
receipt that `ringframe seal check` verifies, ledger clean throughout. Eval
has since been redesigned as a judged verdict with confidence over every open
Ask (sub-agent judges, no project commands); that design is not yet
qualified on a host. Not released to PyPI yet.

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
/rf:eval            judge the work so far against every open Ask; verdict with confidence, no questions asked
/rf:seal accepted   close the open Asks with your decision; the latest Eval is recorded as a fact
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
