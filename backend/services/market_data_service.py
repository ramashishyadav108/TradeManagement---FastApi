"""
Market Data Service - WebSocket subscription management for order book updates.

This service manages WebSocket connections for real-time order book streaming,
handles subscriptions, and broadcasts updates to connected clients.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Set, Any, Optional
from decimal import Decimal

from fastapi import WebSocket

from backend.core.matching_engine import MatchingEngine
from backend.core.order import OrderSide


class MarketDataService:
    """
    Service class for managing real-time market data streams.
    
    Handles WebSocket subscriptions, order book snapshots,
    and delta updates for connected clients.
    """
    
    def __init__(self, matching_engine: MatchingEngine):
        """
        Initialize market data service.
        
        Args:
            matching_engine: Reference to the matching engine instance
        """
        self.matching_engine = matching_engine
        self.logger = logging.getLogger(f"{__name__}.MarketDataService")
        
        # Active WebSocket subscriptions: {symbol: {websocket1, websocket2, ...}}
        self.active_subscriptions: Dict[str, Set[WebSocket]] = {}
        
        # Update queue for broadcasting
        self.update_queue: asyncio.Queue = asyncio.Queue()
        
        # Previous order book snapshots for delta calculation
        self._previous_snapshots: Dict[str, Dict[str, Any]] = {}
        
        # Background task handle
        self._broadcast_task: Optional[asyncio.Task] = None
        
        self.logger.info("MarketDataService initialized")
    
    async def subscribe_orderbook(self, websocket: WebSocket, symbol: str) -> None:
        """
        Subscribe a WebSocket connection to order book updates.
        
        Args:
            websocket: WebSocket connection to subscribe
            symbol: Trading pair symbol to subscribe to
        """
        if symbol not in self.active_subscriptions:
            self.active_subscriptions[symbol] = set()
        
        self.active_subscriptions[symbol].add(websocket)
        self.logger.info(
            f"WebSocket subscribed to {symbol} order book. "
            f"Total subscribers: {len(self.active_subscriptions[symbol])}"
        )
        
        # Send initial snapshot
        snapshot = self.generate_orderbook_snapshot(symbol)
        await self._send_to_websocket(websocket, snapshot)
    
    async def unsubscribe_orderbook(self, websocket: WebSocket, symbol: str) -> None:
        """
        Unsubscribe a WebSocket connection from order book updates.
        
        Args:
            websocket: WebSocket connection to unsubscribe
            symbol: Trading pair symbol to unsubscribe from
        """
        if symbol in self.active_subscriptions:
            self.active_subscriptions[symbol].discard(websocket)
            
            # Clean up empty subscription sets
            if not self.active_subscriptions[symbol]:
                del self.active_subscriptions[symbol]
                if symbol in self._previous_snapshots:
                    del self._previous_snapshots[symbol]
            
            self.logger.info(
                f"WebSocket unsubscribed from {symbol} order book. "
                f"Remaining subscribers: "
                f"{len(self.active_subscriptions.get(symbol, set()))}"
            )
    
    async def broadcast_orderbook_update(self, symbol: str, data: Dict[str, Any]) -> None:
        """
        Broadcast order book update to all subscribers of a symbol.
        
        Args:
            symbol: Trading pair symbol
            data: Order book data to broadcast
        """
        if symbol not in self.active_subscriptions:
            return
        
        subscribers = list(self.active_subscriptions[symbol])
        if not subscribers:
            return
        
        # Add message type and timestamp
        message = {
            "type": "orderbook_update",
            "symbol": symbol,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **data
        }
        
        # Broadcast to all subscribers
        dead_connections = []
        for ws in subscribers:
            try:
                await ws.send_json(message)
            except Exception as e:
                self.logger.warning(f"Failed to send to WebSocket: {e}")
                dead_connections.append(ws)
        
        # Clean up dead connections
        for ws in dead_connections:
            await self.unsubscribe_orderbook(ws, symbol)
    
    def generate_orderbook_snapshot(self, symbol: str, levels: int = 10) -> Dict[str, Any]:
        """
        Generate complete order book snapshot.
        
        Args:
            symbol: Trading pair symbol
            levels: Number of price levels to include
        
        Returns:
            Dictionary containing order book snapshot
        """
        order_book = self.matching_engine.get_order_book(symbol)
        
        if not order_book:
            return {
                "symbol": symbol,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "bids": [],
                "asks": [],
                "bbo": {
                    "best_bid": None,
                    "best_ask": None,
                    "spread": None
                }
            }
        
        # Get price levels
        bids = order_book.get_price_levels(OrderSide.BUY, levels)
        asks = order_book.get_price_levels(OrderSide.SELL, levels)
        
        # Calculate BBO
        best_bid = order_book.best_bid
        best_ask = order_book.best_ask
        spread = None
        
        if best_bid and best_ask:
            spread = str(best_ask - best_bid)
        
        snapshot = {
            "symbol": symbol,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "bids": [[str(price), str(volume)] for price, volume in bids],
            "asks": [[str(price), str(volume)] for price, volume in asks],
            "bbo": {
                "best_bid": str(best_bid) if best_bid else None,
                "best_ask": str(best_ask) if best_ask else None,
                "spread": spread
            }
        }
        
        return snapshot
    
    def get_bbo(self, symbol: str) -> Dict[str, Optional[str]]:
        """
        Get Best Bid/Offer for a symbol.
        
        Args:
            symbol: Trading pair symbol
        
        Returns:
            Dictionary with best_bid, best_ask, and spread
        """
        order_book = self.matching_engine.get_order_book(symbol)
        
        if not order_book:
            return {
                "best_bid": None,
                "best_ask": None,
                "spread": None
            }
        
        best_bid = order_book.best_bid
        best_ask = order_book.best_ask
        spread = None
        
        if best_bid and best_ask:
            spread = str(best_ask - best_bid)
        
        return {
            "best_bid": str(best_bid) if best_bid else None,
            "best_ask": str(best_ask) if best_ask else None,
            "spread": spread
        }
    
    async def start_broadcasting(self) -> None:
        """Start background task for polling and broadcasting order book updates."""
        if self._broadcast_task is None or self._broadcast_task.done():
            self._broadcast_task = asyncio.create_task(self._poll_and_broadcast())
            self.logger.info("Order book broadcasting task started")
    
    async def stop_broadcasting(self) -> None:
        """Stop background broadcasting task."""
        if self._broadcast_task and not self._broadcast_task.done():
            self._broadcast_task.cancel()
            try:
                await self._broadcast_task
            except asyncio.CancelledError:
                pass
            self.logger.info("Order book broadcasting task stopped")
    
    async def _poll_and_broadcast(self) -> None:
        """
        Background task to poll order books and broadcast updates.
        
        Runs every 100ms, checks for changes, and broadcasts delta updates.
        """
        while True:
            try:
                await asyncio.sleep(0.1)  # Poll every 100ms
                
                # Check each subscribed symbol
                for symbol in list(self.active_subscriptions.keys()):
                    if not self.active_subscriptions[symbol]:
                        continue
                    
                    # Generate current snapshot
                    current_snapshot = self.generate_orderbook_snapshot(symbol)
                    
                    # Check if changed
                    if self._has_changed(symbol, current_snapshot):
                        # Broadcast update
                        await self.broadcast_orderbook_update(symbol, current_snapshot)
                        
                        # Store as previous
                        self._previous_snapshots[symbol] = current_snapshot
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in poll_and_broadcast: {e}", exc_info=True)
    
    def _has_changed(self, symbol: str, current_snapshot: Dict[str, Any]) -> bool:
        """
        Check if order book has changed since last snapshot.
        
        Args:
            symbol: Trading pair symbol
            current_snapshot: Current order book snapshot
        
        Returns:
            True if order book has changed
        """
        if symbol not in self._previous_snapshots:
            return True
        
        prev = self._previous_snapshots[symbol]
        
        # Compare bids, asks, and BBO
        return (
            current_snapshot['bids'] != prev['bids'] or
            current_snapshot['asks'] != prev['asks'] or
            current_snapshot['bbo'] != prev['bbo']
        )
    
    async def _send_to_websocket(self, websocket: WebSocket, data: Dict[str, Any]) -> None:
        """
        Send data to a specific WebSocket.
        
        Args:
            websocket: WebSocket connection
            data: Data to send
        """
        try:
            await websocket.send_json(data)
        except Exception as e:
            self.logger.warning(f"Failed to send to WebSocket: {e}")
