# RingFrame Ask

Ask is an explicit native-capability router and instruction optimizer.

It converts one user intent into an exact prompt for one qualified capability on
the active harness, asks the user to confirm it, persists the final prompt, and
then either dispatches it through a qualified native surface or presents it for
manual submission in the native TUI.

> RingFrame understands the harness. The harness understands the project. The
> user supplies and approves the intent.

~~~text
explicit Ask
  -> classify routing dimensions
  -> select and explain a native capability
  -> compile an exact prompt
  -> native confirmation
       -> revise: update the temporary candidate
       -> cancel: stop
       -> proceed: persist, then native dispatch or human handoff
~~~

# Status

This document defines the planned command. It does not claim an implemented or
qualified Ask adapter.

ACP, app-server, SDK, headless, and terminal-automation experiments do not define
Ask's product architecture. Ask is experienced through the harness's native
skill and TUI surfaces.

# Ownership boundary

| Responsibility | Owner |
| --- | --- |
| Preserve the exact source intent | RingFrame |
| Understand native commands, modes, activation, continuation, and limitations | RingFrame host profile |
| Select and explain a suitable native capability | RingFrame Ask router |
| Compile and persist the exact generated prompt | RingFrame compiler and ledger |
| Confirm one exact prompt digest | User or explicitly authorized policy |
| Dispatch through a qualified surface or present a handoff | RingFrame native adapter |
| Discover code, configuration, and project instructions | Native harness |
| Choose workflow, tools, agents, and execution sequence | Native harness |
| Manage memory, conversation, permissions, and effects | Native harness |
| Independently assess the resulting work | RingFrame Eval |

RingFrame does not maintain project or business memory. Its Ask artifacts are
transaction evidence for Eval and Seal, not knowledge to inject into later
conversations.

# User surface

The normal interface accepts plain language through an explicit native skill:

~~~text
/rf:ask research and implement authentication

$rf:ask research and implement authentication
~~~

The user does not need to provide a record ID, workflow name, native command, or
prompt template.

Ordinary messages never invoke Ask, create ledger events, or revise an earlier
Ask. The user can steer the harness normally between RingFrame commands.

# Inputs

Ask accepts:

- the exact source intent;
- the detected host, version, native surface, and workspace;
- the invoking actor and authority source;
- explicit outcome, constraints, forbidden effects, and preferences;
- desired acceptance evidence when stated;
- interactive or pre-authorized non-human confirmation mode; and
- an optional human-facing relationship to earlier work.

Free text is sufficient. The active harness may propose structured fields during
the explicit Ask turn, but the deterministic core validates what is persisted.

Ask never invents authority, project context, business context, technology,
permissions, or acceptance requirements. Material ambiguity is presented to an
interactive user or returns `needs_input` to a non-interactive caller.

# Host capability profile

Ask routes only among capabilities declared by the actual host profile. A
profile contains:

~~~text
host and observed version
native surface
capability identity and purpose
activation semantics
confirmation surface
delivery support
continuation after activation
possible effects and permission owner
observable receipts
qualification identity and limitations
~~~

The candidate set is provider-specific. Similar spellings such as `/plan`,
`/goal`, or `/review` do not establish equivalent behavior across hosts.
An unknown or changed host profile falls back conservatively and exposes its
qualification gap.

# Ask algorithm

Ask performs nine bounded operations.

## 1. Verify explicit invocation

The wrapper confirms that Ask was directly invoked and captures the actor,
workspace, worktree when applicable, native session reference when exposed, and
host profile.

## 2. Preserve the source intent

The exact UTF-8 user text remains authoritative. Classification and rendering
must not silently narrow, broaden, or replace it.

## 3. Classify only routing dimensions

Ask identifies only the dimensions required for capability selection:

~~~text
task: question | research | clarify | plan | implement | diagnose | review | operate
result: answer | plan | workspace_change | evidence | continuing_objective
interaction: interactive | approval_gated
horizon: one_turn | session | persistent
effects: read | write | execute | external_effect
~~~

This classification is not project analysis and does not create a RingFrame
workflow.

## 4. Select and explain one native capability

Ask evaluates the qualified candidates exposed by the active profile. Its route
explanation states:

- the selected capability and why it fits;
- plausible native alternatives and why they do not fit;
- expected continuation after approval;
- required effects that remain subject to native permissions; and
- qualification gaps or assumptions that could change the route.

The explanation is a classification evaluation, not RingFrame Eval. RingFrame
Eval checks an exact result only after one exists.

Ask does not route everything complex to planning. It selects planning when a
reviewable plan is a useful native boundary and the capability continues toward
the user's requested result. It selects a persistent goal only for a continuing
objective supported by the host. It may select direct native execution for a
clear bounded task, especially when the user explicitly requests immediate
execution.

## 5. Compile the smallest useful prompt

The compiler combines:

~~~text
exact source intent
+ selected native capability semantics
+ explicit constraints from this Ask
+ qualified host-specific instruction delta
+ observable acceptance framing
~~~

