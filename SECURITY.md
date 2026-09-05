# Security Policy

## Supported releases

RingFrame `0.0.x` receives security fixes. Reproduce a report against the
newest published `0.0.x` release when practical.

## Report a vulnerability privately

Use [GitHub private vulnerability reporting](https://github.com/fab7hq/ringframe/security/advisories/new).
Include the RingFrame version, host and version, reproduction steps, impact,
and any suggested mitigation. Remove credentials, private prompts, source, and
unrelated logs.

Do not open a public issue for an unpatched vulnerability.

## What RingFrame does and does not guarantee

RingFrame records intent, prompts, evaluations, and decisions under
`.fab7/rf/` with digests and an append-only ledger. It does not guarantee that
a prompt was followed, that a result is correct, or that an accepted Seal is
safe. Eval runs caller-selected commands in the caller's workspace; choose
them as you would any script you run yourself.
