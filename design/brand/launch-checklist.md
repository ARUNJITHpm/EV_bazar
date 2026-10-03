# Minimum Brand Kit to Launch Credibly

**Context:** Independent EV charging site assessment + CPO matching. Audience: property owners/RWAs, fleets, CPOs. Problem solved: uncertain ROI.

**Guiding principle:** This business sells *judgment*, not a product. Credibility comes from proving the site assessment is real — not from visual polish. The assessment artifact outranks everything visual.

---

## Where this stands — 2026-09-06

Only what the repo can actually evidence. Everything else on this list is a
human step, and a tick nobody can point at is worse than an open box.

| # | Item | State |
|---|---|---|
| 1 | Name, domain, email on it | **Open.** `hello@chargeworthy.in` is deliberately NOT linked anywhere until the domain exists (`design/DECISIONS.md`). |
| 2 | Wordmark only | **Shipped.** Direction C — Worthy, Newsreader, on every public surface (2026-10-03; was IBM Plex Mono caps). The `Cw` favicon is the wordmark's own initials, not a symbol — see `design/README.md`. |
| 3 | Two colours + one typeface | **Shipped.** `frontend/src/styles/tokens.css`, the only file allowed a raw hex. Copper is reserved for the unverified state and nothing else. |
| 4 | A sample site report — highest priority | **Shipped.** `/report/KL-TVM-DEMO-001`, twelve sections, rendered from the stored payload. Its verdict is DON'T BUILD, unedited. |
| 5 | One-page website | **Shipped.** `/` — core message, three steps, the 34 factors named, the sample report visible, one form. |
| 6 | One inquiry form capturing assessment inputs | **Partly.** `/assess` captures location, space, transformer presence/size/distance and intent. No photos, no ownership type, no contact capture — contact waits on Part 7's schema. |
| 7 | Proof the partner network is real | **Blocked, on purpose.** No operator or charger maker is named without written permission; bracketed slots hold their place. |
| 8 | WhatsApp Business + Google Business Profile | **Open.** Human steps; nothing in the codebase can close them. |
| 9 | One-page PDF for CPOs | **Open.** `brochure/` (site owners, three-fold) and `explainer/` (site owners, 14 pages) both exist; neither is the CPO-facing pitch, which is a different audience asking for nothing. |

---

## Ship these — the minimum

**1. Name, domain, email on that domain**
Functional over clever. A domain email instead of Gmail is the cheapest credibility jump available.

**2. Wordmark logo only**
Business name in one good typeface. No symbol or icon — a custom mark communicates nothing decodable and costs weeks.

**3. Two colors + one typeface**
The entire visual system. Documented so it stays consistent.

**4. A sample site report — highest priority asset**
Redacted real report or a representative example. This is what separates the business from a lead broker. Owners can't evaluate judgment from a website; they can from a report. Build this first.

**5. One-page website**
In order: core message headline → 3 steps (assess → match → connect) → sample report visible → named CPO partner logos → one form. Nothing else.

**6. One inquiry form capturing assessment inputs**
Location, parking capacity, ownership type, existing power connection, photos. Means the first reply is substantive, not "let's schedule a call."

**7. Proof the partner network is real**
Named CPOs, or "X operators across Y states" if naming is contractually blocked. Vague network claims read as bluffing.

**8. WhatsApp Business + Google Business Profile**
WhatsApp is the working channel for RWA and property-owner conversations in India. GBP is free, makes the business findable and verifiable.

**9. One-page (max two) PDF for CPOs**
Different audience, different pitch — offering them qualified sites, not asking for anything.

---

## Deliberately postpone

**Don't build yet:**
- Custom logo mark, brand book, brand guidelines
- Public ROI calculator — makes automated promises before deployment data exists, and undercuts the actual product (human judgment)
- Published pricing
- Blog, SEO content engine, video, PR
- App or customer portal
- CRM (a spreadsheet handles the first 50 leads)
- Paid ads — converting audience is still unknown
- Multi-page site with About/Careers/Blog

**Don't over-think:**
Tagline, color psychology, whether the logo is "right." These feel like brand work, consume weeks, and will decide zero deals in the first six months.

---

## The test to design against
The first ten customers will come from conversations, not the website. The brand's only job now is to look real when someone Googles the business *after* a conversation. Build for that check and stop.
