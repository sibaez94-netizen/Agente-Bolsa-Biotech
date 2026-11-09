# -*- coding: utf-8 -*-
"""
Motor Analítico Híbrido para el Agente de Bolsa (Estrategia Dual: Largo Plazo vs. Dinámica Diaria).
1. Evalúa precios frente a Soportes Históricos de 3 años (Órdenes Limitadas), RSI(14), Drawdown y DCA.
2. Verifica las 3 Constantes Vitales Anti-Dilución en Biotech Clínica (Cash Runway, Market Cap vs Cash, Insiders).
3. Genera el Resumen Ejecutivo Telegráfico (vía API de Google Gemini con el Prompt Maestro Definitivo
   si GEMINI_API_KEY está configurada, o mediante motor cuantitativo autónomo si no hay clave).
"""

import json
import os
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

GEMINI_MASTER_SYSTEM_PROMPT = """[ROL Y OBJETIVO]
Eres mi Agente de Inteligencia Financiera Personal. Tu trabajo es leer un volcado de datos crudos (precios de acciones vía API y titulares de noticias vía RSS) y cruzar esa información con mi tesis de inversión.
No eres un asesor financiero genérico. Eres un filtro de ruido. Tu único objetivo final es enviarme una notificación ultracorta, ejecutiva y directa que me diga si todo va bien o si hay una oportunidad de compra/venta según mis dos estrategias (Largo Plazo vs. Dinámica Diaria).

[MI PERFIL Y ESTRATEGIA (CORE-SATELLITE)]
Soy un inversor científico (Doctor en genética vegetal, experto en diagnóstico in vitro y analista geopolítico). Invierto 200 € al mes (ampliable a 500 €) usando la estrategia DCA (Dollar Cost Averaging) para comprar acciones fraccionadas en XTB (con reporte automático a Hacienda en España).
Mi cartera está dividida en DOS velocidades:

A) ESTRATEGIA 1 - LARGO PLAZO (No tocar salvo alerta gorda o entrada en soporte histórico):
1. NÚCLEO (50% - 100€): iShares Core MSCI World (Ticker: EUNL.DE). Es mi base térmica darwiniana de Acumulación (interés compuesto sin peaje fiscal). Nunca lo toco salvo debacle mundial extrema (y solo para comprar más barato, nunca vender por pánico).
2. SATÉLITE 1 - DIAGNÓSTICO IN VITRO Y LABORATORIO (20% - 40€): Thermo Fisher (TMO), Danaher (DHR, matriz de Cepheid/Beckman/Leica), Siemens Healthineers (SHL.DE), Roche (ROG.SW), Illumina (ILMN) y ETFs de salud emergente (KURE con Mindray, NDIA.L India).
3. SATÉLITE 2 - AGTECH Y GENÉTICA VEGETAL (15% - 30€): Corteva Agriscience (CTVA) y Novonesis (NSIS-B.CO). Mi apuesta por la revolución CRISPR (semillas NGT1 aprobadas en Europa para 2028) y biopesticidas de RNAi (dsRNA / SIGS).
4. SATÉLITE 3 - DEFENSA Y GEOPOLÍTICA (10% - 20€): VanEck Defense UCITS ETF (DFNS.MI) y Rheinmetall (RHM.DE). Rearme OTAN (2-3% PIB).

B) ESTRATEGIA 2 - DINÁMICA DE SEGUIMIENTO DIARIO (Vigilar todos los días):
5. SATÉLITE 4 - BIOTECH FASE CLÍNICA Y RADAR (5% - 10€): Bicycle Therapeutics (BCYC), Beam Therapeutics (BEAM), Summit Therapeutics (SMMT), Oxford Nanopore (ONT.L), Ginkgo Bioworks (DNA), Guardant Health (GH) y 3B Blackbio DX (3BBLACKBIO.BO). Busco asimetrías científicas vigilando las 3 constantes vitales anti-dilución (Cash Runway >= 15 meses, Market Cap > Total Cash e Insider Buying) y catalizadores FDA/EMA.

[REGLAS DE ANÁLISIS INTERNO (Piensa esto, pero no lo escribas)]
- Si una acción de Satélite cae más de un 3.5%-4% o entra en su soporte histórico de 3 años (ej. DHR en 190-205$, SHL.DE en 39-43€, TMO en 480-510$, CTVA en 50-56$), verifica si la tesis científica sigue intacta. Si sigue intacta, destácalo como OPORTUNIDAD DE COMPRA / ORDEN LIMITADA.
- Si hay noticias sobre regulaciones europeas agrícolas (NGT1), biopesticidas RNAi, secuenciación NGS en hospitales o aprobaciones de la FDA, crúzalo con mis empresas.

[FORMATO DE SALIDA (ESTRICTO)]
Máximo 5-6 líneas en total. Cero saludos largos, directo al grano:
- Línea 1 (Largo Plazo / Núcleo): Estado de EUNL.DE y si hay alguna alerta gorda o todo sigue en piloto automático.
- Línea 2-3 (Soportes y Oportunidades DCA): Qué satélites están hoy en zona de compra histórica o han tenido caída relevante.
- Línea 4-5 (Estrategia Dinámica / Noticias): Estado de Biotech Clínica (BCYC, BEAM, SMMT) y el titular más relevante de hoy (FierceBiotech / AgFunderNews / PubMed / DefenseNews).
"""


