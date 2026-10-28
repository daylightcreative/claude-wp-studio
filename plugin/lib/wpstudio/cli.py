"""`wpsite`: the studio's one route to a WordPress site.

Exit codes: 0 ok, 2 usage, 3 refused by a safety rule, 4 can't connect, 5 the remote command failed.
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
import posixpath
import re
import secrets as pysecrets
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from . import PLUGIN_ROOT, __version__, dropbox, envfile, guard, redact, remote, workspace
from .sites import Site, SiteError, list_sites, parse_spec, resolve

EXIT_USAGE = 2
EXIT_REFUSED = 3

# Folders a whole-folder deploy may never replace: replacing them would delete everything else in them.
PROTECTED_DIRS = {
    "", ".", "wp-admin", "wp-includes", "wp-content", "wp-content/uploads", "wp-content/plugins",
    "wp-content/themes", "wp-content/mu-plugins", "wp-content/languages", "wp-content/upgrade",
}
SKIP_NAMES = {".DS_Store", ".git", ".svn", "node_modules", "__pycache__"}
CACHE_COMMANDS = (
    ("kinsta cache", "wp kinsta cache purge --all"),
    ("litespeed-purge", "wp litespeed-purge all"),
    ("rocket clean", "wp rocket clean --confirm"),
    ("w3-total-cache flush", "wp w3-total-cache flush all"),
    ("super-cache flush", "wp super-cache flush"),
    ("sg purge", "wp sg purge"),
)
EDGE_HEADERS = ("cf-cache-status", "x-kinsta-cache", "x-cache", "x-litespeed-cache", "x-proxy-cache",
                "x-sucuri-cache", "x-varnish", "age")
SENSITIVE_ARG = re.compile(r"^(--[\w-]*(pass|key|secret|token|salt)[\w-]*=).+$", re.I)


class Refused(Exception):
    pass


def say(message: str = "") -> None:
    print(message, flush=True)


def stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def human_age(seconds: float) -> str:
    minutes = int(seconds // 60)
    if minutes < 60:
        return "%d min" % minutes
    return "%dh %02dmin" % (minutes // 60, minutes % 60)


def log_activity(site: Site, command: str) -> None:
    """Append a line to the project's activity log (secrets stripped), so 'what changed?' has an answer."""
    words = []
    for word in shlex.split(command) if command else []:
        words.append(SENSITIVE_ARG.sub(lambda m: m.group(1) + redact.MASK, word))
    line = redact.redact_line(" ".join(shlex.quote(w) for w in words), remote.secret_literals(site))
    with open(site.project / "activity.log", "a", encoding="utf-8") as handle:
        handle.write("%s\t%s\t%s\n" % (dt.datetime.now().isoformat(timespec="seconds"), site.env, line))


def refuse_secret_path(root: Path, path: Path, what: str) -> None:
    """Never let a wpsite command read or write a secret: the drop box or the secrets store."""
    resolved = path.expanduser().resolve()
    store = workspace.secrets_home().resolve()
    box = workspace.dropbox_path(root).resolve()
    key = key_path().resolve()
    ssh_dir = (Path.home() / ".ssh").resolve()
    if (resolved in (box, store, key, key.with_suffix(".pub")) or store in resolved.parents or ssh_dir == resolved
            or ssh_dir in resolved.parents or resolved.name.lower() == "credentials.txt"):
        raise Refused("Refused: %s would read or write the credential drop box or the secrets store." % what)


def require_fresh_backup(site: Site, what: str) -> None:
    found = guard.latest_backup(site.backups)
    if found is not None and found[1] <= guard.BACKUP_MAX_AGE:
        return
    age = "there is no verified database backup of it yet" if found is None else \
        "its newest verified database backup is %s old (the limit is %s)" % (human_age(found[1]), human_age(guard.BACKUP_MAX_AGE))
    raise Refused(
        "Refused: %s can change %s, and %s.\nTake one first, then run the same command again:\n  wpsite backup %s"
        % (what, site.spec, age, site.spec)
    )


# ── commands ────────────────────────────────────────────────────────────────────────────────────


def cmd_list(args, root: Path) -> int:
    found = list_sites(root)
    if not found:
        say("No projects yet. Create one with: wpsite init <name> --url <site address>")
        return 0
    for site in found:
        if not site.values:
            say("%-28s no connection details yet" % site.spec)
            continue
        missing = site.missing_for_ssh()
        auth = "key" if site.values.get("SSH_KEY") else ("password" if site.values.get("SSH_PASSWORD") else "no login")
        backup = guard.latest_backup(site.backups)
        backup_text = "no backup" if backup is None else "backup %s ago" % human_age(backup[1])
        state = ("missing " + ", ".join(missing)) if missing else "ready (%s)" % auth
        say("%-28s %-40s %-22s %s" % (site.spec, site.values.get("SITE_URL", "(no URL)"), state, backup_text))
    return 0


def _fill(template: Path, values: Dict[str, str]) -> str:
    text = template.read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace("{{%s}}" % key, value)
    return text


