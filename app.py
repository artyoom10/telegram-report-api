import os
import html
import requests
from flask import Flask, request, jsonify, make_response
from weasyprint import HTML  # HTML -> PDF

app = Flask(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

def _cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    return resp

@app.get("/")
def health():
    return _cors(jsonify({"ok": True}))

@app.route("/send_report", methods=["OPTIONS"])
def send_report_options():
    return _cors(make_response("", 204))

def send_pdf(chat_id: str, pdf_bytes: bytes, filename="report.pdf", caption="Отчёт"):
    files = {"document": (filename, pdf_bytes, "application/pdf")}
    data = {"chat_id": chat_id, "caption": caption}
    r = requests.post(f"{TG_API}/sendDocument", data=data, files=files, timeout=60)
    r.raise_for_status()

@app.post("/send_report")
def send_report():
    payload = request.get_json(silent=True) or {}
    title = str(payload.get("title") or "Отчёт")
    text = str(payload.get("text") or "")

    # защита от HTML-инъекций в отчёте
    safe_title = html.escape(title)
    safe_text = html.escape(text)

    html_doc = f"""
    <html>
      <head>
        <meta charset="utf-8">
        <style>
          @page {{ size: A4; margin: 18mm; }}
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
            font-size: 20px;
            letter-spacing: .2px;
          }}
          .meta {{
            margin-top: 6px;
            font-size: 11px;
            color: #666;
          }}
          .box {{
            border: 1px solid #d9d9d9;
            border-radius: 12px;
            padding: 12px 14px;
            background: #fafafa;
          }}
          .mono {{
            white-space: pre-wrap;
            font-size: 12px;
            line-height: 1.35;
          }}
        </style>
      </head>
      <body>
        <div class="header">
          <h1>{safe_title}</h1>
          <div class="meta">PDF сформирован автоматически</div>
        </div>
        <div class="box mono">{safe_text}</div>
      </body>
    </html>
    """

    pdf_bytes = HTML(string=html_doc).write_pdf()
    send_pdf(CHAT_ID, pdf_bytes, filename="report.pdf", caption=title)

    return _cors(jsonify({"ok": True}))
