import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseQuote, quoteMailto, quoteText } from '../lib/quote.ts';
const valid = {
  id: 'bce9ec5f-9c9f-4a30-9fcb-d59ee3a87d06',
  name: 'Alex Morgan',
  email: 'alex@example.com',
  company: 'Example',
  project: 'Build a customer portal with an accessible onboarding flow.',
  timeline: 'Within 1 month',
};
await test('quote fields are validated and trimmed', () => {
  const q = parseQuote({ ...valid, name: ' Alex Morgan ' });
  assert.equal(q.name, valid.name);
  for (const patch of [
    { email: 'bad' },
    { project: 'short' },
    { id: 'invalid' },
    { timeline: 'unknown' },
    { name: 'Injected\r\nHeader: test' },
    { project: 'x'.repeat(5001) },
  ])
    assert.throws(() => parseQuote({ ...valid, ...patch }));
  assert.throws(() => parseQuote(null));
});
await test('draft has a fixed recipient and encodes supplied content safely', () => {
  const q = parseQuote({
    ...valid,
    project: valid.project + ' & scope #1? x=2',
  });
  const draft = quoteMailto(q);
  assert.ok(draft.startsWith('mailto:info@qmachina.com?'));
  const params = new URLSearchParams(draft.split('?')[1]);
  assert.equal(params.get('body'), quoteText(q));
  assert.equal(params.get('subject'), 'Autodev quote request — Alex Morgan');
});
