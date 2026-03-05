# Retail AI Assistant — Architecture Document

## 1. System Overview

The Retail AI Assistant is a **CLI-based agentic AI system** that combines two retail roles into a single intelligent agent:

- **Personal Shopper** — recommends products with multi-constraint reasoning
- **Customer Support Assistant** — evaluates return/exchange eligibility using policy rules

The agent uses **OpenAI function calling** to dynamically select and invoke structured tools, ensuring all responses are grounded in real data.

```
┌──────────────────────────────────────────────────────────┐
│                      CLI Interface                       │
│                      (main.py)                           │
└──────────────────────┬───────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────┐
│                    Retail Agent                           │
│                    (agent.py)                             │
│                                                          │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  System Prompt: dual-role behavior + anti-          │ │
│  │  hallucination rules                                │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌──────────────┐    ┌──────────────┐                    │
│  │ User Message  │───▶│  Ollama API  │──┐                │
│  └──────────────┘    │  (llama 3.2)│  │                │
│         ▲            └──────────────┘  │ tool_calls      │
│         │                              ▼                 │
│         │  final     ┌──────────────────────────┐        │
│         │  answer    │    Tool Executor          │        │
│         └────────────│    (tools.py)             │        │
│                      └──────────────────────────┘        │
└──────────────────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────┐
│                    Data Layer                             │
│                  (data_loader.py)                         │
│                                                          │
│  product_inventory.csv │ orders.csv │ policy.txt         │
└──────────────────────────────────────────────────────────┘
```

## 2. Why This Architecture

### Tool Calling Over Hardcoded Logic

Instead of using if/else branches to detect user intent, the agent uses **OpenAI's native function calling**. The LLM receives structured tool schemas and decides which tools to invoke based on semantic understanding of the user's message. This means:

- The agent handles novel phrasings without brittle keyword matching
- Multi-step reasoning is natural (e.g., search → filter → explain)
- New tools can be added by simply defining a new schema + function

### Separation of Concerns

| Layer | Responsibility |
|-------|---------------|
| `main.py` | CLI input/output loop |
| `agent.py` | LLM orchestration, tool schema definitions, system prompt |
| `tools.py` | Pure data operations — filtering, policy evaluation |
| `data_loader.py` | File I/O, parsing, caching |

The LLM never touches raw files. It only sees structured JSON results from tools.

## 3. Hallucination Prevention

Hallucination is minimized through a **defense-in-depth** approach:

1. **System prompt constraints** — The agent is explicitly instructed to never invent data and to only reference tool results
2. **Structured tool outputs** — Tools return JSON with explicit `found: false` or `error` fields. The model cannot silently fabricate data
3. **Explicit refusal** — When `get_order` or `get_product` returns "not found", the system prompt instructs the model to refuse rather than guess
4. **No training data leakage** — Product/order data is entirely synthetic and loaded at runtime; the LLM has no prior knowledge of it
5. **Grounded reasoning** — The `evaluate_return` tool applies policy rules deterministically in code, not via the LLM. The LLM only explains the result

## 4. Tool Selection Mechanism

The agent exposes 4 tools to the LLM via function schemas:

| Tool | When Selected |
|------|--------------|
| `search_products(filters)` | User asks for recommendations with any combination of tags, price, size, sale preference |
| `get_product(product_id)` | User asks about a specific product by ID |
| `get_order(order_id)` | User asks about a specific order's details |
| `evaluate_return(order_id)` | User asks about returning or exchanging an order |

The LLM selects tools based on its semantic understanding of the user query. It may chain multiple tools (e.g., `search_products` → `get_product` for more detail). The **agentic loop** in `agent.py` continues processing tool calls until the LLM produces a final text response.

## 5. Demo Examples

### Shopping Scenario 1
**Input:** "I need a modest evening gown under $300 in size 8. I prefer something on sale."
**Expected behavior:** Agent calls `search_products(tags=["modest","evening"], max_price=300, size="8", is_sale=true)`, receives filtered results sorted by bestseller_score, and explains why each recommendation fits.

### Shopping Scenario 2
**Input:** "Show me sparkle bridal dresses in size 4, any price range"
**Expected behavior:** Agent searches with `tags=["sparkle","bridal"], size="4"` and presents results with reasoning.

### Support Scenario 1
**Input:** "Order O0044 — I bought this dress recently. Can I return it?"
**Expected behavior:** Agent calls `evaluate_return("O0044")` which checks P0035 (Aurelia Couture, sale item) → applies vendor exception (exchange only) and sale window.

### Support Scenario 2
**Input:** "Order O0049 — Can I return this? It was a clearance purchase."
**Expected behavior:** Agent calls `evaluate_return("O0049")` which checks P0033 (clearance=True) → refuses (final sale).

### Edge Case — Invalid Order
**Input:** "Order O9999 — I want to return this"
**Expected behavior:** Agent calls `evaluate_return("O9999")` → order not found → refuses clearly without guessing.
