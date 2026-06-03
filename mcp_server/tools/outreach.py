import os
import re
import json
import sqlite3
import smtplib
import anthropic
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from . import db_path

load_dotenv()


def _get_lead(lead_id: int):
    c = sqlite3.connect(db_path())
    c.row_factory = sqlite3.Row
    row = c.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
    c.close()
    return dict(row) if row else None


def _save_message(lead_id, channel, direction, content):
    c = sqlite3.connect(db_path())
    c.execute(
        "INSERT INTO messages (lead_id,channel,direction,content,timestamp) "
        "VALUES (?,?,?,?,datetime('now'))",
        (lead_id, channel, direction, content)
    )
    c.commit()
    c.close()


def _advance_status(lead_id, channel, new_status):
    order = ["Not Sent", "Contacted", "Replied", "Interested", "Booked"]
    field = "email_status" if channel == "email" else "whatsapp_status"
    c = sqlite3.connect(db_path())
    c.row_factory = sqlite3.Row
    row = c.execute(f"SELECT {field} FROM leads WHERE id=?", (lead_id,)).fetchone()
    if row:
        current = row[field] or "Not Sent"
        if order.index(new_status) > order.index(current):
            c.execute(f"UPDATE leads SET {field}=? WHERE id=?", (new_status, lead_id))
            c.execute(
                "UPDATE leads SET status=? WHERE id=? AND status NOT IN ('Interested','Booked')",
                (new_status, lead_id)
            )
            c.commit()
    c.close()


def generate_message(lead_id: int, context: str = "") -> str:
    """Generate a hyper-personalised cold email and WhatsApp message for a lead using AI.
    Returns JSON with email_subject, email_body, and whatsapp_message."""
    lead = _get_lead(lead_id)
    if not lead:
        return json.dumps({"error": f"Lead {lead_id} not found"})

    client = anthropic.Anthropic(api_key=os.getenv("CLAUDE_API_KEY"))
    pitch = context or "AI-powered outbound platform automating LinkedIn and email campaigns for B2B teams"

    sender  = os.getenv("SENDER_NAME", "Jamie")
    role    = os.getenv("SENDER_ROLE", "Account Executive")
    company = os.getenv("SENDER_COMPANY", "Houdiny AI")

    prompt = f"""Write cold outreach for this lead. You are {sender}, {role} at {company}.
{company} automates email and WhatsApp outreach campaigns for B2B sales teams.

Lead:
- Name: {lead['name']}
- Company: {lead['company']}
- Role: {lead['role']}
- Industry: {lead['industry'] or 'B2B'}
- Notes: {lead['notes'] or ''}

════ EMAIL ════
Use this EXACT structure with blank lines between sections:

Subject: [specific subject referencing their role or company]

Hi {lead['name'].split()[0]},

[Sentence 1: Reference their role/company and the pain — e.g. "Running outbound at [Company] manually still takes up a big chunk of time."]

[Sentence 2: What we do and how it helps — one clear sentence. Mention email + WhatsApp channels.]

[Sentence 3: ONE qualifying question — e.g. "Quick question — which countries are you targeting for outbound right now?"]

Best,
{sender}
{role} | {company}

════ WHATSAPP ════
This is the FIRST message — introduce yourself briefly then ask one question.
Format: "Hey! [sender first name] from [company] here. [One short hook question — 10 words max]"
Keep it casual like a real text. Total: 2 short sentences.
Example: "Hey! Jamie from Houdiny AI here. Still doing outbound manually at {lead['company']}?"

Respond ONLY with valid JSON (no markdown, no extra text):
{{"email_subject": "...", "email_body": "...", "whatsapp_message": "..."}}"""

    resp = client.messages.create(
        model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6"),
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = resp.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return raw  # already JSON string


def send_email(lead_id: int, subject: str, body: str) -> str:
    """Send a personalised email to a lead via Gmail. Automatically saves to DB and updates status."""
    lead = _get_lead(lead_id)
    if not lead:
        return json.dumps({"error": f"Lead {lead_id} not found"})
    if not lead["email"]:
        return json.dumps({"error": f"Lead {lead_id} has no email address"})

    gmail_user = os.getenv("GMAIL_USER")
    gmail_pass = os.getenv("GMAIL_APP_PASSWORD")

    msg = MIMEMultipart()
    msg["From"]    = gmail_user
    msg["To"]      = lead["email"]
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_pass)
            server.send_message(msg)

        _save_message(lead_id, "email", "sent", body)
        _advance_status(lead_id, "email", "Contacted")

        return json.dumps({
            "success": True,
            "to": lead["email"],
            "subject": subject,
            "message": f"Email sent to {lead['name']} at {lead['email']}"
        })
    except Exception as e:
        return json.dumps({"error": f"Failed to send email: {str(e)}"})


def send_whatsapp(lead_id: int, message: str) -> str:
    """Send a WhatsApp message to a lead via Twilio. Automatically saves to DB and updates status."""
    lead = _get_lead(lead_id)
    if not lead:
        return json.dumps({"error": f"Lead {lead_id} not found"})
    if not lead["whatsapp"]:
        return json.dumps({"error": f"Lead {lead_id} has no WhatsApp number"})

    from twilio.rest import Client
    client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))

    number = lead["whatsapp"].strip().lstrip("+")
    to = f"whatsapp:+{number}"

    try:
        msg = client.messages.create(
            body=message,
            from_=os.getenv("TWILIO_WHATSAPP_FROM"),
            to=to
        )
        _save_message(lead_id, "whatsapp", "sent", message)
        _advance_status(lead_id, "whatsapp", "Contacted")

        return json.dumps({
            "success": True,
            "sid": msg.sid,
            "to": to,
            "message": f"WhatsApp sent to {lead['name']}"
        })
    except Exception as e:
        return json.dumps({"error": f"Failed to send WhatsApp: {str(e)}"})
