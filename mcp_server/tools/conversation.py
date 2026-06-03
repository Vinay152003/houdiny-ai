import sqlite3
import json
from . import db_path


def _conn():
    c = sqlite3.connect(db_path())
    c.row_factory = sqlite3.Row
    return c


def get_conversation(lead_id: int, channel: str = None) -> str:
    """Get full message history for a lead. Optionally filter by channel ('email' or 'whatsapp')."""
    with _conn() as conn:
        if channel:
            rows = conn.execute(
                "SELECT * FROM messages WHERE lead_id=? AND channel=? ORDER BY timestamp",
                (lead_id, channel)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM messages WHERE lead_id=? ORDER BY timestamp",
                (lead_id,)
            ).fetchall()
    if not rows:
        return json.dumps({"messages": [], "count": 0,
                           "note": "No conversation history yet."})
    return json.dumps({
        "messages": [dict(r) for r in rows],
        "count": len(rows)
    }, default=str)


def save_message(lead_id: int, channel: str, direction: str, content: str) -> str:
    """Save a message to the database. channel='email'|'whatsapp', direction='sent'|'received'."""
    with _conn() as conn:
        conn.execute(
            "INSERT INTO messages (lead_id,channel,direction,content,timestamp) "
            "VALUES (?,?,?,?,datetime('now'))",
            (lead_id, channel, direction, content)
        )
        conn.commit()
    return json.dumps({"success": True, "saved": f"{direction} {channel} message for lead {lead_id}"})
