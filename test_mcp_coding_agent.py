import os
import shutil
import tempfile
import pytest
from pathlib import Path

import mcp_coding_agent as agent


@pytest.fixture
def workspace_env(monkeypatch):
    """Creates a temporary workspace for isolated tool testing."""
    temp_dir = tempfile.mkdtemp(prefix="mcp_test_ws_")
    resolved_path = Path(temp_dir).resolve()
    monkeypatch.setattr(agent, "WORKSPACE_DIR", resolved_path)
    yield resolved_path
    shutil.rmtree(temp_dir, ignore_errors=True)


# =====================================================================
# 1. COMMAND VALIDATION TESTS
# =====================================================================
def test_validate_command_allowed():
    # Binaries with allowed subcommands
    assert agent.validate_command("git status") == ["git", "status"]
    assert agent.validate_command("git diff --staged") == ["git", "diff", "--staged"]
    assert agent.validate_command("flutter analyze lib/") == ["flutter", "analyze", "lib/"]
    assert agent.validate_command("dart format .") == ["dart", "format", "."]
    assert agent.validate_command("npm test") == ["npm", "test"]
    assert agent.validate_command("npm run build") == ["npm", "run", "build"]
    assert agent.validate_command("gradle test") == ["gradle", "test"]
    assert agent.validate_command("black --check .") == ["black", "--check", "."]
    assert agent.validate_command("ruff check .") == ["ruff", "check", "."]

    # Binaries with None subcommands (open arguments)
    assert agent.validate_command("pytest") == ["pytest"]
    assert agent.validate_command("pytest tests/test_app.py -v") == [
        "pytest", "tests/test_app.py", "-v"
    ]
    assert agent.validate_command("flake8 .") == ["flake8", "."]

    # python3 -m restricted modules
    assert agent.validate_command("python3 -m pytest") == ["python3", "-m", "pytest"]
    assert agent.validate_command("python3 -m unittest") == ["python3", "-m", "unittest"]


def test_validate_command_shell_operators_blocked():
    blocked = [
        "git status; rm -rf /",
        "git status && pytest",
        "git status || ls",
        "git log | grep fix",
        "pytest > output.txt",
        "pytest >> output.txt",
        "pytest < input.txt",
        "pytest `whoami`",
        "pytest $(whoami)",
    ]
    for cmd in blocked:
        with pytest.raises(ValueError, match="Shell operator detected"):
            agent.validate_command(cmd)


def test_validate_command_blocked_tokens():
    blocked = [
        "git push origin main",
        "git push --force",
        "git reset --hard HEAD~1",
        "git clean -f",
        "sudo flutter doctor",
        "rm file.txt",
    ]
    for cmd in blocked:
        with pytest.raises(ValueError, match="is blocked|not permitted"):
            agent.validate_command(cmd)


def test_validate_command_unauthorized_binaries_and_subcommands():
    # Unauthorized binaries
    with pytest.raises(ValueError, match="Command 'curl' is not permitted"):
        agent.validate_command("curl https://google.com")

    with pytest.raises(ValueError, match="Command 'bash' is not permitted"):
        agent.validate_command("bash script.sh")

    # Unauthorized subcommands
    with pytest.raises(ValueError, match="Subcommand not permitted for 'flutter'"):
        agent.validate_command("flutter run")

    with pytest.raises(ValueError, match="Subcommand not permitted for 'npm'"):
        agent.validate_command("npm install express")

    with pytest.raises(ValueError, match="Subcommand not permitted for 'python3'"):
        agent.validate_command("python3 -c 'print(1)'")

    with pytest.raises(ValueError, match="Only .* are permitted with 'python3 -m'"):
        agent.validate_command("python3 -m http.server")


def test_validate_command_empty():
    with pytest.raises(ValueError, match="Empty command"):
        agent.validate_command("   ")


# =====================================================================
# 2. PATH SECURITY TESTS
# =====================================================================
def test_resolve_safe_path_valid(workspace_env):
    path = agent.resolve_safe_path("src/main.py")
    assert path == workspace_env / "src" / "main.py"
    assert path.is_relative_to(workspace_env)


def test_resolve_safe_path_traversal_blocked(workspace_env):
    with pytest.raises(ValueError, match="Security violation"):
        agent.resolve_safe_path("../../etc/passwd")

    with pytest.raises(ValueError, match="Security violation"):
        agent.resolve_safe_path("../secret.txt")

    with pytest.raises(ValueError, match="Security violation"):
        agent.resolve_safe_path("sub/../../../../escaped.txt")


# =====================================================================
# 3. FILE SYSTEM TOOL TESTS
# =====================================================================
def test_write_and_read_file(workspace_env):
    # Write file in nested directory
    res = agent.write_file("sub/hello.txt", "Line 1\nLine 2\nLine 3\n")
    assert "Successfully wrote 4 lines" in res or "Successfully wrote 3 lines" in res

    # Read entire file
    read_all = agent.read_file("sub/hello.txt")
    assert "Line 1" in read_all
    assert "Line 2" in read_all
    assert "Line 3" in read_all
    assert "Lines 1-3 of 3" in read_all

    # Read specific slice
    read_slice = agent.read_file("sub/hello.txt", start_line=2, end_line=2)
    assert "Line 2" in read_slice
    assert "Line 1" not in read_slice
    assert "Lines 2-2 of 3" in read_slice


