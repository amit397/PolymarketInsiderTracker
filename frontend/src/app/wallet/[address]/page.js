"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { fetchWallet } from "@/lib/api";
import { explainFactors } from "@/lib/intelligence";
import { FACTOR_LABELS, formatNum, formatPercent, formatUSD, timeAgo } from "@/lib/utils";

export default function WalletPage({ params }) {
  const { address } = use(params);
  const [wallet, setWallet] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let ignore = false;

    async function loadWallet() {
      try {
        const nextWallet = await fetchWallet(address);
        if (!ignore) {
          setWallet(nextWallet);
        }
      } catch {
        if (!ignore) {
          setWallet(null);
        }
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    }

    void loadWallet();
    return () => {
      ignore = true;
    };
  }, [address]);

  if (loading) {
    return <div style={{ padding: "var(--space-8)", textAlign: "center", color: "var(--text-muted)" }}>Loading wallet profile…</div>;
  }

  if (!wallet) {
    return (
      <div className="panel" style={{ padding: "var(--space-12)", textAlign: "center" }}>
        <div style={{ fontSize: "2rem", opacity: 0.3, marginBottom: "var(--space-4)" }}>🔍</div>
        <div style={{ color: "var(--text-main)", fontWeight: 600 }}>Wallet not found</div>
        <div style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginBottom: "var(--space-6)" }}>
          This address has not appeared in recent stored analysis.
        </div>
        <Link href="/" className="btn btn-primary">Return to monitor</Link>
      </div>
    );
  }

  const topScore = wallet.alerts?.length ? Math.max(...wallet.alerts.map((alert) => alert.suspicion_score || 0)) : wallet.risk_score || 0;

  return (
    <>
      <div style={{ marginBottom: "var(--space-4)" }}>
        <Link href="/" className="btn btn-outline" style={{ display: "inline-flex", padding: "4px 8px", fontSize: "0.75rem" }}>
          ← Back to monitor
        </Link>
      </div>

      <div className="panel" style={{ padding: "var(--space-6)", marginBottom: "var(--space-6)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-4)", flexWrap: "wrap" }}>
          <div style={{ width: 64, height: 64, background: "linear-gradient(135deg, var(--bg-surface), var(--bg-highlight))", borderRadius: "var(--radius-lg)", display: "grid", placeItems: "center", fontSize: "1.5rem", fontWeight: 700, border: "1px solid var(--border-mid)" }}>
            {(wallet.username || wallet.address)?.[0]?.toUpperCase()}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", flexWrap: "wrap" }}>
              <h1 style={{ fontSize: "1.3rem", fontWeight: 700 }}>{wallet.username || "Unknown entity"}</h1>
              <span className="badge zinc">{wallet.score_label}</span>
              <span className="badge" style={{ color: "var(--signal-danger)", border: "1px solid var(--signal-danger)" }}>Risk {topScore.toFixed(1)}</span>
            </div>
            <div className="mono" style={{ color: "var(--text-muted)", fontSize: "0.82rem", marginTop: 4 }}>{wallet.address}</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginTop: "var(--space-3)" }}>
              {(wallet.why_flagged?.length ? wallet.why_flagged : explainFactors(wallet.analysis?.factors, 4)).map((reason) => (
                <span key={reason} className="badge zinc">{reason}</span>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="stats-grid">
        <StatCard label="Total trades" value={formatNum(wallet.total_trades)} />
        <StatCard label="Volume traded" value={formatUSD(wallet.total_volume)} />
        <StatCard label="Win rate" value={formatPercent(wallet.win_rate, 0)} highlight={wallet.win_rate > 70} />
        <StatCard label="Total PnL" value={formatUSD(wallet.total_pnl || wallet.total_profit)} highlight={wallet.total_pnl > 0} />
        <StatCard label="Resolved markets" value={formatNum(wallet.resolved_markets_count || 0)} />
      </div>

      <div className="panel" style={{ padding: "var(--space-6)", marginBottom: "var(--space-6)" }}>
        <h2 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "var(--space-4)" }}>Factor breakdown</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "var(--space-4)" }}>
          {Object.entries(FACTOR_LABELS).map(([key, label]) => {
            const value = wallet.analysis?.factors?.[key] ?? 0;
            return (
              <div key={key} className="panel" style={{ padding: "var(--space-4)", background: "var(--bg-surface)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "var(--space-2)", gap: "var(--space-2)" }}>
                  <span style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>{label}</span>
                  <span className="mono" style={{ color: "var(--text-main)", fontSize: "0.78rem" }}>{formatPercent(value, 0)}</span>
                </div>
                <div className="micro-bar-track">
                  <div className="micro-bar-fill" style={{ width: `${value * 100}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div>
        <h2 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "var(--space-4)" }}>Suspicious activity log</h2>
        {!wallet.alerts?.length ? (
          <div className="panel" style={{ padding: "var(--space-8)", color: "var(--text-muted)", fontSize: "0.85rem" }}>
            No suspicious activity has been stored for this wallet yet.
          </div>
        ) : (
          <div className="feed-container">
            {wallet.alerts.map((alert, index) => (
              <div key={alert.id || index} className="alert-item">
                <div className="alert-rank">#{index + 1}</div>
                <div className="alert-main">
                  <div className="alert-title">{alert.market_question}</div>
                  <div className="alert-meta">
                    <span className="meta-tag">{alert.trade_side === "BUY" ? "▲ Buy" : "▼ Sell"} {formatUSD(alert.trade_size)}</span>
                    <span className="meta-tag">{timeAgo(alert.created_at)}</span>
                  </div>
                </div>
                <div className="alert-metrics">
                  <span className="metric-value">{alert.suspicion_score.toFixed(1)}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}

function StatCard({ label, value, highlight = false }) {
  return (
    <div className="stat-card" style={highlight ? { borderColor: "var(--border-mid)" } : undefined}>
      <span className="stat-label">{label}</span>
      <span className="stat-value" style={highlight ? { color: "var(--signal-success)" } : undefined}>{value}</span>
    </div>
  );
}
