"""
data_loader.py — Loads product inventory, orders, and return policy from disk.

All data is cached at module level after first load for performance.
"""

import csv
import ast
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# ─── Module-level caches ────────────────────────────────────────────────────
_products_cache: list[dict] | None = None
_orders_cache: list[dict] | None = None
_policy_cache: str | None = None


def load_products() -> list[dict]:
    """Load product_inventory.csv and return a list of product dicts.

    Parses:
      - price / compare_at_price → float
      - tags → list[str]
      - sizes_available → list[str]
      - stock_per_size → dict[str, int]
      - is_sale / is_clearance → bool
      - bestseller_score → int
    """
    global _products_cache
    if _products_cache is not None:
        return _products_cache

    products = []
    path = os.path.join(DATA_DIR, "product_inventory.csv")
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            product = {
                "product_id": row["product_id"],
                "title": row["title"],
                "vendor": row["vendor"],
                "price": float(row["price"]),
                "compare_at_price": float(row["compare_at_price"]),
                "tags": [t.strip() for t in row["tags"].split(",")],
                "sizes_available": row["sizes_available"].split("|"),
                "stock_per_size": ast.literal_eval(row["stock_per_size"]),
                "is_sale": row["is_sale"].strip() == "True",
                "is_clearance": row["is_clearance"].strip() == "True",
                "bestseller_score": int(row["bestseller_score"]),
            }
            products.append(product)

    _products_cache = products
    return _products_cache


def load_orders() -> list[dict]:
    """Load orders.csv and return a list of order dicts.

    Parses:
      - price_paid → float
    """
    global _orders_cache
    if _orders_cache is not None:
        return _orders_cache

    orders = []
    path = os.path.join(DATA_DIR, "orders.csv")
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            order = {
                "order_id": row["order_id"],
                "order_date": row["order_date"],
                "product_id": row["product_id"],
                "size": row["size"],
                "price_paid": float(row["price_paid"]),
                "customer_id": row["customer_id"],
            }
            orders.append(order)

    _orders_cache = orders
    return _orders_cache


def load_policy() -> str:
    """Load policy.txt and return the raw text."""
    global _policy_cache
    if _policy_cache is not None:
        return _policy_cache

    path = os.path.join(DATA_DIR, "policy.txt")
    with open(path, encoding="utf-8") as f:
        _policy_cache = f.read()

    return _policy_cache
