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

1. Resolve the Ask. `ringframe ask list --json` shows every Ask (id, title,
   outcome); then `ringframe ask show --json --ask "<id or title>"` for the
   one the person means. When several Asks could be meant (exit 3, or the
   person named none and more than one exists), present them through
   `request_user_input` (one option per Ask, label = title) and let the
   person choose. Never pick the newest because it is newest, and never ask
   the person to re-invoke the skill instead of choosing.
2. Read the Ask's prompt with `ringframe ask copy --ask <ask_id>` (it prints
   `prompt.txt`; never ask the person to paste it and never read it through
   the shell). Then run `ringframe eval scaffold --subject-ref <HEAD sha>
   --title "<Ask title>" --ask <ask_id> --json`: a draft built from facts (the
   project's test command as `command` evidence, changed paths as
   `scope.allowed_paths`, `artifact` checks `deps_unchanged` and
   `scope_clean`). Refine it into the definition as JSON:
   - `schema`: `ringframe.eval-definition/1`
   - `requirements`: one per concrete obligation in the prompt, each
     `{"id","text","required","evidence":[...]}` where evidence is
     `{"kind":"command","run":[...],"pass_when":{"exit_code":0}}` for checks
     the repository already trusts (tests, linters, path existence) or
     `{"kind":"attributed","source":"human:local-user"}` for what only a
     person can confirm.
   - evidence kinds, strongest first; use the strongest that can see the
     property: `command` (give `origin`: `preexisting`, `agent` for tests the
     change added, `person`/`hidden`), `artifact` (`paths_present`,
     `deps_unchanged`, `scope_clean`, `marker_present`), `attributed` only for
     what no command or artifact can see, saying why in `text`.
   - `scope.allowed_paths`: the paths the Ask allows the change to touch.
   - `forbidden_effects`: things the prompt said must not happen, same shape.
   - `freshness`: `{"max_age":"PT24H"}` unless the person says otherwise.
   - An Eval whose required requirements rest on the person's word alone is
     `attested`, not `aligned`; the CLI refuses a definition that runs nothing
     when the project declares tests unless `--attested-only` is recorded.
   Do not invent requirements the prompt did not state. Show the complete
   definition through `request_user_input` (`Freeze and run (Recommended)` /
   `Revise` / `Cancel`). Free text is a revision.
3. Freeze, then run. Subject: the current commit (`git rev-parse HEAD`, kind
   `git_commit`) unless the person names a worktree, file set, or artifact.
   1. Write the definition to `.fab7/rf/tmp/eval-<nonce>.json` (under the
      workspace root, never under this skill's directory).
   2. `ringframe eval freeze --ask <ask_id> --subject-kind git_commit
      --subject-ref <sha> --definition @<file> --json`; keep `eval_id` and
      `definition.sha256`.
   3. For each attributed requirement, ask the person through
      `request_user_input` (options `Pass`, `Fail`, `Indeterminate`; free
      text allowed) and write exactly
      `{"requirement":"<id>","source":"human:local-user","scope":"<what they
      looked at>","time":"<now, ISO 8601>","statement":"<their answer,
      verbatim>","outcome":"pass|fail|indeterminate","limitations":[]}` to
      `.fab7/rf/tmp/obs-<nonce>-<id>.json`. One file per requirement.
   4. `ringframe eval run --eval <eval_id> --definition-sha256 <sha>
      --observation @<file>... --json`, once. If it reports an error, fix the
      one thing it names and run again; do not freeze a second definition.

   Attributed evidence is the person's word, not yours. Record their answer
   verbatim as `statement` and their chosen outcome as `outcome`; if they only
   picked an option, the statement is that option's label. Never write
   your own findings into an attributed observation and never decide an attributed
   outcome yourself. What you noticed while reading the code goes into your
   report as context, labelled as your review; it is not evidence and does
   not change the verdict.

4. Report the verdict, each requirement's status, the submission grade in the
   record's limitations, the `eval_id`, and the record path
   `.fab7/rf/evals/<eval_id>.json` (the CLI wrote it). Never soften `drifted` or
   `incomplete`.
