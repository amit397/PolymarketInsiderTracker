"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchWhales } from "@/lib/api";
import { sortWhales, DEFAULT_WHALE_SORT } from "@/lib/whales";
import { readWatchlist, toggleWatchlist } from "@/lib/watchlist";
import { formatNum, formatPercent, formatUSD, shortAddr } from "@/lib/utils";

const COLUMNS = [
  { key: "followed", label: "Followed" },
  { key: "followability_score", label: "Followability" },
  { key: "win_rate", label: "Win rate" },
  { key: "total_profit", label: "PnL" },
  { key: "total_volume", label: "Volume" },
  { key: "resolved_markets_count", label: "Resolved" },
  { key: "risk_score", label: "Risk" },
];

export default function WhalesPage() {
  const [whales, setWhales] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sort, setSort] = useState(DEFAULT_WHALE_SORT);
  const [followed, setFollowed] = useState([]);

  useEffect(() => {
    let ignore = false;

    async function loadWhales() {
      try {
        const [nextWhales] = await Promise.all([
          fetchWhales({ limit: 75, minVolume: 5000 }),
        ]);
        if (!ignore) {
          setWhales(nextWhales);
          setFollowed(readWatchlist());
        }
      } catch {
        if (!ignore) {
          setWhales([]);
        }
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    }

    void loadWhales();
    return () => {
      ignore = true;
    };
  }, []);

  const followedSet = useMemo(() => new Set(followed), [followed]);
  const sortedWhales = useMemo(() => sortWhales(whales, sort, followedSet), [whales, sort, followedSet]);
  const followedWhales = useMemo(() => sortedWhales.filter((wallet) => followedSet.has(wallet.address.toLowerCase())), [sortedWhales, followedSet]);

  function handleSort(columnKey) {
    setSort((current) => ({
      key: columnKey,
      direction: current.key === columnKey && current.direction === "desc" ? "asc" : "desc",
    }));
  }

  function handleToggleFollow(address) {
    const next = toggleWatchlist(address);
    setFollowed(next);
  }

  return (
    <>
      <div className="hero-shell" style={{ marginBottom: "var(--space-6)" }}>
        <div>
          <div className="hero-kicker mono">Follow-trader workspace</div>
          <h1 className="display hero-title" style={{ fontSize: "2.2rem" }}>Whale dashboard</h1>
          <p className="hero-subtitle">
            Separate the best-performing traders from the suspicious-wallet feed, rank them by followability, and keep a local watchlist for repeat monitoring.
          </p>
        </div>
      </div>

      <div className="whales-overview-grid">
        <MetricCard label="Profiles loaded" value={formatNum(whales.length)} />
        <MetricCard label="Followed wallets" value={formatNum(followed.length)} />
        <MetricCard label="Default sort" value="Followability" />
      </div>

      <div className="home-grid" style={{ alignItems: "start" }}>
        <div className="panel" style={{ padding: "var(--space-6)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: "var(--space-4)", marginBottom: "var(--space-5)", alignItems: "flex-start" }}>
            <div>
              <h2 style={{ fontSize: "1rem", color: "var(--text-main)", marginBottom: "var(--space-1)" }}>Leaderboard</h2>
              <p style={{ color: "var(--text-muted)", fontSize: "0.82rem" }}>Sortable performance metrics with risk context and follow actions.</p>
            </div>
            <div className="badge zinc">{sort.key.replaceAll("_", " ")}</div>
          </div>

          {loading ? (
            <div style={{ padding: "var(--space-10)", textAlign: "center", color: "var(--text-muted)" }}>Loading whale metrics…</div>
          ) : !sortedWhales.length ? (
            <div style={{ padding: "var(--space-10)", textAlign: "center", color: "var(--text-muted)" }}>No whales found yet. Run a scan to populate trader metrics.</div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Wallet</th>
                    {COLUMNS.map((column) => (
                      <th key={column.key}>
                        <button className="table-sort" onClick={() => handleSort(column.key)}>
                          {column.label}
                          {sort.key === column.key ? (sort.direction === "desc" ? " ↓" : " ↑") : ""}
                        </button>
                      </th>
                    ))}
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedWhales.map((wallet) => {
                    const isFollowed = followedSet.has(wallet.address.toLowerCase());
                    const riskColor = wallet.risk_score >= 40 ? "var(--signal-warning)" : "var(--text-muted)";
                    return (
                      <tr key={wallet.address}>
                        <td>
                          <div style={{ display: "grid", gap: 2 }}>
                            <span className="mono" style={{ color: "var(--brand-primary)", fontWeight: 600 }}>{wallet.username || shortAddr(wallet.address)}</span>
                            <span className="mono" style={{ color: "var(--text-muted)", fontSize: "0.72rem" }}>{shortAddr(wallet.address)}</span>
                          </div>
                        </td>
                        <td>{isFollowed ? "Yes" : "No"}</td>
                        <td>{formatNum(wallet.followability_score || 0, 0)}</td>
                        <td>{formatPercent(wallet.win_rate, 0)}</td>
                        <td style={{ color: wallet.total_profit >= 0 ? "var(--signal-success)" : "var(--signal-danger)" }}>{wallet.total_profit >= 0 ? "+" : ""}{formatUSD(wallet.total_profit)}</td>
                        <td>{formatUSD(wallet.total_volume)}</td>
                        <td>{formatNum(wallet.resolved_markets_count || 0)}</td>
                        <td style={{ color: riskColor }}>{formatNum(wallet.risk_score || 0, 0)}</td>
                        <td>
                          <button className={`btn ${isFollowed ? "btn-primary" : "btn-outline"}`} style={{ fontSize: "0.72rem", padding: "4px 8px" }} onClick={() => handleToggleFollow(wallet.address)}>
                            {isFollowed ? "Following" : "Follow"}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div style={{ display: "grid", gap: "var(--space-4)" }}>
          <div className="panel" style={{ padding: "var(--space-6)" }}>
            <h2 style={{ fontSize: "1rem", color: "var(--text-main)", marginBottom: "var(--space-2)" }}>Followed wallets</h2>
            <p style={{ color: "var(--text-muted)", fontSize: "0.82rem", marginBottom: "var(--space-4)" }}>Stored locally in your browser for quick access.</p>
            <div style={{ display: "grid", gap: "var(--space-3)" }}>
              {followedWhales.length ? followedWhales.map((wallet) => (
                <div key={wallet.address} className="signal-row">
                  <div>
                    <div className="mono" style={{ color: "var(--text-main)" }}>{wallet.username || shortAddr(wallet.address)}</div>
                    <div style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>{formatPercent(wallet.win_rate, 0)} win rate · {formatUSD(wallet.total_profit)} PnL</div>
                  </div>
                  <button className="btn btn-outline" style={{ fontSize: "0.72rem", padding: "4px 8px" }} onClick={() => handleToggleFollow(wallet.address)}>
                    Unfollow
                  </button>
                </div>
              )) : (
                <div style={{ color: "var(--text-muted)", fontSize: "0.82rem" }}>Follow a wallet from the leaderboard to build your shortlist.</div>
              )}
            </div>
          </div>

          <div className="panel" style={{ padding: "var(--space-6)" }}>
            <h2 style={{ fontSize: "1rem", color: "var(--text-main)", marginBottom: "var(--space-2)" }}>How to use this surface</h2>
            <ul style={{ margin: 0, paddingLeft: "1rem", display: "grid", gap: "0.4rem", color: "var(--text-muted)", fontSize: "0.82rem" }}>
              <li>Sort by followability for a balanced starting point.</li>
              <li>Sort by risk to quickly avoid likely insider-style behavior.</li>
              <li>Use the local watchlist as a light copytrading prep feature.</li>
            </ul>
          </div>
        </div>
      </div>
    </>
  );
}

function MetricCard({ label, value }) {
  return (
    <div className="stat-card">
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
    </div>
  );
}
