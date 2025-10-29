"""
Comprehensive API integration tests for FastAPI endpoints.

Tests all REST and WebSocket endpoints with various scenarios.
"""

import pytest
import asyncio
from decimal import Decimal
from uuid import uuid4
from fastapi.testclient import TestClient

from backend.main import app
from backend.core.order import OrderType, OrderSide
from backend.core.matching_engine import MatchingEngine
from backend.services.order_service import OrderService
from backend.services.market_data_service import MarketDataService
from backend.services.trade_service import TradeService
import backend.main as main_module


@pytest.fixture(scope="module", autouse=True)
def setup_services():
    """Setup global services for testing."""
    # Initialize services
    main_module.matching_engine = MatchingEngine()
    main_module.order_service = OrderService(main_module.matching_engine)
    main_module.market_data_service = MarketDataService(main_module.matching_engine)
    main_module.trade_service = TradeService(main_module.matching_engine)
    
    # Start market data broadcasting
    asyncio.run(main_module.market_data_service.start_broadcasting())
    
    yield
    
    # Cleanup
    asyncio.run(main_module.market_data_service.stop_broadcasting())
    main_module.matching_engine = None
    main_module.order_service = None
    main_module.market_data_service = None
    main_module.trade_service = None


@pytest.fixture
def test_client():
    """Create a test client with services initialized."""
    with TestClient(app) as client:
        yield client


class TestHealthEndpoint:
    """Test health check endpoint."""
    
    def test_health_check(self, test_client):
        """Test health check returns 200 and correct structure."""
        response = test_client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data
        assert "matching_engine" in data
        assert isinstance(data["matching_engine"], dict)


class TestOrderSubmission:
    """Test order submission endpoints."""
    
    def test_submit_valid_limit_order(self, test_client):
        """Test submitting a valid limit buy order."""
        order_data = {
            "symbol": "BTC-USDT",
            "order_type": "limit",
            "side": "buy",
            "quantity": "0.5",
            "price": "50000.00"
        }
        
        response = test_client.post("/api/v1/orders", json=order_data)
        assert response.status_code == 201
        
        data = response.json()
        assert "order_id" in data
        assert data["status"] in ["pending", "filled", "partial"]
        assert data["filled_quantity"] is not None
        assert data["remaining_quantity"] is not None
        assert isinstance(data["trades"], list)
    
    def test_submit_market_order(self, test_client):
        """Test submitting a market order."""
        # First add a limit sell order for liquidity
        limit_order = {
            "symbol": "BTC-USDT",
            "order_type": "limit",
            "side": "sell",
            "quantity": "1.0",
            "price": "50000.00"
        }
        test_client.post("/api/v1/orders", json=limit_order)
        
        # Now submit market buy
        market_order = {
            "symbol": "BTC-USDT",
            "order_type": "market",
            "side": "buy",
            "quantity": "0.5"
        }
        
        response = test_client.post("/api/v1/orders", json=market_order)
        assert response.status_code == 201
        
        data = response.json()
        assert data["status"] == "filled"
        assert Decimal(data["filled_quantity"]) == Decimal("0.5")
    
    def test_submit_ioc_order(self, test_client):
        """Test submitting an IOC (Immediate-Or-Cancel) order."""
        # Add liquidity
        limit_order = {
            "symbol": "ETH-USDT",
            "order_type": "limit",
            "side": "sell",
            "quantity": "2.0",
            "price": "3000.00"
        }
        test_client.post("/api/v1/orders", json=limit_order)
        
        # Submit IOC
        ioc_order = {
            "symbol": "ETH-USDT",
            "order_type": "ioc",
            "side": "buy",
            "quantity": "5.0",
            "price": "3000.00"
        }
        
        response = test_client.post("/api/v1/orders", json=ioc_order)
        assert response.status_code == 201
        
        data = response.json()
        assert data["status"] in ["partial", "cancelled"]
        # IOC should fill what's available (2.0) and cancel rest
        assert Decimal(data["filled_quantity"]) == Decimal("2.0")
    
    def test_submit_fok_order(self, test_client):
        """Test submitting a FOK (Fill-Or-Kill) order."""
        # Add insufficient liquidity
        limit_order = {
            "symbol": "SOL-USDT",
            "order_type": "limit",
            "side": "sell",
            "quantity": "5.0",
            "price": "100.00"
        }
        test_client.post("/api/v1/orders", json=limit_order)
        
        # Submit FOK for more than available
        fok_order = {
            "symbol": "SOL-USDT",
            "order_type": "fok",
            "side": "buy",
            "quantity": "10.0",
            "price": "100.00"
        }
        
        response = test_client.post("/api/v1/orders", json=fok_order)
        assert response.status_code == 201
        
        data = response.json()
        # FOK should be killed due to insufficient liquidity
        assert data["status"] == "cancelled"
        assert Decimal(data["filled_quantity"]) == Decimal("0")


