# Guide 01 — Activation Checklist

**Audience:** the Claude Code instance activating the studio for the first time. Work top to
bottom. Most of the studio ships ready-made — this is mostly **verifying, indexing, installing
any missing tools, and confirming the backup.** Keep the operator updated in plain language,
and remember: **you have bypass permissions — install whatever you need yourself; don't hand
the operator commands.**

When this checklist is done, `library/catalog.db` exists, search works, the backup is
confirmed, and every future session is fully equipped.

---

## Step 0 — Confirm you're home

- The current folder should contain `CLAUDE.md`, `START_HERE.md`, `GETTING_STARTED.md`,
  `studio.sh`, `guides/`, `library/`, `tooling/`, and `projects/`.
- If `library/catalog.db` already exists, the studio is already activated — greet the operator
  and skip to Step 6 (first-project readiness).

Open with a brief, friendly hello and a one-line plan ("I'll get your studio set up — it'll
take a minute, and I'll handle the technical parts").

## Step 1 — Environment (install what's missing yourself)

Follow **`guides/02_environment_and_tools.md`**. Verify the tools. **Anything missing that you
need, install it** (you're authorized). The essentials for activation are a **modern `python3`**
(the macOS system Python is old/locked-down — use the Homebrew one) and `sqlite3` (bundled with
Python). The installer normally handled all of this; if something's missing, install it now.
Install the WordPress/image tools (`wp-cli`, `imagemagick`, `mysql-client`) now or when the
first client task needs them.

## Step 2 — Verify the shipped pieces are present

Confirm these exist (they ship with the kit):

- `tooling/catalog.py`, `tooling/save.sh`, `tooling/maintain.sh`, `tooling/credentials.sh`,
  `tooling/templates/`
- `library/CONTRIBUTING.md`, `library/INDEX.md`
- `library/lessons/` (six lessons), `library/playbooks/` (four), `library/clients/README.md`,
  `library/reference/README.md`
- `.gitignore`, `CREDENTIALS.txt.template`, and `.claude/settings.json` at the studio root

The live credential drop box is **`CREDENTIALS.txt`** (git-ignored, so it isn't in the
download). If it doesn't exist yet, create it from the template:

```bash
[ -f CREDENTIALS.txt ] || cp CREDENTIALS.txt.template CREDENTIALS.txt
```

If anything else is missing, recreate it from the matching guide/template. Normally it's all here.

## Step 3 — Build the search catalog

This creates `library/catalog.db` — the local SQLite database that makes the knowledge
searchable. (This is the moment the studio is "activated.")

```bash
python3 tooling/catalog.py build
python3 tooling/catalog.py categories
python3 tooling/catalog.py search "divi gutenberg migration"
python3 tooling/catalog.py search "kinsta cache"
```

Confirm a non-zero document count and that searches return the seeded lessons/playbooks.

## Step 4 — Make scripts executable

```bash
chmod +x tooling/catalog.py tooling/save.sh tooling/maintain.sh tooling/credentials.sh studio.sh
```

## Step 5 — Confirm the backup

Follow **`guides/04_git_and_backup.md`**. The studio is a git repo; your work auto-saves.

```bash
tooling/save.sh "Studio activated"
```

- If a GitHub backup was linked during install, this reports "backed up to GitHub ✓".
- If not, it reports "saved locally" — that's fine. Mention to the operator that they can
  connect a private GitHub backup anytime (see `guides/04_git_and_backup.md`); don't block on it.
- **Before any push, confirm `git status` shows nothing under `.secrets/` or `CREDENTIALS.txt`.**
  Secrets must never reach GitHub.

## Step 6 — Prepare for the first project (no site access yet)

Read **`library/playbooks/client_project_setup.md`** and skim
**`library/playbooks/wordpress_workflow.md`**. Do **not** create a project or touch any live
site yet. Just be ready to propose the first step when the operator wants to start: set up
their site as a project and do a no-changes discovery pass.

## Step 7 — Wrap-up for the operator

Save your work (`tooling/save.sh "Studio activated"`), then give the operator a short,
plain-language wrap-up:

- ✅ Your studio is ready. (It now has a searchable notebook that already knows a stack of
  WordPress lessons, so I'll be careful and fast on your sites. Your work is saved
  automatically.)
- The only things you do day-to-day: open this folder, run `./studio.sh`, and talk to me.
- The recommended next move: set up your first WordPress site as a project whenever you're
  ready — I'll need the site's login details (you can drop them in `CREDENTIALS.txt`).

Then you're done. Future sessions begin from `CLAUDE.md` automatically.
