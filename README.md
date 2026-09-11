# RingFrame

RingFrame connects what you ask an AI coding agent to do with a review of its
work and your decision to accept it. It runs inside Claude Code and Codex.

| Command | Purpose |
| --- | --- |
| [**Ask**](https://github.com/fab7hq/ringframe/blob/main/docs/commands/ask.md) | Turn your intent into a prompt you review and confirm. |
| [**Eval**](https://github.com/fab7hq/ringframe/blob/main/docs/commands/eval.md) | Review the work against open Asks with independent model judges. |
| [**Seal**](https://github.com/fab7hq/ringframe/blob/main/docs/commands/seal.md) | Close those Asks with your decision and a local receipt. |

Continue working with your agent between commands. Run Eval when you want a
review, and Seal when you decide to close the work. Prompts, reviews, and
receipts stay in your project's `.fab7/rf/`, ignored by Git by default.
RingFrame requires the project to be a Git repository with at least one commit.

## Installation

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/), Python
3.11+, Git, and a POSIX shell on macOS or Linux.

```sh
curl -fsSL https://raw.githubusercontent.com/fab7hq/ringframe/main/install.sh | sh
```

This installs the latest CLI and downloads your configuration — harness
profiles and rules — from the [Fab7 marketplace](https://github.com/fab7hq/fab7)
into `~/.fab7/rf/config/`. Run `ringframe sync` to update it later. Then install
the plugin for your harness from that marketplace using its guide below.

Personal rule changes belong in `~/.fab7/rf/overrides/` and project ones in
`<project>/.fab7/rf/deltas/`; neither is touched by a sync.

The published PyPI release predates this configuration layout and cannot read
it, so the installer takes the CLI from `main` until a newer release exists.
To build and install a local checkout, run `./install.sh --source` from it.

## Use with your harness

Each guide covers prerequisites, plugin installation, first use, and updates.

- [Claude Code](https://github.com/fab7hq/ringframe/blob/main/docs/usage/claude.md)
- [Codex](https://github.com/fab7hq/ringframe/blob/main/docs/usage/codex.md)

## Customization

Deltas tailor the rules Ask uses to compose your prompt. Set personal defaults
or override them for a project. See [delta configuration](https://github.com/fab7hq/ringframe/blob/main/docs/architecture/delta.md)
for examples.

[Product reference](https://github.com/fab7hq/ringframe/blob/main/docs/product.md) · [Contributing](https://github.com/fab7hq/ringframe/blob/main/AGENTS.md) ·
[Security](https://github.com/fab7hq/ringframe/blob/main/SECURITY.md) · [Apache 2.0](https://github.com/fab7hq/ringframe/blob/main/LICENSE)
