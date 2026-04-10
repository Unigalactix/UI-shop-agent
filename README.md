# 🛒 UI Shop Agent — Visual Walkthrough

A **chat-based, multi-agent Walmart shopping automation system** powered by Playwright, MCP, and GPT-4o / Claude.

> 📖 For full technical documentation see [`shopping-agent/README.md`](shopping-agent/README.md).

---

## Table of Contents

1. [What It Does](#what-it-does)
2. [Terminal UI](#terminal-ui)
3. [Browser Actions — Step-by-Step](#browser-actions--step-by-step)
   - [Step 1 — Start the Agent](#step-1--start-the-agent)
   - [Step 2 — Login to Walmart](#step-2--login-to-walmart)
   - [Step 3 — Walmart Home Page Verified](#step-3--walmart-home-page-verified)
   - [Step 4 — Navigate to Cart](#step-4--navigate-to-cart)
   - [Step 5 — Clear the Cart](#step-5--clear-the-cart)
   - [Step 6 — Search for a Product](#step-6--search-for-a-product)
   - [Step 7 — Select a Delivery-Eligible Product](#step-7--select-a-delivery-eligible-product)
   - [Step 8 — Add to Cart](#step-8--add-to-cart)
   - [Step 9 — Proceed to Checkout](#step-9--proceed-to-checkout)
4. [Running the Full Automated Workflow](#running-the-full-automated-workflow)
5. [Chat Command Reference](#chat-command-reference)
6. [Adding Your Own Screenshots](#adding-your-own-screenshots)

---

## What It Does

The agent opens a real Chromium browser, navigates to Walmart.com, logs in, searches for
products, and walks through checkout — all driven by natural-language chat commands or a
single `--workflow` flag.

```
User types "search milk"
      │
      ▼
Orchestrator (GPT-4o) classifies intent
      │
      ▼
SearchAgent ──► MCP Server (JSON-RPC) ──► Playwright / Chromium ──► walmart.com
```

---

## Terminal UI

When you run `python main.py` you are greeted by a Rich-powered terminal interface:

```
╔══════════════════════════════════════════════════════════╗
║        🛒  Walmart UI Shop Agent  ·  MCP + Playwright   ║
╚══════════════════════════════════════════════════════════╝

Type help for available commands.   Type exit to quit.

Browser ready — current page: Walmart.com | Save Money. Live Better.

You: _
```

> 📸 **Screenshot:** `docs/screenshots/01_terminal_banner.png`

The chat layout renders user messages in **blue**, agent responses in **green**, and errors in
**red**.  A divider rule separates each turn.

---

## Browser Actions — Step-by-Step

### Step 1 — Start the Agent

```bash
cd shopping-agent
python main.py
```

The agent:
1. Starts the **MCP HTTP server** on `localhost:8765`.
2. Launches a **Chromium browser** window (visible by default).
3. Shows the terminal chat banner above.

---

### Step 2 — Login to Walmart

```
You: login
```

**What happens in the browser:**

| # | Browser action | MCP tool used |
|---|----------------|---------------|
| 1 | Navigate to `https://www.walmart.com` | `navigate` |
| 2 | Click **Sign In** button | `click_element` |
| 3 | Fill in email field | `fill_field` |
| 4 | Click **Continue** | `click_element` |
| 5 | Fill in password field | `type_text` (character-by-character) |
| 6 | Click **Sign In** | `click_element` |
| 7 | Wait for the account menu to appear | `wait_for_selector` |

**Terminal output:**

```
You:   login
Agent: 🔐 Logging in to Walmart…
Agent: ✅ Logged in successfully. Home page verified.
──────────────────────────────────────────────────
```

> 📸 **Screenshots:**
> - `docs/screenshots/02_login_prompt.png` — browser showing the login modal
> - `docs/screenshots/03_walmart_home.png` — Walmart homepage after login

---

### Step 3 — Walmart Home Page Verified

The **AuthAgent** calls `get_page_info` after login and confirms the URL contains
`walmart.com` and the page title includes "Walmart".  If a CAPTCHA or phone-verification
prompt is detected the agent reports it and stops.

---

### Step 4 — Navigate to Cart

```
You: clear cart
```

**What happens in the browser:**

| # | Browser action | MCP tool used |
|---|----------------|---------------|
| 1 | Navigate to `https://www.walmart.com/cart` | `navigate` |
| 2 | Count cart item rows | `count_elements` |
| 3 | Click first **Remove** button | `click_element` |
| 4 | Repeat until cart count = 0 | loop |

> 📸 **Screenshot:** `docs/screenshots/04_cart_empty.png` — cart showing "Your cart is empty"

---

### Step 5 — Clear the Cart

The **CartAgent** uses a ReAct loop:

```
Reason: "I see 3 items. I need to remove them."
Act:    click_element(".remove-btn")
Observe: count_elements → 2
Reason: "Still 2 items."
Act:    click_element(".remove-btn")
… (repeats until 0)
```

**Terminal output:**

```
Agent: 🛒 Navigating to cart and clearing items…
Agent: ✅ Cart cleared. Returned to home page.
──────────────────────────────────────────────────
```

---

### Step 6 — Search for a Product

```
You: search milk
```

**What happens in the browser:**

| # | Browser action | MCP tool used |
|---|----------------|---------------|
| 1 | Find the search input bar | `wait_for_selector` |
| 2 | Type "milk" into the search bar | `fill_field` |
| 3 | Press **Enter** | `press_key` |
| 4 | Wait for results to load | `wait_for_selector` |
| 5 | Scan all result titles for "Delivery" badge | `query_all_texts` |

> 📸 **Screenshot:** `docs/screenshots/05_search_results.png` — Walmart search results for "milk"

**Terminal output:**

```
You:   search milk
Agent: 🔍 Searching Walmart for 'milk'…
Agent: ✅ Added Great Value Whole Milk, 1 Gallon ($3.48) to cart.
──────────────────────────────────────────────────
```

---

### Step 7 — Select a Delivery-Eligible Product

The **SearchAgent** scans the results list for items that include a **"Delivery"** or
**"Ships"** badge (indicating home-delivery availability), then clicks the first matching
product title to open its detail page.

> 📸 **Screenshot:** `docs/screenshots/06_product_detail.png` — product detail page

---

### Step 8 — Add to Cart

**What happens in the browser:**

| # | Browser action | MCP tool used |
|---|----------------|---------------|
| 1 | Locate the **Add to Cart** button on the PDP | `wait_for_selector` |
| 2 | Click **Add to Cart** | `click_element` |
| 3 | Wait for the cart-count badge to update | `wait_for_selector` |
| 4 | Confirm cart count increased | `get_element_text` |

> 📸 **Screenshot:** `docs/screenshots/07_cart_with_item.png` — cart showing the added item

---

### Step 9 — Proceed to Checkout

```
You: checkout
```

**What happens in the browser:**

| # | Browser action | MCP tool used |
|---|----------------|---------------|
| 1 | Navigate to `https://www.walmart.com/cart` | `navigate` |
| 2 | Locate **Continue to Checkout** button | `wait_for_selector` |
| 3 | Click **Continue to Checkout** | `click_element` |
| 4 | Report the page reached | `get_page_info` |

> ⚠️ The agent **stops here** and does not place an order.

**Terminal output:**

```
You:   checkout
Agent: 💳 Proceeding to checkout…
Agent: ✅ Reached checkout page: https://www.walmart.com/checkout/…
──────────────────────────────────────────────────
```

> 📸 **Screenshots:**
> - `docs/screenshots/08_checkout_page.png` — Walmart checkout page

---

## Running the Full Automated Workflow

Run all 12 steps in one shot:

```bash
python main.py --workflow
```

Or type `workflow` in the chat UI.

**Terminal output (Rich progress spinner):**

```
 ⠸ Steps 1–3: Login & verify home page             [0:00:08]
 ✅ Steps 1–3: Login & verify home page             [0:00:08]
    Logged in. Home page verified.
 ⠴ Steps 4–6: Clear cart & return home              [0:00:04]
 ✅ Steps 4–6: Clear cart & return home              [0:00:04]
    Cart cleared. Back on home page.
 ⠦ Steps 7–10: Search milk, pick delivery item…    [0:00:15]
 ✅ Steps 7–10: Search milk, pick delivery item…    [0:00:15]
    Added Great Value Whole Milk ($3.48) to cart.
 ⠧ Steps 11–12: Cart → Continue to Checkout        [0:00:06]
 ✅ Steps 11–12: Cart → Continue to Checkout        [0:00:06]
    Reached checkout page.

────────────── Workflow complete! 🎉 ──────────────
```

> 📸 **Screenshots:**
> - `docs/screenshots/09_workflow_progress.png` — terminal showing Rich spinner
> - `docs/screenshots/10_workflow_complete.png` — terminal showing "Workflow complete! 🎉"

---

## Chat Command Reference

| Command | What it does |
|---------|-------------|
| `login` | Log in to Walmart with credentials from `.env` |
| `clear cart` | Navigate to `/cart` and remove all items |
| `search <term>` | Search, pick a delivery-eligible product, and add it to cart |
| `checkout` | Go to cart and click **Continue to Checkout** |
| `workflow` | Run the complete 12-step automated workflow |
| `status` | Print current browser URL and page title |
| `help` | Show available commands |
| `exit` / `quit` | Exit the chat |

Free-form questions (e.g. *"what is MCP?"*) are answered by the LLM without touching the
browser.

---

## Adding Your Own Screenshots

1. Run the agent with the browser visible (`BROWSER_HEADLESS=false` in `.env`).
2. Capture screenshots with your OS tool **or** call the `screenshot` command in the chat.
3. Place image files in [`docs/screenshots/`](docs/screenshots/) using the naming convention
   described in [`docs/screenshots/README.md`](docs/screenshots/README.md).
4. Update the `![alt](docs/screenshots/<file>.png)` links above to display them inline.

> Screenshots taken during agent runs are also auto-saved to  
> `/tmp/shop_agent_screenshots/` for quick inspection.

---

*For full setup instructions, architecture details, and the MCP tool reference, see
[`shopping-agent/README.md`](shopping-agent/README.md).*
