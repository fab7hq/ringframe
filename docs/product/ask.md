# Ask

Ask turns an explicit intent into a prompt for a native host capability. The
skill proposes the route and wording; the CLI validates and stores the
candidate before the user confirms it.

| Claude Code | Codex |
| --- | --- |
| `/rf:ask <intent>` | `$rf:ask <intent>` |

```mermaid
flowchart TD
    I[Explicit intent] --> R[Classify and select capability]
    R --> P[Compose and persist candidate]
    P --> C{User confirmation}
    C -->|Revise or change route| N[Compile successor linked by revises]
    N --> C
    C -->|Cancel| X[Record cancellation]
    C -->|Proceed| A[Record confirmation]
    A --> D[Activate capability, continue directly, or hand off]
    D --> O[Record available delivery or submission evidence]
```

## Routing and compilation

Classify only the task, result, interaction, horizon, effects, and optional
concerns needed for routing. Preserve the user's constraints without inventing
project context, permissions, or acceptance requirements.

The shipped skills prefer `native_plan` for work with effects and
`native_direct` for read-only work or an explicit request to act immediately.
The CLI requires `route.explicit_direct_request=true` for direct execution with
specified write, execute, or external effects; the skill supplies that assertion.
Codex also offers `native_goal` for a continuing objective. Host profiles define
capabilities and delivery modes; unavailable capabilities are refused.

The [compiler](../architecture/compiler.md) selects directives. The skill
composes a task brief with labelled `Rules:` lines, then stages `source.txt`
and `composed.txt`. The CLI publishes `source.txt` and `prompt.txt`, records
byte counts and SHA-256 digests, and appends `ask.compiled`.

Each compile creates a new `ask_id`, including revisions shown in the chooser.
Revisions link to the previous Ask with `revises`; remediation can link to an
Eval with `remediates`. Published candidates are never overwritten.

## Confirmation and delivery

The chooser presents the complete stored prompt, route, continuation, and
expected effects. Proceed records `ask.confirmed`; cancel records
`ask.cancelled`. Confirmation is reported by the skill, not independently
verified by the CLI. Unanswered candidates can remain compiled but unconfirmed.

| Observation | Meaning |
| --- | --- |
| `native_accepted` | A hook receipt records native capability acceptance. |
| `handoff_ready` | The prompt is available for the user to submit. |
| `delivery_failed` / `unavailable` | Delivery failed or is unavailable. |
| No delivery event | No recorded delivery outcome; includes direct continuation. |
| Submission `observed` | A prompt hook matched the compiled input. |
| Submission `attributed` | A caller attested submission with `ask submitted`. |

Source verification requires a matching captured Ask in the resolved session;
comparison tolerates one final newline. Missing or ambiguous captures leave
`source_verified` as `unverified`. Submission matching also supports a dropped
trailing newline or host-stripped capability prefix and records the match type.
None of these observations proves execution, completion, or prompt quality.

See [Claude Code](../architecture/claude-code.md) and
[Codex](../architecture/codex.md) for their distinct delivery paths.

## Inspect records

```sh
ringframe ask list --json
ringframe ask show --ask <ask_id> --json
ringframe ask copy --ask <ask_id>
```

`ask copy` prints the exact prompt. Without an ID, `ask show` resolves a unique
record using session or workspace context; ambiguity returns `needs_input`
(exit 3). Explicit references may use an ID or unique title substring. The CLI
does not choose a record merely because it is newest.
