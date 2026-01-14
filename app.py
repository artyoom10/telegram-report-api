import os
import re
import html
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Flask, request, jsonify, make_response
from weasyprint import HTML

app = Flask(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

def _cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS, GET"
    return resp

@app.get("/")
def health():
    return _cors(jsonify({"ok": True}))

@app.route("/send_report", methods=["OPTIONS"])
def send_report_options():
    return _cors(make_response("", 204))

def _safe_filename(s: str) -> str:
    s = re.sub(r"\s+", "_", s.strip().lower())
    s = re.sub(r"[^a-z0-9_\-]+", "", s)
    return s[:60] or "report"

def send_pdf(chat_id: str, pdf_bytes: bytes, filename: str, caption: str):
    files = {"document": (filename, pdf_bytes, "application/pdf")}
    data = {"chat_id": chat_id, "caption": caption}
    r = requests.post(f"{TG_API}/sendDocument", data=data, files=files, timeout=60)
    r.raise_for_status()

def build_report_html(title: str, department: str, kpis: dict, rows: list, generated_date: str) -> str:
    # escape
    title = html.escape(title)
    department = html.escape(department)

    def esc(v): return html.escape("" if v is None else str(v))

    # KPI defaults
    total = esc(kpis.get("total", "—"))
    open_cnt = esc(kpis.get("open", "—"))
    open_high7 = esc(kpis.get("open_high7", "—"))
    hosts = esc(kpis.get("hosts", "—"))
    hosts_open = esc(kpis.get("hosts_open", "—"))

    # table rows
    tr = []
    for r in rows[:50]:
      tr.append(f"""
        <tr>
          <td class="num">{esc(r.get("cvss",""))}</td>
          <td><span class="badge threat-{esc(r.get("threat_key","other"))}">{esc(r.get("threat",""))}</span></td>
          <td><span class="badge status-{esc(r.get("status_key","other"))}">{esc(r.get("status",""))}</span></td>
          <td>{esc(r.get("host",""))}</td>
          <td class="mono">{esc(r.get("port",""))}</td>
          <td>{esc(r.get("plugin",""))}</td>
          <td class="mono">{esc(r.get("detected",""))}</td>
        </tr>
      """)

    tbody = "\n".join(tr) if tr else """
      <tr><td colspan="7" class="muted">Нет открытых уязвимостей.</td></tr>
    """

    return f"""
    <html>
      <head>
        <meta charset="utf-8">
        <style>
          @page {{ size: A4; margin: 16mm; }}
          body {{
            font-family: DejaVu Sans, Arial, sans-serif;
            color: #111;
          }}
          .header {{
            border-bottom: 2px solid #111;
            padding-bottom: 10px;
            margin-bottom: 14px;
          }}
          h1 {{
            margin: 0;
            font-size: 18px;
            letter-spacing: .2px;
          }}
          .meta {{
            margin-top: 6px;
            font-size: 11px;
            color: #666;
          }}

          .kpi-grid {{
            width: 100%;
            border-collapse: separate;
            border-spacing: 10px;
            margin: 6px -10px 14px -10px;
          }}
          .kpi {{
            border: 1px solid #e5e5e5;
            border-radius: 12px;
            padding: 10px 12px;
            background: #fafafa;
            vertical-align: top;
          }}
          .kpi .t {{ font-size: 11px; color: #666; }}
          .kpi .v {{ font-size: 22px; font-weight: 800; margin-top: 2px; }}
          .kpi .h {{ font-size: 11px; color: #777; margin-top: 6px; }}

          table.data {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 8px;
          }}
          table.data thead th {{
            text-align: left;
            font-size: 11px;
            color: #444;
            border-bottom: 1px solid #ddd;
            padding: 8px 6px;
          }}
          table.data tbody td {{
            border-bottom: 1px solid #eee;
            padding: 8px 6px;
            font-size: 11px;
          }}
          table.data tbody tr:nth-child(2n) td {{ background: #fbfbfb; }}

          .num {{ text-align: right; width: 48px; }}
          .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace; }}

          .badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 999px;
            font-size: 10px;
            font-weight: 700;
            border: 1px solid rgba(0,0,0,.08);
          }}
          .threat-high {{ background: #ffe8e8; color: #9b111e; }}
          .threat-medium {{ background: #fff4db; color: #7a4b00; }}
          .threat-low {{ background: #e7f6ff; color: #004e7c; }}
          .threat-info {{ background: #f0f0f0; color: #444; }}
          .threat-other {{ background: #f0f0f0; color: #444; }}

          .status-open {{ background: #ffe8e8; color: #9b111e; }}
          .status-inprogress {{ background: #fff4db; color: #7a4b00; }}
          .status-resolved {{ background: #e9f8ef; color: #116a35; }}
          .status-other {{ background: #f0f0f0; color: #444; }}

          .muted {{ color: #777; font-size: 11px; }}
          .section-title {{ font-weight: 800; margin: 12px 0 6px 0; }}
        </style>
      </head>
      <body>
        <div class="header">
          <h1>{title}</h1>
          <div class="meta">Дата: {html.escape(generated_date)} • Отдел: {department}</div>
        </div>

        <table class="kpi-grid">
          <tr>
            <td class="kpi">
              <div class="t">Всего уязвимостей</div>
              <div class="v">{total}</div>
              <div class="h">Все статусы</div>
            </td>
            <td class="kpi">
              <div class="t">Открытые</div>
              <div class="v">{open_cnt}</div>
              <div class="h">Статус: Открыто</div>
            </td>
            <td class="kpi">
              <div class="t">Open с CVSS ≥ 7</div>
              <div class="v">{open_high7}</div>
              <div class="h">Высокий и выше</div>
            </td>
            <td class="kpi">
              <div class="t">Хосты</div>
              <div class="v">{hosts}</div>
              <div class="h">Хосты с open: {hosts_open}</div>
            </td>
          </tr>
        </table>

        <div class="section-title">Открытые уязвимости (до 50)</div>
        <table class="data">
          <thead>
            <tr>
              <th class="num">CVSS</th>
              <th>Критичность</th>
              <th>Статус</th>
              <th>Хост</th>
              <th>Порт</th>
              <th>Плагин</th>
              <th>Обнаружено</th>
            </tr>
          </thead>
          <tbody>
            {tbody}
          </tbody>
        </table>

        <div class="muted" style="margin-top:10px;">
          Сформировано автоматически.
        </div>
      </body>
    </html>
    """

@app.post("/send_report")
def send_report():
    payload = request.get_json(silent=True) or {}

    department = str(payload.get("department") or "unknown")
    kpis = payload.get("kpis") or {}
    rows = payload.get("open_rows") or []

    # дата в Helsinki
    today = datetime.now(ZoneInfo("Europe/Helsinki")).strftime("%Y-%m-%d")
    caption = f"Отчёт {today} по отделу {department}"
    title = caption  # пусть заголовок PDF совпадает с caption

    html_doc = build_report_html(
        title=title,
        department=department,
        kpis=kpis,
        rows=rows,
        generated_date=today
    )

    pdf_bytes = HTML(string=html_doc).write_pdf()
    filename = f"{_safe_filename(department)}_{today}.pdf"
    send_pdf(CHAT_ID, pdf_bytes, filename=filename, caption=caption)
    return _cors(jsonify({"ok": True}))
