"""Deterministic swing-bias ranker for IDX banking names."""

from __future__ import annotations

from typing import Any


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def score_bank(m: dict[str, Any]) -> float:
    """Higher = more constructive weekly swing bias. Not a trade signal."""
    roe = float(m.get("roe") or 0)
    car = float(m.get("car") or 0)
    npl = float(m.get("npl") or 0.05)
    nim = float(m.get("nim") or 0)
    eg = float(m.get("earnings_growth_yoy") or 0)
    rg = float(m.get("revenue_growth_yoy") or 0)
    mom = float(m.get("weekly_momentum") or 0)
    pe = float(m.get("pe") or 20)
    dy = float(m.get("dividend_yield") or 0)

    quality = (
        0.35 * _clamp(roe / 0.25)
        + 0.25 * _clamp(car / 0.30)
        + 0.25 * _clamp(1.0 - npl / 0.05)
        + 0.15 * _clamp(nim / 0.08)
    )
    growth = 0.55 * _clamp((eg + 0.05) / 0.20) + 0.45 * _clamp((rg + 0.05) / 0.20)
    momentum = _clamp((mom + 0.02) / 0.05)
    value = 0.6 * _clamp(1.0 - (pe - 8) / 25) + 0.4 * _clamp(dy / 0.06)

    return round(
        100 * (0.40 * quality + 0.25 * growth + 0.20 * momentum + 0.15 * value),
        2,
    )


def one_line_why(m: dict[str, Any], score: float) -> str:
    bits = []
    if m.get("roe"):
        bits.append(f"ROE {float(m['roe'])*100:.1f}%")
    if m.get("earnings_growth_yoy") is not None:
        bits.append(f"earn Δ {float(m['earnings_growth_yoy'])*100:+.1f}% YoY")
    if m.get("nim"):
        bits.append(f"NIM {float(m['nim'])*100:.1f}%")
    if m.get("weekly_momentum") is not None:
        bits.append(f"1w mom {float(m['weekly_momentum'])*100:+.1f}%")
    head = ", ".join(bits[:3]) if bits else "balanced bank metrics"
    return f"Score {score:.0f}/100 — {head}."


def explicit_risks(m: dict[str, Any]) -> list[str]:
    risks: list[str] = []
    npl = float(m.get("npl") or 0)
    pe = float(m.get("pe") or 0)
    mom = float(m.get("weekly_momentum") or 0)
    car = float(m.get("car") or 1)
    mcap = float(m.get("market_cap") or 0)

    if npl >= 0.025:
        risks.append(f"Elevated NPL ({npl*100:.1f}%) — asset-quality watch.")
    if pe >= 18:
        risks.append(f"Rich valuation (PE ~{pe:.1f}) — pullback risk on multiple compress.")
    if mom < 0:
        risks.append("Negative weekly momentum — swing bias may lag peers.")
    if car < 0.22:
        risks.append(f"Thinner CAR ({car*100:.1f}%) vs big-4 peers.")
    if mcap and mcap < 50_000_000_000_000:
        risks.append("Smaller float / liquidity vs BBCA–BMRI — wider spreads.")
    risks.append("Macro: BI rate path & IDR FX can reprice bank NIMs quickly.")
    return risks[:4]


def rank_banks(metrics_list: list[dict[str, Any]], top_n: int = 5) -> list[dict[str, Any]]:
    scored = []
    for m in metrics_list:
        s = score_bank(m)
        scored.append(
            {
                **m,
                "score": s,
                "why": one_line_why(m, s),
                "risks": explicit_risks(m),
            }
        )
    scored.sort(key=lambda x: x["score"], reverse=True)
    out = []
    for i, row in enumerate(scored[:top_n], start=1):
        out.append({**row, "rank": i})
    return out
