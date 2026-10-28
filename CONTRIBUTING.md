# Contributing

## Layout

```
.claude-plugin/marketplace.json   the "daylight" marketplace (this repo)
plugin/                           the wp-studio plugin
  .claude-plugin/plugin.json      version: the one source of truth
  bin/wpsite, bin/studio          on Claude's PATH while the plugin is enabled
  lib/wpstudio/                   the runtime (Python 3.9+, standard library only)
  hooks/hooks.json                SessionStart, PreToolUse (Bash), SessionEnd
  skills/<name>/SKILL.md          WordPress knowledge; see docs/SKILL_AUTHORING.md
  agents/                         site-scout, page-converter, qa-checker
  templates/workspace/            files laid down in (and kept current in) a studio folder
.mcp.json                         (in plugin/) the pinned Playwright MCP server
install.sh                        the one-line installer
tests/unit, tests/e2e             the gates
```

## The gates

```bash
python3 -m pytest tests/unit -q     # needs: pytest, php, shellcheck
python3 -m pytest tests/e2e -q      # needs: Docker. Builds a WordPress + SSH + MariaDB host and
                                    # runs every wpsite command against it for real
claude plugin validate .            # marketplace and plugin manifests
```

CI runs all three, with the unit tests on Python 3.9 (what Apple's Command Line Tools ship) and
on the current release. A change to `wpsite`, the hooks or the scanner ships with a test that
fails without it.

## Releasing

1. Bump `version` in `plugin/.claude-plugin/plugin.json`.
2. Add the matching entry at the top of `CHANGELOG.md`. A test fails if the two disagree.
3. Merge to `main`. Installed studios pick up the new version through Claude Code's plugin
   auto-update (enabled for this marketplace in the studio's settings). The next session then
   refreshes the studio's kit-owned files.

Changing the Playwright MCP version: edit only `plugin/.mcp.json`. The installer reads the pin from
there (`studio mcp-version`), so the server and the browser it needs can't drift apart.

## Writing skills

Read [docs/SKILL_AUTHORING.md](docs/SKILL_AUTHORING.md). The repository is public:
`tests/unit/test_public_hygiene.py` fails on known client names, personal paths and dated model IDs.
