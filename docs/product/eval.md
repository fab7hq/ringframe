# RingFrame Eval

Eval independently evaluates one exact subject against a definition frozen
before any outcome-dependent evidence is collected. It is read-only. The
harness's own self-review is evidence with a source, never the verdict.

~~~text
/rf:eval [ask reference] [subject]

$rf:eval [ask reference] [subject]        (planned)
~~~

# Subject

One immutable, digestible thing:

| kind | reference | digest |
| --- | --- | --- |
| `git_commit` | commit id | tree hash of the commit |
| `worktree` | absolute root | SHA-256 over sorted path, mode, and content digest of tracked and untracked non-ignored files |
| `file_set` | comma-separated globs | SHA-256 over sorted path and content digests |
| `artifact` | file path | SHA-256 of the file |

The digest is taken before evidence collection and again after. A change
between the two makes the verdict `incomplete` regardless of evidence.

# Definition

A JSON document, frozen with `ringframe eval freeze` before anything runs:

~~~json
{
  "schema": "ringframe.eval-definition/1",
  "requirements": [
    { "id": "R1", "text": "tests pass", "required": true,
      "evidence": [ { "kind": "command", "run": ["uv", "run", "pytest"], "pass_when": { "exit_code": 0 } } ] },
    { "id": "R2", "text": "a person agrees the behaviour matches", "required": true,
      "evidence": [ { "kind": "attributed", "source": "human:local-user" } ] }
  ],
  "forbidden_effects": [
    { "id": "F1", "text": "no ledger tracked by Git",
      "evidence": [ { "kind": "command", "run": ["sh", "-c", "test -z \"$(git ls-files .fab7)\""], "pass_when": { "exit_code": 0 } } ] }
  ],
  "freshness": { "max_age": "PT24H" }
}
~~~

`command` evidence is run by the CLI in the subject root; commands are
caller-chosen and RingFrame does not judge them. `attributed` evidence is
supplied, not produced: an observation document naming `requirement`,
`source`, `scope`, `time`, `statement`, `outcome`, and `limitations`. The
native harness's review enters only this way, with a `native-review:` source.

Freezing writes `evals/<eval_id>.definition.json` and returns the id and
digest. `eval run` refuses a definition whose bytes changed.

# Verdict

Each requirement is `covered-pass`, `covered-fail`, `uncovered`, or
`indeterminate` (a command that timed out or could not start). The verdict is
computed, never judged:

- `aligned`: every required requirement and every forbidden-effect check is
  `covered-pass`, and the subject digest is unchanged;
- `drifted`: any required requirement or forbidden-effect check is
  `covered-fail`;
- `incomplete`: anything else, including a subject that changed during the run.

Missing evidence never becomes success.

# Record

`evals/<eval_id>.json` holds the basis (Ask id and prompt digest, or an
explicit contract), the definition reference and digest, the subject with
both digests, every requirement with its evidence and status, the verdict,
freshness, and limitations. The ledger gets one `eval.completed` line with an
`evaluates` link to the Ask when there is one.

# Command line

~~~text
ringframe eval freeze --ask <ask_id> | --contract <file> --subject-kind <kind> --subject-ref <ref> --definition @<file> --json
ringframe eval run --eval <eval_id> [--definition-sha256 <hex>] [--observation @<file>]... --json
~~~

# Planned

Model graders, calibration and disagreement handling, and comparison against
an untreated native baseline inside Eval wait until a frozen comparison shows
the Ask treatment beats the untreated prompt on the same task and stratum.


## Listing

`ringframe eval list --json` enumerates every Eval in the workspace (frozen or
completed) with id, state, verdict, basis Ask, subject, and record path. Seal
chooses from this list; nothing else enumerates Evals.
