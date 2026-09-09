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

Install the latest release:

```sh
uv tool install ringframe
```

Upgrade an existing unpinned installation with `uv tool upgrade ringframe`.
For a specific version, open its
[repository release/tag](https://github.com/fab7hq/ringframe/releases)
and follow that release's version-specific CLI and plugin instructions.

### Claude Code

```sh
claude plugin marketplace add fab7hq/ringframe
claude plugin install rf@ringframe
```

### Codex

```sh
codex plugin marketplace add fab7hq/ringframe
codex plugin add rf@ringframe
```

Start a new host session after installation. In Codex, open `/hooks` and trust
the `rf@ringframe` prompt hook. Ask and Seal require the native
`request_user_input` tool. If unavailable, use a host mode that exposes it;
on hosts offering `default_mode_request_user_input`, you can enable that
feature with `codex features enable default_mode_request_user_input`.
RingFrame does not change host settings.

Upgrade the CLI and both installed host plugins together. Plugin installation
does not enable automatic updates; use your host's marketplace/plugin update flow.

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

## Qualification limits

Formal host qualification is incomplete. The documentation describes the
implemented CLI and intended skill behavior; it does not establish host
reliability or improved results over a native workflow.

See the [documentation](https://github.com/fab7hq/ringframe/blob/main/docs/product.md), [contributor instructions](https://github.com/fab7hq/ringframe/blob/main/AGENTS.md),
and [security policy](https://github.com/fab7hq/ringframe/blob/main/SECURITY.md). Licensed under [Apache 2.0](https://github.com/fab7hq/ringframe/blob/main/LICENSE).
