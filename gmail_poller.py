"""
Gmail Reply Poller — checks inbox every 30s for lead replies.
Uses MCP agent to handle replies intelligently.
"""

import imaplib
import email
import smtplib
import os
import re
import time
import sqlite3
import anthropic
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
from dotenv import load_dotenv
import mcp_agent

load_dotenv()

IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993
processed_ids = set()

SKIP_SENDERS = [
    "noreply", "no-reply", "donotreply", "do-not-reply",
    "accounts.google.com", "email.anthropic.com",
    "mailer-daemon", "postmaster", "notifications@",
    "team@email", "@email.", "alert", "security"
]

def _build_skip():
    """Add our own Gmail address to skip list to prevent self-reply loops."""
    own = os.getenv("GMAIL_USER", "").lower()
    if own and own not in SKIP_SENDERS:
        SKIP_SENDERS.append(own)
_build_skip()


def _db_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "instance", "houdiny.db")


def _find_lead_by_email(sender_raw: str):
    match = re.search(r"<(.+?)>", sender_raw)
    addr = (match.group(1) if match else sender_raw).strip().lower()
    try:
        conn = sqlite3.connect(_db_path())
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, name, company, role FROM leads WHERE lower(email)=?", (addr,)
        ).fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception as e:
        print(f"[EMAIL] DB error: {e}")
        return None


def _decode_str(value):
    if not value:
        return ""
    decoded, encoding = decode_header(value)[0]
    if isinstance(decoded, bytes):
        return decoded.decode(encoding or "utf-8", errors="replace")
    return decoded or ""


