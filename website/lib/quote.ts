export const QUOTE_RECIPIENT = 'info@qmachina.com';
export const BUDGETS = [
  'Under $25k',
  '$25k–$75k',
  '$75k–$150k',
  '$150k+',
  'Not sure yet',
];
export const TIMELINES = [
  'As soon as possible',
  'Within 1 month',
  'Within 3 months',
  'Flexible',
];
export type Quote = {
  id: string;
  name: string;
  email: string;
  company: string;
  project: string;
  budget: string;
  timeline: string;
};
export function parseQuote(value: unknown): Quote {
  if (!value || typeof value !== 'object' || Array.isArray(value))
    throw new Error('Please complete the project brief.');
  const v = value as Record<string, unknown>;
  function field(name: string, max: number, min = 0) {
    const text = typeof v[name] === 'string' ? v[name].trim() : '';
    if (text.length < min || text.length > max)
      throw new Error(`Please check the ${name} field.`);
    return text;
  }
  const id = field('id', 36, 36);
  if (
    !/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
      id,
    )
  )
    throw new Error('Please refresh the page and try again.');
  const name = field('name', 100, 1),
    email = field('email', 254, 3),
    company = field('company', 150),
    project = field('project', 5000, 20),
    budget = field('budget', 40),
    timeline = field('timeline', 40);
  if (
    !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) ||
    /[\r\n]/.test(name + company)
  )
    throw new Error('Please check your name, company, and email address.');
  if (!BUDGETS.includes(budget) || !TIMELINES.includes(timeline))
    throw new Error('Please choose a budget and timeline.');
  return { id, name, email, company, project, budget, timeline };
}
export function quoteText(q: Quote) {
  return `Autodev project enquiry\n\nName: ${q.name}\nEmail: ${q.email}\nCompany: ${q.company || 'Not provided'}\nBudget: ${q.budget}\nTimeline: ${q.timeline}\n\nProject brief\n${q.project}\n\nReference: ${q.id}`;
}
export function quoteMailto(q: Quote) {
  return `mailto:${QUOTE_RECIPIENT}?subject=${encodeURIComponent('Autodev quote request — ' + q.name)}&body=${encodeURIComponent(quoteText(q))}`;
}
