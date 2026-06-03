# Houdiny AI — Custom MCP Outreach Agent

> An AI-powered outbound sales agent built on a **custom Model Context Protocol (MCP) server** — automating personalised email and WhatsApp outreach, qualifying leads through real conversations, and booking meetings automatically.

---

## What This Project Does (Non-Technical)

Imagine you run a sales team. Every day your reps:
- Find potential customers
- Write personalised emails one by one
- Send WhatsApp messages
- Wait for replies
- Follow up again
- Answer questions
- Eventually book a meeting

This project automates **all of that**.

You add a person's name, company, and contact details to a dashboard. The AI:
1. Writes a personalised email and WhatsApp message for that specific person
2. Sends it to them automatically
3. When they reply — the AI reads it and responds
4. The AI asks qualifying questions (which country? how many leads? which channels?)
5. Once enough info is collected — the AI sends a meeting booking link
6. The person books a meeting with you

**You just show up to warm calls. The AI handles everything before.**

---

## Why This Project Exists

### The Problem
B2B sales teams waste 60-70% of their time on manual outreach:
- Writing the same emails with small variations
- Copy-pasting into WhatsApp
- Forgetting to follow up
- Asking the same qualifying questions repeatedly
- Juggling multiple tools (email, WhatsApp, CRM)

### The Solution
An AI agent that handles the entire outreach lifecycle end-to-end — personalised, human-sounding, and automatic.

### Who Benefits
- **Founders** doing their own sales without a full team
- **Sales teams** wanting to scale without hiring more reps
- **Agencies** running outreach campaigns for clients
- **Anyone** doing B2B outbound manually today

---

## Key Differentiator — Custom MCP

This project is built on a **custom MCP (Model Context Protocol) server** written from scratch — no official SDK, raw JSON-RPC 2.0 over HTTP.

**What this means:**
- Claude AI is the brain that decides what to do
- The MCP server exposes 11 custom tools (send email, read messages, qualify lead, etc.)
- Claude calls tools in the right order, reads results, decides next steps
- Everything flows through a standard protocol — adding a new tool takes 5 minutes

---

## Demo Flow

```
1. Add a lead → Name, Company, Role, Email, WhatsApp
        ↓
2. Click "Send Email" or "Send WhatsApp"
        ↓
3. AI generates personalised message → delivers it
        ↓
4. Lead replies (email or WhatsApp)
        ↓
5. AI reads reply → responds naturally
   Asks: channels? country? lead volume?
        ↓
6. When fully qualified → AI sends Calendly meeting link
        ↓
7. Lead books meeting
        ↓
8. Dashboard shows full conversation history + status
```

---

## Architecture

```
                    ┌─────────────────┐
                    │   YOU (Browser) │
                    └────────┬────────┘
                             │ HTTP
                             ▼
              ┌──────────────────────────┐
              │   Flask Web App :5000    │
              │   Dashboard + Webhook   │
              └─────────────┬────────────┘
                            │
                            ▼
              ┌──────────────────────────┐
              │     mcp_agent.py         │
              │  Claude API ↔ MCP bridge │
              └──────┬─────────┬─────────┘
                     │         │
               HTTP calls    Claude API
                     │         │
                     ▼         ▼
     ┌───────────────────┐  ┌──────────────────┐
     │  MCP Server :8080 │  │  Claude Sonnet   │
     │  11 Custom Tools  │  │  Decides actions │
     │  JSON-RPC 2.0     │  └──────────────────┘
     └─────────┬─────────┘
               │ calls
       ┌───────┼───────┐
       ▼       ▼       ▼
   SQLite   Gmail   Twilio
    (DB)   (Email) (WhatsApp)

   BACKGROUND:
   gmail_poller.py — checks Gmail every 30s for lead replies
   ngrok — gives your laptop a public URL for WhatsApp webhooks
```

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Language | Python 3.11+ | Entire backend |
| Web Framework | Flask | Website + API routes |
| Database | SQLite + SQLAlchemy | Store leads and messages |
| AI Model | Claude (Anthropic) | Brain — decides actions, writes copy |
| MCP Server | Custom JSON-RPC 2.0 | Protocol layer — AI to tools |
| Email Sending | Gmail SMTP | Send outreach emails |
| Email Reading | Gmail IMAP | Detect and read replies |
| WhatsApp | Twilio Sandbox | Send and receive WhatsApp messages |
| Tunnel | ngrok | Public URL for Twilio webhooks |
| Frontend | Bootstrap 5 + Jinja2 | Dashboard UI (no React needed) |
| Live Updates | JavaScript polling | Real-time chat without page refresh |

---

## MCP Architecture Explained

```
Standard MCP Flow:

Client                    MCP Server
  │                           │
  │── initialize ────────────►│  Hello, what can you do?
  │◄─ capabilities ───────────│  I have tools
  │                           │
  │── tools/list ────────────►│  What tools exactly?
  │◄─ [tool definitions] ─────│  Here are 11 tools with schemas
  │                           │
  │── tools/call ────────────►│  Call send_email with these args
  │◄─ result ─────────────────│  Email sent successfully
```

