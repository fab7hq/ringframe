# Delta configuration and extension

Deltas are standing instructions that Ask selects from YAML and adapts to the
user's task. Use practice deltas for engineering preferences shared across
harnesses, and host deltas for instructions tied to one native capability.
Profiles define available capability routes; deltas do not add routes or tools.
The [compiler](compiler.md) owns prompt composition and provenance.

## Files and scopes

| Catalog | Global file | Project file |
| --- | --- | --- |
| Practices | `~/.fab7/rf/deltas/practice/software-development.yaml` | `.fab7/rf/deltas/practice/software-development.yaml` |
| Claude Code | `~/.fab7/rf/deltas/claude-code.yaml` | `.fab7/rf/deltas/claude-code.yaml` |
| Codex | `~/.fab7/rf/deltas/codex.yaml` | `.fab7/rf/deltas/codex.yaml` |

The installer or `ringframe init --global` seeds missing global files from the
package. A delta read also initializes missing global catalogs. Existing files
are preserved, including during upgrades; they are not silently refreshed with
new packaged defaults. Run `ringframe init` from a consumer project to create
its matching, initially empty files. First use also initializes them.

Configuration is read on each CLI invocation. Profiles remain package-owned;
Ask/Eval/Seal records share `.fab7/rf/` with the project delta catalogs.
Only the paths above are read; legacy configuration layouts are not migrated.

Extend the existing catalogs. Dropping an arbitrarily named YAML file into the
directory does not register a new host, domain, or selection rule. The shipped
Ask workflow uses the `software-development` practice domain.

Use block-style mappings with two-space indentation and compact lists for short
vocabularies, as in the examples below. Project files are partial overrides of
the same catalog structure.

## Merge rules

The CLI merges the global file with the matching project file. Project fields
win conflicts; this is configuration precedence, not rendering priority.

| Project value | Result |
| --- | --- |
| Empty or comment-only file | Inherit the complete global catalog. |
| Mapping | Merge recursively; project fields override matching global fields. |
| Nonempty list of entries keyed by `id` | Merge matching entries; append new IDs. |
| Other list or scalar | Replace the global value. |
| `entries: []` | Clear all entries in this catalog. |
| Entry with `enabled: false` | Keep the entry configured but exclude it from rendering. |

An override can contain only the fields you change. Keep IDs unique and stable.
Updating an existing ID retains its position in the merged catalog; a new
project ID is appended after global entries. Restoring an empty project file
restores inheritance. Use `[]` to clear a list; YAML `null` is not an empty list.

For example, change KISS and disable YAGNI in one project:

```yaml
entries:
  - id: practice.kiss
    text: Keep changes small and direct.
  - id: practice.yagni
    enabled: false
```

## Practice catalog

A complete global practice catalog has this shape. A project override inherits
the header and only needs the fields it changes.

```yaml
schema: ringframe.deltas/1
scope: practice
domain: software-development
render:
  heading: 'Rules:'
  core_cap: 5
concerns: [api_surface, refactor, tests_only]
entries:
  - id: practice.task_workflow
    label: Task workflow
    status: attributed
    tier: core
    priority: 10
    applies_to:
      task: [plan, implement]
    text: >-
      For each implementation task, analyze the existing code and acceptance
      criteria; write a failing test, implement the smallest passing change,
      and refactor; then review the diff and resolve findings before advancing.
      In a plan, describe this sequence for each task without executing it.
      In a continuing goal, repeat it until the stated completion criteria
      are met. Use appropriate checks for non-code tasks.
```

To add this rule to a project, copy only the `entries` section into its practice
file. Combine it with other overrides in a single `entries` list.

| Entry field | Meaning and default |
| --- | --- |
| `id` | Required stable identifier; used for merging and provenance. |
| `text` | Required instruction text; write a concrete action. |
| `applies_to` | Required mapping of classification filters; `{}` matches any classification. |
| `label` | Short Rules label. Falls back to `principle`, then the final component of `id`. Use distinct labels without commas, colons, or ` and `. |
| `principle` | Optional descriptive name and alternative audit label. |
| `enabled` | Only the boolean `false` disables an entry. |
| `status` | Defaults to `attributed`; see selection below. |
| `tier` | `core`, `situational` (default), or `reference`. |
| `priority` | Numeric sort order, default `100`; lower values render earlier within a tier. |
| `concerns` | List of concern names; a situational entry needs at least one match. |
| `requires.host_capability` | Currently recognizes `subagents`; excludes the entry when the profile does not declare sub-agent support. This does not prove the tool is exposed. |

`render` supports only `heading` and `core_cap`, shown above. Keep `heading` as
`Rules:` for the shipped composed-prompt workflow; its audit expects that heading.
`core_cap` defaults to `5`; use a nonnegative integer. It caps core entries only,
not situational or host rules.

Metadata such as `source`, `why`, and `evidence` describes a rule but does not
run a check or change practice matching.

### Classification filters

`applies_to` supports three optional lists. Populated filters must all match;
within each list, one matching value is enough. Missing or empty filters impose
no restriction.

| Filter | Values used by Ask |
| --- | --- |
| `task` | `question`, `research`, `clarify`, `plan`, `implement`, `diagnose`, `review`, `operate`, `document` |
| `result` | `answer`, `plan`, `workspace_change`, `evidence`, `continuing_objective` |
| `effects` | `read`, `write`, `execute`, `external_effect` |

