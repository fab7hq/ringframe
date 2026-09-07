---
name: eval
description: Evaluate one exact subject against a frozen contract derived from an Ask; record an attributed verdict.
argument-hint: [ask reference] [subject]
disable-model-invocation: true
allowed-tools: AskUserQuestion Write Bash(ringframe *) Bash(git rev-parse *)
---

You are running RingFrame Eval. Eval is read-only and independent: it checks
an exact subject against a definition frozen before evidence is collected.
Claude Code's own review is evidence with a source, never the verdict.

Reference (optional): `$ARGUMENTS`

Shell discipline: `Bash` is for `ringframe` only, exactly one plain
`ringframe …` command per call, plus `git rev-parse HEAD` for the subject. No
`&&`, `;`, pipes, `2>&1`, `head`, `cd`, `which`, or `claude --version`. Read
the command's JSON output directly; never page or filter it.

## 1. Resolve the Ask

Run `ringframe ask list --json` to see every Ask (id, title, outcome), then
`ringframe ask show --json --ask "<id or title>"` for the one the person means.
Exit 3 means several candidates: present them with `AskUserQuestion` and ask
the user to choose, or to supply an explicit contract file instead. Never pick
the newest because it is newest.

## 2. Draft the definition, facts first

Read the Ask's prompt with `ringframe ask copy --ask <ask_id>` (it prints
`prompt.txt`; never ask the user to paste it). Then run `ringframe eval
scaffold --subject-ref <HEAD sha> --title "<Ask title>" --ask <ask_id> --json`:
it returns a draft built from facts (the project's test command as `command`
evidence, the commit's changed paths as `scope.allowed_paths`, `artifact`
checks `deps_unchanged` and `scope_clean`). Start from that draft and refine
it into a JSON definition:

- `schema`: `ringframe.eval-definition/1`
- `requirements`: one per concrete obligation in the prompt, each `{id, text,
  required, evidence: [...]}` where evidence is `{"kind":"command","run":[...],
  "pass_when":{"exit_code":0}}` for checks the repository already trusts
  (tests, linters, path existence, digest equality) or
  `{"kind":"attributed","source":"human:local-user"}` for what only a person
  can confirm.
- evidence kinds, strongest first, and you use the strongest that can see the
  property: `command` (runs; give `origin`: `preexisting` for tests that
  existed before the change, `agent` for tests the change itself added,
  `person`/`hidden` for tests the user supplies), `artifact` (facts the CLI
  computes: `paths_present`, `deps_unchanged`, `scope_clean`,
  `marker_present`), `attributed` (the person's word) only for what no
  command or artifact can see, and say why in `text`.
- `scope.allowed_paths`: the paths the Ask allows the change to touch; the CLI
  measures commission drift against it.
- `forbidden_effects`: things the prompt said must not happen, same shape.
- `freshness`: `{"max_age": "PT24H"}` unless the user says otherwise.
- An Eval whose required requirements rest on the person's word alone is
  `attested`, not `aligned`; the CLI refuses to freeze a definition that runs
  nothing when the project declares tests (`--attested-only` records the
  exception).

Do not invent requirements the prompt did not state. Show the complete
definition in an `AskUserQuestion` (`Freeze and run` / `Revise` / `Cancel`).
Free text is a revision.

## 3. Freeze, then run

Subject: default to the current commit (`git rev-parse HEAD`, kind
`git_commit`) unless the user names a worktree, file set, or artifact.

1. `Write` the definition to `.fab7/rf/tmp/eval-<nonce>.json`.
2. `ringframe eval freeze --ask <ask_id> --subject-kind <kind> --subject-ref
   <ref> --definition @<file> --json` and keep `eval_id` and
   `definition.sha256`.
3. For each attributed requirement, ask the user for their observation and
   `Write` it as `{"requirement":"<id>","source":"human:local-user","scope":
   "...","time":"<now>","statement":"...","outcome":"pass|fail|indeterminate",
   "limitations":[]}` to `.fab7/rf/tmp/obs-<nonce>-<id>.json`.
4. `ringframe eval run --eval <eval_id> --definition-sha256 <sha> --observation
   @<file>... --json`.

Attributed evidence is the person's word, not yours. When a requirement's
evidence is `attributed`, ask the person with `AskUserQuestion` (options
`Pass`, `Fail`, `Indeterminate`, free text allowed) and record their answer
**verbatim** as the observation's `statement` and their chosen outcome as
`outcome`; if they only picked an option, the statement is that option's
label. Never write your own findings into an attributed observation and
never decide an attributed outcome yourself. What you noticed while reading
the code goes into your report as context, labelled as your review; it is
not evidence and it does not change the verdict.

## 4. Report

State the verdict (`aligned`, `drifted`, `incomplete`), each requirement's
status, forbidden effects observed, and the record path
`.fab7/rf/evals/<eval_id>.json` (the CLI wrote it; `ringframe eval list
--json` shows it). Give the `eval_id` explicitly so the person can seal it. Do not soften an
`incomplete` or `drifted` verdict. If the user wants to fix drift, that is
native work followed by a new Eval, optionally after a new `/rf:ask` linked
with `remediates`.
