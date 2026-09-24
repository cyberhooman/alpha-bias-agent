# Alpha Bias Agent

**Sectors Hackathon 2026 — Track 1 MVP**

Indo swing trader asks: *Bias minggu ini untuk banking?*

Custom orchestration (not a single LLM+MCP prompt):

1. **screen** — list IDX names in subsector (`banks`)
2. **fundamentals** — company report per ticker
3. **rank** — deterministic swing-bias scorer
4. **explain_risk** — one-line why + explicit risks

Output: ≤5 ranked IDX tickers. **No trade execution / no broker code.**

---

## Sectors REST API (verified)

Looked up from [docs.sectors.app](https://docs.sectors.app) / [llms.txt](https://docs.sectors.app/llms.txt) (2026):

| Item | Value |
|------|--------|
| Base URL | `https://api.sectors.app/v2` |
| Auth | `Authorization: <API_KEY>` — **raw key, no `Bearer` prefix** (official quick-start & agent-skills recipes) |
| Screen (≈ MCP `fetch-companies-by-subsector`) | `GET /v2/companies/?where=sub_sector='banks'&order_by=-market_cap` |
| Report (≈ MCP `fetch-company-report`) | `GET /v2/company/report/{symbol}/?sections=overview,financials,valuation` |

v1 (`/v1/*`) was discontinued 2026-05-11 (HTTP 410). This project uses **v2 only**.

---

## Env vars

| Var | Default | Meaning |
|-----|---------|---------|
| `MOCK_SECTORS` | `1` | Deterministic Indonesian banking mock (BBCA, BBRI, BMRI, BBNI, BRIS, BTPS) |
| `SECTORS_API_KEY` | _(empty)_ | Live key from https://sectors.app/api |
| `HOST` / `PORT` | `0.0.0.0` / `8000` | Uvicorn bind |

Live mode requires **both** `SECTORS_API_KEY` set **and** `MOCK_SECTORS=0` (or any value other than `1`).

Copy `.env.example` → `.env` (never commit secrets).

---

## Setup & run (one command)

```bash
cd /workspace/alpha-bias-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Mock happy path (default)
MOCK_SECTORS=1 python -m uvicorn alpha_bias_agent.app:app --host 0.0.0.0 --port 8000
```

Open **http://127.0.0.1:8000** — demo question is prefilled / one-click.

### Live API (optional)

```bash
export SECTORS_API_KEY="your_key_here"
MOCK_SECTORS=0 python -m uvicorn alpha_bias_agent.app:app --host 0.0.0.0 --port 8000
```

---

## Exact demo path for judges

1. `cd /workspace/alpha-bias-agent && source .venv/bin/activate`
2. `MOCK_SECTORS=1 python -m uvicorn alpha_bias_agent.app:app --host 0.0.0.0 --port 8000`
3. Browser → `http://127.0.0.1:8000`
4. Click suggestion **Bias minggu ini untuk banking?** (or press **Run**)
5. **Left**: ≤5 ranked banking tickers with one-line why + risks  
6. **Right**: step timeline — each Sectors call as `METHOD path · status · Nms` with expandable JSON (also printed to console)

Health check:

```bash
curl -s http://127.0.0.1:8000/api/health | python -m json.tool
```

API-only:

```bash
curl -s -X POST http://127.0.0.1:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Bias minggu ini untuk banking?","top_n":5}' | python -m json.tool
```

---

## Package layout

```
alpha-bias-agent/
├── alpha_bias_agent/
│   ├── __init__.py
│   ├── app.py              # FastAPI + static UI
│   ├── orchestrator.py     # 4-step pipeline
│   ├── ranker.py           # score / why / risks
│   ├── sectors_client.py   # live + mock REST
│   ├── models.py
│   └── static/index.html   # chat + timeline
├── .env.example
├── requirements.txt
└── README.md
```

---

## Disclaimer

Research bias helper only. Not investment advice. Does not place orders.
