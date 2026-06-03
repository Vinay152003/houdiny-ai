import sqlite3
import json
from . import db_path


def get_campaign_stats() -> str:
    """Get overall campaign performance statistics across all leads and channels."""
    with sqlite3.connect(db_path()) as conn:
        stats = {
            "total_leads":     conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0],
            "emails_sent":     conn.execute("SELECT COUNT(*) FROM messages WHERE channel='email' AND direction='sent'").fetchone()[0],
            "whatsapp_sent":   conn.execute("SELECT COUNT(*) FROM messages WHERE channel='whatsapp' AND direction='sent'").fetchone()[0],
            "email_replies":   conn.execute("SELECT COUNT(*) FROM messages WHERE channel='email' AND direction='received'").fetchone()[0],
            "wa_replies":      conn.execute("SELECT COUNT(*) FROM messages WHERE channel='whatsapp' AND direction='received'").fetchone()[0],
            "interested":      conn.execute("SELECT COUNT(*) FROM leads WHERE status='Interested'").fetchone()[0],
            "booked":          conn.execute("SELECT COUNT(*) FROM leads WHERE status='Booked'").fetchone()[0],
            "by_email_status": dict(conn.execute(
                "SELECT email_status, COUNT(*) FROM leads GROUP BY email_status"
            ).fetchall()),
            "by_wa_status":    dict(conn.execute(
                "SELECT whatsapp_status, COUNT(*) FROM leads GROUP BY whatsapp_status"
            ).fetchall()),
        }
    return json.dumps(stats, indent=2)
