# Claude Code adapter

The `rf` plugin provides `/rf:ask`, `/rf:eval`, and `/rf:seal` as explicit-only
skills. Skills call the `ringframe` CLI for record writes; hooks capture prompt
and Plan activation evidence. See the [README](../../README.md#claude-code)
for installation.

## Ask path

```mermaid
sequenceDiagram
    actor User
    participant Host as Claude Code
    participant Skill as Ask skill
    participant CLI as RingFrame CLI
    User->>Host: /rf:ask intent
    Host->>CLI: UserPromptSubmit capture
    Host->>Skill: Explicit invocation
    Skill->>CLI: Select directives and compile staged candidate
    CLI-->>Skill: Ask ID and stored prompt
    Skill->>User: AskUserQuestion with exact prompt
    alt Proceed with Plan
        Skill->>CLI: Record confirmation
        Skill->>Host: EnterPlanMode
        Host->>CLI: PostToolUse receipt
        Host->>User: Native planning and plan review
    else Proceed directly
        Skill->>CLI: Record confirmation
        Skill->>Host: Continue in the same turn
    else Cancel
        Skill->>CLI: Record cancellation
    end
```

Revisions compile a successor candidate and return to confirmation. Plan
activation records `native_accepted` only when the hook supplies its receipt;
it does not resubmit the prompt as a new user message. Direct continuation has
no delivery receipt. On activation error, the skill reports failure and offers
the stored prompt for manual handoff.

## Profile and limits

The [shipped profile](../../core/ringframe/profiles/claude-code.yaml) is selected
by host name `claude-code`, independently of its version. Its stable ID is
`claude-code`; the profile digest identifies the configuration, and captured
host versions remain provenance in the ledger. An unrecognized host uses the
`unknown` profile and its `human_handoff` capability.

Profile selection describes integration rules, not current tool availability.
The host must provide the native chooser and selected capability. RingFrame
sets no model pin or host-version window and does not claim support for every
past or future build or surface.

The Ask skill exposes Plan and direct execution. The profile also defines a
manual Goal route, which this skill does not offer. Both hooks exit 0 on errors;
missing hook evidence leaves source or delivery unverified.

## Earlier host evidence

The following historical results were reported from maintainer tests. Their
raw records are not published or included in this repository or package:

| Qualification | Artifact and surface | Reported scope |
| --- | --- | --- |
| `ringframe-ask-ledger-q07` | `156a8bf`; Claude Code 2.1.263 through Agent SDK; Sonnet 5, low | 3/3 composed Asks with audited Rules, native confirmation, Plan activation receipt, and clean ledger |
| `ringframe-loop-q05` | `007ac50`; same host/model surface | 3/3 two-Ask loops with the earlier Eval and Seal design |

The identifiers above are provenance labels, not paths users must resolve.
They do not qualify this candidate or establish native-TUI parity. Formal
qualification of the current candidate remains incomplete.
Prompt quality and improvement over a native baseline require separate evidence.
