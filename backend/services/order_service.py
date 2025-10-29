"""
Order Service - Business logic layer for order operations.

This service handles order submission, cancellation, and validation,
acting as an intermediary between the API layer and the matching engine.
"""

import logging
from decimal import Decimal
from typing import Optional, Dict, Any
from uuid import UUID

from backend.core.matching_engine import MatchingEngine
from backend.core.order import Order, OrderType, OrderSide, OrderResult
from backend.utils.exceptions import (
    InvalidOrderException,
    OrderNotFoundException,
    ValidationException
)

logger = logging.getLogger(__name__)


class OrderService:
    """
    Service class for handling order operations.
    
    Provides business logic layer between API and matching engine,
    including validation, error handling, and order management.
    """
    
    def __init__(self, matching_engine: MatchingEngine):
        """
        Initialize order service.
        
        Args:
            matching_engine: Reference to the matching engine instance
        """
        self.matching_engine = matching_engine
        self.logger = logging.getLogger(f"{__name__}.OrderService")
        self.logger.info("OrderService initialized")
    
    def submit_order(
        self,
        symbol: str,
        order_type: OrderType,
        side: OrderSide,
        quantity: Decimal,
        price: Optional[Decimal] = None
    ) -> OrderResult:
        """
        Submit a new order to the matching engine.
        
        Args:
            symbol: Trading pair symbol (e.g., "BTC-USDT")
            order_type: Type of order (MARKET, LIMIT, IOC, FOK)
            side: Order side (BUY or SELL)
            quantity: Order quantity
            price: Limit price (required for non-market orders)
        
        Returns:
            OrderResult containing order details and trades
        
        Raises:
            ValidationException: If order parameters are invalid
            InvalidOrderException: If order cannot be processed
        """
        # Validate order parameters
        self._validate_order_params(symbol, order_type, side, quantity, price)
        
        try:
            # Create order
            order = Order(
                symbol=symbol,
                order_type=order_type,
                side=side,
                quantity=quantity,
                price=price
            )
            
            self.logger.info(
                f"Submitting order: {order_type.value} {side.value} "
                f"{quantity} {symbol} @ {price or 'MARKET'}"
            )
            
            # Submit to matching engine
            result = self.matching_engine.submit_order(order)
            
            self.logger.info(
                f"Order {order.order_id} submitted successfully. "
                f"Status: {result.order.status.value}, "
                f"Filled: {result.order.filled_quantity}/{result.order.quantity}, "
                f"Trades: {len(result.trades)}"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error submitting order: {str(e)}", exc_info=True)
            raise InvalidOrderException(f"Failed to submit order: {str(e)}")
    
    def cancel_order(self, order_id: UUID, symbol: str) -> bool:
        """
        Cancel an existing order.
        
        Args:
            order_id: ID of the order to cancel
            symbol: Symbol of the order (for validation)
        
        Returns:
            True if order was cancelled successfully
        
        Raises:
            OrderNotFoundException: If order doesn't exist
            InvalidOrderException: If order cannot be cancelled
        """
        try:
            self.logger.info(f"Cancelling order {order_id} for {symbol}")
            
            # Cancel order in matching engine
            success = self.matching_engine.cancel_order(order_id, symbol)
            
            if not success:
                raise OrderNotFoundException(f"Order {order_id} not found for symbol {symbol}")
            
            self.logger.info(f"Order {order_id} cancelled successfully")
            return True
            
        except OrderNotFoundException:
            raise
        except Exception as e:
            self.logger.error(f"Error cancelling order {order_id}: {str(e)}", exc_info=True)
            raise InvalidOrderException(f"Failed to cancel order: {str(e)}")
    
    def get_order_status(self, order_id: UUID, symbol: str) -> Optional[Order]:
        """
        Get the current status of an order.
        
        Args:
            order_id: ID of the order to query
            symbol: Symbol of the order
        
        Returns:
            Order object if found, None otherwise
        """
        try:
            order = self.matching_engine.get_order_status(order_id, symbol)
            if order:
                self.logger.debug(
                    f"Order {order_id} status: {order.status.value}, "
                    f"filled {order.filled_quantity}/{order.quantity}"
                )
            return order
        except Exception as e:
            self.logger.error(f"Error getting order status {order_id}: {str(e)}")
            return None
    
    def validate_order_request(self, params: Dict[str, Any]) -> bool:
        """
        Validate order request parameters.
        
        Args:
            params: Dictionary of order parameters
        
        Returns:
            True if validation passes
        
        Raises:
            ValidationException: If validation fails
        """
        required_fields = ['symbol', 'order_type', 'side', 'quantity']
        
        # Check required fields
        for field in required_fields:
            if field not in params or params[field] is None:
                raise ValidationException(f"Missing required field: {field}")
        
        # Validate order type
        order_type_str = params['order_type'].upper()
        if order_type_str not in [ot.value for ot in OrderType]:
            raise ValidationException(
                f"Invalid order type: {params['order_type']}. "
                f"Must be one of: {', '.join([ot.value.lower() for ot in OrderType])}"
            )
        
        # Validate side
        side_str = params['side'].upper()
        if side_str not in [s.value for s in OrderSide]:
            raise ValidationException(
                f"Invalid side: {params['side']}. Must be 'buy' or 'sell'"
            )
        
        # Validate price requirement
        order_type = OrderType[order_type_str]
        if order_type != OrderType.MARKET:
            if 'price' not in params or params['price'] is None:
                raise ValidationException(
                    f"Price is required for {order_type.value} orders"
                )
        
        return True
    
    def _validate_order_params(
        self,
        symbol: str,
        order_type: OrderType,
        side: OrderSide,
        quantity: Decimal,
        price: Optional[Decimal]
    ) -> None:
        """
        Internal validation of order parameters.
        
        Args:
            symbol: Trading pair symbol
            order_type: Order type
            side: Order side
            quantity: Order quantity
            price: Order price
        
        Raises:
            ValidationException: If any parameter is invalid
        """
        # Validate symbol format
        if not symbol or len(symbol) < 3 or '-' not in symbol:
            raise ValidationException(
                f"Invalid symbol format: {symbol}. Must be in format XXX-YYY"
            )
        
        # Validate quantity
        if quantity <= 0:
            raise ValidationException("Quantity must be positive")
        
        if quantity > Decimal("1000000"):
            raise ValidationException("Quantity exceeds maximum allowed (1,000,000)")
        
        # Validate price for non-market orders
        if order_type != OrderType.MARKET:
            if price is None:
                raise ValidationException(
                    f"Price is required for {order_type.value} orders"
                )
            if price <= 0:
                raise ValidationException("Price must be positive")
            if price > Decimal("10000000"):
                raise ValidationException("Price exceeds maximum allowed (10,000,000)")
        
        # Market orders should not have a price
        if order_type == OrderType.MARKET and price is not None:
            self.logger.warning(
                "Market order submitted with price. Price will be ignored."
            )
    
    def get_order_book_snapshot(self, symbol: str, levels: int = 10) -> Dict[str, Any]:
        """
        Get current order book snapshot.
        
        Args:
            symbol: Trading pair symbol
            levels: Number of price levels to return
        
        Returns:
            Dictionary containing order book data
        """
        try:
            order_book = self.matching_engine.get_order_book(symbol)
            if not order_book:
                return {
                    'symbol': symbol,
                    'bids': [],
                    'asks': [],
                    'bbo': {
                        'best_bid': None,
                        'best_ask': None,
                        'spread': None
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
            
            return {
                'symbol': symbol,
                'bids': [[str(price), str(volume)] for price, volume in bids],
                'asks': [[str(price), str(volume)] for price, volume in asks],
                'bbo': {
                    'best_bid': str(best_bid) if best_bid else None,
                    'best_ask': str(best_ask) if best_ask else None,
                    'spread': spread
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error getting order book snapshot: {str(e)}")
            raise
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get matching engine statistics.
        
        Returns:
            Dictionary containing engine statistics
        """
        return self.matching_engine.get_statistics()
