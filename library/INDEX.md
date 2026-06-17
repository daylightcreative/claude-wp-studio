# Library — Master Index

> Categorized links to every active document. See `CONTRIBUTING.md` for how to add docs.
> Search instead of scroll: `python3 tooling/catalog.py search "<topic>"` (run from the
> studio root).

---

## Lessons

*Hard-won, reusable lessons — host quirks, gotchas, fixes. The most valuable category.*

- [wordpress_safety_and_backups.md](lessons/wordpress_safety_and_backups.md) — The non-negotiable safety habits: discover before you touch, back up before every change, work on staging not live, confirm anything irreversible, edit safely via WP-CLI, lint PHP, purge cache
- [custom_css_belongs_in_mu_plugin.md](lessons/custom_css_belongs_in_mu_plugin.md) — Why custom CSS goes in an mu-plugin (not the Customizer or Divi's box, which are unreliable/suppressed), the deploy ritual with the mandatory `php -l`, and using the same pattern to fix broken theme JS
- [caching_by_host.md](lessons/caching_by_host.md) — Caching differs by host and will fool you: the Kinsta MU-plugin-present-vs-absent split, Cloudflare's 24h edge, why `wp cache flush` isn't enough, and how to actually clear cache per host
- [ssh_sftp_and_access_gotchas.md](lessons/ssh_sftp_and_access_gotchas.md) — Connection snags and one-line fixes: host-key rotation, `sftp -b` killing password auth (`-o BatchMode=no`), FTPS TLS session reuse, custom SSH ports, quoting secrets, and WP-CLI needing no WP login
- [divi_pitfalls.md](lessons/divi_pitfalls.md) — Why we lean away from Divi (fragile front-end runtime, update breakage, suppressed custom CSS, dead-class plugin fatals) and the facts you need to work on an existing Divi site (D4 shortcodes vs D5 block JSON, premium version installs, Theme Builder)
- [image_optimization.md](lessons/image_optimization.md) — The standard ImageMagick recipe (WebP, 1600px, q82, strip, auto-orient) for ~95% size reduction, descriptive filenames, edge cases, and responsive `srcset` wiring

## Playbooks

*Reusable step-by-step methods — the "how we do things."*

- [wordpress_workflow.md](playbooks/wordpress_workflow.md) — The everyday working method: the operator/Claude division of labor, the tools in order of preference, a task start-to-finish, and design tokens via `theme.json`
- [client_project_setup.md](playbooks/client_project_setup.md) — Standing up a new client project: the folder, secrets, helper scripts, the live-site discovery pass, and generating the project-specific `CLAUDE.md` (the per-client `/init`)
- [divi_to_gutenberg.md](playbooks/divi_to_gutenberg.md) — Assessing and performing a Divi→Gutenberg migration that preserves design and content: lead with the Phase 0 scoping assessment, the module→block mapping, theme.json tokens, Theme Builder rebuild, forms, cutover, and honest caveats
- [sub_agents_and_workflows.md](playbooks/sub_agents_and_workflows.md) — Using sub-agents, model routing (route by verification cost: Opus main loop / Sonnet + Haiku delegation / Fable escalation), self-contained spawn prompts, running work in the background to stay unblocked, and dynamic-workflow fan-out for big jobs

## Clients

*One doc per client site — stack, where secrets live (not the secrets), decisions, work log.*

- [README.md](clients/README.md) — What a client doc holds (and what it must never hold). One file per client is created at project setup.

## Reference

*Durable external pointers — docs URLs, dashboard locations (not credentials).*

- [README.md](reference/README.md) — What belongs in reference (add as real needs arise)
