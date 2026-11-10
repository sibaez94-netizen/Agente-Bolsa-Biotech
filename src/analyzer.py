# -*- coding: utf-8 -*-
"""
Motor Analítico, Pedagógico y con Memoria Episódica para el Agente de Bolsa.
- Antes de responder en cada ronda, chequea la memoria almacenada en SQLite (data/bolsa.db):
  compara precios, rachas de días subiendo/bajando, entradas o salidas de zonas de soporte
  y titulares nuevos frente a sesiones anteriores.
- Explica cada indicador (RSI, Soporte Histórico 3Y, Cash Runway, Dilución, DCA e Interés Compuesto)
  de forma profunda, intuitiva y didáctica en español.
"""

import datetime
import json
import os
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

GEMINI_MASTER_SYSTEM_PROMPT = """[ROL Y OBJETIVO]
Eres mi Mentor y Analista Jefe de Inversiones Personal con MEMORIA EPISÓDICA. Soy Doctor en genética vegetal, experto y distribuidor en diagnóstico in vitro (PCR, NGS, anatomía patológica y biología molecular hospitalaria en España) y sigo de cerca la geopolítica, pero ESTOY EMPEZANDO DE CERO EN BOLSA y quiero aprender mientras invierto.
Tu objetivo es analizar:
1) La MEMORIA DE SESIONES ANTERIORES (qué precios teníamos guardados, qué activos han entrado o salido de soporte y qué rachas llevan).
2) Los PRECIOS REALES DE HOY y su posición en los últimos 3 años.
3) Las NOTICIAS DEL SECTOR (FierceBiotech, AgFunderNews, DefenseNews y PubMed RNAi/CRISPR).
Y redactar un INFORME DIARIO PROFUNDO, DIDÁCTICO E INTUITIVO en español. No uses jerga financiera sin explicarla con analogías sencillas. Explícame el "porqué" de cada movimiento, qué ha cambiado respecto a los días anteriores guardados en memoria y qué debería hacer hoy.

[MI PERFIL Y ESTRATEGIA (CORE-SATELLITE · 200 €/mes DCA en XTB)]
Opero desde España en euros (€) con 200 €/mes mediante compras periódicas (DCA) de acciones fraccionadas. Mi cartera tiene DOS velocidades:
1. ESTRATEGIA LARGO PLAZO (No tocar salvo alerta gorda o rebajas históricas):
   - NÚCLEO (50% - 100€/mes): iShares Core MSCI World (EUNL.DE, de Acumulación).
   - SATÉLITE 1 - DIAGNÓSTICO Y LABORATORIO (20% - 40€/mes): Thermo Fisher (TMO), Danaher (DHR - dueña de Cepheid, Beckman Coulter, Leica y Radiometer), Siemens Healthineers (SHL.DE), Roche (ROG.SW), Illumina (ILMN), ETF China Salud con Mindray (KURE) y ETF India (NDIA.L).
   - SATÉLITE 2 - AGTECH, GENÉTICA VEGETAL CRISPR Y RNAi (15% - 30€/mes): Vylor (VYLR, el negocio de semillas Pioneer/Brevant y edición genética separado de Corteva el 1 de octubre de 2026), Corteva (CTVA, ahora solo protección de cultivos, en radar con 0 €) y Novonesis (NSIS-B.CO, microbioma agrícola).
   - SATÉLITE 3 - GEOPOLÍTICA Y DEFENSA OTAN (10% - 20€/mes): VanEck Defense UCITS ETF (DFNS.MI) y Rheinmetall (RHM.DE).
2. ESTRATEGIA DINÁMICA DE SEGUIMIENTO DIARIO (Vigilar catalizadores y caja):
   - SATÉLITE 4 - BIOTECH FASE CLÍNICA Y RADAR (5% - 10€/mes): Bicycle Therapeutics (BCYC - péptidos bicíclicos), Beam Therapeutics (BEAM - edición de bases 2.0), Summit Therapeutics (SMMT - biespecífico Ivonescimab), Oxford Nanopore (ONT.L), Ginkgo Bioworks (DNA), Guardant Health (GH - biopsia líquida) y 3B Blackbio DX (3BBLACKBIO.BO).

[ESTRUCTURA OBLIGATORIA DE TU RESPUESTA]
Redacta un informe claro, cercano, profundo y muy bien estructurado en estos 6 bloques:
1. 🧠 MEMORIA DEL AGENTE (Qué ha cambiado desde la última ronda guardada): Resume qué variaciones, rachas o cambios de estado se han producido respecto a los días previos almacenados en nuestra base de datos.
2. 🧭 TU BRÚJULA DE HOY (¿Qué tengo que hacer hoy en XTB?): Dime claramente si hoy debo hacer algo o dejar el plan automático tranquilo, y qué empresas están hoy a precio de "rebajas históricas".
3. 🛡️ LARGO PLAZO · EL NÚCLEO INTOCABLE (EUNL.DE): Explica cómo va mi índice mundial, por qué el interés compuesto de acumulación trabaja solo y por qué no debemos tocarlo.
4. 🎯 TUS GIGANTES DE LABORATORIO, AGTECH Y DEFENSA (Precios vs. Soportes de 3 años): Explica en lenguaje intuitivo cómo están TMO, DHR, SHL.DE, VYLR y DFNS.MI respecto a su "suelo histórico" de los últimos 3 años y qué significa su RSI.
5. 🔬 SEGUIMIENTO DIARIO · BIOTECH CLÍNICA Y ESCUDO ANTI-DILUCIÓN: Analiza BCYC, BEAM, SMMT, DNA, GH y ONT.L explicando sus 3 constantes vitales (Cash Runway o meses de vida en banco, valor en bolsa vs caja e insiders) para no caer nunca en una trampa tipo Biocartis o GreenLight.
6. 📰 LECTURA TRADUCIDA Y EXPLICADA DE LAS NOTICIAS DE HOY: Explica en español qué dicen los titulares nuevos de hoy de FierceBiotech, AgFunderNews, DefenseNews y PubMed (RNAi/CRISPR) y cómo conectan con mis empresas.

[REGLA INNEGOCIABLE SOBRE LOS DATOS]
Usa EXCLUSIVAMENTE las cifras que te paso (precios, caja, runway, capitalización, insiders, noticias). No inventes ni estimes cifras de memoria.
Si un dato no aparece (por ejemplo una empresa sin constantes vitales o un activo "SIN DATOS HOY"), dilo claramente en vez de rellenarlo.
"""


