"""Local research API. All order endpoints are simulation-only; no broker integration exists."""
import json
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query
from market_engine.db import connect, init_db, now_iso
from market_engine.models import SourceDocumentIn, EventIn, PredictionIn, PaperOrderIn
from market_engine.paper import create_paper_order, simulate_fill
from market_engine.evaluation import evaluate_binary_probabilities
from market_engine.patterns import summarize_event_counts, describe_pattern

app = FastAPI(
    title="Market Pattern Intelligence Engine",
    version="0.1.0",
    description="Research, event timelines, probability evaluation and paper trading for Nifty 50. No live orders.",
)


@app.on_event("startup")
def startup() -> None:
    """Initialize the local schema when the service starts."""
    init_db()


@app.get("/health")
def health() -> dict:
    """Basic liveness and operating mode."""
    return {"status": "ok", "mode": "research-and-paper-only", "live_trading": False}


@app.post("/sources", status_code=201)
def create_source(payload: SourceDocumentIn) -> dict:
    """Register a source record while preserving its publication and retrieval times."""
    with connect() as conn:
        try:
            cursor = conn.execute(
                """INSERT INTO source_documents
                (source_type,title,url,published_at,first_seen_at,retrieved_at,content_hash,text_excerpt)
                VALUES (?,?,?,?,?,?,?,?)""",
                (payload.source_type, payload.title, payload.url,
                 payload.published_at.isoformat() if payload.published_at else None,
                 payload.first_seen_at.isoformat(), payload.retrieved_at.isoformat(),
                 payload.content_hash, payload.text_excerpt),
            )
        except Exception as exc:
            if "UNIQUE constraint failed" in str(exc):
                raise HTTPException(409, "Source URL and content hash already registered") from exc
            raise
        return dict(conn.execute("SELECT * FROM source_documents WHERE id=?",
                                 (cursor.lastrowid,)).fetchone())


