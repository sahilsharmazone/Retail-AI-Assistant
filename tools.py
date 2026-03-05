"""
tools.py — Structured tool functions for the Retail AI Assistant.

These tools are called by the LLM agent via function calling.
They never hallucinate — they return real data or explicit "not found" errors.
"""

import json
from datetime import datetime, timedelta
from data_loader import load_products, load_orders, load_policy


# ─── Helper ────────────────────────────────────────────────────────────────

def _product_to_summary(product: dict) -> dict:
    """Return a concise summary of a product for search results."""
    return {
        "product_id": product["product_id"],
        "title": product["title"],
        "vendor": product["vendor"],
        "price": product["price"],
        "compare_at_price": product["compare_at_price"],
        "tags": product["tags"],
        "sizes_available": product["sizes_available"],
        "is_sale": product["is_sale"],
        "is_clearance": product["is_clearance"],
        "bestseller_score": product["bestseller_score"],
    }


# ─── Tool 1: search_products ───────────────────────────────────────────────

def _run_search(
    products: list[dict],
    tags: list[str] | None = None,
    max_price: float | None = None,
    min_price: float | None = None,
    size: str | None = None,
    is_sale: bool | None = None,
    is_clearance: bool | None = None,
    vendor: str | None = None,
    limit: int = 5,
) -> list[dict]:
    """Internal search — returns list of (product, tag_match_count) tuples."""
    results = []

    for p in products:
        tag_matches = 0

        # Tag filter — match ANY tag, count how many match
        if tags:
            product_tags_lower = [t.lower() for t in p["tags"]]
            tag_matches = sum(1 for t in tags if t.lower() in product_tags_lower)
            if tag_matches == 0:
                continue

        # Price filters
        if max_price is not None and p["price"] > max_price:
            continue
        if min_price is not None and p["price"] < min_price:
            continue

        # Size filter — must be available AND in stock
        if size is not None:
            size_str = str(size)
            if size_str not in p["sizes_available"]:
                continue
            stock = p["stock_per_size"].get(size_str, 0)
            if stock <= 0:
                continue

        # Sale filter
        if is_sale is not None and p["is_sale"] != is_sale:
            continue

        # Clearance filter
        if is_clearance is not None and p["is_clearance"] != is_clearance:
            continue

        # Vendor filter
        if vendor is not None and vendor.lower() not in p["vendor"].lower():
            continue

        results.append((p, tag_matches))

    # Sort: more tag matches first, then by bestseller_score
    results.sort(key=lambda x: (x[1], x[0]["bestseller_score"]), reverse=True)

    return results[:limit]


def search_products(
    tags: list[str] | None = None,
    max_price: float | None = None,
    min_price: float | None = None,
    size: str | None = None,
    is_sale: bool | None = None,
    is_clearance: bool | None = None,
    vendor: str | None = None,
    limit: int = 5,
) -> str:
    """Search products with filters. Tags use ANY-match (more matches rank higher).

    If no results found with all filters, automatically relaxes sale/clearance
    filters and retries.
    """
    products = load_products()
    relaxed_note = None

    results = _run_search(products, tags, max_price, min_price, size, is_sale, is_clearance, vendor, limit)

    # Auto-relax: if no results and sale/clearance was set, retry without it
    if not results and (is_sale is not None or is_clearance is not None):
        results = _run_search(products, tags, max_price, min_price, size, None, None, vendor, limit)
        if results:
            relaxed_note = "No exact matches with sale/clearance filter — showing best alternatives."

    if not results:
        return json.dumps({"count": 0, "products": [], "message": "No products match the given filters. Try broader criteria."})

    summaries = []
    for p, tag_count in results:
        s = _product_to_summary(p)
        s["tags_matched"] = tag_count
        if size is not None:
            s["stock_for_requested_size"] = p["stock_per_size"].get(str(size), 0)
        summaries.append(s)

    output = {"count": len(summaries), "products": summaries}
    if relaxed_note:
        output["note"] = relaxed_note

    return json.dumps(output)


# ─── Tool 2: get_product ───────────────────────────────────────────────────

def get_product(product_id: str) -> str:
    """Get full details of a single product by ID. Returns JSON string."""
    products = load_products()
    product_id = product_id.strip().upper()

    for p in products:
        if p["product_id"] == product_id:
            return json.dumps({"found": True, "product": p})

    return json.dumps({"found": False, "error": f"Product '{product_id}' not found in inventory."})


# ─── Tool 3: get_order ─────────────────────────────────────────────────────

def get_order(order_id: str) -> str:
    """Get full details of a single order by ID. Returns JSON string."""
    orders = load_orders()
    order_id = order_id.strip().upper()

    for o in orders:
        if o["order_id"] == order_id:
            return json.dumps({"found": True, "order": o})

    return json.dumps({"found": False, "error": f"Order '{order_id}' not found in records."})


