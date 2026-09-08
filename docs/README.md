# RingFrame documentation

Start with the [README](../README.md) for installation and first use.
These references describe the 0.0.1 source and intended skill behavior;
host evidence is scoped separately in the adapter notes.

| Reference | Read it to understand |
| --- | --- |
| [Product](product/product.md) | Responsibilities and limits |
| [Ask](product/ask.md) | Prompt compilation, confirmation, and delivery |
| [Eval](product/eval.md) | Open Asks, judged verdicts, and confidence |
| [Seal](product/seal.md) | Decisions, authority, and receipt checks |
| [Ledger](architecture/ledger.md) | Local files, events, and integrity checks |
| [Compiler](architecture/compiler.md) | Directive selection and prompt provenance |
| [Claude Code](architecture/claude-code.md) | Native Plan activation and hook evidence |
| [Codex](architecture/codex.md) | Prompt handoff, hook setup, and limitations |

For maintenance, use [AGENTS.md](../AGENTS.md). For data handling and private
reports, use [SECURITY.md](../SECURITY.md). CLI syntax is available through
`ringframe --help` and each subcommand's `--help`.

Contributor tests involving models follow [LLM verification](verification.md).
