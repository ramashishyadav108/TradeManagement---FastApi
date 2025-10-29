"""
Unit tests for order book

Comprehensive test suite for order book functionality including
price-time priority, BBO calculation, and edge cases.
"""

import pytest
from decimal import Decimal
from datetime import datetime
import time

from backend.core.order import Order, OrderType, OrderSide, OrderStatus
from backend.core.order_book import OrderBook
from backend.core.price_level import PriceLevel
from backend.utils.exceptions import DuplicateOrderException, OrderBookException


class TestPriceLevel:
    """Test cases for PriceLevel class."""
    
    def test_price_level_creation(self):
        """Test creating a price level."""
        level = PriceLevel(Decimal("50000"), OrderSide.BUY)
        assert level.price == Decimal("50000")
        assert level.side == OrderSide.BUY
        assert level.is_empty()
        assert level.order_count == 0
    
    def test_add_order_to_level(self):
        """Test adding order to price level."""
        level = PriceLevel(Decimal("50000"), OrderSide.BUY)
        order = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=Decimal("1.0"),
            price=Decimal("50000")
        )
        
        level.add_order(order)
        assert level.order_count == 1
        assert not level.is_empty()
        assert level.total_volume == Decimal("1.0")
    
    def test_fifo_ordering(self):
        """Test FIFO order processing."""
        level = PriceLevel(Decimal("50000"), OrderSide.BUY)
        
        # Add 3 orders
        order1 = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=Decimal("1.0"),
            price=Decimal("50000")
        )
        time.sleep(0.001)  # Ensure different timestamps
        
        order2 = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=Decimal("2.0"),
            price=Decimal("50000")
        )
        time.sleep(0.001)
        
        order3 = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=Decimal("3.0"),
            price=Decimal("50000")
        )
        
        level.add_order(order1)
        level.add_order(order2)
        level.add_order(order3)
        
        # Verify FIFO order
        assert level.pop_next_order() == order1
        assert level.pop_next_order() == order2
        assert level.pop_next_order() == order3
        assert level.is_empty()
    
    def test_remove_order(self):
        """Test removing order from level."""
        level = PriceLevel(Decimal("50000"), OrderSide.BUY)
        
        order1 = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=Decimal("1.0"),
            price=Decimal("50000")
        )
        order2 = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=Decimal("2.0"),
            price=Decimal("50000")
        )
        
        level.add_order(order1)
        level.add_order(order2)
        
        removed = level.remove_order(order1.order_id)
        assert removed == order1
        assert level.order_count == 1
        assert level.get_next_order() == order2


