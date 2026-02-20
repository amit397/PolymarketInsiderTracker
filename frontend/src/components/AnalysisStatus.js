'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { shortAddr } from "@/lib/utils";

export default function AnalysisStatus() {
    const [status, setStatus] = useState(null);
    const [error, setError] = useState(false);
    const [visible, setVisible] = useState(false);

    useEffect(() => {
        const fetchStatus = async () => {
            try {
                const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";
                const res = await fetch(`${API_BASE}/api/monitor/status`);
                if (!res.ok) throw new Error('Failed to fetch status');
                const data = await res.json();
                setStatus(data);
                setError(false);

                // Show if doing anything other than "Idle" or if we have a wallet
                if (data.status !== "Idle" || data.current_wallet) {
                    setVisible(true);
                }
            } catch (err) {
                console.error(err);
                setError(true);
            }
        };

        const interval = setInterval(fetchStatus, 1000);
        fetchStatus();

        return () => clearInterval(interval);
    }, []);

    if (error || !status) return null;
    if (!visible && status.status === "Idle") return null;

    return (
        <div
            className={`panel agent-active`}
            style={{
                marginBottom: "var(--space-6)",
                display: "grid",
                gridTemplateColumns: "1fr auto 1fr",
                alignItems: "center",
                padding: "var(--space-4)",
                transition: "all 0.5s ease",
                opacity: visible ? 1 : 0,
                transform: visible ? "translateY(0)" : "translateY(-1rem)"
            }}
        >

            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-4)" }}>
                {/* Status Indicator */}
                <div style={{ position: "relative", width: "12px", height: "12px", display: "flex" }}>
                    <span style={{
                        position: "absolute",
                        width: "100%", height: "100%",
                        borderRadius: "50%",
                        background: "var(--signal-success)",
                        opacity: 0.75,
                        animation: "ping 1s cubic-bezier(0, 0, 0.2, 1) infinite"
                    }}></span>
                    <span style={{
                        position: "relative",
                        width: "12px", height: "12px",
                        borderRadius: "50%",
                        background: "var(--signal-success)"
                    }}></span>
                </div>

                <div>
                    <div className="mono" style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                        Agent Status
                    </div>
                    <div style={{ fontSize: "0.95rem", fontWeight: 600, color: "var(--text-main)" }}>
                        {status.status}
                    </div>
                </div>
            </div>

            {/* Current Wallet (Centered) */}
            <div style={{ justifySelf: "center", display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
                {status.current_wallet ? (
                    <>
                        <span className="mono" style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>TARGET:</span>
                        <Link
                            href={`/wallet/${status.current_wallet}`}
                            className="badge zinc hover-underline mono"
                            style={{
                                fontSize: "0.75rem",
                                display: "flex",
                                alignItems: "center",
                                gap: "4px",
                                textDecoration: "none",
                                color: "inherit",
                                cursor: "pointer"
                            }}
                            title="View Analysis"
                        >
                            {shortAddr(status.current_wallet)}
                        </Link>
                        <a
                            href={`https://polymarket.com/profile/${status.current_wallet}`}
                            target="_blank"
                            rel="noreferrer"
                            style={{ fontSize: "0.7rem", color: "var(--text-dim)", marginLeft: "4px" }}
                            title="View on Polymarket"
                        >
                            ↗
                        </a>
                    </>
                ) : (
                    <>
                        <span className="mono" style={{ fontSize: "0.7rem", color: "var(--text-dim)" }}>TARGET:</span>
                        <span className="mono animate-pulse" style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>SCANNING...</span>
                    </>
                )}
            </div>

            {/* Stats (Right Aligned) */}
            <div style={{ justifySelf: "end", textAlign: "right" }}>
                {status.stats && (status.stats.processed || status.stats.loop_cycle) && (
                    <>
                        <div className="mono" style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase" }}>
                            {status.stats.processed ? 'Progress' : 'Cycle'}
                        </div>
                        <div className="mono" style={{ fontSize: "0.9rem", color: "var(--brand-primary)" }}>
                            {status.stats.processed
                                ? `${status.stats.processed} / ${status.stats.total}`
                                : `#${status.stats.loop_cycle || 1}`
                            }
                        </div>
                    </>
                )}
            </div>

            <style jsx>{`
                @keyframes ping {
                    75%, 100% { transform: scale(2); opacity: 0; }
                }
                .hover-underline:hover {
                    text-decoration: underline;
                    border-color: var(--text-main);
                }
            `}</style>
        </div>
    );
}
