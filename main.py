# -*- coding: utf-8 -*-
"""
Orquestador Principal del Agente de Bolsa con Memoria Episódica Persistente (SQLite + GitHub Pages).
Ejecuta las 5 fases:
1. Lectura de Memoria Previa en SQLite (data/bolsa.db): chequea precios, soportes y notas de días anteriores.
2. Recolección de cotizaciones en vivo e histórico de 3 años (Yahoo Finance JSON API).
3. Recolección de noticias sectoriales (FierceBiotech, AgFunderNews, DefenseNews y PubMed NCBI RNAi/CRISPR).
4. Análisis Pedagógico Profundo (Core-Satellite + Cash Runway + Comparativa con Memoria Histórica).
5. Guardado de la nueva ronda en Memoria (data/bolsa.db), exportación Web (docs/data/) y envío por Email / Telegram.
"""

import argparse
import json
import os
import sys
from typing import Any, Dict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.analyzer import PortfolioAnalyzer
from src.market_fetcher import MarketAndNewsFetcher
from src.notifier import BolsaNotifier
from src.storage import MarketStorage


def load_dotenv_if_present(base_dir: str) -> None:
    env_path = os.path.join(base_dir, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v


def load_config(base_dir: str) -> Dict[str, Any]:
    cfg_path = os.path.join(base_dir, "config.json")
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_agent(skip_network: bool = False) -> Dict[str, Any]:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    load_dotenv_if_present(base_dir)
    config = load_config(base_dir)

    storage = MarketStorage(
        db_path=os.path.join(base_dir, "data", "bolsa.db"),
        docs_data_dir=os.path.join(base_dir, "docs", "data"),
    )

    print("[1/5] Chequeando Memoria Histórica de sesiones anteriores en data/bolsa.db...")
    previous_memory = storage.load_previous_memory()

    print("[2/5] Consultando cotizaciones en vivo y soportes históricos de 3 años (Yahoo Finance)...")
    fetcher = MarketAndNewsFetcher(config)
    quotes = fetcher.fetch_all_quotes(skip_network=skip_network)
    ok_count = sum(1 for q in quotes.values() if q.get("data_ok"))
    print(f"      Cotizaciones reales obtenidas: {ok_count}/{len(quotes)}")

    print("[2b/5] Calculando constantes vitales de las biotech con datos oficiales de la SEC (caja, runway, insiders)...")
    fetcher.attach_biotech_vitals(quotes, skip_network=skip_network)

    print("[3/5] Escaneando noticias de FierceBiotech, AgFunderNews, DefenseNews y PubMed (RNAi/CRISPR)...")
    news = fetcher.fetch_rss_and_pubmed_news(skip_network=skip_network)

    print("[4/5] Cruzando datos de hoy con la Memoria previa y generando Informe Pedagógico Profundo...")
    analyzer = PortfolioAnalyzer(config)
    analysis = analyzer.analyze_portfolio(quotes, news, previous_memory=previous_memory)

    print("[5/5] Almacenando sesión de hoy en Memoria SQLite (data/bolsa.db) y exportando Panel Web...")
    web_payload = storage.save_analysis(analysis, config)

    notifier = BolsaNotifier(config)
    notifier.send_daily_report(web_payload, docs_dir=os.path.join(base_dir, "docs"))

    stats = web_payload.get("stats", {})
    print(
        f"[OK] Cartera y Memoria actualizadas ({stats.get('memory_days_count', 1)} sesiones en memoria): "
        f"{stats.get('total_assets')} activos | {stats.get('support_zone_count')} en Soporte Histórico | "
        f"Núcleo EUNL.DE: {stats.get('core_price')} EUR ({stats.get('core_change_1d_pct'):+.2f}%)"
    )
    return web_payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agente de Bolsa Core-Satellite & Biotech con Memoria")
    parser.add_argument("--offline", action="store_true", help="Ejecutar sin red (no se inventan precios: el informe saldrá 'sin datos')")
    args = parser.parse_args()
    run_agent(skip_network=args.offline)
