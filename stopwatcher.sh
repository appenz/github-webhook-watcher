#!/bin/bash
# Shell script to stop the watcher service

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
uv run webhookclient/main.py --uninstall
