'use client';
import { useRef, useState, type SubmitEvent } from 'react';
import { ArrowUpRight, Check, Loader2 } from 'lucide-react';
import { parseQuote, quoteMailto } from '@/lib/quote';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '@/components/ui/select';
export default function QuoteForm({
  emailDeliveryEnabled,
}: {
  emailDeliveryEnabled: boolean;
}) {
  const [timeline, setTimeline] = useState<string | null>(null);
  const [status, setStatus] = useState<
    'idle' | 'sending' | 'success' | 'error' | 'draft'
  >('idle');
  const [message, setMessage] = useState('');
  const [draft, setDraft] = useState('');
  const requestId = useRef<string | null>(null);
  async function submit(e: SubmitEvent<HTMLFormElement>) {
    e.preventDefault();
    if (status === 'sending') return;
    const form = new FormData(e.currentTarget);
    requestId.current ||= crypto.randomUUID();
    const payload = {
      id: requestId.current,
      name: form.get('name'),
      email: form.get('email'),
      company: form.get('company'),
      project: form.get('project'),
      website: form.get('website'),
      timeline: timeline || 'Flexible',
    };
    if (!emailDeliveryEnabled) {
      try {
        setDraft(quoteMailto(parseQuote(payload)));
        setStatus('draft');
      } catch (error) {
        setStatus('error');
        setMessage(
          error instanceof Error ? error.message : 'Please check your brief.',
        );
      }
      return;
    }
    setStatus('sending');
    setMessage('');
    try {
      const response = await fetch('/api/quotes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(15000),
      });
      const result = await response.json();
      if (!response.ok)
        throw new Error(
          result.error || 'Your request could not be saved. Please try again.',
        );
      setStatus('success');
      setMessage(result.reference);
    } catch (error) {
      setStatus('error');
      setMessage(
        error instanceof Error
          ? error.message
          : 'Something went wrong. Please try again.',
      );
    }
  }
  if (status === 'draft')
    return (
      <div className="quote-success" aria-live="polite">
        <h3>Your brief is ready.</h3>
        <p>
          Open the draft in your email app and send it to{' '}
          <strong>info@qmachina.com</strong> to submit your request.
        </p>
        <a className="cta" href={draft}>
          Open email draft <ArrowUpRight size={18} />
        </a>
        <Button
          variant="link"
          className="edit-brief"
          onClick={() => setStatus('idle')}
        >
          Start another brief
        </Button>
        <p className="reference">Nothing has been sent yet.</p>
      </div>
    );
  if (status === 'success')
    return (
      <div className="quote-success" aria-live="polite">
        <span className="success-icon">
          <Check size={30} />
        </span>
        <h3>You’re on our radar.</h3>
        <p>
          Your project brief has been received. We’ll use the email you provided
          to follow up.
        </p>
        <span className="reference">Reference {message}</span>
      </div>
    );
  return (
    <form className="quote-form" onSubmit={submit}>
      <h3>Request a quote</h3>
      <div className="form-grid">
        <label htmlFor="name">
          Your name
          <Input
            id="name"
            name="name"
            autoComplete="name"
            placeholder="Alex Morgan"
            required
            maxLength={100}
          />
        </label>
        <label htmlFor="email">
          Work email
          <Input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            placeholder="alex@company.com"
            required
            maxLength={254}
          />
        </label>
      </div>
      <label htmlFor="company">
        Company <span className="optional">(optional)</span>
        <Input
          id="company"
          name="company"
          autoComplete="organization"
          placeholder="Your company"
          maxLength={150}
        />
      </label>
      <label htmlFor="project">
        What would you like to build?
        <Textarea
          id="project"
          name="project"
          placeholder="The idea, the challenge, and what success looks like."
          required
          minLength={20}
          maxLength={5000}
          rows={4}
        />
      </label>
      <div className="select-field">
        <label id="timeline-label" htmlFor="timeline">
          Timeline
        </label>
        <Select value={timeline} onValueChange={setTimeline}>
          <SelectTrigger id="timeline" aria-labelledby="timeline-label">
            <SelectValue placeholder="When do we start?" />
          </SelectTrigger>
          <SelectContent>
            {[
              'As soon as possible',
              'Within 1 month',
              'Within 3 months',
              'Flexible',
            ].map((v) => (
              <SelectItem key={v} value={v}>
                {v}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="honeypot" aria-hidden="true">
        <label htmlFor="website">
          Website
          <Input id="website" name="website" tabIndex={-1} autoComplete="off" />
        </label>
      </div>
      {status === 'error' && (
        <p className="form-error" role="alert">
          {message}
        </p>
      )}
      <Button
        className="quote-submit"
        type="submit"
        disabled={status === 'sending'}
      >
        {status === 'sending' ? (
          <>
            Sending your brief <Loader2 className="animate-spin" />
          </>
        ) : (
          <>
            {emailDeliveryEnabled ? 'Request a quote' : 'Prepare quote request'}{' '}
            <ArrowUpRight />
          </>
        )}
      </Button>
      <p className="form-privacy">
        {emailDeliveryEnabled
          ? 'Your details are used to respond to this project enquiry.'
          : 'Prepares an email to info@qmachina.com. You review and send it.'}
      </p>
    </form>
  );
}
