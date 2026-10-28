---
name: staging
description: Staging sites are a hazard as well as a safety net — a push can deindex live, staging can mail real people, fall behind on security patches and sit public on the internet. Covers detecting which environment you are on, pushing safely, search visibility, password protection, keeping staging patched, and blocking outbound email and webhooks with the bundled staging-guard mu-plugin. Use when creating, using, pushing or auditing a staging environment, or before testing forms, email or integrations on one.
---

# Staging: use it, and guard it

Use staging (`acme:staging`) for anything risky: updates, conversions, new code. But treat it
as a second production site with its own risks. Five things go wrong, all seen on real sites:

1. **A push deindexes live.** A push that copies the database carries staging's "discourage
   search engines" setting (`blog_public = 0`) onto production. WordPress gives no warning; the
   client quietly drops out of Google.
2. **Staging mails real people.** A clone carries live's forms, notification addresses,
   newsletter feeds and webhooks. A test submission can add a real person to a real list.
3. **Staging falls behind on patches.** Auto-updates and licences often don't follow it. One
   staging copy sat months behind live, running a form plugin with an unauthenticated
   file-upload flaw, while publicly reachable.
4. **Staging is public.** A `*.host-staging-domain` URL is reachable by anyone and by crawlers
   unless it is password-protected.
5. **Code thinks staging is production.** See the next section.

## Know which environment you are on

**Decide by `home_url()`, never by `wp_get_environment_type()` or a constant naming the
environment.** `wp_get_environment_type()` returns `production` by default when nothing sets
`WP_ENVIRONMENT_TYPE`, and at least one managed host's staging copies report `production`. A
constant or option that names the environment gets copied by a push and confidently reports the
wrong answer on the environment that matters most. The URL a copy serves is the truth:

```bash
wpsite wp acme:staging option get home
wpsite check acme:staging       # also reports home URL and search visibility
```

In code, compare the normalized host of `home_url()` with the known production host, and treat
an unknown host as a failure to report, never as a pass. The bundled `staging-guard.php` does
exactly this.

## Search visibility: lock it per environment

Production must have `blog_public = 1`; staging must have `blog_public = 0`. Check both after
any push, clone or restore:

```bash
wpsite wp acme option get blog_public            # must be 1
wpsite wp acme:staging option get blog_public    # must be 0
```

- **Before any push to live, ask the operator to check the push options**, and after it, check
  live's `blog_public` immediately. Plain version: *"Pushing staging to live copies its settings,
  including 'hide from Google'. I'll check that right after, because if it sticks the site drops
  out of search."*
- **For a site you maintain long-term, make it a guarantee, not a habit:** an mu-plugin check that
  derives the environment from `home_url()` and raises an admin notice or Site Health failure if
  production is not indexable or staging is.
- **Staging's robots.txt will look permissive. That is correct.** Modern core's `do_robots()`
  no longer prints `Disallow: /` for a non-public site (checked against WordPress 7.1); the real
  signal is the `<meta name='robots' content='noindex, nofollow' />` tag that `blog_public = 0`
  produces.
- **Do not add `Disallow: /` to staging's robots.txt.** Blocking the crawl stops search engines
  from ever seeing the `noindex`, which is how staging URLs end up stuck in results as bare
  links. Password-protect instead, and leave the crawl path open.

## Password-protect staging

A login prompt in front of staging stops crawlers and the public entirely.

- **Kinsta: dashboard only.** Kinsta's API has no password-protection endpoint (checked against
  its OpenAPI spec), so it cannot be scripted. The operator does it: MyKinsta → Sites → the site
  → the staging environment → Tools → Password protection. **It refuses to turn on while CDN or
  Edge Caching is enabled for that environment** — switch those off first.
- **Other hosts:** use the host panel's directory-password feature. UNVERIFIED per host; ask the
  operator what the panel offers.
- **After it is on, every anonymous HTTP request returns 401**, including `robots.txt`,
  `wp-sitemap.xml` and `wp-login.php`. A 401 from curl is correct, not a fault. `wpsite` is
  unaffected, because WP-CLI over SSH is not HTTP — so verify server-side. For example, render a
  form with `do_shortcode()` through `wp eval-file --use-include` instead of fetching the page.
