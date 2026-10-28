---
name: caching
description: How WordPress caching layers differ by host (Kinsta, Cloudways, LiteSpeed hosts, Cloudflare in front), what `wpsite purge` clears and what it cannot, and how to prove a change is really live. Use when a change "doesn't show", after any visible change, before telling the operator something is fixed, or when choosing how to clear cache on a host.
---

# Caching: suspect it before you suspect your change

The most common cause of "my change didn't work" is a stale cache, not a bad change. Before
re-editing anything: purge, cache-bust, re-check. And never report a fix as live from a page
that might have come from cache — a reviewer once signed off a "fixed" modal from a cached page
while the real one was still broken.

## The layers

A visitor's request can be answered by any of these, outermost first:

| Layer | Holds | Cleared by |
|---|---|---|
| Browser cache | Pages, CSS, JS, images for that one person | Shift-reload, or a changed asset URL |
| Edge / CDN (Cloudflare, host CDN) | Whole pages and assets near the visitor | Host purge or the CDN's own purge |
| Server page cache (host full-page cache, Varnish, a cache plugin) | Rendered HTML | Host purge or the plugin's purge |
| Builder output caches (Divi `et-cache`, Elementor CSS) | Generated CSS per post | The builder's own save hook, or deleting the files |
| Object cache (Redis, Memcached) | Database query results | `wp cache flush` |
| PHP opcode cache | Compiled PHP | `wpsite deploy` resets it (see `wp-studio:safe-changes`) |

`wp cache flush` clears **only the object cache** (WP-CLI docs: "Flushes the object cache").
It never clears the page cache visitors actually hit. On multisite with a persistent object
cache it typically flushes every site.

## `wpsite purge`

```bash
wpsite purge acme
```

It clears the page cache the right way for the detected host and **says plainly what it could
not clear.** Read that output every time; whatever it lists as not cleared is now your job —
either another command, or a plain-words request to the operator. Layers no server-side purge
can reach:

- **Visitors' browsers.** Nothing on the server clears them. Versioned asset URLs (below) make
  them fetch the new file; for a person who already loaded the page, Shift-reload.
- **A Cloudflare zone the client runs themselves** (separate from the host's own Cloudflare
  integration). That needs the Cloudflare dashboard or API with the client's access. Plain
  version to the operator: *"The site sits behind Cloudflare, which keeps its own copy. Please
  open Cloudflare → Caching → Purge Everything, or give me access."*
- **Builder CSS caches** written when a post was saved with the theme skipped (Divi
  `et-cache`). See `wp-studio:safe-changes` §5.
- **Panel-only caches** on hosts with no CLI purge (Cloudways Varnish and Breeze, below).

## By host

**Find the host and layers first:** `wpsite check acme` reports the host and cache layer. Then
read the response headers of a cache-busted request:

```bash
curl -sI "https://example.com/?cb=$RANDOM" | grep -iE 'server|cache|x-kinsta|ki-|cf-|age|x-varnish|x-litespeed'
```

### Kinsta

- **Needs the Kinsta must-use plugin** (`kinsta-mu-plugins` in `wp-content/mu-plugins/`). With
  it, `wp kinsta cache purge` clears the full-page cache and, when Edge Caching is on, the edge
  cache; `wp kinsta cache purge --all` clears everything (Kinsta docs). Without it, the command
  does not exist ("'kinsta' is not a registered wp command") and the purge has to happen in
  MyKinsta → the site → the environment → Tools → Clear cache. Check:
  `wpsite wp acme plugin list --status=must-use` (WP-CLI has no `mu-plugin` command).
- **The WP-CLI purge fails if `/kinsta-clear-cache-all/` is password-protected or restricted**
  (Kinsta docs) — relevant to a password-protected staging site.
- **Manual purges are rate-limited to one every 10 seconds**, from MyKinsta, wp-admin or
  WP-CLI alike. Don't loop purges.
