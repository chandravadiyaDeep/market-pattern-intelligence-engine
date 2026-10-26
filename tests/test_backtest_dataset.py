"""Tests for point-in-time backtest panel construction."""
from datetime import date, timedelta

from market_engine.backtest_dataset import build_backtest_panel
from market_engine.db import connect, init_db


def _insert_price(conn, symbol, day, price, source="provider_a"):
    """Insert one deterministic synthetic OHLC row for the selected test source."""
    conn.execute(
        """INSERT INTO market_bars
        (symbol,session_date,open,high,low,close,adjusted_close,volume,source_name,retrieved_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (symbol, day, price, price * 1.01, price * 0.99, price, price, 1000,
         source, "2026-10-25T00:00:00+00:00"),
    )


def test_panel_uses_membership_on_feature_date_and_one_price_source(tmp_path):
    """Historical membership gates rows, and the requested source isolates price data."""
    db_file = tmp_path / "panel.sqlite3"
    init_db(db_file)
    first_day = date(2026, 1, 1)
    with connect(db_file) as conn:
        for index in range(45):
            day = (first_day + timedelta(days=index)).isoformat()
            _insert_price(conn, "NIFTY50", day, 100 + index * 0.4)
            _insert_price(conn, "AAA", day, 50 + index * 0.6)
            _insert_price(conn, "BBB", day, 70 + index * 0.3)
            # Conflicting values from a different provider must not be mixed in.
            _insert_price(conn, "AAA", day, 500 + index, source="provider_b")
        conn.execute(
            """INSERT INTO constituent_membership
            (symbol,company_name,start_date,end_date,source_name,retrieved_at)
            VALUES (?,?,?,?,?,?)""",
            ("AAA", "Alpha Ltd", "2026-01-01", "2026-02-04", "verified-history",
             "2026-10-25T00:00:00+00:00"),
        )
        conn.execute(
            """INSERT INTO constituent_membership
            (symbol,company_name,start_date,end_date,source_name,retrieved_at)
            VALUES (?,?,?,?,?,?)""",
            ("BBB", "Beta Ltd", "2026-01-15", None, "verified-history",
             "2026-10-25T00:00:00+00:00"),
        )

    result = build_backtest_panel(
        start_date="2026-01-01",
        end_date="2026-02-14",
        source_name="provider_a",
        db_path=db_file,
        volatility_window=5,
        momentum_windows=(2, 5),
        horizon_sessions=3,
    )
    assert result["status"] == "ok"
    assert result["symbols_with_rows"] == 2
    assert result["source_name"] == "provider_a"
    assert all(row["price_source"] == "provider_a" for row in result["rows"])
    assert all(row["target_end_date"] <= "2026-02-14" for row in result["rows"])
    assert all(row["date"] <= row["target_end_date"] for row in result["rows"])
    assert all(row["symbol"] != "BBB" or row["date"] >= "2026-01-15" for row in result["rows"])
    assert all(row["symbol"] != "AAA" or row["date"] <= "2026-02-04" for row in result["rows"])
    assert all(len(row["features"]) == len(result["feature_names"]) for row in result["rows"])
    # If provider_b leaked into the calculation, AAA's first momentum values would be huge.
    assert all(abs(row["features"][3]) < 1 for row in result["rows"] if row["symbol"] == "AAA")


def test_panel_requires_benchmark_from_selected_source(tmp_path):
    """The builder returns a clear insufficient-data status instead of guessing a benchmark."""
    db_file = tmp_path / "no-benchmark.sqlite3"
    init_db(db_file)
    result = build_backtest_panel(
        start_date="2026-01-01", end_date="2026-02-01",
        source_name="missing-provider", db_path=db_file,
    )
    assert result["status"] == "insufficient_data"
    assert "No benchmark bars found" in result["reason"]
