# Claude Code adapter

The `rf` plugin ships three explicit-only skills (`/rf:ask`, `/rf:eval`,
`/rf:seal`) and two hooks. Skills carry the routing rules and drive Claude
Code's native surfaces; they never write the ledger. The `ringframe` CLI does
every write.

~~~text
/rf:ask <intent>
  UserPromptSubmit hook -> ringframe sessions capture   (exact invocation bytes)
  skill: classify, compile, AskUserQuestion              (proceed / revise / other route / cancel)
  skill: Write source.txt + prompt.txt to .fab7/rf/tmp/stage-*/
  skill: ringframe ask confirm --staged ...              (publishes artifacts, appends ask.confirmed,
                                                          source_verified = exact when bytes match the capture)
  skill: EnterPlanMode
  PostToolUse hook -> ringframe ask delivery --from-hook (appends ask.delivery native_accepted from the receipt)
  Claude Code: research, plan, ExitPlanMode, implementation under its own permissions
~~~

Delivery is recorded only from the hook's receipt. If the hook does not fire,
no `ask.delivery` line exists and RingFrame has no recorded delivery outcome.
Direct execution records a confirmed Ask and no delivery, because no native
receipt exists for same-turn continuation. Any error from `EnterPlanMode`
downgrades to `delivery_failed` plus a human handoff that names the prompt
file and never implies the prompt was submitted.

Qualified host tuple for `native_plan`: Claude Code 2.1.260 through the Agent
SDK (`ringframe-ask-plan-q04`), with one native TUI feasibility observation.
Other versions degrade to the unknown profile and human handoff.
