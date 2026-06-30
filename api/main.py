"""FastAPI backend for the Meridian compliance web product.

Every endpoint is a thin wrapper over the existing engine (`src/`) via
`api/services.py`. The API performs NO computation of its own — it serves what
the deterministic engine produced, so the five constraints hold unchanged.

Run locally:
    uvicorn api.main:app --reload --port 8000
"""
from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

try:  # load a local .env if present (no-op in prod, where env vars are injected)
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from api import services

app = FastAPI(
    title="Meridian Compliance API",
    description="Audit-defensible compliance figures over a knowledge graph. "
                "Numbers come only from the deterministic engine; the LLM writes "
                "narrative behind a firewall.",
    version="1.0.0",
)

# CORS: allow the Next.js dev server and the deployed frontend.
_origins = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000",
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins if o.strip()] or ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "graph_backend": services.BACKEND}


@app.get("/api/firms")
def firms() -> dict:
    """The available firms and the method knobs that distinguish them."""
    return {"firms": services.list_firms()}


@app.get("/api/figures")
def figures(firm: str = Query("A", pattern="^[AB]$")) -> dict:
    """The report table for a firm: every figure + status + reconciliation result."""
    return services.get_figures(firm)


@app.get("/api/figures/{figure_id}")
def figure_detail(figure_id: str, firm: str = Query("A", pattern="^[AB]$")) -> dict:
    """One figure's full trace: value, graph path, source citation, delta vs the
    answer key, and which config rule produced it (the replay viewer)."""
    detail = services.get_figure_detail(firm, figure_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"unknown figure: {figure_id}")
    return detail


@app.get("/api/reconciliation")
def reconciliation(firm: str = Query("A", pattern="^[AB]$")) -> dict:
    """Per-figure pass/fail + delta vs the firm's answer key."""
    return services.get_reconciliation(firm)


@app.get("/api/config/{firm}")
def config(firm: str) -> dict:
    if firm not in ("A", "B"):
        raise HTTPException(status_code=404, detail="firm must be A or B")
    return services.get_config(firm)


@app.get("/api/audit")
def audit(limit: int = Query(500, ge=1, le=5000)) -> dict:
    """The append-only, hash-chained audit log + whether the chain is intact."""
    return services.get_audit(limit)


@app.get("/api/multihop-demo")
def multihop() -> dict:
    """Multi-hop graph query: breach action + owner for a duration breach."""
    return services.multihop_demo()


@app.post("/api/run")
def run(firm: str = Query("A", pattern="^[AB]$")) -> dict:
    """Run the FULL audited pipeline for a firm: compute, reconcile, firewall,
    export report + figures, and append audit events. Returns a summary."""
    try:
        return services.run_full(firm)
    except SystemExit as exc:  # gate held the run for human review
        raise HTTPException(status_code=409,
                            detail=f"run halted (review gate): exit {exc.code}")
