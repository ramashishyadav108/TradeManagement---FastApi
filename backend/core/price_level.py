"""
Price level queue management with FIFO ordering

This module defines the PriceLevel class which maintains a queue of orders
at a single price level with strict time-priority (FIFO) enforcement.
"""

from collections import deque
from decimal import Decimal
from typing import Optional, Deque
from uuid import UUID

from .order import Order, OrderSide


class PriceLevel:
    """
    Manages orders at a single price level with FIFO ordering.
    
    This class maintains strict time-priority by using a deque for O(1)
    append and pop operations. Orders are processed in the exact order
    they were added (First-In-First-Out).
    
    Attributes:
        price: The price level
        side: Buy or sell side
        orders: Deque of orders at this price level
    """
    
    def __init__(self, price: Decimal, side: OrderSide):
        """
        Initialize a price level.
        
        Args:
            price: The price for this level
            side: The side (BUY or SELL) for this level
        """
        self.price: Decimal = price
        self.side: OrderSide = side
        self.orders: Deque[Order] = deque()
        self._order_map: dict[UUID, Order] = {}  # For O(1) order lookup
    
    def add_order(self, order: Order) -> None:
        """
        Add an order to the end of the queue (FIFO).
        
        Args:
            order: Order to add
            
        Raises:
            ValueError: If order price doesn't match level or order already exists
        """
        if order.price != self.price:
            raise ValueError(
                f"Order price {order.price} doesn't match level price {self.price}"
            )
        
        if order.side != self.side:
            raise ValueError(
                f"Order side {order.side} doesn't match level side {self.side}"
            )
        
        if order.order_id in self._order_map:
            raise ValueError(f"Order {order.order_id} already exists at this level")
        
        self.orders.append(order)
        self._order_map[order.order_id] = order
    
    def remove_order(self, order_id: UUID) -> Optional[Order]:
        """
        Remove an order from the queue.
        
        Note: This is O(n) as we need to search through the deque.
        For high-frequency scenarios, consider maintaining a separate index.
        
        Args:
            order_id: ID of order to remove
            
        Returns:
            Removed order or None if not found
        """
        if order_id not in self._order_map:
            return None
        
        # Remove from map
        order = self._order_map.pop(order_id)
        
        # Remove from deque (O(n) operation)
        try:
            self.orders.remove(order)
        except ValueError:
            # Should not happen if map and deque are in sync
            pass
        
        return order
    
    def get_next_order(self) -> Optional[Order]:
        """
        Get the next order in FIFO order without removing it.
        
        Returns:
            Next order or None if queue is empty
        """
        if not self.orders:
            return None
        return self.orders[0]
    
    def pop_next_order(self) -> Optional[Order]:
        """
        Get and remove the next order in FIFO order.
        
        Returns:
            Next order or None if queue is empty
        """
        if not self.orders:
            return None
        
        order = self.orders.popleft()
        self._order_map.pop(order.order_id, None)
        return order
    
    def get_total_quantity(self) -> Decimal:
        """
        Calculate total quantity at this price level.
        
        Returns:
            Sum of remaining quantities of all orders
        """
        return sum(order.remaining_quantity for order in self.orders)
    
    def is_empty(self) -> bool:
        """
        Check if this price level has no orders.
        
        Returns:
            True if no orders remain
        """
        return len(self.orders) == 0
    
    @property
    def total_volume(self) -> Decimal:
        """Total volume at this price level."""
        return self.get_total_quantity()
    
    @property
    def order_count(self) -> int:
        """Number of orders at this price level."""
        return len(self.orders)
    
    def __repr__(self) -> str:
        """String representation of the price level."""
        return (
            f"PriceLevel(price={self.price}, side={self.side.value}, "
            f"orders={self.order_count}, volume={self.total_volume})"
        )
    
    def __len__(self) -> int:
        """Number of orders at this level."""
        return len(self.orders)
