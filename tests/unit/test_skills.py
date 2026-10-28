"""Skills and agents: valid frontmatter, real wpsite commands, referenced files, lint-clean PHP and shell."""

import re
import shutil
import subprocess

import pytest

from conftest import PLUGIN

SKILLS = sorted(p for p in (PLUGIN / "skills").iterdir() if p.is_dir())
AGENTS = sorted((PLUGIN / "agents").glob("*.md"))


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    assert match, "%s has no frontmatter" % path
    fields = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(":")
        if key.strip() and not line.startswith(" "):
            fields[key.strip()] = value.strip()
    return fields, match.group(2)


def wpsite_commands():
    import sys
    sys.path.insert(0, str(PLUGIN / "lib"))
    from wpstudio.cli import build_parser
    parser = build_parser()
    sub = next(a for a in parser._actions if a.__class__.__name__ == "_SubParsersAction")
    return set(sub.choices)


def test_there_are_skills_and_agents():
    assert len(SKILLS) >= 15 and len(AGENTS) == 3


@pytest.mark.parametrize("skill", SKILLS, ids=lambda p: p.name)
def test_skill_frontmatter_and_size(skill):
    fields, body = frontmatter(skill / "SKILL.md")
    assert fields.get("name") == skill.name
    assert 40 <= len(fields.get("description", "")) <= 1536
    assert len(body.splitlines()) <= 260


@pytest.mark.parametrize("skill", SKILLS, ids=lambda p: p.name)
def test_supporting_files_are_referenced(skill):
    body = (skill / "SKILL.md").read_text(encoding="utf-8")
    orphans = [f.name for f in skill.iterdir() if f.name != "SKILL.md" and f.name not in body]
    assert orphans == []


def test_every_wpsite_command_mentioned_exists():
    known = wpsite_commands()
    used = set()
    for path in list((PLUGIN / "skills").rglob("*.md")) + AGENTS + [PLUGIN / "templates" / "workspace" / "studio-manual.md"]:
        used |= set(re.findall(r"`wpsite ([a-z][a-z-]+)", path.read_text(encoding="utf-8")))
        used |= set(re.findall(r"^\s*wpsite ([a-z][a-z-]+)", path.read_text(encoding="utf-8"), re.M))
    assert used - known == set()


def test_skills_never_tell_claude_to_pipe_into_wpsite():
    offenders = []
    for path in (PLUGIN / "skills").rglob("*"):
        if path.is_file() and path.suffix in (".md", ".php", ".sh"):
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if re.search(r"wpsite (wp|sh) .*\s<\s*[^\s<>]+\s*(#.*)?$", line) or re.search(r"\|\s*wpsite ", line):
                    offenders.append("%s:%d" % (path.relative_to(PLUGIN), number))
    assert offenders == []


@pytest.mark.parametrize("agent", AGENTS, ids=lambda p: p.stem)
def test_agent_frontmatter(agent):
    fields, body = frontmatter(agent)
    assert fields["name"] == agent.stem
    assert fields.get("model") in ("haiku", "sonnet", "opus")
    assert len(fields.get("description", "")) >= 40


def test_read_only_agents_cannot_write_files():
    for name in ("site-scout", "qa-checker"):
        fields, _ = frontmatter(PLUGIN / "agents" / ("%s.md" % name))
        denied = {t.strip() for t in fields.get("disallowedTools", "").split(",")}
        assert {"Write", "Edit"} <= denied


PHP = sorted(PLUGIN.rglob("*.php"))


@pytest.mark.parametrize("path", PHP, ids=lambda p: str(p.relative_to(PLUGIN)))
def test_php_files_lint_clean(path):
    php = shutil.which("php")
    assert php, "php is required to run this gate (brew install php / apt install php-cli)"
    result = subprocess.run([php, "-l", str(path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


SHELL = sorted(list(PLUGIN.rglob("*.sh")) + [PLUGIN.parent / "install.sh", PLUGIN / "templates" / "workspace" / "studio.sh"])


@pytest.mark.parametrize("path", SHELL, ids=lambda p: p.name)
def test_shell_scripts_pass_shellcheck(path):
    shellcheck = shutil.which("shellcheck")
    assert shellcheck, "shellcheck is required to run this gate"
    result = subprocess.run([shellcheck, "-x", str(path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout
