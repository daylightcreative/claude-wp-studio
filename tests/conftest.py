"""Shared fixtures. The runtime is stdlib-only; tests need pytest and nothing else."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PLUGIN = REPO / "plugin"
sys.path.insert(0, str(PLUGIN / "lib"))


@pytest.fixture
def studio(tmp_path, monkeypatch):
    """A fresh, synced studio workspace that is a git repo, with the cwd inside it."""
    from wpstudio import sync

    root = tmp_path / "studio"
    root.mkdir()
    (root / ".wp-studio").write_text("test\n")
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "t@example.com"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
    sync.sync(root)
    monkeypatch.chdir(root)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    return root


def make_site(root, slug="acme", env="live", values=None):
    from wpstudio import envfile

    project = root / "projects" / slug
    (project / "backups").mkdir(parents=True, exist_ok=True)
    data = {"SITE_URL": "https://acme.test", "SSH_HOST": "203.0.113.5", "SSH_PORT": "2222",
            "SSH_USER": "acme", "SSH_PASSWORD": "Hunter2-secret!", "WP_PATH": "/www/acme/public"}
    data.update(values or {})
    envfile.write(project / ".secrets" / ("%s.env" % env), data)
    return project


def make_backup(project, env="live", age=0.0, bytes_override=None):
    """A dump plus the verification marker `wpsite backup` writes."""
    from wpstudio import guard

    folder = project / "backups" / env
    folder.mkdir(parents=True, exist_ok=True)
    dump = folder / ("db-%d.sql.gz" % int(time.time() * 1000))
    dump.write_bytes(b"x" * 64)
    marker = dump.with_name(dump.name + guard.VERIFIED_SUFFIX)
    marker.write_text(json.dumps({"created": time.time() - age,
                                  "bytes": bytes_override if bytes_override is not None else 64}))
    return dump
