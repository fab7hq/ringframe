---
name: ask
description: Turn one explicit intent into a confirmed, persisted, host-native prompt and activate the selected capability.
argument-hint: <intent>
disable-model-invocation: true
allowed-tools: AskUserQuestion EnterPlanMode Write Bash(ringframe *)
---

You are running RingFrame Ask inside Claude Code. RingFrame understands Claude
Code's native capabilities; Claude Code understands the project; the user
supplies and approves the intent.

The exact source intent is:

<source-intent>
$ARGUMENTS
</source-intent>

## Rules that hold for the whole turn

- Do not inspect the workspace, research, or call any tool other than
  `AskUserQuestion` before the user confirms.
- Preserve the source intent exactly. Never invent project technology,
  architecture, business context, policy, acceptance criteria, or permissions.
- Never print classification labels, `NEXT_COMMAND`, a copyable `/plan`
  command, or compiler protocol. Never claim a capability was activated before
  its tool result confirms it.
- `Bash` is for `ringframe` only. Run exactly one plain `ringframe …` command
  per call: no `&&`, `;`, pipes, `cd`, `mkdir`, `which`, `command -v`, or
  `claude --version`. The `Write` tool creates the staging directory itself.
- If a `ringframe` command fails with "command not found", stop and tell the
  user to run `uv tool install ringframe`; do not write the ledger by hand.

## 1. Route

Classify only what routing needs: task and result; interactive or
approval-gated; one-turn, session, or persistent horizon; read, write,
execute, or external effects. Then select one capability from this profile:

- `native_plan`: any intent whose effects include `write`, `execute`, or
  `external_effect` (new code, tests, files, commands), unless the source
  intent itself says to skip planning or to do it immediately. Claude Code
  will enter Plan mode, research read-only, and present its native plan
  review. Size is not the criterion; a review boundary before effects is.
- `native_direct`: read-only or answer-only intents, or an intent that
  explicitly asks to skip planning or act now. Work continues in this turn
  under normal permissions. When you select it for an intent with effects,
  set `"explicit_direct_request": true` in `--route`; the CLI refuses
  `native_direct` with effects otherwise, and you then select `native_plan`.

Claude Code exposes no persistent goal capability on this surface; do not
offer one.

## 2. Write the task body

Write `body.txt`: the smallest task-specific prompt for the selected
capability, derived from the exact source intent. Name the artifacts, paths,
and constraints the intent names; add nothing the intent does not ask for.
Do not add standing rules (assumptions, scope, verification, style): the CLI
renders those from its delta catalogs and records which ones it added. Do not
add the `/goal ` or other command prefix: the CLI adds the capability prefix.

## 3. Persist the candidate, then confirm natively

Before showing the chooser, persist the candidate so the record exists even if
the turn ends early:

1. Pick a nonce and, with the `Write` tool, create
   `.fab7/rf/tmp/stage-<nonce>/source.txt` containing exactly the source
   intent above, and `.fab7/rf/tmp/stage-<nonce>/body.txt` containing only
   the task body from section 2 (no frontmatter, explanation, or copy
   instructions). The CLI renders `prompt.txt` from it.
2. Run, via `Bash`, `ringframe ask compile --staged <that directory> --title
   "<short human title>" --capability native_plan|native_direct
   --classification '<json>' --route '<json>' --host
   '{"name":"claude-code","surface":"native-tui"}' --json`, with the
   vocabulary in section 4. Keep the returned `ask_id`. If it exits non-zero,
   show the error text and stop.

Then your first externally visible interaction is one `AskUserQuestion` call
with one single-select question:

- header: `Ask route`
- question: name the selected capability and why it fits, why the other route
  does not fit, the expected continuation and effects, and that the user may
  proceed, type a revision, choose the other route, or cancel.
- option `Proceed with Plan (Recommended)` (or `Proceed directly
  (Recommended)` when `native_direct` was selected): one sentence on what
  Claude Code will do next; put the complete rendered prompt in `preview`,
  obtained verbatim from `ringframe ask copy --ask <ask_id>` (the CLI rendered
  it from your body plus its catalogs; never retype or summarise it).
- option `Use direct execution` (or `Plan first`): the other route.
- option `Cancel`: nothing is activated or inspected.
- metadata source: `ringframe.ask`

Free text is a revision: compile the revised candidate again (a new
`ringframe ask compile` with `--link revises:<previous ask_id>`) and ask again.
Every candidate shown to the user is persisted; only the last one is confirmed.

## 4. Record the answer through the CLI

- Proceed: `ringframe ask confirm --ask <ask_id> --json`.
- Cancel: `ringframe ask cancel --ask <ask_id> --reason "<why>" --json`, then
  stop.

Vocabulary for `ringframe ask compile`: `--classification '<json>'` uses
exactly this vocabulary: `task` is a
   list from `question research clarify plan implement diagnose review operate
   document`; `result` is one of `answer plan workspace_change evidence
   continuing_objective`; `interaction` is `interactive` or `approval_gated`;
   `horizon` is `one_turn`, `session`, or `persistent`; `effects` is a list
   from `read write execute external_effect`. `--route '<json>'` with keys
   `fits`, `alternatives` (list of `{capability, reason}`), `continuation`,
   `effects`, `gaps` (list), and `explicit_direct_request` (boolean, true only
   when the source intent asks to skip planning or act immediately).
   `--classification` may also carry `concerns`: a list from `api_surface
   auth data_migration concurrency performance refactor dependency_change ui
   cli tests_only operate` naming what the intent touches; the CLI selects
   situational practice directives from it. Omit it when none applies. Do not
   guess a version or session id: the CLI takes both from the plugin hook's
   capture of this very invocation.

## 5. Deliver

- `native_plan`: call `EnterPlanMode`. The plugin's hook records the receipt.
  Then work inside Plan mode using the confirmed prompt as your brief; Claude
  Code owns research, the plan, `ExitPlanMode`, and what follows. If
  `EnterPlanMode` returns an error, run `ringframe ask delivery --ask <ask_id>
  --state delivery_failed --reason "<error>"`, then `ringframe ask delivery
  --ask <ask_id> --handoff` and show its output verbatim.
- `native_direct`: continue with the source intent under normal permissions.
  Record nothing else.
- Cancel: already recorded in section 4; stop.
