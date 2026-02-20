"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { fetchWhales } from "@/lib/api";
import { shortAddr, formatUSD } from "@/lib/utils";

/* ═══════════════════════════════════════════════════════════
   High Win Rate Whales Page
   ═══════════════════════════════════════════════════════════ */

export default function WhalesPage() {
    const [whales, setWhales] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchWhales({ limit: 50 })
            .then(setWhales)
            .catch(() => setWhales([]))
            .finally(() => setLoading(false));
    }, []);

    return (
        <>
            <div style={{ marginBottom: "var(--space-6)" }}>
                <h1 style={{ fontSize: "1.25rem", fontWeight: 700, color: "var(--text-main)", letterSpacing: "-0.01em" }}>
                    High Win Rate Wallets
                </h1>
                <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                    Top performing wallets by profit on large positions — likely skilled traders, not insiders
                </p>
            </div>

            {loading ? (
                <div style={{ padding: "var(--space-8)", textAlign: "center", color: "var(--text-muted)" }}>Loading data...</div>
            ) : !whales.length ? (
                <div className="panel" style={{ padding: "var(--space-12)", textAlign: "center" }}>
                    <div style={{ fontSize: "2rem", opacity: 0.3, marginBottom: "var(--space-4)" }}>🐋</div>
                    <div style={{ color: "var(--text-main)", fontWeight: 600 }}>No whales found yet</div>
                    <div style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
                        The system needs more scan cycles to identify high-performing wallets.
                    </div>
                </div>
            ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
                    {/* Header row */}
                    <div className="panel" style={{
                        display: "grid",
                        gridTemplateColumns: "2fr 1fr 1fr 1fr 1fr 1fr",
                        padding: "var(--space-3) var(--space-4)",
                        fontSize: "0.7rem",
                        textTransform: "uppercase",
                        color: "var(--text-muted)",
                        letterSpacing: "0.05em",
                        fontWeight: 600,
                    }}>
                        <span>Wallet</span>
                        <span style={{ textAlign: "right" }}>Win Rate</span>
                        <span style={{ textAlign: "right" }}>Profit</span>
                        <span style={{ textAlign: "right" }}>Volume</span>
                        <span style={{ textAlign: "right" }}>Trades</span>
                        <span style={{ textAlign: "right" }}>Risk</span>
                    </div>

                    {whales.map((w) => {
                        const winRate = w.win_rate || w.analysis?.win_rate || 0;
                        const profit = w.analysis?.total_profit ?? 0;
                        const profitColor = profit > 0 ? "var(--signal-success)" : profit < 0 ? "var(--signal-danger)" : "var(--text-muted)";
                        const winColor = winRate >= 0.7 ? "var(--signal-success)" : winRate >= 0.5 ? "var(--text-main)" : "var(--signal-danger)";

                        return (
                            <Link
                                key={w.address}
                                href={`/wallet/${w.address}`}
                                style={{ textDecoration: "none" }}
                            >
                                <div className="panel" style={{
                                    display: "grid",
                                    gridTemplateColumns: "2fr 1fr 1fr 1fr 1fr 1fr",
                                    padding: "var(--space-4)",
                                    alignItems: "center",
                                    cursor: "pointer",
                                    transition: "border-color 0.2s",
                                }}>
                                    <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                                        <span className="mono" style={{ color: "var(--brand-primary)", fontSize: "0.85rem", fontWeight: 600 }}>
                                            {w.username || shortAddr(w.address)}
                                        </span>
                                        {w.username && (
                                            <span className="mono" style={{ color: "var(--text-muted)", fontSize: "0.7rem" }}>
                                                {shortAddr(w.address)}
                                            </span>
                                        )}
                                    </div>

                                    <span className="mono" style={{ textAlign: "right", color: winColor, fontWeight: 700, fontSize: "0.9rem" }}>
                                        {(winRate * 100).toFixed(0)}%
                                    </span>

                                    <span className="mono" style={{ textAlign: "right", color: profitColor, fontWeight: 600 }}>
                                        {profit >= 0 ? "+" : ""}{formatUSD(profit)}
                                    </span>

                                    <span className="mono" style={{ textAlign: "right", color: "var(--text-main)" }}>
                                        {formatUSD(w.total_volume)}
                                    </span>

                                    <span className="mono" style={{ textAlign: "right", color: "var(--text-muted)" }}>
                                        {w.total_trades}
                                    </span>

                                    <span className="mono" style={{
                                        textAlign: "right",
                                        color: w.risk_score >= 50 ? "var(--signal-danger)" : w.risk_score >= 30 ? "var(--signal-warning, orange)" : "var(--text-muted)",
                                        fontWeight: w.risk_score >= 30 ? 700 : 400,
                                    }}>
                                        {w.risk_score?.toFixed(0) ?? "—"}
                                    </span>
                                </div>
                            </Link>
                        );
                    })}
                </div>
            )}
        </>
    );
}
