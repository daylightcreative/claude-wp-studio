---
name: big-jobs
description: Plan and delegate large WordPress jobs — whole-site inventories, converting many pages (for example off a page builder onto core blocks), site-wide QA — across subagents without losing quality or blocking the operator. Use when a job covers more than a few pages or independent pieces, when the operator asks "how long will this take across the whole site?", or before launching the site-scout, page-converter or qa-checker agents.
---

# Big jobs: delegation without losing quality

**Delegate work only when you can check its output cheaply.** Route by *verification cost*, not
by how hard the work looks. If you can check the result by running a command, diffing it, or
spot-checking cited page IDs, a subagent can do it. If checking it would mean redoing the
thinking, keep it in the main conversation. Judgment — design calls, ambiguous requirements,
"is this worth doing", anything the operator must decide — always stays with you.

**Fewer than about three independent pieces of work: just do them yourself.** Orchestration
costs more than it saves on a small job.

## Routing

| Work | Who | Model | How you check it |
|---|---|---|---|
| Read-only inventory: pages, post types, plugins, builder modules in use, images | `site-scout` agent | haiku | Spot-check a few cited IDs with `wpsite wp` |
| One well-specified conversion: "turn page 14 into core blocks using this mapping" | `page-converter` agent | sonnet | Read the markup; render it on staging; compare to the baseline screenshot |
| One QA dimension with explicit criteria (links, alt text, overflow…) | `qa-checker` agent | sonnet | Re-run a sample of its failures yourself |
| Design decisions, multi-page structure, what to tell the operator, anything ambiguous | you | the session's model | — |

Two exclusions with no exceptions:

- **haiku finds and reports; it never writes markup or code that ships.** Its failure mode is
  quietly dropping requirements.
- **Nothing grades its own work.** The agent that produced a conversion doesn't verify it; you, or
  a fresh `qa-checker`, do.

Use model aliases (`haiku`, `sonnet`, `opus`), never dated model IDs; aliases keep working as
models change. A hard, stuck problem stays in the main conversation: investigate, reproduce, and
if two fixes built on the same assumption have failed, test that assumption directly before a
third. If you are still stuck, tell the operator plainly what you tried, what you saw, and the
specific decision or information you need.

## Write prompts that stand on their own

A subagent can't see your conversation with the operator. It sees its prompt, the files, and the
project's `CLAUDE.md`. Every prompt carries:

1. **The site and environment**, as a `wpsite` site name (`acme:staging`), and the project folder
   (`projects/acme/`).
2. **The exact items**: page IDs, URLs, or the file in `work/` that lists them.
3. **A canonical example to copy**: "match the block structure of page 14, already converted, in
   `work/convert/14.html`".
4. **The rules that govern it, by path**: the relevant skill section copied in, or the file to
   read.
5. **The acceptance checks** it must pass before returning.
6. **The return format** — each agent file defines one; restate it if you need a variant.

If you can't write that prompt, the work isn't ready to delegate. Keep it.

## Keep the operator unblocked

The operator should never sit waiting on a slow task. Run independent work as **background**
subagents, keep talking, and fold the results in when they arrive. Launch independent agents
together so they run in parallel. Say what's running, in plain words: "I've got a helper
inventorying every page while we talk about the homepage."

## Fan out per item

**One agent per page (or per QA dimension), so coverage is guaranteed by construction.** Give
each a status to return — `done`, `blocked`, or `failed` — and keep a list in
`projects/<slug>/work/` of every item and its status. When the fan-out finishes, the list must
have one row per item; a missing row is a missing page.

## Serial barrier on anything shared

**Write shared files once, yourself, before the fan-out reads them.** A page conversion depends on
the site's design tokens (`theme.json`: palette, fonts, spacing) and the module-to-block mapping.
Settle those first, one writer, and have the operator approve them. Then the parallel agents
only *read* them. Parallel writers to one shared file corrupt it.

The same applies to deploying: agents write into `work/`; only you deploy, one change at a time,
with a backup (`wpsite backup`) and a purge.

## Block, don't improvise

**An agent that can't finish an item returns `blocked` with the reason. It never invents something
to look complete.** A slider with no clean core equivalent, a module it doesn't recognise, a
missing image: each is a decision for you and the operator. Collect the blocked items and bring
them to the operator as choices, with your recommendation.

## The Workflow tool

Claude Code's Workflow tool (scripted multi-agent workflows) runs **only when the operator
explicitly asks for it**. Never start one on your own. For everything else, direct subagents are
enough: launch them in parallel, in the background, as above.

## Worked shapes

- **Scope a site** ("how much work is it to move off the builder?"): one `site-scout` returns the
  inventory; you rate each page Easy / Medium / Hard with the reason, list the shared templates
  (header, footer) and the hard cases, and bring the operator one report with a go/no-go.
- **Convert many pages** (the full playbook is the `divi-to-blocks` skill): capture baseline screenshots of every page (desktop and mobile); settle
  `theme.json` and the mapping serially; fan out one `page-converter` per page into
  `work/convert/<ID>.html`; review each result and deploy to staging one at a time; QA with
  `qa-checker`; bring blocked pages to the operator.
- **Pre-launch QA**: one `qa-checker` per dimension, in parallel; see the `launch-qa` skill.
