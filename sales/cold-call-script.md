# Chargeworthy — cold call scripts and the idea pitch

Written 2026-09-09. Copy and positioning are taken from `design/brand/positioning.md`,
`design/brand/what-we-do.md` and the shipped landing page.

## Before you dial

**Everything in square brackets is a placeholder**, per the same rule the brochure
follows: `[38%]`, `[x]%`, `[2,000]`, `[city]`, `[amount]`. Fill them from the real
ledger, or cut the line. **Never say a number on a call you cannot put on a screen.**

**Section 1 leans on "we are not an operator."** `OVERVIEW.md` §6.3 — the
operator-affiliation decision — is unresolved. If the affiliation is still live,
that line is a liability on a recorded call, not just a positioning choice.
Decide it before dialling.

**Do not sell uptime or station usage.** Status scraping is a deferred later
stage. Station counts per operator are real (`app/domain/cpo/presence.py`, report
section 06); measured uptime and usage are not. Commercial terms do not exist.
Saying otherwise turns the one product built on honesty into a liar.

**Do not promise what a bank will do.** "Detailed enough for your bank to lend
against" — describes the document, which we control. Never "your bank will
accept this."

---

# 1. Cold call — property owner / RWA (primary)

**Target:** owner of parking or roadside land in Kerala, Tamil Nadu, Karnataka,
Maharashtra, Delhi-NCR or Gujarat. Anyone else goes to the waitlist, which is
still a logged lead and still the expansion signal.

**The goal of the call is not a sale.** It is one pin on a map. Nothing more.

## Beat 1 — Nine seconds. Name, place, permission.

> "Good morning, am I speaking with [name]? This is [your name] from Chargeworthy
> in [city]. I'll be ninety seconds and then you decide if there's a second call —
> is that fair?"

Wait for the yes. Do not talk through it.

## Beat 2 — The reason it's them

> "You've got the parking at [specific: the frontage on X road / the apartment
> block at Y / the yard behind Z]. We work out whether a piece of land can make
> money from EV charging. Yours came up because [it's on a state highway / your
> district crossed ten thousand EV registrations / the nearest charger is over two
> kilometres away]."

Specific beats flattering. If you cannot name why it is them, you are not ready
to dial them.

## Beat 3 — Name the pain before you name the product

> "The reason people call us is that they've had two or three companies pitch them
> a charger, every one of them says the site is excellent, and every one of them
> sells chargers. There's no way to tell which is right."

Pause. Let them agree. They usually have a story here — listen to it, it is your
qualification.

## Beat 4 — The differentiator, in one breath

> "Charging stations are built and run by operators. We are not one of them and we
> hold no stake in any of them. We assess the site, tell you what it will actually
> earn, and if it's a bad site we tell you that. About [38%] of the sites we look
> at, we advise against."

That last sentence is the whole pitch. **The "no" is the product.** If they hear
you can say no, everything after it is credible.

## Beat 5 — The small ask

Not a meeting. Not a brochure.

> "All I want to do is drop a pin on your location — takes about fifteen seconds
> and it's free. It gives you one number: how busy that site has to be, every
> single day, just to break even. Not a forecast. Arithmetic. If the number is
> ugly you've saved yourself twenty lakh and we're done. Do you want me to run it
> while we're on the call?"

Fifteen seconds and free is very hard to refuse. Run it live if you can — the
result screen is built for exactly this.

## Beat 6 — The five taps (qualify while it runs)

Ask these as conversation, not as a form:

1. Is there already an electricity connection at the site?
2. Do you know the sanctioned load — the kVA on your bill?
3. Is there a transformer on the property or nearby?
4. Is the land owned or leased?
5. Roughly what were you willing to put in — under ten lakh, ten to twenty-five,
   above that?

Anyone who answers four of five is a real lead. Anyone who says "I'll have to
check the bill" and then *calls you back with it* is a buyer.

## Beat 7 — Close on the report, not on the sale

> "Your breakeven is [x]%. What I can send you is the full assessment — thirty-four
> things about that specific plot, three financial scenarios, and the operators
> ranked for your site with the returns worked out separately for each one. It's
> written so your accountant and your bank can read it. Twelve sections. Can I put
> that together and call you [day] at [time] to walk you through it?"

**Book the follow-up on this call.** "I'll send it and you can get back to me" is
a dead lead.

## Objection handling

| They say | You say |
|---|---|
| **"Not interested."** | "Understood. Before I go — can I ask what you decided to do with the parking? If you've already got a plan I'll take you off the list properly." *(Half of these turn back around.)* |
| **"We're already talking to [operator]."** | "Good — that's normal. We're not replacing them, we assess the site and then rank the operators. If they come out on top for your location, that's a stronger position for you than taking their word for it. And you'll know what to ask them for." |
| **"How much does it cost?"** | "The breakeven number is free. The full assessment is ₹[amount]. Worth knowing: we charge for the report and separately for the introduction to the operator, so a 'don't build' verdict still earns us. That's deliberate — otherwise you couldn't trust the verdict." |
| **"So you're taking a commission from the charger company."** | "There is one, on the introduction, and I'd rather tell you than have you find out. It's priced separately from the report so the verdict can't be bought, and we publish how often we say don't build. If we recommended a build every time, the published number would show it." |
| **"Just email me something."** | "I will — but the email is generic and your site isn't. Give me fifteen seconds on the pin now and the email I send is about your plot instead of about us." |
| **"We don't have enough power / no transformer."** | "That's one of the thirty-four things we check, and it's usually the cheapest one to fix or the reason to walk away. Cabling runs about ₹[2,000] a metre — the assessment tells you which of the two it is, before you spend anything." |
| **"How is this different from what the charger company tells me?"** | "They start at the product. We start at your location. They compare one option — themselves. We compare several and recommend one, and we show you why." |
| **"Send it to my son / my CA / the committee."** | "Perfect — the report is written for exactly that reader. What's their number? I'd rather walk them through it than have you defend it for me." |

