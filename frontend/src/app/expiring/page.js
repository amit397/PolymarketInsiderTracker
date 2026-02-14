"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { fetchExpiringMarkets } from "@/lib/api";
import { scoreClass, shortAddr, formatUSD, formatCountdown } from "@/lib/utils";

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
        { value: 72, label: "3 days" },
        { value: 168, label: "7 days" },
    ];

    return (
        <>
            <div className="section-header" style={{ marginBottom: "var(--space-6)" }}>
                <div>
                    <h1 className="section-title" style={{ fontSize: "1.5rem", fontWeight: 800, letterSpacing: "-0.03em" }}>
                        Expiring Markets
                    </h1>
                    <p className="section-subtitle">
                        Markets approaching resolution — highest risk window for insider activity
                    </p>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                    <span className="pulse-dot" />
                    <span style={{ fontSize: "0.82rem", color: "var(--accent-primary)", fontWeight: 600 }}>
                        Live
                    </span>
                </div>
            </div>

            <div className="horizon-group">
                {options.map((o) => (
                    <button
                        key={o.value}
                        className={`horizon-pill ${horizon === o.value ? "active" : ""}`}
                        onClick={() => setHorizon(o.value)}
                    >
                        {o.label}
                    </button>
                ))}
            </div>

            {loading ? (
                <div className="expiring-grid">
                    {[...Array(6)].map((_, i) => (
                        <div key={i} className="expiring-card" style={{ pointerEvents: "none" }}>
                            <div className="skeleton" style={{ width: "80%", height: 18 }} />
                            <div className="skeleton" style={{ width: "40%", height: 14 }} />
                            <div className="skeleton" style={{ width: "100%", height: 40 }} />
                        </div>
                    ))}
                </div>
            ) : !markets.length ? (
                <div className="empty-state">
                    <div className="empty-icon">⏳</div>
                    <div className="empty-title">No expiring markets found</div>
                    <div className="empty-desc">
                        No markets are resolving within this time window, or none have suspicious activity above the threshold.
                    </div>
                </div>
            ) : (
                <div className="expiring-grid">
                    {markets.map((m, i) => (
                        <div key={m.market_id || i} className="expiring-card">
                            <div className="expiring-header">
                                <span className="expiring-question">{m.question}</span>
                                <div className="expiring-countdown" style={
                                    m.hours_remaining < 12
                                        ? { animation: "pulse-ring 2s ease-out infinite", background: "var(--danger-soft)" }
                                        : m.hours_remaining < 48
                                            ? { background: "var(--warning-soft)", borderColor: "var(--warning-border)" }
                                            : {}
                                }>
                                    <span className="countdown-value" style={
                                        m.hours_remaining < 12
                                            ? { color: "var(--danger)" }
                                            : m.hours_remaining < 48
                                                ? { color: "var(--warning)" }
                                                : { color: "var(--text-secondary)" }
                                    }>
                                        {formatCountdown(m.hours_remaining)}
                                    </span>
                                    <span className="countdown-label">remaining</span>
                                </div>
                            </div>

                            <div className="expiring-stats">
                                <div className="expiring-stat">
                                    <span className="expiring-stat-label">Volume</span>
                                    <span className="expiring-stat-value">{formatUSD(m.volume)}</span>
                                </div>
                                <div className="expiring-stat">
                                    <span className="expiring-stat-label">Flags</span>
                                    <span className="expiring-stat-value" style={m.suspicious_trade_count > 0 ? { color: "var(--danger)" } : undefined}>
                                        {m.suspicious_trade_count}
                                    </span>
                                </div>
                                {m.top_suspicion_score > 0 && (
                                    <div className="expiring-stat">
                                        <span className="expiring-stat-label">Score</span>
                                        <span className={`score-badge ${scoreClass(m.top_suspicion_score)}`} style={{ fontSize: "0.78rem" }}>
                                            {m.top_suspicion_score.toFixed(1)}
                                        </span>
                                    </div>
                                )}
                            </div>

                            {m.flagged_wallets?.length > 0 && (
                                <div className="expiring-wallets">
                                    {m.flagged_wallets.map((w) => (
                                        <Link key={w} href={`/wallet/${w}`} className="wallet-chip">
                                            {shortAddr(w)}
                                        </Link>
                                    ))}
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </>
    );
}
