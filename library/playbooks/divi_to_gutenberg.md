# Playbook: Divi → Gutenberg Migration

**Date**: 2026-06-15
**Status**: Active
**Scope**: How to assess and perform stripping Divi out of a WordPress site and rebuilding it on native Gutenberg blocks while preserving the existing design and content. Lead with the scoping assessment.

The goal: get a site **off Divi** and onto **native WordPress blocks** (Gutenberg), keeping
the design and content already built — so the site is faster, more durable, and far
easier to maintain (no more [Divi fragility](../lessons/divi_pitfalls.md)).

**Always start with Phase 0 (Assessment).** The first question is almost always "how much
work is this?" — answer that with a real, page-by-page estimate *before* touching anything.
Then do the migration on **staging**, page by page, and remove Divi only at the very end.

---

## Phase 0 — Assessment ("how much work is this?")

Produce a scoping report for the operator. **No changes to the site in this phase.**

1. **Inventory the content.**
   ```bash
   ./wp.sh post list --post_type=page --fields=ID,post_title,post_status
   ./wp.sh post list --post_type=post --fields=ID,post_title --posts_per_page=-1 --format=count
   ```
   Note pages, posts, and any custom post types.

2. **Determine the Divi era** (decides the extraction method):
   ```bash
   ./wp.sh post get <ID> --field=content | head -c 400
   ```
   - `[et_pb_section]...` → **Divi 4 (shortcodes)**.
   - `<!-- wp:divi/* -->` → **Divi 5 (block JSON with `$variable()$` tokens)**.

3. **Find the global/templated pieces** built in the **Divi Theme Builder** (header, footer,
   blog templates, etc.) — these must be rebuilt as block template parts, not just page
   bodies. Check the Theme Builder and `tb-*` templates.

4. **Catalog the Divi modules in use** across the site. For each page, what module types
   appear? Most map cleanly to core blocks; a few don't (see the mapping table). The count of
   "hard" modules is the main driver of effort.

5. **Flag the hard cases** (these turn a 1-hour page into a 1-day page):
   - **Sliders / carousels** — no core equivalent.
   - **Animations / scroll effects / parallax** — partial core support (some via block
     supports), often a redesign decision.
   - **Tabs / toggles / accordions** — core has a `Details` block (accordion-ish); tabs need
     a lightweight block plugin or a rethink.
   - **Forms** — Divi's built-in contact form → move to a real forms plugin (e.g. Gravity
     Forms) or a core/block form.
   - **Dynamic content / ACF / shortcodes / theme-builder loops.**
   - **Specialty modules** (pricing tables, countdowns, maps, galleries with lightbox).

6. **Capture a visual baseline.** Screenshot every page (desktop + mobile) in a real browser.
   This is the regression reference for the whole project.

7. **Write the scoping report** in the client doc: a table of every page with a
   difficulty rating (Easy / Medium / Hard) and the reason, the list of global templates, the
   hard-case decisions the operator needs to make, a recommended target theme, and a rough
   effort/timeline estimate. **Present this to the operator and get a go/no-go before Phase 1.**

> Honest framing for the operator: text, headings, images, buttons, columns, and galleries convert
> cleanly and quickly. The time goes into (a) global header/footer rebuild, (b) any
> slider/animation/tabs/forms, and (c) careful visual matching. The report tells them exactly
> where the hours are so the decision is informed.

---

## Phase 1 — Choose the target & set up design tokens

- **Target:** a clean **block theme** (Full Site Editing) is the modern default — it gives a
  visual editor for header/footer/templates and a `theme.json` for design tokens. A
  well-built block theme + core blocks covers the vast majority of Divi designs. (A classic
  theme + blocks is an alternative if the project needs it.)
