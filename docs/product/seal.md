# RingFrame Seal

Seal is the person's decision to close the open Asks. It records the latest
Eval over them as a fact and writes a receipt. It merges, publishes, deploys,
and certifies nothing, and no Eval verdict blocks it.

~~~text
/rf:seal accepted|rejected|deferred|abandoned [note]
$rf:seal accepted|rejected|deferred|abandoned [note]
~~~

# Basis

Every open Ask. After the Seal they are closed: the next Eval and the next
Seal start from this Seal's subject.

# Refusals

| code | check |
| --- | --- |
| `seal.no_open_ask` | there is at least one open Ask to close |
| `seal.eval_missing` | an `--eval` named explicitly exists and is completed |
| `seal.eval_unrelated` | an `--eval` named explicitly judged at least one of the open Asks |
| `seal.authority_missing` | an interactive human, or a valid authorization for a non-human actor |

A refusal appends `seal.refused` with the codes and writes no receipt.
Everything else is a recorded fact, not a refusal: the Eval's verdict and
confidence, whether the subject still matches the Eval's subject, the Eval's
age, or the absence of any Eval.

# Authority

An interactive human is authorized by being present. A non-human actor
(`agent:` or `policy:`) needs `.fab7/rf/authorizations/<actor_id>.json`
naming who granted it, the allowed dispositions and subject kinds, and an
expiry.

# Receipt

`seals/<seal_id>.json` holds the basis (Ask ids and titles); the Eval fact
(`eval_id`, `verdict`, `confidence`, record digest, `subject_matches`,
`age_s`) or `null`; the subject kind, reference, and digest now; the
disposition; the person's `note` verbatim when given; the actor and
authority; limitations; and the time. The ledger gets one `seal.created` line
with `seals` links to each Ask and to the Eval.

# Downstream

`ringframe seal check --seal <seal_id> --json` re-verifies the receipt and the
Eval record digests and reports `fresh`, the disposition, the basis, the Eval
fact, and `subject_matches` now. Exit `0` when the receipt is intact. A gate
that relies on a Seal reads these facts and decides for itself.

# Command line

~~~text
ringframe seal create --disposition <d> [--eval <eval_id>] [--note <text>] [--actor kind:id --authority preauthorized] --json
ringframe seal check --seal <seal_id> --json
~~~