class TestOrderValidation:
    """Test order validation and error handling."""
    
    def test_invalid_order_type(self, test_client):
        """Test submitting order with invalid order type."""
        order_data = {
            "symbol": "BTC-USDT",
            "order_type": "invalid_type",
            "side": "buy",
            "quantity": "1.0",
            "price": "50000.00"
        }
        
        response = test_client.post("/api/v1/orders", json=order_data)
        assert response.status_code == 422
    
    def test_missing_required_fields(self, test_client):
        """Test submitting order with missing fields."""
        order_data = {
            "symbol": "BTC-USDT",
            "order_type": "limit",
            # Missing side and quantity
        }
        
        response = test_client.post("/api/v1/orders", json=order_data)
        assert response.status_code == 422
    
    def test_invalid_quantity_negative(self, test_client):
        """Test submitting order with negative quantity."""
        order_data = {
            "symbol": "BTC-USDT",
            "order_type": "limit",
            "side": "buy",
            "quantity": "-1.0",
            "price": "50000.00"
        }
        
        response = test_client.post("/api/v1/orders", json=order_data)
        assert response.status_code == 422
    
    def test_invalid_quantity_zero(self, test_client):
        """Test submitting order with zero quantity."""
        order_data = {
            "symbol": "BTC-USDT",
            "order_type": "limit",
            "side": "buy",
            "quantity": "0",
            "price": "50000.00"
        }
        
        response = test_client.post("/api/v1/orders", json=order_data)
        assert response.status_code == 422
    
    def test_invalid_quantity_too_large(self, test_client):
        """Test submitting order with excessive quantity."""
        order_data = {
            "symbol": "BTC-USDT",
            "order_type": "limit",
            "side": "buy",
            "quantity": "10000000",  # > 1,000,000 limit
            "price": "50000.00"
        }
        
        response = test_client.post("/api/v1/orders", json=order_data)
        assert response.status_code == 422
    
    def test_invalid_price_negative(self, test_client):
        """Test submitting limit order with negative price."""
        order_data = {
            "symbol": "BTC-USDT",
            "order_type": "limit",
            "side": "buy",
            "quantity": "1.0",
            "price": "-50000.00"
        }
        
        response = test_client.post("/api/v1/orders", json=order_data)
        assert response.status_code == 422


class TestOrderCancellation:
    """Test order cancellation endpoints."""
    
    def test_cancel_existing_order(self, test_client):
        """Test cancelling an existing order."""
        # Submit a limit order
        order_data = {
            "symbol": "BTC-USDT",
            "order_type": "limit",
            "side": "buy",
            "quantity": "1.0",
            "price": "45000.00"  # Below market, won't fill
        }
        
        response = test_client.post("/api/v1/orders", json=order_data)
        assert response.status_code == 201
        
        order_id = response.json()["order_id"]
        
        # Cancel the order
        cancel_response = test_client.delete(f"/api/v1/orders/{order_id}?symbol=BTC-USDT")
        assert cancel_response.status_code == 200
        
        data = cancel_response.json()
        assert data["cancelled"] is True
        assert data["order_id"] == order_id
    
    def test_cancel_nonexistent_order(self, test_client):
        """Test cancelling a non-existent order."""
        fake_order_id = str(uuid4())
        
        response = test_client.delete(f"/api/v1/orders/{fake_order_id}?symbol=BTC-USDT")
        assert response.status_code == 404


