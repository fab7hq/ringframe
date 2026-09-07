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

1. Resolve the Ask: `ringframe ask show --json` (add `--ask "<title or id>"`
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
4. Report the verdict, each requirement's status, the submission grade in the
   record's limitations, and the record path. Never soften `drifted` or
   `incomplete`.
