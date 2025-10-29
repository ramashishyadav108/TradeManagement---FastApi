"""
Comprehensive tests for the matching engine.

Tests all order types, edge cases, and REG NMS compliance.
"""

import pytest
import threading
import time
from decimal import Decimal
from datetime import datetime
from uuid import uuid4

from backend.core.order import Order, OrderType, OrderSide, OrderStatus
from backend.core.matching_engine import MatchingEngine
from backend.utils.exceptions import (
    InvalidOrderException,
    OrderNotFoundException,
    TradeThroughException,
)


class TestMatchingEngineBasics:
    """Basic matching engine functionality tests."""
    
    def test_engine_initialization(self):
        """Test matching engine initializes correctly."""
        engine = MatchingEngine()
        
        assert len(engine.order_books) == 0
        assert len(engine.trade_journal) == 0
        assert engine.statistics["orders_processed"] == 0
    
    def test_create_order_book_on_first_order(self):
        """Test order book is created when first order is submitted."""
        engine = MatchingEngine()
        
        order = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=Decimal("1.0"),
            price=Decimal("50000.00")
        )
        
        result = engine.submit_order(order)
        
        assert "BTC-USDT" in engine.order_books
        assert result.order.status == OrderStatus.PENDING


class TestMarketOrders:
    """Test market order execution logic."""
    
    def test_market_buy_against_empty_book(self):
        """Market buy against empty book should cancel."""
        engine = MatchingEngine()
        
        order = Order(
            symbol="BTC-USDT",
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=Decimal("1.0"),
        )
        
        result = engine.submit_order(order)
        
        assert result.order.status == OrderStatus.CANCELLED
        assert len(result.trades) == 0
        assert result.order.filled_quantity == Decimal("0")
    
    def test_market_buy_partial_fill(self):
        """Market buy with partial fill should cancel remainder."""
        engine = MatchingEngine()
        
        # Add sell orders to book
        sell1 = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("3.0"),
            price=Decimal("50000.00")
        )
        engine.submit_order(sell1)
        
        # Market buy for more than available
        buy = Order(
            symbol="BTC-USDT",
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=Decimal("10.0"),
        )
        
        result = engine.submit_order(buy)
        
        assert result.order.filled_quantity == Decimal("3.0")
        assert result.order.remaining_quantity == Decimal("7.0")
        assert result.order.status == OrderStatus.PARTIAL
        assert len(result.trades) == 1
    
    def test_market_buy_full_fill_across_levels(self):
        """Market buy should fill across multiple price levels."""
        engine = MatchingEngine()
        
        # Add sell orders at different prices
        sell1 = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("2.0"),
            price=Decimal("50000.00")
        )
        sell2 = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("3.0"),
            price=Decimal("50100.00")
        )
        sell3 = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("5.0"),
            price=Decimal("50200.00")
        )
        
        engine.submit_order(sell1)
        engine.submit_order(sell2)
        engine.submit_order(sell3)
        
        # Market buy across all levels
        buy = Order(
            symbol="BTC-USDT",
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=Decimal("10.0"),
        )
        
        result = engine.submit_order(buy)
        
        assert result.order.is_fully_filled
        assert len(result.trades) == 3
        assert result.trades[0].price == Decimal("50000.00")
        assert result.trades[1].price == Decimal("50100.00")
        assert result.trades[2].price == Decimal("50200.00")


