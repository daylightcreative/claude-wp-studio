# Guide 03 — How the Studio Works

**Audience:** Claude. A quick map of how the three areas, the catalog, and the daily habits
fit together.

## The three areas (all under the studio root)

- **`library/`** — durable knowledge. Lessons, playbooks, per-client docs, reference. Indexed
  by the catalog. This is the studio's memory.
- **`tooling/`** — the scripts. `catalog.py` (search), `save.sh` (auto-backup), `maintain.sh`
  (housekeeping), `credentials.sh` (the drop-box helper), and per-project helper templates in
  `templates/`.
- **`projects/`** — one folder per client site: working files, `backups/`, `.secrets/`.

The operating rules live in `../CLAUDE.md` (auto-loaded every session). The library's own
rulebook is `library/CONTRIBUTING.md`.

## The catalog (search before you work; rebuild after you write)

The knowledge base is a SQLite full-text index built from the markdown in `library/`.

```bash
python3 tooling/catalog.py search "<topic>"   # before starting anything
python3 tooling/catalog.py build               # after adding/editing any library doc
python3 tooling/catalog.py categories
python3 tooling/catalog.py browse lessons
```

**Always search first.** A two-minute search of past lessons routinely saves hours and
prevents repeating a mistake on a client's live site.

## Document conventions (short version)

Full rules in `library/CONTRIBUTING.md`. The essentials:

- `snake_case.md`, one topic per file.
- Start with `# Title`, then `**Date**`, `**Status**`, `**Scope**`, then a 1–3 sentence
  summary paragraph (that paragraph becomes the searchable blurb).
- Metadata is **inline bold** — no YAML.
- After writing: update `library/INDEX.md`, run `catalog.py build`, log a line in
  `../WORKLOG.md`.

## How knowledge flows

The bench (`projects/`, scratch work) is where things happen; the **library is where the
lessons stay.** When you learn something durable:

1. Write it as a lesson/playbook/client-doc in `library/`.
2. Index it (`catalog.py build`).
3. Note it in `WORKLOG.md`.

Future sessions inherit it automatically. That compounding memory is the whole point of the
studio.

## Working with the operator

The operator is in the room: they set design direction, content, and approvals — talk to them
in plain language. When you need a credential or a decision that's theirs, ask directly (use
the credential drop box for anything secret). There's no other human in the loop; you and the
operator settle everything together.
