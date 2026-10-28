---
name: new-site
description: Onboard a client WordPress site into the studio — create the project, file its login through the drop box, connect, run a read-only discovery pass, and write the project manual (projects/<slug>/CLAUDE.md) and the client record (clients/<slug>.md). Use when the operator says "add a new site", "set up a new client", "start working on <url>", or when a project's CLAUDE.md is still the unfilled template.
---

# Onboarding a new client site

**Nothing on the site changes during onboarding.** Every command in this skill is read-only.
Onboarding ends with two local files written and a plain-language summary for the operator. If
discovery turns up something that needs fixing, report it and propose the fix; do it in a later,
separate step with a backup.

## 1. Pick the slug and create the project

Run `wpsite list` first. If the site is already there, stop and use the existing project.

Choose a short kebab-case slug from the client's name and confirm it with the operator. Use the
URL the public actually visits, with the scheme and the right `www.` choice:

```bash
wpsite init acme --url https://www.example.com
```

`init` creates `projects/acme/` (`CLAUDE.md`, `backups/`, `work/`, `.secrets/`) and fills the
`{{slug}}`, `{{url}}` and `{{date}}` placeholders in this skill's two templates,
`project-CLAUDE.md` and `client.md`. If `clients/acme.md` does not exist afterwards, create it
from `client.md` in this folder with those three values filled in.

## 2. Get the login through the drop box

**Never ask for a password, key or SSH detail in chat, and never open `CREDENTIALS.txt` or any
`.secrets/` file yourself.** `wpsite` reads them; you only ever see field names.

Tell the operator, in plain words:

> Open `CREDENTIALS.txt` in your studio folder. Below the line, paste the site's SSH (or SFTP)
> details from your hosting dashboard: host, port, username, password, and the folder WordPress
> lives in, if the host shows it. Save the file and tell me when it's done.

Then:

```bash
wpsite secrets status            # confirms the drop box has something in it
wpsite secrets file acme         # files it for the live site; prints field names only, wipes the box
```

If the output shows a field missing, ask the operator for that one field by name, through the
drop box again. If the operator pastes a credential into the chat anyway, don't repeat it back;
file it through the drop box as normal and suggest they change that password once the site is
connected.

## 3. Connect

```bash
wpsite check acme
```

- Exit 0: note the WordPress version, home URL, search visibility, host, cache layer and CLI PHP
  version it reports. These feed steps 5–7.
- Exit 4 (could not connect): ask the operator to confirm host, port and username in their hosting
  dashboard. **Don't retry in a tight loop** — a managed host has briefly refused password logins
  after about eight SSH logins in quick succession. The `site-access` skill diagnoses the rest.
- Exit 3 (refused by a safety rule): read the message and do what it says.

**If the live site reports search engines discouraged, tell the operator now.** A live site with
`blog_public = 0` serves a `noindex` tag on every page and drops out of search results; it often
arrives when a whole staging database is pushed over live.

## 4. Optional: SSH key login

Offer `wpsite key acme` once the password login works. Explain it plainly: "This sets up a key so
I stop using your password on every connection. Your host has to allow key logins; most do." Skip
it if the operator declines or the host refuses.

## 5. Staging

Ask whether the site has a staging (practice) copy. If yes, file and check it the same way:

```bash
wpsite secrets file acme:staging
wpsite check acme:staging
```

Staging should report search engines discouraged and live should not. Record the result either
way. Do not rely on `wp_get_environment_type()` to tell them apart: a managed host's staging
clone has been seen reporting `production`. The home URL is the dependable tell (the `staging`
skill covers this and the push hazards).

## 6. Discovery pass (read-only)

Run these and keep the output in the session; you need it for step 7. For a site with many pages
or post types, hand the inventory to the `site-scout` agent and spot-check what it returns.

