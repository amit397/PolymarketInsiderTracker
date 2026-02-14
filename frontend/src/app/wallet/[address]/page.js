"use client";

import { useEffect, useState, use } from "react";
import Link from "next/link";
import { fetchWallet } from "@/lib/api";
import {
    scoreClass,
    shortAddr,
    formatNum,
    formatUSD,
    timeAgo,
    FACTOR_LABELS,
} from "@/lib/utils";

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
        return (
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
                <div className="skeleton" style={{ width: "50%", height: 32 }} />
                <div className="skeleton" style={{ width: "30%", height: 18 }} />
                <div className="stats-grid">
                    {[...Array(4)].map((_, i) => (
                        <div key={i} className="stat-card"><div className="skeleton skeleton-stat" /></div>
                    ))}
                </div>
            </div>
        );
    }

    if (!wallet) {
        return (
            <div className="empty-state">
                <div className="empty-icon">🔍</div>
                <div className="empty-title">Wallet not found</div>
                <div className="empty-desc">
                    This address hasn&apos;t been scanned yet. Try running a scan first.
                </div>
                <Link href="/" className="btn btn-ghost">Back to Dashboard</Link>
            </div>
        );
    }

    const topScore = wallet.alerts?.length
        ? Math.max(...wallet.alerts.map((a) => a.suspicion_score || 0))
        : 0;

    return (
        <>
            {/* ── Breadcrumb ── */}
            <div style={{ marginBottom: "var(--space-4)" }}>
                <Link href="/" className="nav-link" style={{ display: "inline-flex", padding: 0 }}>
                    ← Dashboard
                </Link>
            </div>

            {/* ── Header ── */}
            <div className="wallet-header">
                <div className="wallet-avatar">
                    {(wallet.username || wallet.address)?.[0]?.toUpperCase() || "?"}
                </div>
                <div className="wallet-title">
                    <h1 className="wallet-name">{wallet.username || shortAddr(wallet.address)}</h1>
                    <span className="wallet-address">{wallet.address}</span>
                </div>
                {topScore > 0 && (
                    <span className={`score-badge ${scoreClass(topScore)}`} style={{ fontSize: "1rem", padding: "6px 16px" }}>
                        {topScore.toFixed(1)}
                    </span>
                )}
            </div>

            {/* ── Meta ── */}
            <div className="wallet-meta-grid">
                <div className="stat-card">
                    <span className="stat-label">Total Trades</span>
                    <span className="stat-value">{formatNum(wallet.total_trades)}</span>
                </div>
                <div className="stat-card">
                    <span className="stat-label">Total Volume</span>
                    <span className="stat-value">{formatUSD(wallet.total_volume)}</span>
                </div>
                <div className="stat-card">
                    <span className="stat-label">Alerts</span>
                    <span className="stat-value" style={{ color: wallet.alerts?.length ? "var(--danger)" : "inherit" }}>
                        {formatNum(wallet.alerts?.length || 0)}
                    </span>
                </div>
                <div className="stat-card">
                    <span className="stat-label">Categories</span>
                    <span className="stat-value">{formatNum(Object.keys(wallet.categories || {}).length)}</span>
                </div>
            </div>

            {/* ── Alerts ── */}
            {wallet.alerts?.length > 0 && (
                <>
                    <div className="section-header">
                        <h2 className="section-title">Suspicious Activity</h2>
                        <span className="section-subtitle">{wallet.alerts.length} alert{wallet.alerts.length !== 1 ? "s" : ""}</span>
                    </div>

                    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
                        {wallet.alerts.map((a, i) => (
                            <div key={a.id || i} className="card">
                                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "var(--space-4)" }}>
                                    <div>
                                        <div style={{ fontWeight: 600, marginBottom: 4 }}>
                                            {a.market_question || "Unknown market"}
                                        </div>
                                        <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                                            {a.trade_side === "BUY" ? "▲ Bought" : "▼ Sold"} {formatUSD(a.trade_size)} · {timeAgo(a.created_at)}
                                        </div>
                                    </div>
                                    <span className={`score-badge ${scoreClass(a.suspicion_score)}`}>
                                        {a.suspicion_score?.toFixed(1)}
                                    </span>
                                </div>

                                {/* Factor bars */}
                                {a.factors && (
                                    <div className="factor-breakdown">
                                        {Object.entries(FACTOR_LABELS).map(([key, label]) => {
                                            const val = a.factors[key] ?? 0;
                                            const isElevated = a.factors.elevated_factors?.includes(key);
                                            return (
                                                <div className="factor-row" key={key}>
                                                    <span className="factor-label" style={isElevated ? { color: "var(--accent-primary)", fontWeight: 600 } : undefined}>
                                                        {label}
                                                        {isElevated && " ●"}
                                                    </span>
                                                    <div className="factor-bar-track">
                                                        <div
                                                            className="factor-bar-fill"
                                                            style={{
                                                                width: `${Math.round(val * 100)}%`,
                                                                background: isElevated ? "var(--accent-gradient)" : "var(--bg-elevated)",
                                                            }}
                                                        />
                                                    </div>
                                                    <span className="factor-value">{(val * 100).toFixed(0)}%</span>
                                                </div>
                                            );
                                        })}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                </>
            )}
        </>
    );
}
