"""End to end: wpsite against a real WordPress over SSH (Docker; see compose.yml).

Run with: python3 -m pytest tests/e2e -q   (builds and starts the containers; needs Docker)
"""

import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parents[1] / "plugin"
SITE = "http://localhost:8089"
DB_PASSWORD = "dbpw-e2e-secret"
SSH_PASSWORD = "s3cret-Pass!word"


def compose(*args, check=True):
    return subprocess.run(["docker", "compose", "-f", str(HERE / "compose.yml")] + list(args),
                          capture_output=True, text=True, check=check)


@pytest.fixture(scope="module")
def server():
    compose("up", "-d", "--build", "--force-recreate")
    for _ in range(100):
        if compose("exec", "-T", "wp", "test", "-f", "/tmp/e2e-ready", check=False).returncode == 0:
            break
        time.sleep(3)
    else:
        raise RuntimeError("the WordPress container never became ready:\n" + compose("logs", check=False).stdout[-3000:])
    yield
    compose("down", "-v", check=False)


@pytest.fixture(scope="module")
def ws(server, tmp_path_factory):
    base = Path("/tmp") / ("wps-e2e-%d" % os.getpid())   # short: SSH socket paths are limited
    shutil.rmtree(base, ignore_errors=True)
    root = base / "ws"
    root.mkdir(parents=True)
    (root / ".wp-studio").write_text("e2e\n")
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    env = dict(os.environ, WPSTUDIO_KNOWN_HOSTS=str(base / "known_hosts"), WPSTUDIO_CONTROL_DIR=str(base / "cm"),
               WPSTUDIO_KEY=str(base / "key"), WPSTUDIO_SECRETS_HOME=str(base / "secrets"))
    run = lambda *a, **kw: wpsite(root, env, *a, **kw)
    subprocess.run([sys.executable, str(PLUGIN / "bin" / "studio"), "sync"], cwd=str(root), check=True, capture_output=True)
    run("init", "e2e", "--url", SITE)
    with open(root / "CREDENTIALS.txt", "a") as box:
        box.write("ssh deploy@127.0.0.1 -p 2289\nSSH password: %s\nWordPress folder on the server: /var/www/html\n" % SSH_PASSWORD)
    assert run("secrets", "file", "e2e").returncode == 0
    yield run, root, base
    shutil.rmtree(base, ignore_errors=True)


def wpsite(root, env, *args, path=None):
    environment = dict(env)
    if path is not None:
        environment["PATH"] = path
    return subprocess.run([sys.executable, str(PLUGIN / "bin" / "wpsite")] + list(args), cwd=str(root),
                          capture_output=True, text=True, env=environment)


def page(path="/"):
    with urllib.request.urlopen("%s%s?cb=%d" % (SITE, path, time.time() * 1e6), timeout=20) as response:
        return response.read().decode("utf-8", "replace")


def test_check_reports_the_real_site(ws):
    run, root, _ = ws
    result = run("check", "e2e")
    assert result.returncode == 0, result.stderr
    assert re.search(r"WordPress \d+\.\d+", result.stdout)
    assert "Home URL: %s" % SITE in result.stdout


def test_changes_need_a_backup_and_backups_are_verified(ws, tmp_path):
    run, root, _ = ws
    assert run("wp", "e2e", "option", "update", "blogdescription", "Before backup").returncode == 3
    # Review round 1: these changed the site through read-looking commands. Now they need a backup.
    exec_flag = "--exec=WP_CLI::add_hook('after_wp_load', function(){ update_option('blogname','pwned-exec'); });"
    assert run("wp", "e2e", "option", "get", "home", exec_flag).returncode == 3
    assert run("wp", "e2e", "db", "query", "SELECT 1",
               "--init-command=UPDATE wp_options SET option_value='pwned' WHERE option_name='blogname'").returncode == 3
    assert run("sh", "e2e", "ls >/dev/null\nwp option update blogname pwned-newline").returncode == 3
    php = tmp_path / "x.php"
    php.write_text("<?php\n")
    assert run("deploy", "e2e", str(php), "wp-content/mu-plugins/x.php").returncode == 3
    assert "pwned" not in run("wp", "e2e", "option", "get", "blogname").stdout
    result = run("backup", "e2e")
    assert result.returncode == 0, result.stderr
    assert "Database backup verified" in result.stdout
    assert run("wp", "e2e", "option", "update", "blogdescription", "Set by wpsite").returncode == 0
    assert run("wp", "e2e", "option", "get", "blogdescription").stdout.strip() == "Set by wpsite"