def cmd_init(args, root: Path) -> int:
    slug, env = parse_spec(args.slug)
    if env != "live":
        raise SiteError("Create the project first (wpsite init %s --url …); environments like :%s are added by "
                        "filing their details with: wpsite secrets file %s:%s" % (slug, env, slug, env))
    url = dropbox._clean("SITE_URL", args.url)
    project = workspace.projects_dir(root) / slug
    if project.exists():
        raise SiteError("projects/%s already exists." % slug)
    for sub in ("backups", "work"):
        (project / sub).mkdir(parents=True, exist_ok=True)
    fill = {"slug": slug, "url": url, "date": dt.date.today().isoformat()}
    templates = PLUGIN_ROOT / "skills" / "new-site"
    (project / "CLAUDE.md").write_text(_fill(templates / "project-CLAUDE.md", fill), encoding="utf-8")
    client_doc = workspace.clients_dir(root) / ("%s.md" % slug)
    client_doc.parent.mkdir(exist_ok=True)
    if not client_doc.exists():
        client_doc.write_text(_fill(templates / "client.md", fill), encoding="utf-8")
    envfile.write(Site(slug=slug, env="live", root=root).env_file, {"SITE_URL": url},
                  header="Connection details for %s (live). Filed by wpsite; never commit or paste this file." % slug)
    say("Created projects/%s and clients/%s.md." % (slug, slug))
    say("Next: ask the operator to fill in CREDENTIALS.txt, then run: wpsite secrets file %s" % slug)
    return 0


def cmd_secrets(args, root: Path) -> int:
    box = workspace.dropbox_path(root)
    dropbox.ensure(box)
    if args.action == "wipe":
        dropbox.wipe(box)
        say("The drop box is blank again.")
        return 0
    if args.action == "status":
        if not args.site:
            say("The drop box has something in it." if dropbox.has_content(box) else "The drop box is empty.")
            return 0
        site = resolve(args.site, root, need_connection=False)
        if not site.values:
            say("%s has no connection details yet." % site.spec)
            return 0
        say("%s has: %s" % (site.spec, ", ".join(sorted(site.values))))
        missing = site.missing_for_ssh()
        if missing:
            say("Still needed for SSH: %s" % ", ".join(missing))
        return 0
    # file
    if not args.site:
        raise SiteError("Say which site these details belong to, e.g.: wpsite secrets file acme  (or acme:staging)")
    slug, env = parse_spec(args.site)
    site = Site(slug=slug, env=env, root=root)
    if not site.project.is_dir():
        raise SiteError("There's no project called %r yet. Create it first: wpsite init %s --url <site address>" % (slug, slug))
    parsed = dropbox.parse(box.read_text(encoding="utf-8"))
    if not parsed.values:
        dropbox.wipe(box)
        reasons = ["nothing on the labeled lines"]
        if parsed.unrecognized_lines:
            reasons.append("%d line(s) without a label" % parsed.unrecognized_lines)
        reasons.extend(parsed.refused)
        say("Nothing was filed (%s). The drop box was cleared for safety." % "; ".join(reasons))
        say("Ask the operator to put each detail on its labeled line (for example 'SSH password: …') and tell you when it's there.")
        return EXIT_REFUSED
    existing = envfile.read(site.env_file) if site.env_file.is_file() else {}
    changed = sorted(k for k, v in parsed.values.items() if existing.get(k) != v)
    merged = dict(existing)
    merged.update(parsed.values)
    envfile.write(site.env_file, merged,
                  header="Connection details for %s. Filed by wpsite; never commit or paste this file." % site.spec)
    dropbox.wipe(box)
    say("Filed for %s: %s." % (site.spec, ", ".join(changed) if changed else "nothing new (same values as before)"))
    if parsed.unrecognized_lines:
        say("Ignored %d line(s) without a label (not shown)." % parsed.unrecognized_lines)
    for note in parsed.refused:
        say("Not filed: %s." % note)
    say("The drop box is blank again.")
    missing = [k for k in guard_required() if not merged.get(k)]
    if missing:
        say("Still needed before connecting: %s" % ", ".join(missing))
    else:
        say("Next: wpsite check %s" % site.spec)
    return 0


def guard_required() -> Sequence[str]:
    from .sites import REQUIRED_FOR_SSH
    return REQUIRED_FOR_SSH


def http_get(url: str, timeout: int = 20) -> Tuple[Optional[int], Dict[str, str], str]:
    """GET a URL with the Mac's curl: (status, lower-cased headers, first 64 KB of the body).

    Not Python's urllib: the Python that ships with Apple's Command Line Tools links LibreSSL 2.8,
    which fails the TLS handshake with common CDNs ("tlsv1 alert protocol version"), and that is the
    Python the studio runs on. curl uses the system TLS stack and works.
    """
    with tempfile.NamedTemporaryFile() as body_file:
        proc = subprocess.run(
            [os.environ.get("WPSTUDIO_CURL", "curl"), "-sS", "-m", str(timeout), "-A", "Mozilla/5.0 (wp-studio)",
             "-D", "-", "-o", body_file.name, url],
            capture_output=True, text=True)
        if proc.returncode != 0:
            return None, {"error": proc.stderr.strip()[:200]}, ""
        body = body_file.read(65536).decode("utf-8", "replace")
    status, headers = None, {}
    for line in proc.stdout.splitlines():
        if line.startswith("HTTP/"):
            parts = line.split()
            status = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
            headers = {}
        elif ":" in line:
            key, _, value = line.partition(":")
            headers[key.strip().lower()] = value.strip()
    return status, headers, body


