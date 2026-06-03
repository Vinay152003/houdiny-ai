"""
Houdiny AI — Web Dashboard (thin Flask layer)
All business logic goes through mcp_agent → MCP server → tools.
Flask only handles: routing, rendering templates, webhook entry point.
"""

import os
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
import time
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from twilio.twiml.messaging_response import MessagingResponse
from database import db, Lead, Message
from dotenv import load_dotenv
import mcp_agent

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///houdiny.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)


def migrate_db():
    import sqlite3
    db_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instance", "houdiny.db")
    if not os.path.exists(db_file):
        return
    conn = sqlite3.connect(db_file)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(leads)").fetchall()]
    if "email_status" not in cols:
        conn.execute("ALTER TABLE leads ADD COLUMN email_status TEXT DEFAULT 'Not Sent'")
    if "whatsapp_status" not in cols:
        conn.execute("ALTER TABLE leads ADD COLUMN whatsapp_status TEXT DEFAULT 'Not Sent'")
    conn.commit()
    conn.close()


with app.app_context():
    migrate_db()
    db.create_all()

# Forces Claude to reply with one clean short sentence — no markdown, no tables
BRIEF = "Complete the task using tools. Reply with ONE short sentence (under 12 words). No markdown, no tables, no emoji."


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    leads = Lead.query.order_by(Lead.created_at.desc()).all()
    stats = {
        "total":         Lead.query.count(),
        "emails_sent":   Message.query.filter_by(channel="email",    direction="sent").count(),
        "whatsapp_sent": Message.query.filter_by(channel="whatsapp", direction="sent").count(),
        "replies":       Message.query.filter_by(direction="received").count(),
        "booked":        Lead.query.filter_by(status="Booked").count(),
    }
    return render_template("index.html", leads=leads, stats=stats)


# ── Add Lead ──────────────────────────────────────────────────────────────────

@app.route("/leads/add", methods=["GET", "POST"])
def add_lead():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        # Call MCP tool directly — no Claude needed for simple create
        mcp_agent.call_mcp_tool("create_lead", {
            "name":     name,
            "company":  request.form.get("company", ""),
            "role":     request.form.get("role", ""),
            "email":    request.form.get("email", ""),
            "whatsapp": request.form.get("whatsapp", ""),
            "industry": request.form.get("industry", ""),
            "notes":    request.form.get("notes", ""),
        })
        flash(f"Lead {name} added.", "success")
        return redirect(url_for("index"))
    return render_template("add_lead.html")


# ── Lead Detail ───────────────────────────────────────────────────────────────

