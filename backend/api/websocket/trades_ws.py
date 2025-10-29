"""
WebSocket endpoint for real-time trade feed streaming.
"""

import logging
import asyncio
from typing import Optional
from fastapi import WebSocket, WebSocketDisconnect, APIRouter

from backend.services.trade_service import TradeService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

# Global service instance
_trade_service: TradeService = None


def set_trade_service(service: TradeService) -> None:
    """Set the global TradeService instance."""
    global _trade_service
    _trade_service = service


@router.websocket("/ws/trades/{symbol}")
async def trades_websocket(websocket: WebSocket, symbol: str):
    """
    WebSocket endpoint for real-time trade feed (symbol-specific).
    
    Sends last 50 trades on connection, then streams new trades in real-time.
    """
    await websocket.accept()
    logger.info(f"WebSocket connected for {symbol} trade feed")
    
    try:
        # Subscribe to trade feed
        await _trade_service.subscribe_trades(websocket, symbol=symbol)
        
        # Keep connection alive
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({"type": "heartbeat"})
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for {symbol} trade feed")
    except Exception as e:
        logger.error(f"Error in trade WebSocket: {e}", exc_info=True)
    finally:
        await _trade_service.unsubscribe_trades(websocket, symbol=symbol)


@router.websocket("/ws/trades")
async def all_trades_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time trade feed (all symbols).
    
    Streams all trades across all symbols in real-time.
    """
    await websocket.accept()
    logger.info("WebSocket connected for all trades feed")
    
    try:
        # Subscribe to all trades
        await _trade_service.subscribe_trades(websocket, symbol=None)
        
        # Keep connection alive
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({"type": "heartbeat"})
            
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for all trades feed")
    except Exception as e:
        logger.error(f"Error in all trades WebSocket: {e}", exc_info=True)
    finally:
        await _trade_service.unsubscribe_trades(websocket, symbol=None)
