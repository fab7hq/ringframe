---
name: seal
description: Bind a fresh Eval and unchanged subject to one authorized disposition and record the receipt.
---

You are running RingFrame Seal inside Codex. A Seal records a decision; it
merges, publishes, deploys, or certifies nothing.

Shell discipline: the shell is for `ringframe` only, exactly one plain
`ringframe …` command per call, No
`&&`, `;`, pipes, `2>&1`, `head`, `cd`, `which`, or `codex --version`. Read
the command's JSON output directly; never page or filter it.

1. Identify the Eval. Run `ringframe eval list --json`: it lists every Eval
   in this workspace with its id, state, verdict, basis Ask, and subject. If
   an id or title was given, match it there; otherwise show the completed
   Evals through `request_user_input` and let the person choose. Never pick
   the newest for being newest, and never guess an id.
2. Confirm with `request_user_input`: Eval id, verdict, subject, disposition.
   If the disposition is `accepted` and the verdict is not `aligned`, ask the
   person to state the acknowledged risk and pass it as `--acknowledge`.
3. `ringframe seal create --eval <evl_id> --disposition <d> [--acknowledge
   "<text>"] --json`. The actor is the interactive person.
4. Show the receipt path and limitations verbatim, or the `refusal_codes`
   verbatim and stop. Downstream gates verify with `ringframe seal check`.
