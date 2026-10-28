import json
import subprocess

from wpstudio import save
from conftest import make_site


def git(root, *args):
    return subprocess.run(["git", "-C", str(root)] + list(args), capture_output=True, text=True)


def test_save_commits_the_workspace(studio, capsys):
    assert save.save(studio, "first", detach=False) == 0
    assert git(studio, "log", "--format=%s").stdout.strip() == "first"
    assert "Saved locally (no GitHub backup linked)." in capsys.readouterr().out


def test_save_refuses_a_held_secret_and_leaves_nothing_staged(studio, capsys):
    make_site(studio)
    save.save(studio, "base", detach=False)
    (studio / "clients" / "acme.md").write_text("pw: Hunter2-secret!\n")
    assert save.save(studio, "leak", detach=False) == 1
    assert git(studio, "log", "-1", "--format=%s").stdout.strip() == "base"
    assert git(studio, "diff", "--cached", "--name-only").stdout == ""
    assert "clients/acme.md:1" in capsys.readouterr().out


def test_secrets_folder_and_drop_box_are_ignored(studio):
    make_site(studio)
    save.save(studio, "x", detach=False)
    tracked = git(studio, "ls-files").stdout.split()
    assert not any(".secrets" in t or t == "CREDENTIALS.txt" for t in tracked)


def test_pre_commit_hook_blocks_a_manual_commit_of_a_secret(studio):
    make_site(studio)
    (studio / "note.md").write_text("Hunter2-secret!\n")
    git(studio, "add", "note.md")
    result = git(studio, "commit", "-m", "manual")
    assert result.returncode != 0
    assert "note.md:1: contains a secret" in result.stderr


def test_push_records_success_and_failure(studio, tmp_path):
    bare = tmp_path / "backup.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    git(studio, "remote", "add", "origin", str(bare))
    assert save.save(studio, "pushed", detach=False) == 0
    assert save.last_push(studio)["ok"] is True
    assert git(bare, "log", "--format=%s", "main").stdout.strip() == "pushed"
    git(studio, "remote", "set-url", "origin", str(tmp_path / "missing.git"))
    (studio / "WORKLOG.md").write_text("more")
    save.save(studio, "second", detach=False)
    status = save.last_push(studio)
    assert status["ok"] is False and status["message"]
