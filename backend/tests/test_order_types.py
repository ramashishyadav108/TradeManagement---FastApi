"""
Detailed tests for different order types and their specific behaviors.
"""

import pytest
from decimal import Decimal

from backend.core.order import Order, OrderType, OrderSide, OrderStatus
from backend.core.matching_engine import MatchingEngine


class TestMarketOrderBehavior:
    """Detailed market order behavior tests."""
    
    def test_market_order_no_price_required(self):
        """Market orders should not require a price."""
        order = Order(
            symbol="BTC-USDT",
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=Decimal("1.0"),
        )
        
        assert order.price is None
        # Market orders are always marketable regardless of bid/ask
        assert order.is_marketable(None, None)
    
    def test_market_sell_execution(self):
        """Test market sell order execution."""
        engine = MatchingEngine()
        
        # Add buy orders
        buy1 = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=Decimal("5.0"),
            price=Decimal("50000.00")
        )
        buy2 = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=Decimal("5.0"),
            price=Decimal("49900.00")
        )
        
        engine.submit_order(buy1)
        engine.submit_order(buy2)
        
        # Market sell
        sell = Order(
            symbol="BTC-USDT",
            order_type=OrderType.MARKET,
            side=OrderSide.SELL,
            quantity=Decimal("7.0"),
        )
        
        result = engine.submit_order(sell)
        
        assert result.order.filled_quantity == Decimal("7.0")
        assert len(result.trades) == 2
        # Should execute at best bid first
        assert result.trades[0].price == Decimal("50000.00")
        assert result.trades[0].quantity == Decimal("5.0")
        assert result.trades[1].price == Decimal("49900.00")
        assert result.trades[1].quantity == Decimal("2.0")


class TestLimitOrderBehavior:
    """Detailed limit order behavior tests."""
    
    def test_limit_order_requires_price(self):
        """Limit orders must have a price."""
        with pytest.raises(ValueError):
            Order(
                symbol="BTC-USDT",
                order_type=OrderType.LIMIT,
                side=OrderSide.BUY,
                quantity=Decimal("1.0"),
                price=None
            )
    
    def test_limit_buy_post_only_behavior(self):
        """Test limit order that should rest on book."""
        engine = MatchingEngine()
        
        # Limit buy below market
        buy = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=Decimal("10.0"),
            price=Decimal("49000.00")
        )
        
        result = engine.submit_order(buy)
        
        assert result.order.status == OrderStatus.PENDING
        assert result.order.filled_quantity == Decimal("0")
        
        book = engine.get_order_book("BTC-USDT")
        assert book.get_best_bid() == Decimal("49000.00")
    
    def test_limit_sell_post_only_behavior(self):
        """Test limit sell that should rest on book."""
        engine = MatchingEngine()
        
        # Limit sell above market
        sell = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("10.0"),
            price=Decimal("51000.00")
        )
        
        result = engine.submit_order(sell)
        
        assert result.order.status == OrderStatus.PENDING
        assert result.order.filled_quantity == Decimal("0")
        
        book = engine.get_order_book("BTC-USDT")
        assert book.get_best_ask() == Decimal("51000.00")
    
    def test_limit_order_price_protection(self):
        """Limit order should not execute worse than limit price."""
        engine = MatchingEngine()
        
        # Add sell at 50000
        sell = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("10.0"),
            price=Decimal("50000.00")
        )
        engine.submit_order(sell)
        
        # Limit buy at 49900 (below sell price)
        buy = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=Decimal("5.0"),
            price=Decimal("49900.00")
        )
        
        result = engine.submit_order(buy)
        
        # Should not execute
        assert len(result.trades) == 0
        assert result.order.status == OrderStatus.PENDING


class TestIOCOrderBehavior:
    """Detailed IOC order behavior tests."""
    
    def test_ioc_with_limit_price(self):
        """IOC can have a limit price."""
        engine = MatchingEngine()
        
        # Add sell at 50000
        sell = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("10.0"),
            price=Decimal("50000.00")
        )
        engine.submit_order(sell)
        
        # IOC buy with limit
        buy = Order(
            symbol="BTC-USDT",
            order_type=OrderType.IOC,
            side=OrderSide.BUY,
            quantity=Decimal("5.0"),
            price=Decimal("50100.00")
        )
        
        result = engine.submit_order(buy)
        
        assert result.order.is_fully_filled
        assert result.trades[0].price == Decimal("50000.00")
    
    def test_ioc_respects_price_limit(self):
        """IOC should respect price limit and not execute beyond it."""
        engine = MatchingEngine()
        
        # Add sell at 50100
        sell = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("10.0"),
            price=Decimal("50100.00")
        )
        engine.submit_order(sell)
        
        # IOC buy with limit at 50000 (below sell)
        buy = Order(
            symbol="BTC-USDT",
            order_type=OrderType.IOC,
            side=OrderSide.BUY,
            quantity=Decimal("5.0"),
            price=Decimal("50000.00")
        )
        
        result = engine.submit_order(buy)
        
        # Should not execute - price limit prevents it
        assert len(result.trades) == 0
        assert result.order.status == OrderStatus.CANCELLED
    
    def test_ioc_never_rests_on_book(self):
        """IOC orders should never rest on book."""
        engine = MatchingEngine()
        
        # IOC with no matching orders
        order = Order(
            symbol="BTC-USDT",
            order_type=OrderType.IOC,
            side=OrderSide.BUY,
            quantity=Decimal("10.0"),
            price=Decimal("50000.00")
        )
        
        result = engine.submit_order(order)
        
        assert result.order.status == OrderStatus.CANCELLED
        
        book = engine.get_order_book("BTC-USDT")
        assert book.get_best_bid() is None


