"""Run commands on a site over one shared SSH connection.

Why one shared connection: managed hosts throttle rapid logins (about eight quick logins got a
correct password refused on one host), so `wpsite` opens a master connection once and multiplexes
every later command over it for ten minutes.

The master is started explicitly with `-f -N` and its output sent to a file. Letting `ssh` start
it implicitly (ControlMaster=auto) leaves the backgrounded master holding our capture pipes open,
which hangs any caller that reads to end-of-file.

Password logins go through SSH_ASKPASS (OpenSSH 8.4+ with SSH_ASKPASS_REQUIRE=force): the password
travels in an environment variable to a two-line helper and is never on a command line or in a
terminal prompt.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import IO, List, Optional, Sequence

from . import PLUGIN_ROOT, envfile, redact
from .sites import Site

ASKPASS = PLUGIN_ROOT / "lib" / "wpstudio" / "askpass.sh"
EXIT_CONNECT = 4
EXIT_REMOTE = 5

HOST_KEY_CHANGED = "REMOTE HOST IDENTIFICATION HAS CHANGED"


class RemoteError(Exception):
    def __init__(self, message: str, code: int = EXIT_CONNECT):
        super().__init__(message)
        self.code = code


def ssh_binary() -> str:
    return os.environ.get("WPSTUDIO_SSH", "ssh")


# A Unix socket path can be at most 104 bytes on macOS. ssh adds "/" + 40 hex (%C) + a 17-byte
# temporary suffix while it creates the socket.
SOCKET_PATH_MAX = 104
SOCKET_NAME_LEN = 1 + 40 + 17


def control_dir() -> Path:
    """Where shared-connection sockets live: ~/.ssh/wpstudio, or a short /tmp folder when that's too long."""
    path = Path(os.environ.get("WPSTUDIO_CONTROL_DIR", str(Path.home() / ".ssh" / "wpstudio")))
    if len(str(path).encode("utf-8")) + SOCKET_NAME_LEN > SOCKET_PATH_MAX:
        path = Path("/tmp") / ("wpstudio-%d" % os.getuid())
    path.mkdir(parents=True, exist_ok=True)
    if path.stat().st_uid != os.getuid():
        raise RemoteError("%s belongs to another user; remove it and try again." % path)
    os.chmod(path, 0o700)
    return path


def known_hosts() -> Optional[str]:
    return os.environ.get("WPSTUDIO_KNOWN_HOSTS")


def _common_options(site: Site) -> List[str]:
    opts = [
        "-p", site.port,
        "-o", "ControlPath=%s/%%C" % control_dir(),
        "-o", "ServerAliveInterval=30",
        "-o", "ConnectTimeout=20",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "LogLevel=ERROR",
    ]
    if known_hosts():
        opts += ["-o", "UserKnownHostsFile=%s" % known_hosts()]
    key = site.values.get("SSH_KEY")
    if key:
        opts += ["-i", key, "-o", "IdentitiesOnly=yes"]
    return opts


def _target(site: Site) -> str:
    return "%s@%s" % (site.values["SSH_USER"], site.values["SSH_HOST"])


def auth_env(site: Site) -> dict:
    env = dict(os.environ)
    password = site.values.get("SSH_PASSWORD")
    if password:
        env["WPSTUDIO_SSH_PASSWORD"] = password
        env["SSH_ASKPASS"] = str(ASKPASS)
        env["SSH_ASKPASS_REQUIRE"] = "force"
        env.setdefault("DISPLAY", "wpstudio:0")
    return env


def _auth_options(site: Site) -> List[str]:
    if site.values.get("SSH_KEY"):
        return ["-o", "BatchMode=yes"]  # IdentitiesOnly (in _common_options) offers just this key
    if site.values.get("SSH_PASSWORD"):
        # Go straight to the password. Otherwise ssh first offers every key in the Mac's SSH agent,
        # and a server allowing six attempts disconnects ("Too many authentication failures")
        # before the password is ever tried.
        return ["-o", "PreferredAuthentications=password,keyboard-interactive", "-o", "PubkeyAuthentication=no",
                "-o", "NumberOfPasswordPrompts=1"]
    return ["-o", "BatchMode=yes"]


def _explain_failure(site: Site, stderr: str) -> str:
    if HOST_KEY_CHANGED in stderr:
        return (
            "The server's identity key for %s has changed since the studio last connected. Hosts sometimes "
            "rotate keys, but this is also what an interception looks like. Don't connect until the operator "
            "confirms with the host that they rotated it; then run: wpsite trust-host %s"
            % (site.values["SSH_HOST"], site.spec)
        )
    lowered = stderr.lower()
    if "permission denied" in lowered:
        if site.values.get("SSH_PASSWORD") or site.values.get("SSH_KEY"):
            return "The server refused the login for %s. The username, password or key is wrong, or the host is " \
                   "rate-limiting logins; ask the operator to re-check the details in their hosting dashboard." % site.spec
        return "The server wants a password or key for %s and none is on file. Ask the operator to add the SSH " \
               "password to CREDENTIALS.txt, then run: wpsite secrets file %s" % (site.spec, site.spec)
    if "could not resolve" in lowered or "name or service not known" in lowered:
        return "The SSH host name for %s doesn't resolve. Check the SSH host in the hosting dashboard." % site.spec
    if "connection refused" in lowered or "timed out" in lowered or "no route" in lowered:
        return "Couldn't reach %s on port %s. The host, the port, or a firewall is wrong (managed hosts often use a " \
               "custom port shown in their dashboard)." % (site.values["SSH_HOST"], site.port)
    return "SSH to %s failed: %s" % (site.spec, stderr.strip() or "no details from ssh")


