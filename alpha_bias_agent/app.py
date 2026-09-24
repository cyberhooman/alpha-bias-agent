"""FastAPI app — chat UI + bias pipeline API."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .orchestrator import DEMO_QUESTION, Orchestrator
from .sectors_client import BASE_URL, use_mock

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("alpha_bias.app")

STATIC_DIR = Path(__file__).resolve().parent / "static"
INDEX_HTML = STATIC_DIR / "index.html"

app = FastAPI(
    title="Alpha Bias Agent",
    description=(
        "Sectors Hackathon 2026 Track 1 — Indo swing bias for banking "
        "(screen → fundamentals → rank → explain_risk). No trade execution."
    ),
    version="0.1.0",
)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    top_n: int = Field(5, ge=1, le=5)


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "mock": use_mock(),
        "sectors_base": BASE_URL,
        "demo_question": DEMO_QUESTION,
        "has_api_key": bool(os.getenv("SECTORS_API_KEY")),
        "index_html": INDEX_HTML.exists(),
        "module": "alpha_bias_agent.app:app",
    }


@app.get("/api/demo-question")
def demo_question() -> dict:
    return {"question": DEMO_QUESTION}


@app.post("/api/chat")
def chat(req: ChatRequest) -> dict:
    """Run the 4-step bias pipeline; return tickers + timeline/api_calls."""
    logger.info("chat request: %r", req.message)
    try:
        orch = Orchestrator()
        result = orch.run(req.message.strip(), top_n=req.top_n)
        payload = result.model_dump()
        payload["api_calls"] = payload["timeline"]
        return payload
    except Exception as exc:
        logger.exception("pipeline failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/")
def index():
    if not INDEX_HTML.exists():
        return HTMLResponse(
            f"<h1>Alpha Bias Agent</h1><p>static/index.html missing at {INDEX_HTML}</p>",
            status_code=500,
        )
    return FileResponse(INDEX_HTML, media_type="text/html")


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def main() -> None:
    import uvicorn

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        "alpha_bias_agent.app:app",
        host=host,
        port=port,
        reload=False,
    )


if __name__ == "__main__":
    main()
