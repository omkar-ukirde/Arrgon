# Local Coding Agent MCP Server (Production Streamable HTTP)

A production-ready Local MCP Server built on the official Model Context Protocol (MCP) Python SDK, bound strictly to `127.0.0.1:8000` via **Streamable HTTP**, designed for seamless integration with the **Gemini Desktop App**.

---

## 🔒 Security Architecture (`run_command` & Filesystem)

The server implements multi-layered security controls to protect the host machine while providing autonomous development capabilities:

1. **`shell=False` OS Vector Execution**:
   - Commands are tokenized with `shlex.split()` and executed directly via `subprocess.run(..., shell=False)`.
   - Shell chaining operators (`;`, `&&`, `||`, `|`, `>`, `>>`, `<`, `` ` ``, `$()`) are blocked, preventing arbitrary shell command injection.

2. **Strict Binary & Subcommand Whitelist**:
   - Only pre-approved developer tools are permitted:
     - `flutter` (subcommands: `analyze`, `test`, `pub`, `doctor`, `clean`)
     - `dart` (subcommands: `analyze`, `test`, `format`, `fix`, `pub`, `compile`)
     - `git` (subcommands: `status`, `diff`, `log`, `branch`, `show`, `rev-parse`)
     - `pytest` (test suite runner)
     - `ruff` (subcommands: `check`, `format`)
     - `flake8` (linter)
     - `black` (flags: `--check`, `--diff` only, blocking destructive uninspected writes)
     - `python3` (`-m` only with safe modules: `pytest`, `unittest`, `ruff`, `mypy`, `py_compile`)
     - `npm` (subcommands: `test`, `run`)
     - `gradle` (subcommands: `build`, `test`, `check`, `tasks`, `assemble`)

3. **Explicitly Blocked Destructive Tokens**:
   - Tokens like `--force`, `-f`, `push`, `reset`, `clean -f`, `rm`, `sudo`, `eval`, `exec` are intercepted and blocked before execution.

4. **Hard Timeout & Output Truncation**:
   - Commands default to a 60-second timeout (configurable between 5s and 180s) to prevent hanging tasks.
   - Outputs exceeding 15,000 characters are safely truncated to protect the LLM's context window.

5. **Path Traversal & Symlink Defense**:
   - All filesystem operations are validated via `resolve_safe_path()` to ensure operations strictly stay within `WORKSPACE_DIR`.
   - Directory traversal attempts (`../`, symlink escapes) raise security violations.

6. **Atomic File Writes**:
   - File edits and creations use temporary files swapped atomically via `os.replace` to prevent 0-byte corruption.

---

## 🛠 Available MCP Tools

| Tool | Description |
| :--- | :--- |
| `list_files` | Lists workspace files with sizes in KB, filtering out `.git`, `node_modules`, `build`, etc. |
| `read_file` | Reads file content with 1-indexed line numbers and optional line slicing (`start_line`, `end_line`). |
| `write_file` | Atomically creates or replaces a file, automatically creating parent directories. |
| `patch_file` | Performs an exact, unambiguous search-and-replace edit on code files. |
| `search_code` | Performs regex or string search across code files, returning matching paths, lines, and snippets. |
| `move_or_rename_file` | Safely renames or moves a file within the workspace boundaries. |
| `delete_file` | Deletes a single file within the workspace (directory deletion is blocked). |
| `run_command` | Sandboxed CLI runner for whitelisted developer commands. |

---

## 🚀 Quickstart

### 1. Requirements & Setup

Using Python 3.10+:

```bash
# Clone/navigate to directory
cd /Users/omkar/GeminiAppMCP

# Activate venv and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> **Note on MCP Version**: `requirements.txt` pins `mcp>=1.30.0,<2` because `FastMCP` with `transport="streamable-http"` is the native streamable HTTP transport in the 1.x series.

### 2. Run the Server

You can use the helper script:

```bash
# Launch server pointing to a specific workspace directory
./run_server.sh /path/to/your/project

# Or run directly with environment variables:
export MCP_WORKSPACE_DIR="/path/to/your/project"
export MCP_PORT="8000"
source .venv/bin/activate
python3 mcp_coding_agent.py
```

The server will start listening at:
```text
http://127.0.0.1:8000/mcp
```

### 3. Connect to Gemini Desktop App

1. Open **Gemini Desktop App**.
2. Navigate to **Settings** > **MCP Servers** (or **Custom Tools**).
3. Add a new **HTTP MCP Server**:
   - **Name**: `Local Coding Agent`
   - **Type**: `HTTP` / `Streamable HTTP`
   - **URL**: `http://127.0.0.1:8000/mcp`
4. Save and connect.

---

## 🧪 Running Automated Tests

Run the test suite verifying all tools, security rules, and HTTP endpoints:

```bash
source .venv/bin/activate
pytest -v
```
