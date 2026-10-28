---
name: site-access
description: Diagnosing why `wpsite` cannot reach a site — connection refused vs. timeout vs. authentication failure, custom SSH ports, password vs. key login, a changed host key (possible attack — confirm before `wpsite trust-host`), rate limits on rapid logins, hosts with SFTP/FTPS but no shell, and why the PHP version WP-CLI reports may not be the site's. Use when `wpsite` exits 4, a login is refused, a host-key warning appears, a host offers no SSH, or a PHP version matters.
---

# Site access through `wpsite`

`wpsite` is the only route to a site; never fall back to raw `ssh`, `scp`, `sftp` or `rsync`
(a hook blocks them, and they bypass the backup gate and connection handling). When it cannot
connect it exits **4**. Read its message, then sort the failure into one of the cases below
before changing anything — most "wrong password" problems are not wrong passwords.

Start with what is configured (field names only, never values):

```bash
wpsite list
wpsite secrets status acme
wpsite check acme          # the first command to run against any new site
```

## Which failure is it?

| What you see | Usually means | Do |
|---|---|---|
| **Connection refused** | Nothing listening on that host and port: wrong port, SSH not enabled on the plan, or the host blocks your IP | Check the port in the host panel; ask the operator whether SSH is enabled |
| **Timed out** | Wrong host or IP, a firewall dropping packets, or the server is down | Check the host name; check the site loads in a browser |
| **Permission denied (publickey,password)** | The server answered and rejected the login: wrong user, wrong password, key not installed, or a temporary lockout | See "Authentication" below |
| **Host key changed / identification has changed** | The server presented a different key than last time | See "Host key changed" — **stop first** |
| Connected, but WP-CLI says it is not a WordPress install | Wrong environment, or the WordPress root differs from what the project records | `wpsite check acme` and compare the home URL |

## Custom ports

Managed hosts rarely use port 22; some use a different high port for each environment of the same
site (live and staging can share an IP and differ only by port). Take the port from the host's
dashboard for **that environment**, give it to the operator to paste into `CREDENTIALS.txt`, and
file it:

```bash
wpsite secrets file acme:staging
```

A connection to the right IP on the wrong port reaches the other environment or nothing — always
confirm with `wpsite check` that the home URL is the one you meant.

## Authentication

- **Password or key.** Many hosts start with password login. Set up a key so the password is not
  in play on every connection: `wpsite key acme`. Use it per environment.
- **A burst of logins can lock you out briefly.** On one managed host, about eight logins in quick
  succession were followed by a short password refusal on live, with the right password.
  `wpsite` reuses one connection for a run of commands, so this mostly shows up when many separate
  `wpsite` invocations fire in parallel (for example several sub-agents). Run site commands one
  after another, combine read-only checks into one `wpsite sh` call, and if a correct password
  is refused, wait a few minutes before retrying — don't retry in a loop.
- **The password really changed.** Hosts let clients rotate SFTP/SSH passwords, and rotating them
  is good practice after any incident. Ask the operator for the current one; never guess or reuse
  another environment's.
- **Never paste credentials into chat or a command line.** The operator puts them in the drop
  box and `wpsite secrets file` files them.

## Host key changed — treat it as a possible attack until confirmed

When a server's host key changes, SSH refuses to connect. Hosts do rotate keys (a managed host
has done so with the same IP and port), but **a changed key is also exactly what a
man-in-the-middle looks like**. Re-trusting blindly would hand the site's credentials to whoever
answered.

1. Stop. Do not run anything else against that site.
2. Tell the operator in plain words: *"The server's identity card changed since last time. Usually
   that's the host doing maintenance, but it can also mean someone is intercepting the connection.
   Can you check with the host — their status page, recent emails, or support — that they changed
   the SSH key for this site?"*
3. If the host publishes the new key's fingerprint, compare it with the fingerprint in the
   `wpsite` error message.
4. **Only after the operator confirms**, re-trust:
   ```bash
   wpsite trust-host acme
   ```
5. If the host did not rotate it, or can't say, do not connect. Treat the credentials as possibly
   exposed: ask the operator to rotate the SSH/SFTP password with the host, then re-key.

## Hosts without SSH

Some plans offer only SFTP or FTPS, or no file access at all. WP-CLI needs a shell on the server,
so without SSH:

- **Does not work:** `wpsite wp`, `wpsite sh`, `wpsite backup` (the database dump runs on the
  server), and therefore anything behind the backup gate. Whether `wpsite deploy`/`pull` work
  over SFTP alone is UNVERIFIED — `wpsite check` will say what it could do; don't assume.
- **What the operator can still do:** the host panel's own backups and one-click staging, the
  host's file manager, and wp-admin.
- **The REST API** works from outside with an Application Password (the normal password is
  refused). The studio's `hardening.php` turns Application Passwords off by default; to use the
  REST API, set `WPSTUDIO_DISABLE_APP_PASSWORDS` to `false` in that file (see
  `wp-studio:updates-and-hardening`). Without SSH the operator places that change with the host's
  file manager, then creates the password under Users → profile → Application Passwords. It
  covers content, not files, and rich markup still depends on the user having `unfiltered_html`.
- **Recommend asking the host to enable SSH.** Plain version: *"This hosting plan doesn't allow
  the secure command-line access I use to back up and change the site safely. Most hosts can
  switch it on, sometimes on a higher plan. Can you ask them?"*
- **FTPS stalls on some hosts** whose data channel requires TLS session reuse; clients that don't
  reuse the session stall mid-transfer. UNVERIFIED on our own sites (from earlier notes); prefer
  SFTP whenever the plan offers it.

## Files in `/tmp` may not be shared between connections

On at least one managed host each SSH session gets a private `/tmp`: a file written there in one
connection is "No such file or directory" in the next. Keep server-side scratch files in a
directory under the account's home or the site, and fetch results with `wpsite pull` in the same
flow. Prefer `wpsite backup` for database dumps; it already handles this.

## CLI PHP is not the web PHP

On several managed hosts the `php` WP-CLI uses is **not** the PHP version serving the site. The
server has several PHP-FPM versions installed, and the site runs whichever the host dashboard
selects. On one site the CLI was PHP 8.4 while the web ran 8.3. `wpsite check` and `wp cli info`
report the **CLI** version.

This matters when:

- **Checking a PHP security patch.** Verify the web PHP, not the CLI one. List the installed FPM
  builds and their dates, and confirm the running FPM master processes started *after* the
  patched build — otherwise old workers are still serving:
  ```bash
  wpsite sh acme 'for b in /usr/sbin/php-fpm*; do echo "$b"; "$b" -v | head -1; done'
  wpsite sh acme 'ps -eo lstart,args | grep "[p]hp-fpm: master"'
  ```
  (Paths are from managed hosts we have used; on another host, find the FPM binaries first.)
- **Code behaves differently from CLI and web.** A script that works through `wp eval-file` can
  still fatal on the web version, and the reverse; run PHP files with `--use-include`
  (see `wp-studio:safe-changes` §5).
- **Settings like memory limits.** Some hosts set PHP limits only in their dashboard; a
  `.user.ini` or `ini_set()` change is ignored. Ask the operator to change it there.

The authoritative web version is the one in the host dashboard, or WordPress's own
Tools → Site Health → Info → Server, which runs under the web PHP.
