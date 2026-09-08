# RingFrame

RingFrame connects what you ask an AI coding agent to do with a review of its
work and your decision to accept it. It runs inside Claude Code and Codex.

| Command | Purpose |
| --- | --- |
| **Ask** | Turn your intent into a prompt you review and confirm. |
| **Eval** | Judge the work against all open Asks; report a verdict and confidence. |
| **Seal** | Close those Asks with your decision and a local receipt. |

Your agent keeps control of its tools, permissions, and workflow. RingFrame
stores prompts and records in `.fab7/rf/` in your project, ignored by Git by
default.

## Install

Requires Python 3.11+, uv, Git, and a POSIX environment (macOS or Linux).
Install the CLI first, then choose your host plugin.

For the upcoming 0.0.1 release, run this from the RingFrame checkout root:

```sh
uv tool install .
```

After 0.0.1 is published to PyPI:

```sh
uv tool install ringframe==0.0.1
```

### Claude Code

```sh
claude plugin marketplace add fab7hq/ringframe
claude plugin install rf@ringframe
```

### Codex

```sh
codex features enable default_mode_request_user_input
codex plugin marketplace add fab7hq/ringframe
codex plugin add rf@ringframe
```

In Codex, open `/hooks` and trust the `rf@ringframe` prompt hook. The feature
above enables Ask and Seal confirmation outside Plan mode.

## Use

Open your project in the host and invoke the skills explicitly:

| Action | Claude Code | Codex |
| --- | --- | --- |
| Start work | `/rf:ask add a health endpoint with tests` | `$rf:ask add a health endpoint with tests` |
| Review work | `/rf:eval` | `$rf:eval` |
| Accept work | `/rf:seal accepted` | `$rf:seal accepted` |

Ask shows the generated prompt for confirmation. Claude Code can enter Plan
mode after approval. For Codex Plan or Goal routes, submit the complete
`prompt.txt` that RingFrame provides. Direct routes continue in the same turn.

Continue ordinary conversation as needed, and run Eval again when you want
another review. Eval uses model judges; it does not run your project's tests.
Seal accepts `accepted`, `rejected`, `deferred`, or `abandoned`, with or without
an Eval. An accepted Seal records your decision; it does not certify correctness.

To inspect local records:

```sh
ringframe ask list --json
ringframe eval list --json
ringframe ledger verify --json
```

## Before release

The current judged Eval and the edited skill instructions still need host
qualification. Earlier host results apply to earlier artifacts; see the
[Claude Code](docs/architecture/claude-code.md) and
[Codex](docs/architecture/codex.md) notes for their scope.

See the [documentation](docs/README.md), [contributor instructions](AGENTS.md),
and [security policy](SECURITY.md). Licensed under [Apache 2.0](LICENSE).
