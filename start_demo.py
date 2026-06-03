import os
import sys
import time
import threading
import requests
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()


def run_mcp_server():
    from mcp_server.server import app
    app.run(port=8080, debug=False, use_reloader=False, threaded=True)


def run_flask_app():
    from app import app
    app.run(port=5000, debug=False, use_reloader=False, threaded=True)


def run_gmail_poller():
    from gmail_poller import run_poller
    run_poller(interval=30)


def wait_for_service(url, name, retries=10):
    for i in range(retries):
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                print(f"      {name} ready")
                return True
        except Exception:
            pass
        time.sleep(1)
    print(f"      WARNING: {name} did not respond after {retries}s")
    return False


def main():
    print("\n" + "=" * 60)
    print("  HOUDINY AI — PRODUCTION MCP DEMO")
    print("=" * 60)

    # Step 1 — MCP Server
    print("\n[1/5] Starting MCP Server (port 8080)...")
    t1 = threading.Thread(target=run_mcp_server, daemon=True)
    t1.start()
    wait_for_service("http://localhost:8080/health", "MCP Server")

    # Step 2 — Flask Web App
    print("\n[2/5] Starting Web Dashboard (port 5000)...")
    t2 = threading.Thread(target=run_flask_app, daemon=True)
    t2.start()
    wait_for_service("http://localhost:5000/health", "Web Dashboard")

    # Step 3 — ngrok
    print("\n[3/5] Starting ngrok tunnel...")
    from pyngrok import ngrok, conf
    conf.get_default().auth_token = os.getenv("NGROK_AUTH_TOKEN")
    tunnel = ngrok.connect(5000)
    webhook_url = f"{tunnel.public_url}/webhook"
    print(f"      Public URL: {webhook_url}")

    # Step 4 — Twilio webhook setup
    print("\n[4/5] Set this URL in Twilio console:")
    print("\n" + "=" * 60)
    print(f"  {webhook_url}")
    print("=" * 60)
    print("\n  Steps:")
    print("  1. console.twilio.com")
    print("  2. Messaging -> Try it out -> Send a WhatsApp message")
    print("  3. Click 'Sandbox settings' tab")
    print("  4. Paste URL above into 'WHEN A MESSAGE COMES IN'")
    print("  5. Click Save\n")
    input("  Press ENTER after saving...")

    # Step 5 — Gmail poller
    print("\n[5/5] Starting Gmail reply poller (every 30s)...")
    t3 = threading.Thread(target=run_gmail_poller, daemon=True)
    t3.start()

    # Ready
    print("\n" + "=" * 60)
    print("  ALL SYSTEMS RUNNING")
    print("=" * 60)
    print(f"\n  Web Dashboard : http://localhost:5000")
    print(f"  MCP Server    : http://localhost:8080")
    print(f"  Webhook       : {webhook_url}")
    print(f"\n  Architecture  : Browser -> Flask -> Claude -> MCP Server -> Tools")
    print(f"\n  Press Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        ngrok.kill()


if __name__ == "__main__":
    main()
