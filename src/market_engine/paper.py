"""Paper-order ledger helpers. There is intentionally no live broker integration."""
from datetime import datetime
from .db import connect, now_iso
from .models import PaperOrderIn


def create_paper_order(order: PaperOrderIn, db_path: str | None = None) -> int:
    """Persist a pending simulated order without placing any real order."""
    with connect(db_path) as conn:
        cursor = conn.execute(
            """INSERT INTO paper_orders
            (symbol, side, quantity, reference_price, estimated_cost, strategy_name,
             signal_time, expected_fill_time, rationale, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?)""",
            (order.symbol.strip().upper(), order.side, order.quantity, order.reference_price,
             order.estimated_cost, order.strategy_name, order.signal_time.isoformat(),
             order.expected_fill_time.isoformat(), order.rationale, now_iso()),
        )
        return int(cursor.lastrowid)


def simulate_fill(order_id: int, fill_price: float, fill_time: datetime,
                  db_path: str | None = None) -> None:
    """Record an explicitly supplied simulated fill after its eligible time."""
    if fill_price <= 0:
        raise ValueError("fill_price must be positive")
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM paper_orders WHERE id = ?", (order_id,)).fetchone()
        if row is None:
            raise ValueError("paper order not found")
        if row["status"] != "PENDING":
            raise ValueError("only pending paper orders can be filled")
        expected = datetime.fromisoformat(row["expected_fill_time"])
        comparable = fill_time
        if expected.tzinfo and comparable.tzinfo is None:
            comparable = comparable.replace(tzinfo=expected.tzinfo)
        if comparable < expected:
            raise ValueError("fill_time cannot precede expected_fill_time")
        conn.execute(
            """UPDATE paper_orders SET status='SIMULATED_FILLED', simulated_fill_price=?,
            simulated_fill_time=? WHERE id=?""",
            (fill_price, fill_time.isoformat(), order_id),
        )
