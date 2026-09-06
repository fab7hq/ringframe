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

- `native_plan`: bounded, non-trivial work that requests material effects and
  benefits from reviewing an approach before those effects. Claude Code will
  enter Plan mode, research read-only, and present its native plan review.
- `native_direct`: a small clear task, or the user explicitly asks to skip the
  planning boundary. Work continues in this turn under normal permissions.

Claude Code exposes no persistent goal capability on this surface; do not
offer one.

## 2. Compile the prompt

Write the smallest useful prompt for the selected capability. Start from the
exact source intent. Add only instructions that earn their place against the
untreated prompt, choosing from: make material assumptions visible; preserve
behaviour outside the requested scope; prefer the smallest change consistent
with the repository; make success conditions testable before material work;
verify every requested path before completion; after plan approval, continue
to the requested artifacts instead of stopping at the plan. For research that
produces documents also: prefer current first-party sources, cite material
claims, mark unverified behaviour, expand finite path templates. Omit anything
Claude Code already does reliably.

## 3. Confirm natively

Your first externally visible action is one `AskUserQuestion` call with one
single-select question:

- header: `Ask route`
- question: name the selected capability and why it fits, why the other route
  does not fit, the expected continuation and effects, and that the user may
  proceed, type a revision, choose the other route, or cancel.
- option `Proceed with Plan (Recommended)` (or `Proceed directly
  (Recommended)` when `native_direct` was selected): one sentence on what
  Claude Code will do next; put the complete compiled prompt in `preview`.
- option `Use direct execution` (or `Plan first`): the other route.
- option `Cancel`: nothing is activated or inspected.
- metadata source: `ringframe.ask`

Free text is a revision: update the prompt without losing the source intent
and ask again. Drafts are not persisted.

## 4. Persist through the CLI

When the interaction ends with a final candidate:

1. Pick a nonce and, with the `Write` tool, create
   `.fab7/rf/tmp/stage-<nonce>/source.txt` containing exactly the source
   intent above, and `.fab7/rf/tmp/stage-<nonce>/prompt.txt` containing only
   the final prompt (no frontmatter, explanation, or copy instructions). For a
   cancelled Ask, `prompt.txt` is the last candidate.
2. Run, via `Bash`, `ringframe ask confirm` (or `ringframe ask cancel
   --reason "<why>"`) with `--staged <that directory>`, `--title "<short
   human title>"`, `--capability native_plan|native_direct`,
   `--classification '<json>'` with keys `task` (list), `result`,
   `interaction`, `horizon`, `effects` (list), `--route '<json>'` with keys
   `fits`, `alternatives` (list of `{capability, reason}`), `continuation`,
   `effects`, `gaps` (list), `--host '{"name":"claude-code","surface":"native-tui"}'`,
   and `--json`. Do not guess a version or session id: the CLI takes both from
   the plugin hook's capture of this very invocation.
3. If the command exits non-zero, show its error text and stop.

## 5. Deliver

- `native_plan`: call `EnterPlanMode`. The plugin's hook records the receipt.
  Then work inside Plan mode using the confirmed prompt as your brief; Claude
  Code owns research, the plan, `ExitPlanMode`, and what follows. If
  `EnterPlanMode` returns an error, run `ringframe ask delivery --ask <ask_id>
  --state delivery_failed --reason "<error>"`, then `ringframe ask delivery
  --ask <ask_id> --handoff` and show its output verbatim.
- `native_direct`: continue with the source intent under normal permissions.
  Record nothing else.
- Cancel: stop.
