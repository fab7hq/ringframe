---
name: seal
description: Bind a fresh Eval and unchanged subject to one authorized disposition and record the receipt.
argument-hint: [eval reference] <accepted|rejected|deferred|abandoned>
disable-model-invocation: true
allowed-tools: AskUserQuestion Bash(ringframe *)
---

You are running RingFrame Seal. A Seal records a decision; it merges,
publishes, deploys, or certifies nothing.

Arguments: `$ARGUMENTS`

1. Identify the Eval. If no id was given, list `eval.completed` records via
   `ringframe ledger verify --json` context and `ringframe ask show`, or ask
   the user with `AskUserQuestion`. Never pick the newest for being newest.
2. Confirm with `AskUserQuestion`: the Eval id, its verdict, the subject, and
   the disposition. If the disposition is `accepted` and the verdict is not
   `aligned`, ask the user to state the acknowledged risk in their own words;
   pass it as `--acknowledge "<text>"`.
3. Run `ringframe seal create --eval <evl_id> --disposition <d> [--acknowledge
   "<text>"] --json`. The actor is the interactive user; do not pass
   `--actor` or `--authority` unless the user explicitly names a
   pre-authorized policy.
4. On success show the receipt path and its limitations verbatim. On exit 2
   show the `refusal_codes` verbatim and stop; do not retry with a different
   subject or by editing records. Downstream gates verify a receipt with
   `ringframe seal check --seal <sel_id>`.
