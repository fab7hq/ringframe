---
name: ask
description: Turn one explicit intent into a confirmed, persisted prompt for a native Codex capability and hand it to the person to submit.
---

You are running RingFrame Ask inside Codex. RingFrame understands Codex's
native capabilities; Codex understands the project; the person supplies and
approves the intent, and on Codex the person also submits the prompt.

Prerequisites the person must have done: `uv tool install ringframe`, and
`codex features enable default_mode_request_user_input` so that the native
`request_user_input` tool is available outside Plan mode. If
`request_user_input` is not available to you, stop and tell the person to
enable that feature; do not confirm through ordinary chat.

The exact source intent is the text after `$rf:ask` in the person's message.
Treat it as immutable.

## Rules for the whole turn

- Do not inspect the workspace, research, or run any command other than
  `ringframe …` before the person confirms.
- Preserve the source intent exactly. Never invent project technology,
  architecture, business context, policy, acceptance criteria, or permissions.
- Shell is for `ringframe` only: exactly one plain `ringframe …` command per
  call, no `&&`, `;`, pipes, `cd`, `mkdir`, `which`, or `codex --version`.
- Never claim the person submitted anything. RingFrame records submission only
  when its hook observes it or the person attests it.

## 1. Route

Classify only what routing needs (task, result, interaction, horizon,
effects). Codex capabilities in this profile:

- `native_plan`: any intent with `write`, `execute`, or `external_effect`
  effects, unless the intent itself says to skip planning. `prompt.txt` must
  begin with `/plan ` followed by the compiled prompt; the person enters it.
- `native_goal`: only when the intent is a continuing objective with a
  terminal condition. `prompt.txt` must begin with `/goal ` and stay under
  4000 characters.
- `native_direct`: read-only or answer-only intents, or an explicit request to
  act now (`"explicit_direct_request": true` in `--route`). Work continues in
  this turn.

## 2. Compile and persist before asking

Write the smallest useful prompt for the selected capability, starting from
the exact intent and adding only instructions that earn their place. Then:

1. Write `.fab7/rf/tmp/stage-<nonce>/source.txt` (exact intent) and
   `.fab7/rf/tmp/stage-<nonce>/prompt.txt` (the compiled prompt, with the
   `/plan ` or `/goal ` prefix when required, nothing else).
2. Run `ringframe ask compile --staged <dir> --title "<short title>"
   --capability <id> --classification '<json>' --route '<json>' --host
   '{"name":"codex","surface":"native-tui"}' --json`. Vocabulary: `task` from
   `question research clarify plan implement diagnose review operate
   document`; `result` from `answer plan workspace_change evidence
   continuing_objective`; `interaction` `interactive|approval_gated`; `horizon`
   `one_turn|session|persistent`; `effects` from `read write execute
   external_effect`. Route keys: `fits`, `alternatives`, `continuation`,
   `effects`, `gaps`, `explicit_direct_request`. Keep the returned `ask_id`.

## 3. Confirm with the native tool

Call `request_user_input` with one question, `id: "route"`, whose text names
the selected capability, why it fits, why the alternatives do not, what will
happen next, and includes the complete compiled prompt. Options: `Proceed
(Recommended)`, `Use direct execution` (or `Plan first`), `Cancel`. Free text
is a revision: compile again with `--link revises:<ask_id>` and ask again.

## 4. Record the answer and deliver

- Proceed: `ringframe ask confirm --ask <ask_id> --json`. Then, for
  `native_plan` or `native_goal`, run `ringframe ask delivery --ask <ask_id>
  --handoff` and show its output verbatim: the person opens `prompt.txt` and
  submits its contents in the Codex composer. For `native_direct`, continue
  with the intent under normal permissions.
- Cancel: `ringframe ask cancel --ask <ask_id> --reason "<why>" --json`, then
  stop.

Submission stays unobserved unless the RingFrame prompt hook sees the exact
bytes or the person runs `ringframe ask submitted --ask <ask_id>`.
