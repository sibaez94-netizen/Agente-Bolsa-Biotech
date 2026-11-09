# -*- coding: utf-8 -*-
"""
Notificador Diario (Email HTML de fondo blanco + Bot de Telegram opcional).
Distingue claramente entre:
1. Estrategia Dinámica / Oportunidades en Soporte Histórico (seguimiento diario).
2. Estrategia a Largo Plazo (Núcleo MSCI World + DCA, que solo avisa si hay alerta gorda).
"""

import datetime
import html
import json
import os
import smtplib
import ssl
import urllib.parse
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

    def build_telegram_text(self, web_payload: Dict[str, Any]) -> str:
        today_str = datetime.datetime.now().strftime("%d/%m/%Y")
        briefing = web_payload.get("ai_briefing", "")
        sup_count = web_payload.get("stats", {}).get("support_zone_count", 0)
        header = f"🧬 *RADAR BOLSA BIOTECH, AGTECH & DEFENSA ({today_str})*\n"
        header += f"🎯 Activos en Soporte Histórico hoy: *{sup_count}*\n\n"
        body = briefing
        if self.dashboard_url:
            body += f"\n\n🌐 [Abrir Panel Web Interactivo]({self.dashboard_url})"
        return header + body

    def send_telegram_if_configured(self, web_payload: Dict[str, Any]) -> bool:
        if not self.telegram_token or not self.telegram_chat_id:
            return False
        text = self.build_telegram_text(web_payload)
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload = {
            "chat_id": self.telegram_chat_id,
            "text": text,
            "parse_mode": "Markdown",
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
        briefing = web_payload.get("ai_briefing", "")
        briefing_source = web_payload.get("briefing_source", "Motor Cuantitativo")

        support_assets = [a for a in assets if a.get("in_support_zone") and a["ticker"] != "EUNL.DE"]
        dynamic_assets = [a for a in assets if a.get("strategy_group") == "dynamic"]
        long_term_assets = [a for a in assets if a.get("strategy_group") == "long_term"]

        briefing_html = "<br><br>".join(html.escape(line) for line in briefing.split("\n\n") if line.strip())

        def render_asset_row(a: Dict[str, Any]) -> str:
            chg = a.get("change_1d_pct", 0.0)
            chg_color = "#15803d" if chg > 0 else ("#b91c1c" if chg < 0 else "#475569")
            chg_sign = f"+{chg:.2f}%" if chg > 0 else f"{chg:.2f}%"
            sup_str = f"{a['historical_support_low']:.0f} - {a['historical_support_high']:.0f} {a['currency']}"
            reason_first = html.escape((a.get("reasons") or [""])[0])
            vitals_html = ""
            if a.get("clinical_vitals"):
                v = a["clinical_vitals"]
                vitals_html = (
                    f"<div style='font-size:12px;color:#0369a1;margin-top:4px;'>"
                    f"💊 <b>Cash Runway:</b> {v.get('cash_runway_months')} meses · "
                    f"<b>Riesgo Dilución:</b> {html.escape(str(v.get('dilution_risk')))}</div>"
                )
            return f"""
            <div style="padding:12px 14px;border:1px solid #e2e8f0;border-radius:10px;margin-bottom:10px;background:#ffffff;">
              <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;">
                <div>
                  <span style="font-size:11px;font-weight:700;color:#475569;text-transform:uppercase;">{html.escape(a['category_label'])}</span>
                  <div style="font-size:15px;font-weight:700;color:#0f172a;margin-top:2px;">
                    <a href="{html.escape(a.get('yahoo_url','#'))}" style="color:#0284c7;text-decoration:none;">{html.escape(a['ticker'])} · {html.escape(a['name'])}</a>
                  </div>
                </div>
                <span style="background:#f1f5f9;color:#0f172a;padding:4px 9px;border-radius:6px;font-size:12px;font-weight:700;">
                  {html.escape(a['signal_badge'])} · Score {a['opportunity_score']}/100
                </span>
              </div>
              <div style="margin-top:8px;font-size:13px;color:#334155;">
                <b>Precio:</b> {a['current_price']:.2f} {html.escape(a['currency'])}
                (<span style="color:{chg_color};font-weight:700;">{chg_sign} hoy</span> | 2 Años: {a['change_2y_pct']:+.1f}%)
                · <b>Soporte 3Y:</b> {html.escape(sup_str)}
                {f" · <b>DCA:</b> {a['monthly_allocation_eur']:.0f} €/mes" if a.get('in_base_dca') else ""}
              </div>
              <div style="margin-top:5px;font-size:12px;color:#64748b;">{reason_first}</div>
              {vitals_html}
            </div>
            """

        sup_rows = "".join(render_asset_row(a) for a in support_assets) or (
            "<p style='font-size:13px;color:#64748b;'>Ningún satélite está hoy dentro de su banda de suelo histórico de 3 años. Mantener compras periódicas DCA normales.</p>"
        )
        dyn_rows = "".join(render_asset_row(a) for a in dynamic_assets)
        lt_rows = "".join(render_asset_row(a) for a in long_term_assets)

        news_rows = ""
        for n in news[:6]:
            news_rows += f"""
            <li style="margin-bottom:8px;font-size:13px;color:#334155;">
              <span style="font-weight:700;color:#0369a1;">[{html.escape(n.get('source','RSS'))}]</span>
              <a href="{html.escape(n.get('url','#'))}" style="color:#0f172a;font-weight:600;text-decoration:none;">{html.escape(n.get('title',''))}</a>
            </li>
            """

        btn_html = ""
        if self.dashboard_url:
            btn_html = f"""
            <div style="margin-top:16px;text-align:center;">
              <a href="{html.escape(self.dashboard_url)}" style="display:inline-block;background:#0284c7;color:#ffffff;font-weight:700;padding:10px 20px;border-radius:8px;text-decoration:none;font-size:14px;">
                Abrir Panel Web Interactivo y Tabla Excel
              </a>
            </div>
            """

        return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><title>Radar Bolsa Biotech & Geopolítica</title></head>
<body style="margin:0;padding:20px;background:#f8fafc;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#0f172a;">
  <div style="max-width:700px;margin:0 auto;background:#ffffff;border:1px solid #e2e8f0;border-radius:14px;padding:24px;">
    <div style="border-bottom:2px solid #f1f5f9;padding-bottom:16px;margin-bottom:18px;">
      <div style="font-size:12px;font-weight:700;color:#0284c7;text-transform:uppercase;letter-spacing:0.6px;">
        Agente de Inteligencia Financiera · Estrategia Core-Satellite (200 €/mes DCA)
      </div>
      <h1 style="margin:6px 0 4px;font-size:22px;color:#0f172a;">Parte Diario de Bolsa · {today_str}</h1>
      <div style="font-size:13px;color:#64748b;">
        Diagnóstico In Vitro (IVD/NGS) · AgTech (CRISPR NGT1 / RNAi) · Defensa OTAN · Biotech Fase Clínica
      </div>
      {btn_html}
    </div>

    <div style="background:#f0f9ff;border-left:4px solid #0284c7;padding:14px 16px;border-radius:8px;margin-bottom:22px;">
      <div style="font-size:12px;font-weight:700;color:#0369a1;text-transform:uppercase;margin-bottom:6px;">
        🧠 Resumen Ejecutivo Telegráfico ({html.escape(briefing_source)})
      </div>
      <div style="font-size:14px;line-height:1.55;color:#0f172a;">
        {briefing_html}
      </div>
    </div>

    <h2 style="font-size:16px;color:#0f172a;margin:20px 0 10px;border-bottom:1px solid #e2e8f0;padding-bottom:6px;">
      🎯 1. Oportunidades en Zona de Soporte Histórico (3 Años)
    </h2>
    {sup_rows}

    <h2 style="font-size:16px;color:#0f172a;margin:22px 0 10px;border-bottom:1px solid #e2e8f0;padding-bottom:6px;">
      🔬 2. Estrategia Dinámica · Seguimiento Diario (Biotech Clínica, Biopsia Líquida & Radar)
    </h2>
    {dyn_rows}

    <h2 style="font-size:16px;color:#0f172a;margin:22px 0 10px;border-bottom:1px solid #e2e8f0;padding-bottom:6px;">
      🛡️ 3. Estrategia Largo Plazo · Núcleo Intocable y Satélites Estructurales (DCA)
    </h2>
    {lt_rows}

    <h2 style="font-size:16px;color:#0f172a;margin:22px 0 10px;border-bottom:1px solid #e2e8f0;padding-bottom:6px;">
      📰 4. Radar de Noticias Sectoriales (FierceBiotech, AgFunderNews, PubMed RNAi & DefenseNews)
    </h2>
    <ul style="padding-left:18px;margin:0;">
      {news_rows}
    </ul>
  </div>
</body>
</html>"""

    def send_daily_report(self, web_payload: Dict[str, Any], docs_dir: str) -> bool:
        html_body = self.build_email_html(web_payload)
        os.makedirs(docs_dir, exist_ok=True)
        preview_path = os.path.join(docs_dir, "last_email_preview.html")
        with open(preview_path, "w", encoding="utf-8") as f:
            f.write(html_body)

        # Enviar a Telegram si está configurado
        tg_ok = self.send_telegram_if_configured(web_payload)

        # Enviar por Email SMTP si está configurado
        if not self.smtp_user or not self.smtp_password or not self.notify_email:
            print("[Email] Credenciales SMTP no configuradas; vista previa guardada en docs/last_email_preview.html.")
            return tg_ok

        today_str = datetime.datetime.now().strftime("%d/%m/%Y")
        sup_count = web_payload.get("stats", {}).get("support_zone_count", 0)
        subject = f"🧬 Radar Bolsa ({today_str}) · {sup_count} en Soporte Histórico | Biotech, AgTech & Defensa"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.smtp_user
        msg["To"] = self.notify_email
        msg.attach(MIMEText(self.build_telegram_text(web_payload), "plain", "utf-8"))
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
            print(f"[Email] Informe bursátil enviado correctamente a {self.notify_email}.")
            return True
        except Exception as e:
            print(f"[Email] Aviso al enviar correo SMTP: {e}")
            return tg_ok
