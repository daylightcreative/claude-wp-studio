import stat

from wpstudio import sync


def test_kit_owned_files_are_restored(studio):
    manual = studio / ".claude" / "studio-manual.md"
    manual.write_text("edited")
    assert sync.sync(studio) == [".claude/studio-manual.md"]
    assert manual.read_bytes() == (sync.TEMPLATES / "studio-manual.md").read_bytes()


def test_operator_files_are_never_overwritten(studio):
    (studio / "CLAUDE.md").write_text("mine")
    (studio / "WORKLOG.md").write_text("log")
    assert sync.sync(studio) == []
    assert (studio / "CLAUDE.md").read_text() == "mine"
    assert (studio / "WORKLOG.md").read_text() == "log"


def test_launcher_is_executable_and_runs_auto_mode(studio):
    launcher = studio / "studio.sh"
    assert launcher.stat().st_mode & stat.S_IXUSR
    assert "claude --permission-mode auto --settings .claude/launch-settings.json" in launcher.read_text()


def test_pre_commit_hook_points_at_this_plugin(studio):
    hook = studio / ".git" / "hooks" / "pre-commit"
    assert hook.stat().st_mode & stat.S_IXUSR
    assert str(sync.PLUGIN_ROOT / "bin" / "studio") in hook.read_text()


def test_v1_studio_migrates_without_losing_operator_files(tmp_path):
    root = tmp_path / "v1"
    (root / "tooling").mkdir(parents=True)
    (root / "tooling" / "catalog.py").write_text("")
    (root / "library" / "clients").mkdir(parents=True)
    (root / "library" / "clients" / "acme.md").write_text("# Acme")
    (root / "library" / "clients" / "README.md").write_text("readme")
    secrets = root / "projects" / "acme" / ".secrets"
    secrets.mkdir(parents=True)
    (secrets / "connection.env").write_text("SSH_HOST='h'\n")
    (root / "projects" / "acme" / "wp.sh").write_text("")
    (root / "projects" / "acme" / "backups").mkdir()
    (root / "projects" / "acme" / "backups" / "page-1.html").write_text("old")
    (root / "CLAUDE.md").write_text("old manual + my notes")
    (root / "WORKLOG.md").write_text("my log")
    assert sync.is_v1(root) is True
    sync.migrate_v1(root)
    assert (root / "clients" / "acme.md").read_text() == "# Acme"
    assert (secrets / "live.env").read_text() == "SSH_HOST='h'\n"
    assert not (root / "projects" / "acme" / "wp.sh").exists()
    assert (root / "projects" / "acme" / "backups" / "v1" / "page-1.html").read_text() == "old"
    assert (root / "CLAUDE.v1.md").read_text() == "old manual + my notes"
    assert (root / "WORKLOG.md").read_text() == "my log"
    assert not (root / "library").exists() and not (root / "tooling").exists()
    assert (root / ".wp-studio").is_file() and sync.is_v1(root) is False
