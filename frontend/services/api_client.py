"""
API Client Service for FastAPI Backend Communication

Handles all REST API requests with retry logic and error handling.
"""

import logging
from typing import Dict, List, Optional, Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class APIClient:
    """Client for communicating with the FastAPI backend via REST API."""
    
    def __init__(self, base_url: str = "http://localhost:8000", timeout: int = 5):
        """Initialize API client."""
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """Create requests session with retry logic."""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "DELETE", "PUT"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Handle API response and extract data or errors."""
        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            try:
                error_data = response.json()
                error_msg = error_data.get("detail", str(e))
            except:
                error_msg = str(e)
            raise Exception(f"API Error: {error_msg}")
        except requests.exceptions.JSONDecodeError:
            raise Exception("Invalid response from server")
    
    def health_check(self) -> bool:
        """Check if backend is healthy."""
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=self.timeout)
            data = self._handle_response(response)
            return data.get("status") == "healthy"
        except:
            return False
    
    def submit_order(self, order_data: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        """
        Submit a new order.
        
        Can be called with a dict or with keyword arguments.
        Example 1: submit_order({"symbol": "BTC/USD", "order_type": "limit", ...})
        Example 2: submit_order(symbol="BTC/USD", order_type="limit", side="buy", quantity=1.0, price=50000)
        """
        # Merge order_data dict and kwargs
        if order_data is None:
            order_data = kwargs
        else:
            order_data = {**order_data, **kwargs}
        
        # Convert numeric values to strings as API expects
        payload = {
            "symbol": str(order_data.get("symbol", "")),
            "order_type": str(order_data.get("order_type", "")).lower(),
            "side": str(order_data.get("side", "")).lower(),
            "quantity": str(order_data.get("quantity", ""))
        }
        
        if "price" in order_data and order_data["price"] is not None:
            payload["price"] = str(order_data["price"])
        
        response = self.session.post(f"{self.base_url}/api/v1/orders", json=payload, timeout=self.timeout)
        return self._handle_response(response)
    
    def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """Cancel an existing order."""
        response = self.session.delete(f"{self.base_url}/api/v1/orders/{order_id}", params={"symbol": symbol}, timeout=self.timeout)
        return self._handle_response(response)
    
    def get_order_status(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """Get order status."""
        response = self.session.get(f"{self.base_url}/api/v1/orders/{order_id}", params={"symbol": symbol}, timeout=self.timeout)
        return self._handle_response(response)
    
    def get_orderbook(self, symbol: str, levels: int = 10) -> Dict[str, Any]:
        """Get order book snapshot."""
        response = self.session.get(f"{self.base_url}/api/v1/orderbook/{symbol}", params={"levels": levels}, timeout=self.timeout)
        return self._handle_response(response)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get matching engine statistics."""
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=self.timeout)
            data = self._handle_response(response)
            return data.get("matching_engine", {})
        except:
            return {}
    
    def close(self):
        """Close the session."""
        if self.session:
            self.session.close()


_client_instance: Optional[APIClient] = None


def get_api_client(base_url: str = "http://localhost:8000") -> APIClient:
    """Get or create singleton API client instance."""
    global _client_instance
    if _client_instance is None:
        _client_instance = APIClient(base_url)
    return _client_instance