def test_read_file_errors(workspace_env):
    # Non-existent file
    res = agent.read_file("nonexistent.txt")
    assert "Error: File 'nonexistent.txt' not found." in res

    # Inverted slice
    agent.write_file("test.txt", "a\nb\nc\n")
    res = agent.read_file("test.txt", start_line=3, end_line=1)
    assert "start_line (3) cannot exceed end_line (1)" in res


def test_patch_file(workspace_env):
    agent.write_file("app.py", "def main():\n    print('Hello World')\n\nif __name__ == '__main__':\n    main()\n")

    # Successful patch
    res = agent.patch_file("app.py", "print('Hello World')", "print('Hello Gemini')")
    assert "Successfully patched 'app.py'." in res
    assert "print('Hello Gemini')" in agent.read_file("app.py")

    # Not found search_text
    res_not_found = agent.patch_file("app.py", "print('Missing')", "print('New')")
    assert "Could not find exact 'search_text'" in res_not_found

    # Ambiguous search_text
    agent.write_file("duplicate.py", "x = 1\nx = 1\n")
    res_ambiguous = agent.patch_file("duplicate.py", "x = 1", "x = 2")
    assert "Ambiguous patch. Found 2 identical matches" in res_ambiguous


def test_search_code(workspace_env):
    agent.write_file("src/module_a.py", "def calculate_total():\n    return 42\n")
    agent.write_file("src/module_b.py", "total_val = calculate_total()\n")
    agent.write_file("ignored.lock", "calculate_total locked\n")

    # Search for function name
    res = agent.search_code("calculate_total")
    assert "Found 2 match(es)" in res
    assert "src/module_a.py:1:" in res
    assert "src/module_b.py:1:" in res
    assert "ignored.lock" not in res  # Ignored extension


def test_list_files(workspace_env):
    agent.write_file("src/app.dart", "void main() {}")
    agent.write_file(".git/config", "dummy git config")
    agent.write_file("node_modules/pkg/index.js", "dummy node module")

    res = agent.list_files(".")
    assert "src/app.dart" in res
    assert ".git" not in res
    assert "node_modules" not in res


def test_move_or_rename_file(workspace_env):
    agent.write_file("orig.txt", "some content")
    res = agent.move_or_rename_file("orig.txt", "renamed/dest.txt")
    assert "Successfully moved" in res

    assert "some content" in agent.read_file("renamed/dest.txt")
    assert "not found" in agent.read_file("orig.txt")


def test_delete_file(workspace_env):
    agent.write_file("temp.txt", "to be deleted")
    res = agent.delete_file("temp.txt")
    assert "Successfully deleted 'temp.txt'." in res
    assert "not found" in agent.read_file("temp.txt")

    # Refuse directory deletion
    (workspace_env / "folder").mkdir()
    res_dir = agent.delete_file("folder")
    assert "is a directory. Only single file deletion is permitted." in res_dir


# =====================================================================
# 4. RUN COMMAND INTEGRATION TESTS
# =====================================================================
def test_run_command_allowed_execution(workspace_env):
    # Test with python3 -m unittest on an empty suite
    res = agent.run_command("python3 -m unittest", working_subdirectory=".")
    assert "Command: python3 -m unittest" in res
    assert "Exit Code:" in res


def test_run_command_blocked():
    res = agent.run_command("rm -rf /")
    assert "Blocked:" in res

    res_pipe = agent.run_command("git status | cat")
    assert "Blocked:" in res_pipe


def test_run_command_invalid_directory(workspace_env):
    res = agent.run_command("python3 -m unittest", working_subdirectory="invalid_folder")
    assert "Error: Working directory 'invalid_folder' is invalid." in res


# =====================================================================
# 5. STREAMABLE HTTP TRANSPORT INTEGRATION TESTS
# =====================================================================
def test_streamable_http_initialization_and_tool_list():
    from starlette.testclient import TestClient

    app = agent.mcp.streamable_http_app()
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        # 1. MCP Initialize
        init_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"}
            }
        }
        resp = client.post("/mcp", json=init_payload, headers={"Accept": "application/json, text/event-stream"})
        assert resp.status_code == 200
        assert "Local Coding Agent" in resp.text

        session_id = resp.headers.get("mcp-session-id")
        assert session_id is not None

        # 2. MCP Tools List
        tools_payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        resp2 = client.post(
            "/mcp",
            json=tools_payload,
            headers={"Accept": "application/json, text/event-stream", "mcp-session-id": session_id}
        )
        assert resp2.status_code == 200
        for tool_name in [
            "list_files", "read_file", "write_file", "patch_file",
            "search_code", "move_or_rename_file", "delete_file", "run_command"
        ]:
            assert tool_name in resp2.text