- On Kinsta, `wp kinsta cache purge` fails if `/kinsta-clear-cache-all/` is password-protected
  (Kinsta docs), so expect `wpsite purge` to report that on a protected staging site.
- When the operator shares staging with a client, they share the password too; say so.

## Block outbound email and webhooks

Install the bundled guard on **every** environment, staging and production (a push carries
files anyway, and on production it does nothing):

```bash
# copy staging-guard.php from this skill's folder to projects/acme/work/ first
wpsite backup acme:staging
wpsite deploy acme:staging projects/acme/work/staging-guard.php wp-content/mu-plugins/staging-guard.php
```

Then set, in `wp-config.php` on **every** environment, the **same** value:

```php
define( 'WPSTUDIO_PRODUCTION_URL', 'https://example.com' );
define( 'WPSTUDIO_STAGING_BLOCKED_HOSTS', 'hooks.zapier.com' );   // optional, comma-separated
```

Prefer `wpsite backup acme --file wp-config.php` and then `wpsite wp acme config set
WPSTUDIO_PRODUCTION_URL 'https://example.com'` (no `--raw`: it is a string; see
`wp-studio:safe-changes` §5).

What it does when `home_url()` is not the production URL:

- **Email:** short-circuits `wp_mail()` through the `pre_wp_mail` filter (WordPress 5.7+) and
  reports the mail as sent, so forms can be tested end to end; each suppressed message is logged
  to the PHP error log.
- **Webhooks and APIs:** refuses requests to the listed hosts (and their subdomains) through
  `pre_http_request` with a `WP_Error`, logged. Other requests — updates, licence checks — pass.
- **Fails closed:** if `WPSTUDIO_PRODUCTION_URL` is missing, it blocks mail everywhere and shows
  administrators a red notice. So set the constant on production first, then deploy the file.

Verify on both environments:

```bash
wpsite wp acme:staging eval 'var_dump( wpstudio_sg_is_production() );'   # bool(false)
wpsite wp acme eval 'var_dump( wpstudio_sg_is_production() );'           # bool(true)
```

Limits — tell the operator about these rather than assuming they are covered:

- **Only mail sent through `wp_mail()` and requests made through the WordPress HTTP API.** A
  plugin that opens its own SMTP connection or calls an external API with raw cURL bypasses
  both filters. List the site's mail and integration plugins and check each one.
- **Find the hosts to block from the site's own configuration** (form feeds, newsletter
  integrations, CRM add-ons), not from memory.
- **Scheduled jobs on staging still run.** Server cron jobs copied with a clone can import,
  sync or send from staging; check `wpsite sh acme:staging 'crontab -l'` and WP-Cron
  (`wpsite wp acme:staging cron event list`).

## Keep staging patched and in parity

When staging is used again after a gap, bring it to parity before testing anything:

```bash
wpsite wp acme plugin list --fields=name,status,version,update_version
wpsite wp acme:staging plugin list --fields=name,status,version,update_version
wpsite wp acme:staging core version
```

- Compare versions with live; premium plugins with no update channel on staging may need their
  files deployed from live (pull from live, deploy to staging).
- A staging site that is behind is a security exposure while it is public. Plain version: *"The
  test copy of the site is running old software and anyone can reach it. I'd like to update it
  and put a password on it."*
- **A fresh clone can come up with a lower PHP memory limit** and 500 under a heavy theme. On
  Kinsta, PHP memory is set in MyKinsta only — `.user.ini`/`php.ini` values are ignored — so the
  operator raises it there.

## Before and after a push to live

1. `wpsite backup acme` (live) — the push overwrites it.
2. Confirm with the operator what the push copies (files, database, or both) and get a yes; it is
   irreversible without the backup.
3. After: `option get blog_public` on live (must be 1), `option get home` on live (must be the
   production URL), `wpsite purge acme`, and a cache-busted check of key pages (see
   `wp-studio:caching`).
4. If the push copied the database, check live's outbound integrations still work: the guard is
   inert on live, but any staging-only settings (test API keys, a test mail mode) came across.
