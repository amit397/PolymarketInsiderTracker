"use client";

import Link from "next/link";
import { FACTOR_LABELS } from "@/lib/utils";

/* ═══════════════════════════════════════════════════════════
   About / Methodology Page
   ═══════════════════════════════════════════════════════════ */

export default function AboutPage() {
    return (
        <div style={{ maxWidth: "800px", margin: "0 auto", paddingBottom: "var(--space-12)" }}>
            <div style={{ marginBottom: "var(--space-8)" }}>
                <h1 className="display" style={{ fontSize: "2.5rem", fontWeight: 700, color: "var(--text-main)", lineHeight: 1.1 }}>
                    Methodology
                </h1>
                <p className="mono" style={{ fontSize: "0.9rem", color: "var(--text-muted)", marginTop: "var(--space-2)" }}>
                    How we identify "Smart Money" and potential insider trading on Polymarket
                </p>
            </div>

            <div className="panel" style={{ padding: "var(--space-6)", marginBottom: "var(--space-6)" }}>
                <h2 style={{ fontSize: "1.2rem", fontWeight: 600, color: "var(--text-main)", marginBottom: "var(--space-4)" }}>
                    The Goal
                </h2>
                <p style={{ color: "var(--text-muted)", lineHeight: 1.6, fontSize: "0.9rem", marginBottom: "var(--space-4)" }}>
                    Polymarket Insider Tracker scans the blockchain and Polymarket order books to identify wallets that exhibit highly abnormal, profitable, and specifically timed trading patterns.
                </p>
                <p style={{ color: "var(--text-muted)", lineHeight: 1.6, fontSize: "0.9rem" }}>
                    We separate these wallets into two groups: <strong>High Win Rate Whales</strong> (skilled traders with high volume and profit) and <strong>Possible Insiders</strong> (wallets making massive, uncharacteristic bets right before a market resolves).
                </p>
            </div>

            <div style={{ marginBottom: "var(--space-6)" }}>
                <h2 style={{ fontSize: "1.2rem", fontWeight: 600, color: "var(--text-main)", marginBottom: "var(--space-4)" }}>
                    Risk Score Factors
                </h2>
                <p style={{ color: "var(--text-muted)", lineHeight: 1.6, fontSize: "0.9rem", marginBottom: "var(--space-6)" }}>
                    Every wallet analyzed receives a <strong>Suspicion Score (0–100)</strong> computed from a weighted average of several behavioral signals. A score above 50 flags the wallet on the Live Feed.
                </p>

                <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "var(--space-4)" }}>
                    <FactorCard
                        title={FACTOR_LABELS.f_fresh}
                        weight="20%"
                        desc="Wallets created very recently (e.g., within the last 7 days) and immediately depositing large sums of USDC to bet on a single outcome."
                    />
                    <FactorCard
                        title={FACTOR_LABELS.f_concentration}
                        weight="20%"
                        desc="Wallets that do not diversify. If 90%+ of a wallet's capital is deployed into a single market or related group of markets, it indicates extreme confidence."
                    />
                    <FactorCard
                        title={FACTOR_LABELS.f_position}
                        weight="20%"
                        desc="Position size relative to the market's total liquidity. If a wallet's single trade makes up a significant percentage of the entire market volume, it is flagged."
                    />
                    <FactorCard
                        title={FACTOR_LABELS.f_timing}
                        weight="20%"
                        desc="Trades placed suspiciously close (within 24-48 hours) to the market's resolution or a major news catalyst."
                    />
                    <FactorCard
                        title={FACTOR_LABELS.f_edge}
                        weight="20%"
                        desc="Comparing the wallet's average entry price against the current market price or resolution price. If the wallet consistently beats the market average on execution, they have an edge."
                    />
                </div>
            </div>

            <div className="panel" style={{ padding: "var(--space-6)" }}>
                <h2 style={{ fontSize: "1.2rem", fontWeight: 600, color: "var(--signal-warning)", marginBottom: "var(--space-4)" }}>
                    Disclaimer
                </h2>
                <p style={{ color: "var(--text-muted)", lineHeight: 1.6, fontSize: "0.85rem" }}>
                    This tool is for educational and research purposes only. "Suspicion Score" is a mathematical heuristic, not an accusation of insider activity. Many highly profitable wallets belong to algorithmic trading firms, market makers, or exceptionally well-informed researchers. Always do your own research before counter-trading or copying identified wallets.
                </p>
            </div>

            <div style={{ marginTop: "var(--space-8)", textAlign: "center" }}>
                <Link href="/" className="btn btn-outline">
                    ← RETURn TO DASHBOARD
                </Link>
            </div>
        </div>
    );
}

function FactorCard({ title, weight, desc }) {
    return (
        <div className="panel" style={{ padding: "var(--space-4)", display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span className="mono" style={{ color: "var(--text-main)", fontWeight: 600, fontSize: "0.9rem" }}>{title}</span>
                <span className="badge" style={{ fontSize: "0.7rem", color: "var(--brand-primary)", borderColor: "var(--brand-primary)" }}>
                    {weight} WEIGHT
                </span>
            </div>
            <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", lineHeight: 1.5 }}>
                {desc}
            </p>
        </div>
    );
}
