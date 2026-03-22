"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  exportIntelligenceSnapshot,
  fetchAlerts,
  fetchInsiders,
  fetchStats,
  fetchWhales,
  triggerScan,
} from "@/lib/api";
import AnalysisStatus from "@/components/AnalysisStatus";
import { explainFactors, scoreTone } from "@/lib/intelligence";
import {
  FactorCard,
  FACTOR_LABELS,
  formatNum,
  formatPercent,
  formatUSD,
  shortAddr,
  timeAgo,
} from "@/lib/utils";

export default function DashboardPage() {
  const [stats, setStats] = useState(null);
  const [insiders, setInsiders] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [whales, setWhales] = useState([]);
  const [activePanel, setActivePanel] = useState("insiders");
  const [expandedAlert, setExpandedAlert] = useState(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportStatus, setExportStatus] = useState("");

  useEffect(() => {
    let ignore = false;

    async function loadDashboard() {
      try {
        const [nextStats, nextInsiders, nextAlerts, nextWhales] = await Promise.all([
          fetchStats(),
          fetchInsiders(),
          fetchAlerts(),
          fetchWhales({ limit: 5, minVolume: 5000 }),
        ]);

        if (ignore) return;
        setStats(nextStats);
        setInsiders(nextInsiders);
        setAlerts(nextAlerts);
        setWhales(nextWhales);
      } catch {
        if (!ignore) {
          setStats(null);
          setInsiders([]);
          setAlerts([]);
          setWhales([]);
        }
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    }

    void loadDashboard();
    return () => {
      ignore = true;
    };
  }, []);

  const highlightedAlerts = useMemo(() => alerts.slice(0, 6), [alerts]);

  async function handleScan() {
    setScanning(true);
    try {
      await triggerScan();
      setExportStatus("Manual scan started.");
    } catch {
      setExportStatus("Unable to trigger scan right now.");
    } finally {
      setScanning(false);
    }
  }

  async function handleExport() {
    setExporting(true);
    setExportStatus("");
    try {
      const snapshot = await exportIntelligenceSnapshot();
      const blob = new Blob([JSON.stringify(snapshot, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `polymarket-intelligence-${new Date().toISOString().slice(0, 10)}.json`;
      anchor.click();
      URL.revokeObjectURL(url);
      setExportStatus("Snapshot exported successfully.");
    } catch {
      setExportStatus("Snapshot export failed.");
    } finally {
      setExporting(false);
    }
  }

  return (
    <>
      <div className="hero-shell">
        <div>
          <div className="hero-kicker mono">High-signal market intelligence</div>
          <h1 className="display hero-title">Polymarket Whale Watcher</h1>
          <p className="hero-subtitle">
            Track suspicious wallets, monitor market alerts, and discover traders worth following without leaving the existing terminal-style workflow.
          </p>
        </div>

        <div className="hero-actions">
          <button className="btn btn-primary" onClick={handleScan} disabled={scanning}>
            {scanning ? "Starting scan..." : "Run manual scan"}
          </button>
          <button className="btn btn-outline" onClick={handleExport} disabled={exporting}>
            {exporting ? "Exporting..." : "Export snapshot"}
          </button>
        </div>
      </div>

      {exportStatus ? (
        <div className="panel" style={{ marginBottom: "var(--space-4)", padding: "var(--space-3)", color: "var(--text-muted)", fontSize: "0.85rem" }}>
          {exportStatus}
        </div>
      ) : null}

      <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "var(--space-4)", marginBottom: "var(--space-6)" }}>
        <FactorCard
          title="Current development sprint"
          weight="March 2026"
          desc={
            <ul style={{ margin: 0, paddingLeft: "1.2rem", display: "grid", gap: "0.4rem" }}>
              <li><strong>Risk engine sync:</strong> unify the canonical 6-factor model across backend, copy, and UI.</li>
              <li><strong>Persistence:</strong> add JSON export/import with a Supabase-ready storage adapter.</li>
              <li><strong>Financial logic:</strong> repair win-rate and PnL data flow end to end.</li>
              <li><strong>Whales dashboard:</strong> separate trader discovery from insider detection.</li>
              <li><strong>Detection quality:</strong> apply conservative wallet-age filtering to reduce noise.</li>
            </ul>
          }
        />
      </div>

      <AnalysisStatus />

      <div className="stats-grid">
        <StatCard label="Accounts tracked" value={stats ? formatNum(stats.total_wallets_scanned) : "—"} />
        <StatCard label="Total alerts" value={stats ? formatNum(stats.total_alerts) : "—"} />
        <StatCard label="Average risk score" value={stats ? formatNum(stats.avg_score, 1) : "—"} />
        <StatCard label="Maximum risk score" value={stats ? formatNum(stats.max_score, 1) : "—"} highlight={stats?.max_score > 75} />
      </div>

      <div className="home-grid">
        <div className="panel" style={{ padding: "var(--space-6)" }}>
          <SectionHeader
            title="Insider monitor"
            subtitle="Highest-risk wallets with explainable reasons for review."
            actions={(
              <div className="segmented-controls">
                <button className={`nav-link ${activePanel === "insiders" ? "active" : ""}`} onClick={() => setActivePanel("insiders")}>Top wallets</button>
                <button className={`nav-link ${activePanel === "alerts" ? "active" : ""}`} onClick={() => setActivePanel("alerts")}>Live feed</button>
              </div>
            )}
          />
          {activePanel === "insiders" ? (
            <InsidersTable insiders={insiders} loading={loading} />
          ) : (
            <AlertsFeed
              alerts={highlightedAlerts}
              loading={loading}
              expanded={expandedAlert}
              onToggle={(id) => setExpandedAlert(expandedAlert === id ? null : id)}
            />
          )}
        </div>

        <div style={{ display: "grid", gap: "var(--space-4)" }}>
          <div className="panel" style={{ padding: "var(--space-6)" }}>
            <SectionHeader
              title="Whale preview"
              subtitle="Profitable wallets with lower risk and stronger followability."
              actions={<Link href="/whales" className="btn btn-outline" style={{ fontSize: "0.72rem", padding: "4px 8px" }}>Open whales →</Link>}
            />
            <div style={{ display: "grid", gap: "var(--space-3)" }}>
              {whales.length ? whales.map((wallet) => (
                <div key={wallet.address} className="signal-row">
                  <div>
                    <div className="mono" style={{ color: "var(--text-main)", fontSize: "0.85rem" }}>{wallet.username || shortAddr(wallet.address)}</div>
                    <div style={{ color: "var(--text-muted)", fontSize: "0.78rem" }}>{formatPercent(wallet.win_rate, 0)} win rate · {formatUSD(wallet.total_profit)} profit</div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div className="mono" style={{ color: "var(--brand-primary)", fontWeight: 700 }}>{formatNum(wallet.followability_score, 0)}</div>
                    <div style={{ color: "var(--text-dim)", fontSize: "0.7rem" }}>Followability</div>
                  </div>
                </div>
              )) : (
                <EmptyCopy title="No whale profiles yet" body="Run another scan to populate trader-discovery metrics." />
              )}
            </div>
          </div>

          <div className="panel" style={{ padding: "var(--space-6)" }}>
            <SectionHeader title="Signal health" subtitle="Quick read on data freshness and operator tooling." />
            <div style={{ display: "grid", gap: "var(--space-3)" }}>
              <SignalHealthRow label="Snapshot export" value="Ready" tone="success" />
              <SignalHealthRow label="Risk model" value="6-factor synced" tone="info" />
              <SignalHealthRow label="Detection posture" value="Conservative age filter" tone="warning" />
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

function SectionHeader({ title, subtitle, actions }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "var(--space-4)", marginBottom: "var(--space-5)" }}>
      <div>
        <h2 style={{ fontSize: "1rem", color: "var(--text-main)", marginBottom: "var(--space-1)" }}>{title}</h2>
        <p style={{ color: "var(--text-muted)", fontSize: "0.82rem" }}>{subtitle}</p>
      </div>
      {actions}
    </div>
  );
}

function StatCard({ label, value, highlight = false }) {
  return (
    <div className="stat-card" style={highlight ? { borderColor: "var(--signal-danger)" } : undefined}>
      <span className="stat-label">{label}</span>
      <span className="stat-value" style={highlight ? { color: "var(--signal-danger)" } : undefined}>{value}</span>
    </div>
  );
}

function EmptyCopy({ title, body }) {
  return (
    <div style={{ padding: "var(--space-8)", textAlign: "center", color: "var(--text-muted)" }}>
      <div className="mono" style={{ color: "var(--text-main)", marginBottom: "var(--space-2)" }}>{title}</div>
      <div style={{ fontSize: "0.82rem" }}>{body}</div>
    </div>
  );
}

function SignalHealthRow({ label, value, tone }) {
  const color = tone === "success" ? "var(--signal-success)" : tone === "warning" ? "var(--signal-warning)" : "var(--signal-info)";
  return (
    <div className="signal-row">
      <span className="mono" style={{ color: "var(--text-muted)", fontSize: "0.76rem" }}>{label}</span>
      <span className="badge" style={{ color, border: `1px solid ${color}` }}>{value}</span>
    </div>
  );
}

function WhyFlaggedChips({ wallet }) {
  const reasons = wallet.why_flagged?.length ? wallet.why_flagged : explainFactors(wallet.analysis?.factors);
  if (!reasons.length) return <span className="mono" style={{ color: "var(--text-dim)", fontSize: "0.7rem" }}>Awaiting richer factor history</span>;

  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginTop: "var(--space-2)" }}>
      {reasons.map((reason) => (
        <span key={reason} className="badge zinc" style={{ fontWeight: 500 }}>
          {reason}
        </span>
      ))}
    </div>
  );
}

