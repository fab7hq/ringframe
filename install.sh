#!/bin/sh
# Install or upgrade, then initialize the current user's RingFrame defaults.
set -eu

# Until a release that reads configuration from fab7hq/fab7 is published, install
# from main. Switch back to the published package when one exists.
if [ "$#" -eq 0 ]; then
    package="git+https://github.com/fab7hq/ringframe@main"
elif [ "$#" -eq 1 ] && [ "$1" = "--source" ]; then
    package=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
    if [ ! -f "$package/core/ringframe/cli.py" ]; then
        printf '%s\n' '--source requires a RingFrame source checkout.' >&2
        exit 1
    fi
else
    printf '%s\n' 'Usage: install.sh [--source]' >&2
    exit 1
fi
printf 'Installing RingFrame from %s\n' "$package"
uv tool install --upgrade --reinstall "$package"
"$(uv tool dir --bin)/ringframe" init --global
printf '\n%s\n' 'Now install the plugin for your harness from the Fab7 marketplace:'
printf '%s\n' '  Claude Code:  /plugin marketplace add fab7hq/fab7 && /plugin install rf@fab7'
printf '%s\n' '  Codex:        codex plugin marketplace add fab7hq/fab7 && codex plugin install rf@fab7' 