Potential deltas include:

- make material assumptions visible;
- preserve behavior outside the requested scope;
- prefer the smallest change consistent with the repository;
- make success conditions testable before material work; and
- leave observable verification for the requested result.

These are prompt requirements, not a RingFrame SDLC. RingFrame does not prescribe
research, design, implementation, review, or release phases. Instructions the
host already handles reliably are omitted.

Every added instruction must earn its place against both the untreated user
prompt and the raw native-capability baseline. More text is not inherently a
better prompt.

The prompt excludes invented context, reusable project memory, a RingFrame-owned
architecture, and a provider-neutral workflow.

## 6. Confirm the generated prompt

The native confirmation presents:

- a human title and source-intent summary;
- the selected capability and rejected alternatives;
- the expected continuation and effects;
- the complete generated prompt; and
- proceed, revise, alternative, and cancel actions.

Free-text editing or alternative selection updates the temporary candidate and
returns to confirmation. RingFrame does not retain every draft. The interaction
ends with one final candidate and either proceed or cancel.

No delivery occurs before confirmation.

## 7. Persist one Ask

When the confirmation interaction ends, the core creates:

~~~text
.fab7/rf/asks/<ask_id>/source.txt
.fab7/rf/asks/<ask_id>/prompt.txt
~~~

`source.txt` contains the exact source intent. `prompt.txt` contains only the
final generated native input for the selected host surface: no frontmatter,
debug output, explanation, or copy instructions.

Both files are UTF-8, byte-counted, SHA-256 digested, atomically published, and
then immutable. The core appends either `ask.confirmed` or `ask.cancelled` to
`.fab7/rf/ledger.jsonl` with both artifact references.

Every completed Ask has one `prompt.txt`, including a cancelled Ask and a direct
route whose best prompt is the unchanged source intent.

## 8. Deliver through the native adapter

The adapter selects one delivery mode:

| Mode | Behavior |
| --- | --- |
| `native_dispatch` | Use a qualified documented native surface after confirmation. |
| `human_handoff` | Show the exact prompt path and ask the user to submit its complete contents in the active TUI. |
| `unsupported` | Stop because no safe native rendering or delivery path exists. |

`native_dispatch` has two observable mechanisms:

| Mechanism | Meaning |
| --- | --- |
| `prompt_submit` | A documented native interface accepts the exact `prompt.txt` bytes as new input in the intended session. |
| `capability_activate` | A documented native tool activates the selected capability while the confirmed prompt is already part of the current Ask turn. |

For `prompt_submit`, the adapter must bind the submitted bytes to the confirmed
digest. For `capability_activate`, it records the tool, arguments, current
session reference, and receipt; it does not claim that the prompt was resubmitted
as a new user message.

A host may support one mechanism, both, or neither. Support is qualified for the
exact host, surface, adapter, and observable receipt. Model prose or a missing
error is not a receipt.

When neither mechanism is qualified, `human_handoff` is the normal safe
fallback:

~~~text
Prompt prepared for <harness capability>:
.fab7/rf/asks/<ask_id>/prompt.txt

Open the file, copy its complete contents, and submit them in the active
<harness> TUI.
~~~

The wrapper may expose the path as an openable local link. It does not open a
GUI, write to the clipboard, paste, or press Enter without separate user
authority.

The adapter must not substitute an ACP client, app server, SDK runner, headless
process, simulated keystrokes, or new session and claim that the current TUI
received the prompt.

## 9. Record only observable delivery

Ask records one outcome and, after confirmation, one delivery observation:

~~~text
confirmed -> ask.delivery: native_accepted | handoff_ready
                           | delivery_failed | unavailable
cancelled -> no delivery
~~~

For `handoff_ready`, submission remains `unobserved` unless a separately qualified
native observation later proves it. A user statement may be recorded as an
attributed human observation, never as host evidence.

`native_accepted` proves only that the qualified surface accepted the dispatch
or activation. It does not prove instruction following, execution, completion,
or outcome quality. Those require native observations and, ultimately, Eval
against an exact subject.

# Ask identity

One explicit Ask invocation receives one opaque `ask_id` and produces one final
prompt artifact. Changes made inside its confirmation interaction are temporary
and are not separate records.

A later explicit Ask receives a new `ask_id`, even when it changes earlier
work. Typed relationships connect it:

| Relationship | Meaning |
| --- | --- |
| `new` | Independent intent. |
| `revises` | Changes a material boundary from an earlier Ask. |
| `remediates` | Requests work in response to an Eval finding. |

No finalized prompt artifact is overwritten, and no mutable global “active Ask”
exists.

# Ask ledger events

The workspace ledger is defined by [the product contract](product.md). Ask
uses the following event payloads:

| Event | Required event-specific data |
| --- | --- |
| `ask.confirmed` | Source and prompt artifacts, classification, selected route, expected effects, confirming actor, and limitations |
| `ask.cancelled` | Source and final prompt artifacts, cancelling actor, and optional bounded reason |
| `ask.delivery` | Delivery mode, mechanism, state, adapter qualification, native receipt or handoff path, and limitations |

