"""wpsite commands, run against a fake `ssh` that records what it would have sent."""

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import PLUGIN, make_backup, make_site

WRAP = 'cd /www/acme/public && {\n%s\n}; s=$?; [ "$s" -eq 255 ] && s=254; exit "$s"'

FAKE_SSH = """#!/bin/sh
# Records every invocation; the shared-connection check fails once, then "is open".
printf '%s\\n' "$*" >> "$FAKE_SSH_LOG"
case "$*" in
  *"-O check"*) [ -f "$FAKE_SSH_LOG.master" ] && exit 0 || exit 1 ;;
  *"-f -N"*) touch "$FAKE_SSH_LOG.master"; exit 0 ;;
  *"-O exit"*) exit 0 ;;
esac
last=""; for a in "$@"; do last="$a"; done
printf 'ran: %s\\n' "$last"
"""


@pytest.fixture
def fake_ssh(tmp_path, monkeypatch):
    script = tmp_path / "ssh"
    script.write_text(FAKE_SSH)
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    log = tmp_path / "ssh.log"
    monkeypatch.setenv("WPSTUDIO_SSH", str(script))
    monkeypatch.setenv("FAKE_SSH_LOG", str(log))
    monkeypatch.setenv("WPSTUDIO_CONTROL_DIR", str(tmp_path / "cm"))
    return log


def wpsite(*args):
    return subprocess.run([sys.executable, str(PLUGIN / "bin" / "wpsite")] + list(args),
                          capture_output=True, text=True, env=dict(os.environ))


def test_init_creates_project_and_client_record(studio):
    result = wpsite("init", "acme", "--url", "acme.test/")
    assert result.returncode == 0
    claude_md = (studio / "projects" / "acme" / "CLAUDE.md").read_text()
    assert "{{" not in claude_md and "acme" in claude_md
    assert "https://acme.test" in (studio / "clients" / "acme.md").read_text()
    from wpstudio import workspace
    stored = workspace.secrets_dir(studio) / "acme" / "live.env"
    assert stat.S_IMODE(stored.stat().st_mode) == 0o600
    assert stat.S_IMODE(stored.parent.parent.stat().st_mode) == 0o700
    assert not (studio / "projects" / "acme" / ".secrets").exists()


def test_init_refuses_an_existing_project(studio):
    wpsite("init", "acme", "--url", "acme.test")
    assert wpsite("init", "acme", "--url", "acme.test").returncode == 2


def test_secrets_file_never_prints_values_and_wipes_the_box(studio):
    wpsite("init", "acme", "--url", "acme.test")
    with open(studio / "CREDENTIALS.txt", "a") as box:
        box.write("ssh acme@203.0.113.5 -p 2222\nSSH password: Hunter2-secret!\nWordPress folder on the server: /www/a\n")
    result = wpsite("secrets", "file", "acme")
    assert result.returncode == 0
    assert "Hunter2-secret!" not in result.stdout + result.stderr
    assert "Filed for acme: SSH_HOST, SSH_PASSWORD, SSH_PORT, SSH_USER, WP_PATH." in result.stdout
    assert wpsite("secrets", "status").stdout.strip() == "The drop box is empty."


def test_a_change_without_a_backup_is_refused_before_connecting(studio, fake_ssh):
    make_site(studio)
    result = wpsite("wp", "acme", "plugin", "delete", "hello")
    assert result.returncode == 3
    assert "wpsite backup acme" in result.stderr
    assert not fake_ssh.exists()


def test_a_change_with_a_fresh_backup_runs_and_is_logged(studio, fake_ssh):
    project = make_site(studio)
    make_backup(project)
    result = wpsite("wp", "acme", "option", "update", "blogname", "New name")
    assert result.returncode == 0
    assert result.stdout.strip() == "ran: " + WRAP % "wp option update blogname 'New name'"
    assert "wp option update blogname 'New name'" in (project / "activity.log").read_text()


def test_staging_backup_does_not_cover_live(studio, fake_ssh):
    project = make_site(studio)
    make_site(studio, env="staging")
    make_backup(project, env="staging")
    assert wpsite("wp", "acme", "plugin", "delete", "x").returncode == 3
    assert wpsite("wp", "acme:staging", "plugin", "delete", "x").returncode == 0


def test_reads_run_without_a_backup(studio, fake_ssh):
    make_site(studio)
    result = wpsite("wp", "acme", "plugin", "list")
    assert result.returncode == 0 and result.stdout.strip() == "ran: " + WRAP % "wp plugin list"


def test_printing_a_secret_constant_is_refused(studio, fake_ssh):
    project = make_site(studio)
    make_backup(project)
    assert wpsite("wp", "acme", "config", "get", "DB_PASSWORD").returncode == 3


def test_the_ssh_password_never_appears_on_a_command_line(studio, fake_ssh):
    make_site(studio)
    wpsite("wp", "acme", "core", "version")
    log = fake_ssh.read_text()
    assert "Hunter2-secret!" not in log
    assert "-p 2222" in log and "acme@203.0.113.5" in log


def test_shell_writes_need_a_backup(studio, fake_ssh):
    make_site(studio)
    assert wpsite("sh", "acme", "rm -rf wp-content/cache").returncode == 3
    assert wpsite("sh", "acme", "ls wp-content").returncode == 0


