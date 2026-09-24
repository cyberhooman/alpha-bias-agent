"""Sectors Financial API client (live + deterministic mock).

Verified from https://docs.sectors.app (2026):
  Base URL : https://api.sectors.app/v2
  Auth     : Authorization header with raw API key (NO "Bearer " prefix)
             per official quick-start / agent-skills docs.
  Screen   : GET /v2/companies/?where=sub_sector='banks'&order_by=-market_cap
             (MCP concept: fetch-companies-by-subsector)
  Report   : GET /v2/company/report/{symbol}/?sections=overview,financials,valuation
             (MCP concept: fetch-company-report)
"""

from __future__ import annotations

import copy
import logging
import os
import time
from typing import Any, Callable, Optional

import httpx

logger = logging.getLogger("alpha_bias.sectors")

BASE_URL = "https://api.sectors.app/v2"

# Deterministic mock universe — Indonesian banking names with plausible metrics.
MOCK_BANKS: list[dict[str, Any]] = [
    {
        "symbol": "BBCA",
        "company_name": "PT Bank Central Asia Tbk.",
        "market_cap": 920_000_000_000_000,
        "last_close_price": 9750,
        "pe": 22.4,
        "pb": 4.1,
        "roe": 0.215,
        "roa": 0.032,
        "nim": 0.055,
        "npl": 0.012,
        "car": 0.265,
        "revenue_growth_yoy": 0.098,
        "earnings_growth_yoy": 0.112,
        "dividend_yield": 0.028,
        "weekly_momentum": 0.018,
    },
    {
        "symbol": "BBRI",
        "company_name": "PT Bank Rakyat Indonesia (Persero) Tbk.",
        "market_cap": 680_000_000_000_000,
        "last_close_price": 4650,
        "pe": 11.8,
        "pb": 2.2,
        "roe": 0.188,
        "roa": 0.028,
        "nim": 0.068,
        "npl": 0.028,
        "car": 0.245,
        "revenue_growth_yoy": 0.075,
        "earnings_growth_yoy": 0.064,
        "dividend_yield": 0.055,
        "weekly_momentum": 0.012,
    },
    {
        "symbol": "BMRI",
        "company_name": "PT Bank Mandiri (Persero) Tbk.",
        "market_cap": 610_000_000_000_000,
        "last_close_price": 6250,
        "pe": 10.5,
        "pb": 1.9,
        "roe": 0.205,
        "roa": 0.029,
        "nim": 0.052,
        "npl": 0.018,
        "car": 0.228,
        "revenue_growth_yoy": 0.088,
        "earnings_growth_yoy": 0.095,
        "dividend_yield": 0.048,
        "weekly_momentum": 0.015,
    },
    {
        "symbol": "BBNI",
        "company_name": "PT Bank Negara Indonesia (Persero) Tbk.",
        "market_cap": 195_000_000_000_000,
        "last_close_price": 4850,
        "pe": 9.2,
        "pb": 1.4,
        "roe": 0.152,
        "roa": 0.021,
        "nim": 0.048,
        "npl": 0.022,
        "car": 0.215,
        "revenue_growth_yoy": 0.062,
        "earnings_growth_yoy": 0.055,
        "dividend_yield": 0.042,
        "weekly_momentum": 0.008,
    },
    {
        "symbol": "BRIS",
        "company_name": "PT Bank Syariah Indonesia Tbk.",
        "market_cap": 125_000_000_000_000,
        "last_close_price": 2680,
        "pe": 14.6,
        "pb": 2.6,
        "roe": 0.168,
        "roa": 0.019,
        "nim": 0.058,
        "npl": 0.025,
        "car": 0.232,
        "revenue_growth_yoy": 0.145,
        "earnings_growth_yoy": 0.132,
        "dividend_yield": 0.015,
        "weekly_momentum": 0.022,
    },
    {
        "symbol": "BTPS",
        "company_name": "PT Bank BTPN Syariah Tbk.",
        "market_cap": 18_500_000_000_000,
        "last_close_price": 1450,
        "pe": 8.1,
        "pb": 1.1,
        "roe": 0.142,
        "roa": 0.035,
        "nim": 0.112,
        "npl": 0.031,
        "car": 0.348,
        "revenue_growth_yoy": 0.041,
        "earnings_growth_yoy": 0.028,
        "dividend_yield": 0.038,
        "weekly_momentum": -0.005,
    },
]


TimelineCallback = Callable[[dict[str, Any]], None]


def use_mock() -> bool:
    """Default MOCK_SECTORS=1. Live only when key set AND MOCK_SECTORS explicitly not 1."""
    mock_flag = os.getenv("MOCK_SECTORS", "1").strip()
    if mock_flag == "1":
        return True
    if not os.getenv("SECTORS_API_KEY"):
        logger.warning("MOCK_SECTORS!=1 but SECTORS_API_KEY unset — falling back to mock")
        return True
    return False


