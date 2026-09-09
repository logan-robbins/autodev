import { createHash } from 'node:crypto';
import { parseQuote, quoteText, QUOTE_RECIPIENT } from '@/lib/quote';
export const runtime = 'nodejs';
export async function POST(request: Request) {
  const origin = request.headers.get('origin');
  if (origin && origin !== new URL(request.url).origin)
    return Response.json(
      { error: 'Please submit the form from the autodev team website.' },
      { status: 403 },
    );
  if (!request.headers.get('content-type')?.includes('application/json'))
    return Response.json(
      { error: 'Unsupported request format.' },
      { status: 415 },
    );
  let value;
  try {
    const raw = await request.text();
    if (new TextEncoder().encode(raw).length > 24000)
      return Response.json(
        { error: 'Please shorten your project brief.' },
        { status: 413 },
      );
    value = JSON.parse(raw);
  } catch {
    return Response.json(
      { error: 'Please check your request and try again.' },
      { status: 400 },
    );
  }
  if (value?.website)
    return Response.json(
      { error: 'Unable to submit this request.' },
      { status: 400 },
    );
  let quote;
  try {
    quote = parseQuote(value);
  } catch (error) {
    return Response.json(
      {
        error:
          error instanceof Error ? error.message : 'Please check your request.',
      },
      { status: 400 },
    );
  }
  if (!process.env.RESEND_API_KEY || !process.env.QUOTE_FROM_EMAIL)
    return Response.json(
      {
        error:
          'Email delivery is not connected. Please send your brief to info@qmachina.com.',
        emailFallback: true,
      },
      { status: 503 },
    );
  try {
    // A retry of the same brief stays idempotent; editing the brief creates a new delivery key.
    const key = createHash('sha256')
      .update(JSON.stringify(quote))
      .digest('hex');
    const sent = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${process.env.RESEND_API_KEY}`,
        'Content-Type': 'application/json',
        'Idempotency-Key': `autodev-quote/${key}`,
      },
      body: JSON.stringify({
        from: process.env.QUOTE_FROM_EMAIL,
        to: [QUOTE_RECIPIENT],
        reply_to: quote.email,
        subject: `autodev team quote request — ${quote.name}`,
        text: quoteText(quote),
      }),
      signal: AbortSignal.timeout(12000),
    });
    if (!sent.ok)
      return Response.json(
        {
          error:
            'Your brief could not be sent. Please try again or email info@qmachina.com.',
        },
        { status: 502 },
      );
    return Response.json({ reference: quote.id.slice(0, 8).toUpperCase() });
  } catch {
    return Response.json(
      {
        error:
          'Email delivery timed out. Please retry; duplicate requests are protected.',
      },
      { status: 502 },
    );
  }
}
