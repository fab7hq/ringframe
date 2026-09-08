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

1. Run `ringframe deltas render --host codex --capability <id>
   --classification '<json>' --json` with the classification below. The CLI
   selects the directives that apply to this Ask (`host.entries`,
   `practice.entries`); you never choose, drop, or add rules.
2. Under the project workspace root (the current working directory), never
   under this skill's directory, write `.fab7/rf/tmp/stage-<nonce>/source.txt` (exact intent) and
   `.fab7/rf/tmp/stage-<nonce>/composed.txt` in two parts. First, one brief
   for this task, the way a senior engineer briefs a peer: start from the
   exact intent and name the artifacts, paths, and constraints it names; add
   nothing else. Then a line `Rules:` followed by one line per supplied
   directive you apply: `- <label>: <that directive applied to this task's
   specifics>`, using the `label` values the CLI returned (several labels may
   share one line when one sentence applies them together). Every label must
   come from the supplied set; the CLI refuses unknown labels and records
   which supplied directives you applied or omitted. Do not restate a
   directive generically or explain a principle. Do not add the `/plan ` or
   `/goal ` prefix: the CLI adds it.
3. Only after both files exist, run one command:
   `ringframe ask compile --staged <dir> --title "<short title>"
   --capability <id> --classification '<json>' --route '<json>' --host
   '{"name":"codex","surface":"native-tui"}' --json`. Keep the returned
   `ask_id`. If it exits non-zero, read the `error` and `detail`, fix that one
   thing, and run it again; never run `--help`.

   `--classification` has exactly these keys and shapes (lists stay lists,
   strings stay strings):

   ~~~json
   {"task": ["implement"], "result": "workspace_change", "interaction": "approval_gated", "horizon": "session", "effects": ["write"], "concerns": ["api_surface"]}
   ~~~

   `concerns` is optional: a list from `api_surface auth data_migration
   concurrency performance refactor dependency_change ui cli tests_only
   operate` naming what the intent touches; omit it when none applies.

   `task` items from `question research clarify plan implement diagnose review
   operate document`; `result` one of `answer plan workspace_change evidence
   continuing_objective`; `interaction` one of `interactive approval_gated`;
   `horizon` one of `one_turn session persistent`; `effects` items from `read
   write execute external_effect`.

   `--route` has exactly these keys:

   ~~~json
   {"fits": "<why this capability fits>", "alternatives": [{"capability": "native_direct", "reason": "<why not>"}], "continuation": "<what happens after confirmation>", "effects": "<effects in words>", "gaps": [], "explicit_direct_request": false}
   ~~~

## 3. Confirm with the native tool

First run `ringframe ask copy --ask <ask_id>` to obtain the rendered prompt
verbatim (the CLI rendered it from the staged candidate; never retype
or summarise it). Then call `request_user_input` with one question, `id:
"route"`, whose text names the selected capability, why it fits, why the
alternatives do not, what will happen next, and includes that complete
rendered prompt. Options: `Proceed
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
- No answer (the chooser was dismissed, timed out, or returned nothing):
  `ringframe ask cancel --ask <ask_id> --reason "chooser dismissed" --json`,
  tell the person the Ask was cancelled, and stop. Never continue with the
  intent, plan, or hand off without a recorded answer.

Submission is `observed` only when the prompt hook matches the compiled input.
`ringframe ask submitted --ask <ask_id>` records the person's attestation as
`attributed`, not host-observed submission.
