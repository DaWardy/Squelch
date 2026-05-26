# Squelch — Consumer Feedback Pipeline

This document defines how product requirements flow from **consumer personas**
(the customers) to the **DevSecOps team** (who build and secure). It is the
demand side of the project; `DESIGN_REVIEW.md` is the supply side (the rules the
team builds against).

```
  CONSUMERS (customers)                 DEVSECOPS TEAM (builders)
  ─────────────────────                 ─────────────────────────
  Hank   — seasoned ham (72)            Programmer   — implements, tests
  Marcus — younger seasoned ham (34)    Security Eng — threat model, S1–S9
  Elena  — RF instructor (50)           Pentester    — breaks it, reports
  Sam    — RF student (19)
  Dorothy— new ham, older (66)   ──────►  files requirements & comments
  Tyler  — new ham, younger (15)         which the team triages & builds
```

A requirement is **DONE** only when the requesting consumer would sign off AND
the DevSecOps team confirms it meets the standing rules (R1–R6, S1–S9).

The Security Engineer and Pentester are **dual-role**: they sit on the
DevSecOps team (defining and enforcing S1–S9) and also act as consumers —
Priya uses Squelch for paid RF/security work, so her requirements feed the
backlog like any other customer's. Security review is therefore never
optional or after-the-fact; it is represented on both sides of the pipeline.

---

## The Consumer Panel

### Hank — Seasoned Ham, 72 (Extra, 50 yrs licensed, CW/DX/contesting)
Runs an IC-7100 + IC-7300, big wire antennas, chases DX and works contests.
Used HRD, N1MM, WSJT-X for decades. **Buys software that respects the operator
and matches rig muscle-memory.** Will abandon anything that wastes clicks in a
pileup or transmits unexpectedly.
- Wants: instant frequency/mode/split readout, fast logging with macros,
  band-edge guard, rigctld latency under 100ms, ADIF/Cabrillo that import
  cleanly into LoTW/contest software.
- Won't tolerate: hidden state, software "correcting" him, modal popups mid-QSO.

### Marcus — Younger Seasoned Ham, 34 (General, 12 yrs, digital/SOTA/POTA)
Portable ops, FT8/JS8, POTA activations from a truck. Comfortable with software,
expects modern UX. **Buys software that's fast to set up in the field and syncs
his log.**
- Wants: quick portable setup, POTA/SOTA spotting, GPS/grid auto-fill, gx
  cloud-free local logging, dark mode that survives sunlight, keyboard shortcuts.
- Won't tolerate: slow startup, fiddly config, anything cloud-mandatory.

### Elena — RF Instructor, 50 (teaches Tech/General/Extra license classes)
Runs a club's license courses and a station for demos. **Buys software she can
teach with** — correct terminology, visible units, explains the *why*.
- Wants: tooltips that teach, band-plan accuracy, propagation explained honestly,
  a "guest/demo" mode for class, nothing that could accidentally transmit during
  a lecture.
- Won't tolerate: sloppy terminology, hidden math, implying capabilities the
  hardware lacks.

### Sam — RF Student, 19 (engineering undergrad, studying for General)
Learning the theory, owns an RTL-SDR and a borrowed HT. **"Buys" (adopts) tools
that help him connect theory to practice.** Will dig into internals.
- Wants: SDR waterfall with real controls, signal identification help, a way to
  see modulation, exportable data for lab reports, an honest manual.
- Won't tolerate: black boxes, fake/simulated data presented as real, dead ends.

### Dorothy — New Ham, older, 66 (just passed Tech, first HT + first HF rig)
Retired, joined a club, nervous about "breaking something." **Buys software that
doesn't make her feel stupid and tells her what to do next.**
- Wants: a first-run wizard, plain-language labels, big readable text, a clear
  "you must set this up first" message, an undo for mistakes, large fonts.
- Won't tolerate: jargon with no explanation, blank screens, silent failures.

