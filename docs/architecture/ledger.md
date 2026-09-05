# Workspace ledger

Every RingFrame write lands under the consumer's worktree:

~~~text
.fab7/rf/
├── .gitignore        "*": the directory ignores itself
├── ledger.jsonl      append-only events, one canonical JSON object per line
├── lock              advisory flock taken only around the final append
├── asks/<ask_id>/    source.txt (exact intent), prompt.txt (one final prompt)
├── evals/<evl_id>.definition.json, <evl_id>.json
├── seals/<sel_id>.json
├── authorizations/   optional grants for non-human actors
├── sessions/<host>/<session>/   hook captures; prunable with `ringframe sessions prune`
└── tmp/              staging for atomic publish; garbage after a crash
~~~

The workspace root is the Git worktree root when one exists (`--workspace`
overrides). Artifacts are written to `tmp/`, fsynced, renamed into place, and
only then referenced from a ledger line that carries their byte count and
SHA-256. Final paths are never rewritten. `ringframe ledger verify` reports
torn tails, invalid lines, missing or tampered artifacts, unreferenced
artifacts, duplicate deliveries, and dangling links, and repairs nothing.

Event types: `ask.confirmed`, `ask.cancelled`, `ask.delivery`,
`eval.completed`, `seal.created`, `seal.refused`. Validation lives in
`core/ringframe/schema.py`; vocabularies are enumerated there.

Ids are `<prefix>_<26 Crockford base32 chars>` (48-bit millisecond time plus
80 random bits): `ask_`, `evt_`, `evl_`, `sel_`. They sort by creation time and
are never parsed for logic.

Resolution of "which record" without an id follows one order: explicit id or
unique title substring, same native session, unique record in the workspace,
otherwise a chooser (`needs_input`, exit 3). The newest record is never chosen
for being newest.
