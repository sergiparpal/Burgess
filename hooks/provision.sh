#!/bin/sh
# Dev-convenience shim (review-r5): the SessionStart provisioning logic lives ONCE in
# hooks/provision.mjs — hooks.json invokes it directly, and Node is present wherever Claude Code
# runs. This file remains only so a developer can still run `sh hooks/provision.sh` by hand (and
# so the shipped hook layout stays stable for validate_plugin.py). Silent when node is absent:
# the MCP launcher provisions in the foreground on first server spawn.
exec node "$(dirname -- "$0")/provision.mjs" 2>/dev/null || exit 0
