# Security & Safety

Claude WP Studio is designed for a hands-off experience: you describe what you want and Claude
does the technical work. To make that smooth, it runs Claude Code with elevated autonomy.
Please read this so you understand exactly what that means and how the studio protects you and
your clients' sites.

## Bypass permissions (full autonomy)

The launcher (`studio.sh`) starts Claude Code with `--dangerously-skip-permissions`. Normally
Claude Code asks for approval before running commands or editing files; bypass mode removes
those per-action prompts so Claude can install tools, edit files, and run commands without
stopping to ask each time.

**What this means for you:**

- Claude can read, write, and run commands on your machine within whatever it's working on,
  without prompting. That is the point — it's what makes the studio feel like delegating to a
  capable assistant — but it is real power.
- **Recommendation:** use the studio in a **dedicated folder** (the installer sets one up) and,
  ideally, under an account that doesn't hold unrelated sensitive data. Treat it like giving a
  contractor a key to one room, not the whole house.
- Bypass is applied **only by the launcher**, scoped to studio sessions. It is *not* set in the
  shared project settings (Claude Code ignores bypass there by design), so it doesn't silently
  change how Claude Code behaves elsewhere on your system.

**Bypass removes prompts, not judgment.** The operating manual (`CLAUDE.md`) keeps the rules
that matter and instructs Claude to still **confirm with you** before anything irreversible or
public — touching a live site, changing DNS, deleting things, or spending money — and to:

- **discover before it touches** (read the real site state before changing anything),
- **back up before every change**,
- **work on staging or a local copy, not live**,
- **lint PHP (`php -l`) before deploying**, and
- **purge the right cache** after changes.

If you'd rather *not* run with bypass, launch Claude Code with plain `claude` from the studio
folder instead of `./studio.sh`; you'll keep the model/effort defaults and get normal approval
prompts.

## How credentials are handled

Secrets never go into the chat and never get committed.

- **The drop box.** `CREDENTIALS.txt` at the studio root is where you paste a login, SSH
  details, or an API key when Claude needs one. Claude reads it, files it into the relevant
  project's `.secrets/connection.env` (permissions `600`), confirms it works, and then **wipes
  the drop box back to blank**.
- **Git-ignored by default.** `CREDENTIALS.txt`, every `.secrets/` folder, and database dumps
  are listed in `.gitignore`, so they are never committed and never pushed to your backup.
- **No secrets in the knowledge base.** Library docs only ever *reference where* a secret
  lives, never the secret itself.

Before its first push, the studio also sanity-checks that nothing under `.secrets/` or
`CREDENTIALS.txt` is staged.

## The backup is yours

The optional cloud backup pushes to a **private GitHub repo on your own account** (connected
via `gh auth login` during install). No tokens or credentials are shipped with this kit, and
nothing is sent anywhere you didn't connect.

## Reporting a problem

If you find a security issue in the kit itself (the scripts or configuration), please open an
issue or contact the maintainer rather than disclosing it publicly.