function InsidersTable({ insiders, loading }) {
  if (loading) return <EmptyCopy title="Loading insider data" body="Waiting for backend intelligence surfaces to respond." />;
  if (!insiders.length) return <EmptyCopy title="No insiders identified yet" body="No suspicious wallets have cleared the current risk threshold." />;

  return (
    <div style={{ display: "grid", gap: "var(--space-3)" }}>
      {insiders.slice(0, 8).map((wallet, index) => {
        const tone = scoreTone(wallet.risk_score || 0);
        const color = tone === "critical" ? "var(--signal-danger)" : tone === "high" ? "var(--signal-warning)" : "var(--signal-info)";
        return (
          <div key={wallet.address} className="signal-card">
            <div style={{ display: "flex", justifyContent: "space-between", gap: "var(--space-4)", alignItems: "flex-start" }}>
              <div>
                <div className="mono" style={{ color: "var(--text-dim)", fontSize: "0.72rem", marginBottom: "var(--space-1)" }}>#{index + 1} suspicious wallet</div>
                <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", flexWrap: "wrap" }}>
                  <span className="mono" style={{ color: "var(--text-main)", fontSize: "0.92rem" }}>{wallet.username || shortAddr(wallet.address)}</span>
                  <span className="badge" style={{ color, border: `1px solid ${color}` }}>{wallet.score_label}</span>
                </div>
                <div style={{ color: "var(--text-muted)", fontSize: "0.82rem", marginTop: "var(--space-1)" }}>
                  {formatPercent(wallet.win_rate, 0)} win rate · {formatUSD(wallet.total_pnl || wallet.total_profit)} PnL · {formatNum(wallet.resolved_markets_count || 0)} resolved markets
                </div>
                <WhyFlaggedChips wallet={wallet} />
              </div>

              <div style={{ textAlign: "right", minWidth: 120 }}>
                <div className="mono" style={{ color, fontSize: "1.2rem", fontWeight: 700 }}>{formatNum(wallet.risk_score || 0, 0)}</div>
                <div style={{ color: "var(--text-dim)", fontSize: "0.72rem", marginBottom: "var(--space-3)" }}>Risk score</div>
                <Link href={`/wallet/${wallet.address}`} className="btn btn-outline" style={{ fontSize: "0.72rem", padding: "4px 8px" }}>
                  Review
                </Link>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function AlertsFeed({ alerts, loading, expanded, onToggle }) {
  if (loading) return <EmptyCopy title="Loading alert feed" body="Waiting for the latest anomaly feed." />;
  if (!alerts.length) return <EmptyCopy title="No anomalies detected" body="The current scan window has not produced live-feed alerts." />;

  return (
    <div className="feed-container">
      {alerts.map((alert, index) => {
        const score = alert.suspicion_score || 0;
        const isExpanded = expanded === (alert.id || index);
        const reasons = alert.factors?.elevated_factors?.length
          ? alert.factors.elevated_factors.map((factor) => FACTOR_LABELS[factor] || factor)
          : explainFactors(alert.factors, 3);

        return (
          <div key={alert.id || index} className="alert-item" style={isExpanded ? { background: "var(--bg-surface)" } : undefined}>
            <div className="alert-rank">#{index + 1}</div>
            <div className="alert-main">
              <button className="alert-toggle" onClick={() => onToggle(alert.id || index)}>
                <span className="alert-title">{alert.market_question || "Unknown market"}</span>
                <span className="badge zinc">{scoreTone(score)}</span>
              </button>
              <div className="alert-meta">
                <span className="meta-tag"><span style={{ color: alert.trade_side === "BUY" ? "var(--signal-success)" : "var(--signal-danger)" }}>{alert.trade_side}</span> <span className="mono">{formatUSD(alert.trade_size)}</span></span>
                <span className="meta-tag">{timeAgo(alert.created_at)}</span>
                <Link href={`/wallet/${alert.wallet_address}`} className="meta-tag mono" style={{ color: "var(--brand-primary)" }}>{shortAddr(alert.wallet_address)}</Link>
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginTop: "var(--space-2)" }}>
                {reasons.map((reason) => (
                  <span key={reason} className="badge zinc">{reason}</span>
                ))}
              </div>
              {isExpanded ? (
                <div style={{ marginTop: "var(--space-4)", display: "grid", gap: "var(--space-3)" }}>
                  {Object.entries(FACTOR_LABELS).map(([key, label]) => {
                    const value = alert.factors?.[key] ?? 0;
                    if (value < 0.1) return null;
                    return (
                      <div key={key}>
                        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.72rem", marginBottom: 4 }}>
                          <span style={{ color: "var(--text-muted)" }}>{label}</span>
                          <span className="mono" style={{ color: "var(--text-main)" }}>{formatPercent(value, 0)}</span>
                        </div>
                        <div className="micro-bar-track">
                          <div className="micro-bar-fill" style={{ width: `${value * 100}%` }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : null}
            </div>
            <div className="alert-metrics">
              <div className="metric-value">{score.toFixed(1)}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
