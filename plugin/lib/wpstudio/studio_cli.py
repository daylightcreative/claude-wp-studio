"""`studio`: save, scan, sync, doctor and the hook entry points."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Sequence

from . import PLUGIN_ROOT, __version__, hooks, save, scan, sync, workspace


def cmd_save(args) -> int:
    root = workspace.require_root()
    return save.save(root, args.message, detach=args.background)


def cmd_push_now(args) -> int:
    return save.push_now(workspace.require_root())


def cmd_scan(args) -> int:
    root = workspace.require_root()
    findings = scan.scan_staged(root)
    if not findings:
        return 0
    print("Commit refused: it would put a secret or a site's private data into git:", file=sys.stderr)
    for finding in findings:
        print("  " + str(finding), file=sys.stderr)
    return 1


def cmd_sync(args) -> int:
    root = workspace.require_root()
    changed = sync.sync(root)
    print("Up to date." if not changed else "Updated: " + ", ".join(changed))
    return 0


def cmd_migrate(args) -> int:
    root = Path(args.path).expanduser().resolve()
    if not sync.is_v1(root):
        print("%s isn't a v1 studio; nothing to migrate." % root)
        return 0
    for note in sync.migrate_v1(root):
        print("- " + note)
    return 0


def mcp_version() -> str:
    config = json.loads((PLUGIN_ROOT / ".mcp.json").read_text(encoding="utf-8"))
    package = next(a for a in config["mcpServers"]["playwright"]["args"] if a.startswith("@playwright/mcp@"))
    return package.split("@")[-1]


def cmd_mcp_version(args) -> int:
    print(mcp_version())
    return 0


def cmd_doctor(args) -> int:
    root = workspace.find_root()
    problems = 0

    def report(ok: bool, text: str, fix: str = "") -> None:
        nonlocal problems
        print(("ok    " if ok else "FIX   ") + text + ("" if ok or not fix else "  →  " + fix))
        problems += 0 if ok else 1

    print("Claude WP Studio %s (plugin at %s)" % (__version__, PLUGIN_ROOT))
    report(sys.version_info >= (3, 9), "Python %s" % sys.version.split()[0], "install Xcode Command Line Tools")
    for tool, why in (("git", "saving and backup"), ("ssh", "reaching sites"), ("node", "the browser the studio uses"),
                      ("gh", "the GitHub backup (optional)"), ("magick", "image optimization (optional)")):
        report(shutil.which(tool) is not None, "%s (%s)" % (tool, why), "brew install %s" % ("imagemagick" if tool == "magick" else tool))
    if root is None:
        report(False, "inside a studio folder", "run from your studio folder")
        return 1
    report(True, "studio folder %s" % root)
    report((root / ".git").is_dir(), "git repository", "studio save (creates it)")
    remote = subprocess.run(["git", "-C", str(root), "remote", "get-url", "origin"], capture_output=True, text=True)
    report(remote.returncode == 0, "GitHub backup linked", "see README → Backup")
    status = save.last_push(root)
    if status is not None:
        report(bool(status.get("ok")), "last backup push (%s)" % status.get("time"), status.get("message", "")[:120])
    changed = sync.sync(root)
    report(True, "workspace files current" + (" (just updated: %s)" % ", ".join(changed) if changed else ""))
    return 0 if problems == 0 else 1


def cmd_hook(args) -> int:
    return hooks.run(args.name)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="studio", description="Claude WP Studio housekeeping.")
    parser.add_argument("--version", action="version", version="studio %s" % __version__)
    sub = parser.add_subparsers(dest="command", metavar="command")
    sub.required = True
    p = sub.add_parser("save", help="commit (after the secret scan) and back up")
    p.add_argument("message", nargs="?"); p.add_argument("--background", action="store_true"); p.set_defaults(func=cmd_save)
    sub.add_parser("push-now", help=argparse.SUPPRESS).set_defaults(func=cmd_push_now)
    p = sub.add_parser("scan", help="scan staged files for secrets")
    p.add_argument("--staged", action="store_true"); p.set_defaults(func=cmd_scan)
    sub.add_parser("sync", help="refresh the workspace's kit-owned files").set_defaults(func=cmd_sync)
    p = sub.add_parser("migrate-v1", help="convert a v1 studio folder")
    p.add_argument("path"); p.set_defaults(func=cmd_migrate)
    sub.add_parser("mcp-version", help=argparse.SUPPRESS).set_defaults(func=cmd_mcp_version)
    sub.add_parser("doctor", help="check the setup").set_defaults(func=cmd_doctor)
    p = sub.add_parser("hook", help=argparse.SUPPRESS)
    p.add_argument("name", choices=sorted(hooks.HANDLERS)); p.set_defaults(func=cmd_hook)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except workspace.NotAWorkspace as err:
        print(str(err), file=sys.stderr)
        return 2
