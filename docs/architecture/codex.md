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
  skill: classify, compile; prompt.txt starts with "/plan " or "/goal " (goal <= 4000 chars)
  skill: ringframe ask compile --staged ...          (ask.compiled; refuses a missing prefix or an
                                                      over-long goal before any write)
  skill: request_user_input                          (Proceed / other route / Cancel; free text revises)
  skill: ringframe ask confirm --ask | ask cancel --ask   (graded: observed by the skill,
                                                      surface request_user_input)
  skill: ringframe ask delivery --ask <id> --handoff (ask.delivery handoff_ready; shows prompt.txt)
  person: pastes prompt.txt into the composer
  UserPromptSubmit hook -> ringframe sessions capture   (digest equals prompt.txt, with or without
                                                      its trailing newline -> ask.submission observed)
  Codex: Plan mode or goal under its own permissions
~~~

Profile `codex@0.153` (`core/ringframe/profiles/codex.json`) records the
feature prerequisite, the prompt prefixes, the goal length limit, and that
`native_direct` with write, execute, or external effects needs an explicit
request in the route.

Status: implemented and covered by unit tests (`core/tests/test_plugin.py`,
`test_profiles.py`, `test_ask.py`, `test_sessions.py`), **not qualified**.
Confirmed without model calls on codex-cli 0.153.4: the plugin installs from
this repository's marketplace, the three skills are listed, and the bundled
hook is discovered (untrusted until trusted). Still open for the Codex
qualification: whether `request_user_input` is available to the skill with the
feature enabled, and whether the `$rf:ask` invocation reaches the hook with the
exact bytes. Until that qualification passes, treat Codex as unsupported and
expect human handoff with unobserved submission.
