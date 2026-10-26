"""FastAPI endpoints for local research workflows."""
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query
from .db import connect, init_db, now_iso, row_to_dict
from .models import EventIn, PredictionIn, PaperOrderIn, SourceDocumentIn
from .paper import create_paper_order, simulate_fill
from .evaluation import evaluate_binary_probabilities

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


@app.get("/sources")
def list_sources(source_type: str | None = None, limit: int = 100) -> dict:
    """Browse ingested source metadata without downloading linked article pages."""
    if not 1 <= limit <= 500:
        raise HTTPException(status_code=422, detail="limit must be 1..500")
    with connect() as conn:
        if source_type:
            rows = conn.execute(
                "SELECT * FROM source_documents WHERE source_type=? ORDER BY retrieved_at DESC LIMIT ?",
                (source_type, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM source_documents ORDER BY retrieved_at DESC LIMIT ?", (limit,)
            ).fetchall()
    return {"items": [row_to_dict(row) for row in rows], "count": len(rows)}


@app.get("/pipeline/feeds")
def list_configured_feeds() -> dict:
    """Show configured feed URLs and enabled state without triggering network requests."""
    from .feed_pipeline import load_feed_config

    try:
        config = load_feed_config()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    feeds = [
        {
            "id": feed["id"],
            "name": feed.get("name", feed["id"]),
            "url": feed["url"],
            "enabled": bool(feed.get("enabled", False)),
            "category": feed.get("category", "unspecified"),
        }
        for feed in config["feeds"]
    ]
    return {"items": feeds, "count": len(feeds)}


@app.get("/research-sources")
def list_research_sources() -> dict:
    """List research links from the machine-readable source registry."""
    from .feed_pipeline import load_feed_config

    try:
        config = load_feed_config()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    sources = config.get("research_sources", [])
    return {"items": sources, "count": len(sources)}


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


@app.get("/event-candidates")
def list_event_candidates(
    symbol: str | None = None,
    status: str = "pending_review",
    limit: int = 100,
) -> dict:
    """Browse heuristic headline matches awaiting human review."""
    allowed_statuses = {"pending_review", "accepted", "rejected", "all"}
    if status not in allowed_statuses:
        raise HTTPException(status_code=422, detail="status must be pending_review, accepted, rejected, or all")
    if not 1 <= limit <= 500:
        raise HTTPException(status_code=422, detail="limit must be 1..500")
    query = "SELECT * FROM event_candidates WHERE 1=1"
    params: list = []
    if status != "all":
        query += " AND status=?"
        params.append(status)
    if symbol:
        query += " AND symbol=?"
        params.append(symbol.strip().upper())
    query += " ORDER BY COALESCE(disclosed_at, created_at) DESC LIMIT ?"
    params.append(limit)
    with connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return {"items": [row_to_dict(row) for row in rows], "count": len(rows)}


@app.post("/event-candidates/{candidate_id}/review")
def review_event_candidate(
    candidate_id: int,
    decision: str = Query(..., pattern="^(accept|reject)$"),
) -> dict:
    """Accept a candidate into the unverified event ledger or reject it explicitly."""
    with connect() as conn:
        candidate = conn.execute(
            "SELECT * FROM event_candidates WHERE id=?", (candidate_id,)
        ).fetchone()
        if candidate is None:
            raise HTTPException(status_code=404, detail="Event candidate not found")
        if candidate["status"] != "pending_review":
            raise HTTPException(status_code=409, detail="Candidate has already been reviewed")
        reviewed_at = now_iso()
        event_id = None
        if decision == "accept":
            cur = conn.execute(
                """INSERT INTO events
                (symbol,event_type,title,summary,disclosed_at,source_id,
                 evidence_confidence,materiality,status,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (candidate["symbol"], candidate["event_type"], candidate["title"],
                 candidate["summary"], candidate["disclosed_at"], candidate["source_id"],
                 0.5, 1, "unverified", reviewed_at),
            )
            event_id = int(cur.lastrowid)
        conn.execute(
            "UPDATE event_candidates SET status=?, reviewed_at=? WHERE id=?",
            ("accepted" if decision == "accept" else "rejected", reviewed_at, candidate_id),
        )
    return {
        "candidate_id": candidate_id,
        "decision": decision,
        "event_id": event_id,
        "event_status": "unverified" if event_id is not None else None,
        "note": "Accepted candidates remain unverified until the underlying disclosure is checked.",
    }


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


@app.get("/research/event-study")
def research_event_study(
    benchmark_symbol: str = "NIFTY50",
    horizons: str = "1,3,5,10,20",
    limit: int = 1000,
) -> dict:
    """Measure historical benchmark-relative returns after verified disclosures."""
    from .event_study import run_event_study

    if not 1 <= limit <= 5000:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 5000")
    try:
        horizon_values = tuple(int(value.strip()) for value in horizons.split(",") if value.strip())
        if not horizon_values or any(value < 1 for value in horizon_values):
            raise ValueError("horizons must be positive integers")
        if len(set(horizon_values)) != len(horizon_values):
            raise ValueError("horizons must be unique")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="horizons must be unique positive comma-separated integers") from exc

    with connect() as conn:
        # Only explicitly verified events enter the primary analysis to limit label contamination.
        event_rows = conn.execute(
            """SELECT id,symbol,event_type,disclosed_at FROM events
            WHERE status IN ('official','corroborated') AND disclosed_at IS NOT NULL
            ORDER BY disclosed_at ASC LIMIT ?""",
            (limit,),
        ).fetchall()
        bar_rows = conn.execute(
            """SELECT symbol,session_date,COALESCE(adjusted_close,close) AS price
            FROM market_bars ORDER BY symbol,session_date ASC"""
        ).fetchall()
    prices: dict[str, dict[str, float]] = {}
    for row in bar_rows:
        prices.setdefault(str(row["symbol"]).strip().upper(), {})[row["session_date"]] = float(row["price"])
    events = [dict(row) for row in event_rows]
    try:
        result = run_event_study(events, prices, benchmark_symbol, horizon_values)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result["verified_events_loaded"] = len(events)
    result["price_rows_loaded"] = len(bar_rows)
    result["price_basis"] = "adjusted_close_when_available_else_close"
    result["note"] = (
        "No forecast is generated. Import price history for each issuer and the benchmark, "
        "and explicitly verify events before interpreting results."
    )
    return result


@app.get("/market-bars")
def list_market_bars(symbol: str | None = None, limit: int = 500) -> dict:
    """Browse imported daily OHLCV records, newest first."""
    if not 1 <= limit <= 5000:
        raise HTTPException(status_code=422, detail="limit must be 1..5000")
    with connect() as conn:
        if symbol:
            rows = conn.execute(
                "SELECT * FROM market_bars WHERE symbol=? ORDER BY session_date DESC LIMIT ?",
                (symbol.strip().upper(), limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM market_bars ORDER BY session_date DESC LIMIT ?", (limit,)
            ).fetchall()
    return {"items": [row_to_dict(row) for row in rows], "count": len(rows)}


@app.get("/market-bars/{symbol}/features")
def market_bar_features(
    symbol: str,
    momentum_windows: str = "5,20",
    volatility_window: int = 20,
    limit: int = 2000,
) -> dict:
    """Calculate trailing features from imported prices using no future bars."""
    from .market_features import PriceBar, build_market_features

    if not 1 <= limit <= 5000:
        raise HTTPException(status_code=422, detail="limit must be 1..5000")
    try:
        windows = tuple(int(value.strip()) for value in momentum_windows.split(",") if value.strip())
        if not windows:
            raise ValueError("At least one momentum window is required")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="momentum_windows must be comma-separated positive integers") from exc
    with connect() as conn:
        rows = conn.execute(
            """SELECT session_date, COALESCE(adjusted_close, close) AS feature_close
            FROM market_bars WHERE symbol=? ORDER BY session_date DESC LIMIT ?""",
            (symbol.strip().upper(), limit),
        ).fetchall()
    bars = [PriceBar(row["session_date"], float(row["feature_close"])) for row in reversed(rows)]
    if not bars:
        return {"symbol": symbol.strip().upper(), "count": 0, "items": []}
    try:
        features = build_market_features(
            bars, momentum_windows=windows, volatility_window=volatility_window
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "symbol": symbol.strip().upper(),
        "count": len(features),
        "price_basis": "adjusted_close_when_available_else_close",
        "items": features,
        "note": "Trailing features only; no future prices are used. Validate data adjustments and trading calendars.",
    }


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


@app.post("/predictions/{prediction_id}/outcome")
def resolve_prediction(
    prediction_id: int,
    outcome: int = Query(..., ge=0, le=1),
    outcome_at: datetime = Query(...),
) -> dict:
    """Record a resolved outcome once; preserve the original forecast unchanged."""
    with connect() as conn:
        row = conn.execute("SELECT * FROM predictions WHERE id=?", (prediction_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Prediction not found")
        if row["outcome"] is not None:
            raise HTTPException(status_code=409, detail="Outcome already recorded and is immutable")
        forecast_at = datetime.fromisoformat(row["as_of"])
        comparable_outcome_at = outcome_at
        if forecast_at.tzinfo is None and comparable_outcome_at.tzinfo is not None:
            forecast_at = forecast_at.replace(tzinfo=comparable_outcome_at.tzinfo)
        elif forecast_at.tzinfo is not None and comparable_outcome_at.tzinfo is None:
            comparable_outcome_at = comparable_outcome_at.replace(tzinfo=forecast_at.tzinfo)
        if comparable_outcome_at < forecast_at:
            raise HTTPException(status_code=422, detail="Outcome time cannot precede forecast time")
        conn.execute("UPDATE predictions SET outcome=?, outcome_at=? WHERE id=?",
                     (outcome, outcome_at.isoformat(), prediction_id))
        return row_to_dict(conn.execute("SELECT * FROM predictions WHERE id=?",
                                        (prediction_id,)).fetchone())


@app.get("/evaluation/summary")
def evaluation_summary() -> dict:
    """Evaluate resolved forecasts using proper probability scoring rules."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT probability,outcome FROM predictions WHERE outcome IS NOT NULL"
        ).fetchall()
    metrics = evaluate_binary_probabilities(
        [float(row["probability"]) for row in rows],
        [int(row["outcome"]) for row in rows],
    )
    return {
        "observations": metrics.observations,
        "brier_score": metrics.brier_score,
        "log_loss": metrics.log_loss,
        "accuracy_at_half": metrics.accuracy_at_half,
        "note": "Metrics are descriptive; interpret only with sufficient out-of-sample observations.",
    }


@app.post("/paper-orders/{order_id}/fill")
def fill_paper_order(
    order_id: int,
    fill_price: float = Query(..., gt=0),
    fill_time: datetime = Query(...),
) -> dict:
    """Record a simulated fill only; this endpoint never contacts a broker."""
    try:
        simulate_fill(order_id, fill_price, fill_time)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    with connect() as conn:
        row = conn.execute("SELECT * FROM paper_orders WHERE id=?", (order_id,)).fetchone()
        return row_to_dict(row)


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
