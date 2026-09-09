# RingFrame in Claude Code

## Prerequisites

- Install the [RingFrame CLI](../../README.md#installation).
- Install and sign in to [Claude Code](https://code.claude.com/docs/en/setup).
- Make `ringframe` available on the PATH used by Claude Code.
- Allow the plugin's confirmation, file, shell, and native Agent tools within
  your usual Claude Code permissions. Eval delegates to four native judges.

## Install the plugin

```sh
claude plugin marketplace add fab7hq/ringframe
claude plugin install rf@ringframe
```

This installs for your user. To share the plugin setting with a project, run
`claude plugin install rf@ringframe --scope project` from that project instead.
See Claude's [plugin installation reference](https://code.claude.com/docs/en/plugins-reference#plugin-install)
for installation scopes.

Start a new Claude Code session in your project directory. RingFrame creates
that project's records on first use, including when the project is nested in
another Git repository.

## Ask, work, evaluate, seal

Enter these in Claude Code as you work:

```text
/rf:ask add a health endpoint with tests
/rf:eval
/rf:seal accepted
```

Ask proposes a route and displays the complete prompt for confirmation. You
can proceed, revise it, choose direct execution, or cancel. After approval,
Plan enters Claude's native Plan mode; direct execution continues in the same
turn. For a continuing Goal, Ask provides the saved prompt for you to submit
through the native command. You do not need to name a route in your intent.

Continue ordinary conversation to implement or revise the work. Eval reviews
all open Asks with an intent judge and three assessors: coverage, drift, and
adversary. It reports omissions, unexplained changes, and confidence based on
judge agreement. Eval compares the diff with effective intent; it does not run the project's tests.

Seal asks you to confirm closing the open Asks. Use `accepted`, `rejected`,
`deferred`, or `abandoned`, optionally followed by a note. You can Seal with or
without an Eval; the receipt records your decision.

For command details, see [Ask](../commands/ask.md), [Eval](../commands/eval.md),
and [Seal](../commands/seal.md).

## Update

Run the [CLI installer](../../README.md#installation) again, then refresh the
marketplace and plugin:

```sh
claude plugin marketplace update ringframe
claude plugin update rf@ringframe
```

For a project-scoped installation, add `--scope project` to the plugin update.
Restart Claude Code to load the updated plugin.

## Configuration and records

[Customize deltas](../architecture/delta.md) globally or per project. RingFrame uses
the project directory reported by Claude Code; it does not move records when
a session ends. From that same directory, inspect them with:

```sh
ringframe ask list --json
ringframe eval list --json
ringframe ledger verify --json
```

If the commands are missing, check that the plugin is enabled in `/plugin` and
start a new session. If the CLI is missing, check `ringframe --version` in the
shell that launches Claude Code.
