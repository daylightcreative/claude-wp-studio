# START HERE — Activate the Studio

**You are Claude Code, starting in Claude WP Studio — a working root for building and
maintaining WordPress sites.** This is the first session. Your job now is to **activate the
studio** so every future session begins fully equipped.

Most of the studio ships ready-made: the operating manual (`CLAUDE.md`), the guides (in
`guides/`), the knowledge base (`library/`), and the tooling (`tooling/`). Everything lives
under this one folder, so all paths point downward. Activation is mostly **verifying,
indexing, and confirming** — not building from scratch.

## Is this like `/init`?

Partly. The familiar `/init` command inspects a codebase and *writes a `CLAUDE.md`* for it.
Here:

- The studio's `CLAUDE.md` is **already written** (it encodes rules and philosophy that can't
  be auto-discovered), so you don't generate it — you follow it.
- This activation does **more** than `/init`: it also builds the search catalog and confirms
  the tooling.
- The real `/init` analog comes **later, per client**: when you start an actual site, you'll
  inspect that live site and write a **project-specific `CLAUDE.md`** for it (stack, access,
  gotchas, workflow). That step is in `library/playbooks/client_project_setup.md`.

## What you'll have when activation is done

1. A working knowledge base in `library/` with a built **SQLite catalog** you can search,
   pre-seeded with WordPress lessons and playbooks.
2. Confirmed tooling in `tooling/` (the catalog, the helper templates, save/maintain scripts).
3. A `projects/` area ready for the first client site.
4. A clear, plain-language wrap-up for the operator.

## How to proceed

Follow **`guides/01_bootstrap.md`** top to bottom. It will send you into:

- `guides/02_environment_and_tools.md` — verify the tools and **install anything missing
  yourself** (you have bypass permissions).
- `guides/03_studio_system.md` — how the library, tooling, projects, the catalog, and the
  document conventions fit together.
- `guides/04_git_and_backup.md` — confirm the automatic local + (optional) GitHub backup.

## Working style for this session

- **Talk to the operator in plain language.** Narrate lightly — what you're doing and why —
  without walls of terminal output. Assume they may not be a programmer.
- **Move efficiently and set things up yourself.** You run with bypass permissions — install
  any tools you need (Homebrew packages, Python libraries, CLIs) without making the operator
  do it. Don't stall for permission on routine setup. Still confirm before anything with
  real-world consequences (touching a live site, spending money, deleting).
- **Be faithful to what ships.** The scripts and docs here are proven. Use them as given;
  adapt only where a guide says to.
- **End clearly.** When you're done, tell the operator the studio is ready, show them the one
  or two things they'll actually use day-to-day, and recommend the next step (set up their
  first WordPress site — see `library/playbooks/client_project_setup.md`).

Begin with `guides/01_bootstrap.md`.
