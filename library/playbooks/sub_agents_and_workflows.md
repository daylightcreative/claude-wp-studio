# Playbook: Sub-Agents, Model Routing & Dynamic Workflows

**Date**: 2026-06-15
**Status**: Active
**Scope**: How to use sub-agents, route work across models, run work in the background (so the operator is never blocked), and fan out dynamic workflows for big WordPress jobs.

You (the main session) are the operator's primary partner. You don't have to do everything in
one thread — **dispatch sub-agents** to search, convert, verify, and watch in parallel, and run
slow things in the **background** so the operator keeps working. This playbook is how to do that
well.

## Model routing — route by *verification cost*, not perceived difficulty

The rule: **delegate work down only when you can verify its output mechanically** (run a
command, diff the result, grep, eyeball a screenshot) or by spot-checking cited findings. If
checking the output would mean re-doing the thinking, keep it in the main loop.

| Work shape | Route to | Model | How you verify it |
|------------|----------|-------|-------------------|
| Broad read-only sweep: enumerate pages/plugins, find all images, classify Divi modules across a site | `Explore` / a read-only sub-agent | **Haiku** | Spot-check the cited `file`/page IDs |
| Well-specified build/convert chunk: "convert THIS page's Divi markup to blocks per this mapping," with the spec fully given | a sub-agent | **Sonnet** | Diff the output; screenshot-compare to the baseline |
| Independent QA pass with explicit criteria (links work, alt text present, matches screenshot) | a sub-agent | **Sonnet** | Re-run the checks on a sample |
| Anything with real judgment: design decisions with the operator, ambiguous requirements, multi-page structure, "is this worth doing" | **stay in the main loop** | **Opus** (the session model) | — |
| A genuinely hard, stuck problem (see escalation) | escalation tier | **Fable** (if available on the plan) | Verify the diagnosis against the real site before acting |

**Hard exclusions (no exceptions):**
- A cheap model (Haiku) **never** writes code/markup that ships unverified — its failure mode
  is silently dropping requirements. Use it to *find and report*, not to *build*.
- **Verification never goes to the same tier that produced the work** — a sub-agent doesn't
  grade its own homework; you (or a fresh agent) check it.
- **Fewer than ~3 independent pieces of work → just do it in the main loop.** Don't stand up
  orchestration ceremony for two pages.

## When to escalate (the hard, stuck problems)

The escalation tier is **Fable** (`claude-fable-5`), for genuinely hard problems: a root cause
you can't name in one sentence after real investigation, two failed fix attempts, contradictory
evidence, a tricky async/race/heisenbug, or an architecture call spanning several systems.

- Escalate to Fable only if it's available on the current plan; verify its diagnosis against the
  real site before acting on it.
- If Fable isn't available, stay in the Opus main loop and slow down — investigate harder, read
  the relevant lessons, reproduce the problem.
- If you're still stuck after a genuine effort, **surface it plainly to the operator**: what you
  tried, what you observed, and the specific decision or information you need from them. Don't
  loop silently.

## Self-contained sub-agent prompts (the #1 rule for good results)

A sub-agent **cannot see your conversation with the operator** — it sees only its prompt, the
project, and `CLAUDE.md`. So every spawn prompt must carry everything it needs:

- The **exact files / page IDs** to work on.
- A **canonical example** to copy (e.g. "match the block structure of page 14, already
  converted").
- The **standards/lessons** that govern it, *by path* (e.g.
  `library/playbooks/divi_to_gutenberg.md`, `library/lessons/image_optimization.md`).
- The **acceptance checks** it must run/satisfy before returning.
- The **exact shape of what to return** (e.g. "return the new block markup only," or "return
  a JSON list of `{page_id, difficulty, reason}`").

If you can't write a self-contained prompt for it, it's not ready to delegate — keep it.

## Running work in the background (keep the operator unblocked)

The operator must never sit waiting on a slow task. Run slow/independent things in the
background and keep the conversation live:

- **Background sub-agents** (`run_in_background`) — dispatch, keep talking to the operator, and
  fold in the result when it's ready.
- **Parallel sub-agents** — when several independent pieces can run at once (e.g. scouting a
  site while optimizing images), launch them together.
- Tell the operator, in plain terms, what's running in the background ("I've got a helper
  inventorying the whole site while we talk about the homepage").

## Dynamic workflows (fan-out for the big jobs)

For large, repetitive fan-outs — e.g. converting **every** page of a site from Divi to
blocks, or scoping a whole site page-by-page — a dynamic workflow orchestrates many
sub-agents deterministically (parallel where independent, pipelined where dependent).

Rules of thumb:
- **Workflow sub-agents are Sonnet.** Set the model explicitly on each; don't pin other tiers
  inside a workflow.
- **Pull judgment out.** Any stage needing real judgment (adjudicating a tricky layout, a
  design call) comes back to the main loop or a direct Opus sub-agent — not the workflow.
- **Serial barrier on shared artifacts.** If many page-conversions all depend on one shared
  thing (the site's `theme.json` design tokens), author that **once, serially**, *before* the
  parallel fan-out reads it. Parallel writers to a shared file = broken builds.
- **Coverage by construction.** Fan out per-page (one sub-agent per page), so no page is
  missed; collect a status per page.
- **Block, don't improvise.** If a sub-agent can't finish a page (a slider with no clean
  equivalent), it returns "blocked + why" — it never invents to look complete. You surface
  the gap to the operator.

Workflows are heavier machinery — reach for them when there are many similar items. For a
handful, a few direct sub-agents are simpler. Scale to the actual job.

## WordPress examples

- **Scout a new site:** one read-only sub-agent enumerates pages/posts/plugins/theme and the
  Divi era, returns a table. (Haiku/Explore.)
- **Divi→Gutenberg, many pages:** a pipeline — per page: extract content → convert to blocks
  → screenshot-diff — with Sonnet sub-agents, after you've authored the shared `theme.json`
  tokens once. (See [Divi → Gutenberg](divi_to_gutenberg.md).)
- **Pre-launch QA:** parallel sub-agents each check one dimension (links, images/alt,
  mobile rendering, forms) against the staging site and report findings.
