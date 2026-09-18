# LinkedIn Lead Gen fields — Autodev Team

**Purpose:** Form on Company Page / Lead Gen ads → **Logan** (not self-serve checkout).  
**CTA copy lock (Demand):** Book discovery — scoped Pillar, not free credits.  
**Payment helper (high — form headline / thank-you):** No upfront payment. Pay at UAT milestones.*  
**Full * (About-length / captions only — not on hero):**  
* Hours and scope agreed ahead · invoice at Autodev UAT for that scope · change orders before start.
* (hygiene) Invoices at Autodev-defined UAT acceptance for that scope. Hours and scope are agreed ahead of time. Change orders quoted before start. ≠ pay-when-happy, free forever discovery, open-ended T&M / verbal-only, or “no pay until prod” unless SOW final UAT is cutover.
* Invoices at Autodev-defined UAT acceptance for that scope. Hours and scope are agreed ahead of time. Change orders quoted before start. ≠ pay-when-happy, free forever discovery, or “no pay until prod” unless SOW final UAT is cutover.  
**Updated:** 2026-09-11 (footnote placement: short high / full low — match site)  
**Status:** Field spec only. Wire when page + ads unlocked by Logan.

---

## Routing

| Step | Owner |
|---|---|
| Form submit | LinkedIn → notification to Logan (Company Page admin / Lead Gen inbox) |
| First response SLA | Logan (or designee) within 1 business day |
| Qualify | Offer discovery gate (`discovery-script.md`) |
| Quote | hello@autodev-team.com — itemized only after discovery passes |

**Do not** auto-send Autodev license keys, credit packs, or "start free trial."

---

## Form fields (v0)

LinkedIn pre-fills where possible; keep custom questions ≤4 so completion stays high.

### Prefill (LinkedIn standard — enable)

1. First name  
2. Last name  
3. Work email *(prefer work over personal)*  
4. Job title  
5. Company name  
6. Company size *(if available)*  
7. Phone *(optional — off by default Day-0; turn on if CPL OK but booking rate low)*

### Custom questions (required order)

| # | Question (as shown) | Type | Why |
|---|---|---|---|
| **Q0** | What are you primarily looking for? | Multiple choice (single) | **Hard gate** — kill DIY before calendar |
| **Q1** | What's the urgent delivery problem? (1–2 sentences) | Short text | Trigger + scope hint |
| **Q2** | Company stage / eng org size (approx) | Multiple choice | ICP tier |
| **Q3** | Preferred next step | Multiple choice | Intent |

#### Q0 options (exact labels)

1. **Onshore staff-aug capacity to ship software** (hybrid operators + Autodev; fractional vs FTE) ← *ICP*  
2. **A SaaS/PaaS / seats for our team to run agents ourselves** ← *DIY DQ*  
3. **Not sure yet — need a recommendation** ← *educate once, then gate on call*

#### Q2 options

- Seed–Series A (<50 eng-adjacent)  
- Series B–D (50–400 eng-adjacent) ← *priority*  
- Mid-market / enterprise product org  
- Agency / consultancy (partner later)  
- Other / prefer not to say

#### Q3 options

- Book a discovery call  
- Send the one-pager / pricing shape first  
- Security / clean-room briefing first  

---

## Privacy / consent line (LinkedIn form)

> We use this to route a discovery conversation with Autodev Team. No upfront payment. Pay at UAT milestones.* No self-serve product access. Questions: hello@autodev-team.com

**Form helper (under headline if LI allows):** No upfront payment. Pay at UAT milestones.*  
*(Full footnote lives in Payment helper block above / LinkedIn About — not crammed into the field UI.)*

---

## Thank-you / confirmation

**On-form thank you:**  
Thanks — Logan will follow up within one business day. No upfront payment. Pay at UAT milestones.* Meanwhile: https://autodev-team.com (live demo). If you picked "platform / seats for our team," we may reply with a short category note instead of a call.

**Email auto-response (if LinkedIn allows / or Logan CRM later):**  
- Staff-aug (Q0=1): confirm receipt + calendar link *only when Logan enables*  
- DIY (Q0=2): soft DQ template from `discovery-script.md` — **no calendar**  
- Unsure (Q0=3): short contrast (staff-aug vs SaaS/PaaS configure) + offer one call to decide

---

## Handoff fields Logan should capture (CRM / sheet)

When a lead lands, log:

| Field | Source |
|---|---|
| LinkedIn lead id / time | LinkedIn |
| Q0–Q3 answers | Form |
| Gate | Staff-aug / DIY / Unsure |
| ICP tier | Q2 + title |
| Assigned call | Logan / Offer |
| Outcome | Booked / DQ / nurture |

Sheet path TBD (`gtm/offer/pipeline/` when stood up). Day-0 = Logan inbox is fine.

---

## Sync with Demand ads

| Ad element | Uses |
|---|---|
| CTA button | Get quote / Sign up → **this form** |
| Primary text | Discovery / scoped Pillar — not free credits |
| Success | CPL + **form→booked %** + call→scoped engagement (Demand metrics) |
| Kill | High CPL *and* qualify rate <20% after ≥50 leads **or** majority Q0=DIY → reframe creative (still-09 / still-07) |

---

## Logan gates

- [ ] Create form on Company Page with these fields  
- [ ] Confirm notification email / admin  
- [ ] Enable/disable phone  
- [ ] Calendar link for capacity-qualified only  
- [ ] Ad launch (Demand) after form live
