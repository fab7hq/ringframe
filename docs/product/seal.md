# RingFrame Seal

Seal binds one fresh Eval on an unchanged subject to one authorized
disposition and writes a receipt. It records a decision; it merges, publishes,
deploys, and certifies nothing.

~~~text
/rf:seal [eval reference] accepted|rejected|deferred|abandoned

$rf:seal ...        (planned)
~~~

# Checks, all fail-closed

| code | check |
| --- | --- |
| `seal.eval_missing` | the Eval record exists and its ledger line is present |
| `seal.subject_changed` | the subject re-digests to the value recorded after the Eval ran |
| `seal.stale` | the Eval is younger than its definition's `freshness.max_age` |
| `seal.authority_missing` | an interactive human, or a valid authorization for a non-human actor |
| `seal.verdict_conflict` | `accepted` with a verdict other than `aligned` needs at least one `--acknowledge` |
| `seal.duplicate` | no earlier receipt for the same Eval and disposition |

Any failure appends `seal.refused` with the codes and writes no receipt. The
Eval verdict is copied onto the receipt unchanged even when the owner
knowingly accepts risk.

# Authority

An interactive human is authorized by being present. A non-human actor
(`agent:` or `policy:`) needs `.fab7/rf/authorizations/<actor_id>.json`
naming who granted it, the allowed dispositions, Eval verdicts, and subject
kinds, and an expiry.

# Receipt

`seals/<seal_id>.json` holds the Eval id, digest, and verdict; the subject
kind, reference, and digest; the disposition; acknowledged risks; the actor
and authority; the Eval's limitations plus Seal's own; and the time. The
ledger gets one `seal.created` line with a `seals` link to the Eval.

# Downstream

`ringframe seal check --seal <seal_id> --json` re-verifies the receipt, the
Eval record, and the subject now, and prints `fresh: true` or `false` with
codes. Exit `0` only when fresh. A gate that relies on a Seal reads it this
way.

# Command line

~~~text
ringframe seal create --eval <eval_id> --disposition <d> [--acknowledge <text>]... [--actor kind:id --authority preauthorized] --json
ringframe seal check --seal <seal_id> --json
~~~
