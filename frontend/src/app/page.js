"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { fetchAlerts, fetchStats, triggerScan, fetchExpiringMarkets } from "@/lib/api";
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
  const [tab, setTab] = useState("alerts");
  const [stats, setStats] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [expiring, setExpiring] = useState([]);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [horizon, setHorizon] = useState(168);
  const [expandedAlert, setExpandedAlert] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, a] = await Promise.all([fetchStats(), fetchAlerts()]);
      setStats(s);
      setAlerts(a);
    } catch {
      /* backend offline — use skeleton/empty states */
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (tab !== "expiring") return;
    let active = true;
    fetchExpiringMarkets({ hours: horizon })
      .then((data) => active && setExpiring(data))
      .catch(() => { });
    return () => { active = false; };
  }, [tab, horizon]);

  const handleScan = async () => {
    setScanning(true);
    try {
      await triggerScan();
      await load();
    } catch { /* */ }
    setScanning(false);
  };

  return (
    <>
      <div style={{ marginBottom: "var(--space-8)", display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
        <div>
          <h1 className="display" style={{ fontSize: "2rem", fontWeight: 700, color: "var(--text-main)", lineHeight: 1.1 }}>
            Network Activity
          </h1>
          <p className="mono" style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginTop: "var(--space-2)" }}>
            Real-time surveillance of prediction market flows
          </p>
        </div>
        <button
          onClick={handleScan}
          className="btn btn-primary"
          disabled={scanning}
        >
          {scanning ? "SCANNING..." : "RUN ANALYSIS"}
        </button>
      </div>

      <div className="stats-grid">
        <StatCard label="Active Alerts" value={stats ? formatNum(stats.total_alerts) : "—"} />
        <StatCard label="Wallets Analyzed" value={stats ? formatNum(stats.total_wallets_scanned) : "—"} />
        <StatCard label="Max Risk Score" value={stats ? formatNum(stats.max_score, 1) : "—"} highlight={stats?.max_score > 80} />
        <StatCard label="24h Volume" value="—" />
      </div>

      <div className="panel" style={{ padding: "var(--space-6)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-6)" }}>
          <div style={{ display: "flex", gap: "var(--space-4)" }}>
            <button
              className={`nav-link ${tab === "alerts" ? "active" : ""}`}
              onClick={() => setTab("alerts")}
              style={{ background: "none", border: "none", borderBottom: tab === "alerts" ? "1px solid var(--brand-primary)" : "1px solid transparent", cursor: "pointer" }}
            >
              LIVE FEED
            </button>
            <button
              className={`nav-link ${tab === "expiring" ? "active" : ""}`}
              onClick={() => setTab("expiring")}
              style={{ background: "none", border: "none", borderBottom: tab === "expiring" ? "1px solid var(--brand-primary)" : "1px solid transparent", cursor: "pointer" }}
            >
              EXPIRING
            </button>
          </div>

          {tab === "alerts" && (
            <Link href="/markets" className="btn btn-outline" style={{ fontSize: "0.7rem", padding: "4px 8px" }}>
              VIEW ALL MARKETS →
            </Link>
          )}
        </div>

        {tab === "alerts" && (
          <AlertsFeed
            alerts={alerts}
            loading={loading}
            expanded={expandedAlert}
            onToggle={(id) => setExpandedAlert(expandedAlert === id ? null : id)}
          />
        )}

        {tab === "expiring" && (
          <ExpiringSection
            markets={expiring}
            horizon={horizon}
            onHorizonChange={setHorizon}
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

function AlertsFeed({ alerts, loading, expanded, onToggle }) {
  if (loading) return <div style={{ padding: "var(--space-8)", textAlign: "center", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>LOADING FEED DATA...</div>;
  if (!alerts.length) return (
    <div style={{ padding: "var(--space-12)", textAlign: "center", color: "var(--text-muted)" }}>
      <div style={{ fontSize: "2rem", marginBottom: "var(--space-2)", opacity: 0.3 }}>📡</div>
      <div className="mono">NO ANOMALIES DETECTED</div>
    </div>
  );

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
                      href={`https://polymarket.com/event/${a.market_slug}`}
                      target="_blank"
                      rel="noreferrer"
                      className="btn btn-outline"
                      style={{ fontSize: "0.7rem", padding: "4px 8px" }}
                    >
                      View on Polymarket ↗
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

function ExpiringSection({ markets, horizon, onHorizonChange }) {
  const options = [24, 48, 72, 168];

  return (
    <div>
      <div style={{ marginBottom: "var(--space-4)", display: "flex", gap: "var(--space-2)" }}>
        {options.map((h) => (
          <button
            key={h}
            className="btn btn-outline"
            style={{
              borderColor: horizon === h ? "var(--brand-primary)" : "var(--border-dim)",
              color: horizon === h ? "var(--text-main)" : "var(--text-muted)",
              fontSize: "0.75rem", padding: "4px 8px"
            }}
            onClick={() => onHorizonChange(h)}
          >
            {h}H
          </button>
        ))}
      </div>

      {!markets.length ? (
        <div style={{ padding: "var(--space-6)", color: "var(--text-muted)", textAlign: "center", fontStyle: "italic" }}>No markets expiring in this window.</div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "var(--space-4)" }}>
          {markets.map((m, i) => (
            <div key={i} className="panel" style={{ padding: "var(--space-4)", backgroundColor: "var(--bg-app)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "var(--space-2)" }}>
                <span className="badge amber" style={{ fontSize: "0.65rem" }}>{formatCountdown(m.hours_remaining)} LEFT</span>
                <span className="mono" style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>${formatNum(m.volume)} VOL</span>
              </div>
              <div style={{ fontWeight: 500, fontSize: "0.85rem", marginBottom: "var(--space-4)", height: "2.8em", overflow: "hidden", lineHeight: 1.4 }}>
                {m.question}
              </div>

              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: "0.75rem" }}>
                <span style={{ color: "var(--text-muted)" }}>SUSPICIOUS TRADES</span>
                <span className="mono" style={{ color: m.suspicious_trade_count > 0 ? "var(--signal-danger)" : "var(--text-main)", fontWeight: 700 }}>
                  {m.suspicious_trade_count}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
