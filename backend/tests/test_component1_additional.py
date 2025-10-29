"""
Additional comprehensive tests for Component 1

This module adds tests for validators, config, exceptions, Trade, and Order
to achieve >85% code coverage.
"""

import pytest
from decimal import Decimal
from datetime import datetime

from backend.core.order import Order, OrderType, OrderSide, OrderStatus
from backend.core.trade import Trade
from backend.config import Settings, get_settings
from backend.utils.validators import (
    sanitize_decimal,
    validate_price,
    validate_quantity,
    validate_symbol,
    validate_order_parameters,
)
from backend.utils.exceptions import (
    InvalidOrderException,
    InvalidQuantityException,
    PriceOutOfBoundsException,
    InvalidSymbolException,
)


class TestOrder:
    """Test cases for Order class."""
    
    def test_order_creation(self):
        """Test creating a valid order."""
        order = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=Decimal("1.0"),
            price=Decimal("50000")
        )
        
        assert order.symbol == "BTC-USDT"
        assert order.order_type == OrderType.LIMIT
        assert order.side == OrderSide.BUY
        assert order.quantity == Decimal("1.0")
        assert order.price == Decimal("50000")
        assert order.remaining_quantity == Decimal("1.0")
        assert order.filled_quantity == Decimal("0")
        assert order.status == OrderStatus.PENDING
    
    def test_order_validation_negative_quantity(self):
        """Test that negative quantity is rejected."""
        with pytest.raises(ValueError, match="Quantity must be positive"):
            Order(
                symbol="BTC-USDT",
                order_type=OrderType.LIMIT,
                side=OrderSide.BUY,
                quantity=Decimal("-1.0"),
                price=Decimal("50000")
            )
    
    def test_order_validation_no_price_for_limit(self):
        """Test that limit order requires price."""
        with pytest.raises(ValueError, match="LIMIT orders require a price"):
            Order(
                symbol="BTC-USDT",
                order_type=OrderType.LIMIT,
                side=OrderSide.BUY,
                quantity=Decimal("1.0"),
                price=None
            )
    
    def test_order_is_marketable(self):
        """Test is_marketable method."""
        # Market order is always marketable
        market_order = Order(
            symbol="BTC-USDT",
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=Decimal("1.0")
        )
        assert market_order.is_marketable(None, None)
        
        # Buy limit order marketable if price >= best ask
        buy_order = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=Decimal("1.0"),
            price=Decimal("51000")
        )
        assert buy_order.is_marketable(Decimal("50000"), Decimal("50100"))
        assert not buy_order.is_marketable(Decimal("50000"), Decimal("52000"))
        
        # Sell limit order marketable if price <= best bid
        sell_order = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=Decimal("1.0"),
            price=Decimal("49000")
        )
        assert sell_order.is_marketable(Decimal("50000"), Decimal("51000"))
        assert not sell_order.is_marketable(Decimal("48000"), Decimal("51000"))
    
    def test_order_update_fill(self):
        """Test updating order with fills."""
        order = Order(
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=Decimal("10.0"),
            price=Decimal("50000")
        )
        
        # Partial fill
        order.update_fill(Decimal("3.0"))
        assert order.filled_quantity == Decimal("3.0")
        assert order.remaining_quantity == Decimal("7.0")
        assert order.status == OrderStatus.PARTIAL
        
        # Another partial fill
        order.update_fill(Decimal("4.0"))
        assert order.filled_quantity == Decimal("7.0")
        assert order.remaining_quantity == Decimal("3.0")
        assert order.status == OrderStatus.PARTIAL
        
        # Complete fill
        order.update_fill(Decimal("3.0"))
        assert order.filled_quantity == Decimal("10.0")
        assert order.remaining_quantity == Decimal("0")
        assert order.status == OrderStatus.FILLED
        assert order.is_fully_filled
    
    def test_order_properties(self):
        """Test order properties."""
        buy_order = Order("BTC-USDT", OrderType.LIMIT, OrderSide.BUY, Decimal("1.0"), Decimal("50000"))
        assert buy_order.is_buy
        assert not buy_order.is_sell
        assert buy_order.is_active
        
        sell_order = Order("BTC-USDT", OrderType.LIMIT, OrderSide.SELL, Decimal("1.0"), Decimal("50000"))
        assert sell_order.is_sell
        assert not sell_order.is_buy
    
    def test_order_to_dict(self):
        """Test order serialization."""
        order = Order("BTC-USDT", OrderType.LIMIT, OrderSide.BUY, Decimal("1.0"), Decimal("50000"))
        order_dict = order.to_dict()
        
        assert order_dict["symbol"] == "BTC-USDT"
        assert order_dict["order_type"] == "LIMIT"
        assert order_dict["side"] == "BUY"
        assert order_dict["quantity"] == "1.0"
        assert order_dict["price"] == "50000"


