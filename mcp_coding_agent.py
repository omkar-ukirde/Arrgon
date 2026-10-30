import os
import re
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
from mcp.server.fastmcp import FastMCP

# =====================================================================
# 1. CONFIGURATION
# =====================================================================
WORKSPACE_DIR = Path(
    os.environ.get("MCP_WORKSPACE_DIR", "./my_coding_workspace")
).resolve()
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

HOST = os.environ.get("MCP_HOST", "127.0.0.1")
PORT = int(os.environ.get("MCP_PORT", "8000"))

MAX_FILE_SIZE_BYTES = 500 * 1024       # 500 KB max single-read limit
MAX_OUTPUT_CHARS = 15000               # Truncate huge terminal outputs
DEFAULT_CMD_TIMEOUT_SEC = 60           # Kill hanging commands after 60s

IGNORED_DIRS = {
    ".git", ".dart_tool", ".idea", ".vscode", ".gradle", ".venv", "venv",
    "node_modules", "build", "Pods", "__pycache__", ".next", "dist"
}

IGNORED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip",
    ".tar", ".gz", ".keystore", ".jks", ".so", ".dylib", ".dll", ".exe",
    ".class", ".jar", ".dex", ".lock"
}

# Whitelist of allowed CLI binaries and their permitted first subcommands.
# If the allowed set is None, any non-destructive flag/arg is permitted.
ALLOWED_COMMANDS: dict[str, Optional[set[str]]] = {
    "flutter": {"analyze", "test", "pub", "doctor", "clean"},
    "dart": {"analyze", "test", "format", "fix", "pub", "compile"},
    "git": {"status", "diff", "log", "branch", "show", "rev-parse"},
    "pytest": None,
    "ruff": {"check", "format"},
    "flake8": None,
    "black": {"--check", "--diff"},
    "python3": {"-m"},
    "npm": {"test", "run"},
    "gradle": {"build", "test", "check", "tasks", "assemble"},
}

# Explicitly blocked flags/tokens anywhere in the command arguments
BLOCKED_ARG_TOKENS = {
    "--force", "-f", "push", "reset", "clean -f", "rm", "sudo", "eval", "exec"
}

# Initialize FastMCP bound strictly to localhost (127.0.0.1)
mcp = FastMCP("Local Coding Agent", host=HOST, port=PORT)


# =====================================================================
# 2. SECURITY & FILESYSTEM HELPERS
# =====================================================================
def resolve_safe_path(relative_path: str) -> Path:
    """Strictly resolves a path inside WORKSPACE_DIR, blocking traversal and symlink escapes."""
    clean_rel = relative_path.strip().lstrip("/\\")
    target_path = (WORKSPACE_DIR / clean_rel).resolve()

    if not target_path.is_relative_to(WORKSPACE_DIR):
        raise ValueError(
            f"Security violation: Path '{relative_path}' resolves outside the workspace."
        )
    return target_path


def is_ignored_dir(dir_name: str) -> bool:
    return dir_name in IGNORED_DIRS or (dir_name.startswith(".") and dir_name != ".")