class TestOrderBook:
    """Test cases for OrderBook class."""
    
    def test_orderbook_creation(self):
        """Test creating an order book."""
        book = OrderBook("BTC-USDT")
        assert book.symbol == "BTC-USDT"
        assert book.best_bid is None
        assert book.best_ask is None
        assert len(book.order_registry) == 0
    
    def test_add_buy_order(self):
        """Test adding a buy order."""
        book = OrderBook("BTC-USDT")
        order = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=Decimal("1.0"),
            price=Decimal("50000")
        )
        
        book.add_order(order)
        assert book.best_bid == Decimal("50000")
        assert book.best_ask is None
        assert len(book.order_registry) == 1
    
    def test_add_sell_order(self):
        """Test adding a sell order."""
        book = OrderBook("BTC-USDT")
        order = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("1.0"),
            price=Decimal("51000")
        )
        
        book.add_order(order)
        assert book.best_bid is None
        assert book.best_ask == Decimal("51000")
        assert len(book.order_registry) == 1
    
    def test_bbo_calculation(self):
        """Test BBO calculation with multiple orders."""
        book = OrderBook("BTC-USDT")
        
        # Add buy orders
        buy1 = Order("BTC-USDT", OrderType.LIMIT, OrderSide.BUY, Decimal("1.0"), Decimal("50000"))
        buy2 = Order("BTC-USDT", OrderType.LIMIT, OrderSide.BUY, Decimal("2.0"), Decimal("49999"))
        buy3 = Order("BTC-USDT", OrderType.LIMIT, OrderSide.BUY, Decimal("3.0"), Decimal("49998"))
        
        # Add sell orders
        sell1 = Order("BTC-USDT", OrderType.LIMIT, OrderSide.SELL, Decimal("1.0"), Decimal("51000"))
        sell2 = Order("BTC-USDT", OrderType.LIMIT, OrderSide.SELL, Decimal("2.0"), Decimal("51001"))
        sell3 = Order("BTC-USDT", OrderType.LIMIT, OrderSide.SELL, Decimal("3.0"), Decimal("51002"))
        
        book.add_order(buy1)
        book.add_order(buy2)
        book.add_order(buy3)
        book.add_order(sell1)
        book.add_order(sell2)
        book.add_order(sell3)
        
        # Verify BBO
        assert book.best_bid == Decimal("50000")
        assert book.best_ask == Decimal("51000")
        assert book.spread == Decimal("1000")
        assert book.mid_price == Decimal("50500")
    
    def test_price_time_priority(self):
        """Test price-time priority with orders at same price."""
        book = OrderBook("BTC-USDT")
        
        # Add 3 orders at same price with slight time delays
        order1 = Order("BTC-USDT", OrderType.LIMIT, OrderSide.BUY, Decimal("1.0"), Decimal("50000"))
        time.sleep(0.001)
        order2 = Order("BTC-USDT", OrderType.LIMIT, OrderSide.BUY, Decimal("2.0"), Decimal("50000"))
        time.sleep(0.001)
        order3 = Order("BTC-USDT", OrderType.LIMIT, OrderSide.BUY, Decimal("3.0"), Decimal("50000"))
        
        book.add_order(order1)
        book.add_order(order2)
        book.add_order(order3)
        
        # Get the price level
        level = book.bids[Decimal("50000")]
        
        # Verify FIFO order
        assert level.get_next_order() == order1
        level.pop_next_order()
        assert level.get_next_order() == order2
        level.pop_next_order()
        assert level.get_next_order() == order3
    
    def test_remove_order(self):
        """Test order removal and book cleanup."""
        book = OrderBook("BTC-USDT")
        
        order = Order("BTC-USDT", OrderType.LIMIT, OrderSide.BUY, Decimal("1.0"), Decimal("50000"))
        book.add_order(order)
        
        assert book.best_bid == Decimal("50000")
        
        removed = book.remove_order(order.order_id)
        assert removed == order
        assert book.best_bid is None
        assert len(book.order_registry) == 0
    
    def test_duplicate_order(self):
        """Test that duplicate orders are rejected."""
        book = OrderBook("BTC-USDT")
        
        order = Order("BTC-USDT", OrderType.LIMIT, OrderSide.BUY, Decimal("1.0"), Decimal("50000"))
        book.add_order(order)
        
        with pytest.raises(DuplicateOrderException):
            book.add_order(order)
    
    def test_order_book_depth(self):
        """Test getting order book depth."""
        book = OrderBook("BTC-USDT")
        
        # Add multiple levels
        for i in range(5):
            buy_price = Decimal("50000") - Decimal(str(i * 100))
            sell_price = Decimal("51000") + Decimal(str(i * 100))
            
            book.add_order(Order("BTC-USDT", OrderType.LIMIT, OrderSide.BUY, Decimal("1.0"), buy_price))
            book.add_order(Order("BTC-USDT", OrderType.LIMIT, OrderSide.SELL, Decimal("1.0"), sell_price))
        
        depth = book.get_depth(levels=5)
        
        assert len(depth["bids"]) == 5
        assert len(depth["asks"]) == 5
        assert depth["best_bid"] == "50000"
        assert depth["best_ask"] == "51000"
    
    def test_empty_book(self):
        """Test operations on empty order book."""
        book = OrderBook("BTC-USDT")
        
        assert book.best_bid is None
        assert book.best_ask is None
        assert book.spread is None
        assert book.mid_price is None
        
        depth = book.get_depth()
        assert len(depth["bids"]) == 0
        assert len(depth["asks"]) == 0
    
    def test_single_sided_book(self):
        """Test book with only bids or only asks."""
        book = OrderBook("BTC-USDT")
        
        # Add only buy orders
        book.add_order(Order("BTC-USDT", OrderType.LIMIT, OrderSide.BUY, Decimal("1.0"), Decimal("50000")))
        
        assert book.best_bid == Decimal("50000")
        assert book.best_ask is None
        assert book.spread is None
        assert book.mid_price is None
    
    def test_decimal_precision(self):
        """Test handling of high-precision decimals."""
        book = OrderBook("BTC-USDT")
        
        # Use very precise quantities and prices
        order = Order(
            "BTC-USDT",
            OrderType.LIMIT,
            OrderSide.BUY,
            Decimal("0.00000001"),
            Decimal("50000.12345678")
        )
        
        book.add_order(order)
        assert book.best_bid == Decimal("50000.12345678")
        
        level = book.bids[Decimal("50000.12345678")]
        assert level.total_volume == Decimal("0.00000001")
    
    def test_get_total_volume_at_price(self):
        """Test getting total volume at a specific price."""
        book = OrderBook("BTC-USDT")
        
        # Add multiple orders at same price
        price = Decimal("50000")
        book.add_order(Order("BTC-USDT", OrderType.LIMIT, OrderSide.BUY, Decimal("1.0"), price))
        book.add_order(Order("BTC-USDT", OrderType.LIMIT, OrderSide.BUY, Decimal("2.0"), price))
        book.add_order(Order("BTC-USDT", OrderType.LIMIT, OrderSide.BUY, Decimal("3.0"), price))
        
        total_volume = book.get_total_volume_at_price(price, OrderSide.BUY)
        assert total_volume == Decimal("6.0")


class TestOrderBookPerformance:
    """Performance tests for order book."""
    
    def test_add_remove_performance(self):
        """Test performance of adding and removing orders."""
        book = OrderBook("BTC-USDT")
        num_orders = 10000
        
        # Measure add performance
        start_time = time.time()
        orders = []
        
        for i in range(num_orders):
            price = Decimal("50000") + Decimal(str(i % 100))
            side = OrderSide.BUY if i % 2 == 0 else OrderSide.SELL
            order = Order("BTC-USDT", OrderType.LIMIT, side, Decimal("1.0"), price)
            book.add_order(order)
            orders.append(order)
        
        add_time = time.time() - start_time
        
        # Measure remove performance
        start_time = time.time()
        
        for order in orders:
            book.remove_order(order.order_id)
        
        remove_time = time.time() - start_time
        
        print(f"\nAdded {num_orders} orders in {add_time:.3f}s ({num_orders/add_time:.0f} orders/sec)")
        print(f"Removed {num_orders} orders in {remove_time:.3f}s ({num_orders/remove_time:.0f} orders/sec)")
        
        # Performance targets (should process >1000 orders/sec)
        assert num_orders / add_time > 1000
        assert num_orders / remove_time > 1000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
