"""Custom 4-step orchestration (NOT a single LLM+MCP prompt).

1. screen → 2. fundamentals → 3. rank → 4. explain_risk
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Optional

from .models import BiasResponse, RankedTicker, TimelineEntry
from .ranker import rank_banks
from .sectors_client import SectorsClient, normalize_report_metrics

logger = logging.getLogger("alpha_bias.orchestrator")

DEMO_QUESTION = "Bias minggu ini untuk banking?"

SUBSECTOR_ALIASES = {
    "banking": "banks",
    "bank": "banks",
    "banks": "banks",
    "perbankan": "banks",
}


def detect_subsector(query: str) -> str:
    q = query.lower()
    for alias, slug in SUBSECTOR_ALIASES.items():
        if alias in q:
            return slug
    return "banks"


class Orchestrator:
    def __init__(self, client: Optional[SectorsClient] = None) -> None:
        self._timeline: list[dict[str, Any]] = []
        self.client = client or SectorsClient(on_call=self._on_call)

    def _on_call(self, entry: dict[str, Any]) -> None:
        self._timeline.append(entry)

    def _push_local(
        self, step: str, method: str, path: str, summary: Any, t0: float
    ) -> None:
        latency = int((time.perf_counter() - t0) * 1000)
        entry = {
            "step": step,
            "method": method,
            "path": path,
            "status": 200,
            "latency_ms": max(latency, 1),
            "summary": summary,
            "error": None,
        }
        line = f"[local] {method} {path} · 200 · {entry['latency_ms']}ms"
        logger.info(line)
        print(line, flush=True)
        self._timeline.append(entry)

    def run(self, query: str, top_n: int = 5) -> BiasResponse:
        self._timeline = []
        self.client.on_call = self._on_call

        subsector = detect_subsector(query)
        logger.info(
            "pipeline start query=%r subsector=%s mode=%s",
            query,
            subsector,
            self.client.mode,
        )

        # 1. SCREEN
        companies = self.client.fetch_companies_by_subsector(
            subsector, limit=12, step="screen"
        )
        symbols: list[str] = []
        for c in companies:
            sym = str(c.get("symbol") or c.get("ticker") or "").upper()
            sym = re.sub(r"\.(JK|jk)$", "", sym)
            if sym and sym not in symbols:
                symbols.append(sym)
        if not symbols:
            raise RuntimeError(f"No companies returned for subsector={subsector}")

        screen_syms = symbols[:8]

        # 2. FUNDAMENTALS
        metrics_list: list[dict[str, Any]] = []
        for sym in screen_syms:
            report = self.client.fetch_company_report(sym, step="fundamentals")
            metrics_list.append(normalize_report_metrics(report))

        # 3. RANK
        t0 = time.perf_counter()
        ranked = rank_banks(metrics_list, top_n=top_n)
        self._push_local(
            "rank",
            "LOCAL",
            "ranker.rank_banks",
            {
                "input_n": len(metrics_list),
                "top_n": top_n,
                "order": [r["symbol"] for r in ranked],
                "scores": {r["symbol"]: r["score"] for r in ranked},
            },
            t0,
        )

        # 4. EXPLAIN_RISK
        t0 = time.perf_counter()
        tickers = [
            RankedTicker(
                rank=r["rank"],
                symbol=r["symbol"],
                company_name=r["company_name"],
                score=r["score"],
                why=r["why"],
                risks=r["risks"],
                metrics={
                    k: r.get(k)
                    for k in (
                        "pe",
                        "pb",
                        "roe",
                        "roa",
                        "nim",
                        "npl",
                        "car",
                        "revenue_growth_yoy",
                        "earnings_growth_yoy",
                        "dividend_yield",
                        "weekly_momentum",
                        "market_cap",
                        "last_close_price",
                    )
                },
            )
            for r in ranked
        ]
        self._push_local(
            "explain_risk",
            "LOCAL",
            "ranker.explain_risk",
            {
                "tickers": [
                    {"symbol": t.symbol, "why": t.why, "risks": t.risks}
                    for t in tickers
                ]
            },
            t0,
        )

        return BiasResponse(
            query=query,
            subsector=subsector,
            mode=self.client.mode,
            tickers=tickers,
            timeline=[TimelineEntry(**e) for e in self._timeline],
        )