@app.route("/leads/<int:lead_id>")
def lead_detail(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    messages = Message.query.filter_by(lead_id=lead_id).order_by(Message.timestamp).all()
    return render_template("lead_detail.html", lead=lead, messages=messages)


# ── Send Email ────────────────────────────────────────────────────────────────

@app.route("/leads/<int:lead_id>/send-email", methods=["POST"])
def send_email_to_lead(lead_id):
    import threading
    lead = Lead.query.get_or_404(lead_id)
    threading.Thread(
        target=mcp_agent.run,
        args=(f"Send outreach email to lead {lead_id}. "
              "get_lead then get_conversation (email) then generate_message then send_email.",),
        kwargs={"system": BRIEF},
        daemon=True
    ).start()
    flash(f"Sending email to {lead.name}...", "success")
    return redirect(url_for("lead_detail", lead_id=lead_id))


# ── Send WhatsApp ─────────────────────────────────────────────────────────────

@app.route("/leads/<int:lead_id>/send-whatsapp", methods=["POST"])
def send_whatsapp_to_lead(lead_id):
    import threading
    lead = Lead.query.get_or_404(lead_id)
    threading.Thread(
        target=mcp_agent.run,
        args=(f"Send WhatsApp to lead {lead_id}. "
              "get_lead then get_conversation (whatsapp) then generate_message then send_whatsapp.",),
        kwargs={"system": BRIEF},
        daemon=True
    ).start()
    flash(f"Sending WhatsApp to {lead.name}...", "success")
    return redirect(url_for("lead_detail", lead_id=lead_id))


# ── Delete Lead ───────────────────────────────────────────────────────────────

@app.route("/leads/<int:lead_id>/delete", methods=["POST"])
def delete_lead(lead_id):
    lead = Lead.query.get(lead_id)
    name = lead.name if lead else f"ID {lead_id}"
    # Call MCP tool directly — no Claude needed for simple delete
    mcp_agent.call_mcp_tool("delete_lead", {"id": lead_id})
    flash(f"Lead {name} deleted.", "info")
    return redirect(url_for("index"))


# ── Twilio WhatsApp Webhook ───────────────────────────────────────────────────

@app.route("/webhook", methods=["POST"])
def webhook():
    incoming   = request.values.get("Body", "").strip()
    from_field = request.values.get("From", "").replace("whatsapp:", "").lstrip("+").strip()

    if not incoming:
        return str(MessagingResponse())

    # Find which lead this number belongs to
    lead = None
    for l in Lead.query.all():
        stored = (l.whatsapp or "").replace("whatsapp:", "").lstrip("+").strip()
        if stored == from_field:
            lead = l
            break

    if not lead:
        return str(MessagingResponse())

    calendly    = os.getenv("CALENDLY_LINK", "")
    sender      = os.getenv("SENDER_NAME", "Jamie")
    sender_role = os.getenv("SENDER_ROLE", "Account Executive")
    company     = os.getenv("SENDER_COMPANY", "Houdiny AI")

    # Hand full conversation handling to Claude via MCP
    mcp_agent.run(
        f"""WhatsApp from {lead.name} ({lead.role} at {lead.company}): "{incoming}"

Steps:
1. save_message({lead.id}, 'whatsapp', 'received', the message)
2. get_conversation({lead.id}, 'whatsapp') to read history
3. update_lead_status({lead.id}, 'whatsapp', 'Replied')
4. send_whatsapp({lead.id}, your reply)
5. If Calendly in reply → update_lead_status({lead.id}, 'whatsapp', 'Interested')""",
        system=f"""You are {sender}, {sender_role} at {company} — texting on WhatsApp.
{company} automates email + WhatsApp outreach for B2B sales teams.

OUTPUT RULE: Return ONLY the WhatsApp message text. No analysis, no labels, no thinking.

Silently check the history for: channels, country, monthly lead volume.
Then ask only what is still missing — in order:
1. Channels unknown → "What channels do you use — email, WhatsApp, or LinkedIn?"
2. Country unknown → "Which country are you targeting?"
3. Volume unknown → "How many leads per month are you reaching?"
4. All three known → pitch Houdiny + share: {calendly}
NEVER ask something already answered. NEVER repeat.

WHATSAPP FORMAT:
- MAX 2 short sentences. Text message, not an email.
- No "Hi [Name]" opener — reply naturally
- Casual, like texting
- Calendly ONLY when: yes / sure / interested / let's connect / book
- Not interested → "No worries, ping me whenever!"
- Never sound like a bot."""
    )

    # Return empty TwiML — Claude already sent the reply via Twilio
    return str(MessagingResponse())


@app.route("/health")
def health():
    return jsonify({"status": "running", "leads": Lead.query.count()})


# ── Polling API endpoints (reliable, no SSE buffering issues) ─────────────────

@app.route("/api/lead/<int:lead_id>/updates")
def lead_updates(lead_id):
    """Returns new messages and current status for a lead since a given message ID."""
    since_id = request.args.get("since", 0, type=int)
    db_file  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instance", "houdiny.db")
    try:
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row

        msgs = conn.execute(
            "SELECT id, channel, direction, content, timestamp "
            "FROM messages WHERE lead_id=? AND id>? ORDER BY id",
            (lead_id, since_id)
        ).fetchall()

        lead = conn.execute(
            "SELECT email_status, whatsapp_status FROM leads WHERE id=?", (lead_id,)
        ).fetchone()
        conn.close()

        return jsonify({
            "messages": [
                {
                    "id":        m["id"],
                    "channel":   m["channel"],
                    "direction": m["direction"],
                    "content":   m["content"],
                    "ts":        str(m["timestamp"] or "")[:16]
                }
                for m in msgs
            ],
            "email_status":    lead["email_status"]    if lead else "Not Sent",
            "whatsapp_status": lead["whatsapp_status"] if lead else "Not Sent",
        })
    except Exception as e:
        return jsonify({"error": str(e), "messages": []}), 500



@app.route("/api/dashboard")
def dashboard_data():
    """Returns current stats and all lead statuses for dashboard live update."""
    try:
        leads = Lead.query.order_by(Lead.created_at.desc()).all()
        return jsonify({
            "stats": {
                "total":         Lead.query.count(),
                "emails_sent":   Message.query.filter_by(channel="email",    direction="sent").count(),
                "whatsapp_sent": Message.query.filter_by(channel="whatsapp", direction="sent").count(),
                "replies":       Message.query.filter_by(direction="received").count(),
                "booked":        Lead.query.filter_by(status="Booked").count(),
            },
            "leads": [
                {
                    "id":              l.id,
                    "email_status":    l.email_status    or "Not Sent",
                    "whatsapp_status": l.whatsapp_status or "Not Sent",
                }
                for l in leads
            ]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500




if __name__ == "__main__":
    app.run(port=5000, debug=False, use_reloader=False)