**Our custom server implements this entire protocol in `mcp_server/server.py` — ~100 lines of raw JSON-RPC 2.0, no SDK.**

### The 11 Custom Tools

**Lead Management**
- `get_lead` — Read one lead's details
- `list_leads` — Get all leads with optional filters
- `create_lead` — Add new lead to database
- `update_lead_status` — Advance status (Contacted → Replied → Interested → Booked)
- `delete_lead` — Remove lead and all their messages

**Outreach**
- `generate_message` — AI writes personalised email + WhatsApp copy
- `send_email` — Send via Gmail SMTP, auto-saves to DB
- `send_whatsapp` — Send via Twilio, auto-saves to DB

**Conversation**
- `get_conversation` — Read full message history for a lead
- `save_message` — Log incoming reply to database

**Analytics**
- `get_campaign_stats` — Campaign performance overview

---

## Project Structure

```
houdiny-ai/
├── app.py                    # Flask web app — all routes and webhook
├── mcp_agent.py              # Claude ↔ MCP server bridge
├── database.py               # SQLAlchemy models (Lead, Message)
├── gmail_poller.py           # Background email reply watcher
├── start_demo.py             # One command to start everything
├── requirements.txt          # Python dependencies
├── .env.example              # Template for credentials (copy to .env)
│
├── mcp_server/               # Custom MCP server (JSON-RPC 2.0)
│   ├── server.py             # HTTP endpoint + protocol handler
│   └── tools/
│       ├── leads.py          # Lead CRUD tools
│       ├── outreach.py       # Email + WhatsApp sending tools
│       ├── conversation.py   # Message history tools
│       └── campaign.py       # Stats tools
│
└── templates/                # HTML pages (Bootstrap 5)
    ├── base.html             # Layout + navbar
    ├── index.html            # Dashboard
    ├── add_lead.html         # Add lead form
    └── lead_detail.html      # Conversation history + send buttons
```

---

## Prerequisites

Before installing, make sure you have:

