import Link from 'next/link';
import {
  ArrowUpRight,
  ArrowRight,
  Cpu,
  Layers3,
  GitBranch,
  ShieldCheck,
  ScanLine,
  LockKeyhole,
  Database,
  Cloud,
  Unplug,
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
        <Link href="/" className="wordmark" aria-label="autodev team home">
          <span className="brand-mark">a↗</span>
          <span className="brand-name">
            autodev{' '}
            <span className="brand-team">
              team<span className="brand-period">.</span>
            </span>
          </span>
        </Link>
        <nav aria-label="Main navigation">
          <a href="#approach">Our approach</a>
          <a href="/demo/index.html?demo=1" target="_blank" rel="noreferrer">
            Platform demo <ArrowUpRight size={15} />
          </a>
          <a href="#pricing">Pricing</a>
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
          <p className="hero-prop">
            No upfront payment. Pay at UAT milestones.
            <sup aria-hidden="true">*</sup>
          </p>
          <p className="hero-prop-note">
            <sup>*</sup> Hours and scope are agreed ahead of time. Invoices at
            Autodev-defined UAT acceptance for that scoped work. Change orders
            are quoted before start.
          </p>
          <div className="hero-bottom">
            <p>
              Extraordinary engineers. Relentless AI automation.
              <br />
              We build ambitious software at a fraction of the cost.
              <br />
              100% On-shore team.
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
                    </span>
                  ))}
                </div>
                <div className="fleet-caption">
                  Configurable engineering pods. Built to scale.
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
        <section
          className="security wrap"
          id="security"
          aria-labelledby="security-title"
        >
          <div className="security-intro">
            <div>
              <span className="eyebrow">DATA SECURITY AND PRIVACY</span>
              <h2 id="security-title">
                Frontier AI.
                <br />A controlled environment.
              </h2>
            </div>
            <p>
              Our AI clean room approach keeps development focused on code and
              synthetic data. Real data access is a last resort, scoped with you
              when the work requires it.
            </p>
          </div>
          <figure className="clean-room" aria-labelledby="clean-room-caption">
            <figcaption id="clean-room-caption">
              <span>
                <LockKeyhole size={17} aria-hidden="true" /> AUTODEV / AI CLEAN
                ROOM
              </span>
              <span>Security architecture concept</span>
            </figcaption>
            <div className="clean-room-flow">
              <div className="security-node">
                <Database aria-hidden="true" />
                <span className="mono">01 / INPUT</span>
                <h3>Code + synthetic data</h3>
                <p>We generate the data needed to build and test.</p>
              </div>
              <ArrowRight className="security-arrow" aria-hidden="true" />
              <div className="security-node clean-room-core">
                <LockKeyhole aria-hidden="true" />
                <span className="mono">02 / BUILD</span>
                <h3>AI clean room</h3>
                <p>Engineer operators and configurable AI engineering pods.</p>
                <span className="security-tag">Code-focused development</span>
              </div>
              <ArrowRight className="security-arrow" aria-hidden="true" />
              <div className="security-node">
                <GitBranch aria-hidden="true" />
                <span className="mono">03 / DELIVER</span>
                <h3>Your GitHub. Your cloud.</h3>
                <p>
                  Delivery through GitHub, or a secure environment we provision
                  in your cloud. Any cloud.
                </p>
              </div>
            </div>
            <div className="security-modes">
              <div className="connected-mode">
                <div className="security-mode-heading">
                  <ShieldCheck size={20} aria-hidden="true" />
                  <h3>Controlled provider access</h3>
                </div>
                <div className="outbound-path">
                  <span>Outbound connections</span>
                  <ArrowRight size={17} aria-hidden="true" />
                  <span className="security-layers">
                    <ShieldCheck size={19} aria-hidden="true" /> Multiple
                    security layers
                  </span>
                  <ArrowRight size={17} aria-hidden="true" />
                  <span>
                    <Cloud size={19} aria-hidden="true" /> AI providers
                  </span>
                </div>
                <p>
                  Layered outbound controls designed to prevent sensitive
                  information from being shared with AI providers.
                </p>
              </div>
              <div className="airgap-mode">
                <div className="security-mode-heading">
                  <Unplug size={20} aria-hidden="true" />
                  <h3>100% air-gapped option</h3>
                </div>
                <p>
                  Local coding models inside your environment. No outbound AI
                  provider connections.
                </p>
                <span className="mono">LOCAL MODELS / OFFLINE EXECUTION</span>
              </div>
            </div>
          </figure>
        </section>
        <section
          className="pricing wrap"
          id="pricing"
          aria-labelledby="pricing-title"
        >
          <div className="pricing-intro">
            <span className="eyebrow">PRICING MODEL</span>
            <h2 id="pricing-title">
              A platform license.
              <br />A human advantage.
            </h2>
            <p>
              Software licenses and hourly engineering expertise, with AI
              subscriptions and extra token costs itemized in your quote.
            </p>
          </div>
          <div className="pricing-components">
            <article className="pricing-component">
              <span className="mono">01 / SOFTWARE LICENSE</span>
              <h3>Autodev platform</h3>
              <div className="license-price">
                <strong>$100</strong>
                <span>
                  per agent
                  <br />
                  per month
                </span>
              </div>
              <p>
                License the proprietary Autodev platform for the agents working
                on your project.
              </p>
            </article>
            <span className="pricing-plus" aria-label="plus">
              +
            </span>
            <article className="pricing-component">
              <span className="mono">02 / ENGINEER OPERATORS</span>
              <h3>100% onshore engineers</h3>
              <div className="operator-price">Low hourly rate</div>
              <p>
                Experienced engineers direct the work, operate the platform, and
                guide delivery.
              </p>
            </article>
          </div>
          <div className="quote-breakdown">
            <h3>Every quote, fully itemized.</h3>
            <dl>
              <div>
                <dt>Staff &amp; hours</dt>
                <dd>
                  Team roles, hourly rates, estimated hours, and staffing costs.
                </dd>
              </div>
              <div>
                <dt>Software costs</dt>
                <dd>
                  Agent count, license duration, and software costs at $100 per
                  agent per month.
                </dd>
              </div>
              <div>
                <dt>Extra token costs</dt>
                <dd>
                  Estimated additional AI token usage and its associated costs.
                </dd>
              </div>
              <div>
                <dt>AI subscriptions</dt>
                <dd>Required AI subscription plans, quantities, and costs.</dd>
              </div>
            </dl>
          </div>
          <div className="pricing-footer">
            <p>
              See the team, the platform, and the AI costs before work begins.
            </p>
            <a className="text-link" href="#quote">
              Request a quote <ArrowUpRight size={18} />
            </a>
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
                A new product. A critical platform. The&nbsp;backlog that never
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
        <Link className="wordmark" href="/" aria-label="autodev team home">
          <span className="brand-name">
            autodev{' '}
            <span className="brand-team">
              team<span className="brand-period">.</span>
            </span>
          </span>
        </Link>
        <span>Human × AI. Built for what’s next.</span>
        <span>© {new Date().getFullYear()} autodev team</span>
      </footer>
    </>
  );
}
