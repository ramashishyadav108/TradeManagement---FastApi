"""
WebSocket endpoint for real-time order book streaming.
"""

import logging
import asyncio
from fastapi import WebSocket, WebSocketDisconnect, APIRouter

from backend.services.market_data_service import MarketDataService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

# Global service instance
_market_data_service: MarketDataService = None


def set_market_data_service(service: MarketDataService) -> None:
    """Set the global MarketDataService instance."""
    global _market_data_service
    _market_data_service = service


@router.websocket("/ws/orderbook/{symbol}")
async def orderbook_websocket(websocket: WebSocket, symbol: str):
    """
    WebSocket endpoint for real-time order book updates.
    
    Sends initial snapshot on connection, then streams delta updates.
    Implements heartbeat/ping-pong every 30 seconds.
    """
    await websocket.accept()
    logger.info(f"WebSocket connected for {symbol} order book")
    
    try:
        # Subscribe to order book updates
        await _market_data_service.subscribe_orderbook(websocket, symbol)
        
        # Keep connection alive and handle heartbeat
        last_ping = asyncio.get_event_loop().time()
        
        while True:
            # Send ping every 30 seconds
            current_time = asyncio.get_event_loop().time()
            if current_time - last_ping > 30:
                await websocket.send_json({"type": "ping"})
                last_ping = current_time
            
            # Wait for messages from client (like pong)
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=1.0)
                if data.get("type") == "pong":
                    logger.debug(f"Received pong from {symbol} subscriber")
            except asyncio.TimeoutError:
                # No message received, continue
                pass
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for {symbol} order book")
    except Exception as e:
        logger.error(f"Error in orderbook WebSocket: {e}", exc_info=True)
    finally:
        await _market_data_service.unsubscribe_orderbook(websocket, symbol)
