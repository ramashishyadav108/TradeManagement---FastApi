"""
Order book data structure with price-time priority

This module implements a high-performance order book using sorted dictionaries
for efficient price-level management and O(1) order lookups.
"""

from decimal import Decimal
from typing import Optional, Dict, List, Tuple
from uuid import UUID
from sortedcontainers import SortedDict

from .order import Order, OrderSide, OrderStatus
from .price_level import PriceLevel
from .bbo_manager import BBOManager
from ..utils.exceptions import (
    OrderNotFoundException,
    DuplicateOrderException,
    OrderBookException,
)


class OrderBook:
    """
    Manages the order book for a trading pair with price-time priority.
    
    This class maintains separate sorted dictionaries for bids and asks,
    with bids sorted in descending order and asks in ascending order.
    This ensures O(log n) insertion and the best prices are always accessible.
    
    Attributes:
        symbol: Trading pair symbol
        bids: Sorted dictionary of bid price levels (descending)
        asks: Sorted dictionary of ask price levels (ascending)
        order_registry: Fast lookup of orders by ID
        bbo_manager: Manages best bid/offer tracking
    """
    
    def __init__(self, symbol: str):
        """
        Initialize an order book for a symbol.
        
        Args:
            symbol: Trading pair symbol (e.g., "BTC-USDT")
        """
        self.symbol: str = symbol
        
        # Bids sorted in descending order (highest price first)
        self.bids: SortedDict[Decimal, PriceLevel] = SortedDict(lambda x: -x)
        
        # Asks sorted in ascending order (lowest price first)
        self.asks: SortedDict[Decimal, PriceLevel] = SortedDict()
        
        # Order registry for O(1) lookup by order ID
        self.order_registry: Dict[UUID, Order] = {}
        
        # BBO manager for tracking best prices
        self.bbo_manager: BBOManager = BBOManager(symbol)
    
    def add_order(self, order: Order) -> bool:
        """
        Add an order to the book.
        
        Args:
            order: Order to add
            
        Returns:
            True if order was added successfully
            
        Raises:
            DuplicateOrderException: If order already exists
            OrderBookException: If order cannot be added
        """
        # Check for duplicate
        if order.order_id in self.order_registry:
            raise DuplicateOrderException(
                f"Order {order.order_id} already exists in book",
                details={"order_id": str(order.order_id)}
            )
        
        # Validate order has remaining quantity
        if order.remaining_quantity <= 0:
            raise OrderBookException(
                "Cannot add order with no remaining quantity",
                details={"order_id": str(order.order_id)}
            )
        
        # Only add limit orders to the book (market orders execute immediately)
        if order.price is None:
            raise OrderBookException(
                "Cannot add order without price to book",
                details={"order_id": str(order.order_id), "order_type": order.order_type.value}
            )
        
        # Add to appropriate side
        self._add_to_price_level(order)
        
        # Register order
        self.order_registry[order.order_id] = order
        
        # Update BBO
        self._update_bbo()
        
        return True
    
    def remove_order(self, order_id: UUID) -> Optional[Order]:
        """
        Remove an order from the book.
        
        Args:
            order_id: ID of order to remove
            
        Returns:
            Removed order or None if not found
        """
        # Check if order exists
        order = self.order_registry.get(order_id)
        if order is None:
            return None
        
        # Remove from price level
        self._remove_from_price_level(order)
        
        # Unregister order
        del self.order_registry[order_id]
        
        # Update BBO
        self._update_bbo()
        
        return order
    
    def remove_from_book_only(self, order_id: UUID) -> Optional[Order]:
        """
        Remove an order from the book's price levels but keep it in the registry.
        This is used for filled orders that should remain queryable.
        
        Args:
            order_id: ID of order to remove from price levels
            
        Returns:
            Order if found, None otherwise
        """
        # Check if order exists
        order = self.order_registry.get(order_id)
        if order is None:
            return None
        
        # Remove from price level only (keep in registry)
        self._remove_from_price_level(order)
        
        # Update BBO
        self._update_bbo()
        
        return order
    
    def get_order(self, order_id: UUID) -> Optional[Order]:
        """
        Get an order by ID.
        
        Args:
            order_id: Order ID to lookup
            
        Returns:
            Order if found, None otherwise
        """
        return self.order_registry.get(order_id)
    
    def get_best_bid(self) -> Optional[Decimal]:
        """
        Get the best bid price.
        
        Returns:
            Best bid price or None if no bids
        """
        if not self.bids:
            return None
        return self.bids.keys()[0]  # First key (highest price)
    
    def get_best_ask(self) -> Optional[Decimal]:
        """
        Get the best ask price.
        
        Returns:
            Best ask price or None if no asks
        """
        if not self.asks:
            return None
        return self.asks.keys()[0]  # First key (lowest price)
    
    def get_bbo(self) -> Tuple[Optional[Decimal], Optional[Decimal]]:
        """
        Get best bid and offer.
        
        Returns:
            Tuple of (best_bid, best_ask)
        """
        return self.get_best_bid(), self.get_best_ask()
    
    def get_depth(self, levels: int = 10) -> Dict:
        """
        Get order book depth (L2 market data).
        
        Args:
            levels: Number of price levels to include (default 10)
            
        Returns:
            Dictionary with bids and asks as lists of [price, quantity]
        """
        bids = []
        asks = []
        
        # Get top bid levels
        for i, (price, level) in enumerate(self.bids.items()):
            if i >= levels:
                break
            bids.append([str(price), str(level.total_volume)])
        
        # Get top ask levels
        for i, (price, level) in enumerate(self.asks.items()):
            if i >= levels:
                break
            asks.append([str(price), str(level.total_volume)])
        
        return {
            "symbol": self.symbol,
            "bids": bids,
            "asks": asks,
            "best_bid": str(self.best_bid) if self.best_bid else None,
            "best_ask": str(self.best_ask) if self.best_ask else None,
            "spread": str(self.spread) if self.spread else None,
        }
    
    def get_total_volume_at_price(self, price: Decimal, side: OrderSide) -> Decimal:
        """
        Get total volume at a specific price level.
        
        Args:
            price: Price level to query
            side: BUY or SELL side
            
        Returns:
            Total volume at the price level
        """
        book = self.bids if side == OrderSide.BUY else self.asks
        level = book.get(price)
        return level.total_volume if level else Decimal("0")
    
    @property
    def best_bid(self) -> Optional[Decimal]:
        """Best bid price."""
        return self.get_best_bid()
    
    @property
    def best_ask(self) -> Optional[Decimal]:
        """Best ask price."""
        return self.get_best_ask()
    
    @property
    def spread(self) -> Optional[Decimal]:
        """Bid-ask spread."""
        bid = self.best_bid
        ask = self.best_ask
        if bid is None or ask is None:
            return None
        return ask - bid
    
    @property
    def mid_price(self) -> Optional[Decimal]:
        """Mid-market price."""
        bid = self.best_bid
        ask = self.best_ask
        if bid is None or ask is None:
            return None
        return (bid + ask) / Decimal("2")
    
    def _add_to_price_level(self, order: Order) -> None:
        """
        Add order to appropriate price level.
        
        Args:
            order: Order to add
        """
        book = self.bids if order.side == OrderSide.BUY else self.asks
        price = order.price
        
        # Create price level if it doesn't exist
        if price not in book:
            book[price] = PriceLevel(price, order.side)
        
        # Add order to level
        book[price].add_order(order)
    
    def _remove_from_price_level(self, order: Order) -> None:
        """
        Remove order from its price level.
        
        Args:
            order: Order to remove
        """
        book = self.bids if order.side == OrderSide.BUY else self.asks
        price = order.price
        
        if price not in book:
            return
        
        level = book[price]
        level.remove_order(order.order_id)
        
        # Clean up empty level
        if level.is_empty():
            self._cleanup_empty_levels()
    
    def _cleanup_empty_levels(self) -> None:
        """Remove empty price levels from the book."""
        # Clean up empty bid levels
        empty_bids = [price for price, level in self.bids.items() if level.is_empty()]
        for price in empty_bids:
            del self.bids[price]
        
        # Clean up empty ask levels
        empty_asks = [price for price, level in self.asks.items() if level.is_empty()]
        for price in empty_asks:
            del self.asks[price]
    
    def _update_bbo(self) -> None:
        """Update the BBO manager with current best prices."""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        self.bbo_manager.update_bbo(best_bid, best_ask)
    
    def get_price_levels(self, side: OrderSide, levels: int = 10) -> List[Tuple[Decimal, Decimal]]:
        """
        Get price levels for a specific side.
        
        Args:
            side: BUY or SELL
            levels: Number of levels to return
            
        Returns:
            List of (price, volume) tuples
        """
        book = self.bids if side == OrderSide.BUY else self.asks
        result = []
        
        for i, (price, level) in enumerate(book.items()):
            if i >= levels:
                break
            result.append((price, level.total_volume))
        
        return result
    
    def __repr__(self) -> str:
        """String representation of the order book."""
        return (
            f"OrderBook({self.symbol}: "
            f"{len(self.bids)} bid levels, {len(self.asks)} ask levels, "
            f"BBO={self.best_bid}/{self.best_ask}, "
            f"{len(self.order_registry)} orders)"
        )
