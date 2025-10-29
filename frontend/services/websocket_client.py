"""
WebSocket Client for Real-Time Data Streaming

Handles WebSocket connections for order book and trade feed updates.
"""

import logging
import json
import threading
import time
from typing import Dict, Callable, Optional, Any
import websocket


class WebSocketClient:
    """Client for real-time WebSocket communication with backend."""
    
    def __init__(self, ws_url: str = "ws://localhost:8000"):
        """Initialize WebSocket client."""
        self.ws_url = ws_url.rstrip('/')
        self.logger = logging.getLogger(__name__)
        self.connections: Dict[str, websocket.WebSocketApp] = {}
        self.callbacks: Dict[str, Callable] = {}
        self.threads: Dict[str, threading.Thread] = {}
        self.running: Dict[str, bool] = {}
        self.reconnect_attempts: Dict[str, int] = {}
        self.max_reconnect_attempts = 5
    
    def connect_orderbook(self, symbol: str, callback: Callable[[Dict], None]) -> bool:
        """
        Connect to order book WebSocket stream.
        
        Args:
            symbol: Trading pair symbol
            callback: Function to call with order book updates
            
        Returns:
            True if connection successful
        """
        channel = f"orderbook_{symbol}"
        url = f"{self.ws_url}/ws/orderbook/{symbol}"
        
        return self._connect(channel, url, callback)
    
    def connect_trades(self, callback: Callable[[Dict], None], symbol: Optional[str] = None) -> bool:
        """
        Connect to trade feed WebSocket stream.
        
        Args:
            callback: Function to call with trade updates
            symbol: Optional symbol for symbol-specific feed
            
        Returns:
            True if connection successful
        """
        if symbol:
            channel = f"trades_{symbol}"
            url = f"{self.ws_url}/ws/trades/{symbol}"
        else:
            channel = "trades_all"
            url = f"{self.ws_url}/ws/trades"
        
        return self._connect(channel, url, callback)
    
    def _connect(self, channel: str, url: str, callback: Callable) -> bool:
        """Internal method to establish WebSocket connection."""
        try:
            # Disconnect existing connection if any
            if channel in self.connections:
                self.disconnect(channel)
            
            self.callbacks[channel] = callback
            self.running[channel] = True
            self.reconnect_attempts[channel] = 0
            
            # Create WebSocket app
            ws = websocket.WebSocketApp(
                url,
                on_message=lambda ws, msg: self._on_message(channel, msg),
                on_error=lambda ws, error: self._on_error(channel, error),
                on_close=lambda ws, *args: self._on_close(channel),
                on_open=lambda ws: self._on_open(channel)
            )
            
            self.connections[channel] = ws
            
            # Run in background thread
            thread = threading.Thread(target=ws.run_forever, daemon=True)
            thread.start()
            self.threads[channel] = thread
            
            self.logger.info(f"WebSocket connection initiated for {channel}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect WebSocket for {channel}: {e}")
            return False
    
    def _on_message(self, channel: str, message: str):
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(message)
            callback = self.callbacks.get(channel)
            if callback:
                callback(data)
        except Exception as e:
            self.logger.error(f"Error processing message for {channel}: {e}")
    
    def _on_error(self, channel: str, error):
        """Handle WebSocket error."""
        self.logger.error(f"WebSocket error for {channel}: {error}")
    
    def _on_close(self, channel: str):
        """Handle WebSocket close."""
        self.logger.warning(f"WebSocket closed for {channel}")
        
        # Attempt reconnection if still running
        if self.running.get(channel, False):
            attempts = self.reconnect_attempts.get(channel, 0)
            if attempts < self.max_reconnect_attempts:
                self.reconnect_attempts[channel] = attempts + 1
                time.sleep(2 ** attempts)  # Exponential backoff
                self.logger.info(f"Attempting to reconnect {channel} (attempt {attempts + 1})")
                # Reconnection would need to be implemented based on channel type
    
    def _on_open(self, channel: str):
        """Handle WebSocket open."""
        self.logger.info(f"WebSocket opened for {channel}")
        self.reconnect_attempts[channel] = 0
    
    def disconnect(self, channel: str) -> bool:
        """
        Disconnect from a WebSocket channel.
        
        Args:
            channel: Channel identifier
            
        Returns:
            True if disconnection successful
        """
        try:
            self.running[channel] = False
            
            if channel in self.connections:
                ws = self.connections[channel]
                ws.close()
                del self.connections[channel]
            
            if channel in self.callbacks:
                del self.callbacks[channel]
            
            if channel in self.threads:
                del self.threads[channel]
            
            self.logger.info(f"Disconnected from {channel}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error disconnecting from {channel}: {e}")
            return False
    
    def is_connected(self, channel: str) -> bool:
        """
        Check if a channel is connected.
        
        Args:
            channel: Channel identifier
            
        Returns:
            True if connected
        """
        return channel in self.connections and self.running.get(channel, False)
    
    def disconnect_all(self):
        """Disconnect all WebSocket connections."""
        channels = list(self.connections.keys())
        for channel in channels:
            self.disconnect(channel)


_websocket_instance: Optional[WebSocketClient] = None


def get_websocket_client(ws_url: str = "ws://localhost:8000") -> WebSocketClient:
    """Get or create singleton WebSocket client instance."""
    global _websocket_instance
    if _websocket_instance is None:
        _websocket_instance = WebSocketClient(ws_url)
    return _websocket_instance
