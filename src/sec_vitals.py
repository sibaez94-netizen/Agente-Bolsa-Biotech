# -*- coding: utf-8 -*-
"""
Constantes vitales anti-dilución para biotech cotizadas en EE. UU., calculadas con datos OFICIALES
de la SEC (EDGAR, gratis y sin clave):

- Caja: efectivo + inversiones/valores negociables del último 10-Q/10-K (XBRL "companyfacts").
- Quema de caja: flujo de caja operativo de los últimos 12 meses (TTM).
- Cash runway (meses): caja / quema mensual.
- Capitalización: acciones en circulación (portada del último informe) x precio de hoy (Yahoo).
- Directivos (insiders): compras (código P) y ventas (código S) en mercado abierto de los Form 4 de los últimos 90 días.

La SEC exige identificarse con un User-Agent que incluya un correo de contacto. Se toma de la variable
SEC_USER_AGENT o, si no existe, se construye con SMTP_USER / NOTIFY_EMAIL.
Si una empresa no reporta a la SEC (p. ej. ONT.L o 3BBLACKBIO.BO) se devuelve available=False con el motivo.
"""

import datetime
import json
import os
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"

CASH_CONCEPTS = [
    "CashAndCashEquivalentsAtCarryingValue",
    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    "Cash",
]
SHORT_TERM_INV_CONCEPTS = [
    "ShortTermInvestments",
    "MarketableSecuritiesCurrent",
    "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
    "HeldToMaturitySecuritiesCurrent",
]
LONG_TERM_INV_CONCEPTS = [
    "MarketableSecuritiesNoncurrent",
    "AvailableForSaleSecuritiesDebtSecuritiesNoncurrent",
    "LongTermInvestments",
]
OPCF_CONCEPT = "NetCashProvidedByUsedInOperatingActivities"


def _parse_date(s: str) -> datetime.date:
    return datetime.date.fromisoformat(s[:10])


