---
name: seal
description: Close the open Asks with one disposition; record the latest Eval as a fact and the receipt.
argument-hint: <accepted|rejected|deferred|abandoned> [note]
disable-model-invocation: true
allowed-tools: AskUserQuestion Bash(ringframe *)
---

You are running RingFrame Seal. A Seal is the person's decision to close the
open Asks; it merges, publishes, deploys, or certifies nothing, and no Eval
verdict blocks it.

Arguments: `$ARGUMENTS`

Shell discipline: `Bash` is for `ringframe` only, exactly one plain
`ringframe …` command per call. No `&&`, `;`, pipes, `2>&1`, `head`, `cd`,
`which`, or `claude --version`. Read the command's JSON output directly;
never page or filter it.

1. Run `ringframe eval list --json` and `ringframe ask list --json` to see the
   open Asks and the latest completed Eval over them (its verdict and
   confidence). Seal binds that Eval by default; pass `--eval <evl_id>` only
   when the person names another.
2. One confirmation with `AskUserQuestion`: the open Asks by title, the Eval's
   verdict and confidence (or "no Eval"), and the disposition. Options:
   the disposition as given (Recommended), the other dispositions, Cancel.
   Free text is the person's note; pass it verbatim as `--note "<text>"`.
   Do not ask for an acknowledgement or a justification; the decision is
   theirs.
3. Run `ringframe seal create --disposition <d> [--eval <evl_id>] [--note
   "<text>"] --json`. The actor is the interactive user; do not pass
   `--actor` or `--authority` unless the user explicitly names a
   pre-authorized policy.
4. On success show the receipt path, the sealed Asks, the recorded Eval fact
   (`verdict`, `confidence`, `subject_matches`), and the limitations verbatim.
   On exit 2 show the `refusal_codes` verbatim and stop (`seal.no_open_ask`
   means there is nothing to close; `seal.eval_unrelated` means the named
   Eval judged other Asks). Downstream gates read a receipt with
   `ringframe seal check --seal <sel_id>`.
