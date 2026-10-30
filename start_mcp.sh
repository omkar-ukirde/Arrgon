#!/usr/bin/env bash
# ==============================================================================
# Arrgon MCP Server Launcher for Gemini Desktop App (Local MCP Mode)
# ==============================================================================
#
# Paste this file's full path into Gemini Desktop App's "Command" field:
#   /path/to/Arrgon/start_mcp.sh
#
# To point Arrgon to your project folder:
# 1. Pass as an argument:  /path/to/Arrgon/start_mcp.sh /path/to/project
# 2. Or create a .workspace file with your project path in this directory
# 3. Or set the MCP_WORKSPACE_DIR environment variable
# 4. Fallback defaults to: ~/my_coding_workspace
# ==============================================================================

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

LOCAL_WS_FILE="$DIR/.workspace"
SAVED_WS=""
if [ -f "$LOCAL_WS_FILE" ]; then
    SAVED_WS="$(cat "$LOCAL_WS_FILE" | tr -d '\r\n')"
fi

DEFAULT_WORKSPACE="${SAVED_WS:-${DEFAULT_WORKSPACE:-$HOME/my_coding_workspace}}"
TARGET_WORKSPACE="${1:-${MCP_WORKSPACE_DIR:-$DEFAULT_WORKSPACE}}"

# Optional logging for troubleshooting (kept in /tmp/arrgon.log)
LOG="/tmp/arrgon.log"
echo "=== Arrgon Launched: $(date) ===" > "$LOG"
echo "Workspace: $TARGET_WORKSPACE" >> "$LOG"

export MCP_WORKSPACE_DIR="$TARGET_WORKSPACE"
exec "$DIR/.venv/bin/python3" "$DIR/mcp_coding_agent.py" "$TARGET_WORKSPACE" 2>>"$LOG"
