# SSH / SFTP Access Gotchas

**Date**: 2026-06-15
**Status**: Active
**Scope**: The connection-level snags that waste time when working on remote WordPress hosts, and the one-line fixes.

These are the small, maddening access issues that look like "the credentials are wrong"
but aren't. Recognize them and move on fast.

## Host-key rotation: "REMOTE HOST IDENTIFICATION HAS CHANGED"

Hosts (Kinsta has done this) occasionally rotate the server's SSH host key — same IP and
port, new key. SSH then refuses to connect with a scary warning. It's not a hack; just
clear the old key and re-trust:

```bash
ssh-keygen -R "[HOST]:PORT"
ssh -p PORT -o StrictHostKeyChecking=accept-new USER@HOST true
```

Then your normal `wp.sh` works again.

## SFTP batch mode kills password auth

`sftp -b <batchfile>` forces `BatchMode=yes`, which **disables password authentication**. If
you're authenticating with a password (e.g. via `sshpass`), batch SFTP fails with
*"Permission denied (publickey,password)"* even though the password is correct. Override it:

```bash
sftp -o BatchMode=no ...
```

Plain `ssh` (which `wp.sh` uses for WP-CLI) is unaffected — this only bites scripted SFTP.

## FTPS upload weirdness (some hosts, e.g. Hostinger)

Some hosts' FTPS endpoints require **TLS session reuse** for the data channel; uploaders
that don't reuse the session stall or fail mid-transfer. If SFTP/scp over SSH is available,
prefer it. If you must use FTPS, use a client that supports TLS session resumption.

## Custom SSH ports

Managed hosts rarely use port 22. **Kinsta uses a custom high port** — find it in MyKinsta
(or the host panel) and put it in the project's `.secrets/connection.env` (`SSH_PORT`).

## Quoting secrets in the env file

If any value in `.secrets/connection.env` contains shell metacharacters (passwords with
`$`, `!`, spaces, quotes), keep it **single-quoted** — otherwise `source`-ing the file
breaks or mangles the value.

## WP-CLI runs without a WordPress login

A useful fact: WP-CLI over SSH talks to the database directly, so it works **without** any
wp-admin login. SSH access alone is enough to inspect and edit everything. That's why it's
the fastest, most authoritative tool — reach for it before the dashboard.
