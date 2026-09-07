# Codex adapter

Codex's Plan mode (`/plan`) and persistent goal (`/goal`) are entered by the
person; no model-callable transition exists. So on Codex every routed
capability except direct execution is `human_handoff`: RingFrame compiles and
confirms the prompt, the person submits it, and the plugin's prompt hook
observes that submission.

Prerequisites: `uv tool install ringframe`, then
`codex features enable default_mode_request_user_input` (the confirmation
tool outside Plan mode). Codex loads the plugin's bundled `hooks.json` but
runs the hook only after you trust it: open `/hooks` in Codex and trust the
`rf@ringframe` UserPromptSubmit hook (Codex records its hash under
`hooks.state` in `config.toml`). Until then submission stays `unobserved`.

~~~text
$rf:ask <intent>
  UserPromptSubmit hook -> ringframe sessions capture --host codex   (exact invocation bytes)
  skill: classify (task, result, effects, concerns); write source.txt + body.txt
  skill: ringframe ask compile --staged ...          (renders prompt.txt = "/plan " or "/goal " + body +
                                                      delta catalogs; refuses an over-long goal before any
                                                      write; ask.compiled records which deltas rendered)
  skill: request_user_input                          (Proceed / other route / Cancel; free text revises)
  skill: ringframe ask confirm --ask | ask cancel --ask   (graded: observed by the skill,
                                                      surface request_user_input)
  skill: ringframe ask delivery --ask <id> --handoff (ask.delivery handoff_ready; shows prompt.txt)
  person: pastes prompt.txt into the composer
  UserPromptSubmit hook -> ringframe sessions capture   (digest equals prompt.txt, with or without
                                                      its trailing newline -> ask.submission observed)
  Codex: Plan mode or goal under its own permissions
~~~

Observed Codex behaviours the adapter accounts for (TUI run card
`ringframe-ask-codex-tui-q01`, one human run on 0.153.4):

- Codex strips the slash command before `UserPromptSubmit` runs: pasting
  `/plan <text>` reaches the hook as `<text>`. The submission match therefore
  also accepts the compiled prompt without its capability prefix and records
  `match: host_prefix_stripped`.
- The `request_user_input` chooser can disappear on its own after a while in
  Default mode. The skill treats a missing answer as a cancel and never
  proceeds without a recorded answer; RingFrame records nothing for that Ask
  beyond `ask.compiled` and `ask.cancelled`. What Codex itself does after the
  dismissal is host behaviour outside RingFrame's control.
- Invoking `$rf:ask` twice with the same text within 30 minutes makes the
  session lookup ambiguous; RingFrame then verifies nothing, falls back to the
  unknown profile, and hands off without the `/plan ` prefix. Use one
  invocation per intent, or vary the text.

Profile `codex@0.153` (`core/ringframe/profiles/codex.yaml`) records the
feature prerequisite, the prompt prefixes, the goal length limit, and that
`native_direct` with write, execute, or external effects needs an explicit
request in the route.

Qualified host tuple: Codex CLI 0.153.4 through the app-server,
`gpt-5.6-terra` at low effort, plugin hook trusted, feature
`default_mode_request_user_input` enabled (`ringframe-ask-codex-q06`,
candidate `0cee135`: three of three attempts obtained the CLI-selected
directives, composed one brief, compiled the exact intent before the chooser,
confirmed through `request_user_input` with the rendered prompt, recorded a
`handoff_ready` delivery with no submission claim, clean ledger, no project
write; `compiler.source = composed` in all three). q05 passed on earlier
bytes; the TUI run card `ringframe-ask-codex-tui-q01` showed the paste path
end to end. Not covered: revision and cancel branches, prompt quality. Other
Codex versions degrade to the unknown profile and human handoff. Unit tests:
`core/tests/test_plugin.py`, `test_profiles.py`, `test_ask.py`,
`test_sessions.py`.
