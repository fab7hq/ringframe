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

Shell discipline: `Bash` is for `ringframe` only, exactly one plain
`ringframe …` command per call, No
`&&`, `;`, pipes, `2>&1`, `head`, `cd`, `which`, or `claude --version`. Read
the command's JSON output directly; never page or filter it.

1. Identify the Eval. Run `ringframe eval list --json`: it lists every Eval
   in this workspace with its id, state, verdict, basis Ask, and subject. If
   an id or title was given, match it there. Otherwise show the completed
   Evals in an `AskUserQuestion` and let the user choose. Never pick the
   newest for being newest, and never guess an id.
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
