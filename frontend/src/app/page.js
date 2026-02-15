"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { fetchAlerts, fetchStats, triggerScan, fetchExpiringMarkets } from "@/lib/api";
import {
  scoreClass,
  shortAddr,
  formatNum,
  formatUSD,
  timeAgo,
  formatCountdown,
  FACTOR_LABELS,
} from "@/lib/utils";

/* ═══════════════════════════════════════════════════════════
   Dashboard Home Page
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
      /* backend offline — show empty */
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
      {/* ── Header ── */}
      <div className="section-header" style={{ marginBottom: "var(--space-6)" }}>
        <div>
          <h1 className="section-title" style={{ fontSize: "1.5rem", fontWeight: 800, letterSpacing: "-0.03em" }}>
            Activity Monitor
          </h1>
          <p className="section-subtitle">
            Real-time suspicion scoring across Polymarket
          </p>
        </div>
        <button
          className="btn btn-primary"
          onClick={handleScan}
          disabled={scanning}
        >
          {scanning ? (
            <><span className="spinner" /> Scanning…</>
          ) : (
            <>
              <ScanIcon />
              Run Scan
            </>
          )}
        </button>
      </div>

      {/* ── Stats ── */}
      <div className="stats-grid">
        <StatCard label="Total Alerts" value={stats ? formatNum(stats.total_alerts) : "—"} />
        <StatCard label="Wallets Scanned" value={stats ? formatNum(stats.total_wallets_scanned) : "—"} />
        <StatCard label="Top Score" value={stats ? formatNum(stats.max_score, 1) : "—"} color="var(--score-critical)" />
        <StatCard label="Today" value={stats ? formatNum(stats.alerts_today) : "—"} accent />
      </div>

      {/* ── Tab switcher ── */}
      <div className="tab-group">
        <button className={`tab-btn ${tab === "alerts" ? "active" : ""}`} onClick={() => setTab("alerts")}>
          <AlertsIcon /> All Alerts
          {alerts.length > 0 && <span className="tab-count">{alerts.length}</span>}
        </button>
        <button className={`tab-btn ${tab === "expiring" ? "active" : ""}`} onClick={() => setTab("expiring")}>
          <ClockIcon /> Expiring Soon
        </button>
      </div>

      {/* ── Content ── */}
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
    </>
  );
}

/* ═══════════════════════════════════════════════════════════
   Stat Card
   ═══════════════════════════════════════════════════════════ */

