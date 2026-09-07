# Compiler: delta catalogs

The CLI selects; the model composes (default); the CLI can also render
(baseline). Three staged forms, always `source.txt` plus one of:

| Staged file | Who phrases the directives | `compiler.source` |
| --- | --- | --- |
| `composed.txt` (default) | the skill, after `ringframe deltas render --json` returned the selected directives (`id`, `label`, `text`), writes the task brief followed by `Rules:` and one `- <labels>: <directive applied to this task>` line per applied directive; the CLI adds the prefix, audits every label against the supplied set, and records `applied` and `omitted` | `composed` |
| `body.txt` (baseline) | the CLI appends `Rules:` with one `- <label>: <directive>` line per selected entry, verbatim | `body` |
| `prompt.txt` (legacy) | the model wrote everything | `prompt` |

In every form the CLI adds the capability prefix, enforces the length limit,
validates `concerns` before any write, and records in
`ask.compiled.data.compiler` the catalog digests, the selected entry ids
(recomputed from the classification, never taken from the model), the matched
concerns, and anything dropped by the budget.

Two catalogs, all YAML:

| Catalog | Where | Keyed by | Renders by default |
| --- | --- | --- | --- |
| host deltas | `core/ringframe/deltas/<host>.yaml` | host, capability | only `qualified` entries; every shipped entry is a `candidate` until a probabilistic advantage evaluation on that stratum passes |
| practice deltas | `core/ringframe/deltas/practice/software-development.yaml`, overridden by `~/.fab7/rf/deltas.yaml` then `<workspace>/.fab7/rf/deltas.yaml` | classification `task`, `result`, `effects`, `concerns` | `attributed` and `qualified` entries |

Practice entries are semantic directives organised by software-engineering
law; each carries a short `label` (KISS, Hyrum, Boy Scout) that appears only
as the traceability tag of its `Rules:` line, never as an explanation. Selection is
tiered: `core` entries render on task match (capped, `render.core_cap`),
`situational` entries only when a classified concern matches, `reference`
entries never. Overrides replace fields by entry id (`text`, `enabled`,
`applies_to`, `tier`, `concerns`) or add new ids.

~~~sh
ringframe deltas list --host codex --capability native_goal --json
ringframe deltas list --effective --json          # merged practice set with the layer each line came from
ringframe deltas render --host codex --host-version "codex-cli 0.153.4" --capability native_plan \
  --classification '{"task":["implement"],"result":"workspace_change","interaction":"approval_gated","horizon":"session","effects":["write"],"concerns":["api_surface"]}'
~~~

No delta carries a check: whether the work has the property a directive asks
for is `rf:eval`'s question. Design: `plans/ringframe/adr/0008` in the fab7
planning tree; identities are digests of each document's canonical JSON.
