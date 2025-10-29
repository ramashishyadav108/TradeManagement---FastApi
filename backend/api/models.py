"""
Pydantic models for API request/response validation.

This module defines all data models used in the REST API and WebSocket
communications, ensuring type safety and validation.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, ConfigDict

from backend.core.order import OrderType, OrderSide, OrderStatus


# ============================================================================
# Request Models
# ============================================================================

class OrderRequest(BaseModel):
    """Request model for submitting a new order."""
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "symbol": "BTC-USDT",
            "order_type": "limit",
            "side": "buy",
            "quantity": "0.5",
            "price": "50000.00"
        }
    })
    
    symbol: str = Field(
        ...,
        description="Trading pair symbol (e.g., BTC-USDT)",
        min_length=3,
        max_length=20,
        pattern=r'^[A-Z]+-[A-Z]+$'
    )
    order_type: str = Field(
        ...,
        description="Order type: market, limit, ioc, fok",
        pattern=r'^(market|limit|ioc|fok)$'
    )
    side: str = Field(
        ...,
        description="Order side: buy or sell",
        pattern=r'^(buy|sell)$'
    )
    quantity: str = Field(
        ...,
        description="Order quantity as decimal string",
        pattern=r'^\d+(\.\d+)?$'
    )
    price: Optional[str] = Field(
        None,
        description="Limit price (required for limit/ioc/fok orders)",
        pattern=r'^\d+(\.\d+)?$'
    )
    
    @field_validator('quantity')
    @classmethod
    def validate_quantity(cls, v: str) -> str:
        """Validate quantity is positive."""
        qty = Decimal(v)
        if qty <= 0:
            raise ValueError("Quantity must be positive")
        if qty > Decimal("1000000"):
            raise ValueError("Quantity exceeds maximum allowed (1,000,000)")
        return v
    
    @field_validator('price')
    @classmethod
    def validate_price(cls, v: Optional[str]) -> Optional[str]:
        """Validate price is positive if provided."""
        if v is None:
            return v
        price = Decimal(v)
        if price <= 0:
            raise ValueError("Price must be positive")
        if price > Decimal("10000000"):
            raise ValueError("Price exceeds maximum allowed (10,000,000)")
        return v
    
    def to_order_params(self) -> Dict[str, Any]:
        """Convert to parameters for Order creation."""
        return {
            "symbol": self.symbol,
            "order_type": OrderType[self.order_type.upper()],
            "side": OrderSide[self.side.upper()],
            "quantity": Decimal(self.quantity),
            "price": Decimal(self.price) if self.price else None
        }


# ============================================================================
# Response Models
# ============================================================================

class TradeResponse(BaseModel):
    """Response model for a trade."""
    
    model_config = ConfigDict(from_attributes=True)
    
    trade_id: UUID = Field(..., description="Unique trade identifier")
    price: str = Field(..., description="Execution price")
    quantity: str = Field(..., description="Executed quantity")
    timestamp: datetime = Field(..., description="Trade execution timestamp")
    aggressor_side: str = Field(..., description="Aggressor side (buy/sell)")
    
    @classmethod
    def from_trade(cls, trade: 'Trade') -> 'TradeResponse':
        """Create from Trade object."""
        return cls(
            trade_id=trade.trade_id,
            price=str(trade.price),
            quantity=str(trade.quantity),
            timestamp=trade.timestamp,
            aggressor_side=trade.aggressor_side.value.lower()
        )


class OrderResponse(BaseModel):
    """Response model for order submission."""
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "order_id": "550e8400-e29b-41d4-a716-446655440000",
            "status": "filled",
            "filled_quantity": "0.5",
            "remaining_quantity": "0.0",
            "trades": [
                {
                    "trade_id": "650e8400-e29b-41d4-a716-446655440000",
                    "price": "50000.00",
                    "quantity": "0.5",
                    "timestamp": "2025-10-25T10:30:45.123456",
                    "aggressor_side": "buy"
                }
            ],
            "timestamp": "2025-10-25T10:30:45.123456"
        }
    })
    
    order_id: UUID = Field(..., description="Unique order identifier")
    status: str = Field(..., description="Order status: filled/partial/pending/cancelled")
    filled_quantity: str = Field(..., description="Quantity filled")
    remaining_quantity: str = Field(..., description="Quantity remaining")
    trades: List[TradeResponse] = Field(default_factory=list, description="List of trades executed")
    timestamp: datetime = Field(..., description="Order submission timestamp")
    
    @classmethod
    def from_order_result(cls, result: 'OrderResult') -> 'OrderResponse':
        """Create from OrderResult object."""
        return cls(
            order_id=result.order.order_id,
            status=result.order.status.value.lower(),
            filled_quantity=str(result.order.filled_quantity),
            remaining_quantity=str(result.order.remaining_quantity),
            trades=[TradeResponse.from_trade(t) for t in result.trades],
            timestamp=result.order.timestamp
        )


class OrderStatusResponse(BaseModel):
    """Response model for order status query."""
    
    model_config = ConfigDict(from_attributes=True)
    
    order_id: UUID
    symbol: str
    order_type: str
    side: str
    status: str
    quantity: str
    filled_quantity: str
    remaining_quantity: str
    price: Optional[str] = None
    timestamp: datetime
    
    @classmethod
    def from_order(cls, order: 'Order') -> 'OrderStatusResponse':
        """Create from Order object."""
        return cls(
            order_id=order.order_id,
            symbol=order.symbol,
            order_type=order.order_type.value.lower(),
            side=order.side.value.lower(),
            status=order.status.value.lower(),
            quantity=str(order.quantity),
            filled_quantity=str(order.filled_quantity),
            remaining_quantity=str(order.remaining_quantity),
            price=str(order.price) if order.price else None,
            timestamp=order.timestamp
        )


class CancelOrderResponse(BaseModel):
    """Response model for order cancellation."""
    
    order_id: UUID = Field(..., description="Cancelled order ID")
    cancelled: bool = Field(..., description="Cancellation success status")
    message: str = Field(..., description="Cancellation message")


class BBOResponse(BaseModel):
    """Response model for Best Bid/Offer."""
    
    best_bid: Optional[str] = Field(None, description="Best bid price")
    best_ask: Optional[str] = Field(None, description="Best ask price")
    spread: Optional[str] = Field(None, description="Bid-ask spread")


class OrderBookResponse(BaseModel):
    """Response model for order book snapshot."""
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "symbol": "BTC-USDT",
            "timestamp": "2025-10-25T10:30:45.123456",
            "bids": [
                ["50000.00", "1.5"],
                ["49999.00", "2.3"]
            ],
            "asks": [
                ["50001.00", "0.8"],
                ["50002.00", "1.2"]
            ],
            "bbo": {
                "best_bid": "50000.00",
                "best_ask": "50001.00",
                "spread": "1.00"
            }
        }
    })
    
    symbol: str = Field(..., description="Trading pair symbol")
    timestamp: datetime = Field(..., description="Snapshot timestamp")
    bids: List[List[str]] = Field(..., description="Bid levels [[price, quantity], ...]")
    asks: List[List[str]] = Field(..., description="Ask levels [[price, quantity], ...]")
    bbo: BBOResponse = Field(..., description="Best bid/offer")


# ============================================================================
# WebSocket Message Models
# ============================================================================

class OrderBookUpdateMessage(BaseModel):
    """WebSocket message for order book updates."""
    
    type: str = Field(default="orderbook_update", description="Message type")
    symbol: str = Field(..., description="Trading pair symbol")
    timestamp: datetime = Field(..., description="Update timestamp")
    bids: List[List[str]] = Field(default_factory=list, description="Updated bid levels")
    asks: List[List[str]] = Field(default_factory=list, description="Updated ask levels")
    bbo: BBOResponse = Field(..., description="Best bid/offer")


class TradeMessage(BaseModel):
    """WebSocket message for trade feed."""
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "type": "trade",
            "timestamp": "2025-10-25T10:30:45.123456",
            "symbol": "BTC-USDT",
            "trade_id": "650e8400-e29b-41d4-a716-446655440000",
            "price": "50000.00",
            "quantity": "0.5",
            "aggressor_side": "buy",
            "maker_order_id": "750e8400-e29b-41d4-a716-446655440000",
            "taker_order_id": "850e8400-e29b-41d4-a716-446655440000"
        }
    })
    
    type: str = Field(default="trade", description="Message type")
    timestamp: datetime = Field(..., description="Trade timestamp")
    symbol: str = Field(..., description="Trading pair symbol")
    trade_id: UUID = Field(..., description="Trade identifier")
    price: str = Field(..., description="Execution price")
    quantity: str = Field(..., description="Executed quantity")
    aggressor_side: str = Field(..., description="Aggressor side")
    maker_order_id: UUID = Field(..., description="Maker order ID")
    taker_order_id: UUID = Field(..., description="Taker order ID")
    
    @classmethod
    def from_trade(cls, trade: 'Trade', taker_order_id: UUID) -> 'TradeMessage':
        """Create from Trade object."""
        return cls(
            timestamp=trade.timestamp,
            symbol=trade.symbol,
            trade_id=trade.trade_id,
            price=str(trade.price),
            quantity=str(trade.quantity),
            aggressor_side=trade.aggressor_side.value.lower(),
            maker_order_id=trade.maker_order_id,
            taker_order_id=taker_order_id
        )


class HealthResponse(BaseModel):
    """Response model for health check."""
    
    status: str = Field(..., description="Service status")
    timestamp: datetime = Field(..., description="Check timestamp")
    version: str = Field(..., description="API version")
    matching_engine: Dict[str, Any] = Field(..., description="Matching engine statistics")


class ErrorResponse(BaseModel):
    """Response model for errors."""
    
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")
    timestamp: datetime = Field(..., description="Error timestamp")