class SecVitalsFetcher:
    def __init__(self, user_agent: Optional[str] = None, min_interval_s: float = 0.15):
        contact = (os.environ.get("SMTP_USER") or os.environ.get("NOTIFY_EMAIL") or "").strip()
        self.user_agent = (
            user_agent
            or (os.environ.get("SEC_USER_AGENT") or "").strip()
            or (f"RadarBolsaPersonal/1.0 {contact}" if contact else "RadarBolsaPersonal/1.0")
        )
        self.min_interval_s = min_interval_s
        self._last_call = 0.0
        self._ticker_map: Optional[Dict[str, int]] = None

    # ------------------------------------------------------------------ HTTP
    def _get(self, url: str, timeout: int = 25) -> bytes:
        wait = self.min_interval_s - (time.time() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.user_agent, "Accept-Encoding": "identity", "Accept": "*/*"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        finally:
            self._last_call = time.time()

    def _get_json(self, url: str) -> Dict[str, Any]:
        return json.loads(self._get(url).decode("utf-8", errors="replace"))

    # ------------------------------------------------------------- Mapeo CIK
    def cik_for(self, ticker: str) -> Optional[int]:
        if "." in ticker:  # Tickers europeos/indios de Yahoo (ONT.L, 3BBLACKBIO.BO...) no reportan a la SEC
            return None
        if self._ticker_map is None:
            data = self._get_json(SEC_TICKERS_URL)
            self._ticker_map = {
                str(v.get("ticker", "")).upper(): int(v.get("cik_str"))
                for v in data.values()
                if v.get("ticker") and v.get("cik_str") is not None
            }
        return self._ticker_map.get(ticker.upper())

    # ------------------------------------------------------- Extracción XBRL
    @staticmethod
    def _usd_entries(facts: Dict[str, Any], concept: str) -> List[Dict[str, Any]]:
        node = (facts.get("facts", {}).get("us-gaap", {}) or {}).get(concept) or {}
        return list((node.get("units") or {}).get("USD") or [])

    @classmethod
    def _instant_values_by_date(cls, facts: Dict[str, Any], concepts: List[str]) -> Tuple[Optional[str], Dict[str, float]]:
        """Primer concepto con datos: devuelve (concepto, {fecha_fin: valor más recientemente presentado})."""
        for c in concepts:
            entries = [e for e in cls._usd_entries(facts, c) if "start" not in e and e.get("end")]
            if not entries:
                continue
            by_end: Dict[str, Tuple[str, float]] = {}
            for e in entries:
                end = e["end"]
                filed = e.get("filed", "")
                if end not in by_end or filed > by_end[end][0]:
                    by_end[end] = (filed, float(e["val"]))
            return c, {k: v[1] for k, v in by_end.items()}
        return None, {}

    @classmethod
    def compute_cash(cls, facts: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        cash_c, cash_by_end = cls._instant_values_by_date(facts, CASH_CONCEPTS)
        if not cash_by_end:
            return None
        as_of = max(cash_by_end.keys())
        total = cash_by_end[as_of]
        parts = [cash_c]
        for group in (SHORT_TERM_INV_CONCEPTS, LONG_TERM_INV_CONCEPTS):
            c, vals = cls._instant_values_by_date(facts, group)
            if c and as_of in vals:
                total += vals[as_of]
                parts.append(c)
        return {"as_of": as_of, "total_usd": total, "concepts": parts}

    @classmethod
    def compute_ttm_operating_cash_flow(cls, facts: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        entries = [e for e in cls._usd_entries(facts, OPCF_CONCEPT) if e.get("start") and e.get("end")]
        if not entries:
            return None
        dedup: Dict[Tuple[str, str], Tuple[str, float]] = {}
        for e in entries:
            key = (e["start"], e["end"])
            filed = e.get("filed", "")
            if key not in dedup or filed > dedup[key][0]:
                dedup[key] = (filed, float(e["val"]))
        periods = [
            {"start": _parse_date(s), "end": _parse_date(en), "val": v[1]}
            for (s, en), v in dedup.items()
        ]
        for p in periods:
            p["days"] = (p["end"] - p["start"]).days
        latest_end = max(p["end"] for p in periods)
        latest = max((p for p in periods if p["end"] == latest_end), key=lambda p: p["days"])

        if latest["days"] >= 350:
            return {"ttm_usd": latest["val"], "as_of": latest_end.isoformat(), "method": "anual"}

        annual = [
            p for p in periods
            if p["days"] >= 350 and abs((latest["start"] - p["end"]).days) <= 10
        ]
        prior_ytd = [
            p for p in periods
            if abs(p["days"] - latest["days"]) <= 20
            and abs((latest["end"] - p["end"]).days - 365) <= 20
        ]
        if annual and prior_ytd:
            ttm = annual[0]["val"] + latest["val"] - prior_ytd[0]["val"]
            return {"ttm_usd": ttm, "as_of": latest_end.isoformat(), "method": "TTM (anual + acumulado del año - mismo periodo anterior)"}
        if latest["days"] > 0:
            ttm = latest["val"] * 365.0 / latest["days"]
            return {"ttm_usd": ttm, "as_of": latest_end.isoformat(), "method": f"anualizado desde {latest['days']} días"}
        return None

    @staticmethod
    def compute_shares_outstanding(facts: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        candidates = [
            ((facts.get("facts", {}).get("dei", {}) or {}).get("EntityCommonStockSharesOutstanding") or {}),
            ((facts.get("facts", {}).get("us-gaap", {}) or {}).get("CommonStockSharesOutstanding") or {}),
        ]
        for node in candidates:
            entries = list(((node.get("units") or {}).get("shares")) or [])
            if not entries:
                continue
            latest_filed = max(e.get("filed", "") for e in entries)
            same_filing = [e for e in entries if e.get("filed", "") == latest_filed]
            latest_end = max(e.get("end", "") for e in same_filing)
            # Varias clases de acciones en la misma portada -> se suman
            total = sum(float(e["val"]) for e in same_filing if e.get("end", "") == latest_end)
            if total > 0:
                return {"shares": total, "as_of": latest_end}
        return None

    # ---------------------------------------------------------- Form 4
    @staticmethod
    def parse_form4_xml(xml_bytes: bytes) -> Dict[str, float]:
        out = {"buy_usd": 0.0, "sell_usd": 0.0, "buy_tx": 0, "sell_tx": 0}
        root = ET.fromstring(xml_bytes)
        for tx in root.iter("nonDerivativeTransaction"):
            code = (tx.findtext("transactionCoding/transactionCode") or "").strip().upper()
            try:
                shares = float(tx.findtext("transactionAmounts/transactionShares/value") or 0)
            except ValueError:
                shares = 0.0
            try:
                price = float(tx.findtext("transactionAmounts/transactionPricePerShare/value") or 0)
            except ValueError:
                price = 0.0
            if code == "P":
                out["buy_usd"] += shares * price
                out["buy_tx"] += 1
            elif code == "S":
                out["sell_usd"] += shares * price
                out["sell_tx"] += 1
        return out

    def insider_activity(self, cik: int, days: int = 90, max_filings: int = 25) -> Optional[Dict[str, Any]]:
        sub = self._get_json(SEC_SUBMISSIONS_URL.format(cik=cik))
        recent = (sub.get("filings") or {}).get("recent") or {}
        forms = recent.get("form", [])
        accs = recent.get("accessionNumber", [])
        dates = recent.get("filingDate", [])
        docs = recent.get("primaryDocument", [])
        cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
        totals = {"buy_usd": 0.0, "sell_usd": 0.0, "buy_tx": 0, "sell_tx": 0, "filings": 0, "errors": 0}
        checked = 0
        for form, acc, fdate, doc in zip(forms, accs, dates, docs):
            if form != "4" or fdate < cutoff:
                continue
            if checked >= max_filings:
                break
            checked += 1
            raw_doc = re.sub(r"^xsl[^/]*/", "", doc or "")
            if not raw_doc.lower().endswith(".xml"):
                continue
            url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{raw_doc}"
            try:
                r = self.parse_form4_xml(self._get(url))
                for k in ("buy_usd", "sell_usd", "buy_tx", "sell_tx"):
                    totals[k] += r[k]
                totals["filings"] += 1
            except Exception:  # noqa: BLE001
                totals["errors"] += 1
        totals["window_days"] = days
        return totals

    # ------------------------------------------------------------ Resultado
    def get_vitals(self, ticker: str, price_usd: Optional[float]) -> Dict[str, Any]:
        cik = self.cik_for(ticker)
        if not cik:
            return {"available": False, "reason": "No reporta a la SEC de EE. UU. (sin datos oficiales de caja)."}

        facts = self._get_json(SEC_FACTS_URL.format(cik=cik))
        cash = self.compute_cash(facts)
        opcf = self.compute_ttm_operating_cash_flow(facts)
        shares = self.compute_shares_outstanding(facts)
        if not cash:
            return {"available": False, "reason": "La SEC no publica el dato de caja de esta empresa en formato XBRL."}

        total_cash_musd = round(cash["total_usd"] / 1e6, 1)
        burn_annual_musd = None
        runway_months = None
        cash_flow_positive = False
        if opcf:
            if opcf["ttm_usd"] >= 0:
                cash_flow_positive = True
                burn_annual_musd = 0.0
            else:
                burn_annual_musd = round(-opcf["ttm_usd"] / 1e6, 1)
                monthly = burn_annual_musd / 12.0
                runway_months = int(round(total_cash_musd / monthly)) if monthly > 0 else None

        market_cap_musd = None
        if shares and price_usd:
            market_cap_musd = round(shares["shares"] * float(price_usd) / 1e6, 1)
        trading_below_cash = bool(market_cap_musd is not None and market_cap_musd < total_cash_musd)

        if cash_flow_positive:
            dilution_risk = "Bajo (genera caja con su actividad)"
        elif runway_months is None:
            dilution_risk = "Sin dato de quema de caja"
        elif runway_months < 12:
            dilution_risk = "Alto"
        elif runway_months < 18:
            dilution_risk = "Medio"
        else:
            dilution_risk = "Bajo"

        insiders = None
        try:
            insiders = self.insider_activity(cik)
        except Exception as exc:  # noqa: BLE001
            print(f"[WARN] Form 4 de {ticker} no disponibles: {exc}")

        if insiders and insiders.get("filings"):
            b, s = insiders["buy_usd"], insiders["sell_usd"]
            if insiders["buy_tx"] == 0 and insiders["sell_tx"] == 0:
                insider_text = f"Sin compras ni ventas en mercado abierto en {insiders['window_days']} días ({insiders['filings']} Form 4 revisados: concesiones, opciones, etc.)."
            else:
                insider_text = (
                    f"Últimos {insiders['window_days']} días: compras ${b/1e6:.2f}M ({insiders['buy_tx']} op.) · "
                    f"ventas ${s/1e6:.2f}M ({insiders['sell_tx']} op.). Muchas ventas son planes 10b5-1 o pago de impuestos; las compras con dinero propio son la señal fuerte."
                )
        elif insiders is not None:
            insider_text = f"Ningún Form 4 presentado en los últimos {insiders['window_days']} días."
        else:
            insider_text = "No se pudieron consultar los Form 4 hoy."

        return {
            "available": True,
            "source": "SEC EDGAR",
            "cik": cik,
            "balance_date": cash["as_of"],
            "total_cash_musd": total_cash_musd,
            "annual_burn_musd": burn_annual_musd,
            "burn_method": opcf["method"] if opcf else None,
            "cash_flow_positive": cash_flow_positive,
            "cash_runway_months": runway_months,
            "shares_outstanding": shares["shares"] if shares else None,
            "market_cap_musd": market_cap_musd,
            "trading_below_cash": trading_below_cash,
            "dilution_risk": dilution_risk,
            "insiders": insiders,
            "insider_activity": insider_text,
        }
