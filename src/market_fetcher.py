# -*- coding: utf-8 -*-
"""
Motor de Recolección de Cotizaciones (Yahoo Finance 3Y Chart API) y Radar Sectorial
(FierceBiotech, AgFunderNews, DefenseNews, Breaking Defense y PubMed NCBI E-utilities).

Regla de oro: este módulo NUNCA inventa datos. Si Yahoo, un RSS o PubMed no responden,
el activo o la fuente se marcan como "sin datos" y el informe lo dice tal cual.
"""

import datetime
import json
import math
import time
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:
    requests = None

try:
    import feedparser
except ImportError:
    feedparser = None

from src.sec_vitals import SecVitalsFetcher


YAHOO_HOSTS = ("query1.finance.yahoo.com", "query2.finance.yahoo.com")
DEFAULT_PUBMED_ESEARCH = (
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    "?db=pubmed&term=(CRISPR+plant+OR+RNAi+biopesticide+OR+NGS+liquid+biopsy)&retmode=json&retmax=3&sort=date"
)


class MarketAndNewsFetcher:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        }
        self.session = requests.Session() if requests else None
        if self.session:
            self.session.headers.update(self.headers)
        self.feed_errors: List[str] = []

    # ------------------------------------------------------------------ HTTP
    def _http_get_bytes(self, url: str, timeout: int = 12) -> bytes:
        if self.session:
            resp = self.session.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.content
        req = urllib.request.Request(url, headers=self.headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()

    def _http_get_json(self, url: str, timeout: int = 12) -> Dict[str, Any]:
        raw = self._http_get_bytes(url, timeout=timeout)
        return json.loads(raw.decode("utf-8", errors="replace"))

    # ---------------------------------------------------------------- Precios
    def _compute_rsi(self, closes: List[float], period: int = 14) -> Optional[float]:
        if len(closes) < period + 1:
            return None
        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        gains = [max(d, 0.0) for d in deltas[-period:]]
        losses = [abs(min(d, 0.0)) for d in deltas[-period:]]
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0
        rs = avg_gain / avg_loss
        return round(100.0 - (100.0 / (1.0 + rs)), 1)

    def _download_chart(self, ticker: str) -> Dict[str, Any]:
        last_exc: Optional[Exception] = None
        for host in YAHOO_HOSTS:
            url = f"https://{host}/v8/finance/chart/{ticker}?range=3y&interval=1d"
            try:
                data = self._http_get_json(url, timeout=12)
                result = (data.get("chart") or {}).get("result")
                if result:
                    return result[0]
                err = (data.get("chart") or {}).get("error")
                last_exc = ValueError(f"Yahoo sin resultado: {err}")
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
            time.sleep(0.6)
        raise last_exc or ValueError("Yahoo no respondió")

    def _fetch_single_yahoo_quote(self, asset_cfg: Dict[str, Any]) -> Dict[str, Any]:
        ticker = asset_cfg["ticker"]
        result = self._download_chart(ticker)
        meta = result.get("meta", {})
        timestamps = result.get("timestamp", []) or []
        indicators = result.get("indicators", {}).get("quote", [{}])[0]
        raw_closes = indicators.get("close", []) or []

        closes: List[float] = []
        dated: Dict[str, float] = {}
        for idx, c in enumerate(raw_closes):
            if c is None:
                continue
            try:
                fc = float(c)
            except (TypeError, ValueError):
                continue
            if math.isnan(fc):
                continue
            val = round(fc, 2)
            closes.append(val)
            if idx < len(timestamps) and timestamps[idx]:
                dt_str = datetime.datetime.fromtimestamp(int(timestamps[idx]), datetime.timezone.utc).strftime("%Y-%m-%d")
                dated[dt_str] = val
        if not closes:
            raise ValueError(f"Sin cierres para {ticker}")

        last_keys = sorted(dated.keys())[-10:]
        recent_history = {k: dated[k] for k in last_keys}
        last_session_date = last_keys[-1] if last_keys else None

        price = float(meta.get("regularMarketPrice") or closes[-1])
        if last_session_date:
            recent_history[last_session_date] = round(price, 2)
        prev_close = closes[-2] if len(closes) >= 2 else price
        close_5d = closes[-6] if len(closes) >= 6 else closes[0]
        close_1m = closes[-22] if len(closes) >= 22 else closes[0]
        close_1y = closes[-252] if len(closes) >= 252 else closes[0]
        close_2y = closes[-504] if len(closes) >= 504 else closes[0]

        def pct(a: float, b: float) -> float:
            return ((a - b) / b * 100.0) if b else 0.0

        closes_52w = closes[-252:] if len(closes) >= 252 else closes
        high_3y = max(closes)
        low_3y = min(closes)

        sorted_closes = sorted(closes)
        p10 = sorted_closes[int(len(sorted_closes) * 0.10)]
        p22 = sorted_closes[int(len(sorted_closes) * 0.22)]
        support_low = asset_cfg.get("historical_support_low") or round(p10, 2)
        support_high = asset_cfg.get("historical_support_high") or round(p22, 2)
        support_origin = "config" if asset_cfg.get("historical_support_high") else "percentiles_historia"

        sma_50 = sum(closes[-50:]) / min(len(closes), 50)
        sma_200 = sum(closes[-200:]) / min(len(closes), 200)

        return {
            "ticker": ticker,
            "data_ok": True,
            "current_price": round(price, 2),
            "price": round(price, 2),
            "prev_close": round(prev_close, 2),
            "last_session_date": last_session_date,
            "change_1d_pct": round(pct(price, prev_close), 2),
            "change_5d_pct": round(pct(price, close_5d), 2),
            "change_1m_pct": round(pct(price, close_1m), 2),
            "change_1y_pct": round(pct(price, close_1y), 2),
            "change_2y_pct": round(pct(price, close_2y), 2),
            "high_52w": round(max(closes_52w), 2),
            "low_52w": round(min(closes_52w), 2),
            "low_3y": round(low_3y, 2),
            "high_3y": round(high_3y, 2),
            "history_sessions": len(closes),
            "drawdown_3y_pct": round(pct(price, high_3y), 2),
            "dyn_support_low": round(float(support_low), 2),
            "dyn_support_high": round(float(support_high), 2),
            "support_origin": support_origin,
            "rsi_14": self._compute_rsi(closes, 14),
            "sma_50": round(sma_50, 2),
            "sma_200": round(sma_200, 2),
            "recent_history": recent_history,
            "source": "Yahoo Finance",
        }

    def fetch_all_quotes(self, skip_network: bool = False) -> Dict[str, Dict[str, Any]]:
        """Devuelve cotizaciones reales. Si un ticker falla, se marca data_ok=False (sin precio inventado)."""
        results: Dict[str, Dict[str, Any]] = {}
        for asset in self.config.get("assets", []):
            ticker = asset["ticker"]
            if skip_network:
                results[ticker] = {"ticker": ticker, "data_ok": False, "error": "Modo sin conexión (--offline)"}
                continue
            try:
                results[ticker] = self._fetch_single_yahoo_quote(asset)
            except Exception as exc:  # noqa: BLE001
                print(f"[WARN] Sin cotización de {ticker} hoy: {exc}")
                results[ticker] = {"ticker": ticker, "data_ok": False, "error": str(exc)[:200]}
        return results

    # ------------------------------------------------- Constantes vitales SEC
    def attach_biotech_vitals(self, quotes: Dict[str, Dict[str, Any]], skip_network: bool = False) -> None:
        """
        Para los activos del Satélite 4 (biotech en fase clínica) y los que tengan "sec_vitals": true en config,
        calcula con datos oficiales de la SEC: caja, quema de caja, meses de runway, capitalización y compras/ventas de directivos.
        """
        if skip_network:
            return
        targets = [
            a for a in self.config.get("assets", [])
            if a.get("sec_vitals", a.get("category") == "sat4_clinical_biotech_dynamic")
        ]
        if not targets:
            return
        sec = SecVitalsFetcher()
        for a in targets:
            t = a["ticker"]
            q = quotes.get(t) or {}
            price = q.get("current_price") if q.get("data_ok") else None
            try:
                vitals = sec.get_vitals(t, price_usd=price if a.get("currency", "USD") == "USD" else None)
            except Exception as exc:  # noqa: BLE001
                print(f"[WARN] Constantes vitales SEC no disponibles para {t}: {exc}")
                vitals = {"available": False, "reason": f"Error consultando la SEC: {str(exc)[:120]}"}
            if t in quotes:
                quotes[t]["clinical_vitals"] = vitals

    # ---------------------------------------------------------------- Noticias
    def _configured_feeds(self) -> List[Dict[str, Any]]:
        feeds = list(self.config.get("rss_feeds") or []) + list(self.config.get("news_feeds") or [])
        seen = set()
        out = []
        for f in feeds:
            u = (f.get("url") or "").strip()
            if u and u not in seen:
                seen.add(u)
                out.append(f)
        return out

    def _parse_feed(self, raw_xml: bytes) -> List[Dict[str, str]]:
        entries: List[Dict[str, str]] = []
        if feedparser:
            parsed = feedparser.parse(raw_xml)
            for e in parsed.entries:
                entries.append(
                    {
                        "title": (e.get("title") or "").strip(),
                        "url": (e.get("link") or "").strip(),
                        "published": e.get("published") or e.get("updated") or "",
                    }
                )
            return entries
        root = ET.fromstring(raw_xml)
        for elem in root.findall(".//item"):
            entries.append(
                {
                    "title": (elem.findtext("title") or "").strip(),
                    "url": (elem.findtext("link") or "").strip(),
                    "published": (elem.findtext("pubDate") or "").strip(),
                }
            )
        atom = "{http://www.w3.org/2005/Atom}"
        for elem in root.findall(f".//{atom}entry"):
            link_el = elem.find(f"{atom}link")
            entries.append(
                {
                    "title": (elem.findtext(f"{atom}title") or "").strip(),
                    "url": (link_el.get("href") if link_el is not None else "") or "",
                    "published": (elem.findtext(f"{atom}updated") or "").strip(),
                }
            )
        return entries

    def _fetch_pubmed(self, esearch_url: str, source_name: str, category: str) -> List[Dict[str, Any]]:
        url = esearch_url
        if "retmode=json" not in url:
            url += "&retmode=json"
        if "sort=" not in url:
            url += "&sort=date"
        r_search = self._http_get_json(url, timeout=12)
        id_list = (r_search.get("esearchresult") or {}).get("idlist", [])[:5]
        if not id_list:
            return []
        esum = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id="
            + ",".join(id_list)
            + "&retmode=json"
        )
        r_sum = self._http_get_json(esum, timeout=12).get("result", {})
        items = []
        for pid in id_list:
            art = r_sum.get(pid, {})
            if art.get("title"):
                items.append(
                    {
                        "source": source_name,
                        "category": category,
                        "title": art["title"].strip(),
                        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pid}/",
                        "published": art.get("pubdate", ""),
                    }
                )
        return items

    def fetch_rss_and_pubmed_news(self, skip_network: bool = False) -> List[Dict[str, Any]]:
        """Lee los feeds de config["rss_feeds"]. Si nada responde, devuelve lista vacía (sin titulares inventados)."""
        items: List[Dict[str, Any]] = []
        self.feed_errors = []
        if skip_network:
            return items

        has_pubmed_feed = False
        for feed_cfg in self._configured_feeds():
            name = feed_cfg.get("name", "Fuente")
            category = feed_cfg.get("category", "Sector")
            url = feed_cfg["url"]
            try:
                if "eutils.ncbi.nlm.nih.gov" in url:
                    has_pubmed_feed = True
                    items.extend(self._fetch_pubmed(url, name, category))
                    continue
                raw_xml = self._http_get_bytes(url, timeout=12)
                for e in self._parse_feed(raw_xml)[:4]:
                    if not e["title"] or not e["url"]:
                        continue
                    items.append({"source": name, "category": category, **e})
            except Exception as exc:  # noqa: BLE001
                print(f"[WARN] Fallo en la fuente {name}: {exc}")
                self.feed_errors.append(name)

        if not has_pubmed_feed:
            try:
                items.extend(self._fetch_pubmed(DEFAULT_PUBMED_ESEARCH, "PubMed NCBI (Papers Científicos)", "Biotech / AgTech"))
            except Exception as exc:  # noqa: BLE001
                print(f"[WARN] Fallo en PubMed NCBI: {exc}")
                self.feed_errors.append("PubMed NCBI")

        return items
