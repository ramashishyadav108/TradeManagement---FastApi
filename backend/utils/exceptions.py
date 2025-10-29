"""
Custom exceptions for matching engine

This module defines a hierarchy of exceptions used throughout the matching engine
to handle various error conditions in a structured and meaningful way.
"""


class BaseMatchingEngineException(Exception):
    """Base exception class for all matching engine exceptions."""
    
    def __init__(self, message: str, details: dict = None):
        """
        Initialize the exception.
        
        Args:
            message: Human-readable error message
            details: Optional dictionary with additional error context
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}


class InvalidOrderException(BaseMatchingEngineException):
    """Raised when an order contains invalid parameters or fails validation."""
    pass


class ValidationException(BaseMatchingEngineException):
    """Raised when input validation fails."""
    pass


class OrderNotFoundException(BaseMatchingEngineException):
    """Raised when attempting to access an order that doesn't exist."""
    pass


class InsufficientLiquidityException(BaseMatchingEngineException):
    """Raised when there is not enough liquidity to fill an order."""
    pass


class TradeThroughException(BaseMatchingEngineException):
    """Raised when an order would execute at a worse price than the current BBO."""
    pass


class PriceOutOfBoundsException(BaseMatchingEngineException):
    """Raised when a price is outside acceptable bounds."""
    pass


class InvalidQuantityException(BaseMatchingEngineException):
    """Raised when quantity is invalid (negative, zero, or exceeds limits)."""
    pass


class InvalidSymbolException(BaseMatchingEngineException):
    """Raised when a trading symbol is invalid or not supported."""
    pass


class DuplicateOrderException(BaseMatchingEngineException):
    """Raised when attempting to add an order that already exists."""
    pass


class OrderBookException(BaseMatchingEngineException):
    """Raised for general order book operation errors."""
    pass
