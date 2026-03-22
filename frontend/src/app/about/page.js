"use client";

import Link from "next/link";
import { FactorCard } from "@/lib/utils";

const FACTORS = [
  {
    title: "Win Rate Anomaly",
    weight: "15%",
    desc: "Measures whether a wallet is delivering unusually strong outcomes on resolved markets after discounting tiny sample sizes.",
  },
  {
    title: "Bet Concentration",
    weight: "15%",
    desc: "Captures how much of a wallet&apos;s deployed capital clusters into a single market rather than a diversified book.",
  },
  {
    title: "Timing Signal",
    weight: "10%",
    desc: "Looks for entries that land unusually close to market resolution, when information edges matter most.",
  },
  {
    title: "Entry Price Edge",
    weight: "15%",
    desc: "Rewards wallets that repeatedly buy winning outcomes at prices the market later proves too cheap.",
  },
  {
    title: "Account Pattern",
    weight: "20%",
    desc: "Combines wallet age, diversification, and concentration to detect fresh single-purpose account behavior.",
  },
  {
    title: "Position Size Signal",
    weight: "25%",
    desc: "Flags large low-odds positions where conviction and sizing are both outliers relative to normal market behavior.",
  },
];

export default function AboutPage() {
  return (
    <div style={{ maxWidth: 880, margin: "0 auto", paddingBottom: "var(--space-12)" }}>
      <div className="hero-shell" style={{ marginBottom: "var(--space-8)" }}>
        <div>
          <div className="hero-kicker mono">Methodology</div>
          <h1 className="display hero-title" style={{ fontSize: "2.4rem" }}>Canonical six-factor risk engine</h1>
          <p className="hero-subtitle">
            The UI, backend, and product copy now describe the same scoring model so suspicious-wallet review is easier to trust.
          </p>
        </div>
      </div>

      <div className="panel" style={{ padding: "var(--space-6)", marginBottom: "var(--space-6)" }}>
        <h2 style={{ fontSize: "1.1rem", marginBottom: "var(--space-3)" }}>What the score means</h2>
        <p style={{ color: "var(--text-muted)", lineHeight: 1.7, fontSize: "0.9rem", marginBottom: "var(--space-3)" }}>
          Every wallet receives a risk score from 0 to 100. The score is a behavioral heuristic, not an accusation. High scores indicate that multiple signals line up at once: unusual sizing, unusual timing, concentrated positioning, and suspicious account behavior.
        </p>
        <p style={{ color: "var(--text-muted)", lineHeight: 1.7, fontSize: "0.9rem" }}>
          A conservative wallet-age filter also reduces false positives for established accounts unless the underlying evidence is already extremely strong.
        </p>
      </div>

      <div style={{ display: "grid", gap: "var(--space-4)", marginBottom: "var(--space-6)" }}>
        {FACTORS.map((factor) => (
          <FactorCard key={factor.title} title={factor.title} weight={factor.weight} desc={factor.desc} />
        ))}
      </div>

      <div className="panel" style={{ padding: "var(--space-6)", marginBottom: "var(--space-6)" }}>
        <h2 style={{ fontSize: "1.1rem", marginBottom: "var(--space-3)" }}>Product surfaces</h2>
        <ul style={{ margin: 0, paddingLeft: "1.2rem", display: "grid", gap: "0.4rem", color: "var(--text-muted)", fontSize: "0.88rem" }}>
          <li><strong>Insiders:</strong> suspicious wallets, alerts, and explainable factor breakdowns.</li>
          <li><strong>Whales:</strong> profitable lower-risk traders ranked for discovery and local follow lists.</li>
          <li><strong>Persistence:</strong> local SQLite plus JSON export/import, with a future remote adapter path for Supabase.</li>
        </ul>
      </div>

      <div className="panel" style={{ padding: "var(--space-6)" }}>
        <h2 style={{ fontSize: "1.1rem", color: "var(--signal-warning)", marginBottom: "var(--space-3)" }}>Disclaimer</h2>
        <p style={{ color: "var(--text-muted)", lineHeight: 1.7, fontSize: "0.88rem" }}>
          This tool is for research and education. A high risk score means a wallet deserves closer inspection, not that it committed wrongdoing. Many successful accounts belong to market makers, quantitative traders, or researchers with a legitimate edge.
        </p>
      </div>

      <div style={{ marginTop: "var(--space-8)", textAlign: "center" }}>
        <Link href="/" className="btn btn-outline">
          ← Return to dashboard
        </Link>
      </div>
    </div>
  );
}