def ensure_master(site: Site) -> None:
    """Open the shared connection if it isn't already open."""
    base = [ssh_binary()] + _common_options(site)
    check = subprocess.run(base + ["-O", "check", _target(site)], stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if check.returncode == 0:
        return
    with tempfile.TemporaryFile() as err:
        start = subprocess.run(
            base + _auth_options(site) + ["-o", "ControlMaster=yes", "-o", "ControlPersist=600", "-f", "-N", _target(site)],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=err, env=auth_env(site),
        )
        err.seek(0)
        stderr = err.read().decode("utf-8", "replace")
    if start.returncode != 0:
        raise RemoteError(_explain_failure(site, stderr))


def close_master(site: Site) -> None:
    subprocess.run([ssh_binary()] + _common_options(site) + ["-O", "exit", _target(site)],
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def remote_command(site: Site, command: str) -> str:
    """Run `command` in the WordPress folder.

    ssh reports its own failures as exit status 255, so a remote command's own 255 (PHP's lint uses
    it for a syntax error) is passed back as 254. That keeps 255 meaning "ssh failed" and nothing else.
    """
    return 'cd %s && {\n%s\n}; s=$?; [ "$s" -eq 255 ] && s=254; exit "$s"' % (shlex.quote(site.values["WP_PATH"]), command)


def wp_command(args: Sequence[str]) -> str:
    return "wp " + " ".join(shlex.quote(a) for a in args)


def run(site: Site, command: str, stdin: Optional[IO[bytes]] = None, stdout: Optional[IO[bytes]] = None,
        in_wp_root: bool = True) -> "subprocess.CompletedProcess[bytes]":
    """Run a command on the site. With `stdout` given, output streams there; otherwise it's captured."""
    ensure_master(site)
    full = remote_command(site, command) if in_wp_root else command
    argv = [ssh_binary()] + _common_options(site) + ["-o", "ControlMaster=no", "-o", "BatchMode=yes",
                                                     _target(site), full]
    proc = subprocess.run(argv, stdin=stdin if stdin is not None else subprocess.DEVNULL,
                          stdout=stdout if stdout is not None else subprocess.PIPE,
                          stderr=subprocess.PIPE)
    stderr = proc.stderr.decode("utf-8", "replace")
    if proc.returncode == 255:
        raise RemoteError(_explain_failure(site, stderr))
    return proc


SERVER_SECRETS_MAX_AGE = 24 * 60 * 60
SERVER_SECRETS_COMMAND = "wp config list --format=json --skip-plugins --skip-themes"


def server_secrets(site: Site, refresh: bool = False) -> List[str]:
    """The site's own secret values (database password, keys and salts), read from wp-config.php.

    Redaction by output shape can't cover every way a value can be printed (`cut -d"'" -f4`, YAML,
    a define() split over two lines), so wpsite learns the actual values once a day and masks them
    wherever they appear. They're kept beside the site's connection file, in the secrets store,
    and the commit scan refuses them too.
    """
    cache = site.server_secrets_file
    if not refresh and cache.is_file():
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
            if time.time() - float(data.get("fetched", 0)) < SERVER_SECRETS_MAX_AGE:
                return list(data.get("values", []))
        except (OSError, ValueError):
            pass
    proc = run(site, SERVER_SECRETS_COMMAND)
    try:
        rows = json.loads(proc.stdout.decode("utf-8", "replace") or "[]") if proc.returncode == 0 else None
    except ValueError:
        rows = None
    if not isinstance(rows, list):
        return []  # no readable wp-config.php here; shape-based redaction still applies
    values = sorted({str(r.get("value", "")) for r in rows if isinstance(r, dict)
                     and str(r.get("name", "")).upper() in redact.SECRET_CONSTANTS and len(str(r.get("value", ""))) >= 4})
    cache.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(cache), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump({"fetched": time.time(), "values": values}, handle)
    return values


def escaped_forms(value: str) -> List[str]:
    """The ways a value shows up in output: as is, JSON-escaped (PHP's json_encode also writes / as \\/),
    and with shell or PHP quote escaping."""
    as_json = json.dumps(value)[1:-1]
    forms = {value, as_json, as_json.replace("/", "\\/"), value.replace("/", "\\/"),
             value.replace("'", "\\'"), value.replace('"', '\\"'), value.replace("'", "'\\''")}
    return [f for f in forms if f]


def secret_literals(site: Site, fetch: bool = True) -> List[str]:
    """Every value to mask in this site's output, in every escaped form: everything secret in its
    connection file, plus the server's own secrets."""
    values = envfile.secret_values(site.values)
    if fetch and site.values.get("WP_PATH"):
        learned = server_secrets(site)
        if not learned and not site.server_secrets_file.is_file():
            sys.stderr.write("Note: couldn't read this site's wp-config.php secrets, so output is masked by "
                             "pattern only. Run `wpsite check %s` once WordPress answers.\n" % site.spec)
        values += learned
    return sorted({form for v in values for form in escaped_forms(v)}, key=len, reverse=True)


def run_text(site: Site, command: str, in_wp_root: bool = True, stdin: Optional[IO[bytes]] = None):
    """Run and return (exit code, stdout text, stderr text), both redacted."""
    literals = secret_literals(site)
    proc = run(site, command, stdin=stdin, in_wp_root=in_wp_root)
    out = redact.redact_text(proc.stdout.decode("utf-8", "replace"), literals)
    err = redact.redact_text(proc.stderr.decode("utf-8", "replace"), literals)
    return proc.returncode, out, err
