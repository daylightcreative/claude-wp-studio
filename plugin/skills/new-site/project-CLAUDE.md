# {{slug}} — project manual

Live site: {{url}}
Project created: {{date}}
Client record (engagement, decisions, log): `../../clients/{{slug}}.md`

This file is the operating manual for this site. It owns procedure. Narrative, decisions and the
work log live in the client record. Keep each fact in one place.

## Look it up, don't write it down

Versions change under auto-updates, so this file never records them. Ask the server:

| Question | Command |
|---|---|
| WordPress version | `wpsite wp {{slug}} core version` |
| Themes and versions | `wpsite wp {{slug}} theme list` |
| Plugins, versions, pending updates, auto-update | `wpsite wp {{slug}} plugin list` |
| Must-use plugins and drop-ins | `wpsite wp {{slug}} plugin list --status=must-use` / `--status=dropin` |
| CLI PHP | `wpsite wp {{slug}} cli info` |
| Web PHP (what serves pages) | (fill in: host dashboard location, or wp-admin → Tools → Site Health → Info → Server) |
| Everything at once | `wpsite check {{slug}}` |

## Environments

| Environment | Site | Home URL | Search visibility (expected) |
|---|---|---|---|
| Live | `{{slug}}` | {{url}} | visible (`blog_public` = 1) |
| Staging | (fill in: `{{slug}}:staging`, or "none") | (fill in) | hidden (`blog_public` = 0) |

How staging is made and pushed: (fill in: host tool, and whether a push copies the whole
database — if it does, check `blog_public` on live right after every push)

## Stack (stable facts only)

- Host: (fill in)
- Theme / builder: (fill in, e.g. "child theme of X; content built with Y")
- Forms plugin: (fill in) — where notifications go: (fill in)
- SEO plugin: (fill in) — owns titles, meta, Open Graph: (fill in yes/no; note any second emitter)
- Snippet / header-code plugin: (fill in, or "none")
- Hierarchical custom post types (slug changes need an explicit redirect): (fill in, or "none")
- Automatic updates: (fill in: who patches this site; whether `DISALLOW_FILE_MODS` is set)

## Clearing the cache

Run `wpsite purge {{slug}}`. It clears: (fill in from its output).
It cannot clear: (fill in, and how the operator clears that part, or "nothing").
After any visible change, verify with a cache-busting query string (`?cb=<random>`), not a plain
reload.

## Where content really lives

(fill in: anything that does not render from the page you'd expect — global modules, theme
options, header/footer code, widgets, template parts, snippet plugin entries)

## Gotchas

(fill in: one line each, with the date found)

## Working rules for this site

- Talk to the site only through `wpsite`. Back up with `wpsite backup {{slug}}` before any change.
- Try substantial changes on staging first, when staging exists.
- Skills: `new-site`, `launch-qa`, `debugging`, `big-jobs` (and the rest of the wp-studio set).
