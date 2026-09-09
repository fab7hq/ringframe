#!/bin/sh
# Install or upgrade, then initialize the current user's RingFrame defaults.
set -eu

if [ "$#" -eq 0 ]; then
    package=ringframe
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