---

# 2. Cold call — existing operator (Tariff Audit)

This is the rung that pays **this quarter** and needs no demand model
(`OVERVIEW.md` §6.1). Different call entirely — shorter, sharper, and about money
they have already spent.

> "[Name], [your name] from Chargeworthy. Quick one — you're running [n] chargers
> at [location]. Are you on the [LT-VII / HT-II] tariff category?"

Whatever they answer, including "I don't know" — especially "I don't know":

> "That's the reason I'm calling. Most charging sites we look at are on the wrong
> tariff category, or carrying a sanctioned load two sizes bigger than they use,
> or paying peak rates for charging they could shift by two hours. We read one
> month's bill and tell you what it's costing you. Last [n] audits we did, the
> average was ₹[x] lakh a year, sitting in the bill.
>
> Send me one PDF of your electricity bill. If we find nothing, you've lost the
> ten seconds it took to forward it."

**Why this works:** it is verifiable against a document they already own. No
forecast, no trust required, no model. And every audit customer becomes a warm
prospect for expansion assessments.

---

# 3. Openers for the other two segments

**Fleet / depot:**

> "You're running [n] vehicles out of [depot]. The question we answer is whether
> charging them at your own depot beats paying public rates — and which operator
> can actually serve your duty cycles, because most can't handle a fleet that all
> plugs in at nine at night."

**CPO expansion team** — this is the subscription, not the report, and it is the
biggest rung on the ladder:

> "Your expansion team is choosing between candidate sites right now, mostly on
> someone's judgement. We rank them — same thirty-four factors, same arithmetic,
> every site scored identically, and we can do two hundred at a time. What you get
> is an ordered list with a defensible reason attached to every position,
> including the ones at the bottom."

---

# 4. The idea pitch — 60 seconds

For a partner, an investor, a bank, or anyone who asks "so what do you do?"

> "In India today, if you own land and want to put in an EV charger, every person
> who advises you also sells you the charger. There is no independent answer to
> 'will this pay back.'
>
> We're that answer. You drop a pin. We check thirty-four things about that exact
> spot — traffic direction, distance to a transformer, EV registrations in the
> district, who else is charging within three kilometres — and we tell you the one
> number that decides it: how busy the site has to be to break even. That's not a
> prediction, it's arithmetic on your cost structure, so it can't be wrong the way
> a forecast can.
>
> Then we rank the operators for your specific site, because the same neighbouring
> charger counts differently depending on who you sign with — an operator's own
> nearby station splits your demand in a way a rival's doesn't.
>
> We are not an operator. We hold no stake in any of them. And we publish how often
> we tell people not to build — because a firm that says 'build' ninety-five percent
> of the time is a sales funnel, and everyone can see it.
>
> Right site, right operator. That's the business."

**If they give you three more minutes, add the moat:**

> "The report is the marketing. The business underneath it is two things. One,
> station owners upload their electricity bills and get a free page on how their
> station performs — that gives us real usage figures that are hard to get any other way, published
> only as anonymised averages. Two, no bank in
> this country has an underwriting standard for a charging site. A pessimistic-case
> margin-of-safety number is exactly what a credit committee needs, and one lending
> partnership is worth more than a thousand retail reports."

---

# 5. Follow-up, same day

**WhatsApp — send within ten minutes of the call. This is where the lead lives or dies.**

> [Name], [your name] from Chargeworthy — thanks for the two minutes.
> Your site's breakeven: **[x]% utilisation**. Below that it loses money, above it,
> it earns.
> Full assessment attached — 12 sections, operators ranked for your plot.
> Calling you [day] at [time] as agreed. Anything before that, just reply here.

**Email subject lines that get opened:**

- `Your [locality] site: [x]% breakeven`
- `The number before you spend ₹[20] lakh`
- `[Locality] — we'd advise against this one, here's why`

That last one is not a joke. Send it when it is true, and it will be the
most-replied email you write.

---

# 6. How to work this

1. **Never quote a number you cannot put on a screen.** Every bracket above is a
   real figure from the ledger, or it gets cut.
2. **The verdict distribution is your best line.** As soon as you can say the real
   share of sites you advise against, it replaces `[38%]` and the call gets
   materially stronger. It is also the honesty firewall working as designed
   (`OVERVIEW.md` §6.2).
3. **Sell the free breakeven, not the report.** The teaser is pure arithmetic and
   needs no model. It is the whole reason the first call converts.
4. **Every waitlisted pin is worth logging.** Whichever uncovered district
   accumulates the most is the next state we cover.
