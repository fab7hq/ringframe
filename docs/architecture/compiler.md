# Prompt compiler

The CLI selects instruction deltas from YAML catalogs; the skill composes them
into a task brief. Every candidate stages `source.txt` plus exactly one form:

| File | Processing | `compiler.source` |
| --- | --- | --- |
| `composed.txt` | Add the capability prefix; audit labelled `Rules:` lines against supplied directives. | `composed` |
| `body.txt` | Add the prefix and append selected directives verbatim. | `body` |
| `prompt.txt` | Preserve the supplied complete prompt; validate any required prefix. | `prompt` |

`composed.txt` is the shipped skills' default; `body.txt` is a rendering baseline;
`prompt.txt` is the legacy input. All forms validate concerns and capability
length limits. Only the composed and body forms record catalog selection
provenance; legacy input records `compiler.source` alone.

## Catalogs

| Catalog | Selection | Default inclusion |
| --- | --- | --- |
| `core/ringframe/deltas/<host>.yaml` | Host and capability | `qualified` entries |
| `core/ringframe/deltas/practice/software-development.yaml` | Task, result, effects, concerns | `attributed` and `qualified` entries |

Practice configuration layers are the shipped catalog, then
`~/.fab7/rf/deltas.yaml`, then `<workspace>/.fab7/rf/deltas.yaml`. Overrides
replace fields by entry ID or add new IDs.

Practice entries have a label and tier: `core` uses task matching and a cap;
`situational` also requires a matching concern; `reference` never renders.
Composed `Rules:` lines use the supplied labels, such as KISS, as traceability
tags. The CLI audits labels and records applied and omitted directives; it does
not judge whether the wording correctly applies the rule.

## Inspect and trace

```sh
ringframe deltas list --effective --json
ringframe deltas render --host codex --capability native_plan \
  --classification '{"task":["implement"],"result":"workspace_change","interaction":"approval_gated","horizon":"session","effects":["write"],"concerns":["api_surface"]}' --json
```

`ask.compiled.data.compiler` records catalog digests, selected IDs, matching
concerns, and budget omissions for rendered forms. Composed input also records
applied and omitted IDs. Catalog identities hash canonical JSON parsed from YAML.

Shipped host deltas remain candidates and are excluded by default. Candidate
text and successful composition alone do not establish improvement over the
native prompt baseline. [Eval](../product/eval.md) judges the resulting work.
