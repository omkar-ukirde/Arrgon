#!/usr/bin/env bash
# Arrgon MCP Launcher — paste this script's full path into Gemini Desktop App's "Command" field.
# It activates the venv and starts the MCP server in stdio mode.
#
# Usage in Gemini Desktop App Command field:
#   /Users/omkar/GeminiAppMCP/start_mcp.sh
#
# To change the workspace, edit WORKSPACE_DIR below:

WORKSPACE_DIR="/Users/omkar/Astrology"

# ── Do not edit below ──
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export MCP_WORKSPACE_DIR="$WORKSPACE_DIR"
exec "$DIR/.venv/bin/python3" "$DIR/mcp_coding_agent.py" "$WORKSPACE_DIR"

