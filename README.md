# Claude WP Studio

**Build and maintain WordPress sites by conversation, safely.** One command turns a Mac into a
WordPress studio for [Claude Code](https://claude.com/claude-code): you say what you want in
plain language; Claude does the technical work on your sites over SSH, with the safety rules
enforced by the tools rather than left to good intentions.

```bash
curl -fsSL https://get.daylightcreative.tech/wp-studio | bash
```

macOS. Needs a Claude subscription or API key. MIT licensed. Rather not pipe to bash? Read
[`install.sh`](install.sh) first, then run it from a clone.

## What you get

- **A site tool Claude can't misuse, `wpsite`.** It's the only route to your sites, and it enforces
  the rules:
  - **Backups:** any change needs a verified database backup less than two hours old.
  - **Safe deploys:** PHP is checked by the server's own PHP before it goes live, the previous
    version is kept, PHP's code cache is reset, and checksums confirm the upload.
  - **Secrets stay out of view:** database passwords and WordPress keys are hidden in anything it
    prints.
- **Auto mode, not "skip all permissions".** Claude works without stopping to ask about each step.
  A safety check reviews every action and stops anything risky or irreversible for you to confirm.
- **WordPress knowledge from real client work.** Fifteen skills Claude loads when the task calls
  for them, including:
  - caching by host, and staging hazards;
  - update policy and hardening, and malware response;
  - Divi, and migrating from Divi to blocks;
  - block themes, images, launch QA and debugging.
- **A browser.** Claude looks at the real rendered page, at desktop and phone widths, rather than
  guessing.
- **Passwords never go in the chat.** You type them into a drop-box file. The studio files them
  into a store outside the studio folder without Claude seeing them, and blocks Claude from
  opening them afterwards.
- **Backed up as you go.** Your studio is a git repository that saves to a private GitHub
  repository on your own account. Any save that would include a password is refused.

## How it's put together

| Piece | Where | Who owns it |
|---|---|---|
| The **wp-studio plugin**: skills, agents, hooks, `wpsite` and `studio` commands, the browser | This repository (`plugin/`), installed through Claude Code's plugin system | The kit. It updates itself in the background |
| Your **studio folder**: `projects/`, `clients/`, `WORKLOG.md`, `CLAUDE.md` | `~/claude-wp-studio` by default | You |
| Kit files inside your studio: `.claude/settings.json`, `.claude/studio-manual.md`, `studio.sh`, `.gitignore` | Your studio folder | The kit. Refreshed at the start of each session; put your own preferences in `CLAUDE.md` |

## Day to day

```bash
cd ~/claude-wp-studio && ./studio.sh
```

Then talk to Claude:

- *"Set up a new site: acme.com, hosted on Kinsta."* Claude creates the project and asks you to
  put the login in `CREDENTIALS.txt`, then checks the connection.
- *"Change the phone number in the footer on Acme."*
- *"Something's injecting a weird script into Acme's homepage. Find out what."*
- *"Plan moving Acme off Divi."*

## Upgrading from v1

Run the installer again and point it at your existing folder. It keeps everything that's yours:
- client records move to `clients/`;
- connection files move to the secrets store (comments and quoting from v1 files are handled);
- lessons or guides you added or changed in the old kit folders are kept under `v1-kept/`;
- old backups stay under `backups/v1/`;
- your old `CLAUDE.md` is kept as `CLAUDE.v1.md`;
- the studio is committed to git before anything moves, so the full v1 state stays in history.

## Already use Claude Code?

The plugin only acts inside a studio folder (one with a `.wp-studio` file), so the installer is
the right way to start. To look at the plugin on its own:

```
/plugin install wp-studio --marketplace daylightcreative/claude-wp-studio
```

## Security

See [SECURITY.md](SECURITY.md) for exactly what runs, what Claude can and can't do, and where
your passwords go.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The test suite runs the real tools against a real
WordPress in Docker.

---

Made by [DayLight Creative Technologies](https://daylightcreative.tech/wp-studio).
