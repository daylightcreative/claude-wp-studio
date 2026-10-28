---
name: launch-qa
description: Quality-check a WordPress site before launch or after a significant change — links, images and alt text, mobile overflow, forms, search visibility, redirects, Open Graph and meta tags, feeds — against fresh, uncached pages, fanning out one qa-checker agent per dimension. Use when the operator asks "is it ready to launch?", "check the site", "QA staging", before a staging-to-live push or DNS cutover, after a redesign or migration, or after a plugin/theme update that touched layout or forms.
---

# Launch and post-change QA

**Every check reads a fresh page and reports evidence.** A check that read a cached copy has
checked nothing: on a real site a fix was signed off as "verified" from a cached page while the
live page was still broken. Every finding carries the URL, what was expected, what was seen, and
the command or measurement that showed it.

**QA changes nothing on the site, with one exception: form tests submit real entries.** Tell the
operator before submitting forms, and know where each form's notifications go.

## 0. Set up

1. Settle which environment you're checking (`acme` or `acme:staging`) and, for a launch, which
   one it will replace.
2. Run `wpsite purge <site>` and note what it says it could not clear (see the `caching` skill).
3. **Bust the cache on every request.** Append a unique query string to every URL you fetch,
   in curl and in the browser: `https://www.example.com/about/?cb=$RANDOM`. On the managed hosts
   this kit was built on, that forces a fresh render. Whether a given host's cache ignores query
   strings is **UNVERIFIED** per host; if the host sends a cache-status response header, confirm a
   miss there.
4. **Read stored content from the database, not the page.** `wpsite wp <site> post get <id>
   --field=post_content` and `option get` have no page cache in the way; use them to separate
   "what's stored" from "how it renders".
