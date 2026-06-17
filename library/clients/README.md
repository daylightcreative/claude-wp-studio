# clients/

One markdown doc per client site. This is the **durable, searchable record** of each
engagement — distinct from the working files in `projects/<client>/` and from that
project's operational `CLAUDE.md`.

## What a client doc holds

- **Engagement summary** — who the client is, what the site is, what work is happening.
- **Stack** — URL, WordPress version, theme, key plugins, PHP version, host.
- **Access** — *where the credentials live* (e.g. "`projects/<client>/.secrets/connection.env`").
  **Never the credentials themselves.**
- **Cache method** — the correct way to clear cache for this host.
- **Decisions** — choices made and why.
- **Work log** — dated entries of what was done.

## What it must NOT hold

No passwords, API keys, app passwords, or account numbers. Reference where they're stored.
See [CONTRIBUTING](../CONTRIBUTING.md).

## Creating one

When you set up a new client project (see
[client project setup](../playbooks/client_project_setup.md)), create the matching
`library/clients/<client>.md`, add it to `../INDEX.md`, and rebuild the catalog.
