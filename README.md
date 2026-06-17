# Claude WP Studio

**A ready-to-work WordPress studio for [Claude Code](https://claude.com/claude-code).**
One command sets up everything — the tools, the configuration, and a built-in WordPress
knowledge base — so you can build and maintain WordPress sites by *talking to Claude* instead
of clicking around the dashboard. You direct; Claude does the technical work.

---

## Install (macOS)

```bash
curl -fsSL https://get.daylightcreative.tech/wp-studio | bash
```

<sub>Prefer the source URL? `curl -fsSL https://raw.githubusercontent.com/daylightcreative/claude-wp-studio/main/install.sh | bash`</sub>

The installer is a guided wizard. It will:

1. Install the prerequisites — Xcode Command Line Tools, Homebrew, a **modern Python** (not
   macOS's old, locked-down system one), and the WordPress tooling (`wp-cli`, ImageMagick,
   MySQL client, `gh`).
2. Install the latest **Claude Code** (the native installer, which keeps itself up to date).
3. Lay down the studio — a searchable knowledge library, helper scripts, and the working
   standards — in a folder you choose (default `~/claude-wp-studio`).
4. Write the Claude Code defaults: **xhigh reasoning effort**, the **opus** model, and a
   launcher that runs with **full autonomy** (bypass permissions) so Claude isn't stopped on
   every step.
5. Optionally connect a **private GitHub backup** on your own account.
6. Hand off to Claude's login so you connect your subscription or API key.

> **Unattended / agent-driven install:** add `--unattended` (and optionally `--dir <path>`,
> `--no-backup`). Designed so another agent can run it headlessly.

## Requirements

- macOS (Apple Silicon or Intel)
- A Claude subscription (Pro/Max/Team/Enterprise) **or** an Anthropic API key

## Using it day to day

```bash
cd ~/claude-wp-studio
./studio.sh
```

The first launch asks you to log in, then Claude sets up the rest itself — just tell it
*"Read START_HERE.md and follow it."* After that, open the folder, run `./studio.sh`, and
say what you want, e.g.:

- *"Pull up my site and tell me what it's built with."*
- *"On a safe practice copy, give the homepage more breathing room and show me a picture."*
- *"How much work is it to move this site off Divi onto native WordPress, keeping the design?"*

New users: read **[GETTING_STARTED.md](GETTING_STARTED.md)**.

## What's inside

| | |
|---|---|
| **`CLAUDE.md`** | The operating manual Claude loads every session — philosophy, safety rules, the credential protocol. |
| **`library/`** | A searchable WordPress knowledge base (FTS5 catalog): lessons (caching by host, mu-plugin CSS, SSH/SFTP gotchas, safe edits, image optimization, Divi pitfalls) and playbooks (the working method, client setup, Divi→Gutenberg, sub-agents). |
| **`tooling/`** | The scripts: `catalog.py` (search), `save.sh` (backup), `maintain.sh` (housekeeping), `credentials.sh` (the secure credential drop box), plus per-project helper templates. |
| **`projects/`** | One folder per client site — working files, backups, and git-ignored secrets. |
| **`studio.sh`** | The launcher: updates Claude Code, then starts it with the studio defaults. |

## Safety & credentials

This kit runs Claude Code with **bypass permissions** for a hands-off experience. That's
powerful — please read **[SECURITY.md](SECURITY.md)** for what that means and the recommended
way to use it. In short: the studio keeps the safety rules that matter (back up before
changes, work on staging not live, confirm anything irreversible or public), and your
credentials go through a git-ignored **drop box** (`CREDENTIALS.txt`) — never the chat, never
a commit.

## License

[MIT](LICENSE) © DayLight Creative Technologies