5. Build the page list: the XML sitemap (`/wp-sitemap.xml` in core, or the SEO plugin's index),
   plus `wpsite wp <site> post list --post_type=page,post --post_status=publish
   --fields=ID,post_name,url --posts_per_page=-1`. For a migration, also get the **old** site's
   sitemap: it is the redirect test list.

## 1. Fan out

For more than a handful of pages, launch one `qa-checker` agent per dimension below (sections
2–9, skipping forms — see section 6), in parallel and in the background, so the operator can keep
working. Give each agent, in its prompt:

- the site URL(s) and which is live,
- the page list (or where to read it in `projects/<slug>/work/`),
- that dimension's section of this skill, copied in full, and
- the return format the agent defines.

Then **re-check a sample of each agent's failures yourself** before reporting them. An agent
doesn't grade its own work. For a small site (roughly under ten pages) run the checks yourself.

## 2. Search visibility

**Live must be visible; staging must not.**

```bash
wpsite wp acme option get blog_public            # live: 1
wpsite wp acme:staging option get blog_public    # staging: 0
curl -s "https://www.example.com/?cb=$RANDOM" | grep -io "<meta name=['\"]robots['\"][^>]*>"
```

On live, no page should carry `noindex` unless the operator chose it for that page; check a sample
of pages, because an SEO plugin can set it per page.

- A host's "push staging to live" that copies the whole database carries `blog_public = 0` onto
  live with no warning. Re-check live right after every push.
- In WordPress 7.1.1, core's `robots.txt` no longer prints `Disallow: /` for a hidden site; the
  signal is the `noindex` meta tag. A permissive-looking `robots.txt` on staging is correct.
- **Don't add `Disallow: /` to staging.** Crawlers that can't fetch a page never see its
  `noindex`, and the URL can sit in search results as a bare link. Password-protect staging
  instead (the `staging` skill).

## 3. Links

- Every internal link on every page returns 200, or a single 301 to a 200. Report chains and
  loops.
- **No link or asset on live points at the staging host.** Search stored content too:
  `wpsite wp acme db search 'staging-host.example' --stats` (add `--all-tables-with-prefix` to
  include plugin tables).
- **Unlinked buttons.** A URL pasted into a button block's "HTML anchor" field instead of its link
  renders a button with no `href` that does nothing. Find them in the rendered page:
  `curl -s "<url>?cb=$RANDOM" | grep -o '<a class="wp-block-button__link[^>]*>' | grep -v 'href='`.
- Click the main calls to action in a real browser, logged out.

## 4. Images and alt text

- No image request returns 404.
- Every content image has an `alt` attribute. Meaningful images need real text; decorative images
  take `alt=""`. Hidden tracking pixels and a forms plugin's honeypot field show up in automated
  "missing alt" and "strange field" counts — exclude them before reporting.
- Content images should carry `srcset`. Core adds `srcset`, `sizes`, `width` and `height` only to
  an `<img>` with a `wp-image-<ID>` class tied to an attachment; a hand-coded `<img>` without it
  serves the full original. Flag any image file far larger than its display slot (one real page
  served a 5184 px, 8 MB original into a 376 px slot). Fixes belong to the `images` skill.

## 5. Mobile overflow

**Measure, don't eyeball.** A downscaled screenshot hides overflow and misreads alignment. At a
390 px-wide viewport, run this in the page (browser tool's evaluate) and expect an empty list:

```js
[...document.querySelectorAll('*')]
  .filter(e => e.getBoundingClientRect().right > innerWidth + 1)
  .map(e => [e.tagName, e.className, Math.round(e.getBoundingClientRect().right)]);
```

Report each offender. Common causes: a hidden desktop menu that still takes up width, a
"full-bleed" image positioned with offsets, and `grid-template-columns: 1fr` (its minimum grows to
the widest item; `minmax(0, 1fr)` does not). `overflow-x: hidden` or `clip` on `html` hides the
scrollbar but leaves content off-screen; it is not a fix.

## 6. Forms (main loop, not an agent)

**Submit every form once, for real, and confirm both ends:** the entry is saved, and the
notification arrives where the client expects it. Do this yourself, with the operator's go-ahead —
`qa-checker` agents don't change sites. Use a working address the operator controls.

- **Gravity Forms rejects `@example.com` and `@domain.com` addresses** in email fields as spam
  (filter `gform_email_field_rejectable_values`, in `GF_Field_Email` since Gravity Forms 2.9.15;
  confirmed in 3.2.0). The error looks like a broken form. Use a real address.
- On staging, find out where mail goes before submitting. If staging has no mail guard, a test
  can email the real client (the `staging` skill ships one).
- **Upload fields: narrow the allowed file types** to what the form needs (images and PDF are
  usually enough). On a real site a form plugin's default accepted 104 file types, and an
  arbitrary-upload vulnerability in that plugin was used to drop executable files into uploads.
  Report a wide allowlist as a finding.
- CAPTCHA keys are usually tied to a domain; at a domain change, test that the form still submits
  on the new domain.
- After any update to the forms plugin, repeat one real submission per form.

## 7. Redirects

- For a migration or slug change, every old URL (from the old sitemap) resolves on the new site
  with 200, or one 301 to the right page. On a real rebuild this check found 845 of 846 URLs
  resolving; the missing one was a plugin-generated file.
- **Hierarchical post types don't get WordPress's automatic old-slug redirect.** A changed slug
  there needs an explicit 301.
- Test logged out, and once with a search-engine referrer. A redirect that fires only for some
  visitors is a known malware behaviour; see the `debugging` skill's "every link redirects to one
  page" section.

## 8. Open Graph and meta

For each page, in the rendered `<head>`:

- One `<title>`, one meta description, one canonical — and the canonical points at the live host.
- `og:title`, `og:url`, `og:type` and `og:image` each appear **exactly once**. Two emitters (an SEO
  plugin plus a theme or snippet) on a real site produced two contradictory sets. If a tag's
  source isn't obvious, use the `debugging` skill's head-tag attribution.
- `og:image` loads, and is the common 1200 × 630 share size where the client cares about link
  previews. Social platforms cache previews of links already shared; new shares pick up changes.

## 9. Feeds and sitemaps

```bash
curl -s "https://www.example.com/feed/?cb=$RANDOM" | xmllint --noout - && echo feed-ok
curl -s "https://www.example.com/wp-sitemap.xml?cb=$RANDOM" | xmllint --noout - && echo sitemap-ok
```

Use the SEO plugin's sitemap path if it replaces core's. On a real site both were invalid XML
because a plugin file ended with `?>` followed by blank lines, so every response began with two
line breaks. The fix is removing the closing `?>`; find the file with the `debugging` skill.

## 10. Report

Give the operator one table — dimension, pass or fail, count of findings — then the findings,
blockers first. A **blocker** stops a launch: live hidden from search, a form that doesn't deliver,
broken primary navigation or calls to action, staging URLs on live, redirects missing for pages
that had traffic. Everything else is a list to fix after launch, in plain words.

Record the run in the client's log (`clients/<slug>.md`): date, environment, result.