# ─── Tool 4: evaluate_return ───────────────────────────────────────────────

def evaluate_return(order_id: str) -> str:
    """Evaluate whether a return is eligible for the given order.

    Steps:
      1. Fetch the order (fail if not found)
      2. Fetch the product (fail if not found)
      3. Apply return policy rules:
         - Clearance → final sale, no return
         - Sale → 7-day window, store credit only
         - Normal → 14-day window, full refund
      4. Apply vendor exceptions:
         - Aurelia Couture → exchanges only, no refunds
         - Nocturne → extended 21-day window
      5. Check date eligibility
      6. Check exchange availability (if applicable)

    Returns a structured JSON verdict.
    """
    # Step 1: Fetch order
    order_data = json.loads(get_order(order_id))
    if not order_data["found"]:
        return json.dumps({
            "eligible": False,
            "reason": order_data["error"],
            "policy_applied": "N/A",
            "exchange_possible": False,
        })

    order = order_data["order"]

    # Step 2: Fetch product
    product_data = json.loads(get_product(order["product_id"]))
    if not product_data["found"]:
        return json.dumps({
            "eligible": False,
            "reason": f"Product {order['product_id']} linked to this order no longer exists in inventory.",
            "policy_applied": "N/A",
            "exchange_possible": False,
        })

    product = product_data["product"]
    vendor = product["vendor"]
    order_date = datetime.strptime(order["order_date"], "%Y-%m-%d")
    today = datetime.now()
    days_since_order = (today - order_date).days

    # Step 3: Apply base policy
    if product["is_clearance"]:
        return json.dumps({
            "eligible": False,
            "reason": "This is a clearance item. Clearance items are final sale — not eligible for return or exchange.",
            "policy_applied": "Clearance Policy — Final Sale",
            "exchange_possible": False,
            "order": order,
            "product_title": product["title"],
            "vendor": vendor,
            "days_since_order": days_since_order,
        })

    # Determine return window and refund type
    if product["is_sale"]:
        window_days = 7
        refund_type = "store credit only"
        policy_name = "Sale Item Policy — 7-day return window, store credit only"
    else:
        window_days = 14
        refund_type = "full refund"
        policy_name = "Normal Return Policy — 14-day return window, full refund"

    # Step 4: Vendor exceptions
    vendor_note = None
    if vendor == "Aurelia Couture":
        refund_type = "exchange only (no refunds per Aurelia Couture policy)"
        vendor_note = "Aurelia Couture vendor exception: exchanges only, no refunds."
        policy_name += " + Aurelia Couture Vendor Exception"
    elif vendor == "Nocturne":
        window_days = 21
        vendor_note = "Nocturne vendor exception: extended 21-day return window."
        policy_name += " + Nocturne Vendor Exception (21-day window)"

    # Step 5: Date check
    if days_since_order > window_days:
        eligible = False
        reason = (
            f"Return window has expired. The order was placed {days_since_order} days ago, "
            f"but the return window is {window_days} days."
        )
    else:
        eligible = True
        remaining = window_days - days_since_order
        reason = (
            f"Return is eligible. The order was placed {days_since_order} days ago, "
            f"within the {window_days}-day return window ({remaining} days remaining). "
            f"Refund type: {refund_type}."
        )

    # Step 6: Check exchange possibility
    size = order["size"]
    stock = product["stock_per_size"].get(str(size), 0)
    exchange_possible = stock > 0
    exchange_note = (
        f"Exchange for size {size} is {'available' if exchange_possible else 'NOT available'} "
        f"(current stock: {stock})."
    )

    result = {
        "eligible": eligible,
        "reason": reason,
        "policy_applied": policy_name,
        "refund_type": refund_type,
        "exchange_possible": exchange_possible,
        "exchange_note": exchange_note,
        "order": order,
        "product_title": product["title"],
        "vendor": vendor,
        "days_since_order": days_since_order,
        "return_window_days": window_days,
    }

    if vendor_note:
        result["vendor_exception"] = vendor_note

    return json.dumps(result)


# ─── Tool Dispatch Map ─────────────────────────────────────────────────────

TOOL_DISPATCH = {
    "search_products": search_products,
    "get_product": get_product,
    "get_order": get_order,
    "evaluate_return": evaluate_return,
}


def execute_tool(name: str, arguments: dict) -> str:
    """Execute a tool by name with the given arguments. Returns JSON string."""
    if name not in TOOL_DISPATCH:
        return json.dumps({"error": f"Unknown tool: {name}"})

    fn = TOOL_DISPATCH[name]
    try:
        return fn(**arguments)
    except Exception as e:
        return json.dumps({"error": f"Tool '{name}' failed: {str(e)}"})