def _probe_http(url: str) -> Tuple[Optional[int], Dict[str, str]]:
    if not url:
        return None, {}
    status, headers, _ = http_get(url + ("&" if "?" in url else "?") + "wpstudio-cb=%d" % time.time(), timeout=15)
    return status, headers


CHECK_SCRIPT = r"""
v() { printf '%s=%s\n' "$1" "$2"; }
v wp_version "$(wp core version 2>/dev/null)"
v home "$(wp option get home 2>/dev/null)"
v blog_public "$(wp option get blog_public 2>/dev/null)"
v theme "$(wp theme list --status=active --field=name 2>/dev/null | head -1)"
v php_cli "$(php -r 'echo PHP_VERSION;' 2>/dev/null)"
v wp_cli "$(wp cli version 2>/dev/null | sed 's/^WP-CLI //')"
v mu_plugins "$(wp plugin list --status=must-use --field=name 2>/dev/null | tr '\n' ' ')"
for c in __CACHE_COMMANDS__; do wp cli has-command "$c" >/dev/null 2>&1 && v cache_cmd "$c"; done
v disk "$(df -h . 2>/dev/null | awk 'NR==2 {print $5" used of "$2}')"
"""


def _remote_facts(site: Site) -> Dict[str, List[str]]:
    script = CHECK_SCRIPT.replace("__CACHE_COMMANDS__", " ".join(shlex.quote(c) for c, _ in CACHE_COMMANDS))
    code, out, err = remote.run_text(site, script)
    facts: Dict[str, List[str]] = {}
    for line in out.splitlines():
        key, sep, value = line.partition("=")
        if sep:
            facts.setdefault(key, []).append(value.strip())
    return facts


def cmd_check(args, root: Path) -> int:
    site = resolve(args.site, root)
    remote.server_secrets(site, refresh=True)
    facts = _remote_facts(site)
    first = lambda k: (facts.get(k) or [""])[0]
    if not first("wp_version"):
        say("Connected to %s, but WP-CLI found no WordPress at %s. Check WP_PATH (the WordPress folder on the server)."
            % (site.spec, site.values["WP_PATH"]))
        return remote.EXIT_REMOTE
    home = first("home")
    say("Connected to %s." % site.spec)
    say("WordPress %s, WP-CLI %s, PHP %s on the command line (the website's PHP can differ)."
        % (first("wp_version"), first("wp_cli") or "?", first("php_cli") or "?"))
    say("Home URL: %s   Active theme: %s" % (home, first("theme") or "?"))
    if first("blog_public") == "0":
        say("Search engines are told NOT to index this site (Settings → Reading). Right for staging; on a live site it's a problem.")
    mu = first("mu_plugins")
    if mu:
        say("Must-use plugins: %s" % mu)
    caches = facts.get("cache_cmd", [])
    say("Page cache: %s" % (", ".join(caches) if caches else "no cache plugin command found (wpsite purge will flush the object cache only)"))
    if first("disk"):
        say("Disk: %s" % first("disk"))
    if site.values.get("SITE_URL") and home and home.rstrip("/") != site.values["SITE_URL"].rstrip("/"):
        say("Note: the home URL on the server differs from the SITE_URL on file (%s)." % site.values["SITE_URL"])
    status, headers = _probe_http(home or site.values.get("SITE_URL", ""))
    if status is None:
        say("The website itself didn't answer from here.")
    else:
        edge = ["%s: %s" % (h, headers[h]) for h in EDGE_HEADERS if h in headers]
        say("Website answered HTTP %s%s." % (status, ("; cache headers " + "; ".join(edge)) if edge else ""))
        if "cf-ray" in headers:
            say("Cloudflare sits in front of this site: its edge cache may need clearing too.")
    backup = guard.latest_backup(site.backups)
    say("Newest verified backup: %s" % ("none" if backup is None else human_age(backup[1]) + " old"))
    return 0


def _take_input(args) -> List[str]:
    """`--input FILE` may come before or after the site name; take it out of the command words."""
    rest = list(args.args)
    while rest and (rest[0] == "--input" or rest[0].startswith("--input=")):
        if rest[0] == "--input":
            if len(rest) < 2:
                raise SiteError("--input needs a file.")
            args.input, rest = rest[1], rest[2:]
        else:
            args.input, rest = rest[0].split("=", 1)[1], rest[1:]
    if rest and rest[0] == "--":
        rest = rest[1:]
    return rest


def cmd_wp(args, root: Path) -> int:
    site = resolve(args.site, root)
    wp_args = _take_input(args)
    if wp_args and wp_args[0] == "wp":
        wp_args = wp_args[1:]
    if not wp_args:
        raise SiteError("Give a WP-CLI command, e.g.: wpsite wp %s plugin list" % site.spec)
    command = remote.wp_command(wp_args)
    writes = not guard.wp_is_read_only(wp_args)
    if writes:
        require_fresh_backup(site, "`%s`" % command)
    if redact.wp_secret_get(wp_args):
        raise Refused("Refused: `%s` would print a secret into the conversation. Work with it on the server "
                      "instead (for example `wpsite sh %s 'wp config has DB_PASSWORD'`)." % (command, site.spec))
    code, out, err = _run_with_input(site, command, args.input)
    if writes:
        log_activity(site, command)
    sys.stdout.write(out)
    sys.stderr.write(err)
    return 0 if code == 0 else remote.EXIT_REMOTE