def atomic_write(target_path: Path, content: str) -> None:
    """Writes to a temp file and atomically swaps it to prevent 0-byte file corruption."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(
        dir=str(target_path.parent),
        prefix=f".{target_path.name}.",
        suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as tmp_file:
            tmp_file.write(content)
        os.replace(temp_path, target_path)
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


def validate_command(command_str: str) -> list[str]:
    """
    Parses a command string into an argument list (no shell interpolation)
    and verifies it against the strict binary + subcommand whitelist.
    """
    try:
        args = shlex.split(command_str)
    except ValueError as e:
        raise ValueError(f"Invalid command syntax: {e}")

    if not args:
        raise ValueError("Empty command.")

    # Block shell chaining operators if the LLM tries to pass them as arguments
    shell_metachars = {";", "&&", "||", "|", ">", ">>", "<", "`", "$("}
    for token in args:
        if any(meta in token for meta in shell_metachars):
            raise ValueError(
                f"Security violation: Shell operator detected in '{token}'. "
                "Run single commands only without pipes or redirects."
            )
        if token in BLOCKED_ARG_TOKENS:
            raise ValueError(f"Security violation: Argument '{token}' is blocked.")

    binary = Path(args[0]).name  # Normalize '/opt/homebrew/bin/flutter' -> 'flutter'
    if binary not in ALLOWED_COMMANDS:
        allowed_list = ", ".join(sorted(ALLOWED_COMMANDS.keys()))
        raise ValueError(
            f"Command '{binary}' is not permitted. Allowed binaries: {allowed_list}"
        )

    allowed_subcommands = ALLOWED_COMMANDS[binary]
    if allowed_subcommands is not None:
        if len(args) < 2 or args[1] not in allowed_subcommands:
            subs = ", ".join(sorted(allowed_subcommands))
            raise ValueError(
                f"Subcommand not permitted for '{binary}'. Allowed first arguments: {subs}"
            )

        # Extra check for `python3 -m`: only allow safe test/lint modules
        if binary == "python3" and args[1] == "-m":
            allowed_py_modules = {"pytest", "unittest", "ruff", "mypy", "py_compile"}
            if len(args) < 3 or args[2] not in allowed_py_modules:
                raise ValueError(
                    f"Only {allowed_py_modules} are permitted with 'python3 -m'."
                )

    return args


# =====================================================================
# 3. MCP FILESYSTEM TOOLS
# =====================================================================
@mcp.tool()
def list_files(directory: str = ".", max_depth: int = 4) -> str:
    """
    Lists files in the workspace while automatically filtering out build artifacts
    and hidden dependency folders (.git, build, .dart_tool, Pods, node_modules).
    """
    try:
        start_path = resolve_safe_path(directory)
        if not start_path.exists():
            return f"Error: Directory '{directory}' does not exist."
        if not start_path.is_dir():
            return f"Error: '{directory}' is a file, not a directory."

        results = []
        base_depth = len(start_path.parts)

        for root, dirs, files in os.walk(start_path):
            root_path = Path(root)
            current_depth = len(root_path.parts) - base_depth
            dirs[:] = sorted([d for d in dirs if not is_ignored_dir(d)])

            if current_depth >= max_depth:
                dirs.clear()
                continue

            for file in sorted(files):
                if file.startswith(".") and file not in {".env.example", ".gitignore", ".metadata"}:
                    continue
                full_path = root_path / file
                try:
                    rel_path = full_path.relative_to(WORKSPACE_DIR)
                    size_kb = full_path.stat().st_size / 1024
                    results.append(f"{rel_path.as_posix()} ({size_kb:.1f} KB)")
                except (OSError, ValueError):
                    continue

        if not results:
            return f"No visible files found in '{directory}'."
        return f"Workspace: {WORKSPACE_DIR}\n" + "\n".join(results)
    except Exception as e:
        return f"Error listing files: {str(e)}"


@mcp.tool()
def read_file(
    filename: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None
) -> str:
    """
    Reads a code file with line numbers. Optionally specify start_line and end_line
    (1-indexed, inclusive) to inspect specific sections of large files.
    """
    try:
        path = resolve_safe_path(filename)
        if not path.exists():
            return f"Error: File '{filename}' not found."
        if not path.is_file():
            return f"Error: '{filename}' is a directory, not a file."

        file_size = path.stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES and start_line is None and end_line is None:
            return (
                f"Error: File '{filename}' is {file_size / 1024:.1f} KB (exceeds 500 KB limit). "
                "Pass start_line and end_line to read a specific slice."
            )

        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        total_lines = len(lines)
        s_idx = max(1, start_line) if start_line is not None else 1
        e_idx = min(total_lines, end_line) if end_line is not None else total_lines

        if s_idx > e_idx and total_lines > 0:
            return f"Error: start_line ({s_idx}) cannot exceed end_line ({e_idx})."

        selected_lines = lines[s_idx - 1 : e_idx]
        numbered_output = [
            f"{line_num:4d} | {line.rstrip('\r\n')}"
            for line_num, line in enumerate(selected_lines, start=s_idx)
        ]

        header = f"--- {filename} (Lines {s_idx}-{e_idx} of {total_lines}) ---\n"
        return header + "\n".join(numbered_output)

    except UnicodeDecodeError:
        return f"Error: '{filename}' is a binary file and cannot be read as UTF-8 text."
    except Exception as e:
        return f"Error reading file: {str(e)}"


@mcp.tool()
def write_file(filename: str, content: str) -> str:
    """
    Creates a new file or completely overwrites an existing file atomically.
    Automatically creates parent directories if needed.
    """
    try:
        path = resolve_safe_path(filename)
        if path.exists() and path.is_dir():
            return f"Error: '{filename}' is a directory, not a file."
        normalized_content = content.replace("\r\n", "\n")
        atomic_write(path, normalized_content)
        line_count = normalized_content.count("\n") + (1 if normalized_content else 0)
        return f"Successfully wrote {line_count} lines to '{filename}'."
    except Exception as e:
        return f"Error writing file: {str(e)}"


@mcp.tool()
def patch_file(filename: str, search_text: str, replace_text: str) -> str:
    """
    Finds an exact block of code (search_text) and replaces it with new code (replace_text).
    Requires search_text to appear exactly once in the file to prevent unintended edits.
    """
    try:
        path = resolve_safe_path(filename)
        if not path.exists():
            return f"Error: File '{filename}' does not exist."

        with open(path, "r", encoding="utf-8") as f:
            raw_content = f.read()

        norm_content = raw_content.replace("\r\n", "\n")
        norm_search = search_text.replace("\r\n", "\n")
        norm_replace = replace_text.replace("\r\n", "\n")

        if not norm_search:
            return "Error: 'search_text' cannot be empty."

        match_count = norm_content.count(norm_search)
        if match_count == 0:
            return (
                f"Error: Could not find exact 'search_text' in '{filename}'. "
                "Call read_file first to verify exact indentation and lines."
            )
        if match_count > 1:
            return (
                f"Error: Ambiguous patch. Found {match_count} identical matches in '{filename}'. "
                "Include 2-3 surrounding lines in 'search_text' to make it unique."
            )

        updated_content = norm_content.replace(norm_search, norm_replace, 1)
        atomic_write(path, updated_content)
        return f"Successfully patched '{filename}'."
    except UnicodeDecodeError:
        return f"Error: '{filename}' is a binary file and cannot be patched."
    except Exception as e:
        return f"Error patching file: {str(e)}"


@mcp.tool()
def search_code(
    query: str,
    directory: str = ".",
    case_sensitive: bool = False,
    max_results: int = 50
) -> str:
    """
    Searches for a text string or regex pattern across all code files in the workspace.
    Returns matching file paths, line numbers, and snippets.
    """
    try:
        start_path = resolve_safe_path(directory)
        if not start_path.exists():
            return f"Error: Directory '{directory}' does not exist."

        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            pattern = re.compile(query, flags)
        except re.error:
            pattern = re.compile(re.escape(query), flags)

        matches = []
        for root, dirs, files in os.walk(start_path):
            dirs[:] = sorted([d for d in dirs if not is_ignored_dir(d)])
            root_path = Path(root)

            for file in sorted(files):
                if file.startswith("."):
                    continue
                full_path = root_path / file
                if full_path.suffix.lower() in IGNORED_EXTENSIONS:
                    continue
                if full_path.stat().st_size > MAX_FILE_SIZE_BYTES:
                    continue

                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        for line_num, line in enumerate(f, start=1):
                            if pattern.search(line):
                                rel_path = full_path.relative_to(WORKSPACE_DIR).as_posix()
                                snippet = line.strip()[:120]
                                matches.append(f"{rel_path}:{line_num}: {snippet}")
                                if len(matches) >= max_results:
                                    return (
                                        f"Showing first {max_results} matches for '{query}':\n"
                                        + "\n".join(matches)
                                    )
                except (UnicodeDecodeError, PermissionError):
                    continue

        if not matches:
            return f"No matches found for '{query}' in '{directory}'."
        return f"Found {len(matches)} match(es) for '{query}':\n" + "\n".join(matches)
    except Exception as e:
        return f"Error searching code: {str(e)}"


@mcp.tool()
def move_or_rename_file(source_path: str, destination_path: str) -> str:
    """Moves or renames a file or directory within the workspace."""
    try:
        src = resolve_safe_path(source_path)
        dst = resolve_safe_path(destination_path)
        if not src.exists():
            return f"Error: Source '{source_path}' does not exist."
        if dst.exists():
            return f"Error: Destination '{destination_path}' already exists."

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return f"Successfully moved '{source_path}' to '{destination_path}'."
    except Exception as e:
        return f"Error moving file: {str(e)}"


@mcp.tool()
def delete_file(filename: str) -> str:
    """Deletes a single file from the workspace."""
    try:
        path = resolve_safe_path(filename)
        if not path.exists():
            return f"Error: File '{filename}' does not exist."
        if path.is_dir():
            return f"Error: '{filename}' is a directory. Only single file deletion is permitted."
        os.remove(path)
        return f"Successfully deleted '{filename}'."
    except Exception as e:
        return f"Error deleting file: {str(e)}"


# =====================================================================
# 4. SAFE TERMINAL RUNNER TOOL (Tests, Linters, Git Status/Diff)
# =====================================================================
@mcp.tool()
def run_command(
    command: str,
    working_subdirectory: str = ".",
    timeout_seconds: int = DEFAULT_CMD_TIMEOUT_SEC
) -> str:
    """
    Executes a whitelisted development command (e.g., 'flutter analyze', 'flutter test',
    'dart format .', 'git status', 'git diff', 'pytest') safely inside the workspace.
    Shell chaining (&&, |, ;) is disabled for security.
    """
    try:
        cwd_path = resolve_safe_path(working_subdirectory)
        if not cwd_path.exists() or not cwd_path.is_dir():
            return f"Error: Working directory '{working_subdirectory}' is invalid."

        args = validate_command(command)
        effective_timeout = min(max(5, timeout_seconds), 180)  # Clamp between 5s and 180s

        # Ensure standard macOS paths (Homebrew, Flutter, pub-cache) are available
        env = os.environ.copy()
        env["CI"] = "true"  # Prevents interactive CLI spinners/prompts from hanging

        extra_paths = [
            "/opt/homebrew/bin",
            "/opt/homebrew/sbin",
            "/usr/local/bin",
            str(Path.home() / ".pub-cache" / "bin"),
            str(Path.home() / "flutter" / "bin"),
            str(Path.home() / "development" / "flutter" / "bin"),
        ]
        current_path = env.get("PATH", "")
        paths = current_path.split(os.pathsep) if current_path else []
        for p in extra_paths:
            if p not in paths and os.path.exists(p):
                paths.insert(0, p)
        env["PATH"] = os.pathsep.join(paths)

        result = subprocess.run(
            args,
            cwd=str(cwd_path),
            shell=False,
            capture_output=True,
            text=True,
            timeout=effective_timeout,
            env=env
        )

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        combined = ""
        if stdout:
            combined += f"[STDOUT]\n{stdout}\n"
        if stderr:
            combined += f"[STDERR]\n{stderr}\n"
        if not combined:
            combined = "(Command completed with no output)"

        if len(combined) > MAX_OUTPUT_CHARS:
            half = MAX_OUTPUT_CHARS // 2
            combined = (
                combined[:half]
                + f"\n\n... [TRUNCATED {len(combined) - MAX_OUTPUT_CHARS} CHARACTERS] ...\n\n"
                + combined[-half:]
            )

        return (
            f"Command: {' '.join(args)}\n"
            f"Exit Code: {result.returncode}\n"
            f"{combined}"
        )

    except subprocess.TimeoutExpired:
        return f"Error: Command '{command}' timed out after {timeout_seconds} seconds."
    except ValueError as ve:
        return f"Blocked: {str(ve)}"
    except FileNotFoundError as fnf:
        return f"Error: Executable not found on system PATH ({str(fnf)})."
    except Exception as e:
        return f"Error executing command: {str(e)}"


# =====================================================================
# 5. ENTRYPOINT (Localhost 127.0.0.1 Streamable HTTP)
# =====================================================================
if __name__ == "__main__":
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"============================================================")
    print(f" Local Coding Agent MCP Server")
    print(f" Workspace : {WORKSPACE_DIR}")
    print(f" Endpoint  : http://{HOST}:{PORT}/mcp")
    print(f"============================================================")
    mcp.run(transport="streamable-http")
