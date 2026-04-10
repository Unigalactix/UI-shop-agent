# Screenshots

Place your screenshot images in this directory.

**Recommended filenames:**

| Filename | What to capture |
|---|---|
| `01_terminal_banner.png` | Terminal startup banner with the cyan header |
| `02_login_prompt.png` | Agent logging in — typing email & password |
| `03_walmart_home.png` | Walmart homepage after successful login |
| `04_cart_empty.png` | Cart page after all items have been removed |
| `05_search_results.png` | Search results page for "milk" |
| `06_product_detail.png` | Product detail page with "Add to Cart" button |
| `07_cart_with_item.png` | Cart showing the added milk product |
| `08_checkout_page.png` | Checkout page reached after clicking "Continue to Checkout" |
| `09_workflow_progress.png` | Terminal showing the Rich progress spinner during the 12-step workflow |
| `10_workflow_complete.png` | Terminal showing "Workflow complete! 🎉" |

## How to capture screenshots

Run the agent in non-headless mode and use your OS screenshot tool, **or** call the built-in
`screenshot` MCP tool from the terminal UI:

```
You: screenshot
```

Screenshots are also auto-saved to `/tmp/shop_agent_screenshots/` whenever the agent encounters an
unexpected state.
