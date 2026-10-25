"""FastAPI endpoints for local research workflows."""
from fastapi import FastAPI, HTTPException
from .db import connect, init_db, now_iso, row_to_dict
from .models import EventIn, PredictionIn, PaperOrderIn, SourceDocumentIn
from .paper import create_paper_order

app = FastAPI(
    title="Market Pattern Intelligence Engine",
    version="0.1.0",
    description="Research-only API for dated events, auditable forecasts and paper simulation.",
)


@app.on_event("startup")
def startup() -> None:
    """Ensure local tables exist before requests are served."""
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    """Health endpoint that does not expose credentials or local paths."""
    return {"status": "ok", "mode": "research_only", "timestamp": now_iso()}


@app.post("/sources", status_code=201)
def add_source(source: SourceDocumentIn) -> dict:
    """Store source metadata; content hashes are unique when supplied."""
    now = now_iso()
    try:
        with connect() as conn:
            cur = conn.execute(
                """INSERT INTO source_documents
                (source_type,title,url,published_at,first_seen_at,retrieved_at,content_hash,text_excerpt,created_at)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (source.source_type, source.title, source.url,
                 source.published_at.isoformat() if source.published_at else None,
                 source.first_seen_at.isoformat(), source.retrieved_at.isoformat(),
                 source.content_hash, source.text_excerpt, now),
            )
            source_id = int(cur.lastrowid)
    except Exception as exc:
        raise HTTPException(status_code=409, detail="Could not store source; possible duplicate hash.") from exc
    return {"id": source_id, "title": source.title}


@app.post("/events", status_code=201)
def add_event(event: EventIn) -> dict:
    """Store one structured event and preserve disclosure time."""
    now = now_iso()
    with connect() as conn:
        if event.source_id is not None:
            source = conn.execute("SELECT id FROM source_documents WHERE id=?", (event.source_id,)).fetchone()
            if source is None:
                raise HTTPException(status_code=404, detail="source_id does not exist")
        cur = conn.execute(
            """INSERT INTO events
            (symbol,event_type,title,summary,event_at,disclosed_at,source_id,evidence_confidence,materiality,status,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (event.symbol, event.event_type, event.title, event.summary,
             event.event_at.isoformat() if event.event_at else None,
             event.disclosed_at.isoformat() if event.disclosed_at else None,
             event.source_id, event.evidence_confidence, event.materiality, event.status, now),
        )
        return {"id": int(cur.lastrowid), "symbol": event.symbol, "event_type": event.event_type}


@app.get("/events")
def list_events(symbol: str | None = None, limit: int = 100) -> dict:
    """List recent events, optionally for one symbol."""
    if not 1 <= limit <= 500:
        raise HTTPException(status_code=422, detail="limit must be 1..500")
    with connect() as conn:
        if symbol:
            rows = conn.execute(
                "SELECT * FROM events WHERE symbol=? ORDER BY disclosed_at DESC LIMIT ?",
                (symbol.strip().upper(), limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM events ORDER BY disclosed_at DESC LIMIT ?", (limit,)
            ).fetchall()
    return {"items": [row_to_dict(row) for row in rows], "count": len(rows)}


@app.post("/predictions", status_code=201)
def save_prediction(prediction: PredictionIn) -> dict:
    """Append a forecast; outcome is stored separately when known."""
    now = now_iso()
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO predictions
            (symbol,target_name,horizon_sessions,probability,model_name,model_version,evidence_note,as_of,created_at)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (prediction.symbol.strip().upper(), prediction.target_name, prediction.horizon_sessions,
             prediction.probability, prediction.model_name, prediction.model_version,
             prediction.evidence_note, prediction.as_of.isoformat(), now),
        )
        prediction_id = int(cur.lastrowid)
    return {"id": prediction_id, "as_of": prediction.as_of.isoformat(), "status": "forecast_saved"}


@app.get("/predictions")
def list_predictions(limit: int = 100) -> dict:
    """Return stored forecasts newest first."""
    if not 1 <= limit <= 500:
        raise HTTPException(status_code=422, detail="limit must be 1..500")
    with connect() as conn:
        rows = conn.execute("SELECT * FROM predictions ORDER BY as_of DESC LIMIT ?", (limit,)).fetchall()
    return {"items": [row_to_dict(row) for row in rows], "count": len(rows)}


@app.post("/paper-orders", status_code=201)
def add_paper_order(order: PaperOrderIn) -> dict:
    """Create a simulated order only; no broker integration exists."""
    try:
        order_id = create_paper_order(order)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Could not create paper order") from exc
    return {"id": order_id, "status": "PENDING", "mode": "paper_only"}


@app.get("/paper-orders")
def list_paper_orders(limit: int = 100) -> dict:
    """List paper orders, newest first."""
    if not 1 <= limit <= 500:
        raise HTTPException(status_code=422, detail="limit must be 1..500")
    with connect() as conn:
        rows = conn.execute("SELECT * FROM paper_orders ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return {"items": [row_to_dict(row) for row in rows], "count": len(rows)}


@app.get("/patterns/event-counts")
def event_pattern_counts(lookback_days: int = 90, symbol: str | None = None) -> dict:
    """Summarize disclosed event frequencies in a point-in-time window.

    Counts are descriptive only: frequency does not imply causation or predict an outcome.
    Events without a disclosure timestamp are excluded because their availability is unknown.
    """
    from datetime import datetime, timedelta, timezone
    from .patterns import describe_pattern, summarize_event_counts

    if not 1 <= lookback_days <= 3650:
        raise HTTPException(status_code=422, detail="lookback_days must be between 1 and 3650")
    as_of = datetime.now(timezone.utc)
    cutoff = as_of - timedelta(days=lookback_days)
    query = "SELECT event_type, disclosed_at FROM events WHERE disclosed_at IS NOT NULL AND disclosed_at >= ? AND disclosed_at <= ?"
    params: list = [cutoff.isoformat(), as_of.isoformat()]
    if symbol:
        query += " AND symbol = ?"
        params.append(symbol.strip().upper())
    query += " ORDER BY disclosed_at DESC"
    with connect() as conn:
        rows = conn.execute(query, params).fetchall()
    counts = summarize_event_counts(
        [{"event_type": row["event_type"], "disclosed_at": row["disclosed_at"]} for row in rows],
        lookback_days=lookback_days,
        as_of=as_of,
    )
    return {
        "as_of": as_of.isoformat(),
        "lookback_days": lookback_days,
        "symbol": symbol.strip().upper() if symbol else None,
        "event_count": sum(counts.values()),
        "by_event_type": describe_pattern(counts),
        "interpretation": "descriptive_frequency_only_not_a_forecast",
    }
