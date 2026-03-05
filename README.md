# 🛍️ Retail AI Assistant

A CLI-based agentic AI system that acts as a **Personal Shopper** and **Customer Support Assistant** using LLM tool calling.

Built with **Ollama (llama3.2)** — runs fully local, no API keys needed.

---

## Features

- **Smart Product Search** — filter by style, price, size, sale status
- **Return Policy Engine** — evaluates returns with rule-based reasoning
- **Tool Calling** — LLM dynamically selects tools, no hardcoded responses
- **Hallucination Prevention** — only uses real data from tools, refuses on invalid IDs

## Tech Stack

| Component | Technology |
|-----------|-----------|
| LLM | Ollama (llama3.2) |
| Tool Calling | OpenAI-compatible function calling |
| Language | Python 3.10+ |
| Data | CSV + Text files |

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/sahilsharmazone/Retail-AI-Assistant.git
cd Retail-AI-Assistant

# 2. Install dependencies
pip install -r requirements.txt

# 3. Make sure Ollama is running with llama3.2
ollama pull llama3.2

# 4. Run
python main.py
```

---

## Sample Queries

### 🛒 Shopping (Personal Shopper)
```
I need a modest dress under $200 in size 8
Show me sparkle bridal dresses in size 4
What's the cheapest cocktail dress in size 6?
```

### 📦 Returns (Customer Support)
```
Can I return order O0049?
Order O0044 — can I get a refund?
I want to return order O9999
```

---

## Project Structure

```
├── main.py              # CLI entry point
├── agent.py             # LLM agent with tool calling loop
├── tools.py             # 4 structured tools
├── data_loader.py       # CSV/text parser with caching
├── data/
│   ├── product_inventory.csv   # 100 products
│   ├── orders.csv              # 100 orders
│   └── policy.txt              # Return policy rules
├── ARCHITECTURE.md      # Design document
└── requirements.txt
```

## Tools

| Tool | Purpose |
|------|---------|
| `search_products(filters)` | Search inventory with tags, price, size, sale filters |
| `get_product(product_id)` | Get details of a specific product |
| `get_order(order_id)` | Get details of a specific order |
| `evaluate_return(order_id)` | Check return eligibility with full policy logic |

## Return Policy

| Type | Rule |
|------|------|
| Normal | 14-day return, full refund |
| Sale | 7-day return, store credit only |
| Clearance | Final sale, no returns |
| Aurelia Couture | Exchanges only, no refunds |
| Nocturne | Extended 21-day window |

---

## Architecture

```
User Query → LLM (llama3.2) → Tool Calls → Data Layer → LLM → Response
```

The agent uses an **agentic loop** — the LLM decides which tools to call, processes the results, and generates a final answer grounded in real data. See [ARCHITECTURE.md](ARCHITECTURE.md) for details.

---

## License

MIT