class SectorsClient:
    """Thin REST client that always emits timeline + console logs."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        mock: Optional[bool] = None,
        on_call: Optional[TimelineCallback] = None,
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key or os.getenv("SECTORS_API_KEY", "")
        self.mock = use_mock() if mock is None else mock
        self.on_call = on_call
        self.timeout = timeout
        self.mode = "mock" if self.mock else "live"

    def _emit(self, entry: dict[str, Any]) -> None:
        line = (
            f"[sectors] {entry['method']} {entry['path']} · "
            f"{entry['status']} · {entry['latency_ms']}ms"
        )
        logger.info(line)
        print(line, flush=True)
        if self.on_call:
            self.on_call(entry)

    def _auth_headers(self) -> dict[str, str]:
        # Official docs: raw key in Authorization (no Bearer prefix).
        return {"Authorization": self.api_key}

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        mock_body: Any = None,
        step: str = "sectors",
    ) -> Any:
        display_path = path
        if params:
            qs = "&".join(f"{k}={v}" for k, v in params.items())
            display_path = f"{path}?{qs}"

        if self.mock:
            t0 = time.perf_counter()
            time.sleep(0.045)
            latency = int((time.perf_counter() - t0) * 1000)
            body = copy.deepcopy(mock_body)
            self._emit(
                {
                    "step": step,
                    "method": method,
                    "path": display_path,
                    "status": 200,
                    "latency_ms": latency,
                    "summary": _summarize(body),
                    "error": None,
                }
            )
            return body

        url = f"{BASE_URL}{path}"
        t0 = time.perf_counter()
        status = 0
        error: Optional[str] = None
        body: Any = None
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.request(
                    method, url, headers=self._auth_headers(), params=params
                )
            status = resp.status_code
            latency = int((time.perf_counter() - t0) * 1000)
            try:
                body = resp.json()
            except Exception:
                body = {"raw": resp.text[:500]}
            if resp.is_error:
                error = f"HTTP {status}"
                self._emit(
                    {
                        "step": step,
                        "method": method,
                        "path": display_path,
                        "status": status,
                        "latency_ms": latency,
                        "summary": _summarize(body),
                        "error": error,
                    }
                )
                resp.raise_for_status()
            self._emit(
                {
                    "step": step,
                    "method": method,
                    "path": display_path,
                    "status": status,
                    "latency_ms": latency,
                    "summary": _summarize(body),
                    "error": None,
                }
            )
            return body
        except httpx.HTTPError as exc:
            latency = int((time.perf_counter() - t0) * 1000)
            self._emit(
                {
                    "step": step,
                    "method": method,
                    "path": display_path,
                    "status": status or 0,
                    "latency_ms": latency,
                    "summary": None,
                    "error": str(exc),
                }
            )
            raise

    def fetch_companies_by_subsector(
        self,
        sub_sector: str = "banks",
        *,
        order_by: str = "-market_cap",
        limit: int = 12,
        step: str = "screen",
    ) -> list[dict[str, Any]]:
        """MCP: fetch-companies-by-subsector → GET /v2/companies/."""
        path = "/companies/"
        params = {
            "where": f"sub_sector='{sub_sector}'",
            "order_by": order_by,
            "n_stock": str(limit),
        }
        mock_rows = [
            {
                "symbol": b["symbol"],
                "company_name": b["company_name"],
                "market_cap": b["market_cap"],
                "last_close_price": b["last_close_price"],
                "sub_sector": "banks",
            }
            for b in MOCK_BANKS[:limit]
        ]
        data = self._request(
            "GET", path, params=params, mock_body=mock_rows, step=step
        )
        if isinstance(data, dict):
            for key in ("results", "data", "companies", "items"):
                if key in data and isinstance(data[key], list):
                    return data[key]
            return [data]
        if isinstance(data, list):
            return data
        return []

    def fetch_company_report(
        self,
        symbol: str,
        *,
        sections: str = "overview,financials,valuation",
        step: str = "fundamentals",
    ) -> dict[str, Any]:
        """MCP: fetch-company-report → GET /v2/company/report/{symbol}/."""
        path = f"/company/report/{symbol}/"
        params = {"sections": sections}
        bank = next((b for b in MOCK_BANKS if b["symbol"] == symbol), None)
        if bank is None:
            bank = {
                "symbol": symbol,
                "company_name": symbol,
                "market_cap": 0,
                "last_close_price": 0,
                "pe": 12.0,
                "pb": 1.5,
                "roe": 0.12,
                "roa": 0.015,
                "nim": 0.04,
                "npl": 0.03,
                "car": 0.2,
                "revenue_growth_yoy": 0.05,
                "earnings_growth_yoy": 0.04,
                "dividend_yield": 0.03,
                "weekly_momentum": 0.0,
            }
        mock_body = {
            "symbol": f"{bank['symbol']}.JK",
            "company_name": bank["company_name"],
            "overview": {
                "sector": "Financials",
                "sub_sector": "Banks",
                "market_cap": bank["market_cap"],
                "last_close_price": bank["last_close_price"],
                "daily_close_change": bank.get("weekly_momentum", 0) / 5,
            },
            "valuation": {
                "last_close_price": bank["last_close_price"],
                "forward_pe": bank["pe"] * 0.92,
                "historical_valuation": [
                    {"year": 2025, "pe": bank["pe"], "pb": bank["pb"]}
                ],
            },
            "financials": {
                "yoy_quarter_revenue_growth": bank["revenue_growth_yoy"],
                "yoy_quarter_earnings_growth": bank["earnings_growth_yoy"],
                "historical_financial_ratio": [
                    {
                        "year": "2025",
                        "profitability": {
                            "roa": bank["roa"],
                            "roe": bank["roe"],
                            "net_interest_margin": bank["nim"],
                        },
                        "capital": {"capital_adequacy_ratio": bank["car"]},
                        "asset_quality": {"npl": bank["npl"]},
                    }
                ],
                "bank_metrics": {
                    "nim": bank["nim"],
                    "npl": bank["npl"],
                    "car": bank["car"],
                    "dividend_yield": bank["dividend_yield"],
                    "weekly_momentum": bank["weekly_momentum"],
                },
            },
        }
        return self._request(
            "GET", path, params=params, mock_body=mock_body, step=step
        )


def _summarize(body: Any, max_items: int = 5) -> Any:
    if body is None:
        return None
    if isinstance(body, list):
        slim = []
        for row in body[:max_items]:
            if isinstance(row, dict):
                slim.append(
                    {
                        k: row.get(k)
                        for k in (
                            "symbol",
                            "company_name",
                            "market_cap",
                            "last_close_price",
                        )
                        if k in row
                    }
                    or {k: row[k] for k in list(row)[:4]}
                )
            else:
                slim.append(row)
        return {"count": len(body), "sample": slim}
    if isinstance(body, dict):
        keys = list(body.keys())
        out: dict[str, Any] = {"keys": keys[:12]}
        if "symbol" in body:
            out["symbol"] = body["symbol"]
        if "company_name" in body:
            out["company_name"] = body["company_name"]
        if "overview" in body and isinstance(body["overview"], dict):
            ov = body["overview"]
            out["overview"] = {
                k: ov.get(k)
                for k in ("sub_sector", "market_cap", "last_close_price")
                if k in ov
            }
        if "financials" in body and isinstance(body["financials"], dict):
            fin = body["financials"]
            out["financials"] = {
                k: fin.get(k)
                for k in (
                    "yoy_quarter_revenue_growth",
                    "yoy_quarter_earnings_growth",
                    "bank_metrics",
                )
                if k in fin
            }
        return out
    return {"type": type(body).__name__}


def normalize_report_metrics(report: dict[str, Any]) -> dict[str, Any]:
    """Flatten live or mock report into ranker-friendly metrics."""
    symbol = str(report.get("symbol", "")).replace(".JK", "").replace(".jk", "")
    name = report.get("company_name") or symbol
    overview = report.get("overview") or {}
    valuation = report.get("valuation") or {}
    financials = report.get("financials") or {}
    bank = financials.get("bank_metrics") or {}

    pe = None
    pb = None
    hist = valuation.get("historical_valuation")
    if isinstance(hist, list) and hist:
        pe = hist[-1].get("pe")
        pb = hist[-1].get("pb")
    if pe is None:
        pe = valuation.get("forward_pe")

    roe = roa = nim = npl = car = None
    ratios = financials.get("historical_financial_ratio")
    if isinstance(ratios, list) and ratios:
        latest = ratios[-1]
        prof = latest.get("profitability") or {}
        cap = latest.get("capital") or {}
        aq = latest.get("asset_quality") or {}
        roe = prof.get("roe")
        roa = prof.get("roa")
        nim = prof.get("net_interest_margin")
        car = cap.get("capital_adequacy_ratio")
        npl = aq.get("npl")

    return {
        "symbol": symbol,
        "company_name": name,
        "market_cap": overview.get("market_cap") or 0,
        "last_close_price": overview.get("last_close_price")
        or valuation.get("last_close_price")
        or 0,
        "pe": float(pe or bank.get("pe") or 12.0),
        "pb": float(pb or 1.5),
        "roe": float(roe if roe is not None else bank.get("roe", 0.12)),
        "roa": float(roa if roa is not None else bank.get("roa", 0.015)),
        "nim": float(nim if nim is not None else bank.get("nim", 0.04)),
        "npl": float(npl if npl is not None else bank.get("npl", 0.03)),
        "car": float(car if car is not None else bank.get("car", 0.2)),
        "revenue_growth_yoy": float(
            financials.get("yoy_quarter_revenue_growth")
            or bank.get("revenue_growth_yoy")
            or 0.05
        ),
        "earnings_growth_yoy": float(
            financials.get("yoy_quarter_earnings_growth")
            or bank.get("earnings_growth_yoy")
            or 0.04
        ),
        "dividend_yield": float(bank.get("dividend_yield") or 0.03),
        "weekly_momentum": float(bank.get("weekly_momentum") or 0.0),
    }