For example, `task: [plan, implement]` means plan **or** implement. Adding
`result: [continuing_objective]` also requires that result. `interaction` and
`horizon` guide routing but are not delta filters. Use `result` when targeting
a continuing objective; there is no `task: goal` classification.

Situational rules additionally match the classification's `concerns`. The
catalog's top-level `concerns` is the vocabulary Ask can use. Adding a custom
concern in a project replaces that vocabulary list, so include the existing
names you still need. A situational rule with no matching concern is not
selected, even if its task matches.

### Selection, priority, and budgets

For practice entries the CLI:

1. Excludes disabled entries, ineligible statuses, nonmatching filters, and
   unsupported `requires.host_capability: subagents` entries.
2. Groups eligible entries into core and matching situational rules. Reference
   rules never render.
3. Sorts each group by ascending `priority`, then merged catalog order for ties.
4. Keeps at most `core_cap` ordinary core rules, followed by eligible
   situational rules. Host directives are rendered separately before practices.

A project override wins a field conflict regardless of priority. A **new**
project rule still competes with global core rules for the cap. For example,
with a cap of five and five earlier matching global rules at priority `100`, a
new project core rule at `100` is omitted. Giving it `10` selects it earlier
and can displace the last global rule. Raising the cap keeps more rules but
also lengthens the prompt. Inspect `dropped_by_budget` before assuming a rule
will reach Ask.

Practice statuses `attributed` and `qualified` are eligible by default;
`candidate` and `retired` are excluded. A personal rule can use `attributed`;
`qualified` is a declared metadata value, not a test performed by the CLI.

For isolated evaluation, `deltas render --statuses qualified,candidate` also
includes candidate practice entries. Candidate core rules are appended beyond
the ordinary core cap so experiments can add them without displacing defaults.
This flag also includes candidate **host** rules. Ordinary `ask compile`
recomputes its rules with the default status filter; changing a standalone
render command does not enable candidate rules in the shipped Ask workflow.

## Host catalog

Host entries match a profile capability exactly, rather than practice task
filters. A full host catalog has this structure:

```yaml
schema: ringframe.deltas/1
scope: host
host: claude-code
entries:
  - id: claude-code.native_goal.task_workflow
    label: Task workflow
    status: candidate
    capability: native_goal
    text: >-
      For each task, analyze the code, implement using TDD, and review the
      change before advancing toward the goal's completion criteria.
    matrix_ref: https://code.claude.com/docs/en/goal
```

To extend a project catalog, copy only its `entries` section. Use `host: codex`
and Codex capability IDs when authoring a full Codex catalog.

Each host entry requires `id`, `capability`, `text`, `matrix_ref`, and `status`.
`label` is optional and defaults to the final component of `id`; `enabled: false`
excludes the entry. Valid statuses are `candidate`, `qualified`, and `retired`;
only `qualified` renders by default. The shipped host entries are candidates.
Optional `why` and `evidence` fields describe provenance, not executable checks.

Host entries retain merged catalog order. Practice fields such as `priority`,
`tier`, `applies_to`, and `concerns` do not control host selection. `matrix_ref`
is descriptive provenance; the CLI does not fetch it or check the linked page.
Use the profile's capability IDs from `ringframe profile show`, not a new ID
invented in the delta file.

## Inspect and preview

Run these from the consumer project whose overrides you want to inspect:

```sh
ringframe deltas list --effective --json
ringframe deltas list --host claude-code --json
ringframe profile show --host claude-code --json
ringframe deltas render --host claude-code --capability native_plan   --classification '{"task":["plan"],"result":"plan","interaction":"approval_gated","horizon":"session","effects":["read"]}' --json
```

For a Goal preview, use `--capability native_goal` and a classification with
`task: [implement]`, `result: continuing_objective`, `horizon: persistent`,
and the intended effects. These are previews; they do not launch a native
capability. `list --effective` reports merged practice entries and the last
scope that contributed to each entry, not the final selected set.

The render output exposes `practice.selected`, `practice.dropped_by_budget`,
`practice.entries`, `host.entries`, matching concerns, and catalog digests.
Composed Ask records also report applied and omitted IDs. A selected rule can
still be omitted or poorly applied during model composition; inspect the
stored prompt rather than treating selection as proof of behavior.

| Symptom | Check |
| --- | --- |
| Project entry has no effect | Current workspace, exact catalog filename, and matching entry ID. |
| Entry is listed but not rendered | Status, enabled flag, filters, tier, concerns, and budget. |
| New rule unexpectedly loses to defaults | Equal priorities retain global-first merged order. |
| Unknown concern error | The merged top-level concern vocabulary. |
| Rule renders but does not affect the prompt | Applied/omitted IDs and the composed Rules wording. |
| Rule is present but the agent skips a step | Native behavior and execution evidence; deltas provide instructions, not enforcement. |

Deltas guide how the native agent plans and works. [Eval](../commands/eval.md)
compares the resulting diff with effective intent; it does not audit whether
the agent followed the prescribed implementation sequence. Use a separate
experiment to evaluate whether a delta produces the intended guidance or
behavior.

Thresholds and LLM-judge rubrics belong in the experiment definition. The delta
format does not implement fuzzy scoring, test execution, or automatic review
gates. See [LLM verification](../../LLM_VERIFICATION.md) when evaluating those
behaviors. Source: [selection](../../core/ringframe/deltas.py) and
[merging](../../core/ringframe/config.py).