function StatCard({ label, value, color, accent }) {
  return (
    <div className="stat-card">
      <span className="stat-label">{label}</span>
      <span
        className="stat-value"
        style={color ? { color } : accent ? { background: "var(--accent-gradient)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" } : undefined}
      >
        {value}
      </span>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════
   Alerts Feed
   ═══════════════════════════════════════════════════════════ */

function AlertsFeed({ alerts, loading, expanded, onToggle }) {
  if (loading) {
    return (
      <div className="alert-list">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="alert-row" style={{ pointerEvents: "none" }}>
            <div className="skeleton" style={{ width: 36, height: 36 }} />
            <div style={{ display: "flex", flexDirection: "column", gap: 6, flex: 1 }}>
              <div className="skeleton skeleton-text" style={{ width: "75%" }} />
              <div className="skeleton skeleton-text" style={{ width: "40%" }} />
            </div>
            <div className="skeleton" style={{ width: 52, height: 24, borderRadius: 9999 }} />
          </div>
        ))}
      </div>
    );
  }

  if (!alerts.length) {
    return (
      <div className="empty-state">
        <div className="empty-icon">📡</div>
        <div className="empty-title">No alerts yet</div>
        <div className="empty-desc">
          Click &quot;Run Scan&quot; to analyze recent trading activity and detect suspicious patterns.
        </div>
      </div>
    );
  }

  return (
    <div className="alert-list">
      {alerts.map((a, i) => (
        <div key={a.id || i}>
          <div className="alert-row" onClick={() => onToggle(a.id || i)}>
            <div className="alert-rank">{i + 1}</div>
            <div className="alert-info">
              <a
                href={`https://polymarket.com/event/${a.market_slug}`}
                target="_blank"
                rel="noopener noreferrer"
                className="alert-market"
                onClick={(e) => e.stopPropagation()}
              >
                {a.market_question || "Unknown market"}
              </a>
              <div className="alert-sub-row" style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.85rem", color: "var(--fg-muted)" }}>
                <Link
                  href={`/wallet/${a.wallet_address}`}
                  className="alert-wallet"
                  onClick={(e) => e.stopPropagation()}
                >
                  {shortAddr(a.wallet_address)}
                </Link>
                {a.wallet_risk_score > 0 && (
                  <span style={{
                    fontSize: "0.75rem",
                    padding: "1px 4px",
                    borderRadius: 4,
                    background: "var(--bg-elevated)",
                    color: a.wallet_risk_score > 50 ? "var(--score-high)" : "var(--fg-muted)"
                  }}>
                    Risk: {a.wallet_risk_score.toFixed(0)}
                  </span>
                )}
                <div className="external-links" style={{ display: "flex", gap: 4, marginLeft: 4 }}>
                  <a href={`https://polymarket.com/profile/${a.wallet_address}`} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()} style={{ opacity: 0.6 }}>PM</a>
                  <a href={`https://polygonscan.com/address/${a.wallet_address}`} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()} style={{ opacity: 0.6 }}>Scan</a>
                </div>
              </div>
            </div>
            <div className="alert-meta">
              <span className="alert-trade-size">
                {a.trade_side === "BUY" ? "▲" : "▼"} {formatUSD(a.trade_size)}
              </span>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span className="alert-time">{timeAgo(a.created_at)}</span>
                {a.tx_hash && (
                  <a
                    href={`https://polygonscan.com/tx/${a.tx_hash}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    style={{ fontSize: "0.75rem", opacity: 0.6, textDecoration: "none" }}
                  >
                    Context ↗
                  </a>
                )}
              </div>
            </div>
            <span className={`score-badge ${scoreClass(a.suspicion_score)}`}>
              {a.suspicion_score?.toFixed(1)}
            </span>
          </div>

          {/* Expanded factor breakdown */}
          {expanded === (a.id || i) && a.factors && (
            <div className="card" style={{ marginTop: "var(--space-1)", marginLeft: 56 }}>
              <div className="factor-breakdown">
                {Object.entries(FACTOR_LABELS).map(([key, label]) => {
                  const val = a.factors[key] ?? 0;
                  const isElevated = a.factors.elevated_factors?.includes(key);
                  return (
                    <div className="factor-row" key={key}>
                      <span className="factor-label" style={isElevated ? { color: "var(--accent-primary)", fontWeight: 600 } : undefined}>
                        {label}
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
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════
   Expiring Markets Section
   ═══════════════════════════════════════════════════════════ */

function ExpiringSection({ markets, horizon, onHorizonChange }) {
  const options = [
    { value: 24, label: "24h" },
    { value: 48, label: "48h" },
    { value: 72, label: "3d" },
    { value: 168, label: "7d" },
  ];

  return (
    <>
      <div className="horizon-group">
        {options.map((o) => (
          <button
            key={o.value}
            className={`horizon-pill ${horizon === o.value ? "active" : ""}`}
            onClick={() => onHorizonChange(o.value)}
          >
            {o.label}
          </button>
        ))}
      </div>

      {!markets.length ? (
        <div className="empty-state">
          <div className="empty-icon">⏳</div>
          <div className="empty-title">No expiring markets with suspicious activity</div>
          <div className="empty-desc">
            Try expanding the time horizon or running a scan first.
          </div>
        </div>
      ) : (
        <div className="expiring-grid">
          {markets.map((m, i) => (
            <ExpiringCard key={m.market_id || i} market={m} />
          ))}
        </div>
      )}
    </>
  );
}

function ExpiringCard({ market }) {
  const m = market;
  return (
    <div className="expiring-card">
      <div className="expiring-header">
        <span className="expiring-question">{m.question}</span>
        <div className="expiring-countdown">
          <span className="countdown-value">{formatCountdown(m.hours_remaining)}</span>
          <span className="countdown-label">remaining</span>
        </div>
      </div>

      <div className="expiring-stats">
        <div className="expiring-stat">
          <span className="expiring-stat-label">Volume</span>
          <span className="expiring-stat-value">{formatUSD(m.volume)}</span>
        </div>
        <div className="expiring-stat">
          <span className="expiring-stat-label">Suspicious Trades</span>
          <span className="expiring-stat-value" style={m.suspicious_trade_count > 0 ? { color: "var(--danger)" } : undefined}>
            {m.suspicious_trade_count}
          </span>
        </div>
        <div className="expiring-stat">
          <span className="expiring-stat-label">Top Score</span>
          <span className={`score-badge ${scoreClass(m.top_suspicion_score)}`} style={{ fontSize: "0.78rem" }}>
            {m.top_suspicion_score?.toFixed(1) || "—"}
          </span>
        </div>
      </div>

      {m.flagged_wallets?.length > 0 && (
        <div className="expiring-wallets">
          {m.flagged_wallets.map((w) => (
            <Link key={w} href={`/wallet/${w}`} className="wallet-chip">
              {shortAddr(w)}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Inline SVG icons ── */

function ScanIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  );
}

function AlertsIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
    </svg>
  );
}

function ClockIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}
