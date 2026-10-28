# Writing a wp-studio skill

This is the contract every skill in `plugin/skills/` follows. Contributors and agents read it
before adding or changing a skill. The test suite (`tests/test_skills.py`) enforces the parts a
machine can check.

## What the studio is

Claude WP Studio is a Claude Code plugin plus a workspace folder. An **operator** (often not a
programmer) directs; Claude does the WordPress work on client sites over SSH. Claude talks to
sites only through the `wpsite` command (on PATH from the plugin's `bin/`). Never tell Claude to
run raw `ssh`, `scp`, `sftp` or `rsync` against a site; a hook blocks them.

## The `wpsite` command (the only route to a site)

A *site* is `<slug>` (the live environment) or `<slug>:<env>` (for example `acme:staging`).

| Command | What it does |
|---|---|
| `wpsite list` | Projects and their environments, with which connection fields are set (never values) |
| `wpsite init <slug> --url <url>` | Create `projects/<slug>/` (CLAUDE.md, backups/, work/) and `clients/<slug>.md` |
| `wpsite secrets file <site>` | File what the operator pasted in `CREDENTIALS.txt` into the secrets store outside the studio folder; prints field names only; wipes the drop box |
| `wpsite secrets status [<site>]` | Whether the drop box has something in it, or which fields a site has |
| `wpsite check <site>` | Connect and report read-only facts: WP version, home URL, search visibility, host, cache layer, CLI PHP version |
| `wpsite wp <site> <wp-cli args…>` | Run WP-CLI on the server. Any command that can change the site is refused unless a database backup of that environment less than 2 hours old exists |
| `wpsite sh <site> '<command>'` | Run a shell command on the server. Anything not on the read-only list needs the same fresh backup |
| `wpsite backup <site> [--post ID]… [--file PATH]…` | With no options: a verified gzip database dump. `--post` saves a post's stored content; `--file` saves a remote file. Everything lands in `projects/<slug>/backups/<env>/` |
| `wpsite deploy <site> <local> <remote>` | Upload a file or folder (remote path relative to the WordPress root). PHP is linted on the server before it goes live, the previous version is backed up, PHP's opcode cache is reset, and checksums are verified |
| `wpsite pull <site> <remote> [<local>]` | Download a file or folder into the project's `work/` |
| `wpsite purge <site>` | Clear the page cache the right way for the host, and say plainly what it could not clear |
| `wpsite key <site>` | Set up SSH key login |
| `wpsite trust-host <site>` | Re-trust a host key that changed. Only after the operator confirms the host rotated it |

Exit codes: 0 ok, 2 usage error, 3 refused by a safety rule (the message says what to do), 4
could not connect, 5 the remote command failed.

## File layout

```
plugin/skills/<name>/SKILL.md        # required
plugin/skills/<name>/<file>          # optional supporting files (PHP templates, checklists)
```

`<name>` is kebab-case. The skill is invoked as `/wp-studio:<name>` and Claude loads it on its
own when the description matches the task.

## Frontmatter

```yaml
---
name: <same as the folder>
description: <one or two sentences: what it covers, then "Use when …" with the concrete triggers>
---
```

The description is what Claude reads to decide whether to load the skill, and the listing
truncates `description` + `when_to_use` at 1,536 characters. Lead with the use case. No other
frontmatter unless a skill truly needs it.

## Body rules

1. **Write to Claude, imperatively.** "Back up before…", not "You might consider…".
2. **Lead with the rule, then the why, then the how.** A reader who stops after the first
   paragraph of a section should still do the right thing.
3. **Only verified facts.** Every rule comes from something that happened on a real site or from
   official documentation. If a fact depends on a version (WordPress, PHP, Divi, a host), name
   the version. If you could not confirm something, mark it **UNVERIFIED** and say what would
   settle it. Never invent a filter name, option name, CLI flag or host behavior.
4. **Generic only.** This repository is public. No client names, people, domains, IP addresses,
   host account IDs, secrets, personal paths or indicators of compromise from a real incident.
   Describe the pattern ("a rogue admin account created by the loader"), not the instance.
   `tests/test_public_hygiene.py` fails on known client names.
5. **Use `wpsite` for every remote action** in examples. Show the exact command.
6. **Code you ship must be complete and lint-clean.** PHP files must pass `php -l`. A PHP file
   is a supporting file in the skill folder, not a code block the reader has to copy.
7. **Link, don't repeat.** If another skill owns a topic, point to it by name
   (`see the wp-studio:caching skill`) instead of restating it.
8. **Short.** A SKILL.md body should usually be under 250 lines. Put long reference material in
   a supporting file and say when to read it.
9. **Plain words for the operator.** When a skill tells Claude to explain something to the
   operator, give the plain-language version.
