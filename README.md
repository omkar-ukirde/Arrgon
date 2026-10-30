<p align="center">
  <h1 align="center">⚛️ Arrgon</h1>
  <p align="center">
    <strong>Free, open-source AI coding agent server for Google Gemini</strong>
  </p>
  <p align="center">
    Turn the free Gemini Desktop App into a powerful autonomous coding agent — reads files, writes code, runs tests, and verifies its own changes — all locally on your machine.
  </p>
</p>

<p align="center">
  <a href="#-quickstart-2-minutes">Quickstart</a> •
  <a href="#-how-it-works">How It Works</a> •
  <a href="#%EF%B8%8F-security">Security</a> •
  <a href="#-available-tools">Tools</a> •
  <a href="#-customization">Customization</a> •
  <a href="#-contributing">Contributing</a>
</p>

---

## 💡 What is Arrgon?

**Arrgon** is a local [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server that gives Google Gemini the ability to **read, write, search, and patch code files** — and **run developer commands** like `flutter analyze`, `pytest`, `git diff`, `npm test`, etc. — all inside a sandboxed, zero-shell environment on your machine.

> **Use Gemini as a free AI coding agent.** No API keys. No subscriptions. Just connect Arrgon to the [Gemini Desktop App](https://gemini.google.com/app) and start prompting.

### What can you do with it?

- 🔍 *"Read `lib/main.dart` and find all TODO comments in the project"*
- ✏️ *"Add error handling to the `fetchUser()` function and run `flutter analyze` to check for issues"*
- 🧪 *"Write a unit test for the auth module, then run `pytest` to verify it passes"*
- 🔄 *"Refactor `utils.py` to use dataclasses and check `git diff` to review the changes"*

Gemini autonomously loops through **read → edit → verify** cycles until the task is done.

---

## 🚀 Quickstart (2 Minutes)

### Prerequisites

- **Python 3.10+** installed ([python.org](https://www.python.org/downloads/))
- **Gemini Desktop App** installed ([gemini.google.com/app](https://gemini.google.com/app))

### Step 1: Clone & Install

```bash
git clone https://github.com/omkar-ukirde/Arrgon.git
cd Arrgon

python3 -m venv .venv
source .venv/bin/activate      # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Step 2: Connect to Gemini Desktop App

Open the **Gemini Desktop App** → **Settings** (gear icon) → **Connected Apps** → **Add custom connected app**.

You will see two setup methods. Use **Local MCP** (recommended):

#### Option A: Local MCP (Recommended)

The Gemini app launches and manages the server process for you. Zero maintenance.

| Field | Value |
|:---|:---|
| **Setup method** | **Local MCP** |
| **Server name** | `Arrgon` |
| **Description** | `AI coding agent with file tools and safe command runner` |
| **Command** | See below 👇 |
| **Sandbox** | **Full access** |

**Command** — paste the full path to `start_mcp.sh`:

```
/full/path/to/Arrgon/start_mcp.sh
```

**Example** (on macOS):

```
/Users/yourname/Arrgon/start_mcp.sh
```

> **💡 Changing your project folder:**
> - Edit `DEFAULT_WORKSPACE` inside `start_mcp.sh` to point to whatever project directory you want to work on (e.g., `/Users/yourname/MyProject`), or
> - Pass the directory directly as an argument in the Command field:
>   `/Users/yourname/Arrgon/start_mcp.sh /Users/yourname/MyProject`
> - Always choose **Full access** under Sandbox settings so Arrgon can read and write to your workspace without permission errors.

Click **Next** → **Connect**, and you're done!

#### Option B: Cloud MCP (HTTP Mode)

If you prefer running the server yourself in a terminal (useful for debugging or switching projects):

**1. Start the server:**

```bash
cd Arrgon
./run_server.sh /path/to/your/project
```

**2. In Gemini Desktop App**, choose **Cloud MCP** and enter:

| Field | Value |
|:---|:---|
| **URL** | `http://127.0.0.1:8000/mcp` |

> **Note:** You must keep the terminal running. Closing it stops the server.

### Step 3: Start Coding with Gemini

Go back to the Gemini chat and try:

> *"List all files in my project and give me an overview of the codebase structure"*

Gemini will call Arrgon's tools to browse your files, read code, and respond with a structured overview. From there, you can ask it to make changes, run tests, debug errors — anything a coding assistant would do.

---

## ⚙️ How It Works

```
┌─────────────────────┐        MCP (stdio or HTTP)        ┌──────────────────────┐
│   Gemini Desktop    │ ◄──────────────────────────────► │       Arrgon         │
│   App (free)        │    JSON-RPC tool calls            │   MCP Server         │
│                     │                                    │                      │
│  "Fix the bug in    │  ──► read_file("src/app.py")      │  Reads files         │
│   src/app.py and    │  ◄── file content with line #s    │  Writes atomically   │
│   run the tests"    │  ──► patch_file(search, replace)  │  Searches code       │
│                     │  ◄── "Successfully patched"       │  Runs safe commands  │
│                     │  ──► run_command("pytest")        │                      │
│                     │  ◄── test results                 │  All sandboxed to    │
│                     │                                    │  your workspace dir  │
└─────────────────────┘                                    └──────────────────────┘
```

Arrgon exposes **8 MCP tools** that Gemini calls autonomously. Gemini decides which tools to call and in what order — forming edit → verify loops on its own.

---

## 🛡️ Security

Arrgon is designed to be safe for autonomous AI usage on your local machine. Every operation is sandboxed.

### `run_command` — Zero-Shell Terminal Runner

The `run_command` tool is the most security-critical component. Here's what makes it safe:

| Layer | Protection |
|:---|:---|
| **`shell=False` execution** | Commands are parsed with `shlex.split()` and executed as an OS argument vector (`subprocess.run(..., shell=False)`). Shell chaining (`&& rm -rf`, `;`, `\|`, `` ` ``, `$()`) is **impossible**. |
| **Binary whitelist** | Only pre-approved developer tools are allowed: `flutter`, `dart`, `git`, `pytest`, `ruff`, `flake8`, `black`, `python3`, `npm`, `gradle`. Everything else is rejected. |
| **Subcommand whitelist** | Even allowed binaries are restricted to safe subcommands. For example, `git status` ✅ but `git push` ❌, `flutter analyze` ✅ but `flutter run` ❌. |
| **Destructive token blocklist** | Tokens like `--force`, `-f`, `push`, `reset`, `rm`, `sudo`, `eval`, `exec` are intercepted and blocked regardless of position. |
| **Hard timeout** | Commands are killed after 60 seconds (configurable 5s–180s) to prevent hangs from interactive prompts. |
| **Output truncation** | Massive outputs are truncated to 15,000 characters so they don't crash Gemini's context window. |

### Filesystem Sandbox

| Layer | Protection |
|:---|:---|
| **Path traversal defense** | All paths are resolved against `WORKSPACE_DIR`. Attempts like `../../etc/passwd` raise security violations. |
| **Symlink escape detection** | Paths are fully resolved with `.resolve()` and validated with `.is_relative_to()` — symlinks pointing outside the workspace are blocked. |
| **Atomic writes** | Files are written to a temporary file first, then atomically swapped via `os.replace` to prevent 0-byte corruption on crash. |
| **Single-match patching** | `patch_file` requires the search text to appear exactly once, preventing accidental mass replacements. |

---

## 🔧 Available Tools

| Tool | Description |
|:---|:---|
| `list_files` | Lists workspace files with sizes, filtering out `.git`, `node_modules`, `build`, `__pycache__`, etc. |
| `read_file` | Reads file content with numbered lines. Supports `start_line`/`end_line` slicing for large files. |
| `write_file` | Creates or replaces a file atomically. Auto-creates parent directories. |
| `patch_file` | Exact search-and-replace on code. Requires a unique match to prevent unintended edits. |
| `search_code` | Regex or text search across all code files. Returns file paths, line numbers, and snippets. |
| `move_or_rename_file` | Moves or renames files/directories within the workspace. |
| `delete_file` | Deletes a single file (directory deletion is blocked for safety). |
| `run_command` | Sandboxed CLI runner for whitelisted dev commands (see [Security](#%EF%B8%8F-security)). |

---

## 🎛️ Customization

### Environment Variables

| Variable | Default | Description |
|:---|:---|:---|
| `MCP_WORKSPACE_DIR` | `./my_coding_workspace` | Root directory for all file operations |
| `MCP_HOST` | `127.0.0.1` | Host to bind HTTP server (Cloud MCP mode only) |
| `MCP_PORT` | `8000` | Port for HTTP server (Cloud MCP mode only) |

### Adding More Commands

Edit the `ALLOWED_COMMANDS` dictionary in [`mcp_coding_agent.py`](mcp_coding_agent.py) to allow more tools:

```python
ALLOWED_COMMANDS: dict[str, Optional[set[str]]] = {
    # Add your own:
    "cargo": {"build", "test", "check", "clippy"},
    "go":    {"build", "test", "vet", "fmt"},
    "make":  {"test", "build", "lint"},
    # ... existing entries ...
}
```

Set a value of `None` to allow any subcommand for a binary (only for trusted tools like test runners):

```python
"mypy": None,  # Any arguments are allowed
```

### Switching Projects

**Local MCP:** Edit the command in Gemini Desktop App settings to point to a different workspace directory.

**Cloud MCP:** Stop the server (Ctrl+C) and restart with a new path:

```bash
./run_server.sh /path/to/different/project
```

---

## 🧪 Running Tests

Arrgon includes 18 automated tests covering command validation, path security, file operations, and HTTP endpoint integration:

```bash
source .venv/bin/activate
pytest -v
```

```
test_mcp_coding_agent.py::test_validate_command_allowed PASSED
test_mcp_coding_agent.py::test_validate_command_shell_operators_blocked PASSED
test_mcp_coding_agent.py::test_validate_command_blocked_tokens PASSED
test_mcp_coding_agent.py::test_validate_command_unauthorized_binaries_and_subcommands PASSED
test_mcp_coding_agent.py::test_validate_command_empty PASSED
test_mcp_coding_agent.py::test_resolve_safe_path_valid PASSED
test_mcp_coding_agent.py::test_resolve_safe_path_traversal_blocked PASSED
test_mcp_coding_agent.py::test_write_and_read_file PASSED
test_mcp_coding_agent.py::test_read_file_errors PASSED
test_mcp_coding_agent.py::test_patch_file PASSED
test_mcp_coding_agent.py::test_search_code PASSED
test_mcp_coding_agent.py::test_list_files PASSED
test_mcp_coding_agent.py::test_move_or_rename_file PASSED
test_mcp_coding_agent.py::test_delete_file PASSED
test_mcp_coding_agent.py::test_run_command_allowed_execution PASSED
test_mcp_coding_agent.py::test_run_command_blocked PASSED
test_mcp_coding_agent.py::test_run_command_invalid_directory PASSED
test_mcp_coding_agent.py::test_streamable_http_initialization_and_tool_list PASSED

============================== 18 passed ==============================
```

---

## 📁 Project Structure

```
Arrgon/
├── mcp_coding_agent.py        # Main MCP server (all tools + security)
├── test_mcp_coding_agent.py   # Automated test suite (18 tests)
├── run_server.sh              # Helper script for HTTP mode
├── requirements.txt           # Python dependencies
├── LICENSE                    # MIT License
└── README.md                  # This file
```

---

## 🤝 Contributing

Contributions are welcome! Some ideas:

- **Add more tool commands** (Rust/Cargo, Go, Make, Docker, etc.)
- **Add a `create_directory` tool** for scaffolding projects
- **Add `undo_patch`** with file backup/restore
- **Windows support** improvements (PATH handling, shell detection)
- **Multi-workspace** support for monorepos

```bash
# Fork, clone, and run tests
git clone https://github.com/YOUR_USERNAME/Arrgon.git
cd Arrgon
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -v
```

---

## 📄 License

[MIT License](LICENSE) — use it however you want, free forever.

---

<p align="center">
  <sub>Built with ❤️ for the developer community. Give Gemini superpowers. Star ⭐ if you find this useful!</sub>
</p>