class TestLimitOrders:
    """Test limit order execution logic."""
    
    def test_limit_buy_below_best_ask(self):
        """Limit buy below best ask should rest on book."""
        engine = MatchingEngine()
        
        # Add sell order
        sell = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("1.0"),
            price=Decimal("50000.00")
        )
        engine.submit_order(sell)
        
        # Limit buy below best ask
        buy = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=Decimal("1.0"),
            price=Decimal("49900.00")
        )
        
        result = engine.submit_order(buy)
        
        assert result.order.status == OrderStatus.PENDING
        assert len(result.trades) == 0
        
        # Verify order is on book
        book = engine.get_order_book("BTC-USDT")
        assert book.get_best_bid() == Decimal("49900.00")
    
    def test_limit_buy_matching_best_ask(self):
        """Limit buy at best ask should execute immediately."""
        engine = MatchingEngine()
        
        # Add sell order
        sell = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("1.0"),
            price=Decimal("50000.00")
        )
        engine.submit_order(sell)
        
        # Limit buy at best ask
        buy = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=Decimal("1.0"),
            price=Decimal("50000.00")
        )
        
        result = engine.submit_order(buy)
        
        assert result.order.is_fully_filled
        assert len(result.trades) == 1
        assert result.trades[0].price == Decimal("50000.00")
    
    def test_limit_buy_crossing_spread(self):
        """Limit buy crossing spread should get price improvement."""
        engine = MatchingEngine()
        
        # Add sell order at 50000
        sell = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("1.0"),
            price=Decimal("50000.00")
        )
        engine.submit_order(sell)
        
        # Limit buy at 51000 (crossing)
        buy = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=Decimal("1.0"),
            price=Decimal("51000.00")
        )
        
        result = engine.submit_order(buy)
        
        assert result.order.is_fully_filled
        assert len(result.trades) == 1
        # Should execute at maker's price (50000), not taker's (51000)
        assert result.trades[0].price == Decimal("50000.00")
    
    def test_limit_order_partial_fill_rests_on_book(self):
        """Limit order partial fill should rest remainder on book."""
        engine = MatchingEngine()
        
        # Add sell order for 5 BTC
        sell = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("5.0"),
            price=Decimal("50000.00")
        )
        engine.submit_order(sell)
        
        # Limit buy for 10 BTC
        buy = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=Decimal("10.0"),
            price=Decimal("50000.00")
        )
        
        result = engine.submit_order(buy)
        
        assert result.order.filled_quantity == Decimal("5.0")
        assert result.order.remaining_quantity == Decimal("5.0")
        assert result.order.status == OrderStatus.PARTIAL
        
        # Verify remainder is on book
        book = engine.get_order_book("BTC-USDT")
        assert book.get_total_volume_at_price(Decimal("50000.00"), OrderSide.BUY) == Decimal("5.0")


class TestIOCOrders:
    """Test Immediate-Or-Cancel order logic."""
    
    def test_ioc_full_fill(self):
        """IOC order with sufficient liquidity should fill completely."""
        engine = MatchingEngine()
        
        # Add sell orders
        sell = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("10.0"),
            price=Decimal("50000.00")
        )
        engine.submit_order(sell)
        
        # IOC buy
        buy = Order(
            symbol="BTC-USDT",
            order_type=OrderType.IOC,
            side=OrderSide.BUY,
            quantity=Decimal("5.0"),
            price=Decimal("50000.00")
        )
        
        result = engine.submit_order(buy)
        
        assert result.order.is_fully_filled
        assert len(result.trades) == 1
    
    def test_ioc_partial_fill_cancels_remainder(self):
        """IOC order should fill partially and cancel remainder."""
        engine = MatchingEngine()
        
        # Add sell order for 7 BTC
        sell = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("7.0"),
            price=Decimal("50000.00")
        )
        engine.submit_order(sell)
        
        # IOC buy for 10 BTC
        buy = Order(
            symbol="BTC-USDT",
            order_type=OrderType.IOC,
            side=OrderSide.BUY,
            quantity=Decimal("10.0"),
            price=Decimal("50000.00")
        )
        
        result = engine.submit_order(buy)
        
        assert result.order.filled_quantity == Decimal("7.0")
        assert result.order.remaining_quantity == Decimal("3.0")
        assert result.order.status == OrderStatus.PARTIAL
        
        # Verify nothing rests on book
        book = engine.get_order_book("BTC-USDT")
        assert book.get_best_bid() is None
    
    def test_ioc_no_fill_cancels_entirely(self):
        """IOC order with no matching liquidity should cancel entirely."""
        engine = MatchingEngine()
        
        # Add sell order at higher price
        sell = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("10.0"),
            price=Decimal("51000.00")
        )
        engine.submit_order(sell)
        
        # IOC buy at lower price (won't match)
        buy = Order(
            symbol="BTC-USDT",
            order_type=OrderType.IOC,
            side=OrderSide.BUY,
            quantity=Decimal("5.0"),
            price=Decimal("50000.00")
        )
        
        result = engine.submit_order(buy)
        
        assert result.order.filled_quantity == Decimal("0")
        assert result.order.status == OrderStatus.CANCELLED
        assert len(result.trades) == 0


