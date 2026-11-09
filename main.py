# -*- coding: utf-8 -*-
"""
Orquestador Principal del Agente de Bolsa (Estrategia Dual: Largo Plazo Core-Satellite vs. Dinámica Diaria).
Ejecuta las 4 fases:
1. Recolección de cotizaciones e histórico de 3 años (Yahoo Finance JSON API).
2. Recolección de noticias sectoriales (FierceBiotech, AgFunderNews, DefenseNews y PubMed NCBI RNAi/CRISPR).
3. Análisis Cuantitativo de Soportes Históricos, Constantes Vitales Anti-Dilución (Cash Runway) + Cerebro Gemini IA.
4. Persistencia histórica en SQLite (data/bolsa.db), exportación al Panel Web (docs/data/) y envío por Email / Telegram.
"""

import argparse
import json
import os
from typing import Any, Dict

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

    print("[1/4] Consultando cotizaciones en vivo y soportes históricos de 3 años (Yahoo Finance)...")
    fetcher = MarketAndNewsFetcher(config)
    quotes = fetcher.fetch_all_quotes(skip_network=skip_network)

    print("[2/4] Escaneando noticias de FierceBiotech, AgFunderNews, DefenseNews y PubMed (RNAi/CRISPR)...")
    news = fetcher.fetch_rss_and_pubmed_news(skip_network=skip_network)

    print("[3/4] Evaluando Estrategia Largo Plazo (Core-Satellite) y Estrategia Dinámica (Cash Runway / Soportes)...")
    analyzer = PortfolioAnalyzer(config)
    analysis = analyzer.analyze_portfolio(quotes, news)

    print("[4/4] Guardando histórico en SQLite (data/bolsa.db) y exportando Panel Web (docs/data/)...")
    storage = MarketStorage(
        db_path=os.path.join(base_dir, "data", "bolsa.db"),
        docs_data_dir=os.path.join(base_dir, "docs", "data"),
    )
    web_payload = storage.save_analysis(analysis, config)

    notifier = BolsaNotifier(config)
    notifier.send_daily_report(web_payload, docs_dir=os.path.join(base_dir, "docs"))

    stats = web_payload.get("stats", {})
    print(
        f"[OK] Cartera actualizada: {stats.get('total_assets')} activos | "
        f"{stats.get('support_zone_count')} en Soporte Histórico | "
        f"Núcleo EUNL.DE: {stats.get('core_price')} EUR ({stats.get('core_change_1d_pct'):+.2f}%)"
    )
    return web_payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agente de Bolsa Core-Satellite & Biotech")
    parser.add_argument("--offline", action="store_true", help="Usar cotizaciones de referencia sin red")
    args = parser.parse_args()
    run_agent(skip_network=args.offline)
