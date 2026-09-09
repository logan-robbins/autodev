# Autodev agency website

Next.js website for the Human × AI agency. The product source lives alongside
this directory on the canonical `main` branch. Vercel should use `website` as its
project root, with the detected Next.js defaults.

## Local development

Run `npm ci`, then `npm run dev`. The preview runs at http://127.0.0.1:3000.
Run `npm run build` for the production build and `node --test tests/quote.test.ts`
for quote validation tests (Node 22.18+ supports the test TypeScript directly).

## Fleet demo

`public/demo/` is a generated, standalone copy of the canonical runtime UI at
`../src/autodev/web/`. Run `npm run demo:sync` from the repository before building
when those sources change. Commit generated demo assets with the website so
Vercel can build from this subdirectory alone. The `demoOnly` bootstrap disables
runtime polling and sends exit links back to the agency homepage. No runtime
credentials or real project data are packaged.

## Quote delivery

The recipient is fixed to `info@qmachina.com`. Without email provider settings,
the form prepares a populated email draft and explicitly asks the visitor to
send it. It never reports that an unsent draft was received.

To enable direct form submission, configure `RESEND_API_KEY` and
`QUOTE_FROM_EMAIL` in Vercel. The sender must belong to a domain verified in the
Resend account. The recipient cannot be overridden by the client. Validation,
same-origin requests, a honeypot, timeouts, and provider idempotency are enforced.
No provider keys belong in source control. No test messages are sent by tests.

The team-background and agency pricing claims are marketing copy supplied by
the project owner; the site adds no fabricated case studies or performance metrics.