class TestTrade:
    """Test cases for Trade class."""
    
    def test_trade_creation(self):
        """Test creating a valid trade."""
        from uuid import uuid4
        
        maker_id = uuid4()
        taker_id = uuid4()
        
        trade = Trade(
            symbol="BTC-USDT",
            price=Decimal("50000"),
            quantity=Decimal("1.5"),
            aggressor_side=OrderSide.BUY,
            maker_order_id=maker_id,
            taker_order_id=taker_id
        )
        
        assert trade.symbol == "BTC-USDT"
        assert trade.price == Decimal("50000")
        assert trade.quantity == Decimal("1.5")
        assert trade.aggressor_side == OrderSide.BUY
        assert trade.total_value == Decimal("75000")
    
    def test_trade_validation(self):
        """Test trade validation."""
        from uuid import uuid4
        
        with pytest.raises(ValueError, match="Price must be positive"):
            Trade(
                symbol="BTC-USDT",
                price=Decimal("-50000"),
                quantity=Decimal("1.0"),
                aggressor_side=OrderSide.BUY,
                maker_order_id=uuid4(),
                taker_order_id=uuid4()
            )
        
        with pytest.raises(ValueError, match="Quantity must be positive"):
            Trade(
                symbol="BTC-USDT",
                price=Decimal("50000"),
                quantity=Decimal("0"),
                aggressor_side=OrderSide.BUY,
                maker_order_id=uuid4(),
                taker_order_id=uuid4()
            )
    
    def test_trade_fee_calculation(self):
        """Test fee calculation."""
        from uuid import uuid4
        
        trade = Trade(
            symbol="BTC-USDT",
            price=Decimal("50000"),
            quantity=Decimal("2.0"),
            aggressor_side=OrderSide.BUY,
            maker_order_id=uuid4(),
            taker_order_id=uuid4()
        )
        
        maker_fee, taker_fee = trade.calculate_fees()
        
        # Default rates: 0.1% maker, 0.2% taker
        assert maker_fee == Decimal("100")  # 100000 * 0.001
        assert taker_fee == Decimal("200")  # 100000 * 0.002
    
    def test_trade_properties(self):
        """Test trade properties."""
        from uuid import uuid4
        
        # Trade where taker is buyer (aggressor is buy)
        buy_trade = Trade(
            symbol="BTC-USDT",
            price=Decimal("50000"),
            quantity=Decimal("1.0"),
            aggressor_side=OrderSide.BUY,
            maker_order_id=uuid4(),
            taker_order_id=uuid4()
        )
        
        assert buy_trade.taker_is_buyer
        assert not buy_trade.maker_is_buyer
        
        # Trade where taker is seller
        sell_trade = Trade(
            symbol="BTC-USDT",
            price=Decimal("50000"),
            quantity=Decimal("1.0"),
            aggressor_side=OrderSide.SELL,
            maker_order_id=uuid4(),
            taker_order_id=uuid4()
        )
        
        assert not sell_trade.taker_is_buyer
        assert sell_trade.maker_is_buyer
    
    def test_trade_to_dict(self):
        """Test trade serialization."""
        from uuid import uuid4
        
        trade = Trade(
            symbol="BTC-USDT",
            price=Decimal("50000"),
            quantity=Decimal("1.0"),
            aggressor_side=OrderSide.BUY,
            maker_order_id=uuid4(),
            taker_order_id=uuid4()
        )
        
        trade_dict = trade.to_dict()
        
        assert trade_dict["symbol"] == "BTC-USDT"
        assert trade_dict["price"] == "50000"
        assert trade_dict["quantity"] == "1.0"
        assert trade_dict["aggressor_side"] == "BUY"
        assert "trade_id" in trade_dict


