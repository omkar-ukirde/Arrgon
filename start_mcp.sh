#!/usr/bin/env bash
# ==============================================================================
# Arrgon MCP Server Launcher for Gemini Desktop App (Local MCP Mode)
# ==============================================================================
#
# Paste this file's full path into Gemini Desktop App's "Command" field:
#   /Users/omkar/GeminiAppMCP/start_mcp.sh
#
# To point Arrgon to a specific project folder:
# 1. Edit DEFAULT_WORKSPACE below, OR
# 2. Pass it as an argument: /Users/omkar/GeminiAppMCP/start_mcp.sh /path/to/project
# ==============================================================================

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

DEFAULT_WORKSPACE="/Users/omkar/GeminiAppMCP"
TARGET_WORKSPACE="${1:-${MCP_WORKSPACE_DIR:-$DEFAULT_WORKSPACE}}"

# Optional logging for troubleshooting (kept in /tmp/arrgon.log)
LOG="/tmp/arrgon.log"
echo "=== Arrgon Launched: $(date) ===" > "$LOG"
echo "Workspace: $TARGET_WORKSPACE" >> "$LOG"

export MCP_WORKSPACE_DIR="$TARGET_WORKSPACE"
exec "$DIR/.venv/bin/python3" "$DIR/mcp_coding_agent.py" "$TARGET_WORKSPACE" 2>>"$LOG"