### Priya — Pentester / Security Engineer, 38 (also a real user, work use)
Sits on the DevSecOps side AND uses Squelch at work: she runs RF/SDR
assessments, spectrum surveys, and signal investigations for a security
consultancy. So she is both a builder (breaks the software) and a customer
(depends on it for paid engagements). **Buys software she can trust on a
client network and stake findings on.**
- Wants (as a user): SDR capture/export she can put in a report, no telemetry
  or surprise outbound connections on a client's network, an audit trail of
  what the app did, reproducible captures (SigMF), offline operation, and a
  clear record that the tool never transmitted unless she told it to.
- Wants (as a builder): the S1–S9 rules enforced, threat model kept current,
  every release pen-tested against malicious inputs and rogue servers.
- Won't tolerate: any unsolicited network beacon on a client site, unbounded
  parsing of untrusted server data, plugins that autoload, or TX she didn't
  initiate.

### Tyler — New Ham, younger, 15 (Tech, school radio club, phone-native)
Got licensed through a school club. Phone/tablet-native, low patience for
manuals. **Drawn to the digital modes** — FT8, FT4, JS8 — because they work
with cheap hardware, show instant decodes, and feel like messaging. This is
his main on-air activity. **Adopts tools that are discoverable and fun.**
- Wants: FT8/FT4/JS8 that are easy to start, a clear "you are/aren't
  transmitting" indicator (he knows FT8 auto-transmits and that scares him a
  little), decodes that scroll live, a map that looks alive, obvious happy path.
- Won't tolerate: unlabeled buttons, no onboarding, not knowing whether he's
  on the air, anything that feels like 1998.

---

## How Feedback Flows

1. **Consumers file entries** in the Requirements Backlog below. Each entry
   names the persona, a plain-language need, and an acceptance test.
2. **DevSecOps triages**: assigns a priority, maps to the standing rules
   (R1–R6 usability, S1–S9 security), and notes effort.
3. **Build & verify**: programmer implements, security reviews, pentester
   tries to break it. The requesting persona's acceptance test must pass.
4. **Sign-off**: entry moves to "Shipped" with the version and the reviewers
   who confirmed it.

Priority key: **P0** blocker · **P1** important · **P2** nice-to-have

---

## Requirements Backlog (open)

| ID | Persona | Need (consumer voice) | Acceptance test | Maps to | Pri |
|----|---------|----------------------|-----------------|---------|-----|
| C-01 | Sam | "The SDR tab is empty — I can't see a waterfall or tune anything." | With an RTL-SDR connected, SDR tab shows a live waterfall + gain/freq/sample-rate controls | R5, S7 | P0 |
| C-03 | Hank | "I need to see split and which VFO is transmitting at a glance." | Rig tab shows VFO A/B, split state, and TX VFO unambiguously | R1, R3 | P1 |
| C-04 | Marcus | "Local RF never returns repeaters and I can't change where it searches from." | Configurable 'From' field added (grid/ZIP/city); RepeaterBook call rewritten to correct API + local distance filter. **Blocked externally**: RepeaterBook now requires an approved API token (policy change 2026-03). UI guides the user to apply + paste token in Settings. | R2, R4 | P1 (partial 0.11.8) |
| C-05 | Tyler | "The map is kind of dead — just outlines." | Map shows my station, day/night terminator, and live spots with motion | R5 | P2 |
| C-07 | Dorothy | "The text is small and I couldn't make it bigger." | Font-size setting visibly scales the whole UI | R5 | P1 (shipped 0.11.2) |
| C-13 | Priya | "Captures need to be reproducible for a report (SigMF metadata)." | SDR captures export with SigMF metadata (freq, rate, time, hw) | R6, S3 | P2 |
| C-14 | Elena | "In class I arm Auto-CQ to explain it, but it must not transmit in Guest mode." | Arming auto-sequence/auto-CQ in Guest mode is allowed for teaching but never keys the rig | R1, S9 | P1 (shipped 0.11.6) |
| C-10 | Sam | "Let me export what I see for my lab report." | Waterfall/spectrum and decoded data are exportable (PNG/CSV) | R6, S6 | P2 |

