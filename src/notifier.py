# -*- coding: utf-8 -*-
"""
Notificador Diario Pedagógico y con Memoria Episódica (Email HTML de fondo blanco + Telegram).
Presenta el análisis diario de forma profunda, intuitiva y didáctica:
- Muestra qué ha cambiado respecto a las rondas previas almacenadas en SQLite (data/bolsa.db).
- Explica cada indicador (Soporte Histórico 3Y, RSI, Cash Runway, Dilución, DCA) en lenguaje claro.
- Traduce y contextualiza las noticias del sector (FierceBiotech, AgFunderNews, DefenseNews y PubMed).
"""

import datetime
import html
import json
import os
import smtplib
import ssl
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List


class BolsaNotifier:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.smtp_host = (os.environ.get("SMTP_HOST") or "smtp.gmail.com").strip()
        port_raw = (os.environ.get("SMTP_PORT") or "465").strip()
        self.smtp_port = int(port_raw) if port_raw.isdigit() else 465
        self.smtp_user = (os.environ.get("SMTP_USER") or "").strip()
        self.smtp_password = (os.environ.get("SMTP_PASSWORD") or "").strip()
        self.notify_email = (os.environ.get("NOTIFY_EMAIL") or self.smtp_user).strip()
        self.dashboard_url = (os.environ.get("DASHBOARD_URL") or "").strip()

        self.telegram_token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
        self.telegram_chat_id = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()

    def build_plain_text(self, web_payload: Dict[str, Any]) -> str:
        today_str = datetime.datetime.now().strftime("%d/%m/%Y")
        briefing = web_payload.get("ai_briefing", "")
        sup_count = web_payload.get("stats", {}).get("support_zone_count", 0)
        mem_days = web_payload.get("stats", {}).get("memory_days_count", 1)
        warns = "".join(f"⚠️ {w}\n" for w in (web_payload.get("data_warnings") or []))
        header = (
            f"🧬 INFORME DIARIO DE BOLSA CON MEMORIA ({today_str})\n"
            + warns
            + f"🧠 Sesiones acumuladas en Memoria: {mem_days} | 🎯 En Suelo Histórico hoy: {sup_count}\n\n"
        )
        body = briefing
        if self.dashboard_url:
            body += f"\n\n🌐 Panel Web Interactivo: {self.dashboard_url}"
        return header + body

    def send_telegram_if_configured(self, web_payload: Dict[str, Any]) -> bool:
        if not self.telegram_token or not self.telegram_chat_id:
            return False
        text = self.build_plain_text(web_payload)[:3900]
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload = {
            "chat_id": self.telegram_chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                return resp.status == 200
        except Exception as e:
            print(f"[Telegram] Aviso al enviar mensaje: {e}")
            return False

    def build_email_html(self, web_payload: Dict[str, Any]) -> str:
        today_str = datetime.datetime.now().strftime("%d/%m/%Y")
        stats = web_payload.get("stats", {})
        assets: List[Dict[str, Any]] = web_payload.get("assets", [])
        news: List[Dict[str, str]] = web_payload.get("news", [])
        sections: List[Dict[str, str]] = web_payload.get("briefing_sections") or []
        briefing_source = web_payload.get("briefing_source", "Mentor Pedagógico + Memoria SQLite")

        support_assets = [
            a for a in assets
            if a.get("in_support_zone") and a["ticker"] != "EUNL.DE" and not (a.get("clinical_vitals") and a["clinical_vitals"].get("trading_below_cash"))
        ]
        dynamic_assets = [a for a in assets if a.get("strategy_group") == "dynamic"]
        long_term_assets = [a for a in assets if a.get("strategy_group") == "long_term"]

        sections_html = ""
        for s in sections:
            body_formatted = "<br><br>".join(
                html.escape(p) for p in (s.get("body") or "").split("\n\n") if p.strip()
            ).replace("\n", "<br>")
            sections_html += f"""
            <div style="background:#f8fafc;border:1px solid #e2e8f0;border-left:4px solid #0284c7;padding:14px 16px;border-radius:10px;margin-bottom:12px;">
              <div style="font-size:14px;font-weight:800;color:#0f172a;margin-bottom:6px;">
                {html.escape(s.get('icon',''))} {html.escape(s.get('title',''))}
              </div>
              <div style="font-size:13.5px;line-height:1.6;color:#334155;">
                {body_formatted}
              </div>
            </div>
            """

        def render_asset_row(a: Dict[str, Any]) -> str:
            chg = a.get("change_1d_pct", 0.0)
            chg_color = "#15803d" if chg > 0 else ("#b91c1c" if chg < 0 else "#475569")
            chg_sign = f"+{chg:.2f}%" if chg > 0 else f"{chg:.2f}%"
            sup_str = f"{a['historical_support_low']:.1f} - {a['historical_support_high']:.1f} {a['currency']}"
            mem_note = html.escape(a.get("memory_note") or "")
            sup_expl = html.escape(a.get("support_explanation") or "")
            rsi_expl = html.escape(a.get("rsi_explanation") or "")
            thesis = html.escape(a.get("thesis") or "")
            sell_rule = html.escape(a.get("sell_rule") or "")

            vitals_html = ""
            v = a.get("clinical_vitals") or {}
            if v.get("available"):
                bad = v.get("trading_below_cash") or (
                    v.get("cash_runway_months") is not None and v["cash_runway_months"] < 15 and not v.get("cash_flow_positive")
                )
                bg_v = "#fef2f2" if bad else "#f0fdf4"
                col_v = "#991b1b" if bad else "#166534"
                if v.get("cash_flow_positive"):
                    runway_txt = "flujo de caja operativo positivo (no quema caja)"
                elif v.get("cash_runway_months") is not None:
                    runway_txt = f"~{v['cash_runway_months']} meses (quema ~${v.get('annual_burn_musd')}M/año) · riesgo de dilución {html.escape(str(v.get('dilution_risk')))}"
                else:
                    runway_txt = "sin dato de quema de caja"
                cap_txt = f"${v['market_cap_musd']}M" if v.get("market_cap_musd") is not None else "no disponible"
                vitals_html = f"""
                <div style="background:{bg_v};color:{col_v};padding:8px 11px;border-radius:8px;font-size:12px;margin-top:8px;">
                  <b>🔬 Constantes vitales (SEC EDGAR, balance a {html.escape(str(v.get('balance_date')))}):</b><br>
                  • <b>Cash runway:</b> {runway_txt}<br>
                  • <b>Caja e inversiones vs valor en bolsa:</b> ${v.get('total_cash_musd')}M frente a {cap_txt}{' ⚠️ <b>cotiza bajo caja</b>' if v.get('trading_below_cash') else ''}<br>
                  • <b>Directivos:</b> {html.escape(str(v.get('insider_activity', '')))}
                </div>
                """
            elif v:
                vitals_html = f"""
                <div style="background:#f8fafc;color:#475569;padding:8px 11px;border-radius:8px;font-size:12px;margin-top:8px;">
                  🔬 Constantes vitales: {html.escape(str(v.get('reason', 'sin datos')))}
                </div>
                """

            return f"""
            <div style="padding:14px 16px;border:1px solid #cbd5e1;border-radius:12px;margin-bottom:12px;background:#ffffff;">
              <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;">
                <div>
                  <span style="font-size:11px;font-weight:700;color:#475569;text-transform:uppercase;">{html.escape(a['category_label'])} · {html.escape(a.get('exchange',''))}</span>
                  <div style="font-size:16px;font-weight:800;color:#0f172a;margin-top:2px;">
                    <a href="{html.escape(a.get('yahoo_url','#'))}" style="color:#0284c7;text-decoration:none;">{html.escape(a['ticker'])} · {html.escape(a['name'])}</a>
                  </div>
                </div>
                <span style="background:#e0f2fe;color:#0369a1;padding:4px 10px;border-radius:999px;font-size:11.5px;font-weight:800;">
                  {html.escape(a['signal_badge'])} · Score {a['opportunity_score']}/100
                </span>
              </div>

              <div style="margin-top:8px;font-size:13.5px;color:#0f172a;">
                <b>Precio Hoy:</b> {a['current_price']:.2f} {html.escape(a['currency'])}
                (<span style="color:{chg_color};font-weight:800;">{chg_sign} hoy</span> | Evolución 2 Años: <b>{a['change_2y_pct']:+.1f}%</b>)
                · <b>Suelo Histórico 3Y:</b> {html.escape(sup_str)}
                {f" · <b>Tu Cuota DCA:</b> {a['monthly_allocation_eur']:.0f} €/mes" if a.get('in_base_dca') else ""}
              </div>

              <div style="margin-top:8px;background:#f8fafc;padding:8px 11px;border-radius:8px;font-size:12.5px;color:#334155;">
                <div>{mem_note}</div>
                <div style="margin-top:4px;">📍 <b>Lectura del Precio:</b> {sup_expl}</div>
                <div style="margin-top:4px;">🌡️ <b>Termómetro Técnico:</b> {rsi_expl}</div>
              </div>

              {vitals_html}

              <div style="margin-top:8px;font-size:12px;color:#475569;border-top:1px solid #f1f5f9;padding-top:6px;">
                <b>Por qué está en tu radar:</b> {thesis}<br>
                <span style="color:#0369a1;"><b>Qué hacer según tu estrategia:</b> {sell_rule}</span>
              </div>
            </div>
            """

        warnings_html = "".join(
            f'<div style="background:#fffbeb;border:1px solid #fcd34d;color:#92400e;padding:10px 14px;border-radius:10px;margin-bottom:14px;font-size:13px;">⚠️ {html.escape(w)}</div>'
            for w in (web_payload.get("data_warnings") or [])
        )

        sup_rows = "".join(render_asset_row(a) for a in support_assets) or (
            "<p style='font-size:13px;color:#64748b;'>Hoy ninguna de tus empresas sanas está en su banda de suelo extremo de 3 años. Mantén tu aportación periódica DCA sin cambios.</p>"
        )
        dyn_rows = "".join(render_asset_row(a) for a in dynamic_assets)
        lt_rows = "".join(render_asset_row(a) for a in long_term_assets)

        news_rows = "" if news else "<p style='font-size:13px;color:#64748b;'>Hoy no se ha podido leer ninguna fuente de noticias.</p>"
        for n in news[:6]:
            badge_n = "🆕 NUEVA HOY" if n.get("is_new_today") else f"📌 Vista ({n.get('first_seen_date','')})"
            news_rows += f"""
            <div style="padding:10px 12px;border:1px solid #e2e8f0;border-radius:8px;margin-bottom:8px;background:#ffffff;">
              <div style="font-size:11px;font-weight:800;color:#0284c7;">{html.escape(badge_n)} · {html.escape(n.get('source','RSS'))} ({html.escape(n.get('category',''))})</div>
              <div style="font-size:14px;font-weight:700;margin-top:2px;">
                <a href="{html.escape(n.get('url','#'))}" style="color:#0f172a;text-decoration:none;">{html.escape(n.get('title',''))} ↗</a>
              </div>
              <div style="font-size:12.5px;color:#334155;margin-top:4px;">
                {html.escape(n.get('explanation_es',''))}
              </div>
            </div>
            """

        btn_html = ""
        if self.dashboard_url:
            btn_html = f"""
            <div style="margin-top:16px;text-align:center;">
              <a href="{html.escape(self.dashboard_url)}" style="display:inline-block;background:#0284c7;color:#ffffff;font-weight:700;padding:10px 20px;border-radius:8px;text-decoration:none;font-size:14px;">
                Abrir Panel Web Interactivo, Memoria y Tabla Excel
              </a>
            </div>
            """

        return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><title>Mentor Diario de Bolsa Biotech & Geopolítica</title></head>
<body style="margin:0;padding:20px;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#0f172a;">
  <div style="max-width:760px;margin:0 auto;background:#ffffff;border:1px solid #cbd5e1;border-radius:16px;padding:26px;">
    <div style="border-bottom:2px solid #e2e8f0;padding-bottom:16px;margin-bottom:20px;">
      <div style="font-size:12px;font-weight:800;color:#0284c7;text-transform:uppercase;letter-spacing:0.6px;">
        Mentor Bursátil con Memoria Histórica · Estrategia Core-Satellite (200 €/mes DCA)
      </div>
      <h1 style="margin:6px 0 4px;font-size:23px;color:#0f172a;">Informe Diario Explicado · {today_str}</h1>
      <div style="font-size:13px;color:#64748b;">
        🧠 <b>{stats.get('memory_days_count', 1)} sesiones</b> guardadas en Memoria (`data/bolsa.db`) · Motor: {html.escape(briefing_source)}
      </div>
      {btn_html}
    </div>

    {warnings_html}
    <h2 style="font-size:17px;color:#0f172a;margin:0 0 12px;">
      🎓 Análisis Guiado de Hoy (Paso a Paso y Comparado con Sesiones Anteriores)
    </h2>
    {sections_html}

    <h2 style="font-size:17px;color:#0f172a;margin:24px 0 10px;border-bottom:2px solid #e2e8f0;padding-bottom:6px;">
      🎯 1. Empresas Sanas Hoy en Zona de "Rebajas Históricas" (Suelo de 3 Años)
    </h2>
    {sup_rows}

    <h2 style="font-size:17px;color:#0f172a;margin:24px 0 10px;border-bottom:2px solid #e2e8f0;padding-bottom:6px;">
      🔬 2. Estrategia Dinámica · Seguimiento Diario (Biotech Clínica, Biopsia Líquida & Radar)
    </h2>
    {dyn_rows}

    <h2 style="font-size:17px;color:#0f172a;margin:24px 0 10px;border-bottom:2px solid #e2e8f0;padding-bottom:6px;">
      🛡️ 3. Estrategia Largo Plazo · Núcleo Intocable y Gigantes Estructurales (DCA)
    </h2>
    {lt_rows}

    <h2 style="font-size:17px;color:#0f172a;margin:24px 0 10px;border-bottom:2px solid #e2e8f0;padding-bottom:6px;">
      📰 4. Noticias del Sector Traducidas y Explicadas (FierceBiotech, AgFunder, PubMed RNAi & Defensa)
    </h2>
    {news_rows}
  </div>
</body>
</html>"""

    def send_daily_report(self, web_payload: Dict[str, Any], docs_dir: str) -> bool:
        html_body = self.build_email_html(web_payload)
        os.makedirs(docs_dir, exist_ok=True)
        preview_path = os.path.join(docs_dir, "last_email_preview.html")
        with open(preview_path, "w", encoding="utf-8") as f:
            f.write(html_body)

        if (os.environ.get("NO_ENVIAR_EMAIL") or "").strip() in ("1", "true", "si", "sí"):
            print("[Email] Ejecución local de prueba (NO_ENVIAR_EMAIL): no se envía correo ni Telegram.")
            return False

        tg_ok = self.send_telegram_if_configured(web_payload)

        if not self.smtp_user or not self.smtp_password or not self.notify_email:
            print("[Email] Credenciales SMTP no configuradas; vista previa guardada en docs/last_email_preview.html.")
            return tg_ok

        today_str = datetime.datetime.now().strftime("%d/%m/%Y")
        sup_count = web_payload.get("stats", {}).get("support_zone_count", 0)
        if not web_payload.get("assets"):
            subject = f"⚠️ Mentor Bolsa ({today_str}) · Sin datos de mercado hoy"
        else:
            subject = f"🧬 Mentor Bolsa ({today_str}) · {sup_count} en Suelo Histórico | Informe Explicado + Memoria"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.smtp_user
        msg["To"] = self.notify_email
        msg.attach(MIMEText(self.build_plain_text(web_payload), "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        try:
            context = ssl.create_default_context()
            if self.smtp_port == 465:
                with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, context=context, timeout=20) as server:
                    server.login(self.smtp_user, self.smtp_password)
                    server.sendmail(self.smtp_user, [self.notify_email], msg.as_string())
            else:
                with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=20) as server:
                    server.starttls(context=context)
                    server.login(self.smtp_user, self.smtp_password)
                    server.sendmail(self.smtp_user, [self.notify_email], msg.as_string())
            print(f"[Email] Informe bursátil explicado enviado correctamente a {self.notify_email}.")
            return True
        except Exception as e:
            print(f"[Email] Aviso al enviar correo SMTP: {e}")
            return tg_ok
