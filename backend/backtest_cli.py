"""
Backtest CLI — Quick terminal tool to test insider detection on any wallet.

Usage:
    python backtest_cli.py <wallet_address>

Example:
    python backtest_cli.py 0xdde15ebd95330ce69136dc0ccd810d22382e02c5
"""

import asyncio
import sys

from app.services.backtest import run_backtest


def _format_result(result: dict) -> str:
    """Format the backtest result for terminal display."""
    if "error" in result:
        return f"\n❌ Error: {result['error']}\n"

    lines = []
    addr = result["address"]
    short_addr = f"{addr[:6]}...{addr[-4:]}"

    lines.append("")
    lines.append(f"{'=' * 60}")
    lines.append(f"  Backtest: {result['username']} ({short_addr})")
    lines.append(f"{'=' * 60}")

    # Summary
    s = result.get("summary", {})
    lines.append("")
    lines.append(f"  Account Age:     {s.get('account_age_days', '?')} days")
    lines.append(f"  Markets Traded:  {s.get('markets_traded', 0)}")
    lines.append(f"  Trade Count:     {s.get('trade_count', 0)} buys")
    lines.append(f"  Total USDC In:   ${s.get('total_usdc_invested', 0):,.2f}")
    lines.append(f"  Total Redeemed:  ${s.get('total_redeemed', 0):,.2f}")
    lines.append(f"  Win Rate:        {s.get('win_rate', 0):.1f}%")

    # Factor breakdown
    lines.append("")
    lines.append(f"  {'-' * 40}")
    lines.append(f"  Scoring Breakdown")
    lines.append(f"  {'-' * 40}")

    factors = result.get("factors", {})
    factor_order = [
        ("win_rate_anomaly", "Win Rate Anomaly"),
        ("bet_concentration", "Bet Concentration"),
        ("timing_signal", "Timing Signal"),
        ("entry_price_edge", "Entry Price Edge"),
        ("account_pattern", "Account Pattern"),
        ("position_size_signal", "Position Size Signal"),
    ]
    for key, label in factor_order:
        f = factors.get(key, {})
        val = f.get("value", 0)
        detail = f.get("detail", "")
        bar = "#" * int(val * 20) + "." * (20 - int(val * 20))
        lines.append(f"  {label:>22s}  {val:.2f}  {bar}  {detail}")

    # Verdict
    lines.append("")
    lines.append(f"{'=' * 60}")
    lines.append(f"  SCORE: {result['score']:.1f}/100  --  {result['verdict']}")
    if result.get("elevated_factors"):
        lines.append(f"  Elevated: {', '.join(result['elevated_factors'])}")
    lines.append(f"{'=' * 60}")

    # Markets
    markets = result.get("markets", [])
    if markets:
        lines.append("")
        lines.append(f"  Markets:")
        for m in markets[:10]:
            status = "[WIN]" if m.get("won") else ("[LOSS]" if m.get("resolved") else "[OPEN]")
            lines.append(
                f"    {status}  ${m['usdc_invested']:>10,.2f}  "
                f"@ {m['avg_entry_price']:.2f}  {m['title'][:50]}"
            )

    lines.append("")
    return "\n".join(lines)


async def main():
    if len(sys.argv) < 2:
        print("Usage: python backtest_cli.py <wallet_address>")
        print("Example: python backtest_cli.py 0xdde15ebd95330ce69136dc0ccd810d22382e02c5")
        sys.exit(1)

    address = sys.argv[1]
    print(f"\nRunning backtest for {address}...")

    result = await run_backtest(address)
    print(_format_result(result))


if __name__ == "__main__":
    asyncio.run(main())
