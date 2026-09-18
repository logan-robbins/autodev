# Email cutover — Autodev Team

**Status:** Mailboxes **LIVE** (M365 shared, qMachina Entra). GTM sales copy cutover in progress.  
**Updated:** 2026-09-13  
**Not Vercel** — Vercel = site host; Resend = send-from only. Mailboxes = Microsoft 365 / Exchange.

---

## Mailbox map (lock)

| Address | Role | Status |
|---|---|---|
| **`chief@autodev-team.com`** | CoS / Grok Bot **ops** | Live shared mailbox. **Never** LI About / form / ads / Lead Gen. |
| **`hello@autodev-team.com`** | **Primary** public quote + sales inbound | Live shared mailbox → Logan FullAccess / SendAs |
| **`info@autodev-team.com`** | Alias → `hello@` | Live |
| **`info@qmachina.com`** | 90d fallback / forward | Keep until site Resend + cold traffic drain |

**Hard rule:** `chief@` ≠ sales. Tire-kickers must not hit the bot.

---

## Checklist

1. [x] Domain verified; MX/SPF/autodiscover on Vercel DNS  
2. [x] Mailbox: `hello@` (+ `info@` alias) → Logan  
3. [x] Mailbox: `chief@` → CoS/Grokbot ops only  
4. [ ] Vercel `QUOTE_FROM_EMAIL=hello@autodev-team.com` (+ Resend domain if needed)  
5. [ ] Forward `info@qmachina.com` → `hello@` (90d)  
6. [x] Demand LI kit → `hello@`  
7. [x] Offer one-pager / leadgen → `hello@` (this pass)  
8. [ ] Site form public address → `hello@` (CoS / product)  
9. [ ] CHARTER quote line → `hello@`  
10. [ ] Discovery calendar replies from `hello@` (calendar URL still Logan gate)  
11. [ ] Later: `chief@` → licensed user if Grok Bot needs interactive login (only 1× Business Premium on logan@ today)

---

## Do not publish

- `chief@autodev-team.com` on any Demand / Offer public surface.
