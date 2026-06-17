# tooling/

All the scripting for the studio lives here. Three kinds of things:

## Shared tools

- **`catalog.py`** — the knowledge-base search engine. A SQLite FTS5 full-text index over
  everything in `library/`. Run it from the studio root:

  ```bash
  python3 tooling/catalog.py build                  # (re)build the index — run after adding/editing docs
  python3 tooling/catalog.py search "divi cache"    # ranked full-text search
  python3 tooling/catalog.py search "ssh" -c lessons # filter to one category
  python3 tooling/catalog.py categories             # list categories + counts
  python3 tooling/catalog.py browse lessons         # list docs in a category
  ```

  It indexes the sibling `../library` automatically. The generated `library/catalog.db`
  rebuilds from the markdown any time, so it doesn't need to be backed up or committed.

- **`save.sh`** — auto-save the whole studio: commits everything to the local git repo and,
  if a GitHub backup is linked, pushes it. Safe to run anytime; never disrupts a session.
  Run after a meaningful chunk of work and at session end: `tooling/save.sh "what changed"`.

- **`maintain.sh`** — keep the machine current and the studio tidy: updates Homebrew + CLIs,
  clears `.DS_Store` cruft, and rebuilds the catalog. A good habit at the start of a session.

- **`credentials.sh`** — the credential drop-box helper. Files a pasted secret from
  `CREDENTIALS.txt` into a project's git-ignored `.secrets/connection.env` and wipes the drop
  box back to its blank template. See the credential protocol in `../CLAUDE.md`.

## Per-project helper templates (`templates/`)

These are **templates**, not live scripts. When you set up a client project (see
`library/playbooks/client_project_setup.md`), copy the ones you need into that project's
folder and fill in its details. Each client site gets its own copies because they carry
site-specific connection info.

| Template | Becomes | What it does |
|----------|---------|--------------|
| `connection.env.example` | `projects/<client>/.secrets/connection.env` | Holds SSH host/port/user + WP path + REST app password. **`chmod 600`, never commit, never paste into chat.** |
| `wp.sh` | `projects/<client>/wp.sh` | Runs any WP-CLI command on the live site over SSH. The fastest, most authoritative way to work. |
| `db-pull.sh` | `projects/<client>/db-pull.sh` | Dumps the remote WordPress database to a local timestamped `.sql.gz` in the project's `backups/` — for backups and offline inspection. |
| `mu-plugin-css.php` | upload to the site's `wp-content/mu-plugins/` | The durable, update-proof home for custom CSS (see `library/lessons/custom_css_belongs_in_mu_plugin.md`). |

After copying a template in, make the shell scripts executable: `chmod +x wp.sh db-pull.sh`.
