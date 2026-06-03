"""
Houdiny AI — MCP Agent
Connects Claude API to the production MCP server over HTTP.
Events are logged to a simple in-memory list at the same point
terminal output is produced — this guarantees Live MCP sees everything.
"""

import os
import json
import threading
import requests
import anthropic
from dotenv import load_dotenv

load_dotenv()

MCP_URL      = "http://localhost:8080/mcp"
_tools_cache = None

# ── Event log (written at same point as terminal prints) ─────────────────────
_event_log  = []
_log_seq    = 0
_log_lock   = threading.Lock()
_MAXLOG     = 200


def _log(evt: dict):
    """Append event to log — called at the same point as every terminal print."""
    global _log_seq
    try:
        safe = json.loads(json.dumps(evt, default=str))
    except Exception:
        safe = {"type": str(evt.get("type", "unknown"))}
    with _log_lock:
        _log_seq += 1
        safe["_seq"] = _log_seq
        _event_log.append(safe)
        if len(_event_log) > _MAXLOG:
            _event_log.pop(0)


def get_events_since(seq: int) -> list:
    """Return all logged events with _seq > seq."""
    with _log_lock:
        return [e for e in _event_log if e.get("_seq", 0) > seq]


# kept for backwards compatibility
def subscribe():
    import queue as _q
    q = _q.Queue()
    with _log_lock:
        for e in _event_log:
            try: q.put_nowait(e)
            except Exception: pass
    return q

def unsubscribe(q): pass
def clear_history(): pass   # no-op — clearing caused missed events


# ── MCP protocol calls ────────────────────────────────────────────────────────

def get_mcp_tools():
    global _tools_cache
    if _tools_cache is None:
        resp = requests.post(MCP_URL, json={
            "jsonrpc": "2.0", "id": 1, "method": "tools/list"
        }, timeout=10)
        _tools_cache = resp.json()["result"]["tools"]
    return _tools_cache


def call_mcp_tool(name: str, arguments: dict) -> str:
    data = requests.post(MCP_URL, json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": name, "arguments": arguments}
    }, timeout=30).json()
    if "result" in data:
        content = data["result"].get("content", [])
        return content[0]["text"] if content else ""
    return json.dumps({"error": data.get("error", {}).get("message", "MCP error")})


def mcp_tools_for_claude():
    return [
        {"name": t["name"], "description": t["description"], "input_schema": t["inputSchema"]}
        for t in get_mcp_tools()
    ]


# ── Agent orchestrator ────────────────────────────────────────────────────────

DEFAULT_SYSTEM = """You are an AI sales agent for Houdiny AI — an outbound platform \
that automates LinkedIn and email campaigns for B2B teams.

You have tools to manage leads, send outreach, read conversations, and track campaigns.

How to work:
- Always get_lead or get_conversation BEFORE sending anything — read context first.
- When sending outreach: generate_message → send_email/send_whatsapp → status is auto-updated.
- When replying to a lead: save incoming message → get_conversation → send reply → update_lead_status.
- Keep replies SHORT (3 sentences max for WhatsApp, 4 for email).
- Include Calendly link ({calendly}) if lead shows ANY interest.
- Be concise in your final summary."""

CALENDLY = os.getenv("CALENDLY_LINK", "")


def run(prompt: str, system: str = None, verbose: bool = True) -> str:
    """
    Run Claude with full MCP tool access.
    Every meaningful step is logged (same point as terminal print).
    """
    tools    = mcp_tools_for_claude()
    client   = anthropic.Anthropic(api_key=os.getenv("CLAUDE_API_KEY"))
    sys_msg  = (system or DEFAULT_SYSTEM).replace("{calendly}", CALENDLY)
    messages = [{"role": "user", "content": prompt}]

    # ── log + print start ──
    if verbose:
        print(f"\n[AGENT] Prompt: {prompt[:100]}...")
    _log({"type": "divider"})
    _log({"type": "start", "prompt": prompt[:120]})

    while True:
        # ── log + print thinking ──
        _log({"type": "claude_thinking"})

        resp = client.messages.create(
            model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6"),
            max_tokens=4096,
            tools=tools,
            system=sys_msg,
            messages=messages
        )

        if resp.stop_reason == "end_turn":
            final = ""
            for block in resp.content:
                if hasattr(block, "text"):
                    final = block.text
                    break
            if verbose:
                print(f"[AGENT] Done: {final[:80]}")
            # ── log + print done ──
            _log({"type": "done", "result": final[:200]})
            return final or "Done."

        elif resp.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": resp.content})
            tool_results = []

            for block in resp.content:
                if block.type == "tool_use":
                    args_safe = dict(block.input)   # plain dict copy

                    # ── log + print tool call ──
                    if verbose:
                        print(f"[AGENT]  tool={block.name}  args={json.dumps(args_safe)[:80]}")
                    _log({"type": "tool_call", "name": block.name, "args": args_safe})

                    result = call_mcp_tool(block.name, block.input)

                    # ── log + print tool result ──
                    if verbose:
                        print(f"[AGENT]  result={result[:100]}")
                    _log({"type": "tool_result", "name": block.name, "result": result[:200]})

                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": block.id,
                        "content":     result
                    })

            messages.append({"role": "user", "content": tool_results})

        else:
            if verbose:
                print(f"[AGENT] Unexpected stop: {resp.stop_reason}")
            _log({"type": "error", "message": f"Agent stopped: {resp.stop_reason}"})
            return "Agent stopped unexpectedly."
