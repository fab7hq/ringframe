---
name: seal
description: Close the open Asks with one disposition; record the latest Eval as a fact and the receipt.
---

You are running RingFrame Seal inside Codex. A Seal is the person's decision
to close the open Asks; it merges, publishes, deploys, or certifies nothing,
and no Eval verdict blocks it.

Requires the native `request_user_input` tool in this turn. If it is
unavailable, stop and explain that native confirmation is required. On hosts
exposing `default_mode_request_user_input`, the person can enable it with
`codex features enable default_mode_request_user_input`; otherwise use a host
mode that exposes the tool. Do not change settings or substitute ordinary chat.
If the host rejects the tool call, the chooser is cancelled or dismissed, or
no answer is returned, do not create a Seal.

Shell discipline: the shell is for `ringframe` only, exactly one plain
`ringframe …` command per call. No `&&`, `;`, pipes, `2>&1`, `head`, `cd`,
`which`, or `codex --version`. Read the command's JSON output directly; never
page or filter it.

1. Run `ringframe eval list --json` and `ringframe ask list --json` to see the
   open Asks and the latest completed Eval over them (verdict, confidence).
   Seal binds that Eval by default; pass `--eval <evl_id>` only when the
   person names another.
2. One confirmation through `request_user_input`: the open Asks by title, the
   Eval's verdict and confidence (or "no Eval"), and the disposition. Options:
   the disposition as given (Recommended), the other dispositions, Cancel.
   Free text is the person's note; pass it verbatim as `--note "<text>"`. Do
   not ask for an acknowledgement or a justification.
3. `ringframe seal create --disposition <d> [--eval <evl_id>] [--note
   "<text>"] --json`. The actor is the interactive person.
4. Show the receipt path, the sealed Asks, the recorded Eval fact (`verdict`,
   `confidence`, `subject_matches`), and the limitations verbatim; or the
   `refusal_codes` verbatim and stop (`seal.no_open_ask`: nothing to close).
   Downstream gates read a receipt with `ringframe seal check`.
