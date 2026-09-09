# RingFrame in Codex

## Prerequisites

- Install the [RingFrame CLI](../../README.md#installation).
- Install and sign in to [Codex](https://developers.openai.com/codex/cli/).
- Make `ringframe` available on the PATH used by Codex.
- Enable native sub-agent tools for Eval and allow the plugin's file and shell
  operations within your usual Codex permissions.

Ask and Seal use Codex's native `request_user_input` chooser. Use a mode that
exposes this tool. If your Codex exposes the `default_mode_request_user_input`
feature, you can enable confirmation in Default mode with:

```sh
codex features enable default_mode_request_user_input
```

RingFrame does not change these host settings for you.

## Install the plugin

```sh
codex plugin marketplace add fab7hq/ringframe
codex plugin add rf@ringframe
```

Start a new Codex session in your project directory. Open `/hooks`, review the
`rf@ringframe` prompt hook, and trust it. Plugin installation and hook trust are
separate steps; see the [official Codex reference](https://learn.chatgpt.com/docs/llms-full.txt)
for plugin and hook configuration.

RingFrame creates project records on first use, including when the project is
nested in another Git repository.

## Ask, work, evaluate, seal

Enter these in Codex as you work:

```text
$rf:ask add a health endpoint with tests
$rf:eval use native sub-agents
$rf:seal accepted
```

Ask proposes a route and displays the complete prompt for confirmation. You
can proceed, revise it, choose direct execution, or cancel. For Plan, Goal, or
Review, it provides the saved prompt for you to submit through `/plan`, `/goal`,
or `/review`. Direct execution continues in the same turn. You do not need to
name a route in your intent.

Continue ordinary conversation to implement or revise the work. When invoking
Eval in Codex, explicitly ask it to use sub-agents, as shown above, to authorize
spawning the reviewers. Include this instruction even when native sub-agent
tools are enabled; do not rely on `$rf:eval` alone to request delegation.

The four sub-agents are an intent judge, then coverage, drift, and adversary
assessors. Eval reports omissions, unexplained changes, and confidence based
on judge agreement. It compares the diff with effective intent; it does not run the project's tests.

Seal asks you to confirm closing the open Asks. Use `accepted`, `rejected`,
`deferred`, or `abandoned`, optionally followed by a note. You can Seal with or
without an Eval; the receipt records your decision.

For command details, see [Ask](../commands/ask.md), [Eval](../commands/eval.md),
and [Seal](../commands/seal.md).

## Update

Run the [CLI installer](../../README.md#installation) again, then refresh the
marketplace and install its latest plugin:

```sh
codex plugin marketplace upgrade ringframe
codex plugin add rf@ringframe
```

Start a new session and review `/hooks` again if the hook definition changed.

## Configuration and records

[Customize deltas](../architecture/delta.md) globally or per project. RingFrame uses
the project directory reported by Codex; it does not move records when a
session ends. From that same directory, inspect them with:

```sh
ringframe ask list --json
ringframe eval list --json
ringframe ledger verify --json
```

If Ask or Seal cannot open confirmation, check that `request_user_input` is
available in the current mode. If Eval reports shared-context review, check
that native sub-agent tools are enabled and exposed in the session. If the CLI
is missing, check `ringframe --version` in the shell that launches Codex.
