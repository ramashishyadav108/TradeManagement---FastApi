"""
Input validation utilities

This module provides validation functions for order parameters, prices, and quantities
to ensure data integrity throughout the matching engine.
"""

from decimal import Decimal, InvalidOperation
from typing import Optional, Union
from .exceptions import (
    InvalidOrderException,
    InvalidQuantityException,
    PriceOutOfBoundsException,
    InvalidSymbolException,
)


def sanitize_decimal(value: Union[str, int, float, Decimal]) -> Decimal:
    """
    Convert a value to Decimal with proper error handling.
    
    Args:
        value: Value to convert to Decimal
        
    Returns:
        Decimal representation of the value
        
    Raises:
        InvalidOrderException: If value cannot be converted to Decimal
    """
    try:
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as e:
        raise InvalidOrderException(
            f"Invalid decimal value: {value}",
            details={"value": value, "error": str(e)}
        )


def validate_price(
    price: Optional[Decimal],
    symbol: str,
    required: bool = False,
    min_price: Decimal = Decimal("0.00000001"),
    max_price: Decimal = Decimal("10000000"),
) -> bool:
    """
    Validate a price value.
    
    Args:
        price: Price to validate
        symbol: Trading symbol for context
        required: Whether price is required (False for market orders)
        min_price: Minimum acceptable price
        max_price: Maximum acceptable price
        
    Returns:
        True if price is valid
        
    Raises:
        InvalidOrderException: If price is required but None
        PriceOutOfBoundsException: If price is outside acceptable bounds
    """
    if price is None:
        if required:
            raise InvalidOrderException(
                "Price is required for this order type",
                details={"symbol": symbol}
            )
        return True
    
    if price <= 0:
        raise PriceOutOfBoundsException(
            f"Price must be positive, got {price}",
            details={"symbol": symbol, "price": str(price)}
        )
    
    if price < min_price:
        raise PriceOutOfBoundsException(
            f"Price {price} is below minimum {min_price}",
            details={"symbol": symbol, "price": str(price), "min": str(min_price)}
        )
    
    if price > max_price:
        raise PriceOutOfBoundsException(
            f"Price {price} exceeds maximum {max_price}",
            details={"symbol": symbol, "price": str(price), "max": str(max_price)}
        )
    
    return True


def validate_quantity(
    quantity: Decimal,
    symbol: str,
    min_quantity: Decimal = Decimal("0.00000001"),
    max_quantity: Decimal = Decimal("1000000"),
) -> bool:
    """
    Validate an order quantity.
    
    Args:
        quantity: Quantity to validate
        symbol: Trading symbol for context
        min_quantity: Minimum acceptable quantity
        max_quantity: Maximum acceptable quantity
        
    Returns:
        True if quantity is valid
        
    Raises:
        InvalidQuantityException: If quantity is invalid
    """
    if quantity <= 0:
        raise InvalidQuantityException(
            f"Quantity must be positive, got {quantity}",
            details={"symbol": symbol, "quantity": str(quantity)}
        )
    
    if quantity < min_quantity:
        raise InvalidQuantityException(
            f"Quantity {quantity} is below minimum {min_quantity}",
            details={"symbol": symbol, "quantity": str(quantity), "min": str(min_quantity)}
        )
    
    if quantity > max_quantity:
        raise InvalidQuantityException(
            f"Quantity {quantity} exceeds maximum {max_quantity}",
            details={"symbol": symbol, "quantity": str(quantity), "max": str(max_quantity)}
        )
    
    return True


def validate_symbol(symbol: str, allowed_symbols: Optional[list] = None) -> bool:
    """
    Validate a trading symbol.
    
    Args:
        symbol: Trading symbol to validate
        allowed_symbols: Optional list of allowed symbols
        
    Returns:
        True if symbol is valid
        
    Raises:
        InvalidSymbolException: If symbol is invalid
    """
    if not symbol or not isinstance(symbol, str):
        raise InvalidSymbolException(
            f"Invalid symbol: {symbol}",
            details={"symbol": symbol}
        )
    
    symbol = symbol.strip().upper()
    
    if len(symbol) < 3:
        raise InvalidSymbolException(
            f"Symbol too short: {symbol}",
            details={"symbol": symbol}
        )
    
    if allowed_symbols and symbol not in allowed_symbols:
        raise InvalidSymbolException(
            f"Symbol {symbol} not in allowed list",
            details={"symbol": symbol, "allowed": allowed_symbols}
        )
    
    return True


def validate_order_parameters(
    symbol: str,
    order_type: str,
    side: str,
    quantity: Union[str, Decimal],
    price: Optional[Union[str, Decimal]] = None,
) -> tuple[str, Decimal, Optional[Decimal]]:
    """
    Validate all order parameters together.
    
    Args:
        symbol: Trading symbol
        order_type: Type of order (market, limit, ioc, fok)
        side: Order side (buy, sell)
        quantity: Order quantity
        price: Order price (required for limit orders)
        
    Returns:
        Tuple of (validated_symbol, validated_quantity, validated_price)
        
    Raises:
        InvalidOrderException: If any parameter is invalid
    """
    # Validate and normalize symbol
    symbol = symbol.strip().upper()
    validate_symbol(symbol)
    
    # Validate order type
    valid_order_types = ["MARKET", "LIMIT", "IOC", "FOK"]
    if order_type.upper() not in valid_order_types:
        raise InvalidOrderException(
            f"Invalid order type: {order_type}",
            details={"order_type": order_type, "valid_types": valid_order_types}
        )
    
    # Validate side
    valid_sides = ["BUY", "SELL"]
    if side.upper() not in valid_sides:
        raise InvalidOrderException(
            f"Invalid side: {side}",
            details={"side": side, "valid_sides": valid_sides}
        )
    
    # Sanitize and validate quantity
    validated_quantity = sanitize_decimal(quantity)
    validate_quantity(validated_quantity, symbol)
    
    # Sanitize and validate price
    validated_price = None
    if price is not None:
        validated_price = sanitize_decimal(price)
    
    # Price is required for limit orders
    price_required = order_type.upper() in ["LIMIT", "IOC", "FOK"]
    validate_price(validated_price, symbol, required=price_required)
    
    return symbol, validated_quantity, validated_price