def _run_with_input(site: Site, command: str, input_path: Optional[str]):
    if not input_path:
        return remote.run_text(site, command)
    source = Path(input_path).expanduser()
    refuse_secret_path(site.root, source, "--input %s" % input_path)
    if not source.is_file():
        raise SiteError("--input file %s doesn't exist." % input_path)
    with open(source, "rb") as handle:
        return remote.run_text(site, command, stdin=handle)


def cmd_sh(args, root: Path) -> int:
    site = resolve(args.site, root)
    command = args.command
    if not guard.config_output_is_maskable(command):
        raise Refused("Refused: that command names wp-config.php and could print its passwords and keys in a form "
                      "wpsite can't mask. Read it with grep, cat, head or tail, and change it with "
                      "`wpsite wp %s config set …`." % site.spec)
    if not guard.shell_is_read_only(command):
        require_fresh_backup(site, "`%s`" % command)
        log_activity(site, command)
    code, out, err = _run_with_input(site, command, args.input)
    sys.stdout.write(out)
    sys.stderr.write(err)
    return 0 if code == 0 else remote.EXIT_REMOTE


# ── backups ─────────────────────────────────────────────────────────────────────────────────────


def _stream_to(site: Site, command: str, destination: Path, compress: bool) -> int:
    """Run a remote command and stream its stdout into a local file. Returns the remote exit code."""
    remote.ensure_master(site)
    argv = [remote.ssh_binary()] + remote._common_options(site) + [
        "-o", "ControlMaster=no", "-o", "BatchMode=yes", remote._target(site), remote.remote_command(site, command)]
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".partial")
    with tempfile.TemporaryFile() as err:
        with open(partial, "wb") as raw:
            sink = gzip.GzipFile(fileobj=raw, mode="wb") if compress else raw
            proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=err)
            assert proc.stdout is not None
            for chunk in iter(lambda: proc.stdout.read(1 << 16), b""):
                sink.write(chunk)
            code = proc.wait()
            if compress:
                sink.close()
        err.seek(0)
        stderr = err.read().decode("utf-8", "replace")
    if code != 0:
        partial.unlink()
        if code == 255:
            raise remote.RemoteError(remote._explain_failure(site, stderr))
        sys.stderr.write(redact.redact_text(stderr, remote.secret_literals(site)))
        return code
    partial.rename(destination)
    return 0


