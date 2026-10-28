import json

import pytest

from wpstudio import hooks, sync


def decision(command):
    result = hooks.check_bash(command)
    return None if result is None else result["hookSpecificOutput"]["permissionDecision"]


@pytest.mark.parametrize("command", [
    "ssh acme@203.0.113.5", "scp x.php user@host:/www/", "sftp -b batch user@host", "sshpass -e ssh u@h",
    "cd x && ssh -p 22 u@h 'wp plugin list'", "bash -c 'ssh u@h ls'", "/usr/bin/ssh u@h",
    "rsync -az theme/ user@host:/www/theme/", "rsync -e 'ssh -p 2222' a b", "ssh-copy-id u@h",
    "curl -T x.php sftp://host/www/", "lftp -u u,p host", "sudo ssh u@h", "echo hi; scp a u@h:b",
])
def test_raw_remote_access_is_blocked(command):
    assert decision(command) == "deny"


@pytest.mark.parametrize("command", [
    "wpsite wp acme plugin list", "ssh-keygen -t ed25519 -f k", "git commit -m 'Set up ssh key login'",
    "rsync -a src/ dest/", "grep -r sshd_config docs", "echo 'use wpsite instead of ssh'",
    "wpsite deploy acme theme wp-content/themes/acme", "git push origin HEAD",
])
def test_ordinary_commands_pass(command):
    assert decision(command) is None


@pytest.mark.parametrize("command", [
    "cat CREDENTIALS.txt", "head -5 projects/acme/.secrets/live.env", "python3 -c \"open('CREDENTIALS.txt').read()\"",
    "grep -r PASSWORD projects/acme/.secrets", "cp projects/acme/.secrets/live.env /tmp/x",
    "wpsite secrets file acme && cat CREDENTIALS.txt", "ls projects/acme/.secrets/",
])
def test_secret_paths_are_blocked_outside_wpsite(command):
    assert decision(command) == "deny"


@pytest.mark.parametrize("command", [
    "wpsite secrets file acme", "wpsite secrets status acme:staging", "wpsite secrets wipe",
])
def test_wpsite_may_handle_the_drop_box(command):
    assert decision(command) is None


def test_non_bash_tools_are_left_to_permission_rules():
    assert hooks.pre_tool_use({"tool_name": "Read", "tool_input": {"file_path": "CREDENTIALS.txt"}}) is None


def test_session_start_outside_a_studio_does_nothing(tmp_path):
    assert hooks.session_start({"cwd": str(tmp_path)}) is None


def test_session_start_syncs_and_reports_the_drop_box(studio):
    (studio / ".claude" / "settings.json").write_text("{}")
    with open(studio / "CREDENTIALS.txt", "a") as box:
        box.write("SSH password: abc12345\n")
    out = hooks.session_start({"cwd": str(studio)})["hookSpecificOutput"]
    assert out["hookEventName"] == "SessionStart"
    assert "credential drop box has something in it" in out["additionalContext"]
    assert "refreshed .claude/settings.json" in out["additionalContext"]
    assert (studio / ".claude" / "settings.json").read_bytes() == (sync.TEMPLATES / "settings.json").read_bytes()


def test_session_start_reports_a_failed_backup_push(studio):
    (studio / ".git" / "wp-studio-push.json").write_text(json.dumps({"ok": False, "time": "T", "message": "auth expired"}))
    context = hooks.session_start({"cwd": str(studio)})["hookSpecificOutput"]["additionalContext"]
    assert "last GitHub backup push failed (T): auth expired" in context
