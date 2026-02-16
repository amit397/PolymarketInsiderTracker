"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { fetchExpiringMarkets } from "@/lib/api";
import { shortAddr, formatUSD, formatCountdown } from "@/lib/utils";

/* ═══════════════════════════════════════════════════════════
   Expiring Markets Page
   Theme: Financial Terminal
   ═══════════════════════════════════════════════════════════ */

export default function ExpiringPage() {
    const [markets, setMarkets] = useState([]);
    const [loading, setLoading] = useState(true);
    const [horizon, setHorizon] = useState(168);

    useEffect(() => {
        setLoading(true);
        fetchExpiringMarkets({ hours: horizon, minScore: 0 })
            .then(setMarkets)
            .catch(() => setMarkets([]))
            .finally(() => setLoading(false));
    }, [horizon]);

    const options = [
        { value: 24, label: "24h" },
        { value: 48, label: "48h" },
        { value: 72, label: "3d" },
        { value: 168, label: "7d" },
    ];

    return (
        <>
            <div style={{ marginBottom: "var(--space-6)" }}>
                <h1 style={{ fontSize: "1.25rem", fontWeight: 700, color: "var(--text-main)", letterSpacing: "-0.01em" }}>
                    Expiring Windows
                </h1>
                <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                    High-volatility windows approaching market resolution
                </p>
            </div>

            <div style={{ marginBottom: "var(--space-6)", display: "flex", gap: "var(--space-2)" }}>
                {options.map((o) => (
                    <button
                        key={o.value}
                        className={`btn ${horizon === o.value ? "btn-primary" : "btn-outline"}`}
                        onClick={() => setHorizon(o.value)}
                        style={{ padding: "4px 12px", fontSize: "0.75rem", minWidth: "48px" }}
                    >
                        {o.label}
                    </button>
                ))}
            </div>

            {loading ? (
                <div style={{ padding: "var(--space-8)", textAlign: "center", color: "var(--text-muted)" }}>Loading data...</div>
            ) : !markets.length ? (
                <div className="panel" style={{ padding: "var(--space-12)", textAlign: "center" }}>
                    <div style={{ fontSize: "2rem", opacity: 0.3, marginBottom: "var(--space-4)" }}>⏳</div>
                    <div style={{ color: "var(--text-main)", fontWeight: 600 }}>No active expiries</div>
                    <div style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
                        No suspicious markets found resolving within {horizon} hours.
                    </div>
                </div>
            ) : (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: "var(--space-4)" }}>
                    {markets.map((m, i) => {
                        const timeLeft = m.hours_remaining;
                        const isExpired = timeLeft <= 0;
                        const timeLabel = formatCountdown(timeLeft);

                        // Urgency colors
                        const urgency = timeLeft < 24 ? "critical" : timeLeft < 72 ? "high" : "medium";
                        const badgeColor = urgency === "critical" ? "red" : urgency === "high" ? "amber" : "zinc";

                        return (
                            <div key={m.market_id || i} className="panel">
                                <div className="panel-header" style={{ padding: "var(--space-4)", paddingBottom: 0, borderBottom: "none", display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                                    {!isExpired ? (
                                        <span className={`badge ${badgeColor}`}>
                                            {timeLabel} Left
                                        </span>
                                    ) : <span />} {/* Spacer if no badge, or just nothing */}

                                    {m.top_suspicion_score > 0 && (
                                        <span className="mono" style={{ color: "var(--signal-danger)", fontWeight: 700 }}>
                                            {m.top_suspicion_score.toFixed(1)}
                                        </span>
                                    )}
                                </div>

                                <div className="panel-body" style={{ padding: "var(--space-4)" }}>
                                    <a
                                        href={`https://polymarket.com/event/${m.event_slug || m.slug}`}
                                        target="_blank"
                                        rel="noreferrer"
                                        style={{
                                            display: "block",
                                            height: "3.2em", overflow: "hidden",
                                            marginBottom: "var(--space-4)",
                                            fontWeight: 600, fontSize: "0.95rem", lineHeight: "1.4",
                                            color: "var(--text-main)"
                                        }}
                                        className="hover-underline"
                                    >
                                        {m.question}
                                    </a>

                                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-4)", marginBottom: "var(--space-4)" }}>
                                        <div style={{ display: "flex", flexDirection: "column" }}>
                                            <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Volume</span>
                                            <span className="mono" style={{ color: "var(--text-main)" }}>{formatUSD(m.volume)}</span>
                                        </div>
                                        <div style={{ display: "flex", flexDirection: "column" }}>
                                            <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Flags</span>
                                            <span className="mono" style={{ color: m.suspicious_trade_count > 0 ? "var(--signal-danger)" : "var(--text-main)" }}>
                                                {m.suspicious_trade_count}
                                            </span>
                                        </div>
                                    </div>

                                    {m.flagged_wallets?.length > 0 && (
                                        <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-2)", borderTop: "1px solid var(--border-dim)", paddingTop: "var(--space-3)" }}>
                                            {m.flagged_wallets.map((w) => (
                                                <Link key={w} href={`/wallet/${w}`} style={{
                                                    fontSize: "0.7rem",
                                                    fontFamily: "var(--font-mono)",
                                                    color: "var(--brand-primary)",
                                                    background: "var(--brand-glow)",
                                                    padding: "2px 6px",
                                                    borderRadius: "var(--radius-sm)"
                                                }}>
                                                    {shortAddr(w)}
                                                </Link>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </>
    );
}
