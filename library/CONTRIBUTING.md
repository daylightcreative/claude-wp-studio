# Library — How to Add and Maintain Knowledge

This is the studio's WordPress knowledge base. It's the durable memory of the studio: every
hard-won lesson, every client's setup, every reusable method. Searchable by the catalog,
it's what makes Claude faster and safer on your sites over time.

**Path:** `<studio>/library`

---

## Categories

| Folder | What belongs here |
|--------|-------------------|
| `lessons/` | Hard-won, reusable lessons — host quirks, gotchas, fixes, "always do X / never do Y." One lesson per file. The single most valuable category. |
| `playbooks/` | Reusable step-by-step methods — the WordPress workflow, the Divi→Gutenberg migration, client project setup. The "how we do things." |
| `clients/` | One doc per client site: stack, where the secrets live (not the secrets themselves), decisions, and a dated work log. |
| `reference/` | External pointers and durable reference material — useful URLs, account locations, vendor docs. |

## Finding things (do this before starting any task)

```bash
python3 tooling/catalog.py search "divi cache"     # ranked full-text search
python3 tooling/catalog.py search "ssh" -c lessons # filter to a category
python3 tooling/catalog.py browse playbooks        # list a category
python3 tooling/catalog.py categories              # counts
```

`INDEX.md` has a categorized, human-readable list of every doc.

## Document format

Every doc follows this shape. The opening paragraph becomes the catalog's search
description, so make it scannable.

```markdown
# Document Title

**Date**: YYYY-MM-DD
**Status**: Active | Complete | Planning | Decided | Needs review | Superseded
**Scope**: One line on what this doc covers (when it isn't obvious from the title)

---

First paragraph: 1–3 sentences summarizing the purpose. This is the searchable blurb.

## First Section
...
```

- **File names:** `snake_case.md`.
- **Metadata is inline bold key-value pairs — no YAML frontmatter.**
- **Headings:** one `#` title, `##` for sections, `###` for subsections.
- For a multi-doc topic, group under a subfolder with a `README.md` entry point.

## Adding or changing a doc

1. **Pick the category** and **search first** — update an existing doc rather than create a
   duplicate.
2. Write or edit the doc in the format above. Update its `**Date**` (or add
   `**Last updated**`).
3. **Add/refresh its line in `INDEX.md`** under the right heading.
4. **Rebuild the catalog:** `python3 tooling/catalog.py build`.
5. Log a line in `../WORKLOG.md` (in the workbench) noting what changed.

## Writing a good lesson

A lesson should be findable later by someone who hits the same wall. Include:
- **What happened / the symptom** (so a future search by symptom finds it).
- **The root cause** (what was actually going on).
- **The fix / the rule** (what to do — or never do — going forward).
- The host/theme/context it applies to.

Cross-link related docs with normal relative links, e.g.
`[the workflow](../playbooks/wordpress_workflow.md)`.

## Don'ts

- **No secrets here.** Never store SSH passwords, app passwords, API keys, or account
  numbers. Reference *where* they live (e.g. "in the project's `.secrets/connection.env`").
- **No YAML frontmatter** — metadata is inline bold.
- **Don't skip the `INDEX.md` update** — an undiscoverable doc is a wasted doc.