class TestFOKOrderBehavior:
    """Detailed FOK order behavior tests."""
    
    def test_fok_atomicity(self):
        """FOK must be atomic - all or nothing."""
        engine = MatchingEngine()
        
        # Add partial liquidity
        sell = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("9.5"),
            price=Decimal("50000.00")
        )
        engine.submit_order(sell)
        
        # FOK for more
        buy = Order(
            symbol="BTC-USDT",
            order_type=OrderType.FOK,
            side=OrderSide.BUY,
            quantity=Decimal("10.0"),
            price=Decimal("50000.00")
        )
        
        result = engine.submit_order(buy)
        
        # Should kill entire order
        assert result.order.filled_quantity == Decimal("0")
        assert len(result.trades) == 0
        
        # Verify book unchanged
        book = engine.get_order_book("BTC-USDT")
        assert book.get_total_volume_at_price(Decimal("50000.00"), OrderSide.SELL) == Decimal("9.5")
    
    def test_fok_scans_multiple_levels(self):
        """FOK should scan across price levels for liquidity."""
        engine = MatchingEngine()
        
        # Add orders at multiple levels totaling enough
        sell1 = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("4.0"),
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
            quantity=Decimal("3.0"),
            price=Decimal("50200.00")
        )
        
        engine.submit_order(sell1)
        engine.submit_order(sell2)
        engine.submit_order(sell3)
        
        # FOK for total
        buy = Order(
            symbol="BTC-USDT",
            order_type=OrderType.FOK,
            side=OrderSide.BUY,
            quantity=Decimal("10.0"),
            price=Decimal("50200.00")
        )
        
        result = engine.submit_order(buy)
        
        assert result.order.is_fully_filled
        assert len(result.trades) == 3
    
    def test_fok_with_price_limit(self):
        """FOK with price limit should only consider acceptable prices."""
        engine = MatchingEngine()
        
        # Add orders at different prices
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
            price=Decimal("50300.00")  # Above limit
        )
        
        engine.submit_order(sell1)
        engine.submit_order(sell2)
        
        # FOK with price limit
        buy = Order(
            symbol="BTC-USDT",
            order_type=OrderType.FOK,
            side=OrderSide.BUY,
            quantity=Decimal("10.0"),
            price=Decimal("50200.00")  # Won't reach sell2
        )
        
        result = engine.submit_order(buy)
        
        # Should kill - can't fill 10 at acceptable price
        assert result.order.status == OrderStatus.CANCELLED
        assert len(result.trades) == 0


class TestOrderTypeComparison:
    """Compare behavior across order types."""
    
    def test_same_scenario_different_types(self):
        """Test same scenario with different order types."""
        
        # Scenario: 5 BTC available, want to buy 10 BTC
        
        # MARKET: Fills 5, cancels 5
        engine1 = MatchingEngine()
        sell1 = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("5.0"),
            price=Decimal("50000.00")
        )
        engine1.submit_order(sell1)
        
        market = Order(
            symbol="BTC-USDT",
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=Decimal("10.0"),
        )
        result1 = engine1.submit_order(market)
        
        assert result1.order.filled_quantity == Decimal("5.0")
        assert result1.order.status == OrderStatus.PARTIAL
        
        # LIMIT: Fills 5, rests 5 on book
        engine2 = MatchingEngine()
        sell2 = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("5.0"),
            price=Decimal("50000.00")
        )
        engine2.submit_order(sell2)
        
        limit = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=Decimal("10.0"),
            price=Decimal("50000.00")
        )
        result2 = engine2.submit_order(limit)
        
        assert result2.order.filled_quantity == Decimal("5.0")
        assert result2.order.status == OrderStatus.PARTIAL
        book2 = engine2.get_order_book("BTC-USDT")
        assert book2.get_best_bid() == Decimal("50000.00")
        
        # IOC: Fills 5, cancels 5
        engine3 = MatchingEngine()
        sell3 = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("5.0"),
            price=Decimal("50000.00")
        )
        engine3.submit_order(sell3)
        
        ioc = Order(
            symbol="BTC-USDT",
            order_type=OrderType.IOC,
            side=OrderSide.BUY,
            quantity=Decimal("10.0"),
            price=Decimal("50000.00")
        )
        result3 = engine3.submit_order(ioc)
        
        assert result3.order.filled_quantity == Decimal("5.0")
        assert result3.order.status == OrderStatus.PARTIAL
        book3 = engine3.get_order_book("BTC-USDT")
        assert book3.get_best_bid() is None
        
        # FOK: Fills nothing, cancels all
        engine4 = MatchingEngine()
        sell4 = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("5.0"),
            price=Decimal("50000.00")
        )
        engine4.submit_order(sell4)
        
        fok = Order(
            symbol="BTC-USDT",
            order_type=OrderType.FOK,
            side=OrderSide.BUY,
            quantity=Decimal("10.0"),
            price=Decimal("50000.00")
        )
        result4 = engine4.submit_order(fok)
        
        assert result4.order.filled_quantity == Decimal("0")
        assert result4.order.status == OrderStatus.CANCELLED