A representative confirmed event is:

~~~json
{
  "schema": "ringframe.ledger/1",
  "event_id": "evt_01...",
  "type": "ask.confirmed",
  "time": "2026-09-05T10:51:01Z",
  "id": "ask_01...",
  "actor": {
    "kind": "human",
    "id": "local-user"
  },
  "links": [],
  "data": {
    "title": "Authenticated health details",
    "classification": {
      "task": "plan",
      "result": "plan",
      "effects": ["workspace_read"]
    },
    "selected_capability": "native_plan",
    "delivery_mode": "native_dispatch",
    "host": {
      "name": "claude-code",
      "surface": "native-tui",
      "session_ref": "host-session-reference"
    },
    "source": {
      "role": "source_intent",
      "path": "asks/ask_01.../source.txt",
      "bytes": 42,
      "sha256": "..."
    },
    "prompt": {
      "role": "generated_prompt",
      "path": "asks/ask_01.../prompt.txt",
      "bytes": 216,
      "sha256": "..."
    }
  }
}
~~~

The JSONL event contains bounded metadata; it does not duplicate the prompt or
source bytes. Readers locate artifacts through the relative path and verify
their digest before use.

# Conversation and record resolution

Ask, Eval, and Seal are explicit operations embedded in an ordinary native
conversation. Valid sequences include:

~~~text
Ask -> native prompts -> Eval -> native fix prompt -> Eval

native prompt -> native prompt -> Eval

Ask -> native prompt -> Ask -> native prompts -> Eval -> Seal

Ask -> native prompts
~~~

When a later explicit command omits an ID, the wrapper resolves candidates in
this order:

1. a human reference in the current command;
2. an eligible record associated with the same native conversation;
3. a unique eligible record for the same workspace and worktree;
4. a native interactive chooser with title, intent, subject, and time; or
5. `needs_input` when interactive resolution is unavailable.

The newest global record is never selected merely because it is newest.
Conversation and workspace associations are UX hints, not proof that intervening
ordinary prompts preserved the intent.

If the next Eval detects a possible material change, it shows the proposed basis
and lets the user choose the earlier Ask, create a successor Ask, or supply an
explicit Eval contract. Users do not need to type opaque IDs in the interactive
happy path.

# Reference example

Source intent:

~~~text
research claude code, codex, antigravity harnesses, document the research about
those harnesses' capabilities as
docs/knowledge-base/harnesses/{harness}/capability.md
~~~

Classification:

~~~yaml
task: [research, document]
result: workspace_change
interaction: approval_gated
horizon: session
effects: [external_read, workspace_read, workspace_write]
~~~

Candidate evaluation:

| Candidate | Decision | Reason |
| --- | --- | --- |
| Qualified native plan | Select | The work is bounded but requires multi-source research and three exact workspace artifacts; a native review boundary can confirm the sourcing and file contract before writes. |
| Persistent native goal | Reject | The request has finite deliverables and no continuing terminal condition. |
| Direct native execution | Reject by default | It could complete the work, but it would omit the requested review boundary for an effectful task. |

The generated `prompt.txt` preserves the three requested documents and adds
only qualified sourcing, scope, uncertainty, and final-path verification
requirements. It asks the native plan capability to continue toward the files
rather than stop at a plan artifact.

After the user confirms the exact prompt, the adapter branches:

~~~text
qualified current-context activation
  -> activate native plan
  -> append ask.delivery with native_accepted only from its receipt

no qualified activation
  -> show the prompt.txt path
  -> append ask.delivery with handoff_ready
  -> user copies and submits it in the native TUI
  -> submission remains unobserved
~~~

The harness decides how to research, plan, use subagents, ask follow-up
questions, and write the documents. RingFrame owns only the confirmed prompt and
its delivery truth.

# Initial validation questions

Before implementation, probes must determine:

1. whether the ledger can atomically publish one source, generated prompt, and
   Ask outcome under concurrent invocations;
2. whether confirmation edits produce one correct final prompt without keeping
   unnecessary draft history;
3. whether classification selects the intended native capability and rejects
   plausible alternatives for the right reasons;
4. whether each instruction delta improves alignment over untreated and raw
   native-capability baselines;
5. which native surfaces can accept exact prompt bytes or activate a capability
   in the intended session after confirmation;
6. whether native receipts prove the narrowly claimed dispatch or activation;
7. whether unsupported or changed host profiles reliably downgrade to human
   handoff;
8. whether the handoff file is easy to open, contains only paste-ready input,
   and never implies observed submission;
9. whether proceed, free-text editing, alternative selection, and cancel create
   the correct final Ask and delivery records;
10. whether no-ID resolution remains correct with mixed ordinary prompts,
    repeated Asks, concurrent sessions, and worktrees;
11. whether records remain bounded and useful to Eval and Seal without becoming
    project memory; and
12. whether local privacy, Git-ignore, retention, and crash-recovery behavior
    fail safely.
