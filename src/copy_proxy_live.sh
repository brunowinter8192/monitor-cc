#!/bin/bash

# INFRASTRUCTURE
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ORCHESTRATOR
copy_proxy_live_workflow() {
    _require_args "$@"
    _copy_shim "$1"
    _copy_package "$2"
}

# FUNCTIONS
_require_args() {
    if [ "$#" -ne 2 ]; then
        echo "usage: copy_proxy_live.sh <live_addon_path> <live_dir_path>" >&2
        exit 2
    fi
}

_copy_shim() {
    cp "$SCRIPT_DIR/proxy_addon.py" "$1"
}

_copy_package() {
    mkdir -p "$1/src"
    cp "$SCRIPT_DIR/__init__.py" "$SCRIPT_DIR/constants.py" "$SCRIPT_DIR/monitor_root.py" "$1/src/"
    cp -r "$SCRIPT_DIR/proxy" "$1/src/"
}

copy_proxy_live_workflow "$@"