def verify_dump(dump: Path) -> Tuple[bool, int, str]:
    """A dump counts only if it decompresses, has tables, and mysqldump finished writing it."""
    tables = 0
    tail = b""
    try:
        with gzip.open(dump, "rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                tables += chunk.count(b"CREATE TABLE")
                tail = (tail + chunk)[-4096:]
    except (OSError, EOFError) as err:
        return False, 0, "the file is damaged (%s)" % err
    if tables == 0:
        return False, 0, "it contains no tables"
    if b"Dump completed" not in tail:
        return False, tables, "it ends early (mysqldump didn't finish)"
    return True, tables, ""


def backup_database(site: Site) -> Path:
    dump = site.backups / ("db-%s.sql.gz" % stamp())
    code = _stream_to(site, "wp db export - --single-transaction", dump, compress=True)
    if code != 0:
        raise remote.RemoteError("The database export failed on the server (exit %d)." % code, remote.EXIT_REMOTE)
    ok, tables, problem = verify_dump(dump)
    if not ok:
        bad = dump.with_name(dump.name.replace(".sql.gz", ".FAILED.sql.gz"))
        dump.rename(bad)
        raise remote.RemoteError("The database backup isn't usable: %s. Kept as %s for inspection." % (problem, bad.name),
                                 remote.EXIT_REMOTE)
    marker = dump.with_name(dump.name + guard.VERIFIED_SUFFIX)
    marker.write_text(json.dumps({"created": time.time(), "bytes": dump.stat().st_size, "tables": tables,
                                  "site": site.spec}, indent=2), encoding="utf-8")
    return dump


def cmd_backup(args, root: Path) -> int:
    site = resolve(args.site, root)
    did = False
    for post_id in args.post or []:
        if not post_id.isdigit():
            raise SiteError("--post takes a numeric post ID.")
        out = site.backups / ("post-%s-%s.html" % (post_id, stamp()))
        code = _stream_to(site, remote.wp_command(["post", "get", post_id, "--field=post_content"]), out, compress=False)
        if code != 0:
            return remote.EXIT_REMOTE
        say("Saved post %s's content to %s" % (post_id, out.relative_to(root)))
        did = True
    for path in args.file or []:
        rel = clean_remote_path(path)
        out = site.backups / "files" / stamp() / rel
        code = _stream_to(site, "cat %s" % shlex.quote(rel), out, compress=False)
        if code != 0:
            return remote.EXIT_REMOTE
        say("Saved %s to %s" % (rel, out.relative_to(root)))
        did = True
    if args.db or not did:
        dump = backup_database(site)
        ok, tables, _ = verify_dump(dump)
        say("Database backup verified: %s (%d tables, %.1f MB)." % (dump.relative_to(root), tables, dump.stat().st_size / 1e6))
        say("Changes to %s are allowed for the next %s." % (site.spec, human_age(guard.BACKUP_MAX_AGE)))
    return 0


# ── deploy and pull ─────────────────────────────────────────────────────────────────────────────


def clean_remote_path(path: str) -> str:
    if path.startswith("/") or path.startswith("~"):
        raise SiteError("Give the remote path relative to the WordPress folder (e.g. wp-content/mu-plugins/site.php), "
                        "not an absolute path.")
    norm = posixpath.normpath(path)
    if norm == ".." or norm.startswith("../"):
        raise SiteError("The remote path must stay inside the WordPress folder.")
    return "" if norm == "." else norm


def _tar_stream(source: Path, sink) -> None:
    def keep(info: tarfile.TarInfo):
        name = Path(info.name).name
        if name in SKIP_NAMES or name.startswith("._"):
            return None
        info.uid = info.gid = 0
        info.uname = info.gname = ""
        return info
    with tarfile.open(fileobj=sink, mode="w|", format=tarfile.USTAR_FORMAT) as tar:
        for child in sorted(source.iterdir()):
            tar.add(str(child), arcname=child.name, filter=keep)


def _local_md5s(source: Path) -> Dict[str, str]:
    sums = {}
    if source.is_file():
        return {".": hashlib.md5(source.read_bytes()).hexdigest()}
    for path in sorted(source.rglob("*")):
        rel = path.relative_to(source)
        if path.is_file() and not any(p in SKIP_NAMES or p.startswith("._") for p in rel.parts):
            sums["./" + rel.as_posix()] = hashlib.md5(path.read_bytes()).hexdigest()
    return sums


def _remote_md5s(site: Site, dest: str, is_dir: bool) -> Dict[str, str]:
    q = shlex.quote(dest)
    if is_dir:
        cmd = "cd %s && find . -type f -exec md5sum {} + 2>/dev/null" % q
    else:
        cmd = "md5sum %s 2>/dev/null" % q
    code, out, _ = remote.run_text(site, cmd)
    sums = {}
    for line in out.splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2:
            sums["." if not is_dir else parts[1].strip()] = parts[0]
    return sums


def _php_files(source: Path) -> List[Path]:
    if source.is_file():
        return [source] if source.suffix == ".php" else []
    return [p for p in source.rglob("*.php") if not any(x in SKIP_NAMES for x in p.parts)]


OPCACHE_PHP = b"""<?php
// One-shot file from `wpsite deploy`: it deletes itself first, then resets PHP's opcode cache so the
// web server stops running the previous version of the files just deployed.
@unlink(__FILE__);
header('Content-Type: text/plain');
header('Cache-Control: no-store');
echo 'wpstudio-opcache:' . (function_exists('opcache_reset') ? (opcache_reset() ? 'reset' : 'failed') : 'absent');
"""


def reset_opcache(site: Site) -> str:
    """Reset the web server's PHP opcode cache. WP-CLI can't: it runs in a separate CLI process."""
    name = "wp-content/wpstudio-opcache-%s.php" % pysecrets.token_hex(16)
    with tempfile.TemporaryFile() as payload:
        payload.write(OPCACHE_PHP)
        payload.seek(0)
        proc = remote.run(site, "cat > %s" % shlex.quote(name), stdin=payload)
    if proc.returncode != 0:
        return "couldn't place the cache-reset file"
    base = site.values.get("SITE_URL")
    if not base:
        _, out, _ = remote.run_text(site, "wp option get home")
        base = out.strip()
    try:
        status, headers, body = http_get("%s/%s" % (base.rstrip("/"), name))
        if status is None:
            body = "request failed (%s)" % headers.get("error", "no answer")
    finally:
        remote.run(site, "rm -f %s" % shlex.quote(name))
    if "wpstudio-opcache:reset" in body:
        return "reset"
    if "wpstudio-opcache:absent" in body:
        return "not in use on this server"
    return body.strip()[:120] or "no answer"


def cmd_deploy(args, root: Path) -> int:
    site = resolve(args.site, root)
    source = Path(args.local).expanduser().resolve()
    if not source.exists():
        raise SiteError("%s doesn't exist." % args.local)
    refuse_secret_path(root, source, "deploying %s" % args.local)
    if source.is_dir():
        store = workspace.secrets_home().resolve()
        if source == store or source in store.parents or (source / workspace.DROPBOX).exists():
            raise Refused("Refused: that folder holds the studio's secrets; deploy the specific folder you mean.")
    dest = clean_remote_path(args.remote)
    require_fresh_backup(site, "deploying to %s" % (dest or "the WordPress folder"))
    is_dir = source.is_dir()
    if is_dir and dest in PROTECTED_DIRS:
        raise Refused("Refused: deploying a folder replaces the whole destination, and %r holds things that aren't "
                      "yours to replace. Deploy into a subfolder (e.g. wp-content/themes/<theme>)." % (dest or "the WordPress root"))
    php = _php_files(source)
    local_php = shutil.which("php")
    for path in php if local_php else []:
        lint = subprocess.run([local_php, "-l", str(path)], capture_output=True, text=True)
        if lint.returncode != 0:
            say(lint.stdout.strip() or lint.stderr.strip())
            raise Refused("Refused: %s has a PHP syntax error (shown above). One syntax error can take the whole site down." % path.name)
    # Where things go on the server:
    #   stage  - a private folder in the SSH user's home, outside the website: nothing there can be
    #            requested over the web or loaded by WordPress, so unchecked code waits there.
    #   ready  - the checked copy, placed beside the destination under a name WordPress never loads
    #            (WordPress loads every *.php in mu-plugins/, hidden ones included; folders starting
    #            with "." are skipped by the plugin and theme scanners). Same folder, so the final
    #            rename is atomic.
    token = pysecrets.token_hex(6)
    parent = posixpath.dirname(dest) or "."
    base = posixpath.basename(dest)
    stage = '"$HOME"/.wpstudio-staging/%s' % token
    staged = "%s/%s" % (stage, shlex.quote(base))
    ready = shlex.quote(posixpath.join(parent, ".%s.wpstudio-%s" % (base, token)))
    q_dest, q_parent = shlex.quote(dest), shlex.quote(parent)
    cleanup = "rm -rf %s %s; rmdir \"$HOME\"/.wpstudio-staging 2>/dev/null; true" % (stage, ready)
    try:
        # 1. Upload into the private stage.
        with tempfile.TemporaryFile() as bundle:
            if is_dir:
                _tar_stream(source, bundle)
                upload = "mkdir -p %s && tar -xf - -C %s" % (staged, staged)
            else:
                with open(source, "rb") as handle:
                    shutil.copyfileobj(handle, bundle)
                upload = "mkdir -p %s && cat > %s" % (stage, staged)
            bundle.seek(0)
            proc = remote.run(site, upload, stdin=bundle)
        if proc.returncode != 0:
            raise remote.RemoteError("Upload failed: %s" % proc.stderr.decode("utf-8", "replace").strip(), remote.EXIT_REMOTE)

        # 2. Lint PHP with the server's own PHP before anything goes near the website.
        if php:
            lint = ("find %s -name '*.php' -exec php -l {} \\;" % staged) if is_dir else ("php -l %s" % staged)
            code, out, err = remote.run_text(site, "command -v php >/dev/null || exit 127; " + lint)
            if code == 127 and not local_php:
                raise Refused("Refused: there's no PHP on the server's command line and none on this Mac, so the PHP "
                              "can't be checked for syntax errors before it goes live.")
            bad = [l for l in (out + err).splitlines() if re.search(r"(Parse|Fatal) error|Errors parsing", l)]
            if code not in (0, 127) or bad:
                say("\n".join(bad) or (out + err).strip())
                raise Refused("Refused: the server's PHP found a syntax error (shown above). Nothing was changed on the site.")

        # 3. Keep the current version.
        exists_code, _, _ = remote.run_text(site, "test -e %s" % q_dest)
        saved = None
        if exists_code == 0:
            saved = site.backups / "files" / stamp() / (dest + (".tar" if is_dir else ""))
            cmd = ("tar -cf - -C %s ." % q_dest) if is_dir else ("cat %s" % q_dest)
            if _stream_to(site, cmd, saved, compress=False) != 0:
                raise remote.RemoteError("Couldn't save the current version of %s, so nothing was changed." % dest,
                                         remote.EXIT_REMOTE)

        # 4. Copy beside the destination under a name WordPress ignores, then rename into place. A folder
        #    being replaced moves aside first and comes back if the rename fails.
        place = "mkdir -p %s && cp -R %s %s" % (q_parent, staged, ready)
        if is_dir:
            old = shlex.quote(posixpath.join(parent, ".%s.wpstudio-old-%s" % (base, token)))
            swap = ("if [ -e {d} ]; then mv {d} {old}; fi; "
                    "if mv {r} {d}; then rm -rf {old}; else [ -e {old} ] && mv {old} {d}; exit 1; fi"
                    ).format(old=old, d=q_dest, r=ready)
        else:
            swap = "mv -f %s %s" % (ready, q_dest)
        code, out, err = remote.run_text(site, "%s && %s" % (place, swap))
        if code != 0:
            raise remote.RemoteError("The final move failed; the previous version is still in place. %s" % err.strip(),
                                     remote.EXIT_REMOTE)
    finally:
        remote.run(site, cleanup)
    log_activity(site, "deploy %s to %s" % (source.name, dest))

    # 5. Verify what landed.
    local_sums = _local_md5s(source)
    remote_sums = _remote_md5s(site, dest, is_dir)
    mismatched = sorted(k for k in local_sums if remote_sums.get(k) != local_sums[k])
    say("Deployed %s to %s on %s." % (source.name, dest, site.spec))
    if saved:
        say("Previous version saved to %s" % saved.relative_to(root))
    if mismatched:
        say("WARNING: %d file(s) on the server don't match what was sent: %s" % (len(mismatched), ", ".join(mismatched[:10])))
        return remote.EXIT_REMOTE
    say("Checksums match for %d file(s)." % len(local_sums))
    if php:
        result = reset_opcache(site)
        if result == "reset":
            say("PHP opcode cache reset, so the website runs the new code now.")
        elif result == "not in use on this server":
            say("This server doesn't use PHP's opcode cache; the new code is live.")
        else:
            say("Couldn't reset PHP's opcode cache (%s). The website may run the old code for a minute or two; "
                "check the page again before trusting the result." % result)
    say("Next: wpsite purge %s, then check the page with a cache-busting URL." % site.spec)
    return 0


def extract_inside(archive: Path, target: Path) -> List[str]:
    """Unpack only plain files and folders, and only inside `target` (no ../ paths, no links).
    Returns the names it skipped."""
    target.mkdir(parents=True, exist_ok=True)
    inside = target.resolve()
    skipped = []
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            destination = (inside / member.name).resolve()
            if not (member.isfile() or member.isdir()) or (destination != inside and inside not in destination.parents):
                skipped.append(member.name)
                continue
            tar.extract(member, path=str(inside))
    return skipped


def cmd_pull(args, root: Path) -> int:
    site = resolve(args.site, root)
    rel = clean_remote_path(args.remote)
    target = Path(args.local).expanduser() if args.local else site.work / (rel or "wordpress")
    refuse_secret_path(root, target, "downloading to %s" % target)
    code, _, _ = remote.run_text(site, "test -d %s" % shlex.quote(rel or "."))
    if code == 0:
        archive = target.with_name(target.name + ".wpstudio.tar")
        if _stream_to(site, "tar -cf - -C %s ." % shlex.quote(rel or "."), archive, compress=False) != 0:
            return remote.EXIT_REMOTE
        try:
            extract_inside(archive, target)
        finally:
            archive.unlink()
    else:
        if _stream_to(site, "cat %s" % shlex.quote(rel), target, compress=False) != 0:
            return remote.EXIT_REMOTE
    say("Downloaded %s to %s" % (rel, target.relative_to(root) if root in target.resolve().parents else target))
    return 0


# ── cache, keys, host keys ──────────────────────────────────────────────────────────────────────


def cmd_purge(args, root: Path) -> int:
    site = resolve(args.site, root)
    facts = _remote_facts(site)
    available = facts.get("cache_cmd", [])
    ran = []
    for probe, command in CACHE_COMMANDS:
        if probe in available:
            code, out, err = remote.run_text(site, command)
            ran.append("%s (%s)" % (command, "ok" if code == 0 else "failed: " + (err or out).strip()[:120]))
    code, _, err = remote.run_text(site, "wp cache flush")
    ran.append("wp cache flush (%s)" % ("ok" if code == 0 else "failed"))
    for line in ran:
        say("Ran %s" % line)
    if not available:
        say("No page-cache plugin command was found. If the host caches pages itself (many managed hosts do), clear it "
            "in the host's dashboard; see the wp-studio:caching skill.")
    home = (facts.get("home") or [site.values.get("SITE_URL", "")])[0]
    status, headers = _probe_http(home)
    if "cf-ray" in headers:
        say("Cloudflare is in front of this site; its edge cache isn't cleared by WordPress commands unless the host's "
            "integration does it. If a change still doesn't show, purge it in Cloudflare (or the host dashboard).")
    return 0


def key_path() -> Path:
    return Path(os.environ.get("WPSTUDIO_KEY", str(Path.home() / ".ssh" / "wpstudio_ed25519")))


def cmd_key(args, root: Path) -> int:
    site = resolve(args.site, root)
    key = key_path()
    if not key.exists():
        key.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "wp-studio", "-f", str(key)], check=True)
        say("Created the studio's SSH key (%s)." % key)
    public = key.with_suffix(".pub").read_text(encoding="utf-8").strip()
    if site.values.get("SSH_KEY") == str(key):
        say("%s already logs in with the studio key." % site.spec)
        return 0
    if site.values.get("SSH_PASSWORD"):
        remote.close_master(site)
        # ssh-copy-id needs ~/.ssh to exist (it stages files there); a Mac that has never used SSH has none.
        ssh_dir = Path.home() / ".ssh"
        ssh_dir.mkdir(mode=0o700, exist_ok=True)
        copy = subprocess.run(
            # -f: install without first trying to log in with the key (that probe offers the agent's keys and
            # can use up the server's login attempts); the password options mirror remote._auth_options.
            ["ssh-copy-id", "-f", "-i", str(key.with_suffix(".pub")), "-p", site.port, "-o", "StrictHostKeyChecking=accept-new",
             "-o", "PreferredAuthentications=password,keyboard-interactive", "-o", "PubkeyAuthentication=no",
             "-o", "NumberOfPasswordPrompts=1"] + (["-o", "UserKnownHostsFile=%s" % remote.known_hosts()] if remote.known_hosts() else [])
            + [remote._target(site)],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, env=remote.auth_env(site))
        trial = Site(slug=site.slug, env=site.env, root=root, values=dict(site.values, SSH_KEY=str(key)))
        trial.values.pop("SSH_PASSWORD", None)
        if copy.returncode == 0:
            try:
                remote.ensure_master(trial)
                code, out, _ = remote.run_text(trial, "echo wpstudio-key-ok", in_wp_root=False)
                remote.close_master(trial)
                if "wpstudio-key-ok" in out:
                    values = dict(site.values, SSH_KEY=str(key))
                    envfile.write(site.env_file, values, header="Connection details for %s. Filed by wpsite; never commit or paste this file." % site.spec)
                    say("%s now logs in with the studio key. The password stays on file as a fallback." % site.spec)
                    return 0
            except remote.RemoteError:
                pass
    reason = ""
    if site.values.get("SSH_PASSWORD"):
        lines = (copy.stderr or copy.stdout or "").strip().splitlines()
        if lines:
            reason = redact.redact_text(lines[-1], remote.secret_literals(site, fetch=False))
    say("The key couldn't be installed automatically (many managed hosts manage keys in their dashboard)%s."
        % ((": " + reason) if reason else ""))
    say("Ask the operator to add this public key in the hosting dashboard (it is safe to share):")
    say("  " + public)
    say("Where: MyKinsta → User settings → SSH keys; cPanel → SSH Access → Import Key; otherwise the host's SSH/SFTP settings.")
    say("Once added, run: wpsite key %s" % site.spec)
    if site.values.get("SSH_PASSWORD") is None:
        # Remember the key path so the next run tests it.
        envfile.write(site.env_file, dict(site.values, SSH_KEY=str(key)),
                      header="Connection details for %s. Filed by wpsite; never commit or paste this file." % site.spec)
    return EXIT_REFUSED


