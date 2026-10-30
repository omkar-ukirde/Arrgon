#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# Activate virtual environment
if [ -d "$DIR/.venv" ]; then
    source "$DIR/.venv/bin/activate"
else
    echo "Creating virtual environment in $DIR/.venv..."
    python3 -m venv "$DIR/.venv"
    source "$DIR/.venv/bin/activate"
    pip install -r "$DIR/requirements.txt"
fi

# Optional custom workspace directory (defaults to ./my_coding_workspace)
export MCP_WORKSPACE_DIR="${MCP_WORKSPACE_DIR:-${1:-$DIR/my_coding_workspace}}"
export MCP_PORT="${MCP_PORT:-${2:-8000}}"
export MCP_HOST="${MCP_HOST:-127.0.0.1}"

echo "============================================================"
echo " Starting Local Coding Agent MCP Server"
echo " Workspace : $MCP_WORKSPACE_DIR"
echo " Host      : $MCP_HOST"
echo " Port      : $MCP_PORT"
echo " Endpoint  : http://$MCP_HOST:$MCP_PORT/mcp"
echo "============================================================"
echo " Connect Gemini Desktop App to:"
echo " URL: http://$MCP_HOST:$MCP_PORT/mcp"
echo "============================================================"

exec python3 "$DIR/mcp_coding_agent.py"
