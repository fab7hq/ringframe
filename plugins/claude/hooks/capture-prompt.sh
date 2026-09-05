#!/bin/sh
# UserPromptSubmit: store the exact bytes of a /rf: invocation so `ringframe ask confirm`
# can verify the source intent. Never blocks or alters the turn; silent without the CLI.
command -v ringframe >/dev/null 2>&1 || exit 0
ringframe sessions capture --host claude-code --json >/dev/null 2>&1
exit 0
