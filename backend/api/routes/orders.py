"""
REST API endpoints for order operations.

Provides endpoints for order submission, cancellation, and status queries.
"""

import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import ValidationError

from backend.api.models import (
    OrderRequest,
    OrderResponse,
    OrderStatusResponse,
    CancelOrderResponse,
    ErrorResponse
)
from backend.services.order_service import OrderService
from backend.utils.exceptions import (
    InvalidOrderException,
    OrderNotFoundException,
    ValidationException
)

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/v1/orders", tags=["orders"])


# Dependency injection for OrderService
# This will be overridden in main.py with actual instance
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


@router.post(
    "",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new order",
    description="Submit a new order to the matching engine. "
                "Supports market, limit, IOC, and FOK orders.",
    responses={
        201: {
            "description": "Order submitted successfully",
            "model": OrderResponse
        },
        400: {
            "description": "Invalid order parameters",
            "model": ErrorResponse
        },
        422: {
            "description": "Validation error",
            "model": ErrorResponse
        },
        503: {
            "description": "Service unavailable"
        }
    }
)
async def submit_order(
    order_request: OrderRequest,
    order_service: OrderService = Depends(get_order_service)
) -> OrderResponse:
    """
    Submit a new order.
    
    **Request Body:**
    - `symbol`: Trading pair (e.g., BTC-USDT)
    - `order_type`: market, limit, ioc, or fok
    - `side`: buy or sell
    - `quantity`: Order quantity (positive decimal)
    - `price`: Limit price (required for limit/ioc/fok orders)
    
    **Response:**
    - Order details including status, fills, and trades
    
    **Example:**
    ```json
    {
      "symbol": "BTC-USDT",
      "order_type": "limit",
      "side": "buy",
      "quantity": "0.5",
      "price": "50000.00"
    }
    ```
    """
    try:
        logger.info(
            f"Received order request: {order_request.order_type} {order_request.side} "
            f"{order_request.quantity} {order_request.symbol}"
        )
        
        # Convert request to order parameters
        params = order_request.to_order_params()
        
        # Submit order
        result = order_service.submit_order(
            symbol=params['symbol'],
            order_type=params['order_type'],
            side=params['side'],
            quantity=params['quantity'],
            price=params.get('price')
        )
        
        # Convert to response
        response = OrderResponse.from_order_result(result)
        
        logger.info(
            f"Order submitted successfully: {result.order.order_id}, "
            f"status={result.order.status.value}"
        )
        
        return response
        
    except ValidationException as e:
        logger.warning(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except InvalidOrderException as e:
        logger.warning(f"Invalid order: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error submitting order: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.delete(
    "/{order_id}",
    response_model=CancelOrderResponse,
    summary="Cancel an order",
    description="Cancel an existing order by ID",
    responses={
        200: {
            "description": "Order cancelled successfully",
            "model": CancelOrderResponse
        },
        404: {
            "description": "Order not found",
            "model": ErrorResponse
        },
        400: {
            "description": "Invalid request",
            "model": ErrorResponse
        }
    }
)
async def cancel_order(
    order_id: UUID,
    symbol: str,
    order_service: OrderService = Depends(get_order_service)
) -> CancelOrderResponse:
    """
    Cancel an existing order.
    
    **Path Parameters:**
    - `order_id`: UUID of the order to cancel
    
    **Query Parameters:**
    - `symbol`: Trading pair symbol (for validation)
    
    **Response:**
    - Cancellation confirmation
    
    **Example:**
    ```
    DELETE /api/v1/orders/550e8400-e29b-41d4-a716-446655440000?symbol=BTC-USDT
    ```
    """
    try:
        logger.info(f"Cancelling order {order_id} for {symbol}")
        
        success = order_service.cancel_order(order_id, symbol)
        
        return CancelOrderResponse(
            order_id=order_id,
            cancelled=success,
            message="Order cancelled successfully"
        )
        
    except OrderNotFoundException as e:
        logger.warning(f"Order not found: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except InvalidOrderException as e:
        logger.warning(f"Invalid cancellation request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error cancelling order: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get(
    "/{order_id}",
    response_model=OrderStatusResponse,
    summary="Get order status",
    description="Retrieve current status and details of an order",
    responses={
        200: {
            "description": "Order details retrieved successfully",
            "model": OrderStatusResponse
        },
        404: {
            "description": "Order not found",
            "model": ErrorResponse
        }
    }
)
async def get_order_status(
    order_id: UUID,
    symbol: str,
    order_service: OrderService = Depends(get_order_service)
) -> OrderStatusResponse:
    """
    Get order status and details.
    
    **Path Parameters:**
    - `order_id`: UUID of the order to query
    
    **Query Parameters:**
    - `symbol`: Trading pair symbol
    
    **Response:**
    - Complete order details including fill status
    
    **Example:**
    ```
    GET /api/v1/orders/550e8400-e29b-41d4-a716-446655440000?symbol=BTC-USDT
    ```
    """
    try:
        logger.debug(f"Getting status for order {order_id}")
        
        order = order_service.get_order_status(order_id, symbol)
        
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order {order_id} not found for symbol {symbol}"
            )
        
        return OrderStatusResponse.from_order(order)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting order status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
