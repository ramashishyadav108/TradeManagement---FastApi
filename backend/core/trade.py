"""
Trade execution domain model

This module defines the Trade class representing a completed trade execution
between a maker and taker order.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from .order import OrderSide


@dataclass(frozen=True, slots=True)
class Trade:
    """
    Represents a completed trade execution.
    
    This class is immutable (frozen=True) to ensure trade integrity.
    All trades are final and cannot be modified after creation.
    
    Attributes:
        trade_id: Unique identifier for the trade
        symbol: Trading pair symbol
        price: Execution price
        quantity: Executed quantity
        timestamp: Trade execution time with microsecond precision
        aggressor_side: Side of the taker (aggressor) order
        maker_order_id: ID of the passive (maker) order
        taker_order_id: ID of the aggressive (taker) order
        maker_fee: Fee charged to maker (default 0)
        taker_fee: Fee charged to taker (default 0)
    """
    
    symbol: str
    price: Decimal
    quantity: Decimal
    aggressor_side: OrderSide
    maker_order_id: UUID
    taker_order_id: UUID
    trade_id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    maker_fee: Decimal = field(default=Decimal("0"))
    taker_fee: Decimal = field(default=Decimal("0"))
    
    def __post_init__(self):
        """
        Post-initialization validation.
        
        Raises:
            ValueError: If trade parameters are invalid
        """
        if self.price <= 0:
            raise ValueError(f"Price must be positive, got {self.price}")
        
        if self.quantity <= 0:
            raise ValueError(f"Quantity must be positive, got {self.quantity}")
        
        if self.maker_fee < 0:
            raise ValueError(f"Maker fee cannot be negative, got {self.maker_fee}")
        
        if self.taker_fee < 0:
            raise ValueError(f"Taker fee cannot be negative, got {self.taker_fee}")
        
        if not self.symbol or not self.symbol.strip():
            raise ValueError("Symbol cannot be empty")
    
    @property
    def total_value(self) -> Decimal:
        """Calculate total trade value (price * quantity)."""
        return self.price * self.quantity
    
    @property
    def maker_is_buyer(self) -> bool:
        """Check if maker is the buyer (aggressor is seller)."""
        return self.aggressor_side == OrderSide.SELL
    
    @property
    def taker_is_buyer(self) -> bool:
        """Check if taker is the buyer (aggressor is buyer)."""
        return self.aggressor_side == OrderSide.BUY
    
    def calculate_fees(
        self,
        maker_fee_rate: Decimal = Decimal("0.001"),
        taker_fee_rate: Decimal = Decimal("0.002")
    ) -> tuple[Decimal, Decimal]:
        """
        Calculate trading fees for maker and taker.
        
        Args:
            maker_fee_rate: Fee rate for maker (default 0.1%)
            taker_fee_rate: Fee rate for taker (default 0.2%)
            
        Returns:
            Tuple of (maker_fee, taker_fee) in quote currency
        """
        total_value = self.total_value
        maker_fee = total_value * maker_fee_rate
        taker_fee = total_value * taker_fee_rate
        return maker_fee, taker_fee
    
    def to_dict(self) -> dict:
        """
        Convert trade to dictionary for API serialization.
        
        Returns:
            Dictionary representation of the trade
        """
        return {
            "trade_id": str(self.trade_id),
            "symbol": self.symbol,
            "price": str(self.price),
            "quantity": str(self.quantity),
            "timestamp": self.timestamp.isoformat() + "Z",
            "aggressor_side": self.aggressor_side.value,
            "maker_order_id": str(self.maker_order_id),
            "taker_order_id": str(self.taker_order_id),
            "maker_fee": str(self.maker_fee),
            "taker_fee": str(self.taker_fee),
            "total_value": str(self.total_value),
        }
    
    def __repr__(self) -> str:
        """String representation of the trade."""
        return (
            f"Trade(id={str(self.trade_id)[:8]}..., "
            f"{self.symbol}, {self.quantity} @ {self.price}, "
            f"aggressor={self.aggressor_side.value}, "
            f"value={self.total_value:.2f})"
        )