```bash
wpsite wp acme option get home
wpsite wp acme option get siteurl
wpsite wp acme option get blog_public                     # 1 = visible to search engines
wpsite wp acme option get show_on_front                   # "page" or "posts"
wpsite wp acme option get page_on_front
wpsite wp acme option get page_for_posts
wpsite wp acme theme list
wpsite wp acme plugin list                                # includes update and auto_update columns
wpsite wp acme plugin list --status=must-use
wpsite wp acme plugin list --status=dropin                # object-cache.php, advanced-cache.php
wpsite wp acme post-type list --fields=name,label,public,hierarchical
wpsite wp acme post list --post_type=page --fields=ID,post_title,post_name,post_status --posts_per_page=-1
wpsite wp acme post list --post_type=post --format=count
wpsite wp acme user list --role=administrator --fields=ID,user_login,user_registered
wpsite wp acme cron event list
wpsite wp acme cli info                                   # the CLI's PHP, not necessarily the site's
wpsite wp acme config get DISALLOW_FILE_MODS              # an error just means "not defined"
wpsite wp acme config get DISALLOW_FILE_EDIT
wpsite wp acme config get WP_DEBUG
wpsite wp acme config get WP_ENVIRONMENT_TYPE
```

**Never run `wp config list`, and never `config get` a `DB_*` constant or a salt.** They print
secrets into the transcript.

Then answer these questions from the output:

- **Builder.** Read the front page's stored content:
  `wpsite wp acme post get <page_on_front> --field=post_content | head -c 600`. Divi 4 stores
  shortcodes starting `[et_pb_`; Divi 5 stores `<!-- wp:divi/…` block comments; core blocks start
  `<!-- wp:`. For a Divi site, read the `divi` skill before recording anything else about it.
- **Where content really lives.** Page-builder "global" modules render from a library item, not
  from the page (a Divi global module lives in an `et_pb_layout` post). Headers, footers and
  tracking scripts often live in theme options or snippet plugins. Write down every place you
  find.
- **Snippet and header-code plugins** (WPCode / Insert Headers and Footers, Header Footer Code
  Manager, Code Snippets): their code lives in the database, not in files. Note which is
  installed; the `debugging` skill says where each stores its code.
- **Hierarchical custom post types.** WordPress's old-slug redirect skips them, so a slug change
  there needs an explicit redirect. Note any.
- **Updates.** `DISALLOW_FILE_MODS` set to true turns off every automatic update, security
  releases included. If it is set and no one patches the site by hand, flag it (policy: the
  `updates-and-hardening` skill).
- **Unexpected administrators or cron hooks.** Note anything the operator can't account for;
  don't delete it during onboarding. If it looks like a compromise, switch to the
  `malware-response` skill.
- **Web PHP.** The CLI PHP can differ from the PHP that serves pages (seen on two managed hosts).
  Get the web version from the host's dashboard or **Tools → Site Health → Info → Server** in
  wp-admin, and record where to look, not the number (details: the `site-access` skill).

## 7. Write `projects/<slug>/CLAUDE.md`

Fill in the template. **Record how to look a version up, never the version itself.** On a real
site where everything auto-updated, two documents carried stale WordPress, theme and plugin
versions for three months; the fix was to record the lookup command instead. Record what stays
true: host, environments, builder, forms plugin, cache layer and how to clear it, where content
lives, and gotchas.

For the cache section, record what `wpsite check` reported (see the `caching` skill for what each
layer means). The first time you run
`wpsite purge`, add what it said it could not clear (a CDN in front of the host, for example) and
how the operator clears that part.

## 8. Write `clients/<slug>.md`

This is the durable record of the engagement: who the client is, what the site is for, what the
operator was hired to do, decisions (date, who decided, why), and a dated log. It names **where**
the secrets live (`projects/<slug>/.secrets/<env>.env`) and never holds a secret.

**Give each fact one home.** Operating procedure lives in the project `CLAUDE.md`; narrative,
decisions and the log live in the client file. When the same procedure was kept in both on a real
site, the two copies drifted apart.

Add one line to `WORKLOG.md`: the date, the new client, and that onboarding is done.

## 9. Report to the operator

Keep it short and plain:

- What the site is built with (theme or builder, forms, host) and whether it has staging.
- Anything urgent: live hidden from search engines, automatic updates switched off, plugins with
  pending security updates, administrator accounts no one recognises.
- What you'd suggest doing first, as a recommendation they can say yes or no to.

## Supporting files

- `project-CLAUDE.md` — template for `projects/<slug>/CLAUDE.md`.
- `client.md` — template for `clients/<slug>.md`.
