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
    # Review round 1: positions the old separator regex missed.
    "if ssh deploy@1.2.3.4 true; then echo ok; fi", "{ ssh u@h ls; }", "! ssh u@h", "\"ssh\" u@h",
    "timeout 5 ssh u@h", "env FOO=1 ssh u@h", "eval ssh u@h", "xargs -n1 ssh < hosts", "ls\nssh u@h",
    # Review round 2: option values, bundled -lc, here-strings, pipes into a shell, git's ssh command.
    "sudo -u x ssh u@h", "env -u FOO ssh u@h", "env -S 'ssh u@h'", "exec -a x ssh u@h", "timeout 5s ssh u@h",
    "xargs -I {} ssh {}", "sh -lc 'ssh u@h'", "bash -ec 'ssh u@h'", "bash<<<'ssh u@h'", "echo 'ssh u@h' | bash",
    "function f { ssh u@h; }; f", "coproc ssh u@h", "watch -n1 ssh u@h", "git -c core.sshCommand='ssh u@h' fetch x",
])

def test_raw_remote_access_is_blocked(command):
    assert decision(command) == "deny"


@pytest.mark.parametrize("command", [
    "wpsite wp acme plugin list", "ssh-keygen -t ed25519 -f k", "git commit -m 'Set up SSH key login'",
    "rsync -a src/ dest/", "grep -r sshd_config docs", "echo 'use wpsite instead of SSH'",
    "wpsite deploy acme theme wp-content/themes/acme", "git push origin HEAD",
    "grep -ri SSH docs", "find . -name '*.php' -newer x",
])

def test_ordinary_commands_pass(command):
    assert decision(command) is None


@pytest.mark.parametrize("command", [
    "cat CREDENTIALS.txt", "cat credentials.txt", "cat CRED*.txt", "tail -n5 CREDENTIALS.tx?",
    "python3 -c \"open('CREDENTIALS.txt').read()\"", "wpsite secrets file acme && cat CREDENTIALS.txt",
    "cat ~/.config/wp-studio/secrets/x/acme/live.env", "grep -r PASSWORD ~/.config/wp-studio",
    "ls ~/.config/*/secrets", "cp $HOME/.config/wp-studio/secrets/x/acme/live.env /tmp/x",
    "ssh -i ~/.ssh/wpstudio_ed25519 u@h", "ssh -o ControlPath=~/.ssh/wpstudio/%C u@h",
    # Review round 2: path tricks and globs.
    "grep -r SSH_PASSWORD ~/.config/./wp-studio", "grep -r SSH_PASSWORD ~/.config//wp-studio",
    "cd ~/.config && grep -r PASS wp-studio", "cat ~/.ssh/wpstu?io_ed25519", "cat ~/.ssh/wpst[u]dio_ed25519",
    "grep -r PASS ~/.config",
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


@pytest.mark.parametrize("command,agent,denied", [
    ("wpsite wp acme plugin list", "wp-studio:qa-checker", False),
    ("wpsite check acme && wpsite pull acme wp-content/themes/x", "wp-studio:site-scout", False),
    ("wpsite sh acme 'ls wp-content'", "wp-studio:site-scout", False),
    ("wpsite wp acme plugin deactivate x", "wp-studio:qa-checker", True),
    ("wpsite deploy acme x wp-content/mu-plugins/x.php", "wp-studio:site-scout", True),
    ("wpsite sh acme 'rm -rf wp-content/cache'", "wp-studio:qa-checker", True),
    ("wpsite purge acme", "wp-studio:page-converter", True),
    ("wpsite wp acme --input x.html post update 1 -", "wp-studio:page-converter", True),
    ("wpsite wp acme plugin deactivate x", None, False),
    ("bash -c 'wpsite wp acme option update a b'", "wp-studio:qa-checker", True),
    ("python3 /x/bin/wpsite wp acme option update a b", "wp-studio:qa-checker", True),
])
def test_read_only_agents_cannot_change_sites(command, agent, denied):
    assert (hooks.check_bash(command, agent) is not None) is denied


@pytest.mark.parametrize("command", ["git commit -m 'Set up ssh key login'", "grep -r ssh docs"])
def test_lowercase_ssh_anywhere_is_refused_by_design(command):
    # Fail closed (review round 2): the hook can't tell a quoted string that will run (`bash -lc '…'`,
    # `bash <<<'…'`, `git -c core.sshCommand='…'`) from one that won't, so the lowercase program
    # name is refused anywhere. Writing "SSH" or `grep -ri` gets ordinary work through.
    assert decision(command) == "deny"
