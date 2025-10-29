"""
FastAPI Application - Main Entry Point

Complete REST and WebSocket API for the cryptocurrency matching engine.
"""

import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Dict, Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from backend.core.matching_engine import MatchingEngine
from backend.services.order_service import OrderService
from backend.services.market_data_service import MarketDataService
from backend.services.trade_service import TradeService
from backend.utils.exceptions import (
    InvalidOrderException,
    OrderNotFoundException,
    ValidationException
)

# Import routers
from backend.api.routes import orders, market_data
from backend.api.websocket import market_data_ws, trades_ws
from backend.api.models import HealthResponse, ErrorResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global instances
matching_engine: MatchingEngine = None
order_service: OrderService = None
market_data_service: MarketDataService = None
trade_service: TradeService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    
    Initializes global services on startup and cleans up on shutdown.
    """
    # Startup
    logger.info("=" * 80)
    logger.info("Starting Cryptocurrency Matching Engine API")
    logger.info("=" * 80)
    
    global matching_engine, order_service, market_data_service, trade_service
    
    # Initialize matching engine
    logger.info("Initializing matching engine...")
    matching_engine = MatchingEngine()
    
    # Initialize services
    logger.info("Initializing services...")
    order_service = OrderService(matching_engine)
    market_data_service = MarketDataService(matching_engine)
    trade_service = TradeService(matching_engine)
    
    # Set service instances in routers
    orders.set_order_service(order_service)
    market_data.set_order_service(order_service)
    market_data_ws.set_market_data_service(market_data_service)
    trades_ws.set_trade_service(trade_service)
    
    # Start background tasks
    logger.info("Starting background tasks...")
    await market_data_service.start_broadcasting()
    
    logger.info("API startup complete!")
    logger.info("Swagger UI available at: http://localhost:8000/docs")
    logger.info("ReDoc available at: http://localhost:8000/redoc")
    logger.info("=" * 80)
    
    yield
    
    # Shutdown
    logger.info("=" * 80)
    logger.info("Shutting down API...")
    logger.info("=" * 80)
    
    # Stop background tasks
    logger.info("Stopping background tasks...")
    await market_data_service.stop_broadcasting()
    
    logger.info("API shutdown complete!")


# Create FastAPI application
app = FastAPI(
    title="Cryptocurrency Matching Engine API",
    description="""
    High-performance matching engine for cryptocurrency trading with REG NMS compliance.
    
    ## Features
    * **Order Types**: Market, Limit, IOC (Immediate-Or-Cancel), FOK (Fill-Or-Kill)
    * **Real-time Streams**: WebSocket order book and trade feeds
    * **REG NMS Compliant**: Price-time priority, trade-through prevention
    * **High Performance**: Sub-millisecond matching latency
    
    ## Endpoints
    * **POST /api/v1/orders**: Submit new order
    * **DELETE /api/v1/orders/{order_id}**: Cancel order
    * **GET /api/v1/orders/{order_id}**: Get order status
    * **GET /api/v1/orderbook/{symbol}**: Get order book snapshot
    * **WS /ws/orderbook/{symbol}**: Real-time order book stream
    * **WS /ws/trades/{symbol}**: Real-time trade feed
    * **WS /ws/trades**: All trades feed
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development - restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add unique request ID to each request for tracking."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    # Add to response headers
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    
    return response


# Logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests and responses."""
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.info(
        f"Request [{request_id}]: {request.method} {request.url.path} "
        f"from {request.client.host if request.client else 'unknown'}"
    )
    
    response = await call_next(request)
    
    logger.info(
        f"Response [{request_id}]: {response.status_code}"
    )
    
    return response


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors."""
    request_id = getattr(request.state, "request_id", "unknown")
    logger.warning(f"Validation error [{request_id}]: {exc.errors()}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            error="ValidationError",
            message="Request validation failed",
            detail=str(exc.errors()),
            timestamp=datetime.now(timezone.utc)
        ).model_dump(mode='json')
    )


@app.exception_handler(ValidationException)
async def custom_validation_exception_handler(request: Request, exc: ValidationException):
    """Handle custom validation exceptions."""
    request_id = getattr(request.state, "request_id", "unknown")
    logger.warning(f"Validation error [{request_id}]: {str(exc)}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            error="ValidationError",
            message=str(exc),
            timestamp=datetime.now(timezone.utc)
        ).model_dump(mode='json')
    )


@app.exception_handler(InvalidOrderException)
async def invalid_order_exception_handler(request: Request, exc: InvalidOrderException):
    """Handle invalid order exceptions."""
    request_id = getattr(request.state, "request_id", "unknown")
    logger.warning(f"Invalid order [{request_id}]: {str(exc)}")
    
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=ErrorResponse(
            error="InvalidOrderException",
            message=str(exc),
            timestamp=datetime.now(timezone.utc)
        ).model_dump(mode='json')
    )


@app.exception_handler(OrderNotFoundException)
async def order_not_found_exception_handler(request: Request, exc: OrderNotFoundException):
    """Handle order not found exceptions."""
    request_id = getattr(request.state, "request_id", "unknown")
    logger.warning(f"Order not found [{request_id}]: {str(exc)}")
    
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=ErrorResponse(
            error="OrderNotFoundException",
            message=str(exc),
            timestamp=datetime.now(timezone.utc)
        ).model_dump(mode='json')
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions."""
    request_id = getattr(request.state, "request_id", "unknown")
    logger.error(f"Unhandled exception [{request_id}]: {str(exc)}", exc_info=True)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="InternalServerError",
            message="An internal error occurred",
            detail="Contact support with request ID: " + request_id,
            timestamp=datetime.now(timezone.utc)
        ).model_dump(mode='json')
    )


# Health check endpoint
@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["health"],
    summary="Health check",
    description="Check API and matching engine health status"
)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.
    
    Returns service status and matching engine statistics.
    """
    stats = matching_engine.get_statistics() if matching_engine else {}

    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc),
        version="1.0.0",
        matching_engine=stats
    )


# Include routers
app.include_router(orders.router)
app.include_router(market_data.router)
app.include_router(market_data_ws.router)
app.include_router(trades_ws.router)


# Root endpoint
@app.get("/", tags=["root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Cryptocurrency Matching Engine API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
