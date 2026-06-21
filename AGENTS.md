# AI Agent & Contributor Onboarding

Start here when beginning work on Squelch — as an AI agent (Claude Code,
Copilot, Cursor, …) or a human contributor.

## Read these first, in order

1. **`CLAUDE.md`** — the canonical engineering context: architecture, design
   decisions (the *why*), recurring bug patterns, the mandatory QA gate, and
   the current backlog/handoff. **This is the primary instruction file.**
   > `CLAUDE.md` is intentionally **gitignored and kept off the public repo**
   > (internal handover doc). On the maintainer's machine it is present in the
   > project root and is auto-loaded by Claude Code. On a **fresh clone it will
   > be absent** — request it from the maintainer. Until you have it, `ROADMAP.md`
   > + this file + `CONTRIBUTING.md` + `SECURITY.md` cover the essentials.
2. **`ROADMAP.md`** — vision, the 8-pillar capability model, phased plan,
   priorities, compliance posture, and engineering framework.
3. **`CONTRIBUTING.md`** and **`SECURITY.md`** — contribution rules and the
   security model.

## Starting a new session

Open a session **in the project root** so `CLAUDE.md` is auto-loaded, then say:

> "Read CLAUDE.md, ROADMAP.md, and the memory files, then continue."

The mandatory gate before *any* change or commit:

```bash
python qa_check.py        # must exit 0
```

## When to start a *fresh* session (efficiency)

Long sessions lose fidelity and cost more once context fills up. Start a new
session when:

- **The current sprint/workstream is done** and the next one is unrelated.
  Rule of thumb: ~one sprint or one coherent workstream per session.
- **The context was auto-summarized/compacted** (you'll see a notice). A fresh
  session restores full-fidelity context — re-point it using the line above.
- **You're pivoting topics** (e.g. from a UI feature to a security audit).
- **Replies start missing earlier detail** or slow down noticeably.
- **After a commit/push milestone**, before opening a new line of work.

Carrying an unrelated, bloated history into new work is the main cause of
slow, less-accurate sessions — a clean start re-reads `CLAUDE.md`/`ROADMAP.md`
and is usually faster and better.

## Public-language policy

Everything in this repo is public. Describe capabilities in neutral,
professional terms (amateur radio, RF analysis, RF security research, spectrum
monitoring, transmitter location / interference hunting, RF education). See
`ROADMAP.md §1`.
