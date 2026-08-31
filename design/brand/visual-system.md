# Chargeworthy — Visual System

Paste this block into **every** design or build prompt. It is the shared root that keeps the marketing site, the assessment flow, and the site report reading as one company.

---

## Two surfaces, one brand

| | Marketing site & assessment flow | Site report |
|---|---|---|
| Ground | Deep slate (dark) | Warm paper (light) |
| Register | Premium, confident, spacious | Sober, documentary, printable |
| Motion | Restrained, weighted | None |

The report is the marketing palette inverted onto paper. Same slate, same warm off-white — swapped roles. That is what makes them read as one brand rather than two vendors.

---

## Palette — marketing site & flow (dark)

| Token | Hex | Use |
|---|---|---|
| `ground` | `#0D151E` | Page background |
| `surface` | `#16212C` | Cards, elevated panels |
| `surface-2` | `#1E2C39` | Hover states, nested panels |
| `line` | `#253340` | Borders, dividers |
| `text` | `#F4F1EC` | Primary text — warm white, not pure white |
| `muted` | `#93A1AD` | Secondary text, labels |
| `slate` | `#4A8FB8` | Brand blue, lifted for dark backgrounds |
| `accent` | `#D98A3D` | Copper — CTAs, key figures, highlights |
| `positive` | `#3FA37F` | Confirmations, favourable indicators |
| `negative` | `#C4564A` | Warnings, unfavourable indicators |

**Why copper, not green.** Every EV brand uses green or cyan. Copper is unclaimed in the category, reads as premium rather than eco-startup, and connects to electrical conductor material. It also does not collide with the report's semantic green/red verdicts.

**Accent discipline:** copper appears on roughly 5% of any screen. Primary CTA, one hero figure, active states. Nothing else. The moment it is used decoratively the page stops looking expensive.

---

## Palette — site report (light)

| Token | Hex | Use |
|---|---|---|
| `ink` | `#12171A` | Primary text, rules, threshold ticks |
| `paper` | `#FAF8F4` | Page background — warm off-white |
| `slate` | `#1C3A4F` | Section headers, brand mark |
| `rule` | `#D6D2C8` | Hairlines, table borders |
| `muted` | `#5C5852` | Secondary text, provenance |
| `band` | `#B9C6CC` | P10–P90 confidence bar |
| `verdict-positive` | `#1F5E4A` | "BUILD" only |
| `verdict-negative` | `#8C2A20` | "DON'T BUILD" only |
| `caution` | `#A65B1F` | Conditional verdicts, unverified markers |
| `caution-tint` | `#F5E6D3` | Chip background (text at `#7A4113`) |

**Two locked decisions.** The brand colour is slate blue, not green, so green and red stay purely semantic — a green-branded report saying DON'T BUILD would read as a contradiction. And the report is light-mode only; financial documents do not have a dark mode.

---

## Typography

**Marketing site & flow**
- Display / headings: a confident geometric or transitional sans — Satoshi, General Sans, or Inter Display
- Body: same family, regular weight
- Numbers and data: a monospace with tabular figures — JetBrains Mono or IBM Plex Mono
- Hero headline: 56–72px desktop, 34–40px mobile
- Body: minimum 17px at 1.6 line-height
- No weight below 400 anywhere — the audience is 35–55

**Site report**
- Headings, verdicts, all prose: a serif — Source Serif 4 or Lora
- Every number: monospace with tabular figures, so digits align in columns
- Body: minimum 17px at 1.6 line-height
- Nothing under 13px except the provenance list, which may go to 12px

---

## Audience constraint

The buyer is a 35–55 year old private investor committing ₹20–40 lakh. They benchmark against fixed deposits and rental yield, and will print things to show an accountant.

For this reader, **premium means restraint**: deep colour, generous whitespace, real typography, and motion that feels like weight settling rather than play. Flashy motion reads as a startup that may not exist in three years — precisely the wrong signal for a business selling long-horizon judgment.

Reference the structure and polish of premium B2B SaaS landing pages, but dial motion intensity down by roughly a third.
