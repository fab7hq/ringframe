---
name: eval
description: Judge the work against every open Ask with independent sub-agents; record a verdict with its confidence. Asks nothing.
argument-hint: (no arguments in the common case)
disable-model-invocation: true
allowed-tools: Agent Read Write Bash(ringframe *) Bash(git *)
---

You are running RingFrame Eval. Eval judges the work done so far against
every open Ask in this workspace and records a verdict with a confidence. It
asks the person nothing, runs none of the project's commands, and gates
nothing: the person decides what to do with the result.

Shell discipline: `Bash` is for `ringframe` only, exactly one plain
`ringframe …` command per call. No `&&`, `;`, pipes, `2>&1`, `head`, `cd`,
`which`, or `claude --version`. Read the command's JSON output directly;
never page or filter it. Judges read files with `Read` and the repository
with `git` read commands (`git diff`, `git show`, `git log`); nobody edits.

## 1. Open

Run `ringframe eval open --json`. Keep `eval_id`, `brief_path`, and
`brief.sha256`. The brief lists the open Asks in order (each with its
`prompt_path` under `.fab7/rf/`), the anchor commit, the subject, the changed
files with line counts, and how many unrecorded prompts followed each Ask.
Exit 2 `eval.no_open_ask`: report "nothing to evaluate: no open Ask" and
stop. Exit 3 `eval.anchor_unknown`: report it and stop; the person can pass
`--anchor <commit>` next time.

## 2. Intent (one sub-agent)

Spawn one `Agent` (read-only; give it `brief_path` and `brief.sha256`) with
this task: read the brief and each Ask's `prompt.txt` in order; write the
effective intent as numbered items, one obligation each, in the Asks' own
words; when a later Ask changes an earlier obligation mark the earlier one
`revised` (with the new text as a new `active` item) or `withdrawn` naming
`by_ask_id`; never add an obligation no Ask states; unconfirmed Asks are
context, not obligations. It writes `.fab7/rf/tmp/eval-<eval_id>-intent.json`:

~~~json
{"schema":"ringframe.eval-intent/1","brief_sha256":"<brief.sha256>",
 "judge":{"host":"claude-code","model":"<your model id>","angle":"intent","independence":"sub_agent"},
 "items":[{"id":"i1","text":"...","ask_id":"ask_...","status":"active|revised|withdrawn","by_ask_id":"ask_...","note":"..."}]}
~~~

## 3. Assessors (three sub-agents, in parallel)

Spawn three `Agent`s at once, read-only, each with `brief_path`,
`brief.sha256`, the intent file path, and one angle. Each reads the brief,
the intent, and the change between the anchor and the subject (`git diff
<anchor> <subject>` or `git diff <anchor>` for the worktree, plus `Read` of
the files as they are now), then writes
`.fab7/rf/tmp/eval-<eval_id>-<angle>.json`:

~~~json
{"schema":"ringframe.eval-judgement/1","brief_sha256":"<brief.sha256>",
 "judge":{"host":"claude-code","model":"<your model id>","angle":"<angle>","independence":"sub_agent"},
 "votes":[{"item":"i1","vote":"yes|no|unknown","reason":"names the files that show it"}],
 "drift":[{"path":"<changed path>","finding":"...","classification":"required|consequence|unexplained"}],
 "basis_notes":["an item that reads as two obligations, a misreading you suspect"],
 "commands_run":[]}
~~~

Every `active` item gets exactly one vote. Every judge, whatever its angle,
classifies every changed path in the brief (`required`, `consequence`, or
`unexplained`); the CLI refuses a judgement that leaves a path out. The
angles:

- `coverage`: for each active item, is it met by the change? `yes` only when
  you can point at the files; `unknown` when you cannot tell from the
  repository.
- `drift`: lead with the paths: is each change `required` by an item, a
  reasonable `consequence` of one, or `unexplained` by any Ask? Vote the
  items too, from what the diff shows.
- `adversary`: assume the work is wrong. For each active item look for the
  missing case, the wrong behaviour, the untested claim. Vote `no` only when
  you can point at the failure, else `unknown`; vote `yes` when you tried and
  found nothing.

Sub-agents do not write the ledger, do not edit files, and do not run the
project's build or tests; what they read is what they judge.

## 4. Close

Run `ringframe eval close --eval <eval_id> --intent @<intent file>
--judgement @<coverage file> --judgement @<drift file> --judgement
@<adversary file> --json`, once. If it reports an error, fix the one thing it
names (a missing vote, a bad classification) by asking that sub-agent to
correct its file, then run it again.

## 5. Report

One line first: `verdict` and `confidence`, then the item table (text,
majority, agreement, the three votes), the drift table (`omission` items;
`commission` paths with their agreement, beside the count of unrecorded
prompts that may explain them), `delta` since the previous Eval when there is
one, and the record path `.fab7/rf/evals/<eval_id>/record.json` with the
`eval_id`. Never soften `drifted` or `incomplete`, never present the verdict
as certain, and never ask the person anything. Fixing is native work or a new
`/rf:ask`, followed by `/rf:eval` again; `/rf:seal` closes the work whenever
the person decides.
