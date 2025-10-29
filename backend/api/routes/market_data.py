"""
REST API endpoints for market data.

Provides endpoints for order book snapshots and market statistics.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends, Query, status

from backend.api.models import OrderBookResponse, BBOResponse
from backend.services.order_service import OrderService

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/v1", tags=["market-data"])


# Dependency injection for OrderService
_order_service: OrderService = None


def get_order_service() -> OrderService:
    """Dependency to get OrderService instance."""
    if _order_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Order service not initialized"
        )
    return _order_service


def set_order_service(service: OrderService) -> None:
    """Set the global OrderService instance."""
    global _order_service
    _order_service = service


@router.get(
    "/orderbook/{symbol}",
    response_model=OrderBookResponse,
    summary="Get order book snapshot",
    description="Retrieve current order book snapshot for a trading pair",
    responses={
        200: {
            "description": "Order book snapshot retrieved successfully",
            "model": OrderBookResponse
        },
        404: {
            "description": "Symbol not found"
        }
    }
)
async def get_orderbook(
    symbol: str,
    levels: int = Query(default=10, ge=1, le=100, description="Number of price levels to return"),
    order_service: OrderService = Depends(get_order_service)
) -> OrderBookResponse:
    """
    Get current order book snapshot.
    
    **Path Parameters:**
    - `symbol`: Trading pair symbol (e.g., BTC-USDT)
    
    **Query Parameters:**
    - `levels`: Number of price levels (1-100, default 10)
    
    **Response:**
    - Order book with bids, asks, and BBO
    
    **Example:**
    ```
    GET /api/v1/orderbook/BTC-USDT?levels=10
    ```
    
    **Response Format:**
    ```json
    {
      "symbol": "BTC-USDT",
      "timestamp": "2025-10-25T10:30:45.123456",
      "bids": [["50000.00", "1.5"], ["49999.00", "2.3"]],
      "asks": [["50001.00", "0.8"], ["50002.00", "1.2"]],
      "bbo": {
        "best_bid": "50000.00",
        "best_ask": "50001.00",
        "spread": "1.00"
      }
    }
    ```
    """
    try:
        logger.debug(f"Getting order book snapshot for {symbol}, levels={levels}")
        
        snapshot = order_service.get_order_book_snapshot(symbol, levels)
        
        return OrderBookResponse(
            symbol=snapshot['symbol'],
            timestamp=datetime.now(timezone.utc),
            bids=snapshot['bids'],
            asks=snapshot['asks'],
            bbo=BBOResponse(**snapshot['bbo'])
        )
        
    except Exception as e:
        logger.error(f"Error getting order book: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
