# RingFrame Seal

Seal records an attributable decision about a freshly evaluated, unchanged
subject when a person or system needs to rely on that decision.

# Status

This document is intentionally a placeholder. Seal will be designed in detail
after the Ask and Eval contracts establish what is being decided and which
evidence is eligible.

# Preserved direction

- Seal is explicit and optional.
- It binds one exact subject, one completed Eval, one disposition, and one
  authorized decision actor.
- It rechecks subject identity and evidence freshness before writing a receipt.
- It preserves the Eval verdict even when the owner knowingly accepts risk.
- It is deterministic and creates no external release, merge, deployment,
  trading, publishing, or other consequential effect.
- Missing authority, changed subject identity, or stale evidence fails closed
  without a Seal receipt.

# Design work remaining

The detailed command definition must specify:

1. disposition and authority models;
2. subject and Eval freshness rules;
3. acknowledged-risk and limitation handling;
4. atomic receipt creation and failure behavior;
5. downstream verification and consumption; and
6. the immutable Seal receipt schema.

Until that work is complete, [the product definition](product.md) remains the
authority for Seal semantics.
