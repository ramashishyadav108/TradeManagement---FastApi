"""
Order domain model with enums and validation

This module defines the Order class and related enums representing
orders in the matching engine with comprehensive validation.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from .trade import Trade



class OrderType(Enum):
    """Order type enumeration."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    IOC = "IOC"  # Immediate-Or-Cancel
    FOK = "FOK"  # Fill-Or-Kill
    
    def __str__(self) -> str:
        return self.value


class OrderSide(Enum):
    """Order side enumeration."""
    BUY = "BUY"
    SELL = "SELL"
    
    def __str__(self) -> str:
        return self.value


class OrderStatus(Enum):
    """Order status enumeration."""
    PENDING = "PENDING"      # Order submitted but not yet processed
    PARTIAL = "PARTIAL"      # Order partially filled
    FILLED = "FILLED"        # Order completely filled
    CANCELLED = "CANCELLED"  # Order cancelled
    REJECTED = "REJECTED"    # Order rejected due to validation failure
    
    def __str__(self) -> str:
        return self.value


@dataclass(slots=True)
class Order:
    """
    Represents a trading order in the matching engine.
    
    This class uses slots for memory efficiency and includes comprehensive
    validation and helper methods for order processing.
    
    Attributes:
        order_id: Unique identifier for the order
        symbol: Trading pair symbol (e.g., "BTC-USDT")
        order_type: Type of order (MARKET, LIMIT, IOC, FOK)
        side: Buy or sell
        quantity: Total quantity of the order
        price: Price per unit (None for market orders)
        timestamp: Order creation time with microsecond precision
        status: Current status of the order
        filled_quantity: Amount already filled
        remaining_quantity: Amount yet to be filled
    """
    
    symbol: str
    order_type: OrderType
    side: OrderSide
    quantity: Decimal
    price: Optional[Decimal] = None
    order_id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: Decimal = field(default=Decimal("0"))
    remaining_quantity: Decimal = field(init=False)
    
    def __post_init__(self):
        """
        Post-initialization validation and setup.
        
        Raises:
            ValueError: If order parameters are invalid
        """
        # Set remaining quantity
        object.__setattr__(self, 'remaining_quantity', self.quantity)
        
        # Validate order parameters
        self.validate()
    
    def validate(self) -> None:
        """
        Validate order parameters.
        
        Raises:
            ValueError: If validation fails
        """
        if self.quantity <= 0:
            raise ValueError(f"Quantity must be positive, got {self.quantity}")
        
        if self.filled_quantity < 0:
            raise ValueError(f"Filled quantity cannot be negative, got {self.filled_quantity}")
        
        if self.filled_quantity > self.quantity:
            raise ValueError(f"Filled quantity {self.filled_quantity} exceeds total quantity {self.quantity}")
        
        # Limit orders require a price
        if self.order_type in (OrderType.LIMIT, OrderType.IOC, OrderType.FOK):
            if self.price is None:
                raise ValueError(f"{self.order_type} orders require a price")
            if self.price <= 0:
                raise ValueError(f"Price must be positive, got {self.price}")
        
        # Ensure symbol is not empty
        if not self.symbol or not self.symbol.strip():
            raise ValueError("Symbol cannot be empty")
    
    def is_marketable(self, best_bid: Optional[Decimal], best_ask: Optional[Decimal]) -> bool:
        """
        Check if order is immediately marketable against current BBO.
        
        Args:
            best_bid: Current best bid price
            best_ask: Current best ask price
            
        Returns:
            True if order can be immediately matched
        """
        if self.order_type == OrderType.MARKET:
            return True
        
        if self.price is None:
            return False
        
        # Buy orders are marketable if price >= best ask
        if self.side == OrderSide.BUY:
            return best_ask is not None and self.price >= best_ask
        
        # Sell orders are marketable if price <= best bid
        return best_bid is not None and self.price <= best_bid
    
    def can_fill_quantity(self, quantity: Decimal) -> bool:
        """
        Check if the order can be filled by the given quantity.
        
        Args:
            quantity: Quantity to check
            
        Returns:
            True if order has enough remaining quantity
        """
        return quantity > 0 and quantity <= self.remaining_quantity
    
    def update_fill(self, filled_qty: Decimal) -> None:
        """
        Update the order with a fill.
        
        Args:
            filled_qty: Quantity that was filled
            
        Raises:
            ValueError: If filled quantity is invalid
        """
        if filled_qty <= 0:
            raise ValueError(f"Fill quantity must be positive, got {filled_qty}")
        
        if filled_qty > self.remaining_quantity:
            raise ValueError(
                f"Fill quantity {filled_qty} exceeds remaining {self.remaining_quantity}"
            )
        
        # Update quantities
        object.__setattr__(self, 'filled_quantity', self.filled_quantity + filled_qty)
        object.__setattr__(self, 'remaining_quantity', self.quantity - self.filled_quantity)
        
        # Update status
        if self.remaining_quantity == 0:
            object.__setattr__(self, 'status', OrderStatus.FILLED)
        elif self.filled_quantity > 0:
            object.__setattr__(self, 'status', OrderStatus.PARTIAL)
    
    @property
    def is_fully_filled(self) -> bool:
        """Check if order is completely filled."""
        return self.remaining_quantity == 0
    
    @property
    def is_buy(self) -> bool:
        """Check if this is a buy order."""
        return self.side == OrderSide.BUY
    
    @property
    def is_sell(self) -> bool:
        """Check if this is a sell order."""
        return self.side == OrderSide.SELL
    
    @property
    def is_active(self) -> bool:
        """Check if order is active (can still be matched)."""
        return self.status in (OrderStatus.PENDING, OrderStatus.PARTIAL)
    
    def __repr__(self) -> str:
        """String representation of the order."""
        price_str = f"{self.price:.8f}" if self.price else "MARKET"
        return (
            f"Order(id={str(self.order_id)[:8]}..., "
            f"{self.side.value} {self.quantity} {self.symbol} @ {price_str}, "
            f"type={self.order_type.value}, status={self.status.value}, "
            f"filled={self.filled_quantity}/{self.quantity})"
        )
    
    def __eq__(self, other) -> bool:
        """Equality based on order ID."""
        if not isinstance(other, Order):
            return False
        return self.order_id == other.order_id
    
    def __hash__(self) -> int:
        """Hash based on order ID for use in sets/dicts."""
        return hash(self.order_id)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert order to dictionary for API serialization."""
        return {
            "order_id": str(self.order_id),
            "symbol": self.symbol,
            "order_type": self.order_type.value,
            "side": self.side.value,
            "quantity": str(self.quantity),
            "price": str(self.price) if self.price is not None else None,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
            "filled_quantity": str(self.filled_quantity),
            "remaining_quantity": str(self.remaining_quantity),
        }


@dataclass
class OrderResult:
    """
    Result of an order submission to the matching engine.
    
    Contains the order, list of trades generated, status, and any messages.
    
    Attributes:
        order: The order that was submitted
        trades: List of trades generated from this order
        status: Final status of the order
        message: Human-readable message about the order result
        timestamp: Time when the result was generated
    """
    order: Order
    trades: List['Trade']
    status: OrderStatus
    message: str
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert order result to dictionary for API serialization."""
        return {
            "order_id": str(self.order.order_id),
            "status": self.status.value,
            "filled_quantity": str(self.order.filled_quantity),
            "remaining_quantity": str(self.order.remaining_quantity),
            "trades": [trade.to_dict() for trade in self.trades],
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
        }
    
    def is_successful(self) -> bool:
        """Check if the order was successfully processed."""
        return self.status in (OrderStatus.FILLED, OrderStatus.PARTIAL, OrderStatus.PENDING)
