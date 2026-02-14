"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { fetchSuspiciousMarkets } from "@/lib/api";
import { scoreClass, formatUSD, formatNum } from "@/lib/utils";

export default function MarketsPage() {
    const [markets, setMarkets] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchSuspiciousMarkets()
            .then(setMarkets)
            .catch(() => setMarkets([]))
            .finally(() => setLoading(false));
    }, []);

    return (
        <>
            <div className="section-header" style={{ marginBottom: "var(--space-6)" }}>
                <div>
                    <h1 className="section-title" style={{ fontSize: "1.5rem", fontWeight: 800, letterSpacing: "-0.03em" }}>
                        Suspicious Markets
                    </h1>
                    <p className="section-subtitle">
                        Markets ranked by average suspicion score of their traders
                    </p>
                </div>
            </div>

            {loading ? (
                <div className="alert-list">
                    {[...Array(8)].map((_, i) => (
                        <div key={i} className="alert-row" style={{ pointerEvents: "none" }}>
                            <div className="skeleton" style={{ width: 36, height: 36 }} />
                            <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 6 }}>
                                <div className="skeleton skeleton-text" style={{ width: "60%" }} />
                                <div className="skeleton skeleton-text" style={{ width: "30%" }} />
                            </div>
                            <div className="skeleton" style={{ width: 52, height: 24, borderRadius: 9999 }} />
                        </div>
                    ))}
                </div>
            ) : !markets.length ? (
                <div className="empty-state">
                    <div className="empty-icon">📊</div>
                    <div className="empty-title">No suspicious markets yet</div>
                    <div className="empty-desc">
                        Run a scan from the dashboard to analyze market activity and detect suspicious patterns.
                    </div>
                    <Link href="/" className="btn btn-primary">Go to Dashboard</Link>
                </div>
            ) : (
                <div className="alert-list">
                    {markets.map((m, i) => (
                        <div key={m.market_id || i} className="alert-row" style={{ cursor: "default" }}>
                            <div className="alert-rank">{i + 1}</div>
                            <div className="alert-info">
                                <span className="alert-market">{m.question || "Unknown market"}</span>
                                <span style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
                                    {m.slug || m.market_id}
                                </span>
                            </div>
                            <div className="alert-meta">
                                <span className="alert-trade-size">
                                    {formatNum(m.alert_count)} alert{m.alert_count !== 1 ? "s" : ""}
                                </span>
                                {m.volume > 0 && (
                                    <span className="alert-time">{formatUSD(m.volume)}</span>
                                )}
                            </div>
                            <span className={`score-badge ${scoreClass(m.avg_suspicion_score)}`}>
                                {m.avg_suspicion_score?.toFixed(1)}
                            </span>
                        </div>
                    ))}
                </div>
            )}
        </>
    );
}
