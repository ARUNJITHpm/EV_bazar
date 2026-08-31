# Chargeworthy — copy pass

Audited against the strings actually in the build, not the artboards.

The draft copy is mostly sound. Four things are wrong with it structurally, and
those matter more than any individual headline.

---

## 1. "Operator" appears eight times and is never defined

The landing page says *operator* in the motto, in step 02, on two cards, and in
the footer. A 35–55 year old who is not an EV person does not know what a charge
point operator is. They will infer something, and what they infer is probably
"the company that sells chargers" — which quietly undoes the whole independence
argument, because it makes Chargeworthy sound like a middleman taking a cut on
hardware.

**Fix:** define it once, in plain language, the first time it appears — in the
hero, where the independence line already sits.

> Current: *We are not a charge point operator and hold no stake in any station.*
>
> **Recommended:** *Charging stations are built and run by operators. We are not
> one of them, and we hold no stake in any of them.*

That is 26 characters longer and does two jobs: it teaches the word and states
the position. Everything downstream then reads correctly.

---

## 2. Design vocabulary is leaking into user copy

Three places describe *our own mechanics* to someone who does not care:

| Where | Current | Problem | Recommended |
|---|---|---|---|
| Transformer, step 2 | "Distance and capacity next, one question per screen." | "One question per screen" is our design principle, not a benefit | "Two quick questions about it, one at a time." |
| Working screen | "We are reading the live sources now, not returning a stored answer." | "Stored answer" is developer language, and it defends against an accusation nobody made | "We are checking the live records now. This takes about fifteen seconds." |
| Intent, step 4 | "This changes which operators suit you, and how we model the demand." | "Model the demand" is jargon | "This changes which operators suit you, and how busy we expect the site to be." |

---

## 3. "A document your bank will accept" promises something you do not control

This is the one line on the site that could genuinely embarrass you. You cannot
guarantee what a bank does. If one owner takes a report to a manager who shrugs,
the sentence becomes a lie — on the page of a firm whose entire product is not
lying.

Three ways out, in order of how much I would recommend them:

1. **"Detailed enough for your bank to lend against."** — describes the
   document, not the bank's behaviour. Same force, defensible.
2. **"Written for your accountant as much as for you."** — moves the claim to a
   reader you can actually anticipate.
3. **Keep it**, and be able to name banks that have accepted one. If you can do
   that, the bold version is better than either alternative.

---

## 4. The page says "site". Your reader says "land"

*Site* is our word. The owner thinks *my land*, *my plot*, *the corner by the
highway*. And in the hero, before any pin is dropped, "this site" has no
referent — "this" points at nothing.

> Current headline: *Will this site pay for a charger?*
>
> **Recommended:** *Will your land pay for a charger?*

One word shorter, addresses them directly, and the referent is unambiguous.
Keep "site" everywhere after the pin drops — by then it means something.

---

## Slot-by-slot

Character counts in brackets. Where I have a recommendation it is marked.

### Hero

**Headline** [33]
- *Will this site pay for a charger?* — current
- **★ *Will your land pay for a charger?*** [32] — theirs, not ours; referent is clear
- *Will a charger here make money?* [30] — flatter, but "make money" is the actual question

**Supporting** [166]
- Current: *We assess the location, set the return against what a fixed deposit would earn on the same money, and tell you plainly — including when the answer is no.*
- **★** [149]: *We assess the location, set the return against what a fixed deposit would pay on the same money, and tell you plainly — including when the answer is no.*
- The clause "on the same money" is doing real work. Do not cut it to save length; it is what makes the comparison concrete rather than abstract.

**Primary CTA** [16]
- *Assess this site* — current. "Assess" is our verb.
- **★ *See the verdict*** [15] — names what they get, and "verdict" is the word the whole product turns on
- *Check this location* [19]

**Proof row, first item** [26]
- *1,000+ owners in our network* — current. Vague: what does being in the network mean?
- **★ *1,000+ station owners we work with*** [31] — plainer, still true
- If you can say what the relationship actually is, say that instead. Vagueness reads as padding to this audience.

### How it works

**Section headline** [40] — *Three steps, and we stop at any of them.* Keep. It states the differentiator inside a structural heading, which is rare and good.

**Step 02 body** [174] — Keep. "How fast they reach you for a fault" is the most concrete thing on the page and it should stay exactly as written.

### What we check

**"Nothing here is a guess."** [24] — Keep. Short, blunt, earns the 34 chips below it.

### Cards

**"We tell people not to build."** [28] — Keep. Best line on the site.

**"We have no stake in you building."** [33] — Keep.

**Card 1 body** — currently ends *"Our fee was the same either way."* Consider *"We were paid the same either way."* [30] — active, and "we were paid" is more concrete than "our fee".

### The report

**Headline** [33] — see finding 3 above.

**"Read a real one end to end before you commission your own."** [58]
- "Commission" is formal. **★** *Read a real one end to end before you order your own.* [52]

### Close

**"Start with the location. We will tell you the rest."** [51] — Keep.

### Flow

Most of the flow copy is good — plain, short, and it names things the way an
owner would. The three fixes are in finding 2. One more:

**"I am not sure — skip this one"** [29]
- **★ *I don't know this one — skip it*** [31] — "I am not sure" is hedged; owners
  are more likely to click a button that says plainly they don't know. Removing
  the friction here matters: this is the screen that replaced the dropdown.

---

## Voice rules

For anything written later, by anyone.

**Do**
- Every claim carries a number, or gets cut
- Prefer the concrete noun: "district EV registrations", not "market data"
- Say "no" where it applies — the willingness to reject sites is the product
- Indian numbering: lakh and crore, never millions
- Write what the reader gets, not what the system does

**Never**
- "Revolutionary", "seamless", "empower", "unlock", "game-changing", "journey"
- Exclamation marks
- Addressing the reader as part of a movement
- Any sentence that could describe a different company in a different industry
- Implying Chargeworthy operates stations — one careless line dissolves the
  entire position

**The test for any new sentence:** could a charge point operator put this on
their own site? If yes, it is not saying anything only you can say.