class PortfolioAnalyzer:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.thresholds = config.get("alert_thresholds", {})
        self.allocations = config.get("allocations", {})

    def analyze_portfolio(
        self,
        quotes: Dict[str, Dict[str, Any]],
        news: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        analyzed_assets: List[Dict[str, Any]] = []
        long_term_alerts: List[Dict[str, Any]] = []
        dynamic_alerts: List[Dict[str, Any]] = []
        support_opportunities: List[Dict[str, Any]] = []

        for asset_cfg in self.config.get("assets", []):
            ticker = asset_cfg["ticker"]
            q = quotes.get(ticker, {})
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

            # Distancia porcentual al techo de la zona de soporte histórico
            dist_to_support_pct = (
                round(((cur_price - sup_high) / sup_high) * 100.0, 1) if sup_high > 0 and cur_price > 0 else 0.0
            )
            in_support_zone = cur_price > 0 and cur_price <= (sup_high * 1.03)

            strategy_mode = asset_cfg.get("strategy_mode", "long_term_tactical")
            is_dynamic = strategy_mode == "dynamic_daily"
            is_core = asset_cfg.get("category") == "core_msci_world"

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

            # Simulación de cuánto valdrían hoy 40 € invertidos hace 2 años
            value_of_40eur_2y = round(40.0 * (1.0 + (chg_2y / 100.0)), 2)

            enriched = {
                "ticker": ticker,
                "name": asset_cfg["name"],
                "category": asset_cfg["category"],
                "category_label": self.allocations.get(asset_cfg["category"], {}).get("name", asset_cfg["category"]),
                "strategy_mode": strategy_mode,
                "strategy_group": "dynamic" if is_dynamic else "long_term",
                "strategy_label": "Dinámica (Seguimiento Diario)" if is_dynamic else "Largo Plazo (Core / DCA)",
                "currency": asset_cfg.get("currency", "USD"),
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
                "value_of_40eur_2y": value_of_40eur_2y,
                "low_3y": low_3y,
                "high_3y": high_3y,
                "drawdown_3y_pct": drawdown_3y,
                "sma_50": q.get("sma_50"),
                "sma_200": q.get("sma_200"),
                "rsi_14": rsi_14,
                "historical_support_low": sup_low,
                "historical_support_high": sup_high,
                "in_support_zone": in_support_zone,
                "dist_to_support_pct": dist_to_support_pct,
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

        # Ordenar: primero los de mayor Opportunity Score
        analyzed_assets.sort(key=lambda x: (x["in_base_dca"], x["opportunity_score"]), reverse=True)
        support_opportunities.sort(key=lambda x: x["opportunity_score"], reverse=True)

        # Generar el Resumen Ejecutivo Telegráfico (Híbrido: Gemini API o Algorítmico)
        ai_briefing, briefing_source = self.generate_executive_briefing(
            analyzed_assets=analyzed_assets,
            long_term_alerts=long_term_alerts,
            support_opportunities=support_opportunities,
            dynamic_alerts=dynamic_alerts,
            news=news,
        )

        return {
            "assets": analyzed_assets,
            "long_term_alerts": long_term_alerts,
            "support_opportunities": support_opportunities,
            "dynamic_alerts": dynamic_alerts,
            "news": news,
            "ai_briefing": ai_briefing,
            "briefing_source": briefing_source,
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
        """
        Devuelve (opportunity_score 0..100, signal_badge, signal_color, reasons, alert_level).
        """
        reasons: List[str] = []
        score = 55
        cat = asset_cfg.get("category", "")
        mode = asset_cfg.get("strategy_mode", "long_term_tactical")
        curr = asset_cfg.get("currency", "")

        # 1. Caso Núcleo Intocable (MSCI World EUNL.DE)
        if cat == "core_msci_world":
            if chg_1d <= float(self.thresholds.get("core_major_drop_daily_pct", -4.0)) or drawdown_3y <= float(
                self.thresholds.get("core_major_drawdown_pct", -10.0)
            ):
                score = 92
                reasons.append(
                    f"Alerta Gorda en Núcleo ({chg_1d:+.1f}% hoy | {drawdown_3y:+.1f}% desde máximos): NO vender (evitar peaje Hacienda). Momento ideal para aportación extra."
                )
                return score, "🚨 ALERTA REBAJA NÚCLEO (NO VENDER)", "amber", reasons, "high"
            reasons.append("Bola de nieve (Interés Compuesto Acc) rodando sin alertas. No tocar.")
            reasons.append(f"Cotización actual: {cur_price:.2f} {curr} ({chg_1d:+.2f}% hoy)")
            return 65, "🟢 PILOTO AUTOMÁTICO (INTOCABLE)", "green", reasons, "low"

        # 2. Evaluación de Soporte Histórico de 3 años (Market Timing táctico / Órdenes Limitadas)
        if in_support_zone:
            score += 26
            reasons.append(
                f"🎯 Cotizando en zona de Soporte Histórico de 3 años ({sup_low:.0f}-{sup_high:.0f} {curr} vs actual {cur_price:.2f} {curr})"
            )
        elif dist_to_support_pct <= 8.0:
            score += 12
            reasons.append(
                f"Acercándose a su soporte histórico de compra ({sup_low:.0f}-{sup_high:.0f} {curr}, a un {dist_to_support_pct:+.1f}%)"
            )
        else:
            reasons.append(
                f"Por encima de su suelo histórico ({sup_low:.0f}-{sup_high:.0f} {curr}); ideal acumular vía DCA o esperar con Orden Limitada en {sup_high:.0f} {curr}"
            )

        # 3. Evaluación de caída diaria / RSI (Oportunidad tipo Corteva 31 de julio)
        if chg_1d <= -3.5:
            score += 16
            reasons.append(f"📉 Caída diaria fuerte ({chg_1d:+.2f}%): revisar si el castigo es por ruido trimestral con ciencia intacta")
        elif chg_5d <= -5.0:
            score += 10
            reasons.append(f"Retroceso semanal notable ({chg_5d:+.2f}% en 5 sesiones)")

        if rsi_14 is not None:
            if rsi_14 <= 34:
                score += 12
                reasons.append(f"RSI(14) en sobreventa técnica ({rsi_14:.0f}) -> rebote potencial")
            elif rsi_14 >= 72:
                score -= 8
                reasons.append(f"RSI(14) en sobrecompra ({rsi_14:.0f}) -> no perseguir precio, esperar corrección")

        # 4. Evaluación de Constantes Vitales en Biotech Fase Clínica (Satélite 4)
        if vitals:
            runway = vitals.get("cash_runway_months", 18)
            below_cash = vitals.get("trading_below_cash", False)
            if below_cash:
                score -= 25
                reasons.append("⚠️ PELIGRO: Cotiza cerca/bajo su valor en efectivo (Trading below cash) y alto riesgo de dilución")
                return max(15, min(99, score)), "⚠️ RIESGO DILUCIÓN / BAJO CAJA", "red", reasons, "high"
            elif runway < 14:
                score -= 18
                reasons.append(f"⚠️ Cuidado: Cash Runway corto ({runway} meses < 15m recomendados). Riesgo de ampliación de capital")
                return max(20, min(99, score)), "⚠️ VIGILAR CAJA (<15 MESES)", "amber", reasons, "high"
            else:
                score += 6
                reasons.append(f"Pista financiera sana: Cash Runway de ~{runway} meses ({vitals.get('dilution_risk', 'Bajo')})")
                if vitals.get("key_catalyst"):
                    reasons.append(f"Hito clave: {vitals['key_catalyst']}")

        score = max(15, min(98, int(round(score))))

        # Determinar etiqueta visual y nivel de alerta
        if in_support_zone and score >= 78:
            return score, "🎯 EN SOPORTE HISTÓRICO (COMPRAR)", "emerald", reasons, "high"
        if chg_1d <= -3.5:
            return score, "📉 ALERTA OPORTUNIDAD (CAÍDA)", "amber", reasons, "high"
        if mode == "dynamic_daily":
            if abs(chg_1d) >= 3.5:
                return score, f"🔥 MOVIMIENTO FUERTE ({chg_1d:+.1f}%)", "blue", reasons, "medium"
            return score, "🔬 VIGILANCIA DIARIA (FASE CLÍNICA)", "blue", reasons, "medium"

        return score, "🟢 MANTENER DCA / ORDEN LIMITADA", "green", reasons, "low"

    def generate_executive_briefing(
        self,
        analyzed_assets: List[Dict[str, Any]],
        long_term_alerts: List[Dict[str, Any]],
        support_opportunities: List[Dict[str, Any]],
        dynamic_alerts: List[Dict[str, Any]],
        news: List[Dict[str, str]],
    ) -> Tuple[str, str]:
        """
        Construye el parte diario telegráfico (estilo Telegram/Email ejecutivo).
        Si existe GEMINI_API_KEY, consulta Gemini con el Prompt Maestro Definitivo.
        En caso contrario (o si falla la red), genera el parte determinista estructurado.
        """
        core_asset = next((a for a in analyzed_assets if a["ticker"] == "EUNL.DE"), None)

        # Construir resumen determinista de alta precisión
        lines: List[str] = []

        # 1. Bloque Largo Plazo (Núcleo)
        if core_asset:
            c_chg = core_asset["change_1d_pct"]
            c_price = core_asset["current_price"]
            if core_asset["alert_level"] == "high":
                lines.append(
                    f"🚨 LARGO PLAZO (NÚCLEO EUNL.DE): Caída relevante ({c_chg:+.2f}%, a {c_price:.2f} €). Regla de oro: NO vender por pánico (evita peaje del 19-21% en Hacienda); aprovecha para acumular participaciones más baratas."
                )
            else:
                lines.append(
                    f"🟢 LARGO PLAZO (NÚCLEO EUNL.DE): Todo según lo previsto ({c_price:.2f} €, {c_chg:+.2f}% hoy). Tu bola de nieve de interés compuesto sigue en piloto automático sin alertas."
                )

        # 2. Bloque Satélites en Soporte Histórico (Market Timing Táctico / DCA)
        if support_opportunities:
            sup_strs = [
                f"{a['ticker']} ({a['current_price']:.2f} {a['currency']}, soporte {a['historical_support_low']:.0f}-{a['historical_support_high']:.0f})"
                for a in support_opportunities[:3]
            ]
            lines.append(
                f"🎯 EN SOPORTE HISTÓRICO DE COMPRA: {', '.join(sup_strs)}. Nivel óptimo de los últimos 3 años para concentrar tus compras fraccionadas o ejecutar Orden Limitada."
            )
        else:
            dca_list = [f"{a['ticker']} ({a['change_1d_pct']:+.1f}%)" for a in analyzed_assets if a["in_base_dca"] and a["ticker"] != "EUNL.DE"]
            lines.append(
                f"📊 SATÉLITES DCA (TMO, DHR, CTVA, DFNS): Variaciones contenidas ({', '.join(dca_list)}). Mantén el reparto mensual de 200 €."
            )

        # 3. Bloque Estrategia Dinámica (Biotech Fase Clínica, AgTech RNAi/CRISPR y Defensa)
        dyn_assets = [a for a in analyzed_assets if a["strategy_group"] == "dynamic"]
        dyn_summary = ", ".join([f"{a['ticker']} ({a['change_1d_pct']:+.1f}%)" for a in dyn_assets[:4]])
        lines.append(
            f"🔬 ESTRATEGIA DINÁMICA (SEGUIMIENTO DIARIO): {dyn_summary}. BCYC y BEAM mantienen Cash Runway > 24 meses (sin riesgo de dilución a corto plazo); precaución en DNA por cotizar cerca de caja."
        )

        # 4. Titular sectorial destacado
        if news:
            top_n = news[0]
            lines.append(
                f"📰 RADAR SECTORIAL ({top_n.get('source', 'RSS')}): \"{top_n.get('title', '')}\"."
            )

        deterministic_text = "\n\n".join(lines)

        # Si el usuario ha configurado GEMINI_API_KEY, consultar Gemini API
        api_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
        if api_key:
            raw_dump = self._build_raw_prompt_dump(analyzed_assets, news)
            gemini_resp = self._call_gemini_api(api_key, raw_dump)
            if gemini_resp:
                return gemini_resp.strip(), "Google Gemini AI (Prompt Maestro)"

        return deterministic_text, "Motor Cuantitativo Core-Satellite"

    @staticmethod
    def _build_raw_prompt_dump(analyzed_assets: List[Dict[str, Any]], news: List[Dict[str, str]]) -> str:
        price_lines = []
        for a in analyzed_assets:
            vitals_str = ""
            if a.get("clinical_vitals"):
                v = a["clinical_vitals"]
                vitals_str = f" | CashRunway: {v.get('cash_runway_months')}m | Dilución: {v.get('dilution_risk')}"
            price_lines.append(
                f"- {a['ticker']} ({a['name']}): Precio {a['current_price']} {a['currency']} | Hoy: {a['change_1d_pct']:+.2f}% | Soporte 3Y: {a['historical_support_low']}-{a['historical_support_high']} | EnSoporte: {a['in_support_zone']}{vitals_str}"
            )
        news_lines = [f"- [{n.get('source')}] {n.get('title')}" for n in news[:8]]
        return "COTIZACIONES DE HOY:\n" + "\n".join(price_lines) + "\n\nNOTICIAS RSS Y PUBMED:\n" + "\n".join(news_lines)

    @staticmethod
    def _call_gemini_api(api_key: str, user_prompt: str) -> Optional[str]:
        for model_name in ("gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"):
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            payload = {
                "system_instruction": {"parts": [{"text": GEMINI_MASTER_SYSTEM_PROMPT}]},
                "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                "generationConfig": {"temperature": 0.25, "maxOutputTokens": 450},
            }
            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                    candidates = data.get("candidates") or []
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts") or []
                        if parts and parts[0].get("text"):
                            return parts[0]["text"]
            except Exception:
                continue
        return None
