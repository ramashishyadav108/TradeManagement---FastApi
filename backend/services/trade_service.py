"""
Trade Service - Real-time trade broadcasting and history management.

This service registers as a callback with the matching engine to receive
trades in real-time and broadcasts them to WebSocket subscribers.
"""

import asyncio
import logging
from datetime import datetime
from typing import Set, List, Dict, Any, Optional
from uuid import UUID
from collections import deque

from fastapi import WebSocket

from backend.core.matching_engine import MatchingEngine
from backend.core.trade import Trade


class TradeService:
    """
    Service class for managing real-time trade feeds.
    
    Registers callbacks with matching engine and broadcasts
    trades to WebSocket subscribers.
    """
    
    def __init__(self, matching_engine: MatchingEngine):
        """
        Initialize trade service.
        
        Args:
            matching_engine: Reference to the matching engine instance
        """
        self.matching_engine = matching_engine
        self.logger = logging.getLogger(f"{__name__}.TradeService")
        
        # Active WebSocket subscribers
        self.trade_subscribers: Set[WebSocket] = set()
        
        # Symbol-specific subscribers: {symbol: {websocket1, websocket2, ...}}
        self.symbol_subscribers: Dict[str, Set[WebSocket]] = {}
        
        # Trade history (in-memory cache of recent trades)
        self._trade_history: Dict[str, deque] = {}
        self._max_history = 1000  # Keep last 1000 trades per symbol
        
        # Register callback with matching engine
        self.matching_engine.register_trade_callback(self._on_trade_executed)
        
        self.logger.info("TradeService initialized and registered with matching engine")
    
    async def subscribe_trades(self, websocket: WebSocket, symbol: Optional[str] = None) -> None:
        """
        Subscribe a WebSocket connection to trade feed.
        
        Args:
            websocket: WebSocket connection to subscribe
            symbol: Optional symbol filter (None for all symbols)
        """
        if symbol:
            # Symbol-specific subscription
            if symbol not in self.symbol_subscribers:
                self.symbol_subscribers[symbol] = set()
            self.symbol_subscribers[symbol].add(websocket)
            self.logger.info(
                f"WebSocket subscribed to {symbol} trades. "
                f"Total subscribers: {len(self.symbol_subscribers[symbol])}"
            )
            
            # Send recent trades for this symbol
            recent_trades = self.get_recent_trades(symbol, limit=50)
            if recent_trades:
                await websocket.send_json({
                    "type": "trade_history",
                    "symbol": symbol,
                    "trades": recent_trades
                })
        else:
            # Global trade subscription
            self.trade_subscribers.add(websocket)
            self.logger.info(
                f"WebSocket subscribed to all trades. "
                f"Total subscribers: {len(self.trade_subscribers)}"
            )
    
    async def unsubscribe_trades(self, websocket: WebSocket, symbol: Optional[str] = None) -> None:
        """
        Unsubscribe a WebSocket connection from trade feed.
        
        Args:
            websocket: WebSocket connection to unsubscribe
            symbol: Optional symbol filter
        """
        if symbol:
            if symbol in self.symbol_subscribers:
                self.symbol_subscribers[symbol].discard(websocket)
                if not self.symbol_subscribers[symbol]:
                    del self.symbol_subscribers[symbol]
                self.logger.info(
                    f"WebSocket unsubscribed from {symbol} trades. "
                    f"Remaining subscribers: "
                    f"{len(self.symbol_subscribers.get(symbol, set()))}"
                )
        else:
            self.trade_subscribers.discard(websocket)
            self.logger.info(
                f"WebSocket unsubscribed from all trades. "
                f"Remaining subscribers: {len(self.trade_subscribers)}"
            )
    
    async def broadcast_trade(self, trade: Trade, taker_order_id: UUID) -> None:
        """
        Broadcast a trade to all subscribers.
        
        Args:
            trade: Trade object to broadcast
            taker_order_id: ID of the taker order
        """
        # Store in history
        self._store_trade(trade)
        
        # Prepare trade message
        message = {
            "type": "trade",
            "timestamp": trade.timestamp.isoformat(),
            "symbol": trade.symbol,
            "trade_id": str(trade.trade_id),
            "price": str(trade.price),
            "quantity": str(trade.quantity),
            "aggressor_side": trade.aggressor_side.value.lower(),
            "maker_order_id": str(trade.maker_order_id),
            "taker_order_id": str(taker_order_id)
        }
        
        # Broadcast to global subscribers
        await self._broadcast_to_subscribers(self.trade_subscribers, message)
        
        # Broadcast to symbol-specific subscribers
        if trade.symbol in self.symbol_subscribers:
            await self._broadcast_to_subscribers(
                self.symbol_subscribers[trade.symbol],
                message
            )
    
    def get_recent_trades(self, symbol: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent trades for a symbol.
        
        Args:
            symbol: Trading pair symbol
            limit: Maximum number of trades to return
        
        Returns:
            List of trade dictionaries
        """
        if symbol not in self._trade_history:
            return []
        
        trades = list(self._trade_history[symbol])[-limit:]
        return [self._trade_to_dict(t) for t in trades]
    
    def _on_trade_executed(self, trade: Trade, taker_order_id: UUID) -> None:
        """
        Callback function called by matching engine when trade is executed.
        
        Args:
            trade: Trade object
            taker_order_id: ID of the taker order
        """
        # Create async task to broadcast
        asyncio.create_task(self.broadcast_trade(trade, taker_order_id))
    
    def _store_trade(self, trade: Trade) -> None:
        """
        Store trade in history.
        
        Args:
            trade: Trade to store
        """
        if trade.symbol not in self._trade_history:
            self._trade_history[trade.symbol] = deque(maxlen=self._max_history)
        
        self._trade_history[trade.symbol].append(trade)
    
    def _trade_to_dict(self, trade: Trade) -> Dict[str, Any]:
        """
        Convert Trade object to dictionary.
        
        Args:
            trade: Trade object
        
        Returns:
            Dictionary representation
        """
        return {
            "trade_id": str(trade.trade_id),
            "symbol": trade.symbol,
            "price": str(trade.price),
            "quantity": str(trade.quantity),
            "timestamp": trade.timestamp.isoformat(),
            "aggressor_side": trade.aggressor_side.value.lower(),
            "value": str(trade.value)
        }
    
    async def _broadcast_to_subscribers(
        self,
        subscribers: Set[WebSocket],
        message: Dict[str, Any]
    ) -> None:
        """
        Broadcast message to a set of WebSocket subscribers.
        
        Args:
            subscribers: Set of WebSocket connections
            message: Message to broadcast
        """
        if not subscribers:
            return
        
        dead_connections = []
        for ws in list(subscribers):
            try:
                await ws.send_json(message)
            except Exception as e:
                self.logger.warning(f"Failed to send to WebSocket: {e}")
                dead_connections.append(ws)
        
        # Clean up dead connections
        for ws in dead_connections:
            subscribers.discard(ws)
