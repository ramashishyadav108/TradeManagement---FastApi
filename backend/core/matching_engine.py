"""
Core matching engine with REG NMS-inspired trade execution logic.

Implements price-time priority matching for all order types (Market, Limit, IOC, FOK)
with strict trade-through prevention and comprehensive execution logic.
"""

import threading
import time
from collections import deque
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Callable
from uuid import UUID, uuid4

from .order import Order, OrderType, OrderSide, OrderStatus, OrderResult
from .trade import Trade
from .order_book import OrderBook
from ..utils.exceptions import (
    InvalidOrderException,
    OrderNotFoundException,
    InsufficientLiquidityException,
    TradeThroughException,
)
from ..utils.logger import get_logger


class MatchingEngine:
    """
    High-performance matching engine for cryptocurrency trading.
    
    Implements REG NMS-inspired principles:
    - Price-time priority matching
    - Trade-through prevention
    - Best execution guarantee
    - Support for multiple order types
    
    Thread-safe with per-symbol locking strategy.
    """
    
    MAX_TRADE_JOURNAL_SIZE = 10000  # Rolling window for trade history
    
    def __init__(self, log_level: str = "INFO"):
        """
        Initialize the matching engine.
        
        Args:
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        """
        self.order_books: Dict[str, OrderBook] = {}
        self.trade_journal: deque = deque(maxlen=self.MAX_TRADE_JOURNAL_SIZE)
        self.execution_callbacks: List[Callable[[Trade], None]] = []
        self.statistics: Dict[str, int] = {
            "orders_processed": 0,
            "trades_executed": 0,
            "total_volume": 0,
            "orders_filled": 0,
            "orders_partial": 0,
            "orders_cancelled": 0,
        }
        self.lock = threading.Lock()
        self.logger = get_logger(log_level=log_level)
        
        # Performance tracking
        self._order_latencies: List[float] = []
        self._last_metrics_log = time.time()
    
    def submit_order(self, order: Order) -> OrderResult:
        """
        Submit an order to the matching engine.
        
        Args:
            order: Order to submit
            
        Returns:
            OrderResult with execution details
            
        Raises:
            InvalidOrderException: If order validation fails
        """
        start_time = time.time()
        
        try:
            # Validate order
            order.validate()
            
            # Log order submission
            self.logger.log_order_submission(
                order.order_id,
                order.symbol,
                order.order_type.value,
                order.side.value,
                order.quantity,
                order.price,
            )
            
            with self.lock:
                # Get or create order book for symbol
                order_book = self._get_or_create_order_book(order.symbol)
                
                # Process order based on type
                if order.order_type == OrderType.MARKET:
                    trades = self._process_market_order(order, order_book)
                elif order.order_type == OrderType.LIMIT:
                    trades = self._process_limit_order(order, order_book)
                elif order.order_type == OrderType.IOC:
                    trades = self._process_ioc_order(order, order_book)
                elif order.order_type == OrderType.FOK:
                    trades = self._process_fok_order(order, order_book)
                else:
                    raise InvalidOrderException(f"Unsupported order type: {order.order_type}")
                
                # Update statistics
                self.statistics["orders_processed"] += 1
                if order.is_fully_filled:
                    self.statistics["orders_filled"] += 1
                elif order.filled_quantity > 0:
                    self.statistics["orders_partial"] += 1
                elif order.status == OrderStatus.CANCELLED:
                    self.statistics["orders_cancelled"] += 1
                
                # Track latency
                latency_ms = (time.time() - start_time) * 1000
                self._order_latencies.append(latency_ms)
                
                # Log performance metrics periodically
                if self.statistics["orders_processed"] % 1000 == 0:
                    self._log_performance_metrics()
                
                # Create result
                result = OrderResult(
                    order=order,
                    trades=trades,
                    status=order.status,
                    message=self._generate_result_message(order, trades),
                    timestamp=datetime.now(timezone.utc),
                )
                
                return result
                
        except Exception as e:
            self.logger.log_error(f"Error processing order {order.order_id}", e)
            raise
    
    def cancel_order(self, order_id: UUID, symbol: str) -> bool:
        """
        Cancel an existing order.
        
        Args:
            order_id: ID of the order to cancel
            symbol: Trading symbol
            
        Returns:
            True if order was cancelled, False otherwise
            
        Raises:
            OrderNotFoundException: If order doesn't exist
        """
        with self.lock:
            order_book = self.order_books.get(symbol)
            if not order_book:
                raise OrderNotFoundException(f"No order book for symbol {symbol}")
            
            order = order_book.remove_order(order_id)
            if not order:
                raise OrderNotFoundException(f"Order {order_id} not found")
            
            order.status = OrderStatus.CANCELLED
            self.logger.log_order_cancellation(order_id, symbol)
            self.statistics["orders_cancelled"] += 1
            
            return True
    
    def get_order_status(self, order_id: UUID, symbol: str) -> Optional[Order]:
        """
        Get the current status of an order.
        
        Args:
            order_id: ID of the order
            symbol: Trading symbol
            
        Returns:
            Order if found, None otherwise
        """
        with self.lock:
            order_book = self.order_books.get(symbol)
            if not order_book:
                return None
            
            return order_book.get_order(order_id)
    
    def register_execution_callback(self, callback: Callable[[Trade], None]):
        """
        Register a callback to be notified of trade executions.
        
        Args:
            callback: Function to call with Trade object
        """
        self.execution_callbacks.append(callback)
    
    def get_statistics(self) -> Dict[str, any]:
        """
        Get current engine statistics.
        
        Returns:
            Dictionary of statistics
        """
        with self.lock:
            stats = self.statistics.copy()
            
            if self._order_latencies:
                stats["avg_latency_ms"] = sum(self._order_latencies) / len(self._order_latencies)
                stats["max_latency_ms"] = max(self._order_latencies)
                stats["min_latency_ms"] = min(self._order_latencies)
            
            return stats
    
    def get_order_book(self, symbol: str) -> Optional[OrderBook]:
        """Get order book for a symbol."""
        return self.order_books.get(symbol)
    
    def register_trade_callback(self, callback: Callable[[Trade, UUID], None]) -> None:
        """
        Register a callback to be invoked when trades are executed.
        
        Args:
            callback: Function to call with (trade, taker_order_id) when trade executes
        """
        self.execution_callbacks.append(callback)
        self.logger.info(f"Registered trade callback. Total callbacks: {len(self.execution_callbacks)}")
    
    def unregister_trade_callback(self, callback: Callable[[Trade, UUID], None]) -> None:
        """
        Unregister a trade callback.
        
        Args:
            callback: Callback function to remove
        """
        if callback in self.execution_callbacks:
            self.execution_callbacks.remove(callback)
            self.logger.info(f"Unregistered trade callback. Total callbacks: {len(self.execution_callbacks)}")
    
    # Private matching methods
    
    def _process_market_order(self, order: Order, order_book: OrderBook) -> List[Trade]:
        """
        Process a market order.
        
        Market orders execute immediately at best available prices.
        If partially filled, remaining quantity is cancelled.
        
        Args:
            order: Market order to process
            order_book: Order book for the symbol
            
        Returns:
            List of trades generated
        """
        trades = self._fill_against_book(order, order_book)
        
        # Add to registry so it can be queried
        order_book.order_registry[order.order_id] = order
        
        # Market orders don't rest on book - cancel unfilled portion
        if not order.is_fully_filled:
            order.status = OrderStatus.CANCELLED if not trades else OrderStatus.PARTIAL
            self.logger.info(
                f"Market order {order.order_id} partially filled: "
                f"{order.filled_quantity}/{order.quantity}"
            )
        
        return trades
    
    def _process_limit_order(self, order: Order, order_book: OrderBook) -> List[Trade]:
        """
        Process a limit order.
        
        Limit orders execute at specified price or better.
        Unfilled portion rests on the order book.
        
        Args:
            order: Limit order to process
            order_book: Order book for the symbol
            
        Returns:
            List of trades generated
        """
        if order.price is None:
            raise InvalidOrderException("Limit order must have a price")
        
        # Check if order is marketable
        trades = []
        if self._is_marketable(order, order_book):
            # Execute marketable portion
            trades = self._fill_against_book(order, order_book, limit_price=order.price)
        
        # Add unfilled portion to order book (or just to registry if fully filled)
        if not order.is_fully_filled:
            order_book.add_order(order)
            order.status = OrderStatus.PARTIAL if trades else OrderStatus.PENDING
        else:
            # Fully filled - add to registry only so it can be queried
            order_book.order_registry[order.order_id] = order
        
        return trades
    
    def _process_ioc_order(self, order: Order, order_book: OrderBook) -> List[Trade]:
        """
        Process an Immediate-Or-Cancel order.
        
        IOC orders execute immediately and cancel unfilled portion.
        
        Args:
            order: IOC order to process
            order_book: Order book for the symbol
            
        Returns:
            List of trades generated
        """
        # Execute what we can immediately
        trades = self._fill_against_book(order, order_book, limit_price=order.price)
        
        # Add to registry so it can be queried
        order_book.order_registry[order.order_id] = order
        
        # Cancel unfilled portion (don't add to book)
        if not order.is_fully_filled:
            order.status = OrderStatus.CANCELLED if not trades else OrderStatus.PARTIAL
            self.logger.info(
                f"IOC order {order.order_id} partially filled and cancelled: "
                f"{order.filled_quantity}/{order.quantity}"
            )
        
        return trades
    
    def _process_fok_order(self, order: Order, order_book: OrderBook) -> List[Trade]:
        """
        Process a Fill-Or-Kill order.
        
        FOK orders either fill completely or cancel entirely (atomic).
        
        Args:
            order: FOK order to process
            order_book: Order book for the symbol
            
        Returns:
            List of trades generated (empty if order was killed)
        """
        # Add to registry so it can be queried
        order_book.order_registry[order.order_id] = order
        
        # Check if we can fill the entire order
        can_fill, fill_plan = self._check_can_fill_fok(order, order_book)
        
        if not can_fill:
            # Kill the order
            order.status = OrderStatus.CANCELLED
            self.logger.info(f"FOK order {order.order_id} killed - insufficient liquidity")
            return []
        
        # Execute the entire order atomically
        trades = []
        for maker_order, fill_quantity in fill_plan:
            trade = self._execute_match(
                taker_order=order,
                maker_order=maker_order,
                quantity=fill_quantity,
                price=maker_order.price,
                order_book=order_book
            )
            trades.append(trade)
        
        return trades
    
    def _fill_against_book(
        self,
        order: Order,
        order_book: OrderBook,
        limit_price: Optional[Decimal] = None,
    ) -> List[Trade]:
        """
        Fill an order against the order book.
        
        Walks through price levels filling the order at best available prices.
        
        Args:
            order: Order to fill
            order_book: Order book to match against
            limit_price: Price limit (None for market orders)
            
        Returns:
            List of trades generated
        """
        trades = []
        
        # Determine which side of the book to match against
        if order.is_buy:
            # Buy orders match against asks
            levels = order_book.asks
        else:
            # Sell orders match against bids
            levels = order_book.bids
        
        # Debug logging
        self.logger.debug(f"Fill against book - Order: {order.side.value} {order.quantity} @ {limit_price}")
        self.logger.debug(f"Levels to match: {list(levels.keys())}")
        
        # Iterate through price levels
        prices_to_remove = []
        
        for price in list(levels.keys()):
            self.logger.debug(f"Processing price level: {price}")
            
            if order.is_fully_filled:
                break
            
            # Check price limit
            if limit_price is not None:
                if order.is_buy and price > limit_price:
                    self.logger.debug(f"Price {price} > limit {limit_price}, stopping")
                    break
                if order.is_sell and price < limit_price:
                    self.logger.debug(f"Price {price} < limit {limit_price}, stopping")
                    break
            
            price_level = levels[price]
            
            # Match against orders at this price level (FIFO)
            while not price_level.is_empty() and not order.is_fully_filled:
                maker_order = price_level.get_next_order()
                if not maker_order:
                    break
                
                # Calculate fill quantity
                fill_quantity = min(order.remaining_quantity, maker_order.remaining_quantity)
                
                # Execute the trade (this will remove maker from book if fully filled)
                trade = self._execute_match(
                    taker_order=order,
                    maker_order=maker_order,
                    quantity=fill_quantity,
                    price=price,
                    order_book=order_book
                )
                trades.append(trade)
                
                # Note: _execute_match already removes fully filled makers via order_book.remove_order()
                # which also calls price_level.remove_order(), so we don't need to pop_next_order() here
        
        # Note: Empty price levels are cleaned up automatically by order_book.remove_order()
        # so we don't need to manually delete them here
        
        return trades
    
    def _execute_match(
        self,
        taker_order: Order,
        maker_order: Order,
        quantity: Decimal,
        price: Decimal,
        order_book: OrderBook
    ) -> Trade:
        """
        Execute a match between two orders.
        
        Args:
            taker_order: Incoming order (aggressor)
            maker_order: Resting order (maker)
            quantity: Quantity to match
            price: Execution price
            order_book: Order book for the symbol
            
        Returns:
            Trade object representing the execution
        """
        # Update order quantities
        taker_order.update_fill(quantity)
        maker_order.update_fill(quantity)
        
        # If maker is fully filled, remove from book but keep in registry for querying
        if maker_order.is_fully_filled:
            order_book.remove_from_book_only(maker_order.order_id)
        
        # Create trade
        trade = Trade(
            trade_id=uuid4(),
            symbol=taker_order.symbol,
            price=price,
            quantity=quantity,
            timestamp=datetime.now(timezone.utc),
            aggressor_side=taker_order.side,
            maker_order_id=maker_order.order_id,
            taker_order_id=taker_order.order_id,
        )
        
        # Add to trade journal
        self.trade_journal.append(trade)
        
        # Invoke trade callbacks
        for callback in self.execution_callbacks:
            try:
                callback(trade, taker_order.order_id)
            except Exception as e:
                self.logger.error(f"Error in trade callback: {str(e)}")
        
        # Update statistics
        self.statistics["trades_executed"] += 1
        self.statistics["total_volume"] += float(quantity)
        
        # Log trade execution
        self.logger.log_trade_execution(
            trade.trade_id,
            trade.symbol,
            trade.price,
            trade.quantity,
            trade.aggressor_side.value,
            trade.maker_order_id,
            trade.taker_order_id,
        )
        
        # Notify callbacks
        self._notify_execution(trade)
        
        return trade
    
    def _check_can_fill_fok(
        self,
        order: Order,
        order_book: OrderBook
    ) -> Tuple[bool, List[Tuple[Order, Decimal]]]:
        """
        Check if a FOK order can be completely filled.
        
        Args:
            order: FOK order to check
            order_book: Order book to check against
            
        Returns:
            Tuple of (can_fill, fill_plan) where fill_plan is list of (order, quantity) tuples
        """
        fill_plan = []
        remaining = order.quantity
        
        # Determine which side of the book to check
        if order.is_buy:
            levels = order_book.asks
        else:
            levels = order_book.bids
        
        # Scan price levels
        for price in list(levels.keys()):
            if remaining == 0:
                break
            
            # Check price limit
            if order.price is not None:
                if order.is_buy and price > order.price:
                    break
                if order.is_sell and price < order.price:
                    break
            
            price_level = levels[price]
            
            # Check orders at this price level
            for maker_order in price_level.orders:
                if remaining == 0:
                    break
                
                fill_quantity = min(remaining, maker_order.remaining_quantity)
                fill_plan.append((maker_order, fill_quantity))
                remaining -= fill_quantity
        
        can_fill = (remaining == 0)
        return can_fill, fill_plan if can_fill else []
    
    def _prevent_trade_through(
        self,
        order: Order,
        execution_price: Decimal,
        order_book: OrderBook
    ) -> bool:
        """
        Prevent trade-through by validating execution price against BBO.
        
        Args:
            order: Order being executed
            execution_price: Proposed execution price
            order_book: Current order book
            
        Returns:
            True if execution is valid, False if trade-through detected
        """
        best_bid, best_ask = order_book.get_bbo()
        
        if order.is_buy:
            # Buy order should not execute above best ask
            if best_ask is not None and execution_price > best_ask:
                return False
        else:
            # Sell order should not execute below best bid
            if best_bid is not None and execution_price < best_bid:
                return False
        
        return True
    
    def _is_marketable(self, order: Order, order_book: OrderBook) -> bool:
        """
        Check if an order is immediately marketable.
        
        Args:
            order: Order to check
            order_book: Current order book
            
        Returns:
            True if order can be immediately executed
        """
        if order.price is None:
            return True  # Market orders are always marketable
        
        best_bid, best_ask = order_book.get_bbo()
        
        if order.is_buy:
            # Buy is marketable if price >= best ask
            return best_ask is not None and order.price >= best_ask
        else:
            # Sell is marketable if price <= best bid
            return best_bid is not None and order.price <= best_bid
    
    def _get_or_create_order_book(self, symbol: str) -> OrderBook:
        """Get existing order book or create new one for symbol."""
        if symbol not in self.order_books:
            self.order_books[symbol] = OrderBook(symbol)
            self.logger.info(f"Created new order book for {symbol}")
        
        return self.order_books[symbol]
    
    def _notify_execution(self, trade: Trade):
        """Notify registered callbacks of trade execution."""
        for callback in self.execution_callbacks:
            try:
                callback(trade)
            except Exception as e:
                self.logger.log_error(f"Error in execution callback", e)
    
    def _update_statistics(self, trade: Trade):
        """Update engine statistics with trade information."""
        self.statistics["trades_executed"] += 1
        self.statistics["total_volume"] += float(trade.quantity)
    
    def _generate_trade_id(self) -> str:
        """Generate unique trade identifier."""
        return str(uuid4())
    
    def _generate_result_message(self, order: Order, trades: List[Trade]) -> str:
        """Generate human-readable result message."""
        if order.is_fully_filled:
            return f"Order fully filled: {order.filled_quantity} @ avg price"
        elif order.filled_quantity > 0:
            return f"Order partially filled: {order.filled_quantity}/{order.quantity}"
        elif order.status == OrderStatus.CANCELLED:
            return "Order cancelled - no fill"
        elif order.status == OrderStatus.PENDING:
            return "Order added to book"
        else:
            return "Order processed"
    
    def _log_performance_metrics(self):
        """Log performance metrics periodically."""
        if not self._order_latencies:
            return
        
        avg_latency = sum(self._order_latencies) / len(self._order_latencies)
        max_latency = max(self._order_latencies)
        
        self.logger.log_performance_metrics(
            self.statistics["orders_processed"],
            self.statistics["trades_executed"],
            avg_latency,
            max_latency,
        )
        
        # Reset latency tracking
        self._order_latencies = []

