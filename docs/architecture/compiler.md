# Compiler: delta catalogs

`ringframe ask compile` renders the prompt it hands to a native capability:

~~~text
prompt.txt = <capability prompt_prefix> + body.txt + host deltas (host, capability) + practice deltas (classification)
~~~

The skill writes `source.txt` (the exact intent) and `body.txt` (the smallest
task-specific prompt derived from it). The CLI adds the rest deterministically
and records what it added in `ask.compiled.data.compiler`: the catalog digests,
the selected entry ids, the matched concerns, and anything dropped by the
budget. Staging `prompt.txt` directly is still accepted for hosts without a
catalog; then `compiler.source` is `prompt`.

Two catalogs, all YAML:

| Catalog | Where | Keyed by | Renders by default |
| --- | --- | --- | --- |
| host deltas | `core/ringframe/deltas/<host>.yaml` | host, capability | only `qualified` entries; every shipped entry is a `candidate` until a probabilistic advantage evaluation on that stratum passes |
| practice deltas | `core/ringframe/deltas/practice/software-development.yaml`, overridden by `~/.fab7/rf/deltas.yaml` then `<workspace>/.fab7/rf/deltas.yaml` | classification `task`, `result`, `effects`, `concerns` | `attributed` and `qualified` entries |

Practice entries are semantic directives organised by software-engineering
law; the rendered text never names or explains a principle. Selection is
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