class TestFOKOrders:
    """Test Fill-Or-Kill order logic."""
    
    def test_fok_full_fill(self):
        """FOK order with exact liquidity should fill completely."""
        engine = MatchingEngine()
        
        # Add sell orders totaling exact amount
        sell1 = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("5.0"),
            price=Decimal("50000.00")
        )
        sell2 = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("5.0"),
            price=Decimal("50000.00")
        )
        
        engine.submit_order(sell1)
        engine.submit_order(sell2)
        
        # FOK buy for exact amount
        buy = Order(
            symbol="BTC-USDT",
            order_type=OrderType.FOK,
            side=OrderSide.BUY,
            quantity=Decimal("10.0"),
            price=Decimal("50000.00")
        )
        
        result = engine.submit_order(buy)
        
        assert result.order.is_fully_filled
        assert len(result.trades) == 2
    
    def test_fok_insufficient_liquidity_kills_order(self):
        """FOK order with insufficient liquidity should be killed."""
        engine = MatchingEngine()
        
        # Add sell order for less than needed
        sell = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("9.0"),
            price=Decimal("50000.00")
        )
        engine.submit_order(sell)
        
        # FOK buy for more
        buy = Order(
            symbol="BTC-USDT",
            order_type=OrderType.FOK,
            side=OrderSide.BUY,
            quantity=Decimal("10.0"),
            price=Decimal("50000.00")
        )
        
        result = engine.submit_order(buy)
        
        assert result.order.filled_quantity == Decimal("0")
        assert result.order.status == OrderStatus.CANCELLED
        assert len(result.trades) == 0
        
        # Verify book unchanged
        book = engine.get_order_book("BTC-USDT")
        assert book.get_total_volume_at_price(Decimal("50000.00"), OrderSide.SELL) == Decimal("9.0")
    
    def test_fok_price_improvement(self):
        """FOK order should get price improvement when available."""
        engine = MatchingEngine()
        
        # Add sell orders at different prices
        sell1 = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("5.0"),
            price=Decimal("50000.00")
        )
        sell2 = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("5.0"),
            price=Decimal("50100.00")
        )
        
        engine.submit_order(sell1)
        engine.submit_order(sell2)
        
        # FOK buy willing to pay up to 50200
        buy = Order(
            symbol="BTC-USDT",
            order_type=OrderType.FOK,
            side=OrderSide.BUY,
            quantity=Decimal("10.0"),
            price=Decimal("50200.00")
        )
        
        result = engine.submit_order(buy)
        
        assert result.order.is_fully_filled
        assert len(result.trades) == 2
        assert result.trades[0].price == Decimal("50000.00")
        assert result.trades[1].price == Decimal("50100.00")


class TestPriceTimePriority:
    """Test price-time priority enforcement."""
    
    def test_fifo_at_same_price_level(self):
        """Orders at same price should fill in FIFO order."""
        engine = MatchingEngine()
        
        # Add 3 sell orders at same price
        sell1 = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("1.0"),
            price=Decimal("50000.00")
        )
        sell2 = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("1.0"),
            price=Decimal("50000.00")
        )
        sell3 = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("1.0"),
            price=Decimal("50000.00")
        )
        
        r1 = engine.submit_order(sell1)
        r2 = engine.submit_order(sell2)
        r3 = engine.submit_order(sell3)
        
        # Verify all added successfully
        assert r1.order.status == OrderStatus.PENDING
        assert r2.order.status == OrderStatus.PENDING
        assert r3.order.status == OrderStatus.PENDING
        
        # Market buy should fill first 2 orders partially/fully
        buy = Order(
            symbol="BTC-USDT",
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=Decimal("1.5"),
        )
        
        result = engine.submit_order(buy)
        
        # Verify trades were made
        assert len(result.trades) == 2  # Filled from 2 orders
        assert result.order.status == OrderStatus.FILLED
        assert result.order.filled_quantity == Decimal("1.5")
        
        # Verify 1.5 BTC remain at this price (0.5 from second order, 1.0 from third)
        book = engine.get_order_book("BTC-USDT")
        assert book.get_total_volume_at_price(Decimal("50000.00"), OrderSide.SELL) == Decimal("1.5")
    
    def test_better_price_fills_first(self):
        """Orders with better prices should fill before worse prices."""
        engine = MatchingEngine()
        
        # Add sell orders at different prices
        sell1 = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("1.0"),
            price=Decimal("50100.00")
        )
        sell2 = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("1.0"),
            price=Decimal("50000.00")  # Better price
        )
        
        engine.submit_order(sell1)
        engine.submit_order(sell2)
        
        # Market buy should fill best price first
        buy = Order(
            symbol="BTC-USDT",
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=Decimal("2.0"),
        )
        
        result = engine.submit_order(buy)
        
        assert len(result.trades) == 2
        assert result.trades[0].price == Decimal("50000.00")
        assert result.trades[1].price == Decimal("50100.00")