def test_unknown_site_and_missing_details_are_usage_errors(studio):
    assert "wpsite init nope" in wpsite("check", "nope").stderr
    wpsite("init", "acme", "--url", "acme.test")
    result = wpsite("check", "acme")
    assert result.returncode == 2 and "SSH_HOST, SSH_USER, WP_PATH" in result.stderr


def test_deploy_rejects_paths_outside_wordpress(studio, fake_ssh, tmp_path):
    make_site(studio)
    source = tmp_path / "x.php"
    source.write_text("<?php\n")
    assert wpsite("deploy", "acme", str(source), "../x.php").returncode == 2
    assert wpsite("deploy", "acme", str(source), "/etc/x.php").returncode == 2


def test_folder_deploy_cannot_replace_shared_folders(studio, fake_ssh, tmp_path):
    make_site(studio)
    (tmp_path / "theme").mkdir()
    for dest in ("wp-content/themes", "wp-content/plugins", "wp-content", "."):
        assert wpsite("deploy", "acme", str(tmp_path / "theme"), dest).returncode == 3


def test_outside_a_studio_wpsite_says_so(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = wpsite("list")
    assert result.returncode == 2 and "isn't inside a Claude WP Studio folder" in result.stderr


def test_deploy_needs_a_fresh_backup(studio, fake_ssh, tmp_path):
    make_site(studio)
    source = tmp_path / "x.php"
    source.write_text("<?php\n")
    result = wpsite("deploy", "acme", str(source), "wp-content/mu-plugins/x.php")
    assert result.returncode == 3 and "wpsite backup acme" in result.stderr
    assert not fake_ssh.exists()


def test_input_and_deploy_cannot_read_the_drop_box(studio, fake_ssh):
    project = make_site(studio)
    make_backup(project)
    assert wpsite("sh", "acme", "--input", str(studio / "CREDENTIALS.txt"), "cat").returncode == 3
    assert wpsite("deploy", "acme", str(studio / "CREDENTIALS.txt"), "wp-content/x.txt").returncode == 3


def test_the_servers_own_secrets_are_masked_in_any_output(studio, fake_ssh):
    make_site(studio)
    result = wpsite("sh", "acme", "echo db-pass-from-server")
    assert result.returncode == 0
    assert "db-pass-from-server" not in result.stdout and "[redacted]" in result.stdout


def test_pulled_archives_cannot_write_outside_their_folder(tmp_path):
    import io
    import tarfile as tf
    sys.path.insert(0, str(PLUGIN / "lib"))
    from wpstudio.cli import extract_inside
    archive = tmp_path / "x.tar"
    with tf.open(archive, "w") as tar:
        for name in ("ok.txt", "../escaped.txt", "sub/../../escaped2.txt"):
            info = tf.TarInfo(name); data = b"x"; info.size = len(data); tar.addfile(info, io.BytesIO(data))
        link = tf.TarInfo("link"); link.type = tf.SYMTYPE; link.linkname = "/etc/passwd"; tar.addfile(link)
    target = tmp_path / "work" / "wordpress"
    skipped = extract_inside(archive, target)
    assert sorted(skipped) == ["../escaped.txt", "link", "sub/../../escaped2.txt"]
    assert (target / "ok.txt").read_text() == "x"
    assert not (tmp_path / "work" / "escaped.txt").exists() and not (tmp_path / "escaped2.txt").exists()


def test_transformed_wp_config_output_is_refused_even_with_a_backup(studio, fake_ssh):
    project = make_site(studio)
    make_backup(project)
    for command in ("cat wp-config.php | rev", "od -c wp-config.php", "grep KEY wp-config.php | tr a-z A-Z"):
        result = wpsite("sh", "acme", command)
        assert result.returncode == 3 and "can't mask" in result.stderr


def test_json_escaped_secrets_are_masked(studio, fake_ssh):
    from wpstudio import remote
    from wpstudio.sites import resolve
    project = make_site(studio)
    site = resolve("acme", studio)
    site.server_secrets_file.write_text(json.dumps({"fetched": __import__("time").time(), "values": ["Zq8/kP2+vX9"]}))
    literals = remote.secret_literals(site)
    from wpstudio import redact
    assert redact.redact_line('{"value":"Zq8\\/kP2+vX9","name":"NONCE_SALT"}', literals) == '{"value":"[redacted]","name":"NONCE_SALT"}'


def test_the_studio_ssh_key_cannot_be_deployed(studio, fake_ssh, monkeypatch, tmp_path):
    project = make_site(studio)
    make_backup(project)
    key = tmp_path / "key"
    key.write_text("PRIVATE")
    result = wpsite("deploy", "acme", str(key), "wp-content/uploads/k.txt")
    assert result.returncode == 3


def test_http_get_uses_curl_and_reads_status_headers_and_body(tmp_path):
    """Web requests go through curl: Apple's Python can't handshake with common CDNs."""
    import http.server
    import threading
    sys.path.insert(0, str(PLUGIN / "lib"))
    from wpstudio.cli import http_get

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(418)
            self.send_header("X-Cache", "HIT")
            self.end_headers()
            self.wfile.write(b"wpstudio-opcache:reset")

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.handle_request, daemon=True).start()
    status, headers, body = http_get("http://127.0.0.1:%d/x" % server.server_port)
    assert (status, headers["x-cache"], body) == (418, "HIT", "wpstudio-opcache:reset")
    assert http_get("http://127.0.0.1:9/unreachable", timeout=2)[0] is None