def _get_body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode("utf-8", errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            return payload.decode("utf-8", errors="replace")
    return ""


def _is_real_reply(sender: str, subject: str) -> bool:
    sender_lower = sender.lower()
    subj_lower   = subject.lower()
    # Must be a reply
    if not subj_lower.startswith("re:"):
        return False
    # Skip our own forwarded demo emails (subject contains "[to:")
    if "[to:" in subj_lower:
        return False
    # Skip automated senders
    for skip in SKIP_SENDERS:
        if skip in sender_lower:
            return False
    return True


def _strip_quoted(body: str) -> str:
    """Keep only the new message — strip Gmail quoted text."""
    lines = body.split('\n')
    clean = []
    for line in lines:
        s = line.strip()
        if s.startswith('>') or re.match(r'^On .+wrote:$', s.replace('\r', '')):
            break
        clean.append(line)
    return '\n'.join(clean).strip()


def _handle_email_reply(lead: dict, clean_subj: str, clean_body: str, reply_subject: str):
    """
    Handle an incoming email reply.
    Claude writes the reply body ONLY.
    We control the subject — it never changes within a thread.
    """
    calendly = os.getenv("CALENDLY_LINK", "")

    # 1. Save incoming message (new text only)
    mcp_agent.call_mcp_tool("save_message", {
        "lead_id":   lead["id"],
        "channel":   "email",
        "direction": "received",
        "content":   clean_body
    })

    # 2. Mark as Replied
    mcp_agent.call_mcp_tool("update_lead_status", {
        "id": lead["id"], "channel": "email", "status": "Replied"
    })

    # 3. Read full conversation for context
    history = mcp_agent.call_mcp_tool("get_conversation", {
        "lead_id": lead["id"], "channel": "email"
    })
    calendly_already_sent = calendly and calendly in history

    sender      = os.getenv("SENDER_NAME", "Jamie")
    sender_role = os.getenv("SENDER_ROLE", "Account Executive")
    company     = os.getenv("SENDER_COMPANY", "Houdiny AI")
    first_name  = lead["name"].split()[0]

    calendly_rule = (
        f"Include the Calendly link ({calendly}) ONLY if they explicitly say: "
        "yes / interested / let's connect / book / when can we meet / sure / go ahead."
        if not calendly_already_sent
        else "Do NOT include the Calendly link — already sent earlier in this thread."
    )

    # 4. Claude writes reply BODY only — no tools, no subject choice
    client = anthropic.Anthropic(api_key=os.getenv("CLAUDE_API_KEY"))
    resp = client.messages.create(
        model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6"),
        max_tokens=300,
        system=f"""You are {sender}, {sender_role} at {company}.
{company} automates email and WhatsApp outreach campaigns for B2B sales teams.

OUTPUT RULE: Return ONLY the email body. No analysis, no thinking, no labels, no "---". Just the email.

Before writing, silently check the conversation history for:
- Channels already mentioned? (email / WhatsApp / LinkedIn)
- Country already mentioned?
- Monthly lead volume already mentioned?

Then ask ONLY what is still missing — in this order:
1. Channels (if unknown) → "What channels are you running — email, WhatsApp, or LinkedIn?"
2. Country (if unknown) → "Which country or region are you targeting?"
3. Volume (if unknown) → "How many leads are you trying to reach per month?"
4. All three known → make the pitch and include: {calendly}

NEVER ask about something already answered. NEVER repeat a question.

Write the reply in this exact format:

Hi {first_name},

[1-2 sentences answering their message — genuine and direct]

[ONE question from above, OR Calendly pitch if all info collected]

Best,
{sender}
{sender_role} | {company}

Max 4 sentences total. Sound like a real person. {calendly_rule}""",
        messages=[{"role": "user", "content":
            f"Lead: {lead['name']}, {lead['role']} at {lead['company']}\n"
            f"Their message: {clean_body}\n"
            f"Conversation so far:\n{history[:500]}"
        }]
    )
    reply_body = resp.content[0].text.strip()

    # 5. Send with the SAME subject — we set it, Claude doesn't touch it
    mcp_agent.call_mcp_tool("send_email", {
        "lead_id": lead["id"],
        "subject": reply_subject,   # ← always "Re: <original subject>"
        "body":    reply_body
    })

    # 6. Promote to Interested if Calendly was included
    if calendly and calendly in reply_body:
        mcp_agent.call_mcp_tool("update_lead_status", {
            "id": lead["id"], "channel": "email", "status": "Interested"
        })

    print(f"[EMAIL] Replied to {lead['name']} | subject: {reply_subject}")
    print(f"[EMAIL] Body: {reply_body[:80]}...")


def poll_once():
    try:
        mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        mail.login(os.getenv("GMAIL_USER"), os.getenv("GMAIL_APP_PASSWORD"))
        mail.select("INBOX")

        _, ids_data = mail.search(None, "UNSEEN")
        ids = ids_data[0].split()

        for msg_id in ids:
            if msg_id in processed_ids:
                continue
            processed_ids.add(msg_id)

            _, msg_data = mail.fetch(msg_id, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])

            sender  = _decode_str(msg.get("From", ""))
            subject = _decode_str(msg.get("Subject", ""))
            body    = _get_body(msg)

            if not _is_real_reply(sender, subject):
                continue

            lead = _find_lead_by_email(sender)
            if not lead or not body.strip():
                continue

            print(f"\n[EMAIL] Reply from {lead['name']} ({sender})")

            # ── Keep subject clean — strip all Re: prefixes, add exactly one ──
            clean_subj   = re.sub(r'^(re:\s*)+', '', subject, flags=re.IGNORECASE).strip()
            reply_subject = f"Re: {clean_subj[:80]}"

            # ── Strip quoted text from body ──
            clean_body = _strip_quoted(body)

            # ── Handle reply WITHOUT letting Claude change the subject ──
            _handle_email_reply(lead, clean_subj, clean_body, reply_subject)

        mail.close()
        mail.logout()

    except Exception as e:
        print(f"[EMAIL] Poll error: {e}")


def run_poller(interval: int = 30):
    print(f"[EMAIL] Poller started — checking every {interval}s (leads in DB only)")
    while True:
        poll_once()
        time.sleep(interval)


if __name__ == "__main__":
    run_poller()
