"""
agent.py — Agentic AI core with OpenAI function calling.

The agent acts in two roles:
  1. Personal Shopper (Revenue Agent) — product recommendations with reasoning
  2. Customer Support Assistant (Operations Agent) — return policy evaluation

Hallucination prevention:
  - System prompt strictly instructs the model to only use data from tool calls
  - Never invent product IDs, order IDs, prices, or stock levels
  - Refuse gracefully when data is not found
"""

import json
import os
from openai import OpenAI
from tools import execute_tool

# ─── OpenAI Function Schemas ───────────────────────────────────────────────

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Search for dresses in inventory. Use this when a customer wants product recommendations. Use only 1-2 tags for best results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Style tags. ONLY use from this list: modest, evening, lace, bridal, cocktail, prom, sparkle, sleeve, fitted, flowy, minimal, quinceanera. Use 1-2 tags maximum for best results.",
                    },
                    "max_price": {
                        "type": "number",
                        "description": "Maximum price in dollars.",
                    },
                    "min_price": {
                        "type": "number",
                        "description": "Minimum price in dollars.",
                    },
                    "size": {
                        "type": "string",
                        "description": "Dress size. Must be one of: 2, 4, 6, 8, 10, 12, 14, 16. Only shows in-stock items.",
                    },
                    "is_sale": {
                        "type": "boolean",
                        "description": "Set true to show only sale items.",
                    },
                    "is_clearance": {
                        "type": "boolean",
                        "description": "Set true to show only clearance items.",
                    },
                    "vendor": {
                        "type": "string",
                        "description": "Filter by vendor name.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results to return. Default 5.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product",
            "description": "Get details of one product by ID (e.g. P0001). Use when customer asks about a specific product.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "string",
                        "description": "Product ID like P0001.",
                    },
                },
                "required": ["product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_order",
            "description": "Get details of one order by ID (e.g. O0001). Use when customer asks about an order.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "Order ID like O0001.",
                    },
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "evaluate_return",
            "description": "Check if an order can be returned. Use when customer asks about returning or exchanging an order.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "Order ID like O0043.",
                    },
                },
                "required": ["order_id"],
            },
        },
    },
]


# ─── System Prompt ─────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a retail fashion assistant. You help customers find dresses and handle returns.

TOOLS YOU HAVE:
- search_products: Find dresses by style, price, size, sale status
- get_product: Look up one product by ID
- get_order: Look up one order by ID
- evaluate_return: Check if an order is eligible for return

IMPORTANT RULES:
1. ALWAYS call a tool first. Never make up product or order information.
2. Only use data returned by tools. If a tool says "not found", tell the customer.
3. When searching, use only 1-2 tags from: modest, evening, lace, bridal, cocktail, prom, sparkle, sleeve, fitted, flowy, minimal, quinceanera
4. Do NOT use words like "gown" or "dress" as tags. Map them: "evening gown" = tag "evening", "cocktail dress" = tag "cocktail"
5. For returns, ALWAYS use the evaluate_return tool. Do not guess.

OUTPUT FORMAT — ALWAYS use bullet points:

For product recommendations:
• **[Product Title]** (ID)
  - Price: $X (On Sale / Regular)
  - Size [X]: [Y] units in stock
  - Style: [tags]
  - Bestseller Score: X/100
  - Why: [one line explaining why this fits the request]

For return evaluations:
• **Order:** [order ID]
• **Product:** [title]
• **Decision:** Eligible / Not Eligible
• **Reason:** [clear explanation]
• **Policy Applied:** [which rule]

Keep responses SHORT and CRISP. No long paragraphs."""


# ─── Agent Class ───────────────────────────────────────────────────────────

class RetailAgent:
    """Agentic loop: user message → LLM → tool calls → LLM → final answer."""

    def __init__(self, model: str | None = None):
        ollama_base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        self.client = OpenAI(
            base_url=ollama_base,
            api_key="ollama",  # Ollama doesn't need a real key but the client requires one
        )
        self.model = model or os.getenv("OLLAMA_MODEL", "llama3.2")
        self.messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

    def chat(self, user_message: str) -> str:
        """Send a user message and return the agent's final response.

        The agent may make multiple tool calls before producing a final answer.
        """
        self.messages.append({"role": "user", "content": user_message})

        # Agentic loop — keep going until the model produces a text response
        max_iterations = 10  # safety limit
        for _ in range(max_iterations):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
            )

            message = response.choices[0].message

            # If no tool calls, we have the final answer
            if not message.tool_calls:
                assistant_content = message.content or ""
                self.messages.append({"role": "assistant", "content": assistant_content})
                return assistant_content

            # Process tool calls
            self.messages.append(message)  # append the assistant message with tool_calls

            for tool_call in message.tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments)

                print(f"  🔧 Calling tool: {fn_name}({json.dumps(fn_args, indent=2)})")

                result = execute_tool(fn_name, fn_args)

                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })

        # Safety fallback
        return "I'm sorry, I couldn't complete your request. Please try rephrasing your question."

    def reset(self):
        """Reset conversation history (keep system prompt)."""
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
