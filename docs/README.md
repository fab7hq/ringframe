# RingFrame documentation

| Document | Purpose |
| --- | --- |
| [product/product.md](product/product.md) | Product authority: what RingFrame is, owns, and refuses to own |
| [product/ask.md](product/ask.md) | Ask command contract |
| [product/eval.md](product/eval.md) | Eval command direction (detailed design follows the first slice) |
| [product/seal.md](product/seal.md) | Seal command direction (detailed design follows the first slice) |
| [architecture/ledger.md](architecture/ledger.md) | The `.fab7/rf/` workspace ledger as implemented |
| [architecture/claude-code.md](architecture/claude-code.md) | How the `rf` plugin drives Claude Code |
| [architecture/codex.md](architecture/codex.md) | How the `rf` plugin works on Codex (handoff) |
| [architecture/compiler.md](architecture/compiler.md) | How `ask compile` renders prompts from delta catalogs |

Documents are claims; the tests under `core/tests/` are the evidence for what
the code actually does.
