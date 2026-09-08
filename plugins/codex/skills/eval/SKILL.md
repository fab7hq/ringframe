---
name: eval
description: Judge the work against every open Ask with independent sub-agents; record a verdict with its confidence. Asks nothing.
---

You are running RingFrame Eval inside Codex. Eval judges the work done so far
against every open Ask in this workspace and records a verdict with a
confidence. It asks the person nothing, runs none of the project's commands,
and gates nothing: the person decides what to do with the result.

Shell discipline: the coordinator uses the shell for `ringframe` only:
exactly one plain `ringframe …` command per call. No `&&`, `;`, pipes,
`2>&1`, `head`, `cd`,
`which`, or `codex --version`. Read the command's JSON output directly; never
page or filter it. Judges read files with the file-reading tool and the
repository with `git` read commands (`git diff`, `git show`, `git log`).
Keep project files read-only; judges may write only their assigned output
files under `.fab7/rf/tmp/`. In the shared-context fallback, follow these
judge tool rules during each judge pass.

Delegation is part of this skill: use four native sub-agents, one intent
judge followed by three assessors. Use the exposed native tool
(`collaboration.spawn_agent` on current Codex). Give each child its task,
exact output schema below, input paths and assigned output path. While the
intent judge reads the Asks, inspect the brief and prepare the assessor tasks;
while assessors work, prepare the close command without reading their drafts.

Collect each command's completed result before interpreting it. In Codex code
mode, emit the entire awaited tool result with `text(...)`, including its
status and session ID. If `functions.exec` yields a cell ID, use
`functions.wait`; if `exec_command` returns a running `session_id`, poll it
with `write_stdin` and empty input until it exits, retaining every output.
An empty initial output is not a completed command or evidence that native
sub-agents are unavailable. Polling does not rerun `eval open`.

1. Open. Run `ringframe eval open --json`; keep `eval_id`, `brief_path`, and
   `brief.sha256`. The brief lists the open Asks in order (each with its
   `prompt_path`), the anchor commit, the subject, the changed files with line
   counts, and how many unrecorded prompts followed each Ask. Exit 2
   `eval.no_open_ask`: report "nothing to evaluate: no open Ask" and stop.
   Exit 3 `eval.anchor_unknown`: report it and stop. Exit 2 `eval.already_open`:
   an Eval over these Asks is open and unclosed; continue with the `eval_id`
   in `detail` and its brief under `.fab7/rf/evals/<eval_id>/brief.json`. Run
   `eval open` once per Eval.
2. Intent, one sub-agent. Spawn a sub-agent (project read-only) with `brief_path` and
   `brief.sha256`: read the brief and each Ask's `prompt.txt` in order; write
   the effective intent as numbered items, one obligation each, in the Asks'
   own words; when a later Ask changes an earlier obligation mark the earlier
   one `revised` (adding the new text as a new `active` item) or `withdrawn`
   naming `by_ask_id`; never add an obligation no Ask states; unconfirmed
   Asks are context, not obligations. When the brief lists `previous_evals`,
   read the latest one's `intent.json` under `.fab7/rf/evals/<eval_id>/`
   first and keep its item ids and wording for unchanged obligations, so the
   delta can match them. It writes
   `.fab7/rf/tmp/eval-<eval_id>-intent.json` (under the workspace root):
   `{"schema":"ringframe.eval-intent/1","brief_sha256":"<brief.sha256>",
   "judge":{"host":"codex","model":"<model id>","angle":"intent","independence":"sub_agent"},
   "items":[{"id":"i1","text":"...","ask_id":"ask_...","status":"active|revised|withdrawn","by_ask_id":"...","note":"..."}]}`.
3. Assessors, three sub-agents spawned together; wait for all three to
   finish before closing the Eval. Their project access is read-only,
   each told to read files with the file tool, run one plain `git …` command
   per shell call, and write only its own file; each with `brief_path`,
   `brief.sha256`, the intent file path, and one angle. Each reads the brief,
   the intent, and the change between the anchor and the subject (`git diff
   <anchor> <subject>`, or `git diff <anchor>` for the worktree, plus the
   files as they are now) and writes `.fab7/rf/tmp/eval-<eval_id>-<angle>.json`:
   `{"schema":"ringframe.eval-judgement/1","brief_sha256":"<brief.sha256>",
   "judge":{"host":"codex","model":"<model id>","angle":"<angle>","independence":"sub_agent"},
   "votes":[{"item":"i1","vote":"yes|no|unknown","reason":"names the files"}],
   "drift":[{"path":"<changed path>","finding":"...","classification":"required|consequence|unexplained"}],
   "basis_notes":[],"commands_run":[]}`. Every `active` item gets exactly one
   vote; every judge, whatever its angle, classifies every changed path in
   the brief (the CLI refuses a judgement that leaves one out). Angles:
   - `coverage`: is each active item met by the change? `yes` only when you
     can point at the files; `unknown` when the repository cannot tell you.
   - `drift`: lead with the paths: is each `required` by an item, a
     reasonable `consequence` of one, or `unexplained` by any Ask? Vote the
     items too.
   - `adversary`: assume the work is wrong; for each active item look for the
     missing case, the wrong behaviour, the untested claim. `no` only when you
     can point at the failure, else `unknown`; `yes` when you tried and found
     nothing.
   Use the fallback only if the native tool is absent or returns an explicit
   unavailability error; record that limitation. Run the four passes yourself, one
   after another, each from a fresh reading of the files, and set
   `"independence":"shared_context"` in every file; the record will say so.
   Sub-agents do not write the ledger, do not edit project files, and do not run the
   project's build or tests.
4. Close. `ringframe eval close --eval <eval_id> --intent @<intent file>
   --judgement @<coverage file> --judgement @<drift file> --judgement
   @<adversary file> --json`, once. On an error, fix the one thing it names by
   having that sub-agent correct its file, then run it again.
5. Report: one line with `verdict` and `confidence`; the item table (text,
   majority, agreement, votes); the drift table (`omission` items,
   `commission` paths with agreement beside the unrecorded-prompt count that
   may explain them); `delta` since the previous Eval when present; the
   `eval_id` and record path `.fab7/rf/evals/<eval_id>/record.json`. Never
   soften `drifted` or `incomplete`, never present the verdict as certain, and
   never ask the person anything. Fixing is native work or a new `$rf:ask`,
   then `$rf:eval` again; `$rf:seal` closes the work whenever the person
   decides.