- **Translate the design into `theme.json`:** the color palette, fonts/typography scale, and
  spacing — pulled from the existing Divi design (Divi 5's `$variable()$` tokens map to global
  colors/fonts; Divi 4's are in the theme options). Tokens keep the rebuilt site consistent
  and editable.
- **Plan the module→block mapping** (next section).

## Phase 2 — Convert content, page by page (on staging)

Work on a **staging copy**. For each page, lowest-risk first:

1. Back up the page's current content to `backups/`.
2. Extract the real content from the Divi markup — text, headings, images, links, structure
   (Divi 4: parse shortcodes; Divi 5: parse the block JSON).
3. Rebuild as **clean core blocks** using the mapping below. Keep paragraphs granular, fix
   empty `alt` text, rewrite internal links, and [optimize images](../lessons/image_optimization.md).
4. Save the new block content (`./wp.sh post update <ID> - --user=<admin> --skip-plugins
   --skip-themes < new.html`).
5. **Visually diff** against the Phase-0 screenshot, desktop + mobile. Adjust until it
   matches.

### Divi module → core block mapping

| Divi module | Native block |
|-------------|--------------|
| Section / Row / Column | Group / Columns (+ row block patterns) |
| Text | Paragraph + Heading (split run-together text into discrete blocks) |
| Image | Image (wired to a Media Library attachment for responsive `srcset`) |
| Button | Buttons |
| Blurb (icon + heading + text) | Group containing Image/Icon + Heading + Paragraph |
| Gallery | Gallery |
| Video | Video / Embed |
| Toggle / Accordion | Details block |
| Tabs | Block-library plugin or rethink (no core tabs) |
| Slider / Carousel | No core block — decide: static stack, a slider block plugin, or redesign |
| Call To Action | Group (Cover/columns) + Heading + Paragraph + Buttons |
| Pricing Tables | Columns of Groups |
| Contact Form | Gravity Forms (or a block form) — see the forms note below |
| Blog / dynamic loops | Query Loop block |
| Code | Custom HTML (or a small block) |

## Phase 3 — Rebuild the global templates

Recreate the Divi **Theme Builder** header, footer, and any templated areas as **block
template parts** in the block theme. This is usually the biggest single chunk of effort —
budget for it. Match the nav, logo, and responsive behavior to the baseline screenshots.

Custom CSS that genuinely remains goes in the block theme's stylesheet or an
[mu-plugin](../lessons/custom_css_belongs_in_mu_plugin.md), scoped — never the Customizer.

## Phase 4 — Forms, plugins, and dynamic bits

- **Forms:** rebuild Divi contact forms in a real forms plugin (Gravity Forms is the proven
  choice) — match the original fields, labels, and notifications exactly (read the live form
  first). Test end-to-end on staging with email sending safely intercepted.
- **Other Divi-ecosystem plugins:** identify what depended on Divi and replace or drop it.
- **Dynamic/ACF content:** re-wire to blocks / block bindings as needed.

## Phase 5 — Verify, cut over, and remove Divi

1. **Full visual + functional QA on staging** against the baseline — every page, desktop and
   mobile, every form, every link.
2. Get the operator's sign-off.
3. **Promote staging → production** (or apply the changes to production during a low-traffic
   window, with a fresh DB backup first).
4. **Switch the active theme** to the block theme. Only now **deactivate and remove the Divi
   plugin/theme** and its dependent plugins.
5. **Scrub Divi remnants:** with Divi gone, any leftover `[et_pb_*]` shortcode in old content
   will render as raw text — search the database and clean it up. Remove the orphaned
   `et-cache`.
6. **Purge all caches**, re-verify in a browser, and confirm URLs/redirects are intact (URLs
   shouldn't change; add redirects if any slug did).

## Phase 6 — Record it

Update the client doc's work log, capture any new gotchas as lessons, rebuild the catalog,
and log a line in `../WORKLOG.md`. Note in the client's project `CLAUDE.md` that the site is
now Gutenberg/block-theme based and Divi has been removed.

---

## Risks & honest caveats (tell the operator up front)

- **Pixel-perfect parity takes time.** Blocks will get very close, but matching some Divi
  layouts exactly (spacing, fancy effects) is the slow part. The Phase-0 report should set
  expectations.
- **Sliders, advanced animations, and tabs have no 1:1 core equivalent** — each is a small
  design decision (replace, simplify, or add a focused block plugin).
- **Forms must be rebuilt and re-tested**, not just visually copied.
- **Do it on staging.** Never convert directly on the live site.