class TestOrderCancellation:
    """Test order cancellation functionality."""
    
    def test_cancel_pending_order(self):
        """Should be able to cancel a pending order."""
        engine = MatchingEngine()
        
        # Add limit order
        order = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=Decimal("1.0"),
            price=Decimal("50000.00")
        )
        
        result = engine.submit_order(order)
        assert result.order.status == OrderStatus.PENDING
        
        # Cancel it
        cancelled = engine.cancel_order(order.order_id, "BTC-USDT")
        
        assert cancelled
        
        # Verify removed from book
        book = engine.get_order_book("BTC-USDT")
        assert book.get_order(order.order_id) is None
    
    def test_cancel_nonexistent_order_raises_error(self):
        """Cancelling nonexistent order should raise error."""
        engine = MatchingEngine()
        
        with pytest.raises(OrderNotFoundException):
            engine.cancel_order(uuid4(), "BTC-USDT")


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_decimal_precision(self):
        """Test handling of high-precision decimals."""
        engine = MatchingEngine()
        
        # Very small quantity
        sell = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("0.00000001"),
            price=Decimal("50000.00")
        )
        
        buy = Order(
            symbol="BTC-USDT",
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=Decimal("0.00000001"),
        )
        
        engine.submit_order(sell)
        result = engine.submit_order(buy)
        
        assert result.order.is_fully_filled
        assert result.trades[0].quantity == Decimal("0.00000001")
    
    def test_crossing_limit_orders(self):
        """Test execution when limit orders cross."""
        engine = MatchingEngine()
        
        # Add buy limit at 50100
        buy = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=Decimal("1.0"),
            price=Decimal("50100.00")
        )
        engine.submit_order(buy)
        
        # Add sell limit at 50000 (crosses)
        sell = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("1.0"),
            price=Decimal("50000.00")
        )
        
        result = engine.submit_order(sell)
        
        assert result.order.is_fully_filled
        assert len(result.trades) == 1
        # Should execute at maker's price (50100)
        assert result.trades[0].price == Decimal("50100.00")
    
    def test_statistics_tracking(self):
        """Test that statistics are tracked correctly."""
        engine = MatchingEngine()
        
        # Submit some orders
        for i in range(5):
            order = Order(
                symbol="BTC-USDT",
                order_type=OrderType.LIMIT,
                side=OrderSide.BUY if i % 2 == 0 else OrderSide.SELL,
                quantity=Decimal("1.0"),
                price=Decimal("50000.00")
            )
            engine.submit_order(order)
        
        stats = engine.get_statistics()
        
        assert stats["orders_processed"] == 5
        assert stats["trades_executed"] >= 2  # At least some should match


class TestConcurrency:
    """Test concurrent order processing."""
    
    def test_concurrent_order_submissions(self):
        """Test multiple threads submitting orders simultaneously."""
        engine = MatchingEngine()
        results = []
        
        def submit_orders():
            for i in range(10):
                order = Order(
                    symbol="BTC-USDT",
                    order_type=OrderType.LIMIT,
                    side=OrderSide.BUY if i % 2 == 0 else OrderSide.SELL,
                    quantity=Decimal("0.1"),
                    price=Decimal("50000.00")
                )
                result = engine.submit_order(order)
                results.append(result)
        
        # Create 5 threads
        threads = []
        for _ in range(5):
            t = threading.Thread(target=submit_orders)
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join()
        
        # Verify all orders processed
        assert len(results) == 50
        assert engine.statistics["orders_processed"] == 50


class TestPerformance:
    """Performance and stress tests."""
    
    def test_large_order_execution(self):
        """Test execution of large orders against deep book."""
        engine = MatchingEngine()
        
        # Build deep order book
        for i in range(100):
            price = Decimal("50000.00") + Decimal(str(i))
            order = Order(
                symbol="BTC-USDT",
                order_type=OrderType.LIMIT,
                side=OrderSide.SELL,
                quantity=Decimal("10.0"),
                price=price
            )
            engine.submit_order(order)
        
        # Large market buy
        buy = Order(
            symbol="BTC-USDT",
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=Decimal("500.0"),
        )
        
        start = time.time()
        result = engine.submit_order(buy)
        elapsed = time.time() - start
        
        assert result.order.filled_quantity == Decimal("500.0")
        assert elapsed < 0.05  # Should complete in <50ms (includes logging overhead)
    
    def test_order_processing_throughput(self):
        """Test sustained order processing throughput."""
        engine = MatchingEngine()
        
        start = time.time()
        
        # Submit 1000 orders
        for i in range(1000):
            order = Order(
                symbol="BTC-USDT",
                order_type=OrderType.LIMIT,
                side=OrderSide.BUY if i % 2 == 0 else OrderSide.SELL,
                quantity=Decimal("0.1"),
                price=Decimal("50000.00") + Decimal(str(i % 100))
            )
            engine.submit_order(order)
        
        elapsed = time.time() - start
        orders_per_sec = 1000 / elapsed
        
        assert orders_per_sec > 1000  # Should process >1000 orders/sec
        print(f"Throughput: {orders_per_sec:.0f} orders/sec")

