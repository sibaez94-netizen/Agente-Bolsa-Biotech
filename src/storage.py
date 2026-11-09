# -*- coding: utf-8 -*-
"""
Persistencia histórica en SQLite (data/bolsa.db) + Exportación a JSON/JS (docs/data/market_data.json y .js)
para el Panel Web en GitHub Pages y la Tabla Excel de Histórico de Cotizaciones por Fecha.
"""

import datetime
import json
import os
import sqlite3
from typing import Any, Dict, List, Optional


class MarketStorage:
    def __init__(self, db_path: Optional[str] = None, docs_data_dir: Optional[str] = None):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.db_path = db_path or os.path.join(base_dir, "data", "bolsa.db")
        self.docs_data_dir = docs_data_dir or os.path.join(base_dir, "docs", "data")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(self.docs_data_dir, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS assets (
                    ticker TEXT PRIMARY KEY,
                    name TEXT,
                    category TEXT,
                    category_label TEXT,
                    strategy_mode TEXT,
                    strategy_group TEXT,
                    strategy_label TEXT,
                    currency TEXT,
                    exchange TEXT,
                    in_base_dca INTEGER,
                    monthly_allocation_eur REAL,
                    current_price REAL,
                    prev_close REAL,
                    change_1d_pct REAL,
                    change_5d_pct REAL,
                    change_1m_pct REAL,
                    change_1y_pct REAL,
                    change_2y_pct REAL,
                    value_of_40eur_2y REAL,
                    low_3y REAL,
                    high_3y REAL,
                    drawdown_3y_pct REAL,
                    sma_50 REAL,
                    sma_200 REAL,
                    rsi_14 REAL,
                    historical_support_low REAL,
                    historical_support_high REAL,
                    in_support_zone INTEGER,
                    dist_to_support_pct REAL,
                    opportunity_score INTEGER,
                    signal_badge TEXT,
                    signal_color TEXT,
                    alert_level TEXT,
                    reasons_json TEXT,
                    thesis TEXT,
                    sell_rule TEXT,
                    clinical_vitals_json TEXT,
                    yahoo_url TEXT,
                    updated_at TEXT
                );

                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    recorded_date TEXT NOT NULL,
                    price REAL NOT NULL,
                    change_1d_pct REAL DEFAULT 0,
                    UNIQUE(ticker, recorded_date)
                );

                CREATE INDEX IF NOT EXISTS idx_hist_ticker_date ON price_history(ticker, recorded_date);
                """
            )

    def save_analysis(self, analysis_result: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        today_str = now_iso[:10]
        assets = analysis_result.get("assets", [])

        with self._connect() as conn:
            for a in assets:
                ticker = a["ticker"]
                conn.execute(
                    """
                    INSERT INTO assets (
                        ticker, name, category, category_label, strategy_mode, strategy_group, strategy_label,
                        currency, exchange, in_base_dca, monthly_allocation_eur,
                        current_price, prev_close, change_1d_pct, change_5d_pct, change_1m_pct,
                        change_1y_pct, change_2y_pct, value_of_40eur_2y,
                        low_3y, high_3y, drawdown_3y_pct, sma_50, sma_200, rsi_14,
                        historical_support_low, historical_support_high, in_support_zone, dist_to_support_pct,
                        opportunity_score, signal_badge, signal_color, alert_level,
                        reasons_json, thesis, sell_rule, clinical_vitals_json, yahoo_url, updated_at
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?
                    )
                    ON CONFLICT(ticker) DO UPDATE SET
                        name=excluded.name,
                        category=excluded.category,
                        category_label=excluded.category_label,
                        strategy_mode=excluded.strategy_mode,
                        strategy_group=excluded.strategy_group,
                        strategy_label=excluded.strategy_label,
                        currency=excluded.currency,
                        exchange=excluded.exchange,
                        in_base_dca=excluded.in_base_dca,
                        monthly_allocation_eur=excluded.monthly_allocation_eur,
                        current_price=excluded.current_price,
                        prev_close=excluded.prev_close,
                        change_1d_pct=excluded.change_1d_pct,
                        change_5d_pct=excluded.change_5d_pct,
                        change_1m_pct=excluded.change_1m_pct,
                        change_1y_pct=excluded.change_1y_pct,
                        change_2y_pct=excluded.change_2y_pct,
                        value_of_40eur_2y=excluded.value_of_40eur_2y,
                        low_3y=excluded.low_3y,
                        high_3y=excluded.high_3y,
                        drawdown_3y_pct=excluded.drawdown_3y_pct,
                        sma_50=excluded.sma_50,
                        sma_200=excluded.sma_200,
                        rsi_14=excluded.rsi_14,
                        historical_support_low=excluded.historical_support_low,
                        historical_support_high=excluded.historical_support_high,
                        in_support_zone=excluded.in_support_zone,
                        dist_to_support_pct=excluded.dist_to_support_pct,
                        opportunity_score=excluded.opportunity_score,
                        signal_badge=excluded.signal_badge,
                        signal_color=excluded.signal_color,
                        alert_level=excluded.alert_level,
                        reasons_json=excluded.reasons_json,
                        thesis=excluded.thesis,
                        sell_rule=excluded.sell_rule,
                        clinical_vitals_json=excluded.clinical_vitals_json,
                        yahoo_url=excluded.yahoo_url,
                        updated_at=excluded.updated_at
                    """,
                    (
                        ticker,
                        a["name"],
                        a["category"],
                        a["category_label"],
                        a["strategy_mode"],
                        a["strategy_group"],
                        a["strategy_label"],
                        a["currency"],
                        a["exchange"],
                        1 if a["in_base_dca"] else 0,
                        a["monthly_allocation_eur"],
                        a["current_price"],
                        a["prev_close"],
                        a["change_1d_pct"],
                        a["change_5d_pct"],
                        a["change_1m_pct"],
                        a["change_1y_pct"],
                        a["change_2y_pct"],
                        a["value_of_40eur_2y"],
                        a["low_3y"],
                        a["high_3y"],
                        a["drawdown_3y_pct"],
                        a.get("sma_50"),
                        a.get("sma_200"),
                        a.get("rsi_14"),
                        a["historical_support_low"],
                        a["historical_support_high"],
                        1 if a["in_support_zone"] else 0,
                        a["dist_to_support_pct"],
                        a["opportunity_score"],
                        a["signal_badge"],
                        a["signal_color"],
                        a["alert_level"],
                        json.dumps(a.get("reasons", []), ensure_ascii=False),
                        a.get("thesis", ""),
                        a.get("sell_rule", ""),
                        json.dumps(a.get("clinical_vitals"), ensure_ascii=False) if a.get("clinical_vitals") else None,
                        a.get("yahoo_url", ""),
                        now_iso,
                    ),
                )

                # Guardar histórico de precios por fecha (para la Tabla Excel)
                recent_hist = a.get("recent_history") or {}
                for dt_key, p_val in recent_hist.items():
                    if p_val and p_val > 0:
                        conn.execute(
                            """
                            INSERT INTO price_history (ticker, recorded_date, price, change_1d_pct)
                            VALUES (?, ?, ?, ?)
                            ON CONFLICT(ticker, recorded_date) DO UPDATE SET
                                price=excluded.price,
                                change_1d_pct=excluded.change_1d_pct
                            """,
                            (ticker, dt_key, float(p_val), a["change_1d_pct"] if dt_key == today_str else 0.0),
                        )

        return self.export_web_data(analysis_result, config, now_iso)

    def export_web_data(
        self,
        analysis_result: Dict[str, Any],
        config: Dict[str, Any],
        now_iso: Optional[str] = None,
    ) -> Dict[str, Any]:
        now_str = now_iso or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        with self._connect() as conn:
            hist_rows = conn.execute(
                "SELECT ticker, recorded_date, price FROM price_history ORDER BY recorded_date ASC"
            ).fetchall()

        hist_by_ticker: Dict[str, List[Dict[str, Any]]] = {}
        all_dates_set = set()
        for r in hist_rows:
            all_dates_set.add(r["recorded_date"])
            hist_by_ticker.setdefault(r["ticker"], []).append(
                {"date": r["recorded_date"], "price": r["price"]}
            )

        sorted_dates = sorted(all_dates_set)[-8:]  # Últimas 8 fechas registradas para la tabla Excel

        assets = analysis_result.get("assets", [])
        for a in assets:
            a["price_history"] = hist_by_ticker.get(a["ticker"], [])

        long_term_assets = [a for a in assets if a["strategy_group"] == "long_term"]
        dynamic_assets = [a for a in assets if a["strategy_group"] == "dynamic"]
        support_assets = [a for a in assets if a["in_support_zone"] and a["ticker"] != "EUNL.DE"]
        core_asset = next((a for a in assets if a["ticker"] == "EUNL.DE"), None)

        payload = {
            "updated_at": now_str,
            "investor_profile": config.get("investor_profile", {}),
            "allocations": config.get("allocations", {}),
            "stats": {
                "total_assets": len(assets),
                "long_term_count": len(long_term_assets),
                "dynamic_count": len(dynamic_assets),
                "support_zone_count": len(support_assets),
                "core_status": core_asset["signal_badge"] if core_asset else "🟢 OK",
                "core_change_1d_pct": core_asset["change_1d_pct"] if core_asset else 0.0,
                "core_price": core_asset["current_price"] if core_asset else 0.0,
                "history_dates": sorted_dates,
            },
            "ai_briefing": analysis_result.get("ai_briefing", ""),
            "briefing_source": analysis_result.get("briefing_source", "Motor Cuantitativo"),
            "assets": assets,
            "news": analysis_result.get("news", []),
        }

        json_path = os.path.join(self.docs_data_dir, "market_data.json")
        js_path = os.path.join(self.docs_data_dir, "market_data.js")

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        with open(js_path, "w", encoding="utf-8") as f:
            f.write("window.__BOLSA_DATA__ = ")
            json.dump(payload, f, ensure_ascii=False)
            f.write(";\n")

        return payload
