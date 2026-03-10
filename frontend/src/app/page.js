"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import Link from "next/link";
import { fetchAlerts, fetchStats, triggerScan, fetchInsiders } from "@/lib/api";
import AnalysisStatus from "@/components/AnalysisStatus";
import {
  shortAddr,
  formatNum,
  formatUSD,
  timeAgo,
  formatCountdown,
  FACTOR_LABELS,
} from "@/lib/utils";

/* ═══════════════════════════════════════════════════════════
   Dashboard Home Page
   Theme: Financial Terminal
   ═══════════════════════════════════════════════════════════ */

export default function DashboardPage() {
  const [tab, setTab] = useState("insiders");
  const [stats, setStats] = useState(null);
  const [insiders, setInsiders] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [horizon, setHorizon] = useState(168);
  const [expandedAlert, setExpandedAlert] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, i, a] = await Promise.all([
        fetchStats(),
        fetchInsiders(),
        fetchAlerts()
      ]);
      setStats(s);
      setInsiders(i);
      setAlerts(a);
    } catch {
      /* backend offline — use skeleton/empty states */
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleScan = async () => {
    setScanning(true);
    try {
      await triggerScan();
      // Wait a bit for analysis to run
      await new Promise(r => setTimeout(r, 2000));
      await load();
    } catch { /* */ }
    setScanning(false);
  };

  return (
    <>
      <div style={{ marginBottom: "var(--space-8)", display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
        <div>
          <h1 className="display" style={{ fontSize: "2rem", fontWeight: 700, color: "var(--text-main)", lineHeight: 1.1 }}>
            Polymarket Whale Watcher
          </h1>
          <p className="mono" style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginTop: "var(--space-2)" }}>
            Tracking Top Profitable & Suspicious Wallets
          </p>
        </div>
      </div>

      <AnalysisStatus />

      <div className="stats-grid">
        <StatCard label="Possible Insiders Tracked" value={stats ? formatNum(stats.total_wallets_scanned) : "—"} />
        <StatCard label="Total Alerts" value={stats ? formatNum(stats.total_alerts) : "—"} />
        <StatCard label="Avg Risk Score" value={stats ? formatNum(stats.avg_score, 1) : "—"} />
        <StatCard label="Max Risk Score" value={stats ? formatNum(stats.max_score, 1) : "—"} highlight={stats?.max_score > 80} />
      </div>

      <div className="panel" style={{ padding: "var(--space-6)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-6)" }}>
          <div style={{ display: "flex", gap: "var(--space-4)" }}>
            <button
              className={`nav-link ${tab === "insiders" ? "active" : ""}`}
              onClick={() => setTab("insiders")}
              style={{ background: "none", border: "none", borderBottom: tab === "insiders" ? "1px solid var(--brand-primary)" : "1px solid transparent", cursor: "pointer" }}
            >
              TOP POSSIBLE INSIDERS
            </button>
            <button
              className={`nav-link ${tab === "alerts" ? "active" : ""}`}
              onClick={() => setTab("alerts")}
              style={{ background: "none", border: "none", borderBottom: tab === "alerts" ? "1px solid var(--brand-primary)" : "1px solid transparent", cursor: "pointer" }}
            >
              LIVE FEED
            </button>
          </div>

          {tab === "alerts" && (
            <Link href="/markets" className="btn btn-outline" style={{ fontSize: "0.7rem", padding: "4px 8px" }}>
              VIEW ALL MARKETS →
            </Link>
          )}
        </div>

        {tab === "insiders" && (
          <InsidersTable insiders={insiders} loading={loading} />
        )}

        {tab === "alerts" && (
          <AlertsFeed
            alerts={alerts}
            loading={loading}
            expanded={expandedAlert}
            onToggle={(id) => setExpandedAlert(expandedAlert === id ? null : id)}
          />
        )}
      </div>
    </>
  );
}

/* ── Components ── */

function StatCard({ label, value, highlight }) {
  return (
    <div className="stat-card" style={highlight ? { borderColor: "var(--signal-danger)" } : {}}>
      <span className="stat-label">{label}</span>
      <span className="stat-value" style={highlight ? { color: "var(--signal-danger)" } : {}}>
        {value}
      </span>
    </div>
  );
}

