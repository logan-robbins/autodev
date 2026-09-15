import type { Metadata } from "next";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";

export const metadata: Metadata = {
  title: "Blog — autodev team",
  description: "Notes on agents, staffing middlemen, and shipping with Autodev.",
  alternates: { canonical: "/blog" },
};

const posts: { slug: string; title: string; description: string }[] = [];

export default function BlogIndex() {
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
        <h1 style={{ fontSize: "2rem", marginBottom: 24 }}>Blog</h1>
        <ul style={{ listStyle: "none", padding: 0, display: "grid", gap: 20 }}>
          {posts.map((p) => (
            <li key={p.slug}>
              <Link href={`/blog/${p.slug}`} style={{ fontSize: "1.25rem", fontWeight: 600 }}>
                {p.title}
              </Link>
              <p style={{ opacity: 0.75, marginTop: 6 }}>{p.description}</p>
            </li>
          ))}
        </ul>
      </main>
    </>
  );
}
