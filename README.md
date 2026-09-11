# RingFrame

**You ask an AI agent for something. RingFrame writes down what you asked,
checks what came back, and records what you decided.**

Runs inside Claude Code and Codex.

| Command | What it does |
| --- | --- |
| [**Ask**](https://github.com/fab7hq/ringframe/blob/main/docs/commands/ask.md) | Turns your intent into a prompt you read and confirm before it runs. |
| [**Eval**](https://github.com/fab7hq/ringframe/blob/main/docs/commands/eval.md) | Checks the work against everything still open, using independent judges. |
| [**Seal**](https://github.com/fab7hq/ringframe/blob/main/docs/commands/seal.md) | Closes those Asks with your decision, and a receipt you can verify. |

Talk to your agent normally in between. Run Eval when you want a second
opinion, Seal when you have made up your mind.

Everything stays on your machine, in your project's `.fab7/rf/`, ignored by Git
by default. Your project must be a Git repository with at least one commit —
Eval needs something to diff.

## Install

You need [uv](https://docs.astral.sh/uv/getting-started/installation/),
Python 3.11+, Git, and macOS or Linux.

```sh
curl -fsSL https://raw.githubusercontent.com/fab7hq/ringframe/main/install.sh | sh
```

That installs the CLI and downloads your rules from the
[Fab7 marketplace](https://github.com/fab7hq/fab7) into `~/.fab7/rf/config/`.
Later, `ringframe sync` updates them.

Then install the plugin for your agent — see the guides below.

> The published PyPI release predates this setup and cannot read it, so the
> installer takes the CLI from `main` for now. Building from a checkout:
> `./install.sh --source`.

## Set up your agent

- [Claude Code](https://github.com/fab7hq/ringframe/blob/main/docs/usage/claude.md)
- [Codex](https://github.com/fab7hq/ringframe/blob/main/docs/usage/codex.md)

## Change the rules

Ask attaches your standing rules to every prompt — things like *write the
failing test first*. You can change them for yourself, or for one project.

Yours go in `~/.fab7/rf/overrides/`, a project's in
`<project>/.fab7/rf/deltas/`. A sync never touches either.

See [Rules](https://github.com/fab7hq/ringframe/blob/main/docs/architecture/delta.md).

---

[What RingFrame is](https://github.com/fab7hq/ringframe/blob/main/docs/product.md) ·
[Contributing](https://github.com/fab7hq/ringframe/blob/main/AGENTS.md) ·
[Security](https://github.com/fab7hq/ringframe/blob/main/SECURITY.md) ·
[Apache 2.0](https://github.com/fab7hq/ringframe/blob/main/LICENSE)