- **Python 3.11+** — [python.org/downloads](https://www.python.org/downloads/)
- **Git** — [git-scm.com](https://git-scm.com/)
- **A Gmail account** — with 2-Step Verification enabled
- **Accounts to create** (all free tier):
  - [Anthropic Console](https://console.anthropic.com) — Claude API key
  - [Twilio](https://twilio.com) — WhatsApp messaging
  - [ngrok](https://ngrok.com) — Public URL tunnel
  - [Calendly](https://calendly.com) — Meeting booking link

---

## Installation

### Step 1 — Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/houdiny-ai.git
cd houdiny-ai
```

### Step 2 — Create a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

### Step 4 — Set up credentials

```bash
cp .env.example .env
```

Open `.env` and fill in your credentials (see Credentials Guide below).

---

## Credentials Guide

Open the `.env` file and fill in each value:

### 1. Claude API Key
1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Click **API Keys** → **Create Key**
3. Copy the key starting with `sk-ant-api03-...`
4. Paste into `CLAUDE_API_KEY=`

### 2. Gmail App Password
Your regular Gmail password will NOT work. You need an App Password.

1. Go to [myaccount.google.com](https://myaccount.google.com)
2. Security → 2-Step Verification (must be ON)
3. Scroll down → **App Passwords**
4. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
5. Name it `houdiny-demo` → click Create
6. Copy the 16-character password
7. Paste into `GMAIL_APP_PASSWORD=` (remove spaces)

Also set:
- `GMAIL_USER=your-gmail@gmail.com`
- `TO_EMAIL=your-gmail@gmail.com`

### 3. Twilio (WhatsApp)

> **Important — Free Trial Limitation:**
> Twilio's free trial sandbox only allows sending WhatsApp messages to **one phone number** — your own number that you verified during setup. You cannot message other people's numbers on the free trial. To message any number, you need a paid Twilio account with an approved WhatsApp sender.

**Setup steps:**

1. Sign up at [twilio.com](https://twilio.com) — free trial gives $15 credit
2. From the **Console Dashboard**, copy:
   - `TWILIO_ACCOUNT_SID=AC...`
   - `TWILIO_AUTH_TOKEN=...`
3. Go to **Messaging → Try it out → Send a WhatsApp message**
4. You will see a page with a **QR code** and a **join code** (e.g. `join bright-tiger`)

**Connecting your phone to the sandbox (two ways):**

**Option A — Scan QR code:**
- Open WhatsApp on your phone
- Go to **Settings → Linked Devices → Link a Device**
- Scan the QR code shown on the Twilio page

**Option B — Send join code (easier):**
- Open WhatsApp on your phone
- Start a new chat with the Twilio sandbox number (shown on the page, e.g. `+14155238886`)
- Send the message: `join bright-tiger` (use your actual code)
- You'll receive a confirmation: "You are all set! The sandbox can now send/receive messages."

5. After joining, note the sandbox number:
   - `TWILIO_WHATSAPP_FROM=whatsapp:+14155238886`
6. Set **your own number** (the one you just joined with):
   - `YOUR_WHATSAPP_NUMBER=whatsapp:+91XXXXXXXXXX`

> **Note:** Every time you restart ngrok, the public URL changes. You must update the webhook URL in Twilio's Sandbox settings each time. Go to: **Messaging → Try it out → Send a WhatsApp message → Sandbox settings → "WHEN A MESSAGE COMES IN"** → paste the new ngrok URL.

### 4. ngrok
1. Sign up at [ngrok.com](https://ngrok.com)
2. Dashboard → **Your Authtoken** → copy it
3. Paste into `NGROK_AUTH_TOKEN=`

### 5. Calendly
1. Sign up at [calendly.com](https://calendly.com)
2. Copy your 30-minute meeting link
3. Paste into `CALENDLY_LINK=https://calendly.com/your-name/30min`

### 6. Sender Identity (Optional)
Customise who the AI presents as:
```
SENDER_NAME=Jamie
SENDER_ROLE=Account Executive
SENDER_COMPANY=Houdiny AI
```

---

## Running the Project

### Start everything with one command:

```bash
python start_demo.py
```

This starts:
1. MCP Server on port 8080
2. Flask Web App on port 5000
3. ngrok tunnel (public URL)
4. Gmail reply poller (background, every 30 seconds)

When you see this prompt:
```
Set this URL in Twilio console:
https://abc123.ngrok-free.app/webhook
```

Go to Twilio → Messaging → Try it out → Send a WhatsApp message → **Sandbox settings** → paste the URL → Save.

Then press **ENTER** in the terminal.

### Open the dashboard:
```
http://localhost:5000
```

---

## Using the Dashboard

### Add a Lead
1. Click **+ Add Lead**
2. Fill in: Name, Company, Role, Email, WhatsApp number
3. Add notes (optional — helps AI personalise)
4. Click **Save Lead**

### Send Outreach
- Click **Email** button → AI generates and sends personalised email
- Click **WhatsApp** button → AI sends personalised WhatsApp message
- Both appear in the lead's conversation history instantly

### View Conversations
- Click any lead's name → see full Email + WhatsApp chat history side by side
- Status badges update live: Not Sent → Contacted → Replied → Interested → Booked

### Delete a Lead
- Click **Delete** on any lead
- Removes all their data from the database
- AI stops responding to that lead's emails and WhatsApp permanently

---

## How Conversations Work

The AI qualifies every lead naturally — asking one question at a time:

```
AI:   "What channels are you running outreach on — email, WhatsApp, or LinkedIn?"
Lead: "Email and WhatsApp"
AI:   "Which country or region are you targeting?"
Lead: "India"
AI:   "How many leads are you trying to reach per month?"
Lead: "Around 1,000"
AI:   "1,000/month across email and WhatsApp in India — that's exactly
       where we see the strongest results. Here's a quick 30-min slot:
       [Calendly link]"
```

**Email replies** — detected automatically every 30 seconds via Gmail IMAP.

**WhatsApp replies** — instant, via Twilio webhook → ngrok → your laptop.

---

## Live Dashboard Features

| Feature | How it works |
|---|---|
| Status badges | Update automatically every 5 seconds |
| Chat history | New messages appear within 2 seconds (no page refresh) |
| Email chat | Shows subject as header, proper paragraph formatting |
| WhatsApp chat | Green bubbles, short messages |
| Sent messages | Blue (email) / Green (WhatsApp) — right side |
| Received messages | Gray — left side, quoted text stripped |

---

## Status Flow

```
Not Sent → Contacted → Replied → Interested → Booked
```

| Status | Meaning |
|---|---|
| Not Sent | No outreach sent yet |
| Contacted | First message sent |
| Replied | Lead has replied |
| Interested | Calendly link sent (lead showed interest) |
| Booked | Meeting confirmed |

Email and WhatsApp have **separate statuses** — a lead can be "Interested" on WhatsApp but only "Contacted" on email.

---

## Troubleshooting

**Email not arriving?**
- Check `GMAIL_APP_PASSWORD` is correct (no spaces)
- Make sure 2-Step Verification is ON in your Google account
- Check spam folder

**WhatsApp not working?**
- Make sure you joined the Twilio sandbox from your phone
- Make sure the ngrok URL is set in Twilio Sandbox settings
- ngrok URL changes every restart — update Twilio each time

**"Module not found" error?**
- Make sure virtual environment is activated
- Run `pip install -r requirements.txt` again

**Database errors?**
- Delete `instance/houdiny.db` and restart — it will be recreated fresh

---

## Contributing

This project was built as a technical demo for showcasing custom MCP implementation and AI-powered outreach automation. Pull requests welcome.

---

## License

MIT License — free to use, modify, and distribute.

---

## Built With

- [Anthropic Claude](https://anthropic.com) — AI model
- [Model Context Protocol](https://modelcontextprotocol.io) — AI tool protocol
- [Flask](https://flask.palletsprojects.com) — Web framework
- [Twilio](https://twilio.com) — WhatsApp API
- [Bootstrap 5](https://getbootstrap.com) — UI framework