def cmd_trust_host(args, root: Path) -> int:
    site = resolve(args.site, root)
    host = site.values["SSH_HOST"]
    names = ["[%s]:%s" % (host, site.port)] + ([host] if site.port == "22" else [])
    hosts_file = remote.known_hosts() or str(Path.home() / ".ssh" / "known_hosts")
    for name in names:
        subprocess.run(["ssh-keygen", "-R", name, "-f", hosts_file], capture_output=True)
    remote.close_master(site)
    remote.ensure_master(site)
    say("Re-trusted the new host key for %s and connected." % site.spec)
    return 0


# ── entry point ─────────────────────────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wpsite", description="Work on a WordPress site safely from the studio.")
    parser.add_argument("--version", action="version", version="wpsite %s" % __version__)
    sub = parser.add_subparsers(dest="command", metavar="command")
    sub.required = True
    sub.add_parser("list", help="projects and their environments").set_defaults(func=cmd_list)
    p = sub.add_parser("init", help="create a project")
    p.add_argument("slug"); p.add_argument("--url", required=True); p.set_defaults(func=cmd_init)
    p = sub.add_parser("secrets", help="file, check or clear the credential drop box")
    p.add_argument("action", choices=("file", "status", "wipe")); p.add_argument("site", nargs="?"); p.set_defaults(func=cmd_secrets)
    p = sub.add_parser("check", help="connect and report read-only facts")
    p.add_argument("site"); p.set_defaults(func=cmd_check)
    p = sub.add_parser("wp", help="run WP-CLI on the site")
    p.add_argument("--input", metavar="FILE", help="send this local file to the command's standard input")
    p.add_argument("site"); p.add_argument("args", nargs=argparse.REMAINDER); p.set_defaults(func=cmd_wp)
    p = sub.add_parser("sh", help="run a shell command in the WordPress folder")
    p.add_argument("--input", metavar="FILE", help="send this local file to the command's standard input")
    p.add_argument("site"); p.add_argument("command"); p.set_defaults(func=cmd_sh)
    p = sub.add_parser("backup", help="database dump (default), post content, or files")
    p.add_argument("site"); p.add_argument("--db", action="store_true"); p.add_argument("--post", action="append")
    p.add_argument("--file", action="append"); p.set_defaults(func=cmd_backup)
    p = sub.add_parser("deploy", help="upload a file or folder, linted and verified")
    p.add_argument("site"); p.add_argument("local"); p.add_argument("remote"); p.set_defaults(func=cmd_deploy)
    p = sub.add_parser("pull", help="download a file or folder into work/")
    p.add_argument("site"); p.add_argument("remote"); p.add_argument("local", nargs="?"); p.set_defaults(func=cmd_pull)
    p = sub.add_parser("purge", help="clear the page cache the right way for this host")
    p.add_argument("site"); p.set_defaults(func=cmd_purge)
    p = sub.add_parser("key", help="set up SSH key login")
    p.add_argument("site"); p.set_defaults(func=cmd_key)
    p = sub.add_parser("trust-host", help="re-trust a host key the host has rotated")
    p.add_argument("site"); p.set_defaults(func=cmd_trust_host)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        root = workspace.require_root()
        return args.func(args, root)
    except (workspace.NotAWorkspace, SiteError, dropbox.DropboxError) as err:
        print(str(err), file=sys.stderr)
        return EXIT_USAGE
    except Refused as err:
        print(str(err), file=sys.stderr)
        return EXIT_REFUSED
    except remote.RemoteError as err:
        print(str(err), file=sys.stderr)
        return err.code
