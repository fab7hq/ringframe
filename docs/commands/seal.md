# Seal

Seal closes every open Ask with your decision and writes a receipt. Invoke
`/rf:seal <disposition> [note]` in Claude Code or
`$rf:seal <disposition> [note]` in Codex.

Dispositions: `accepted`, `rejected`, `deferred`, `abandoned`. Each closes the
Asks, including `deferred`. Seal does not merge, publish, deploy, or certify work.

## Decision and authority

The skill is instructed to confirm the disposition, open Ask titles, and Eval
summary once. The CLI records the supplied decision without independently
verifying that host interaction.
An optional note is recorded verbatim. The CLI defaults to the latest completed
Eval that shares at least one open Ask, or no Eval if none exists. The receipt
keeps the Eval ID so consumers can inspect its actual coverage.

An Eval verdict, its age, changed subject, or absence does not block Seal.
An interactive human actor is accepted as declared. Other actors need a local
`authorizations/<actor_id>.json` grant matching their identity, disposition,
and subject kind; an expiry is checked when supplied. These are caller-supplied
identities and local grants, not host authentication.

The [Claude skill](../../plugins/claude/skills/seal/SKILL.md) requests confirmation
with `AskUserQuestion`. The [Codex skill](../../plugins/codex/skills/seal/SKILL.md)
requires `request_user_input` and stops without creating a Seal if that tool is
missing, its call is rejected, or the chooser is cancelled or unanswered.

| Refusal code | Reason |
| --- | --- |
| `seal.no_open_ask` | Nothing to close. |
| `seal.eval_missing` | An explicitly named Eval is not completed or does not exist. |
| `seal.eval_unrelated` | An explicitly named Eval shares no open Ask. |
| `seal.authority_missing` | No matching authorization. |

These refusals append `seal.refused` and write no receipt. Invalid input or
storage errors can also fail through the CLI's standard error handling.

## Receipt and verification

`seals/<seal_id>.json` records Ask IDs and titles, the current subject, the
Eval fact (or `null`), disposition, note, actor, authority, limitations, and time.
The Eval fact includes its record digest, verdict, confidence, age, and whether
its subject matched at sealing. `seal.created` links the receipt to the Asks
and the Eval. Outside Git, the subject can be unknown.

```sh
ringframe seal create --disposition accepted --note "Reviewed locally" --json
ringframe seal check --seal <seal_id> --json
```

`seal check` verifies the receipt digest against the ledger and the referenced
Eval record digest. `fresh: true` and exit 0 mean those checks passed.
`subject_matches` separately compares the recorded subject with its current
digest. For a recorded Git commit, this checks that commit, not whether the
current `HEAD` or worktree equals it. Downstream gates must choose and check
their own acceptance conditions.

Implementation: [receipt creation and checks](../../core/ringframe/seal.py).
