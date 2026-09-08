# RingFrame Eval

Eval judges the work done so far against every open Ask in the workspace and
records a verdict with its confidence. Facts are recorded exactly by the CLI;
the verdict is a judgement by independent sub-agents of the eval skill. Eval
asks the person nothing, runs none of the project's commands, knows nothing
about the project's stack, and gates nothing.

~~~text
/rf:eval
$rf:eval
~~~

# Basis

Every open Ask, in confirmation order. An Ask is open from `ask.compiled`
until a Seal names it in its basis; cancelled Asks are never open. Later Asks
may revise or withdraw obligations of earlier ones; the *effective intent*
after those revisions is judged, never declared by the CLI. Plain prompts are
never stored; the brief counts how many unrecorded prompts followed each Ask
so that changes no Ask explains can be labelled honestly.

# Anchor and subject

The anchor is the commit the work is measured from: the subject of the last
Seal in the workspace, else the commit recorded when the earliest open Ask
was compiled (`ask.compiled` records `base_commit`), else `--anchor`. The
subject is `HEAD` when the tree is clean, else the worktree.

| kind | reference | digest |
| --- | --- | --- |
| `git_commit` | commit id | tree hash of the commit |
| `worktree` | absolute root | SHA-256 over sorted path, mode, and content digest of tracked and untracked non-ignored files |

# Brief

`ringframe eval open` writes `evals/<eval_id>/brief.json`
(`ringframe.eval-brief/1`): the open Asks with their prompt paths and
unrecorded-prompt counts, the anchor, the subject with its digest, the changed
files with line counts, the previous Evals over the same Asks, and
limitations. The brief names no command, runner, manifest, or framework.

# Judgement

The eval skill spawns one *intent* sub-agent that turns the Asks into numbered
items (`active`, `revised`, `withdrawn`, each traced to its Ask), then three
read-only *assessor* sub-agents with distinct angles (`coverage`, `drift`,
`adversary`). Each assessor votes `yes | no | unknown` per active item with a
reason and classifies every changed path as `required`, `consequence`, or
`unexplained`. Their files (`ringframe.eval-intent/1`,
`ringframe.eval-judgement/1`) name the host, the model when known, the angle,
and `independence: sub_agent | shared_context`.

`ringframe eval close` validates them (at least three judgements bound to the
brief's digest, one vote per active item, one classification per changed
path from every judge) and aggregates:

- per item: majority vote and agreement (share of judges in the majority);
- per path: majority classification and agreement; paths no judge mentioned
  are listed as `unmentioned`;
- `verdict`: `aligned` when every active item has a `yes` majority and no
  path an `unexplained` majority; `drifted` when any item has a `no` majority
  or any path an `unexplained` majority; otherwise `incomplete` (ties,
  unknowns, no active item, or a subject that changed between open and close);
- `confidence`: the lowest agreement among the deciding questions;
- `drift.omission`: items without a `yes` majority; `drift.commission`: paths
  with an `unexplained` majority.

Disagreement is reported, never averaged away. No verdict is presented as
certain.

# Record

`evals/<eval_id>/record.json` (`ringframe.eval/1`) holds the basis, the
subject with its digest at open and at close, the brief, intent, and judgement
references with digests, the verdict and confidence, the item table with every
vote, the drift tables, `follows` (the previous Eval over the same Asks) with
a `delta` of what closed and opened, and limitations. The ledger gets
`eval.opened` and `eval.completed` lines with `evaluates` links to each Ask
and a `supersedes` link to the previous Eval.

# Command line

~~~text
ringframe eval open [--anchor <commit>] [--subject-kind git_commit|worktree --subject-ref <ref>] --json
ringframe eval close --eval <eval_id> --intent @<file> --judgement @<file> --judgement @<file> --judgement @<file> [--judgement @<file>]... --json
ringframe eval list --json
~~~

Refusals (exit 2): `eval.no_open_ask`, `eval.already_open` (an unclosed Eval
over the same Asks; its id is in the detail), `eval.no_git`, `eval.anchor_missing`,
`eval.too_few_judges`, `eval.brief_mismatch`, `eval.intent`,
`eval.judgement`, `eval.missing`, `ledger.immutable`. Exit 3
`eval.anchor_unknown` when no Seal and no Ask provide an anchor.

# What Eval refuses to do

Run, detect, or name any project command; store plain-prompt text; ask the
person anything; author intent items the Asks do not state; present a verdict
without its confidence; block a Seal.
