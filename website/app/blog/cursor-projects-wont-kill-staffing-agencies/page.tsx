import type { Metadata } from "next";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";

const ARTICLE_HTML = "<p>Cursor\u2019s Projects launch is the right <em>shape</em>: one coordinator, a persistent thread, subagents that don\u2019t forget the plan. I ran the same shape years before it had a product name. I\u2019m an AI &amp; systems engineer, Autodev Team, Grok Bot Chief of Staff. Ex-FAANG. Pending US patents in AI. I run <strong>4</strong> Autodev Grok Bots \u2014 CoS, Research, Demand, Offer. CoS is the front door. It routes. It doesn\u2019t freelance.</p>\n      <p>Here\u2019s the part the launch thread won\u2019t say: a nicer coordinator does not kill the staffing agency. It just gives the agency a better IDE to mark up.</p>\n      <h2>AI mostly sucks</h2>\n      <p>I say this as someone whose entire working life is downstream of models. Most \u201cAI transformation\u201d is a slide. Most agent demos are a staffing brochure with a progress bar. The only people who consistently get leverage are engineers who already knew how to ship \u2014 architecture, contracts, taste, the willingness to throw work away.</p>\n      <p>If you\u2019re not that, Projects will help you open more chats. It will not make you a lab.</p>\n      <p>That\u2019s not a dunk on Cursor. It\u2019s a dunk on the industry that sold \u201cagents replace teams\u201d to the same buyers who used to buy \u201cwe\u2019ll staff you a pod in 48 hours.\u201d Different logo. Same cut.</p>\n      <h2>The middleman is the product</h2>\n      <p>Staffing agencies exist to sit between the company that needs software and the people who can write it. They take the spread. They rename \u201cengineer\u201d as \u201cresource.\u201d They sell hope and a bench.</p>\n      <p>SaaS agent platforms are learning the same trick: sell <em>seats</em>, not <em>ships</em>. You\u2019re not hiring capacity. You\u2019re renting a coordinator and hoping the subagents hallucinate a roadmap you can show your VP.</p>\n      <p>I built Autodev to delete that layer. Onshore, hybrid, human\u2013AI staff-aug. You buy elite hours and a platform that actually runs the SDLC \u2014 not a prompt window with a price list. No upfront theater. Hours and scope agreed ahead. Invoice at Autodev UAT for that scope. Change orders before start. Not pay-when-happy. Not free-forever discovery. Not open-ended T&amp;M.</p>\n      <p>If that sounds less magical than \u201c40 agents run your company,\u201d good. Magic is how agencies price.</p>\n      <h2>Coordinator \u2260 Chief of Staff</h2>\n      <p>Projects: one persistent thread, a coordinator, subagents, memory that syncs.</p>\n      <p>Autodev: four specialized Grok Bots, one CoS, owner-approved handoffs. A receipt is not proof they read it. The human still owns architecture. The bots execute inside contracts.</p>\n      <p>Same geometry. Different contract. One is a product seat. One is capacity you couldn\u2019t staff through a middleman without lighting the budget on fire.</p>\n      <p>I don\u2019t need Cursor to be wrong for Autodev to be right. I need buyers to stop confusing <em>an IDE that delegates</em> with <em>a team that ships</em>.</p>\n      <h2>Commoditize the expensive part</h2>\n      <p>The goal is not a prettier agency. The goal is to make frontier-quality build capacity cheap enough that the agency markup looks stupid. Commoditize the harness. Keep the scarce thing scarce: engineers with judgment.</p>\n      <p>If AI ever gets good enough that this essay is embarrassing, I\u2019ll take it. Until then, most of it sucks, engineers get the upside, and anyone charging you a staffing spread to wrap a coordinator should be out of the deal.</p>\n      <p>Want the scoped version, not the thread: <a href=\"https://autodev-team.com\">autodev-team.com</a>. Quote goes to <code>hello@autodev-team.com</code>.</p>";

export const metadata: Metadata = {
  title: "Cursor shipped Projects. Staffing agencies still take the cut. — autodev team",
  description:
    "Coordinator agents are a better IDE, not a replacement for elite onshore capacity. AI mostly sucks except for engineers. Kill the middlemen.",
  alternates: { canonical: "/blog/cursor-projects-wont-kill-staffing-agencies" },
  openGraph: {
    title: "Cursor shipped Projects. Staffing agencies still take the cut.",
    url: "/blog/cursor-projects-wont-kill-staffing-agencies",
    description:
      "Coordinator agents are a better IDE, not a replacement for elite onshore capacity.",
  },
};

export default function BlogPost() {
  return (
    <>
      <header className="site-header wrap">
        <Link href="/" className="wordmark" aria-label="autodev team home">
          <span className="brand-mark">a↗</span>
          <span className="brand-name">
            autodev{" "}
            <span className="brand-team">
              team<span className="brand-period">.</span>
            </span>
          </span>
        </Link>
        <nav aria-label="Main navigation">
          <Link href="/blog">Blog</Link>
          <a href="/#approach">Our approach</a>
          <a href="/demo/index.html?demo=1" target="_blank" rel="noreferrer">
            Platform demo <ArrowUpRight size={15} />
          </a>
          <a className="nav-quote" href="/#quote">
            Request a quote <ArrowUpRight size={15} />
          </a>
        </nav>
      </header>
      <main id="main" className="wrap" style={{ maxWidth: 720, paddingTop: 48, paddingBottom: 96 }}>
        <p style={{ opacity: 0.7, marginBottom: 12 }}>
          <Link href="/blog">Blog</Link> · Logan Robbins
        </p>
        <h1 style={{ fontSize: "2rem", lineHeight: 1.2, marginBottom: 24 }}>
          Cursor shipped Projects. Staffing agencies still take the cut.
        </h1>
        <article
          className="blog-prose"
          style={{ lineHeight: 1.65, display: "grid", gap: 16 }}
          dangerouslySetInnerHTML={{ __html: ARTICLE_HTML }}
        />
      </main>
    </>
  );
}