class PortfolioAnalyzer:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.thresholds = config.get("alert_thresholds", {})
        self.allocations = config.get("allocations", {})

    @staticmethod
    def explain_rsi_human(rsi: Optional[float]) -> str:
        if rsi is None:
            return "Sin datos suficientes de sesiones recientes."
        if rsi <= 30:
            return f"RSI {rsi:.0f}/100 (Muy barato / 'Sobreventa'): El mercado ha vendido con pánico exagerado. Históricamente suele ser una gran oportunidad de rebote al alza."
        if rsi <= 40:
            return f"RSI {rsi:.0f}/100 (Zona fría / Atractiva): Hay más vendedores que compradores últimamente, lo que deja el precio en niveles interesantes para acumular."
        if rsi <= 62:
            return f"RSI {rsi:.0f}/100 (Zona templada / Equilibrio): Ni hay fiebre compradora ni pánico vendedor. Precio moviéndose con normalidad para tu compra mensual DCA."
        if rsi <= 70:
            return f"RSI {rsi:.0f}/100 (Zona cálida / Fuerte): La acción lleva semanas subiendo con fuerza porque hay mucho interés comprador."
        return f"RSI {rsi:.0f}/100 (Caliente / 'Sobrecompra'): Ha subido muy rápido en pocos días; conviene no perseguir el precio con compras extraordinarias hoy y esperar a que respire."

    @staticmethod
    def explain_support_position_human(
        cur_price: float,
        sup_low: float,
        sup_high: float,
        low_3y: float,
        high_3y: float,
        currency: str,
        in_support_zone: bool,
    ) -> str:
        span = max(0.01, high_3y - low_3y)
        pct_in_range = max(0.0, min(100.0, ((cur_price - low_3y) / span) * 100.0))
        if in_support_zone:
            return (
                f"🎯 ¡EN ZONA DE REBAJAS HISTÓRICAS! Hoy cotiza a {cur_price:.2f} {currency}, que está en el {pct_in_range:.0f}% más bajo "
                f"de todo su recorrido de los últimos 3 años (suelo entre {sup_low:.1f} y {sup_high:.1f} {currency}, frente a un máximo de {high_3y:.1f} {currency}). "
                f"En bolsa, a este suelo donde la caída suele frenarse porque los grandes fondos ven el precio irresistible se le llama 'Soporte Histórico'."
            )
        if pct_in_range <= 40:
            return (
                f"Precio razonable en la mitad baja de los últimos 3 años (está en el {pct_in_range:.0f}% de su rango entre el mínimo de {low_3y:.1f} {currency} "
                f"y el máximo de {high_3y:.1f} {currency}). Su zona de 'chollo histórico' empieza si baja a {sup_high:.1f} {currency}."
            )
        if pct_in_range <= 75:
            return (
                f"En zona media-alta de los últimos 3 años ({pct_in_range:.0f}% del recorrido entre {low_3y:.1f} y {high_3y:.1f} {currency}). "
                f"Para tu compra automática mensual (DCA) está bien porque promedias precio, pero si quisieras hacer una compra extra buscando rebajas, "
                f"deberías dejar puesta una 'Orden Limitada' (compra automática condicional) en torno a {sup_high:.1f} {currency}."
            )
        return (
            f"Cotizando cerca de sus máximos de 3 años ({pct_in_range:.0f}% del rango entre {low_3y:.1f} y {high_3y:.1f} {currency}). "
            f"Significa que la empresa va como un tiro y el mercado la premia, pero no está 'barata' hoy: mantén solo tu pequeña cuota automática mensual sin meter dinero extra de golpe."
        )

    @staticmethod
    def contextualize_news_item_es(n: Dict[str, str]) -> str:
        if n.get("summary") and len(n["summary"]) > 40 and any(w in n["summary"].lower() for w in ["ensayos", "aprobación", "cartera", "paper"]):
            return n["summary"]

        title_low = (n.get("title") or "").lower()
        cat_low = (n.get("category") or "").lower()
        src = n.get("source", "Prensa Sectorial")

        if "pubmed" in src.lower() or "rnai" in title_low or "dsrna" in title_low or "crispr" in title_low:
            return (
                "🔬 Lectura Científica para tu Satélite 2 (AgTech): Esta publicación confirma avances en silenciamiento génico (RNAi/dsRNA) "
                "y mejora vegetal CRISPR. Respalda directamente la ventaja tecnológica de Vylor (VYLR) y Novonesis (NSIS-B.CO) de cara a la desregulación europea NGT1 en 2028."
            )
        if "agfunder" in src.lower() or "agtech" in cat_low or any(w in title_low for w in ["food", "agri", "crop", "seed", "protein", "farm"]):
            return (
                "🌱 Impacto en tu Satélite 2 (Agricultura y Biotecnología Vegetal): Los movimientos en cadenas de suministro agroalimentarias, "
                "proteínas alternativas y bioinsumos refuerzan la necesidad de semillas más resistentes y biopesticidas, el negocio central de Vylor (VYLR, semillas) y Novonesis (bioinsumos)."
            )
        if "defense" in src.lower() or "geopol" in cat_low or any(w in title_low for w in ["nato", "army", "troops", "arms", "military", "ukraine", "missile"]):
            return (
                "🛡️ Impacto en tu Satélite 3 (Geopolítica y Defensa): Confirma que los presupuestos de defensa, munición y despliegue militar en Europa y la OTAN "
                "siguen en fase expansiva obligatoria. Esto alimenta directamente la cartera de contratos del ETF VanEck Defense (DFNS.MI) y de Rheinmetall (RHM.DE)."
            )
        return (
            "🧬 Impacto en tus Satélites 1 y 4 (Biotecnología y Diagnóstico): Movimiento relevante en el ecosistema farma/biotech internacional. "
            "Recuerda que mientras las startups clínicas (BCYC, BEAM, SMMT) se juegan el éxito en cada ensayo de la FDA, gigantes como Thermo Fisher (TMO) y Danaher (DHR) "
            "ganan dinero vendiendo los equipos, secuenciadores y reactivos a todos los laboratorios por igual."
        )

    def analyze_portfolio(
        self,
        quotes: Dict[str, Dict[str, Any]],
        news: List[Dict[str, str]],
        previous_memory: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        prev_mem = previous_memory or {"prev_assets": {}, "journal_entries": [], "seen_news_urls": {}}
        prev_assets_map = prev_mem.get("prev_assets", {})
        seen_news_urls = prev_mem.get("seen_news_urls", {})
        today_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

        analyzed_assets: List[Dict[str, Any]] = []
        long_term_alerts: List[Dict[str, Any]] = []
        dynamic_alerts: List[Dict[str, Any]] = []
        support_opportunities: List[Dict[str, Any]] = []
        memory_highlights: List[str] = []

        # Enriquecer cada noticia con su explicación didáctica en español + etiqueta de Memoria (Nueva vs Ya vista)
        enriched_news: List[Dict[str, str]] = []
        for n in news:
            n_copy = dict(n)
            n_url = (n_copy.get("url") or "").strip()
            first_seen = seen_news_urls.get(n_url)
            n_copy["is_new_today"] = (first_seen is None) or (first_seen == today_str)
            n_copy["first_seen_date"] = first_seen or today_str
            n_copy["explanation_es"] = self.contextualize_news_item_es(n_copy)
            enriched_news.append(n_copy)

        unavailable_assets: List[Dict[str, Any]] = []
        for asset_cfg in self.config.get("assets", []):
            ticker = asset_cfg["ticker"]
            q = quotes.get(ticker, {})
            if not q.get("data_ok"):
                unavailable_assets.append(
                    {
                        "ticker": ticker,
                        "name": asset_cfg.get("name", ticker),
                        "error": q.get("error", "Sin respuesta de Yahoo Finance"),
                    }
                )
                continue
            cur_price = float(q.get("current_price") or 0.0)
            chg_1d = float(q.get("change_1d_pct") or 0.0)
            chg_5d = float(q.get("change_5d_pct") or 0.0)
            chg_1m = float(q.get("change_1m_pct") or 0.0)
            chg_1y = float(q.get("change_1y_pct") or 0.0)
            chg_2y = float(q.get("change_2y_pct") or 0.0)
            low_3y = float(q.get("low_3y") or cur_price)
            high_3y = float(q.get("high_3y") or cur_price)
            drawdown_3y = float(q.get("drawdown_3y_pct") or 0.0)
            rsi_14 = q.get("rsi_14")

            if q.get("dyn_support_low") and q.get("dyn_support_high"):
                sup_low = float(q["dyn_support_low"])
                sup_high = float(q["dyn_support_high"])
            elif low_3y > 0 and high_3y > low_3y:
                sup_low = round(low_3y, 2)
                sup_high = round(low_3y + (high_3y - low_3y) * 0.22, 2)
            else:
                sup_low = float(asset_cfg.get("historical_support_low") or low_3y)
                sup_high = float(asset_cfg.get("historical_support_high") or low_3y * 1.08)

            dist_to_support_pct = (
                round(((cur_price - sup_high) / sup_high) * 100.0, 1) if sup_high > 0 and cur_price > 0 else 0.0
            )
            in_support_zone = cur_price > 0 and cur_price <= (sup_high * 1.03)

            strategy_mode = asset_cfg.get("strategy_mode", "long_term_tactical")
            is_dynamic = strategy_mode == "dynamic_daily"
            is_core = asset_cfg.get("category") == "core_msci_world"
            curr = asset_cfg.get("currency", "USD")

            # Comparación con la Memoria Almacenada de Rondas Anteriores
            p_mem = prev_assets_map.get(ticker)
            memory_note = ""
            chg_since_first_pct = 0.0
            streak_days = 0
            support_transition = "unchanged"

            if p_mem:
                first_p = float(p_mem.get("first_tracked_price") or cur_price)
                first_d = p_mem.get("first_tracked_date") or today_str
                last_p = float(p_mem.get("last_recorded_price") or cur_price)
                last_d = p_mem.get("last_recorded_date") or today_str
                prev_sup = bool(p_mem.get("prev_in_support_zone", False))
                streak_days = int(p_mem.get("streak_days") or 0)

                if first_p > 0:
                    chg_since_first_pct = round(((cur_price - first_p) / first_p) * 100.0, 2)
                diff_vs_last_pct = round(((cur_price - last_p) / last_p) * 100.0, 2) if last_p > 0 else 0.0

                if in_support_zone and not prev_sup:
                    support_transition = "entered_support"
                    memory_note = f"🆕 ¡NOVEDAD EN MEMORIA! Hoy ha entrado en zona de Soporte Histórico (en la sesión anterior del {last_d} cotizaba a {last_p:.2f} {curr})."
                    memory_highlights.append(f"🎯 {ticker} ({asset_cfg['name']}) acaba de entrar HOY en zona de soporte histórico ({cur_price:.2f} {curr}).")
                elif not in_support_zone and prev_sup:
                    support_transition = "exited_support"
                    memory_note = f"📈 Ha rebotado y salido al alza de su zona de soporte (venía de {last_p:.2f} {curr} el {last_d})."
                    memory_highlights.append(f"📈 {ticker} ha rebotado desde su soporte histórico hasta {cur_price:.2f} {curr} ({chg_since_first_pct:+.1f}% desde el inicio del seguimiento).")
                else:
                    streak_str = ""
                    if streak_days >= 2:
                        streak_str = f" · Encadena {streak_days} sesiones seguidas subiendo."
                    elif streak_days <= -2:
                        streak_str = f" · Encadena {abs(streak_days)} sesiones seguidas corrigiendo (vigilar posible suelo)."
                    memory_note = (
                        f"🧠 Memoria desde {first_d} ({p_mem.get('total_sessions_recorded', 1)} sesiones guardadas): "
                        f"evolución acumulada {chg_since_first_pct:+.2f}% (anterior cierre registrado {last_p:.2f} {curr} el {last_d}, {diff_vs_last_pct:+.2f}%){streak_str}"
                    )
                    if abs(chg_since_first_pct) >= 3.5:
                        memory_highlights.append(
                            f"📊 {ticker}: acumula un {chg_since_first_pct:+.1f}% desde que nuestro agente empezó a monitorizarla el {first_d} ({first_p:.2f} -> {cur_price:.2f} {curr})."
                        )
            else:
                memory_note = f"🧠 Primera sesión registrada en memoria hoy ({today_str}) a {cur_price:.2f} {curr}. En la próxima ronda diaria compararemos su evolución desde este punto."

            vitals = q.get("clinical_vitals")
            score, signal_badge, signal_color, reasons, alert_level = self._evaluate_asset_signal(
                asset_cfg=asset_cfg,
                cur_price=cur_price,
                chg_1d=chg_1d,
                chg_5d=chg_5d,
                drawdown_3y=drawdown_3y,
                rsi_14=rsi_14,
                sup_low=sup_low,
                sup_high=sup_high,
                in_support_zone=in_support_zone,
                dist_to_support_pct=dist_to_support_pct,
                vitals=vitals,
            )

            value_of_40eur_2y = round(40.0 * (1.0 + (chg_2y / 100.0)), 2)

            support_explanation = self.explain_support_position_human(
                cur_price, sup_low, sup_high, low_3y, high_3y, curr, in_support_zone
            )
            hist_sessions = int(q.get("history_sessions") or 0)
            if 0 < hist_sessions < 250:
                support_explanation += (
                    f" ⚠️ Ojo: solo hay {hist_sessions} sesiones de cotización, así que este 'suelo' "
                    f"se calcula con menos de un año de historia y es poco fiable."
                )
            rsi_explanation = self.explain_rsi_human(rsi_14)

            enriched = {
                "ticker": ticker,
                "name": asset_cfg["name"],
                "category": asset_cfg["category"],
                "category_label": self.allocations.get(asset_cfg["category"], {}).get("name", asset_cfg["category"]),
                "strategy_mode": strategy_mode,
                "strategy_group": "dynamic" if is_dynamic else "long_term",
                "strategy_label": "Dinámica (Seguimiento Diario)" if is_dynamic else "Largo Plazo (Core / DCA)",
                "currency": curr,
                "exchange": asset_cfg.get("exchange", ""),
                "in_base_dca": bool(asset_cfg.get("in_base_dca", False)),
                "monthly_allocation_eur": float(asset_cfg.get("monthly_allocation_eur", 0)),
                "current_price": cur_price,
                "prev_close": q.get("prev_close", cur_price),
                "change_1d_pct": chg_1d,
                "change_5d_pct": chg_5d,
                "change_1m_pct": chg_1m,
                "change_1y_pct": chg_1y,
                "change_2y_pct": chg_2y,
                "change_since_first_tracked_pct": chg_since_first_pct,
                "streak_days": streak_days,
                "support_transition": support_transition,
                "memory_note": memory_note,
                "value_of_40eur_2y": value_of_40eur_2y,
                "low_3y": low_3y,
                "high_3y": high_3y,
                "drawdown_3y_pct": drawdown_3y,
                "sma_50": q.get("sma_50"),
                "sma_200": q.get("sma_200"),
                "rsi_14": rsi_14,
                "rsi_explanation": rsi_explanation,
                "historical_support_low": sup_low,
                "historical_support_high": sup_high,
                "in_support_zone": in_support_zone,
                "dist_to_support_pct": dist_to_support_pct,
                "support_explanation": support_explanation,
                "opportunity_score": score,
                "signal_badge": signal_badge,
                "signal_color": signal_color,
                "alert_level": alert_level,
                "reasons": reasons,
                "thesis": asset_cfg.get("thesis", ""),
                "sell_rule": asset_cfg.get("sell_rule", ""),
                "clinical_vitals": vitals,
                "recent_history": q.get("recent_history", {}),
                "quote_source": q.get("source", "Yahoo Finance"),
                "last_session_date": q.get("last_session_date"),
                "history_sessions": hist_sessions,
                "yahoo_url": f"https://finance.yahoo.com/quote/{ticker}",
            }

            analyzed_assets.append(enriched)

            if in_support_zone and not is_core:
                support_opportunities.append(enriched)

            if is_dynamic:
                if alert_level in ("high", "medium") or abs(chg_1d) >= 2.5 or in_support_zone:
                    dynamic_alerts.append(enriched)
            else:
                if alert_level == "high":
                    long_term_alerts.append(enriched)

        analyzed_assets.sort(key=lambda x: (x["in_base_dca"], x["opportunity_score"]), reverse=True)
        support_opportunities.sort(key=lambda x: x["opportunity_score"], reverse=True)

        data_warnings: List[str] = []
        if unavailable_assets:
            data_warnings.append(
                f"Hoy no se pudo descargar la cotización de {len(unavailable_assets)} activo(s): "
                + ", ".join(u["ticker"] for u in unavailable_assets)
                + ". No se muestran precios inventados: esos valores aparecerán en el próximo informe con datos reales."
            )
        if not analyzed_assets:
            data_warnings.append("⚠️ Sin datos de mercado hoy: no hay ninguna cotización real disponible.")

        memory_comparison_summary = (
            " | ".join(memory_highlights[:4])
            if memory_highlights
            else "Estabilidad general respecto a las sesiones previas almacenadas en la base de datos."
        )

        ai_briefing, briefing_sections, briefing_source = self.generate_deep_pedagogical_briefing(
            analyzed_assets=analyzed_assets,
            long_term_alerts=long_term_alerts,
            support_opportunities=support_opportunities,
            dynamic_alerts=dynamic_alerts,
            news=enriched_news,
            previous_memory=prev_mem,
            memory_highlights=memory_highlights,
            unavailable_assets_for_briefing=[
                dict(u, category=next((c.get("category") for c in self.config.get("assets", []) if c["ticker"] == u["ticker"]), ""))
                for u in unavailable_assets
            ],
        )

        return {
            "assets": analyzed_assets,
            "long_term_alerts": long_term_alerts,
            "support_opportunities": support_opportunities,
            "dynamic_alerts": dynamic_alerts,
            "news": enriched_news,
            "ai_briefing": ai_briefing,
            "briefing_sections": briefing_sections,
            "memory_comparison_summary": memory_comparison_summary,
            "briefing_source": briefing_source,
            "unavailable_assets": unavailable_assets,
            "data_warnings": data_warnings,
        }

    def _evaluate_asset_signal(
        self,
        asset_cfg: Dict[str, Any],
        cur_price: float,
        chg_1d: float,
        chg_5d: float,
        drawdown_3y: float,
        rsi_14: Optional[float],
        sup_low: float,
        sup_high: float,
        in_support_zone: bool,
        dist_to_support_pct: float,
        vitals: Optional[Dict[str, Any]],
    ) -> Tuple[int, str, str, List[str], str]:
        reasons: List[str] = []
        score = 55
        cat = asset_cfg.get("category", "")
        mode = asset_cfg.get("strategy_mode", "long_term_tactical")
        curr = asset_cfg.get("currency", "")

        if cat == "core_msci_world":
            if chg_1d <= float(self.thresholds.get("core_major_drop_daily_pct", -4.0)) or drawdown_3y <= float(
                self.thresholds.get("core_major_drawdown_pct", -10.0)
            ):
                score = 92
                reasons.append(
                    f"Alerta Gorda en Núcleo ({chg_1d:+.1f}% hoy | {drawdown_3y:+.1f}% desde máximos): Recuerda que cuando el mundo cae fuerte NO se vende (si vendes pagas un 19%-21% a Hacienda y rompes el interés compuesto). Al contrario: tus 100 €/mes ahora compran más participaciones baratas."
                )
                return score, "🚨 REBAJA EN NÚCLEO (NO VENDER)", "amber", reasons, "high"
            reasons.append(
                "Tu fondo índice de las 1.500 mayores empresas del mundo sigue creciendo en piloto automático. Al ser de Acumulación (Acc), cobra los dividendos de Apple, Microsoft, etc. y los reinvierte dentro del fondo sin que tengas que hacer nada ni pagar impuestos hoy."
            )
            reasons.append(f"Cotización hoy: {cur_price:.2f} {curr} ({chg_1d:+.2f}% en el día).")
            return 68, "🟢 PILOTO AUTOMÁTICO (INTOCABLE)", "green", reasons, "low"

        if in_support_zone:
            score += 26
            reasons.append(
                f"🎯 En Suelo Histórico de 3 Años ({sup_low:.1f} - {sup_high:.1f} {curr} vs precio actual {cur_price:.2f} {curr}): Está en la franja más barata de los últimos 3 años, donde históricamente deja de caer y rebota."
            )
        elif dist_to_support_pct <= 10.0:
            score += 12
            reasons.append(
                f"Bastante cerca de su suelo de compra de 3 años ({sup_low:.1f} - {sup_high:.1f} {curr}, a solo un {dist_to_support_pct:+.1f}% de distancia)."
            )
        else:
            reasons.append(
                f"Cotizando por encima de su suelo de rebajas de 3 años ({sup_low:.1f} - {sup_high:.1f} {curr}). Para tu cuota fija mensual (DCA) sigue adelante sin problema; para meter dinero extra de golpe, sería mejor dejar una Orden Limitada en {sup_high:.1f} {curr}."
            )

        if chg_1d <= -3.5:
            score += 16
            reasons.append(
                f"📉 Caída fuerte hoy ({chg_1d:+.2f}%): Cuando una empresa sólida cae así en un solo día, suele ser una sobrerreacción de Wall Street que te permite comprar más acciones con los mismos euros."
            )
        elif chg_5d <= -5.0:
            score += 10
            reasons.append(f"Retroceso acumulado de {chg_5d:+.2f}% en los últimos 5 días bursátiles (posible descuento a corto plazo).")

        if rsi_14 is not None:
            if rsi_14 <= 34:
                score += 12
                reasons.append(f"Termómetro RSI en {rsi_14:.0f}/100 (Sobreventa): Ha habido demasiadas ventas seguidas y el precio está estadísticamente comprimido.")
            elif rsi_14 >= 72:
                score -= 8
                reasons.append(f"Termómetro RSI en {rsi_14:.0f}/100 (Sobrecompra): Ha subido muy deprisa últimamente; mejor no hacer compras impulsivas hoy.")

        if vitals and vitals.get("available"):
            min_runway = float(self.thresholds.get("min_safe_cash_runway_months", 15))
            runway = vitals.get("cash_runway_months")
            cash_m = vitals.get("total_cash_musd")
            bal_date = vitals.get("balance_date", "")
            if vitals.get("trading_below_cash"):
                score -= 25
                reasons.append(
                    f"⚠️ ALERTA ANTI-DILUCIÓN: toda la empresa vale en bolsa ${vitals.get('market_cap_musd')}M, menos que los ${cash_m}M de caja e inversiones que declaró a la SEC ({bal_date}). "
                    "El mercado duda de que esa caja se convierta en valor; no meter dinero aquí sin un catalizador claro."
                )
                return max(15, min(99, score)), "⚠️ RIESGO DILUCIÓN / BAJO CAJA", "red", reasons, "high"
            if vitals.get("cash_flow_positive"):
                score += 6
                reasons.append(f"✅ Genera caja con su actividad (flujo operativo positivo en 12 meses) y tiene ${cash_m}M de caja ({bal_date}).")
            elif runway is not None and runway < min_runway:
                score -= 18
                reasons.append(
                    f"⚠️ Cuidado con la caja: ${cash_m}M a {bal_date} y quema ~${vitals.get('annual_burn_musd')}M/año → unos {runway} meses de vida. "
                    "Riesgo de ampliación de capital que diluya tu participación."
                )
                return max(20, min(99, score)), f"⚠️ VIGILAR CAJA (<{int(min_runway)} MESES)", "amber", reasons, "high"
            elif runway is not None:
                score += 6
                reasons.append(
                    f"✅ Caja holgada: ${cash_m}M a {bal_date} frente a una quema de ~${vitals.get('annual_burn_musd')}M/año → unos {runway} meses de vida sin necesitar ampliar capital."
                )
            if vitals.get("insider_activity"):
                reasons.append(f"👔 Directivos: {vitals['insider_activity']}")
        elif vitals and not vitals.get("available"):
            reasons.append(f"ℹ️ Constantes vitales: {vitals.get('reason', 'sin datos oficiales hoy')}")

        score = max(15, min(98, int(round(score))))

        if in_support_zone and score >= 76:
            return score, "🎯 EN SUELO HISTÓRICO (OPORTUNIDAD)", "emerald", reasons, "high"
        if chg_1d <= -3.5:
            return score, "📉 REBAJA BRUSCA HOY (OPORTUNIDAD)", "amber", reasons, "high"
        if mode == "dynamic_daily":
            if abs(chg_1d) >= 3.5:
                return score, f"🔥 MOVIMIENTO FUERTE HOY ({chg_1d:+.1f}%)", "blue", reasons, "medium"
            return score, "🔬 VIGILANCIA DIARIA (FASE CLÍNICA)", "blue", reasons, "medium"

        return score, "🟢 MANTENER PLAN DCA NORMAL", "green", reasons, "low"

    def generate_deep_pedagogical_briefing(
        self,
        analyzed_assets: List[Dict[str, Any]],
        long_term_alerts: List[Dict[str, Any]],
        support_opportunities: List[Dict[str, Any]],
        dynamic_alerts: List[Dict[str, Any]],
        news: List[Dict[str, str]],
        previous_memory: Optional[Dict[str, Any]] = None,
        memory_highlights: Optional[List[str]] = None,
        unavailable_assets_for_briefing: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[str, List[Dict[str, str]], str]:
        if not analyzed_assets:
            body = (
                "Hoy no se ha podido descargar ninguna cotización real (Yahoo Finance no respondió). "
                "Para no darte información falsa, el informe de hoy no incluye precios ni recomendaciones: "
                "tu plan de compras periódicas sigue igual y mañana se vuelve a intentar."
            )
            sections = [{"icon": "⚠️", "title": "Sin datos de mercado hoy", "body": body}]
            return body, sections, "Sin datos de mercado"

        by_ticker = {a["ticker"]: a for a in analyzed_assets}
        core = by_ticker.get("EUNL.DE")
        tmo = by_ticker.get("TMO")
        dhr = by_ticker.get("DHR")
        shl = by_ticker.get("SHL.DE")
        vylr = by_ticker.get("VYLR")
        ctva = by_ticker.get("CTVA")
        dfns = by_ticker.get("DFNS.MI")
        bcyc = by_ticker.get("BCYC")
        beam = by_ticker.get("BEAM")
        smmt = by_ticker.get("SMMT")
        dna = by_ticker.get("DNA")

        sections: List[Dict[str, str]] = []

        # BLOQUE 1: Memoria Episódica (Qué ha cambiado respecto a las rondas anteriores guardadas)
        prev_mem = previous_memory or {}
        prev_assets_map = prev_mem.get("prev_assets", {})
        journal_entries = prev_mem.get("journal_entries", [])
        mem_hl = memory_highlights or []

        if prev_assets_map:
            sample_a = next(iter(prev_assets_map.values()))
            sessions_cnt = sample_a.get("total_sessions_recorded", 1)
            first_date = sample_a.get("first_tracked_date", "inicio")
            new_news_cnt = sum(1 for n in news if n.get("is_new_today"))
            hl_text = "\n".join([f"• {h}" for h in mem_hl[:5]]) if mem_hl else "• Todos los activos mantienen su rango de soporte/tendencia respecto al último cierre registrado."
            prev_journal_note = ""
            if journal_entries:
                last_j = journal_entries[0]
                prev_journal_note = (
                    f"\n\n📌 Recordatorio de nuestra última anotación en el Diario ({last_j.get('run_date')}): "
                    f"El núcleo EUNL.DE marcaba {last_j.get('core_price', 0):.2f} € y teníamos en vigilancia de suelo histórico: {last_j.get('alerts_summary', '')}."
                )
            b_mem_text = (
                f"Antes de analizar el mercado de hoy, he chequeado nuestra base de datos histórica (`data/bolsa.db`), donde ya acumulamos {sessions_cnt} sesiones registradas desde el {first_date} y {new_news_cnt} titulares nuevos hoy:\n"
                f"{hl_text}{prev_journal_note}"
            )
        else:
            b_mem_text = (
                "Hoy inauguramos el Diario de Memoria Persistente en `data/bolsa.db`. He dejado guardados los precios base, niveles de RSI, soportes y titulares de hoy para que mañana, antes de contestarte, comparemos qué ha subido, qué ha bajado y qué empresas entran o salen de zona de compra."
            )

        sections.append(
            {
                "icon": "🧠",
                "title": "1. Memoria del Agente: ¿Qué ha cambiado respecto a los días anteriores?",
                "body": b_mem_text,
            }
        )

        # BLOQUE 2: Brújula práctica del día (¿Qué tengo que hacer hoy?)
        healthy_supports = [
            a for a in support_opportunities
            if not (a.get("clinical_vitals") and a["clinical_vitals"].get("trading_below_cash"))
        ]
        if healthy_supports:
            sup_names = ", ".join(
                [f"{a['name']} ({a['ticker']}, a {a['current_price']:.2f} {a['currency']})" for a in healthy_supports]
            )
            b1_text = (
                f"Hoy tu cartera de largo plazo está tranquila, pero el radar ha detectado que tienes en 'zona de rebajas históricas' (suelo de los últimos 3 años) a: {sup_names}. "
                f"¿Qué significa esto en la práctica? Que si este mes vas a meter tus 200 € en XTB, además de tu reparto habitual, estas empresas están en la franja de precio donde históricamente los grandes fondos dejan de vender y empiezan a comprar porque las ven muy baratas. "
                f"En el resto de la cartera no tienes que tocar ni vender absolutamente nada."
            )
        else:
            b1_text = (
                "Hoy es el típico día tranquilo donde el mejor inversor es el que no toca nada. Ninguna de tus empresas principales ha sufrido un desplome de pánico ni una mala noticia clínica. "
                "Tu plan automático de 200 €/mes (Compras Periódicas o DCA) funciona precisamente para días como hoy: vas acumulando fracciones de tus empresas mes a mes sin estresarte mirando si hoy han subido o bajado un 1%."
            )
        sections.append(
            {
                "icon": "🧭",
                "title": "2. Tu Brújula de Hoy: ¿Tengo que hacer algo en el bróker?",
                "body": b1_text,
            }
        )

        # BLOQUE 3: Estrategia 1 (El Núcleo Intocable - MSCI World EUNL.DE)
        if core:
            c_price = core["current_price"]
            c_chg = core["change_1d_pct"]
            c_2y = core["change_2y_pct"]
            b2_text = (
                f"Tu Núcleo es el ETF iShares Core MSCI World (EUNL.DE), donde va la mitad de tu presupuesto (100 € de cada 200 €). "
                f"Hoy cotiza a {c_price:.2f} € ({c_chg:+.2f}% en el día) y acumula una subida del {c_2y:+.1f}% en los últimos 2 años ({core.get('change_since_first_tracked_pct', 0):+.2f}% desde nuestro primer registro en base de datos). "
                f"Piensa en este fondo como en la 'selección natural de Darwin' aplicada a la economía: dentro lleva trocitos de las 1.500 empresas más grandes de los países desarrollados (Apple, Microsoft, Nvidia, farmacéuticas, bancos...). Si una empresa se queda obsoleta, el índice la expulsa sola y mete a la nueva ganadora. "
                f"Además, como elegimos la versión 'Acc' (Acumulación), todos los dividendos que reparten esas 1.500 empresas se reinvierten solos por dentro comprando más acciones sin pasar por tu cuenta bancaria: así hace magia el interés compuesto (ganas beneficios sobre los beneficios anteriores) sin pagar ni un euro a Hacienda hasta dentro de 15 o 20 años."
            )
            sections.append(
                {
                    "icon": "🛡️",
                    "title": "3. Estrategia Largo Plazo · El Núcleo Intocable (MSCI World · 50% de tu cartera)",
                    "body": b2_text,
                }
            )

        # BLOQUE 4: Satélites Estructurales (Diagnóstico IVD, AgTech CRISPR/RNAi y Defensa)
        ivd_parts = []
        if tmo and dhr and shl:
            ivd_parts.append(
                f"• Diagnóstico de Laboratorio y Hospitales (20% -> 40 €/mes): Thermo Fisher (TMO, {tmo['current_price']:.2f} USD, {tmo['change_1d_pct']:+.2f}% hoy) y Danaher (DHR, matriz de Cepheid/GeneXpert, Beckman Coulter y Leica, a {dhr['current_price']:.2f} USD, {dhr['change_1d_pct']:+.2f}% hoy) son los que venden 'los picos y las palas' (reactivos, plásticos, secuenciadores NGS de tumor sólido y PCR rápida) a todos los hospitales. "
                f"Por su parte, Siemens Healthineers (SHL.DE, a {shl['current_price']:.2f} EUR, {shl['change_1d_pct']:+.2f}% hoy) "
                + (
                    f"está dentro de su zona baja de 3 años ({shl['historical_support_low']:.0f}-{shl['historical_support_high']:.0f} €)."
                    if shl.get("in_support_zone")
                    else f"cotiza por encima de su zona baja de 3 años ({shl['historical_support_low']:.0f}-{shl['historical_support_high']:.0f} €)."
                )
            )
        if vylr:
            ctva_note = (
                f" (mientras que la antigua CTVA, hoy a {ctva['current_price']:.2f} USD, se quedó solo con la división de agroquímicos/pesticidas tras la escisión y ya la tenemos marcada con 0 € para no tocarla)"
                if ctva
                else ""
            )
            ivd_parts.append(
                f"• Tu Tesis Doctoral en Agricultura y Genética Vegetal (15% -> 30 €/mes): Vylor Inc. (VYLR, hoy a {vylr['current_price']:.2f} USD, {vylr['change_1d_pct']:+.2f}% hoy) es la compañía 100% pura de Semillas Avanzadas (Pioneer, Brevant), germoplasma y edición genética CRISPR/Cas9 nacida tras separarse de Corteva{ctva_note}. "
                f"Con la nueva legislación europea sobre semillas editadas con CRISPR/Cas sin transgén (NGT1, rumbo a 2028), VYLR te permite invertir exclusivamente en la genética vegetal de alto margen sin comerte el lastre de los agroquímicos tradicionales."
            )
        elif ctva:
            ivd_parts.append(
                f"• Tu Tesis Doctoral en Agricultura y Genética Vegetal (15% -> 30 €/mes): Corteva Agriscience (CTVA, hoy a {ctva['current_price']:.2f} USD, {ctva['change_1d_pct']:+.2f}% hoy) es tu apuesta 'pura' (solo agricultura, sin los juicios del glifosato que lastran a Bayer). "
                f"Con la aprobación en la UE de las plantas editadas con CRISPR sin transgén (NGT1, que entrará de lleno en 2028) y su liderazgo comercial en maíz con silenciamiento génico RNAi (SmartStax PRO), cada vez que Corteva tiene un día flojo en bolsa por la venta de pesticidas químicos tradicionales es una oportunidad para acumular acciones baratas antes de 2028."
            )
        if dfns:
            ivd_parts.append(
                f"• Escudo Geopolítico y Rearme OTAN (10% -> 20 €/mes): Tu ETF de Defensa VanEck (DFNS.MI, hoy a {dfns['current_price']:.2f} EUR, {dfns['change_1d_pct']:+.2f}% hoy) agrupa a los gigantes del armamento, radares y ciberseguridad militar (como Rheinmetall, Thales o Palantir). En vez de jugártela a adivinar qué fabricante ganará el próximo contrato del Ministerio de Defensa, compras toda la cesta de golpe."
            )
        sections.append(
            {
                "icon": "🎯",
                "title": "4. Tus Satélites Estructurales: Diagnóstico IVD, Genética Vegetal (CRISPR/RNAi) y Defensa",
                "body": "\n\n".join(ivd_parts),
            }
        )

        # BLOQUE 5: Estrategia Dinámica Diaria (Biotech Fase Clínica y Escudo Anti-Dilución)
        dyn_lines = []
        dyn_assets = [a for a in analyzed_assets if a.get("category") == "sat4_clinical_biotech_dynamic"]
        for idx, a in enumerate(dyn_assets, 1):
            head = f"{idx}) {a['name']} ({a['ticker']}, {a['current_price']:.2f} {a['currency']}, {a['change_1d_pct']:+.2f}% hoy)"
            v = a.get("clinical_vitals") or {}
            if not v.get("available"):
                dyn_lines.append(f"{head}: sin constantes vitales oficiales — {v.get('reason', 'no consultadas hoy')}.")
                continue
            if v.get("trading_below_cash"):
                verdict = "⚠️ COTIZA POR DEBAJO DE SU CAJA"
            elif v.get("cash_flow_positive"):
                verdict = "✅ GENERA CAJA"
            elif v.get("cash_runway_months") is not None and v["cash_runway_months"] < float(self.thresholds.get("min_safe_cash_runway_months", 15)):
                verdict = "⚠️ CAJA JUSTA"
            else:
                verdict = "✅ CAJA HOLGADA"
            runway_txt = (
                "flujo de caja operativo positivo"
                if v.get("cash_flow_positive")
                else (f"~{v['cash_runway_months']} meses de runway (quema ~${v.get('annual_burn_musd')}M/año)" if v.get("cash_runway_months") is not None else "quema de caja no disponible")
            )
            cap_txt = f"capitalización ~${v['market_cap_musd']}M" if v.get("market_cap_musd") is not None else "capitalización no disponible"
            dyn_lines.append(
                f"{head}: {verdict}. Caja e inversiones ${v.get('total_cash_musd')}M (balance a {v.get('balance_date')}), {runway_txt}, {cap_txt}. "
                f"Directivos: {v.get('insider_activity', 'sin datos')}"
            )
        missing_dyn = [u for u in (unavailable_assets_for_briefing or []) if u.get("category") == "sat4_clinical_biotech_dynamic"]
        for u in missing_dyn:
            dyn_lines.append(f"• {u['ticker']}: sin cotización hoy.")

        b4_text = (
            "Aquí dedicamos solo el 5% del presupuesto (10 €/mes de 'capital riesgo científico'), pero es la parte que vigilamos todos los días porque las biotecnológicas pequeñas en fase clínica pueden multiplicarse si un ensayo sale bien o hundirse si fracasa o se quedan sin dinero.\n\n"
            "Chequeo anti-dilución con datos oficiales de la SEC (último 10-Q/10-K y Form 4 de directivos):\n"
            + ("\n".join(dyn_lines) if dyn_lines else "Hoy no hay datos de las biotech del Satélite 4.")
        )
        sections.append(
            {
                "icon": "🔬",
                "title": "5. Estrategia Dinámica (Seguimiento Diario): Biotech en Fase Clínica y Chequeo Anti-Dilución",
                "body": b4_text,
            }
        )

        # BLOQUE 6: Noticias del día traducidas y conectadas con tu cartera
        news_lines = []
        for idx, n in enumerate(news[:4], 1):
            new_tag = "🆕 NUEVA HOY" if n.get("is_new_today") else f"📌 En memoria ({n.get('first_seen_date')})"
            news_lines.append(
                f"{idx}. [{new_tag} · {n.get('source', 'RSS')}] \"{n.get('title', '')}\"\n"
                f"   👉 Qué significa para ti: {n.get('explanation_es', '')}"
            )
        b5_text = "\n\n".join(news_lines) if news_lines else "Sin titulares críticos en las últimas 24 horas."
        sections.append(
            {
                "icon": "📰",
                "title": "6. Radar de Noticias del Día (Traducidas y Conectadas con tus Empresas)",
                "body": b5_text,
            }
        )

        full_text = "\n\n".join([f"{s['icon']} {s['title'].upper()}\n{s['body']}" for s in sections])

        api_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
        if api_key:
            raw_dump = self._build_raw_prompt_dump(analyzed_assets, news, previous_memory)
            gemini_resp = self._call_gemini_api(api_key, raw_dump)
            if gemini_resp and len(gemini_resp) > 300:
                return gemini_resp.strip(), sections, "Mentor IA Google Gemini + Memoria Histórica SQLite"

        return full_text, sections, "Mentor Pedagógico Core-Satellite + Memoria Histórica SQLite"

    @staticmethod
    def _build_raw_prompt_dump(
        analyzed_assets: List[Dict[str, Any]],
        news: List[Dict[str, str]],
        previous_memory: Optional[Dict[str, Any]] = None,
    ) -> str:
        prev_mem = previous_memory or {}
        journal = prev_mem.get("journal_entries", [])
        mem_lines = [
            f"- Sesión {j.get('run_date')}: EUNL={j.get('core_price')}€ | {j.get('alerts_summary')} | {j.get('key_changes_vs_prev')}"
            for j in journal[:4]
        ] or ["- Primera sesión registrada en memoria."]

        price_lines = []
        for a in analyzed_assets:
            vitals_str = ""
            v = a.get("clinical_vitals") or {}
            if v.get("available"):
                vitals_str = (
                    f" | SEC balance {v.get('balance_date')}: Caja ${v.get('total_cash_musd')}M | Quema anual ${v.get('annual_burn_musd')}M"
                    f" | Runway {v.get('cash_runway_months')}m | Cap ${v.get('market_cap_musd')}M | BajoCaja: {v.get('trading_below_cash')}"
                    f" | Riesgo dilución: {v.get('dilution_risk')} | Insiders: {v.get('insider_activity')}"
                )
            elif v:
                vitals_str = f" | Constantes vitales: {v.get('reason')}"
            price_lines.append(
                f"- {a['ticker']} ({a['name']}): Precio {a['current_price']} {a['currency']} | Hoy: {a['change_1d_pct']:+.2f}% | 2Años: {a['change_2y_pct']:+.1f}% | Soporte 3Y: {a['historical_support_low']}-{a['historical_support_high']} | EnSoporte: {a['in_support_zone']} | RSI: {a.get('rsi_14')} | {a.get('memory_note','')}{vitals_str}"
            )
        news_lines = [
            f"- [{'NUEVA' if n.get('is_new_today') else 'VISTA'} | {n.get('source')}] {n.get('title')}"
            for n in news[:8]
        ]
        return (
            "MEMORIA DE SESIONES ANTERIORES:\n"
            + "\n".join(mem_lines)
            + "\n\nCOTIZACIONES Y CAMBIOS DE HOY:\n"
            + "\n".join(price_lines)
            + "\n\nNOTICIAS RSS Y PUBMED:\n"
            + "\n".join(news_lines)
        )

    @staticmethod
    def _call_gemini_api(api_key: str, user_prompt: str) -> Optional[str]:
        for model_name in ("gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"):
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            payload = {
                "system_instruction": {"parts": [{"text": GEMINI_MASTER_SYSTEM_PROMPT}]},
                "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1800},
            }
            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=18) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                    candidates = data.get("candidates") or []
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts") or []
                        if parts and parts[0].get("text"):
                            return parts[0]["text"]
            except Exception:
                continue
        return None
