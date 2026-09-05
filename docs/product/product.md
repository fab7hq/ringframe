# RingFrame

RingFrame is the **explicit intent and independent-assurance layer inside native
AI harnesses**.

> **Ask** turns intent into an exact native prompt. **Eval** checks an exact
> result. **Seal** records a decision when someone or something needs to rely on
> that result.

The native harness owns the conversation, model, tools, permissions, memory,
workflow, and execution. RingFrame owns the intent contract, generated prompt,
delivery observation, independent evaluation, and decision receipt.

# Status

RingFrame is a planned product. This document is its product authority. Host
bindings remain proposed until their exact implementation is qualified.

ACP clients, app-server frontends, SDK frontends, headless runners, and terminal
automation may be used for experiments. They are not the RingFrame product
surface or dependencies of its native integrations.

# Product contract

RingFrame provides three explicit commands:

| Command | Purpose | Durable result |
| --- | --- | --- |
| **Ask** | Select a host-native capability and compile one confirmed prompt. | Ask record and generated prompt |
| **Eval** | Evaluate one exact subject against an Ask or explicit contract. | Eval record and verdict |
| **Seal** | Bind a fresh Eval to an authorized disposition. | Seal receipt |

~~~text
Ask
  -> confirm prompt
  -> native dispatch or human handoff
  -> native harness work
  -> exact subject
  -> Eval
  -> optional Seal
~~~

Ask, Eval, and Seal are independent operations, not mandatory stages. Ordinary
conversation can occur before, between, and after them without activating
RingFrame.

# Ownership

RingFrame:

- preserves exact user intent;
- understands qualified native harness capabilities;
- selects and explains one route;
- generates and persists the exact prompt;
- records only observable delivery;
- evaluates an exact result independently; and
- records an authorized decision.

The native harness:

- discovers project and business context;
- chooses its workflow, tools, agents, and execution sequence;
- manages conversation, memory, permissions, and approvals; and
- performs all work and external effects.

RingFrame does not maintain project memory or impose a provider-neutral
workflow. Its workspace records connect Ask, Eval, and Seal; they are not
knowledge injected into future conversations.

# Native integration

Each harness exposes RingFrame through manual-only native skills:

| Surface | Ask | Eval | Seal |
| --- | --- | --- | --- |
| Claude Code | `/rf:ask ...` | `/rf:eval ...` | `/rf:seal ...` |
| Codex | `$rf:ask ...` | `$rf:eval ...` | `$rf:seal ...` |

Both wrappers are thin: they call the same `ringframe` command line for
every ledger write.

## Distribution

RingFrame ships as one PyPI distribution and one host plugin, both from the
`ringframe` repository:

~~~sh
uv tool install ringframe                       # the deterministic core and `ringframe` CLI
claude plugin marketplace add fab7hq/ringframe  # then: claude plugin install rf@ringframe
codex plugin marketplace add fab7hq/ringframe   # then: codex plugin add rf@ringframe
~~~

The CLI must be installed first; the `rf` plugin's skills and hooks invoke it
and do nothing useful without it. There is no separate marketplace repository.

Codex additionally requires `codex features enable
default_mode_request_user_input` so that the native `request_user_input`
confirmation is available outside Plan mode.

Each adapter uses only documented, qualified surfaces for that harness and
version. Similar names such as `/plan`, `/goal`, or `/review` do not imply
equivalent behavior across providers.

After Ask confirmation, the adapter has two normal delivery paths:

| Path | Behavior |
| --- | --- |
| `native_dispatch` | A qualified native surface submits the exact prompt or activates the selected capability in the current native context. |
| `human_handoff` | RingFrame shows the generated prompt file and asks the user to copy and submit it in the active TUI. |

If native dispatch is not qualified, RingFrame uses human handoff. It must not
silently substitute an ACP client, SDK, headless runner, simulated keystrokes,
or a new session and describe that as the current TUI.

Command-shaped assistant text is not activation evidence. Native acceptance is
not evidence that the harness followed the prompt or completed the work.

# Ask

Ask turns one explicit user intent into one confirmed native prompt:

1. preserve the exact source intent;
2. classify only what is needed for routing;
3. select and explain one qualified native capability;
4. generate the smallest useful host-specific prompt;
5. let the user proceed, edit, choose another route, or cancel;
6. persist the final source and prompt under one `ask_id`; and
7. after confirmation, dispatch natively or present a human handoff.

Edits inside the confirmation interaction are temporary. RingFrame keeps only
the final candidate. A later explicit Ask receives a new `ask_id` and may link
to the earlier Ask with `revises` or `remediates`.

Every completed Ask, including a cancelled Ask, retains its final generated
prompt. A direct route may produce a prompt identical to the source intent.

Ask never invents project context, business rules, authority, permissions, or
acceptance requirements.