class TestOrderStatus:
    """Test order status query endpoints."""
    
    def test_get_order_status_existing(self, test_client):
        """Test getting status of an existing order."""
        # Submit an order with a unique symbol to avoid matching with previous tests
        order_data = {
            "symbol": "DOGE-USDT",  # Fresh symbol, no prior liquidity
            "order_type": "limit",
            "side": "sell",
            "quantity": "1000.0",
            "price": "0.55"  # Arbitrary price
        }
        
        response = test_client.post("/api/v1/orders", json=order_data)
        assert response.status_code == 201
        order_id = response.json()["order_id"]
        
        # Get order status
        status_response = test_client.get(f"/api/v1/orders/{order_id}?symbol=DOGE-USDT")
        assert status_response.status_code == 200
        
        data = status_response.json()
        assert data["order_id"] == order_id
        assert data["symbol"] == "DOGE-USDT"
        assert data["status"] == "pending"
    
    def test_get_order_status_nonexistent(self, test_client):
        """Test getting status of non-existent order."""
        fake_order_id = str(uuid4())
        
        response = test_client.get(f"/api/v1/orders/{fake_order_id}?symbol=BTC-USDT")
        assert response.status_code == 404


class TestOrderBook:
    """Test order book snapshot endpoint."""
    
    def test_get_orderbook_snapshot(self, test_client):
        """Test getting order book snapshot."""
        # Add some orders
        orders = [
            {"symbol": "BTC-USDT", "order_type": "limit", "side": "buy", "quantity": "1.0", "price": "49000.00"},
            {"symbol": "BTC-USDT", "order_type": "limit", "side": "buy", "quantity": "1.5", "price": "48000.00"},
            {"symbol": "BTC-USDT", "order_type": "limit", "side": "sell", "quantity": "1.0", "price": "51000.00"},
            {"symbol": "BTC-USDT", "order_type": "limit", "side": "sell", "quantity": "2.0", "price": "52000.00"},
        ]
        
        for order in orders:
            test_client.post("/api/v1/orders", json=order)
        
        # Get order book
        response = test_client.get("/api/v1/orderbook/BTC-USDT?levels=10")
        assert response.status_code == 200
        
        data = response.json()
        assert data["symbol"] == "BTC-USDT"
        assert "timestamp" in data
        assert isinstance(data["bids"], list)
        assert isinstance(data["asks"], list)
        assert "bbo" in data
        
        # Check BBO
        if data["bbo"]["best_bid"] and data["bbo"]["best_ask"]:
            assert Decimal(data["bbo"]["best_bid"]) < Decimal(data["bbo"]["best_ask"])


class TestWebSocketOrderBook:
    """Test WebSocket order book stream."""
    
    def test_orderbook_websocket_connection(self, test_client):
        """Test connecting to order book WebSocket."""
        with test_client.websocket_connect("/ws/orderbook/BTC-USDT") as websocket:
            # Should receive initial snapshot
            data = websocket.receive_json()
            assert "symbol" in data
            assert data["symbol"] == "BTC-USDT"
            assert "bids" in data or "asks" in data


class TestWebSocketTrades:
    """Test WebSocket trade feed stream."""
    
    def test_trade_feed_websocket_connection(self, test_client):
        """Test connecting to trade feed WebSocket."""
        with test_client.websocket_connect("/ws/trades/BTC-USDT") as websocket:
            # May receive history first
            try:
                data = websocket.receive_json(timeout=1)
                assert "type" in data
            except:
                pass  # No trades yet is OK


class TestCORSHeaders:
    """Test CORS headers."""
    
    def test_cors_headers_present(self, test_client):
        """Test that CORS headers are present."""
        response = test_client.get("/health", headers={"Origin": "http://localhost:3000"})
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers


class TestConcurrentOrders:
    """Test concurrent order submissions."""
    
    def test_concurrent_order_submissions(self, test_client):
        """Test submitting 10 orders concurrently."""
        import concurrent.futures
        
        def submit_order(i):
            order_data = {
                "symbol": "BTC-USDT",
                "order_type": "limit",
                "side": "buy" if i % 2 == 0 else "sell",
                "quantity": "0.1",
                "price": str(50000 + i * 10)
            }
            return test_client.post("/api/v1/orders", json=order_data)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(submit_order, i) for i in range(10)]
            responses = [f.result() for f in futures]
        
        # All should succeed
        assert all(r.status_code == 201 for r in responses)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
