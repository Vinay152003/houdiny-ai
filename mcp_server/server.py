"""
Houdiny AI — Production MCP Server
Transport: HTTP (POST /mcp)
Port: 8080

Every request is a JSON-RPC 2.0 message.
Supported methods: initialize, tools/list, tools/call
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# ── Tool definitions (the MCP contract) ──────────────────────────────────────

TOOLS = [
    # ── Lead management ──────────────────────────────────────────────────────
    {
        "name": "get_lead",
        "description": "Get full details of a single lead by their ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "Lead ID"}
            },
            "required": ["id"]
        }
    },
    {
        "name": "list_leads",
        "description": "List all leads. Optionally filter by email_status or whatsapp_status.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "email_status":    {"type": "string", "description": "Filter by email status: Not Sent, Contacted, Replied, Interested, Booked"},
                "whatsapp_status": {"type": "string", "description": "Filter by WhatsApp status: Not Sent, Contacted, Replied, Interested, Booked"}
            }
        }
    },
    {
        "name": "create_lead",
        "description": "Create a new lead in the database.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name":     {"type": "string",  "description": "Full name (required)"},
                "company":  {"type": "string",  "description": "Company name"},
                "role":     {"type": "string",  "description": "Job title or role"},
                "email":    {"type": "string",  "description": "Email address"},
                "whatsapp": {"type": "string",  "description": "WhatsApp number with country code e.g. +919876543210"},
                "industry": {"type": "string",  "description": "Industry e.g. SaaS, Healthcare"},
                "notes":    {"type": "string",  "description": "Context notes to personalise outreach"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "update_lead_status",
        "description": "Update the email_status or whatsapp_status of a lead. Status only moves forward: Not Sent → Contacted → Replied → Interested → Booked.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id":      {"type": "integer", "description": "Lead ID"},
                "channel": {"type": "string",  "description": "Channel: 'email' or 'whatsapp'"},
                "status":  {"type": "string",  "description": "New status: Not Sent, Contacted, Replied, Interested, Booked"}
            },
            "required": ["id", "channel", "status"]
        }
    },
    {
        "name": "delete_lead",
        "description": "Delete a lead and all their messages. This permanently stops all future outreach to them.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "Lead ID to delete"}
            },
            "required": ["id"]
        }
    },

    # ── Outreach ─────────────────────────────────────────────────────────────
    {
        "name": "generate_message",
        "description": "Generate a hyper-personalised cold email and WhatsApp message for a lead using AI. Returns email_subject, email_body, and whatsapp_message.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "lead_id": {"type": "integer", "description": "Lead ID"},
                "context": {"type": "string",  "description": "Optional extra context or pitch to personalise around"}
            },
            "required": ["lead_id"]
        }
    },
    {
        "name": "send_email",
        "description": "Send a personalised email to a lead via Gmail. Automatically saves the message to the database and updates email status to Contacted.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "lead_id": {"type": "integer", "description": "Lead ID"},
                "subject": {"type": "string",  "description": "Email subject line"},
                "body":    {"type": "string",  "description": "Email body text"}
            },
            "required": ["lead_id", "subject", "body"]
        }
    },
    {
        "name": "send_whatsapp",
        "description": "Send a WhatsApp message to a lead via Twilio. Automatically saves the message to the database and updates WhatsApp status to Contacted.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "lead_id": {"type": "integer", "description": "Lead ID"},
                "message": {"type": "string",  "description": "WhatsApp message text"}
            },
            "required": ["lead_id", "message"]
        }
    },

    # ── Conversation ─────────────────────────────────────────────────────────
    {
        "name": "get_conversation",
        "description": "Get the full message history for a lead. Optionally filter by channel.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "lead_id": {"type": "integer", "description": "Lead ID"},
                "channel": {"type": "string",  "description": "Optional: 'email' or 'whatsapp'"}
            },
            "required": ["lead_id"]
        }
    },
    {
        "name": "save_message",
        "description": "Save a message to the database. Use this to log incoming replies from leads.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "lead_id":   {"type": "integer", "description": "Lead ID"},
                "channel":   {"type": "string",  "description": "'email' or 'whatsapp'"},
                "direction": {"type": "string",  "description": "'sent' or 'received'"},
                "content":   {"type": "string",  "description": "Message content"}
            },
            "required": ["lead_id", "channel", "direction", "content"]
        }
    },

    # ── Campaign ─────────────────────────────────────────────────────────────
    {
        "name": "get_campaign_stats",
        "description": "Get overall campaign performance statistics: emails sent, WhatsApps sent, replies, interested leads, booked meetings.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]


# ── Tool dispatcher ───────────────────────────────────────────────────────────

def dispatch(name: str, arguments: dict) -> str:
    if name == "get_lead":
        from mcp_server.tools.leads import get_lead
        return get_lead(**arguments)
    elif name == "list_leads":
        from mcp_server.tools.leads import list_leads
        return list_leads(**arguments)
    elif name == "create_lead":
        from mcp_server.tools.leads import create_lead
        return create_lead(**arguments)
    elif name == "update_lead_status":
        from mcp_server.tools.leads import update_lead_status
        return update_lead_status(**arguments)
    elif name == "delete_lead":
        from mcp_server.tools.leads import delete_lead
        return delete_lead(**arguments)
    elif name == "generate_message":
        from mcp_server.tools.outreach import generate_message
        return generate_message(**arguments)
    elif name == "send_email":
        from mcp_server.tools.outreach import send_email
        return send_email(**arguments)
    elif name == "send_whatsapp":
        from mcp_server.tools.outreach import send_whatsapp
        return send_whatsapp(**arguments)
    elif name == "get_conversation":
        from mcp_server.tools.conversation import get_conversation
        return get_conversation(**arguments)
    elif name == "save_message":
        from mcp_server.tools.conversation import save_message
        return save_message(**arguments)
    elif name == "get_campaign_stats":
        from mcp_server.tools.campaign import get_campaign_stats
        return get_campaign_stats()
    else:
        return f'{{"error": "Unknown tool: {name}"}}'


# ── MCP HTTP endpoint ─────────────────────────────────────────────────────────

@app.route("/mcp", methods=["POST"])
def mcp_endpoint():
    msg    = request.get_json(force=True)
    msg_id = msg.get("id")
    method = msg.get("method", "")
    params = msg.get("params", {})

    if method == "initialize":
        result = {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "houdiny-mcp-production", "version": "2.0.0"}
        }

    elif method == "tools/list":
        result = {"tools": TOOLS}

    elif method == "tools/call":
        name      = params.get("name", "")
        arguments = params.get("arguments", {})
        print(f"[MCP] tool={name} args={str(arguments)[:80]}")
        try:
            output = dispatch(name, arguments)
            result = {"content": [{"type": "text", "text": str(output)}]}
        except Exception as e:
            result = {"content": [{"type": "text", "text": f'{{"error": "{str(e)}"}}'}]}

    else:
        return jsonify({"jsonrpc": "2.0", "id": msg_id,
                        "error": {"code": -32601, "message": f"Method not found: {method}"}})

    return jsonify({"jsonrpc": "2.0", "id": msg_id, "result": result})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "running", "version": "2.0.0", "tools": len(TOOLS)})


if __name__ == "__main__":
    print(f"[MCP SERVER] Starting on port 8080 — {len(TOOLS)} tools loaded")
    app.run(port=8080, debug=False, use_reloader=False)