Detailed behavior is defined in [Ask](ask.md).

# Eval

Eval checks one immutable subject against one Ask or explicit external contract.
A subject may be a commit, working-tree snapshot, file set, package, deployment,
dataset, report, or another digestible artifact.

Eval freezes its definition before collecting outcome-dependent evidence. Tests,
linters, native reviews, model graders, external systems, and humans can provide
evidence, but every observation retains its source, scope, time, and
limitations.

Each requirement is `covered-pass`, `covered-fail`, `uncovered`, or
`indeterminate`. The aggregate verdict is:

- `aligned` when all required evidence passes and forbidden effects are absent;
- `drifted` when evidence proves a material mismatch; or
- `incomplete` when identity, coverage, freshness, or reliability is
  insufficient.

Eval is read-only. Native self-review is evidence, not the RingFrame verdict.

Detailed behavior is defined in [Eval](eval.md).

# Seal

Seal binds one fresh Eval and unchanged subject to an authorized disposition:

~~~text
accepted | rejected | deferred | abandoned
~~~

The Eval verdict and disposition remain separate. Seal fails closed when the
subject changed, evidence is stale, or authority is missing.

Seal records a decision only. Merging, publishing, deployment, trading, and
other consequential effects remain with authorized external systems.

Detailed behavior is defined in [Seal](seal.md).

# Workspace ledger

Every RingFrame operation uses one local workspace directory:

~~~text
.fab7/rf/
├── ledger.jsonl
├── asks/
│   └── <ask_id>/
│       ├── source.txt
│       └── prompt.txt
├── evals/<eval_id>.json
└── seals/<seal_id>.json
~~~

One explicit Ask produces one `ask_id` and one final prompt. A later Ask is a
new record linked to the earlier one when needed.

`ledger.jsonl` is the append-only operation history. Each line has:

~~~text
schema
event_id
type
time
id
actor
links
data
~~~

The required event types are:

| Command | Events |
| --- | --- |
| Ask | `ask.confirmed` or `ask.cancelled`, followed by `ask.delivery` when a delivery outcome is observed |
| Eval | `eval.completed` |
| Seal | `seal.created` or `seal.refused` |

An Ask delivery records one of:

~~~text
native_accepted | handoff_ready | delivery_failed | unavailable
~~~

`handoff_ready` means the prompt file was shown; user submission remains
unobserved. If no `ask.delivery` line exists, RingFrame has no recorded delivery
outcome.

Ledger data contains the classification, selected capability, host context,
relationships, bounded observations, and artifact paths with SHA-256 digests.
The prompt itself stays in `prompt.txt` so it is easy to open and copy.

The core writes artifacts before appending their ledger reference and uses one
workspace lock for the final append. Finalized artifacts are immutable.

`.fab7/rf/` is local and Git-ignored by default. It excludes full conversations,
chain of thought, unrestricted tool logs, credentials, and reusable project
knowledge. Export and retention are explicit user or policy actions.

# Identity and resolution

IDs and digests provide reliable links but are not normal user input. A native
wrapper resolves the relevant Ask or Eval from:

1. an explicit human reference;
2. the same native conversation;
3. a unique eligible record in the same workspace or worktree; or
4. a human-readable chooser when several candidates remain.

There is no global “active Ask,” and RingFrame never selects the newest record
merely because it is newest. Ordinary prompts never modify the ledger.

# User workflow

## Interactive

~~~text
human invokes Ask
  -> confirms the generated prompt
  -> adapter dispatches or presents the prompt file
  -> human works and steers in the native harness
  -> human invokes Eval on an exact subject
       -> aligned: optionally Seal
       -> drifted or incomplete: continue native work, then Eval again
~~~

## Autonomous

A non-human caller may confirm and dispatch only when its identity, effects,
permissions, cost limits, evidence rules, and allowed dispositions were
authorized in advance. Otherwise RingFrame stops for input or presents a human
handoff.

RingFrame does not retry, repair, or loop the native harness. An authorized
external orchestrator may do so and record each new relationship.

# Product value

RingFrame provides durable linkage between:

1. user intent and a qualified host-native prompt;
2. confirmation and truthful delivery observation;
3. an exact result and independent evaluation; and
4. an evaluated result and an attributable decision.

# First product slice

The first slice delivers:

1. the workspace ledger and atomic writer;
2. manual-only Ask, Eval, and Seal skills;
3. one source and generated-prompt artifact per Ask;
4. one qualified native adapter with human handoff fallback;
5. one useful independent Eval; and
6. one Seal receipt consumed by a real downstream decision.

Continue only if probes show that prompt treatment improves the native baseline,
delivery claims remain truthful, Eval detects material drift, IDs stay out of
normal UX, records remain bounded, and adapters remain thin.
