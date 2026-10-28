# Caching: It Differs by Host, and It Will Fool You

**Date**: 2026-06-15
**Status**: Active
**Scope**: How WordPress caching behaves on common hosts, why a change "doesn't show," and how to actually clear cache. Suspect cache before you suspect your change.

The single most common "my change didn't work" cause is **stale cache**, not a bad change.
Before re-editing anything, clear the cache and re-check. How you clear it depends entirely
on the host.

## Kinsta — the big one (and its trap)

Kinsta is the most common host for these client sites. **There are two flavors**, and they
clear differently:

| | Kinsta WITH the MU plugin | Kinsta WITHOUT it |
|---|---|---|
| Tell | `kinsta-mu-plugins` present in `wp mu-plugin list` / `mu-plugins/` | absent |
| `wp kinsta cache purge --all` | ✅ works | ❌ *"'kinsta' is not a registered wp command"* |
| `/kinsta-clear-cache-all/` URL | ✅ works | ❌ soft-404 |
| What to use instead | the command above | **MyKinsta dashboard → Sites → (site) → Tools → Clear Cache**, or the Kinsta API |

So the **first thing to check on a Kinsta site** is whether the MU plugin is installed:

```bash
./wp.sh plugin list | grep -i kinsta     # or look in wp-content/mu-plugins/
```

Extra layer: many Kinsta sites also sit **behind Cloudflare**, whose edge cache can hold a
page for **up to 24 hours** (`s-maxage=86400`). The MyKinsta "Clear Cache" purges both the
Kinsta page cache and the Cloudflare edge; a bare WP command may not. After a change that
isn't appearing, clearing via MyKinsta is the reliable move.

Note: `wp cache flush` only clears the **object cache**, not the full-page/edge cache that
visitors actually hit. It is **not** sufficient on its own.

## Other hosts

- **Hostinger / cPanel hosts:** usually a caching plugin (LiteSpeed, WP Super Cache, etc.) or
  a host-panel cache. Check `wp plugin list` for a cache plugin and clear it
  (`wp litespeed-purge all`, `wp cache flush`, or the plugin's tool), plus any panel-level
  cache.
- **Cloudflare in front of anything:** the edge can hold content. Purge in the Cloudflare
  dashboard (or via API) when a DNS/content change must show immediately.

## The rule

After **every** change that should be visible, **purge the right cache for this host**, then
hard-refresh and verify. Record the correct cache-clear method for each client in that
client's doc in `library/clients/` so you never have to rediscover it.
