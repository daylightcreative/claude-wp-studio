# Guide 04 — Git & Automatic Backup

**Audience:** Claude. The operator never has to think about git; you handle it.

The studio is a **git repository**. Your job is to keep everything saved automatically, so the
operator never thinks about it. If a private GitHub backup was linked during install, saves also
push to the cloud; if not, saves stay local until they connect one.

## The mental model for the operator

If they ask whether their work is saved: *"Yes — it's committed locally"* (add *"and backed up
to your private GitHub copy"* if a remote is linked). Keep the language plain; don't make them
learn git unless they want to.

## How saving works

- **`tooling/save.sh`** stages everything, commits with a sensible message, and (if an `origin`
  remote exists) pushes to the private GitHub backup. It's safe to run anytime — it no-ops when
  there's nothing to save and never disrupts a session if the network/remote isn't available.
- **Run it yourself** after finishing a meaningful chunk of work and at the **end of every
  session**:
  ```bash
  tooling/save.sh "Short description of what changed"
  ```
- **Session-end hook:** the shipped `.claude/settings.json` registers a `SessionEnd` hook that
  runs `tooling/save.sh` automatically, so a save happens even if you forget. Running it
  manually *and* via the hook is harmless.

## What never gets backed up

The `.gitignore` excludes secrets and large dumps:
- `.secrets/` and `projects/**/.secrets/` (passwords, tokens, connection info)
- `CREDENTIALS.txt` (the credential drop box)
- `projects/**/backups/`, `*.sql`, `*.sql.gz` (database dumps)
- `library/catalog.db` (rebuilds from markdown)

**Before the first push, sanity-check** that `git status` does not list anything under
`.secrets/` or `CREDENTIALS.txt`. Secrets must never reach GitHub.

## Connecting a private GitHub backup (optional, the operator's own account)

The backup goes to a **private repo under the operator's own GitHub account** — nothing is
shipped with the kit, and no token is stored in the repo. If it wasn't set up during install,
you can connect it anytime:

```bash
gh auth login                                              # one-time, the operator's account
git -C "$(pwd)" rev-parse --is-inside-work-tree >/dev/null 2>&1 || git init -b main
tooling/save.sh "Initial studio"                          # ensure there's a commit
gh repo create claude-wp-studio --private --source=. --remote=origin --push
```

`gh auth login` is interactive (it needs the operator's GitHub sign-in) — present it to them
plainly as a one-time step, or skip it and keep saving locally. From then on, `tooling/save.sh`
pushes automatically using the `gh`/git credentials the operator set up.

## If a push fails

`save.sh` handles it gracefully: the work is committed locally and the push retries on the next
save. Don't surface the failure unless the operator asks; if it keeps failing, tell them plainly
what's wrong (e.g. "the GitHub login expired — want to reconnect it?").
