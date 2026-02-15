"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { fetchSuspiciousMarkets } from "@/lib/api";
import { formatUSD, formatNum } from "@/lib/utils";

/* ═══════════════════════════════════════════════════════════
   Suspicious Markets Page
   Theme: Financial Intelligence
   ═══════════════════════════════════════════════════════════ */

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
            <div style={{ marginBottom: "var(--space-6)" }}>
                <h1 style={{ fontSize: "1.25rem", fontWeight: 700, color: "var(--text-main)", letterSpacing: "-0.01em" }}>
                    Market Intelligence
                </h1>
                <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                    Markets ranked by composite suspicion score
                </p>
            </div>

            {loading ? (
                <div style={{ padding: "var(--space-8)", textAlign: "center", color: "var(--text-muted)" }}>Loading market data...</div>
            ) : !markets.length ? (
                <div className="panel" style={{ padding: "var(--space-12)", textAlign: "center" }}>
                    <div style={{ fontSize: "2rem", opacity: 0.3, marginBottom: "var(--space-4)" }}>📊</div>
                    <div style={{ color: "var(--text-main)", fontWeight: 600 }}>No data available</div>
                    <div style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginBottom: "var(--space-6)" }}>
                        Run a scan from the dashboard to populate market intelligence.
                    </div>
                    <Link href="/" className="btn btn-primary">Go to Monitor</Link>
                </div>
            ) : (
                <div className="feed-container">
                    {markets.map((m, i) => {
                        const score = m.avg_suspicion_score || 0;
                        const severity = score > 75 ? "critical" : score > 50 ? "high" : "medium";

                        return (
                            <div key={m.market_id || i} className={`alert-item ${severity}`}>
                                <div className="alert-rank">#{i + 1}</div>
                                <div className="alert-main">
                                    <span className="alert-title">{m.question || "Unknown Market"}</span>
                                    <div className="alert-meta">
                                        <span className="meta-tag mono" style={{ color: "var(--text-dim)" }}>
                                            ID: {m.market_id?.slice(0, 8)}...
                                        </span>
                                        <span className="meta-tag">
                                            Vol: {formatUSD(m.volume)}
                                        </span>
                                        <span className="meta-tag">
                                            {formatNum(m.alert_count)} Alert{m.alert_count !== 1 ? "s" : ""}
                                        </span>
                                    </div>
                                </div>
                                <div className="alert-metrics">
                                    <span className="metric-value">{score.toFixed(1)}</span>
                                    <span className="metric-label">Avg Score</span>
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </>
    );
}
