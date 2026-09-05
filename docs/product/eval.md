# RingFrame Eval

Eval is RingFrame's product center. It independently evaluates one exact
subject against an Ask's Eval blueprint or another explicit contract.

# Status

This document is intentionally a placeholder. Detailed design will follow
after the Ask contract and its generated Eval blueprint are validated.

# Preserved direction

- Freeze the evaluation definition before collecting outcome-dependent
  evidence.
- Bind the evaluation to an exact, digestible subject.
- Keep deterministic checks, semantic graders, native reviews, external
  observations, and human observations separately attributed.
- Evaluate every obligation and forbidden effect with explicit coverage.
- Return `aligned`, `drifted`, or `incomplete`; missing evidence never becomes
  success.
- Remain read-only. Remediation requires native work and, when appropriate, a
  new explicit Ask.
- Treat the executing harness's self-review as evidence, not as RingFrame's
  final verdict.

# Design work remaining

The detailed command definition must specify:

1. how Ask-generated blueprints become frozen Eval definitions;
2. subject identity and snapshot rules;
3. deterministic, semantic, external, and human evidence contracts;
4. grader independence, calibration, disagreement, and reliability;
5. coverage and aggregate verdict rules;
6. evaluation cost, latency, and freshness limits;
7. comparison against untreated native baselines; and
8. the immutable Eval record schema.

Until that work is complete, [the product definition](product.md) remains the
authority for Eval semantics.