@app.get("/sources")
def list_sources(limit: int = Query(100, ge=1, le=500)) -> dict:
    """List latest source records."""
    with connect() as conn:
        rows = conn.execute("SELECT * FROM source_documents ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return {"items": [dict(row) for row in rows], "count": len(rows)}


@app.post("/events", status_code=201)
def create_event(payload: EventIn) -> dict:
    """Store an event linked to a source record when available."""
    with connect() as conn:
        if payload.source_id is not None and not conn.execute(
            "SELECT 1 FROM source_documents WHERE id=?", (payload.source_id,)
        ).fetchone():
            raise HTTPException(422, "source_id does not exist")
        cursor = conn.execute(
            """INSERT INTO events
            (symbol,event_type,title,summary,event_at,disclosed_at,source_id,
             evidence_confidence,materiality,status,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (payload.symbol, payload.event_type, payload.title, payload.summary,
             payload.event_at.isoformat() if payload.event_at else None,
             payload.disclosed_at.isoformat() if payload.disclosed_at else None,
             payload.source_id, payload.evidence_confidence, payload.materiality,
             payload.status, now_iso()),
        )
        return dict(conn.execute("SELECT * FROM events WHERE id=?", (cursor.lastrowid,)).fetchone())


@app.get("/events")
def list_events(symbol: str | None = None, event_type: str | None = None,
                limit: int = Query(100, ge=1, le=500)) -> dict:
    """Browse the event timeline by ticker or event family."""
    clauses, params = [], []
    if symbol:
        clauses.append("symbol=?")
        params.append(symbol.strip().upper())
    if event_type:
        clauses.append("event_type=?")
        params.append(event_type)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM events{where} ORDER BY disclosed_at DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
    return {"items": [dict(row) for row in rows], "count": len(rows)}


@app.post("/predictions", status_code=201)
def create_prediction(payload: PredictionIn) -> dict:
    """Persist a forecast before its outcome is known."""
    with connect() as conn:
        cursor = conn.execute(
            """INSERT INTO predictions
            (symbol,target_name,horizon_sessions,probability,model_name,model_version,
             evidence_note,as_of) VALUES (?,?,?,?,?,?,?,?)""",
            (payload.symbol, payload.target_name, payload.horizon_sessions, payload.probability,
             payload.model_name, payload.model_version, payload.evidence_note, payload.as_of.isoformat()),
        )
        return dict(conn.execute("SELECT * FROM predictions WHERE id=?",
                                 (cursor.lastrowid,)).fetchone())


@app.get("/predictions")
def list_predictions(resolved: bool | None = None, limit: int = Query(100, ge=1, le=500)) -> dict:
    """List forecasts, preserving the original probability and timestamp."""
    where = " WHERE outcome IS NOT NULL" if resolved is True else (
        " WHERE outcome IS NULL" if resolved is False else ""
    )
    with connect() as conn:
        rows = conn.execute(f"SELECT * FROM predictions{where} ORDER BY as_of DESC LIMIT ?",
                            (limit,)).fetchall()
    return {"items": [dict(row) for row in rows], "count": len(rows)}


@app.post("/predictions/{prediction_id}/outcome")
def resolve_prediction(prediction_id: int, outcome: int = Query(..., ge=0, le=1),
                       outcome_at: datetime = Query(...)) -> dict:
    """Record a binary outcome exactly once; never silently rewrite historical forecasts."""
    with connect() as conn:
        row = conn.execute("SELECT * FROM predictions WHERE id=?", (prediction_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Prediction not found")
        if row["outcome"] is not None:
            raise HTTPException(409, "Outcome already recorded and is immutable")
        if outcome_at < datetime.fromisoformat(row["as_of"]):
            raise HTTPException(422, "Outcome timestamp cannot precede prediction timestamp")
        conn.execute("UPDATE predictions SET outcome=?, outcome_at=? WHERE id=?",
                     (outcome, outcome_at.isoformat(), prediction_id))
        return dict(conn.execute("SELECT * FROM predictions WHERE id=?", (prediction_id,)).fetchone())


@app.get("/patterns/event-frequency")
def event_frequency(symbol: str | None = None, lookback_days: int = Query(90, ge=1, le=3650)) -> dict:
    """Describe historical event frequencies; this is not itself a predictive signal."""
    with connect() as conn:
        if symbol:
            rows = conn.execute("SELECT symbol,event_type,disclosed_at FROM events WHERE symbol=?",
                                (symbol.strip().upper(),)).fetchall()
        else:
            rows = conn.execute("SELECT symbol,event_type,disclosed_at FROM events").fetchall()
    counts = summarize_event_counts([dict(row) for row in rows], lookback_days=lookback_days)
    return {"symbol": symbol.upper() if symbol else None, "lookback_days": lookback_days,
            "patterns": describe_pattern(counts), "interpretation": "descriptive_frequency_only"}


@app.get("/evaluation/summary")
def evaluation_summary() -> dict:
    """Compute probability metrics for resolved forecasts."""
    with connect() as conn:
        rows = conn.execute("SELECT probability,outcome FROM predictions WHERE outcome IS NOT NULL").fetchall()
    metrics = evaluate_binary_probabilities([r["probability"] for r in rows], [r["outcome"] for r in rows])
    return metrics.__dict__


@app.post("/paper/orders", status_code=201)
def submit_paper_order(payload: PaperOrderIn) -> dict:
    """Create a simulated order record only. This never contacts a broker."""
    order_id = create_paper_order(payload)
    with connect() as conn:
        return dict(conn.execute("SELECT * FROM paper_orders WHERE id=?", (order_id,)).fetchone())


@app.post("/paper/orders/{order_id}/fill")
def fill_paper_order(order_id: int, fill_price: float = Query(..., gt=0),
                     fill_time: datetime = Query(...)) -> dict:
    """Record a simulated fill only after the eligible time."""
    try:
        simulate_fill(order_id, fill_price, fill_time)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    with connect() as conn:
        return dict(conn.execute("SELECT * FROM paper_orders WHERE id=?", (order_id,)).fetchone())


@app.get("/paper/orders")
def list_paper_orders(limit: int = Query(100, ge=1, le=500)) -> dict:
    """List simulated orders."""
    with connect() as conn:
        rows = conn.execute("SELECT * FROM paper_orders ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return {"items": [dict(row) for row in rows], "count": len(rows)}
