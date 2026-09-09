import Link from 'next/link';
import {
  ArrowUpRight,
  ArrowRight,
  Cpu,
  Layers3,
  GitBranch,
  ShieldCheck,
  ScanLine,
} from 'lucide-react';
import QuoteForm from './quote-form';

export const dynamic = 'force-dynamic';
const companies = ['OpenAI', 'Anthropic', 'Apple', 'Meta', 'Amazon', 'NVIDIA'];
const steps = [
  [
    '01',
    'Human direction.',
    'Senior engineers shape the architecture, challenge assumptions, and own the decisions that matter.',
  ],
  [
    '02',
    'Agentic execution.',
    'Our proprietary Autodev platform coordinates native AI coding harnesses in parallel, each with a defined scope and delivery contract.',
  ],
  [
    '03',
    'Verified delivery.',
    'Interfaces come first. Outputs pass contract checks before publication. You see the work, the handoffs, and the evidence.',
  ],
];
export default function Home() {
  return (
    <>
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <header className="site-header wrap">
        <Link href="/" className="wordmark" aria-label="Autodev home">
          <span className="brand-mark">a↗</span>autodev
          <span className="brand-period">.</span>
        </Link>
        <nav aria-label="Main navigation">
          <a href="#approach">Our approach</a>
          <a href="/demo/index.html?demo=1" target="_blank" rel="noreferrer">
            Platform demo <ArrowUpRight size={15} />
          </a>
          <a className="nav-quote" href="#quote">
            Request a quote <ArrowUpRight size={15} />
          </a>
        </nav>
      </header>
      <main id="main">
        <section className="hero wrap">
          <div className="eyebrow">
            <span className="signal" /> THE HUMAN × AI AGENCY
          </div>
          <h1>
            Frontier quality.
            <br />
            <span>Face-melting speed.</span>
          </h1>
          <div className="hero-bottom">
            <p>
              Extraordinary engineers. Relentless AI.
              <br />
              We build ambitious software at a fraction of the traditional cost.
            </p>
            <div className="hero-actions">
              <a className="cta" href="#quote">
                Let’s build something <ArrowUpRight size={20} />
              </a>
              <a
                className="text-link"
                href="/demo/index.html?demo=1"
                target="_blank"
                rel="noreferrer"
              >
                See Autodev in action <ArrowRight size={18} />
              </a>
            </div>
          </div>
          <div
            className="system-preview"
            aria-label="Autodev delivery workflow illustration"
          >
            <div className="system-top">
              <span>
                <span className="signal" /> AUTODEV / DELIVERY ENGINE
              </span>
              <span className="diagram-label">
                Human direction. Parallel execution.
              </span>
            </div>
            <div className="system-flow">
              <div className="direction-node">
                <span className="node-icon">
                  <ScanLine size={26} />
                </span>
                <span className="mono">01 / DEFINE</span>
                <h3>Human expertise</h3>
                <p>
                  Architecture. Priorities.
                  <br />
                  Judgment.
                </p>
              </div>
              <div className="flow-connector">
                <span />
                <ArrowRight />
              </div>
              <div className="fleet-node">
                <div className="fleet-title">
                  <Cpu size={22} />
                  <h3>Agentic delivery, at scale.</h3>
                </div>
                <div className="pillar-chips">
                  {[
                    'Research',
                    'Frontend',
                    'Infrastructure',
                    'Data',
                    'Analysis',
                    'Project management',
                  ].map((p) => (
                    <span key={p}>
                      <span className="chip-dot" />
                      {p}
                      <span className="chip-agents">10 ↗</span>
                    </span>
                  ))}
                </div>
                <div className="fleet-caption">
                  60 Harness Agents <span>·</span> 6 Pillars
                </div>
              </div>
              <div className="flow-connector">
                <span />
                <ArrowRight />
              </div>
              <div className="direction-node delivery-node">
                <span className="node-icon">
                  <ShieldCheck size={26} />
                </span>
                <span className="mono">03 / DELIVER</span>
                <h3>Verified output</h3>
                <p>
                  Working software.
                  <br />
                  Evidence included.
                </p>
              </div>
            </div>
            <a
              className="preview-footer"
              href="/demo/index.html?demo=1"
              target="_blank"
              rel="noreferrer"
            >
              <span>Explore the interactive fleet simulation</span>
              <span>
                Open demo <ArrowUpRight size={18} />
              </span>
            </a>
          </div>
        </section>
        <section className="pedigree wrap" aria-label="Team background">
          <p>
            A stealth team of engineers from the companies building the
            frontier.
          </p>
          <div className="company-row">
            {companies.map((name) => (
              <span key={name}>{name}</span>
            ))}
          </div>
        </section>
        <section className="approach wrap" id="approach">
          <div className="section-intro">
            <span className="eyebrow">THE MULTIPLIER</span>
            <h2>
              Human judgment.
              <br />
              <span>Machine velocity.</span>
            </h2>
            <p>
              Great software takes more than a prompt. We combine experienced
              engineering leadership with a platform built for the entire
              software development lifecycle.
            </p>
          </div>
          <div className="principles">
            {steps.map(([n, title, body]) => (
              <article key={n}>
                <span className="step-number">{n}</span>
                <div>
                  <h3>{title}</h3>
                  <p>{body}</p>
                </div>
              </article>
            ))}
          </div>
        </section>
        <section className="platform wrap">
          <div className="platform-copy">
            <span className="eyebrow">POWERED BY OUR PROPRIETARY PLATFORM</span>
            <h2>
              Built to build.
              <br />
              All the way to done.
            </h2>
            <p>
              Autodev runs full Claude Code and Codex harnesses in isolated
              sessions. Pillars give work clear boundaries. Contracts keep
              parallel teams aligned. Every assignment has an owner, a ledger,
              and a verifiable output.
            </p>
            <a
              className="text-link"
              href="/demo/index.html?demo=1"
              target="_blank"
              rel="noreferrer"
            >
              Watch the fleet work <ArrowUpRight size={18} />
            </a>
          </div>
          <div className="platform-points">
            <div>
              <Layers3 />
              <span>Independent Pillars</span>
              <p>Decoupled capabilities, connected by stable interfaces.</p>
            </div>
            <div>
              <GitBranch />
              <span>Parallel by design</span>
              <p>Specialized Harness Agents working across the lifecycle.</p>
            </div>
            <div>
              <ShieldCheck />
              <span>Contracts before code</span>
              <p>Defined outputs, executable checks, visible delivery.</p>
            </div>
          </div>
        </section>
        <section className="quote-section" id="quote">
          <div className="quote-inner wrap">
            <div className="quote-copy">
              <span className="eyebrow">YOUR NEXT UNFAIR ADVANTAGE</span>
              <h2>
                What are
                <br />
                we building?
              </h2>
              <p>
                A new product. A critical platform. The backlog that never
                moves.
              </p>
              <p>
                Tell us where you want to go. We’ll work out the scope, the
                team, and the path to delivery.
              </p>
              <div className="quote-note">
                <ArrowUpRight size={24} />
                <span>
                  Human expertise.
                  <br />
                  Autodev execution.
                </span>
              </div>
            </div>
            <QuoteForm
              emailDeliveryEnabled={Boolean(
                process.env.RESEND_API_KEY && process.env.QUOTE_FROM_EMAIL,
              )}
            />
          </div>
        </section>
      </main>
      <footer className="site-footer wrap">
        <Link className="wordmark" href="/">
          autodev<span className="brand-period">.</span>
        </Link>
        <span>Human × AI. Built for what’s next.</span>
        <span>© {new Date().getFullYear()} Autodev</span>
      </footer>
    </>
  );
}
