"use client";

import { useEffect, useState, use } from "react";
import Link from "next/link";
import { fetchWallet } from "@/lib/api";
import {
    formatNum,
    formatUSD,
    timeAgo,
    FACTOR_LABELS,
} from "@/lib/utils";

/* ═══════════════════════════════════════════════════════════
   Wallet Profile Page
   Theme: Financial Intelligence
   ═══════════════════════════════════════════════════════════ */

export default function WalletPage({ params }) {
    const { address } = use(params);
    const [wallet, setWallet] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchWallet(address)
            .then(setWallet)
            .catch(() => { })
            .finally(() => setLoading(false));
    }, [address]);

    if (loading) {
        return <div style={{ padding: "var(--space-8)", textAlign: "center", color: "var(--text-muted)" }}>Loading wallet profile...</div>;
    }

    if (!wallet) {
        return (
            <div className="panel" style={{ padding: "var(--space-12)", textAlign: "center" }}>
                <div style={{ fontSize: "2rem", opacity: 0.3, marginBottom: "var(--space-4)" }}>🔍</div>
                <div style={{ color: "var(--text-main)", fontWeight: 600 }}>Wallet not found</div>
                <div style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginBottom: "var(--space-6)" }}>
                    This address hasn&apos;t been flagged in recent scans.
                </div>
                <Link href="/" className="btn btn-primary">Return to Monitor</Link>
            </div>
        );
    }

    const topScore = wallet.alerts?.length
        ? Math.max(...wallet.alerts.map((a) => a.suspicion_score || 0))
        : 0;

    const severity = topScore > 75 ? "critical" : topScore > 50 ? "high" : "medium";
    const badgeColor = severity === "critical" ? "red" : severity === "high" ? "amber" : "zinc";

    return (
        <>
            {/* ── Breadcrumb ── */}
            <div style={{ marginBottom: "var(--space-4)" }}>
                <Link href="/" className="btn btn-outline" style={{ display: "inline-flex", padding: "4px 8px", fontSize: "0.75rem" }}>
                    ← Back to Monitor
                </Link>
            </div>

            {/* ── Header ── */}
            <div className="panel" style={{ padding: "var(--space-6)", marginBottom: "var(--space-6)" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "var(--space-4)" }}>
                    <div style={{
                        width: 64, height: 64,
                        background: "linear-gradient(135deg, var(--bg-surface), var(--bg-highlight))",
                        borderRadius: "var(--radius-lg)",
                        display: "flex", alignItems: "center", justifyContent: "center",
                        fontSize: "1.5rem", fontWeight: 700, color: "var(--text-main)",
                        border: "1px solid var(--border-mid)"
                    }}>
                        {(wallet.username || wallet.address)?.[0]?.toUpperCase()}
                    </div>

                    <div style={{ flex: 1 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
                            <h1 style={{ fontSize: "1.25rem", fontWeight: 700, color: "var(--text-main)" }}>
                                {wallet.username || "Unknown Entity"}
                            </h1>
                            {topScore > 0 && (
                                <span className={`badge ${badgeColor}`}>
                                    Risk Score: {topScore.toFixed(1)}
                                </span>
                            )}
                        </div>
                        <div className="mono" style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginTop: 4 }}>
                            {wallet.address}
                        </div>
                    </div>
                </div>
            </div>

            {/* ── Stats ── */}
            <div className="stats-grid">
                <StatCard label="Total Trades" value={formatNum(wallet.total_trades)} />
                <StatCard label="Volume Traded" value={formatUSD(wallet.total_volume)} />
                <StatCard label="Flagged Alerts" value={formatNum(wallet.alerts?.length)} highlight={wallet.alerts?.length > 0} />
                <StatCard label="Win Rate" value={(wallet.win_rate || 0).toFixed(0) + "%"} highlight={wallet.win_rate > 80} />
                <StatCard label="Market Focus" value={Object.keys(wallet.categories || {}).length + " Topics"} />
            </div>

            {/* ── Activity Feed ── */}
            <div>
                <h2 style={{ fontSize: "1rem", fontWeight: 600, color: "var(--text-main)", marginBottom: "var(--space-4)" }}>
                    Suspicious Activity Log
                </h2>

                {!wallet.alerts?.length ? (
                    <div className="panel" style={{ padding: "var(--space-8)", color: "var(--text-muted)", fontSize: "0.85rem" }}>
                        No suspicious activity recorded for this wallet.
                    </div>
                ) : (
                    <div className="feed-container">
                        {wallet.alerts.map((a, i) => {
                            const score = a.suspicion_score || 0;
                            const sev = score > 75 ? "critical" : score > 50 ? "high" : "medium";

                            return (
                                <div key={a.id || i} className={`alert-item ${sev}`}>
                                    <div className="alert-rank">#{i + 1}</div>
                                    <div className="alert-main">
                                        <div className="alert-title">{a.market_question}</div>
                                        <div className="alert-meta">
                                            <span className="meta-tag">
                                                {a.trade_side === "BUY" ? "▲ Buy" : "▼ Sell"} {formatUSD(a.trade_size)}
                                            </span>
                                            <span className="meta-tag">
                                                {timeAgo(a.created_at)}
                                            </span>
                                        </div>

                                        {/* Factors Grid */}
                                        {a.factors && (
                                            <div style={{ marginTop: "var(--space-3)", display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))", gap: "var(--space-2)" }}>
                                                {Object.entries(FACTOR_LABELS).map(([key, label]) => {
                                                    const val = a.factors[key] ?? 0;
                                                    if (val < 0.3) return null; // Only show relevant factors
                                                    return (
                                                        <div key={key} style={{ fontSize: "0.7rem" }}>
                                                            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
                                                                <span style={{ color: "var(--text-muted)" }}>{label}</span>
                                                                <span className="mono" style={{ color: "var(--text-main)" }}>{(val * 100).toFixed(0)}%</span>
                                                            </div>
                                                            <div className="micro-bar-track">
                                                                <div className="micro-bar-fill" style={{ width: `${val * 100}%`, background: val > 0.7 ? "var(--signal-warning)" : "var(--text-muted)" }} />
                                                            </div>
                                                        </div>
                                                    )
                                                })}
                                            </div>
                                        )}
                                    </div>

                                    <div className="alert-metrics">
                                        <span className="metric-value">{score.toFixed(1)}</span>
                                    </div>
                                </div>
                            )
                        })}
                    </div>
                )}
            </div>
        </>
    );
}

function StatCard({ label, value, highlight }) {
    return (
        <div className="stat-card" style={highlight ? { borderColor: "var(--border-mid)" } : {}}>
            <span className="stat-label">{label}</span>
            <span className="stat-value" style={highlight ? { color: "var(--signal-danger)" } : {}}>
                {value}
            </span>
        </div>
    );
}
