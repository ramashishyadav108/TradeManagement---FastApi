"""Formatting Utilities for UI Display"""
from decimal import Decimal
from datetime import datetime
from typing import Union

def format_price(price: Union[str, Decimal, float], decimals: int = 2) -> str:
    try:
        if price is None:
            return "N/A"
        price_dec = Decimal(str(price))
        return f"{float(price_dec):,.{decimals}f}"
    except:
        return str(price)

def format_quantity(qty: Union[str, Decimal, float], decimals: int = 4) -> str:
    try:
        if qty is None:
            return "N/A"
        qty_dec = Decimal(str(qty))
        return f"{float(qty_dec):,.{decimals}f}"
    except:
        return str(qty)

def format_timestamp(ts: Union[str, datetime]) -> str:
    try:
        if isinstance(ts, str):
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
        else:
            dt = ts
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return str(ts)

def format_currency(value: Union[str, Decimal, float], symbol: str = "$") -> str:
    try:
        value_dec = Decimal(str(value))
        return f"{symbol}{value_dec:,.2f}"
    except:
        return f"{symbol}{value}"

def color_by_side(side: str) -> str:
    side_lower = side.lower()
    if side_lower == "buy":
        return "#10b981"
    elif side_lower == "sell":
        return "#ef4444"
    else:
        return "#6b7280"

def calculate_total(price: Union[str, Decimal, float], quantity: Union[str, Decimal, float]) -> Decimal:
    try:
        return Decimal(str(price)) * Decimal(str(quantity))
    except:
        return Decimal("0")

def format_order_id(order_id: str) -> str:
    try:
        if len(order_id) > 16:
            return f"{order_id[:8]}...{order_id[-4:]}"
        return order_id
    except:
        return str(order_id)