def test_database_password_never_reaches_the_output(ws):
    run, root, _ = ws
    out = run("sh", "e2e", "grep DB_PASSWORD wp-config.php").stdout + run("wp", "e2e", "config", "list").stdout
    # Review round 1: shapes the pattern-based redaction missed. Values are now masked by value.
    out += run("sh", "e2e", "grep DB_PASSWORD wp-config.php | cut -d\"'\" -f4").stdout
    out += run("wp", "e2e", "config", "list", "DB_PASSWORD", "--fields=value").stdout
    out += run("wp", "e2e", "config", "list", "--format=yaml").stdout
    assert DB_PASSWORD not in out
    assert "[redacted]" in out


def test_input_file_feeds_post_content(ws, tmp_path):
    run, root, _ = ws
    body = tmp_path / "body.html"
    body.write_text("<!-- wp:paragraph --><p>Body from a file</p><!-- /wp:paragraph -->")
    assert run("wp", "e2e", "--input", str(body), "post", "update", "1", "-").returncode == 0
    assert "Body from a file" in run("wp", "e2e", "post", "get", "1", "--field=post_content").stdout


def test_server_side_lint_stops_broken_php_with_no_local_php(ws, tmp_path):
    run, root, _ = ws
    bad = tmp_path / "bad.php"
    bad.write_text("<?php\nfunction broken( {\n")
    no_php = "/usr/bin:/bin:/usr/sbin:/sbin"   # no Homebrew php on this PATH
    result = run("deploy", "e2e", str(bad), "wp-content/mu-plugins/e2e-bad.php", path=no_php)
    assert result.returncode == 3 and "the server's PHP found a syntax error" in result.stderr
    assert run("sh", "e2e", "ls -a wp-content/mu-plugins").stdout.count("e2e-bad") == 0
    assert page().count("<html") == 1


def test_deploy_makes_new_php_live_through_the_opcode_cache(ws, tmp_path):
    run, root, _ = ws
    source = tmp_path / "e2e-meta.php"
    for version in ("one", "two"):
        source.write_text('<?php\nadd_action("wp_head", function () { echo "<meta name=\\"e2e\\" content=\\"%s\\">"; });\n' % version)
        result = run("deploy", "e2e", str(source), "wp-content/mu-plugins/e2e-meta.php")
        assert result.returncode == 0, result.stderr
        assert "PHP opcode cache reset" in result.stdout
        assert '<meta name="e2e" content="%s">' % version in page()
    assert "wpstudio-opcache" not in run("sh", "e2e", "ls wp-content").stdout


def test_folder_deploy_replaces_atomically_and_keeps_the_old_version(ws, tmp_path):
    run, root, _ = ws
    theme = tmp_path / "theme"
    (theme / "inc").mkdir(parents=True)
    (theme / "style.css").write_text("/*\nTheme Name: E2E Child\nTemplate: twentytwentyfive\n*/\n")
    (theme / "inc" / "v.php").write_text("<?php\nreturn 1;\n")
    (theme / ".DS_Store").write_text("junk")
    assert run("deploy", "e2e", str(theme), "wp-content/themes/e2e-child").returncode == 0
    (theme / "inc" / "v.php").write_text("<?php\nreturn 2;\n")
    result = run("deploy", "e2e", str(theme), "wp-content/themes/e2e-child")
    assert result.returncode == 0 and "Previous version saved" in result.stdout
    listing = run("sh", "e2e", "find wp-content/themes/e2e-child -type f | sort").stdout.split()
    assert listing == ["wp-content/themes/e2e-child/inc/v.php", "wp-content/themes/e2e-child/style.css"]
    assert "return 2;" in run("sh", "e2e", "cat wp-content/themes/e2e-child/inc/v.php").stdout
    assert "wpstudio" not in run("sh", "e2e", "ls -a wp-content/themes").stdout


def test_pull_downloads_into_work(ws):
    run, root, _ = ws
    assert run("pull", "e2e", "wp-content/themes/e2e-child").returncode == 0
    assert (root / "projects" / "e2e" / "work" / "wp-content" / "themes" / "e2e-child" / "style.css").is_file()


def test_key_login_replaces_the_password(ws):
    run, root, base = ws
    result = run("key", "e2e")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "now logs in with the studio key" in result.stdout
    assert run("check", "e2e").returncode == 0


def test_a_changed_host_key_stops_work_until_trusted(ws):
    run, root, base = ws
    compose("exec", "-T", "wp", "sh", "-c",
            "rm -f /etc/ssh/ssh_host_* && ssh-keygen -A >/dev/null && kill -HUP $(cat /run/sshd.pid)")
    subprocess.run(["ssh", "-o", "ControlPath=%s/%%C" % (base / "cm"), "-p", "2289", "-O", "exit", "deploy@127.0.0.1"],
                   capture_output=True)
    result = run("check", "e2e")
    assert result.returncode == 4 and "identity key" in result.stderr
    assert run("trust-host", "e2e").returncode == 0
    assert run("check", "e2e").returncode == 0
