# Claude Code adapter

The `rf` plugin ships three explicit-only skills (`/rf:ask`, `/rf:eval`,
`/rf:seal`) and two hooks. Skills carry the routing rules and drive Claude
Code's native surfaces; they never write the ledger. The `ringframe` CLI does
every write.

~~~text
/rf:ask <intent>
  UserPromptSubmit hook -> ringframe sessions capture   (exact invocation bytes)
  skill: classify, compile, AskUserQuestion              (proceed / revise / other route / cancel)
  skill: Write source.txt + body.txt to .fab7/rf/tmp/stage-*/   (the task body only)
  skill: ringframe ask compile --staged ...              (renders prompt.txt = prefix + body + delta catalogs,
                                                          publishes artifacts, appends ask.compiled with
                                                          compiler provenance; source_verified = exact when
                                                          bytes match the capture)
  skill: AskUserQuestion answered -> ringframe ask confirm --ask | ask cancel --ask   (graded: observed by the skill)
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

Qualified host tuple: Claude Code 2.1.263 through the Agent SDK, Sonnet 5 at
low effort (`ringframe-ask-ledger-q07`, candidate `156a8bf`: three of three
attempts obtained the CLI-selected directives, composed one brief with a
labelled `Rules:` list (all eight supplied directives applied), persisted
the exact intent before the chooser, confirmed natively with the rendered
prompt as preview, entered Plan mode, and recorded the hook receipt with a
clean ledger; `compiler.source = composed` in all three). Predecessors q04, q05 and
q06 passed on earlier bytes. `EnterPlanMode` activation itself was first
qualified in `ringframe-ask-plan-q04`. Other host versions degrade to the
unknown profile and human handoff.
