import sqlite3
import json
from . import db_path

STATUS_ORDER = ["Not Sent", "Contacted", "Replied", "Interested", "Booked"]


def _conn():
    c = sqlite3.connect(db_path())
    c.row_factory = sqlite3.Row
    return c


def get_lead(id: int) -> str:
    """Get a single lead by ID. Returns full lead details."""
    with _conn() as conn:
        row = conn.execute("SELECT * FROM leads WHERE id=?", (id,)).fetchone()
    if row:
        return json.dumps(dict(row), default=str)
    return json.dumps({"error": f"Lead {id} not found"})


def list_leads(email_status: str = None, whatsapp_status: str = None) -> str:
    """List all leads. Optionally filter by email_status or whatsapp_status."""
    query = "SELECT * FROM leads"
    conds, params = [], []
    if email_status:
        conds.append("email_status=?"); params.append(email_status)
    if whatsapp_status:
        conds.append("whatsapp_status=?"); params.append(whatsapp_status)
    if conds:
        query += " WHERE " + " AND ".join(conds)
    query += " ORDER BY created_at DESC"
    with _conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return json.dumps([dict(r) for r in rows], default=str)


def create_lead(name: str, company: str = "", role: str = "",
                email: str = "", whatsapp: str = "",
                industry: str = "", notes: str = "") -> str:
    """Create a new lead in the database."""
    with _conn() as conn:
        cur = conn.execute(
            """INSERT INTO leads
               (name,company,role,email,whatsapp,industry,notes,
                status,email_status,whatsapp_status,created_at)
               VALUES (?,?,?,?,?,?,?,'New','Not Sent','Not Sent',datetime('now'))""",
            (name, company, role, email, whatsapp, industry, notes)
        )
        lead_id = cur.lastrowid
        conn.commit()
    return json.dumps({"success": True, "lead_id": lead_id,
                       "message": f"Lead '{name}' created with ID {lead_id}"})


def update_lead_status(id: int, channel: str, status: str) -> str:
    """Update email_status or whatsapp_status for a lead. channel = 'email' or 'whatsapp'. Status only moves forward."""
    field = "email_status" if channel == "email" else "whatsapp_status"
    with _conn() as conn:
        row = conn.execute(f"SELECT {field} FROM leads WHERE id=?", (id,)).fetchone()
        if not row:
            return json.dumps({"error": f"Lead {id} not found"})
        current = row[field] or "Not Sent"
        try:
            if STATUS_ORDER.index(status) > STATUS_ORDER.index(current):
                conn.execute(f"UPDATE leads SET {field}=? WHERE id=?", (status, id))
                conn.execute(
                    "UPDATE leads SET status=? WHERE id=? AND status NOT IN ('Interested','Booked')",
                    (status, id)
                )
                conn.commit()
                return json.dumps({"success": True,
                                   "updated": f"{field}: {current} -> {status}"})
            else:
                # Already at this level or higher — treat as success (idempotent)
                return json.dumps({"success": True,
                                   "message": f"{field} already at {current} (no change needed)"})
        except ValueError:
            return json.dumps({"error": f"Unknown status '{status}'"})


def delete_lead(id: int) -> str:
    """Delete a lead and all their messages from the database. This stops all future outreach."""
    with _conn() as conn:
        row = conn.execute("SELECT name FROM leads WHERE id=?", (id,)).fetchone()
        if not row:
            return json.dumps({"error": f"Lead {id} not found"})
        name = row["name"]
        conn.execute("DELETE FROM messages WHERE lead_id=?", (id,))
        conn.execute("DELETE FROM leads WHERE id=?", (id,))
        conn.commit()
    return json.dumps({"success": True,
                       "message": f"Lead '{name}' and all their messages deleted."})
