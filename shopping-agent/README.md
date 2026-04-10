# 🛒 UI Shop Agent — Multi-Agent Walmart Shopping System

A **chat-based, multi-agent shopping automation system** built with:

| Component | Technology |
|-----------|-----------|
| Browser automation | [Playwright](https://playwright.dev/python/) (async Chromium) |
| Agent protocol | [MCP](https://spec.modelcontextprotocol.io/) (Model Context Protocol) |
| LLM backbone | OpenAI GPT-4o *or* Anthropic Claude |
| Chat UI | [Rich](https://github.com/Textualize/rich) terminal interface |
| Config management | python-dotenv |

---

## Table of Contents

1. [Architecture](#architecture)
2. [Project Structure](#project-structure)
3. [Prerequisites](#prerequisites)
4. [Setup](#setup)
5. [Configuration](#configuration)
6. [Running the Agent](#running-the-agent)
7. [Chat Commands](#chat-commands)
8. [Automated Workflow](#automated-workflow)
9. [Agent Roles](#agent-roles)
10. [MCP Server & Protocol](#mcp-server--protocol)
11. [Extending the System](#extending-the-system)
12. [Troubleshooting](#troubleshooting)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Terminal (Rich Chat UI)                                        │
│   User types: "search milk"                                     │
│         │                                                       │
│         ▼                                                       │
│  Orchestrator Agent                                             │
│   • Classifies intent (LLM call)                               │
│   • Routes to specialist sub-agent                             │
│         │                                                       │
│   ┌─────┴──────────────────────────────────┐                   │
│   │  AuthAgent  CartAgent  SearchAgent  CheckoutAgent          │
│   │    (each runs a ReAct-style LLM loop)                      │
│   └─────┬──────────────────────────────────┘                   │
│         │  tool calls (JSON-RPC 2.0)                            │
│         ▼                                                       │
│  MCP Server  (HTTP on localhost:8765)                           │
│   • Tool registry: navigate, click, fill, screenshot, …        │
│         │                                                       │
│         ▼                                                       │
│  BrowserHelper (Playwright / Chromium)                         │
│   • Controls a real (or headless) Chromium browser             │
│   • Navigates walmart.com, interacts with DOM                  │
└─────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Single shared browser context** | All agents reuse one Chromium instance so login cookies persist across agents. |
| **HTTP JSON-RPC MCP transport** | Simpler than stdio for multi-agent use; each agent just POSTs to `localhost:8765/mcp`. |
| **LLM decides which selectors to use** | Walmart's DOM changes frequently; letting the LLM choose selectors from `get_page_info` output makes the system resilient. |
| **ReAct loop per agent** | Reason → Act → Observe. Each agent loops until the LLM says "done" or hits a safety limit. |
| **Orchestrator intent classification** | Keeps agent prompts small and focused; each agent only knows its own job. |

---

## Project Structure

```
shopping-agent/
├── main.py                     # Entry point (chat mode or workflow mode)
├── requirements.txt
├── pyproject.toml
├── .env.example                # Copy to .env and fill in credentials
│
├── config/
│   ├── __init__.py
│   └── settings.py             # All settings loaded from environment
│
├── mcp_server/
│   ├── __init__.py
│   ├── server.py               # MCP HTTP server with Playwright tools
│   └── client.py               # Thin JSON-RPC client used by agents
│
├── browser/
│   ├── __init__.py
│   └── playwright_helper.py    # Low-level Playwright wrapper
│
├── agents/
│   ├── __init__.py
│   ├── base_agent.py           # Abstract base: LLM loop + tool calling
│   ├── orchestrator.py         # Routes user messages → sub-agents
│   ├── auth_agent.py           # Step 1–3: Login + home page verification
│   ├── cart_agent.py           # Step 4–6: Navigate cart, remove items, go home
│   ├── search_agent.py         # Step 7–10: Search, select product, add to cart
│   └── checkout_agent.py       # Step 11–12: Cart → Continue to Checkout
│
├── ui/
│   ├── __init__.py
│   └── chat_interface.py       # Rich terminal chat UI
│
└── workflows/
    ├── __init__.py
    └── walmart_shopping.py     # End-to-end automated 12-step workflow
```

---

## Prerequisites

- **Python 3.11+**
- **Google Chrome** or Chromium (Playwright will install it automatically)
- An **OpenAI API key** (GPT-4o recommended) *or* **Anthropic API key**
- A **Walmart.com account** with valid email + password

---

## Setup

```bash
# 1. Clone the repository
git clone <repo-url>
cd UI-shop-agent/shopping-agent

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Install Playwright's Chromium browser
playwright install chromium

# 5. Configure credentials
cp .env.example .env
# Edit .env with your credentials (see Configuration section)
```

---

## Configuration

Edit `shopping-agent/.env`:

```ini
# LLM Provider: "openai" or "anthropic"
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
OPENAI_API_KEY=sk-...

# Walmart account
WALMART_EMAIL=your-email@example.com
WALMART_PASSWORD=your-password

# Browser: set to "true" for headless (CI/server) mode
BROWSER_HEADLESS=false
BROWSER_SLOW_MO=300          # ms delay between actions (reduce for speed)
BROWSER_TIMEOUT=30000        # ms timeout for element waits

# MCP server
MCP_SERVER_HOST=localhost
MCP_SERVER_PORT=8765
```

---

## Running the Agent

### Interactive Chat Mode

```bash
cd shopping-agent
python main.py
```

You'll see a Rich terminal UI. Type commands like:

```
You: login
You: clear cart
You: search milk
You: checkout
You: workflow
```

### Automated Workflow Mode

Runs all 12 steps automatically and exits:

```bash
python main.py --workflow
```

### Headless Mode (no browser window)

```bash
python main.py --workflow --headless
# or
BROWSER_HEADLESS=true python main.py
```

### Skip credential validation (for testing)

```bash
python main.py --no-validate
```

---

## Chat Commands

| Command | Description |
|---------|-------------|
| `login` | Log in to Walmart using credentials from `.env` |
| `clear cart` | Navigate to cart and remove all items |
| `search <term>` | Search for a product and add a delivery-eligible result to cart |
| `checkout` | Go to cart and click "Continue to Checkout" |
| `workflow` | Run the complete automated 12-step workflow |
| `status` | Show current browser URL and page title |
| `help` | Show available commands |
| `exit` / `quit` | Exit the chat |

Free-form questions (e.g. "how do I find organic milk?") are answered
by the LLM in general assistant mode without browser interaction.

---

## Automated Workflow

The 12-step workflow mirrors the problem statement exactly:

| Step | Agent | Action |
|------|-------|--------|
| 1 | AuthAgent | Navigate to walmart.com |
| 2 | AuthAgent | Log in with email + password |
| 3 | AuthAgent | Verify landing on home page |
| 4 | CartAgent | Navigate to cart |
| 5 | CartAgent | Remove all items |
| 6 | CartAgent | Return to home page |
| 7 | SearchAgent | Search for "milk" |
| 8 | SearchAgent | Select a delivery-eligible result |
| 9 | SearchAgent | Open product detail page |
| 10 | SearchAgent | Add item to cart |
| 11 | CheckoutAgent | Navigate to cart |
| 12 | CheckoutAgent | Click "Continue to Checkout" |

---

## Agent Roles

### Orchestrator (`agents/orchestrator.py`)
- Receives all user messages.
- Makes a lightweight LLM call to classify the intent (login, search, checkout, etc.).
- Delegates to the appropriate sub-agent.
- Yields progress strings to the chat UI as work proceeds.

### AuthAgent (`agents/auth_agent.py`)
- System prompt is pre-loaded with Walmart credentials.
- Navigates the login flow, handles multi-step auth (email → continue → password → sign in).
- Reports success or any blocking issues (CAPTCHA, phone verification).

### CartAgent (`agents/cart_agent.py`)
- Navigates to `/cart`.
- Repeatedly finds and clicks "Remove" buttons until the cart count reaches zero.
- Also used to navigate to cart and click "Continue to Checkout" (via `add_item_and_checkout`).

### SearchAgent (`agents/search_agent.py`)
- Accepts a search query string.
- Types the query into Walmart's search bar.
- Scans results for delivery-eligible items (looks for "Delivery" / "Ships" badges).
- Clicks the product to open its detail page.
- Clicks "Add to cart" and waits for confirmation.

### CheckoutAgent (`agents/checkout_agent.py`)
- Navigates to `/cart`.
- Clicks "Continue to Checkout".
- Reports the page reached. Does **not** place an order.

---

## MCP Server & Protocol

The MCP server (`mcp_server/server.py`) runs an HTTP JSON-RPC 2.0 API.

### Available Tools

| Tool | Description |
|------|-------------|
| `navigate` | Navigate to a URL |
| `click_element` | Click a CSS selector |
| `fill_field` | Fill an input field |
| `type_text` | Type character-by-character (bot-safe) |
| `press_key` | Press a keyboard key |
| `wait_for_selector` | Wait for an element to appear |
| `is_visible` | Check if an element is visible |
| `get_element_text` | Get inner text of an element |
| `count_elements` | Count elements matching a selector |
| `get_page_info` | Get current URL, title, and content snippet |
| `screenshot` | Capture a screenshot (base-64 PNG) |
| `scroll_to_bottom` | Scroll to bottom of page |
| `evaluate_js` | Run arbitrary JavaScript |
| `query_all_texts` | Get text of all matching elements |

### JSON-RPC Format

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tool/call",
  "params": {
    "name": "navigate",
    "arguments": { "url": "https://www.walmart.com" }
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [{ "type": "text", "text": "Walmart.com - Shop Online" }]
  }
}
```

---

## Extending the System

### Adding a new agent

1. Create `agents/my_agent.py` inheriting from `BaseAgent`.
2. Define a focused `SYSTEM_PROMPT` with step-by-step instructions.
3. Implement `async def run(self, **kwargs) -> str`.
4. Register it in `agents/orchestrator.py` under a new intent.

### Adding a new browser tool

1. Add a method to `browser/playwright_helper.py`.
2. Register a new `Tool` in `mcp_server/server.py` inside `_register_tools()`.
3. The LLM agents automatically pick up the new tool on the next `tool/list` call.

### Switching LLM providers

Set `LLM_PROVIDER=anthropic` and `LLM_MODEL=claude-3-5-sonnet-20241022` in `.env`.
No code changes needed.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `BrowserError: Timeout navigating` | Slow internet or Walmart rate-limiting | Increase `BROWSER_TIMEOUT=60000` |
| `MCPClientError: Connection refused` | MCP server not yet started | Ensure `main.py` starts the server before clients |
| Agent loops forever | LLM confused by page layout | Check screenshots in `/tmp/shop_agent_screenshots/` |
| CAPTCHA detected | Walmart bot detection | Run with `BROWSER_HEADLESS=false` to solve manually |
| `Missing required environment variables` | `.env` not set up | Copy `.env.example` → `.env` and fill in values |
| `ModuleNotFoundError: playwright` | Dependencies not installed | `pip install -r requirements.txt && playwright install chromium` |

### Debug mode

```bash
LOG_LEVEL=DEBUG python main.py --workflow
```

Screenshots are auto-saved to `/tmp/shop_agent_screenshots/` for inspection.

---

## Notes on Bot Detection

Walmart employs bot-detection measures. The browser helper mitigates some of these:

- Uses a realistic `User-Agent` string.
- Sets `--disable-blink-features=AutomationControlled` Chrome flag.
- Types text character-by-character with random delays (`type_text` tool).
- Runs with a realistic viewport (1280×800).

If Walmart shows a CAPTCHA or an "unusual traffic" page, the agent will
report it and stop rather than proceeding silently with invalid state.