class TestValidators:
    """Test cases for validators."""
    
    def test_sanitize_decimal(self):
        """Test decimal sanitization."""
        assert sanitize_decimal("123.45") == Decimal("123.45")
        assert sanitize_decimal(123.45) == Decimal("123.45")
        assert sanitize_decimal(123) == Decimal("123")
        assert sanitize_decimal(Decimal("99.99")) == Decimal("99.99")
        
        with pytest.raises(InvalidOrderException):
            sanitize_decimal("invalid")
    
    def test_validate_price(self):
        """Test price validation."""
        # Valid price
        assert validate_price(Decimal("50000"), "BTC-USDT", required=True)
        
        # Optional price can be None
        assert validate_price(None, "BTC-USDT", required=False)
        
        # Required price cannot be None
        with pytest.raises(InvalidOrderException):
            validate_price(None, "BTC-USDT", required=True)
        
        # Price must be positive
        with pytest.raises(PriceOutOfBoundsException):
            validate_price(Decimal("-100"), "BTC-USDT", required=True)
        
        # Price too low
        with pytest.raises(PriceOutOfBoundsException):
            validate_price(Decimal("0.000000001"), "BTC-USDT", required=True)
        
        # Price too high
        with pytest.raises(PriceOutOfBoundsException):
            validate_price(Decimal("99999999"), "BTC-USDT", required=True)
    
    def test_validate_quantity(self):
        """Test quantity validation."""
        # Valid quantity
        assert validate_quantity(Decimal("1.5"), "BTC-USDT")
        
        # Quantity must be positive
        with pytest.raises(InvalidQuantityException):
            validate_quantity(Decimal("0"), "BTC-USDT")
        
        with pytest.raises(InvalidQuantityException):
            validate_quantity(Decimal("-1"), "BTC-USDT")
        
        # Quantity too small
        with pytest.raises(InvalidQuantityException):
            validate_quantity(Decimal("0.000000001"), "BTC-USDT")
        
        # Quantity too large
        with pytest.raises(InvalidQuantityException):
            validate_quantity(Decimal("9999999"), "BTC-USDT")
    
    def test_validate_symbol(self):
        """Test symbol validation."""
        assert validate_symbol("BTC-USDT")
        assert validate_symbol("eth-usdt")
        
        with pytest.raises(InvalidSymbolException):
            validate_symbol("")
        
        with pytest.raises(InvalidSymbolException):
            validate_symbol("AB")  # Too short
        
        with pytest.raises(InvalidSymbolException):
            validate_symbol("XYZ-USDT", allowed_symbols=["BTC-USDT", "ETH-USDT"])
    
    def test_validate_order_parameters(self):
        """Test complete order parameter validation."""
        symbol, qty, price = validate_order_parameters(
            symbol="btc-usdt",
            order_type="LIMIT",
            side="BUY",
            quantity="1.5",
            price="50000"
        )
        
        assert symbol == "BTC-USDT"
        assert qty == Decimal("1.5")
        assert price == Decimal("50000")
        
        # Invalid order type
        with pytest.raises(InvalidOrderException):
            validate_order_parameters("BTC-USDT", "INVALID", "BUY", "1.0", "50000")
        
        # Invalid side
        with pytest.raises(InvalidOrderException):
            validate_order_parameters("BTC-USDT", "LIMIT", "INVALID", "1.0", "50000")


class TestConfig:
    """Test cases for configuration."""
    
    def test_settings_default_values(self):
        """Test default configuration values."""
        settings = get_settings()
        
        assert settings.backend_host == "localhost"
        assert settings.backend_port == 8000
        assert settings.min_order_quantity == Decimal("0.00000001")
        assert settings.max_order_quantity == Decimal("1000000")
        assert settings.price_precision == 2
        assert settings.quantity_precision == 8
    
    def test_settings_creation(self):
        """Test creating custom settings."""
        custom_settings = Settings(
            backend_host="0.0.0.0",
            backend_port=9000,
            log_level="DEBUG"
        )
        
        assert custom_settings.backend_host == "0.0.0.0"
        assert custom_settings.backend_port == 9000
        assert custom_settings.log_level == "DEBUG"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])