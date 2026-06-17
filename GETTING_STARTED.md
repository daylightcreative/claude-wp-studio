# Getting Started with Claude WP Studio

Welcome. This studio lets you work on your WordPress sites the way a developer would — by
**talking to Claude** and letting it do the technical heavy lifting, while you stay the
director and the decision-maker. You don't need to write code or memorize commands. You
direct; Claude builds.

If you ran the one-line installer, almost everything below is already set up for you. This
guide explains how to use it day to day.

---

## Starting a work session

1. **Open the Terminal** and go to your studio folder (the installer told you where it is —
   by default `~/claude-wp-studio`).
2. **Launch the studio** by running:
   ```
   ./studio.sh
   ```
   This makes sure Claude Code is up to date, then starts it with the right settings
   (full autonomy and maximum reasoning effort).
3. **The very first time**, Claude will ask you to log in (connect your Claude subscription or
   API key) — just follow the browser prompt. Then tell it:
   ```
   Read START_HERE.md and follow it.
   ```
   Claude will set everything up itself, including installing any technical tools it needs.
   When it's done, it'll tell you, in plain English, that you're ready.

After that, working is simple: open the folder, run `./studio.sh`, and start talking.

---

## How to talk to Claude

Like a smart, fast colleague who happens to handle all the technical parts. For example:

- *"Pull up my site and tell me what it's built with."*
- *"On a safe practice copy, change the homepage headline to X and show me a picture."*
- *"How much work would it be to move this site off Divi onto regular WordPress, keeping the
  design? Walk me through it before we change anything."*
- *"This looks crowded — can we add more breathing room between these sections?"*

Claude will ask you to approve things that matter, show you choices when a decision is yours
(with a recommendation), and always tell you whether it's working on the live site or a safe
copy. If you're ever unsure: *"Is this live or a practice copy?"*

---

## Things Claude handles for you

- **Installing technical tools.** It does this automatically — you won't have to install or
  configure anything.
- **Keeping things updated and tidy.** It quietly keeps the software current and the workspace
  clean in the background.
- **Saving your work.** Claude automatically saves your work as you go (and backs it up to your
  private cloud copy if you connected one during setup). You don't have to save or manage any
  of that — it just happens.
- **The careful, risky bits.** It backs up before changes, builds on practice copies, asks
  before anything permanent, and keeps your passwords private.

---

## Where to put passwords (so you never type them in the chat)

There's a file in your studio folder called **`CREDENTIALS.txt`** — a safe little **drop box**
for website logins, passwords, and keys.

- When Claude needs a login, **paste it into `CREDENTIALS.txt`** and tell Claude it's there
  (e.g. *"I put the site login in the drop box."*).
- Claude reads it, tucks it away somewhere private and secure for that site, and then **wipes
  the file back to blank** — so it'll look empty most of the time. That's normal.
- This file stays on your computer and is **never** backed up, committed, or shared.

This way your passwords never have to go into the chat conversation. 🔒

---

## Your first project

When you're ready to work on a real site, just say so:

> *"Let's set up my WordPress site as a project. Here's the URL — walk me through what you need."*

Claude will create a dedicated project folder, ask you (via the drop box) for the site's login
details, inspect the real site with no changes, and give you an honest picture of what's there
before doing anything. From then on, every session knows that site.

---

## If you ever feel stuck

- Ask Claude: *"explain that in plain terms"* or *"what are my options?"*
- Say *"wait, stop"* or *"undo that"* any time — nothing changes a live site on its own.

That's it. Open the folder, run `./studio.sh`, and tell Claude what you'd like to do.