function Tooltip({ children, content }) {
  const [visible, setVisible] = useState(false);

  return (
    <div
      style={{ position: 'relative', display: 'inline-block', cursor: 'help' }}
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
    >
      {children}
      {visible && (
        <div style={{
          position: 'absolute',
          bottom: '100%',
          left: '50%',
          transform: 'translateX(-50%)',
          marginBottom: '8px',
          padding: '8px 12px',
          background: 'var(--bg-surface)',
          border: '1px solid var(--border-dim)',
          borderRadius: '4px',
          width: '200px',
          zIndex: 100,
          boxShadow: '0 4px 6px rgba(0,0,0,0.3)',
          fontSize: '0.75rem',
          color: 'var(--text-main)',
          pointerEvents: 'none'
        }}>
          {content}
        </div>
      )}
    </div>
  );
}

function InsidersTable({ insiders, loading }) {
  if (loading) return <div style={{ padding: "var(--space-8)", textAlign: "center", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>LOADING INSIDER DATA...</div>;
  if (!insiders.length) return <div className="mono" style={{ textAlign: "center", padding: "2rem", color: "var(--text-muted)" }}>NO INSIDERS IDENTIFIED YET</div>;

  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem", textAlign: "left" }}>
        <thead>
          <tr style={{ borderBottom: "1px solid var(--border-dim)", color: "var(--text-muted)" }}>
            <th style={{ padding: "12px", fontWeight: 500 }}>RANK</th>
            <th style={{ padding: "12px", fontWeight: 500 }}>ADDRESS</th>
            <th style={{ padding: "12px", fontWeight: 500 }}>
              <Tooltip content="Win Rate: Percentage of profitable trades. Higher is better.">
                WIN RATE ⓘ
              </Tooltip>
            </th>
            <th style={{ padding: "12px", fontWeight: 500 }}>
              <Tooltip content="PnL: Total estimated profit/loss across tracked trades.">
                PnL ⓘ
              </Tooltip>
            </th>
            <th style={{ padding: "12px", fontWeight: 500 }}>
              <Tooltip content="Risk Score: 0-100 score indicating likelihood of insider activity based on timing, volume, and profitability.">
                RISK SCORE ⓘ
              </Tooltip>
            </th>
            <th style={{ padding: "12px", fontWeight: 500 }}>ACTION</th>
          </tr>
        </thead>
        <tbody>
          {insiders.map((wallet, i) => {
            const score = wallet.risk_score || 0;
            const winRate = wallet.win_rate || 0;
            const pnl = wallet.total_profit || 0; // Fixed total_profit

            // Determine Score Color
            const scoreColor = score > 75 ? "var(--signal-danger)" : score > 50 ? "var(--signal-warning)" : "var(--text-muted)";

            return (
              <tr key={wallet.address} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                <td style={{ padding: "12px", fontFamily: "var(--font-mono)" }}>#{i + 1}</td>
                <td style={{ padding: "12px", fontFamily: "var(--font-mono)" }}>
                  <span style={{ color: "var(--text-main)" }}>{shortAddr(wallet.address)}</span>
                  {wallet.username && <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>{wallet.username}</div>}
                </td>
                <td style={{ padding: "12px", fontFamily: "var(--font-mono)" }}>
                  <span style={{ color: winRate > 0.6 ? "var(--signal-success)" : "var(--text-main)" }}>
                    {(winRate * 100).toFixed(1)}%
                  </span>
                </td>
                <td style={{ padding: "12px", fontFamily: "var(--font-mono)" }}>
                  <span style={{ color: pnl >= 0 ? "var(--signal-success)" : "var(--signal-danger)" }}>
                    {pnl >= 0 ? "+" : ""}{formatUSD(pnl)}
                  </span>
                </td>
                <td style={{ padding: "12px", fontFamily: "var(--font-mono)", fontWeight: 700, color: scoreColor }}>
                  {score.toFixed(0)}
                </td>
                <td style={{ padding: "12px" }}>
                  <Link href={`/wallet/${wallet.address}`} className="btn btn-outline" style={{ fontSize: "0.75rem", padding: "4px 8px" }}>
                    ANALYZE
                  </Link>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function AlertsFeed({ alerts, loading, expanded, onToggle }) {
  if (loading) return <div style={{ padding: "var(--space-8)", textAlign: "center", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>LOADING FEED DATA...</div>;
  if (!alerts.length) return (
    <div style={{ padding: "var(--space-12)", textAlign: "center", color: "var(--text-muted)" }}>
      <div style={{ fontSize: "2rem", marginBottom: "var(--space-2)", opacity: 0.3 }}>📡</div>
      <div className="mono">NO ANOMALIES DETECTED</div>
    </div>
  );

  // ... (keeping existing AlertsFeed render logic but can simplify if needed)
  return (
    <div className="feed-container">
      {alerts.map((a, i) => {
        const score = a.suspicion_score || 0;
        const severity = score > 75 ? "critical" : score > 50 ? "high" : "medium";
        const isExpanded = expanded === (a.id || i);

        return (
          <div key={a.id || i} className={`alert-item ${severity}`} style={isExpanded ? { background: "var(--bg-surface)" } : {}}>
            <div className="alert-rank">#{i + 1}</div>

            <div className="alert-main">
              <div
                className="alert-title"
                style={{ cursor: "pointer" }}
                onClick={() => onToggle(a.id || i)}
              >
                {a.market_question}
              </div>
              <div className="alert-meta">
                <span className="meta-tag">
                  <span style={{ color: a.trade_side === "BUY" ? "var(--signal-success)" : "var(--signal-danger)" }}>
                    {a.trade_side}
                  </span>
                  <span className="mono"> {formatUSD(a.trade_size)}</span>
                </span>
                <span className="meta-tag">
                  {timeAgo(a.created_at)}
                </span>
                <Link
                  href={`/wallet/${a.wallet_address}`}
                  className="meta-tag mono"
                  style={{ color: "var(--brand-primary)" }}
                  onClick={(e) => e.stopPropagation()}
                >
                  {shortAddr(a.wallet_address)}
                </Link>
              </div>

              {/* Expansion */}
              {isExpanded && a.factors && (
                <div style={{ marginTop: "var(--space-4)", paddingTop: "var(--space-4)", borderTop: "1px solid var(--border-dim)", width: "100%" }}>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))", gap: "var(--space-4)" }}>
                    {Object.entries(FACTOR_LABELS).map(([key, label]) => {
                      const val = a.factors[key] ?? 0;
                      if (val < 0.1) return null;
                      const isHigh = val > 0.7;
                      return (
                        <div key={key}>
                          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.7rem", marginBottom: 4, fontFamily: "var(--font-mono)" }}>
                            <span style={{ color: "var(--text-muted)" }}>{label}</span>
                            <span style={{ color: isHigh ? "var(--text-main)" : "var(--text-dim)" }}>{(val * 100).toFixed(0)}%</span>
                          </div>
                          <div style={{ height: 4, background: "var(--bg-app)", borderRadius: 2, overflow: "hidden" }}>
                            <div style={{ height: "100%", width: `${val * 100}%`, background: isHigh ? "var(--signal-warning)" : "var(--text-dim)" }} />
                          </div>
                        </div>
                      )
                    })}
                  </div>
                  <div style={{ marginTop: "var(--space-4)", textAlign: "right" }}>
                    <a
                      href={`https://polymarket.com/search?q=${encodeURIComponent(a.market_question)}`}
                      target="_blank"
                      rel="noreferrer"
                      className="btn btn-outline"
                      style={{ fontSize: "0.7rem", padding: "4px 8px" }}
                    >
                      Find on Polymarket ↗
                    </a>
                  </div>
                </div>
              )}
            </div>

            <div className="alert-metrics">
              <div className="metric-value" style={{
                color: severity === "critical" ? "var(--signal-danger)" :
                  severity === "high" ? "var(--signal-warning)" : "var(--signal-info)"
              }}>
                {score.toFixed(1)}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