- **Edge Caching runs on Cloudflare.** Clearing it across all data centres can take **2–5
  minutes** after the purge reports done; the edge cache expires every 24 hours by default.
  Wait before concluding a purge failed.
- **Headers:** `X-Kinsta-Cache: HIT` means the page came from Kinsta's page cache; edge caching
  only stores pages that are already in that cache. With Edge Caching, `ki-cache-type: Edge` and
  `Ki-CF-Cache-Status: HIT` (Kinsta docs). An HTTP→HTTPS redirect answered with
  `Server: cloudflare` came from the edge and never reached WordPress.
- **Purge from code** (for a deploy step or a plugin), with Kinsta MU plugin 3.7.0:
  `global $kinsta_cache; $kinsta_cache->kinsta_cache_purge->purge_complete_site_cache();`
  This is the MU plugin's internal object, not a documented API — check it exists before
  calling it, and re-verify after the MU plugin updates.

### Cloudways

- **Three layers:** Varnish, the Breeze page-cache plugin, and often an object cache on Redis.
- **There is no `wp breeze` command.** Varnish and Breeze purge from the Cloudways panel or the
  WordPress admin toolbar; tell the operator when that is needed. The Redis object cache clears
  with `wp cache flush` (or the object-cache plugin's own command when that plugin is active —
  check `wpsite wp acme help` rather than assuming).
- Cached responses made a full update pass look like a no-op: the homepage came back
  byte-identical to the pre-update baseline until the request was cache-busted.

### LiteSpeed hosts (many cPanel and Hostinger plans)

- Usually the LiteSpeed Cache plugin. With it active, `wp litespeed-purge all` purges every
  cache entry (LiteSpeed docs; on multisite, every site in the network). Check
  `wpsite wp acme plugin list` first.
- The host panel may hold another cache layer. UNVERIFIED per host — check the panel and ask
  the operator.

### Any other host

Look for a cache plugin in `plugin list` and use its documented CLI command, or its admin
button through the operator. Never guess a command name: run `wpsite wp acme help` and look for
it.

## Make cache stop being a problem

- **Version your own assets by file time.** A static `?ver=1.0.0` keeps the same URL, so
  browsers and CDNs keep the old file after every deploy. Pass `filemtime()` of the file as the
  `$ver` argument to `wp_enqueue_style()` / `wp_enqueue_script()` so the URL changes with every
  edit.
- **Additional CSS lives in the page.** The Customizer's Additional CSS is printed inline in
  `<head>` (`<style id="wp-custom-css">`), so it only reaches visitors when the **page** cache
  is cleared; flushing the object cache is not enough.
- **Record the right purge method** in the client's `CLAUDE.md` once you have proven it, so the
  next session doesn't rediscover it.

## Prove a change is live

Do all of these before telling the operator it is done:

1. `wpsite purge acme`, and handle whatever it says it could not clear. On Kinsta with Edge
   Caching, allow 2–5 minutes.
2. Fetch with a unique query string on every request, and check several pages, not only the
   homepage:
   ```bash
   for p in "" "contact/" "wp-login.php"; do
     curl -sS -o /tmp/p.html -w "/$p %{http_code} %{size_download}\n" -L "https://example.com/$p?cb=$RANDOM"
     grep -ciE 'fatal error|parse error' /tmp/p.html
   done
   ```
   For a browser check, add `?cb=<unique>` to every navigation.
3. Grep the fresh HTML for a marker of your change (a class name, a comment, the new text).
4. Read the stored value from the database (`wpsite wp acme post get …`, `option get …`); it
   has no page cache.
5. If the page still shows the old version, compare headers on a busted vs. an unbusted request
   to see which layer is holding it.

A unique query string makes that one request a cache miss on the setups we have used. It is
not guaranteed everywhere — a CDN can be configured to ignore query strings — so if a busted
request still shows a cache `HIT`, trust the header, not the URL. It also does **not** tell you
what an ordinary visitor sees; for that, fetch the plain URL after the purge and check
the cache headers show a fresh copy (`MISS`, or an `Age` near zero).
