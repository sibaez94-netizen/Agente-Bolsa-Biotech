# -*- coding: utf-8 -*-
"""
Sistema de Memoria Persistente e Histórica en SQLite (data/bolsa.db) + Exportación Web (docs/data/).
Guarda:
1. Cotizaciones diarias por fecha (price_history) para la Tabla Excel y comparativa interdiaria.
2. Diario de Memoria Episódica del Agente (daily_memory_journal): qué concluyó y recomendó el agente
   en las rondas anteriores para chequeo previo antes de responder cada día.
3. Hemeroteca acumulada de noticias y papers científicos (news_archive) para distinguir noticias nuevas
   de las ya reportadas en días previos.
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
                    rsi_14 REAL,
                    in_support_zone INTEGER DEFAULT 0,
                    signal_badge TEXT DEFAULT '',
                    UNIQUE(ticker, recorded_date)
                );

                CREATE TABLE IF NOT EXISTS daily_memory_journal (
                    run_date TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    core_price REAL,
                    support_tickers_json TEXT,
                    alerts_summary TEXT,
                    key_changes_vs_prev TEXT,
                    briefing_excerpt TEXT
                );

                CREATE TABLE IF NOT EXISTS news_archive (
                    url TEXT PRIMARY KEY,
                    first_seen_date TEXT NOT NULL,
                    source TEXT,
                    category TEXT,
                    title TEXT,
                    explanation_es TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_hist_ticker_date ON price_history(ticker, recorded_date);
                """
            )
            # Migraciones suaves si la tabla price_history ya existía de una versión previa
            conn.execute("CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT)")
            for col_sql in (
                "ALTER TABLE price_history ADD COLUMN rsi_14 REAL",
                "ALTER TABLE price_history ADD COLUMN in_support_zone INTEGER DEFAULT 0",
                "ALTER TABLE price_history ADD COLUMN signal_badge TEXT DEFAULT ''",
            ):
                try:
                    conn.execute(col_sql)
                except Exception:
                    pass

            # Limpieza única (v2): las versiones anteriores rellenaban con precios de referencia inventados
            # cuando Yahoo fallaba, y no hay forma de distinguirlos de los reales. Se vacía la memoria una vez;
            # en la primera ejecución se reconstruye con las 10 últimas sesiones reales de Yahoo.
            done = conn.execute("SELECT value FROM schema_meta WHERE key = 'limpieza_datos_inventados_v2'").fetchone()
            if not done:
                conn.execute("DELETE FROM price_history")
                conn.execute("DELETE FROM daily_memory_journal")
                conn.execute("DELETE FROM assets")
                conn.execute(
                    "INSERT OR REPLACE INTO schema_meta (key, value) VALUES ('limpieza_datos_inventados_v2', ?)",
                    (datetime.datetime.now(datetime.timezone.utc).isoformat(),),
                )

    def load_previous_memory(self) -> Dict[str, Any]:
        """
        Lee la memoria acumulada en SQLite ANTES de analizar la jornada actual:
        - Estado previo de cada activo (último precio guardado, primer precio registrado, si estaba o no en soporte).
        - Últimas entradas del diario de memoria (daily_memory_journal).
        - URLs de noticias ya vistas en días anteriores.
        """
        today_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        prev_assets: Dict[str, Dict[str, Any]] = {}
        journal_entries: List[Dict[str, Any]] = []
        seen_news_urls: Dict[str, str] = {}

        with self._connect() as conn:
            # 1. Estado previo en tabla assets + serie en price_history
            asset_rows = conn.execute("SELECT * FROM assets").fetchall()
            for r in asset_rows:
                t = r["ticker"]
                hist = conn.execute(
                    "SELECT recorded_date, price, in_support_zone, signal_badge FROM price_history WHERE ticker = ? ORDER BY recorded_date ASC",
                    (t,),
                ).fetchall()
                first_date = hist[0]["recorded_date"] if hist else today_str
                first_price = float(hist[0]["price"]) if hist else float(r["current_price"] or 0.0)

                # Buscar el cierre inmediatamente anterior a hoy (o el último guardado)
                prev_Points = [h for h in hist if h["recorded_date"] < today_str]
                if prev_Points:
                    last_pt = prev_Points[-1]
                elif hist:
                    last_pt = hist[-1]
                else:
                    last_pt = None

                # Calcular racha de sesiones seguidas en soporte o tendencia
                streak_days = 0
                if len(hist) >= 2:
                    for i in range(len(hist) - 1, 0, -1):
                        diff = hist[i]["price"] - hist[i - 1]["price"]
                        if diff > 0 and streak_days >= 0:
                            streak_days += 1
                        elif diff < 0 and streak_days <= 0:
                            streak_days -= 1
                        else:
                            break

                prev_assets[t] = {
                    "ticker": t,
                    "last_recorded_date": last_pt["recorded_date"] if last_pt else None,
                    "last_recorded_price": float(last_pt["price"]) if last_pt else float(r["current_price"] or 0.0),
                    "prev_in_support_zone": bool(r["in_support_zone"]),
                    "prev_signal_badge": r["signal_badge"] or "",
                    "prev_opportunity_score": int(r["opportunity_score"] or 50),
                    "first_tracked_date": first_date,
                    "first_tracked_price": first_price,
                    "total_sessions_recorded": len(hist),
                    "streak_days": streak_days,
                }

            # 2. Últimas 7 entradas del Diario de Memoria del Agente
            j_rows = conn.execute(
                "SELECT * FROM daily_memory_journal ORDER BY run_date DESC LIMIT 7"
            ).fetchall()
            for jr in j_rows:
                journal_entries.append(
                    {
                        "run_date": jr["run_date"],
                        "created_at": jr["created_at"],
                        "core_price": jr["core_price"],
                        "support_tickers": json.loads(jr["support_tickers_json"] or "[]"),
                        "alerts_summary": jr["alerts_summary"] or "",
                        "key_changes_vs_prev": jr["key_changes_vs_prev"] or "",
                        "briefing_excerpt": jr["briefing_excerpt"] or "",
                    }
                )

            # 3. Noticias ya registradas en días anteriores
            n_rows = conn.execute("SELECT url, first_seen_date FROM news_archive").fetchall()
            for nr in n_rows:
                seen_news_urls[nr["url"]] = nr["first_seen_date"]

        return {
            "prev_assets": prev_assets,
            "journal_entries": journal_entries,
            "seen_news_urls": seen_news_urls,
        }

    def save_analysis(self, analysis_result: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        today_str = now_iso[:10]
        assets = analysis_result.get("assets", [])
        news = analysis_result.get("news", [])

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

                # Solo cierres reales fechados por Yahoo (la última sesión lleva el precio de hoy)
                recent_hist = dict(a.get("recent_history") or {})
                last_session = a.get("last_session_date")
                for dt_key, p_val in recent_hist.items():
                    if p_val and p_val > 0:
                        is_today = dt_key == last_session
                        conn.execute(
                            """
                            INSERT INTO price_history (ticker, recorded_date, price, change_1d_pct, rsi_14, in_support_zone, signal_badge)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(ticker, recorded_date) DO UPDATE SET
                                price=excluded.price,
                                change_1d_pct=excluded.change_1d_pct,
                                rsi_14=COALESCE(excluded.rsi_14, price_history.rsi_14),
                                in_support_zone=excluded.in_support_zone,
                                signal_badge=CASE WHEN excluded.signal_badge != '' THEN excluded.signal_badge ELSE price_history.signal_badge END
                            """,
                            (
                                ticker,
                                dt_key,
                                float(p_val),
                                a["change_1d_pct"] if is_today else 0.0,
                                a.get("rsi_14") if is_today else None,
                                (1 if a["in_support_zone"] else 0) if is_today else 0,
                                a["signal_badge"] if is_today else "",
                            ),
                        )

            # Guardar noticias en la hemeroteca persistente (news_archive)
            for n in news:
                n_url = (n.get("url") or "").strip()
                if not n_url:
                    continue
                conn.execute(
                    """
                    INSERT INTO news_archive (url, first_seen_date, source, category, title, explanation_es)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(url) DO UPDATE SET
                        explanation_es=excluded.explanation_es
                    """,
                    (
                        n_url,
                        n.get("first_seen_date") or today_str,
                        n.get("source", ""),
                        n.get("category", ""),
                        n.get("title", ""),
                        n.get("explanation_es", ""),
                    ),
                )

            # Guardar entrada de hoy en el Diario de Memoria del Agente (solo si hubo datos reales)
            core_asset = next((x for x in assets if x["ticker"] == "EUNL.DE"), None)
            sup_tickers = [
                x["ticker"]
                for x in assets
                if x.get("in_support_zone") and x["ticker"] != "EUNL.DE" and not (x.get("clinical_vitals") and x["clinical_vitals"].get("trading_below_cash"))
            ]
            mem_comparison = analysis_result.get("memory_comparison_summary", "")
            briefing_sections = analysis_result.get("briefing_sections") or []
            b1_excerpt = briefing_sections[0]["body"] if briefing_sections else ""

            if assets:
                conn.execute(
                """
                INSERT INTO daily_memory_journal (
                    run_date, created_at, core_price, support_tickers_json,
                    alerts_summary, key_changes_vs_prev, briefing_excerpt
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_date) DO UPDATE SET
                    created_at=excluded.created_at,
                    core_price=excluded.core_price,
                    support_tickers_json=excluded.support_tickers_json,
                    alerts_summary=excluded.alerts_summary,
                    key_changes_vs_prev=excluded.key_changes_vs_prev,
                    briefing_excerpt=excluded.briefing_excerpt
                """,
                (
                    today_str,
                    now_iso,
                    core_asset["current_price"] if core_asset else 0.0,
                    json.dumps(sup_tickers, ensure_ascii=False),
                    f"{len(sup_tickers)} activos en suelo histórico ({', '.join(sup_tickers) or 'ninguno'})",
                    mem_comparison,
                    b1_excerpt[:500],
                ),
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
            journal_rows = conn.execute(
                "SELECT * FROM daily_memory_journal ORDER BY run_date DESC LIMIT 14"
            ).fetchall()

        hist_by_ticker: Dict[str, List[Dict[str, Any]]] = {}
        all_dates_set = set()
        for r in hist_rows:
            all_dates_set.add(r["recorded_date"])
            hist_by_ticker.setdefault(r["ticker"], []).append(
                {"date": r["recorded_date"], "price": r["price"]}
            )

        sorted_dates = sorted(all_dates_set)[-10:]

        journal_list = [
            {
                "run_date": jr["run_date"],
                "created_at": jr["created_at"],
                "core_price": jr["core_price"],
                "support_tickers": json.loads(jr["support_tickers_json"] or "[]"),
                "alerts_summary": jr["alerts_summary"],
                "key_changes_vs_prev": jr["key_changes_vs_prev"],
                "briefing_excerpt": jr["briefing_excerpt"],
            }
            for jr in journal_rows
        ]

        assets = analysis_result.get("assets", [])
        for a in assets:
            a["price_history"] = hist_by_ticker.get(a["ticker"], [])

        long_term_assets = [a for a in assets if a["strategy_group"] == "long_term"]
        dynamic_assets = [a for a in assets if a["strategy_group"] == "dynamic"]
        support_assets = [
            a for a in assets
            if a["in_support_zone"] and a["ticker"] != "EUNL.DE" and not (a.get("clinical_vitals") and a["clinical_vitals"].get("trading_below_cash"))
        ]
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
                "memory_days_count": len(sorted_dates),
            },
            "ai_briefing": analysis_result.get("ai_briefing", ""),
            "briefing_sections": analysis_result.get("briefing_sections", []),
            "memory_comparison_summary": analysis_result.get("memory_comparison_summary", ""),
            "memory_journal": journal_list,
            "briefing_source": analysis_result.get("briefing_source", "Mentor Pedagógico Core-Satellite"),
            "assets": assets,
            "news": analysis_result.get("news", []),
            "unavailable_assets": analysis_result.get("unavailable_assets", []),
            "data_warnings": analysis_result.get("data_warnings", []),
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