---

## Shipped (with reviewer sign-off)

| ID | Persona | Delivered | Version | Confirmed by |
|----|---------|-----------|---------|--------------|
| C-07 | Dorothy | Font size scales whole UI (stripped 260 inline overrides) | 0.11.2 | Programmer, Dorothy |
| — | Elena/Dorothy | FT8 control tooltips explain function + warn on TX | 0.11.3 | Instructor, New Ham |
| — | All | Text everywhere is selectable/copyable | 0.11.1 | All |
| — | Sam/Tyler | SDR tab no longer blank when SoapySDR absent (shows guide) | 0.11.3 | Student, New Ham |
| — | All | Light/Night/System themes readable (stripped 171 inline colors) | 0.11.2 | All |
| C-06 | Elena | Demo Mode disables all TX + shows banner; applies without restart (renamed from "guest" in 0.11.10 — that was a misnomer) | 0.11.5 | Security, Pentester, Elena |
| C-08 | Hank | All TX paths (_send_cq, fldigi) gated through safety.can_transmit() | 0.11.5 | Security, Programmer, Hank |
| C-11 | Tyler | Big ON-AIR/RECEIVING indicator on FT8 reflecting real TX state | 0.11.6 | Instructor, Tyler |
| C-14 | Elena | Auto-CQ/seq can be armed in Guest mode for teaching but never keys rig | 0.11.6 | Security, Pentester, Elena |
| C-12 | Priya | Network Activity log records every outbound connection (AUTO vs USER), viewable in Help menu; credentials redacted | 0.11.7 | Security, Pentester, Priya |
| C-02 | Dorothy | First-run wizard now includes a radio-selection step (callsign->grid->rig) | 0.11.9 | New Ham, Dorothy |
| C-15 | Sam/Elena | Guest Operator mode for students/visitors: enters guest callsign (used for FT8 ID), TX stays enabled, generates a read-aloud voice contact script | 0.11.10 | Instructor, Student, Programmer |
| C-09 | Marcus | App restores last-used tab + window geometry on launch | 0.11.9 | Programmer, Marcus |

---

## External Dependencies & Blockers

Some consumer requirements depend on third-party services whose policies we
do not control. Tracked honestly here so they are not mistaken for bugs:

- **RepeaterBook API (affects C-04, Local RF).** As of **March 2026**,
  RepeaterBook restricted API access to *approved clients with a token*
  (`X-RB-App-Token`), and there is no public proximity endpoint. Squelch now
  uses the correct `export.php?country=&state_id=` query with local distance
  filtering, but the user must apply for their own token
  (repeaterbook.com/api/token_request.php — free for non-commercial use) and
  paste it into Settings -> Credentials. RepeaterBook also states that a
  standalone "nearby repeater finder" is unlikely to be approved as a public
  product; personal/field-use is the supported case. Squelch is personal-use
  software, which fits the approvable category, but each operator obtains
  their own token.

---

## QA / QC Gate (DevSecOps)

Ops raised that broken builds were reaching the customer (repeated NameError
crashes: `_hold_tx_cb`, `_sep`, `_vsep`). There is now a mandatory pre-package
gate — **`python qa_check.py`** — that must pass before any release zip is
built. It runs:

1. **Syntax** — every `.py` file must `compile()` (stricter than ast.parse;
   catches e.g. `__future__` import-ordering mistakes).
2. **Undefined names** — `pyflakes` over ui/core/modes/network. This catches
   the exact recurring bug class: a missing import or a dropped `self.`
   (every one of the shipped crashes would have been caught here).
3. **Test suite** — full pytest run.
4. **Tab smoke test** — `tests/test_tab_smoke.py` builds the MainWindow and
   every tab under an offscreen Qt platform; fails naming the exact tab if
   any raises. Runs on the dev box and in CI (skips only where PyQt6 is
   absent).

CI also runs the pyflakes step. The rule: **no zip is packaged unless
`qa_check.py` exits 0.**
