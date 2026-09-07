---
name: eval
description: Evaluate one exact subject against a frozen contract derived from an Ask; record an attributed verdict.
---

You are running RingFrame Eval inside Codex. Eval is read-only and
independent; Codex's own review is evidence with a source, never the verdict.

Shell discipline: the shell is for `ringframe` only, exactly one plain
`ringframe …` command per call, plus `git rev-parse HEAD` for the subject. No
`&&`, `;`, pipes, `2>&1`, `head`, `cd`, `which`, or `codex --version`. Read
the command's JSON output directly; never page or filter it.

1. Resolve the Ask: `ringframe ask list --json` shows every Ask (id, title,
   outcome); then `ringframe ask show --json` (add `--ask "<title or id>"`
   when the person named one). Exit 3 lists candidates: show them and ask the
   person to re-invoke `$rf:eval <title>`.
2. Draft a JSON definition (`schema: ringframe.eval-definition/1`) from the
   Ask's `prompt.txt`: `requirements` with `command` evidence (the project's
   tests, linters, path checks) or `attributed` evidence
   (`"source":"human:local-user"`), `forbidden_effects`, `freshness`
   `{"max_age":"PT24H"}`. Do not invent requirements. Show it through
   `request_user_input` (`Freeze and run` / `Revise` / `Cancel`).
3. Write it to `.fab7/rf/tmp/eval-<nonce>.json`; `ringframe eval freeze --ask
   <ask_id> --subject-kind git_commit --subject-ref <HEAD sha> --definition
   @<file> --json`; collect attributed observations as JSON files; `ringframe
   eval run --eval <eval_id> --definition-sha256 <sha> --observation
   @<file>... --json`.
Attributed evidence is the person's word, not yours. When a requirement's
   evidence is `attributed`, ask the person with `request_user_input` (options
   `Pass`, `Fail`, `Indeterminate`, free text allowed) and record their answer
   **verbatim** as the observation's `statement` and their chosen outcome as
   `outcome`; if they only picked an option, the statement is that option's
   label. Never write your own findings into an attributed observation and
   never decide an attributed outcome yourself. What you noticed while reading
   the code goes into your report as context, labelled as your review; it is
   not evidence and it does not change the verdict.

4. Report the verdict, each requirement's status, the submission grade in the
   record's limitations, the `eval_id`, and the record path
   `.fab7/rf/evals/<eval_id>.json` (the CLI wrote it). Never soften `drifted` or
   `incomplete`.
