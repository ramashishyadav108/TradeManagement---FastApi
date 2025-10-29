"""
Logging configuration and utilities for the matching engine.

Provides structured logging with JSON format for production environments
and human-readable format for development.
"""

import logging
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from decimal import Decimal
from uuid import UUID


class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging.
    
    Converts log records to JSON format with additional context fields.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON string."""
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add extra fields if present
        if hasattr(record, "order_id"):
            log_data["order_id"] = str(record.order_id)
        if hasattr(record, "trade_id"):
            log_data["trade_id"] = str(record.trade_id)
        if hasattr(record, "symbol"):
            log_data["symbol"] = record.symbol
        if hasattr(record, "execution_time_ms"):
            log_data["execution_time_ms"] = record.execution_time_ms
        if hasattr(record, "correlation_id"):
            log_data["correlation_id"] = record.correlation_id
            
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_data)


class MatchingEngineLogger:
    """
    Centralized logger for the matching engine.
    
    Provides structured logging with correlation IDs and performance metrics.
    Supports both JSON (production) and console (development) formats.
    """
    
    def __init__(
        self,
        name: str = "MatchingEngine",
        log_level: str = "INFO",
        log_dir: Optional[Path] = None,
        use_json: bool = False,
    ):
        """
        Initialize the matching engine logger.
        
        Args:
            name: Logger name
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_dir: Directory for log files (None for console only)
            use_json: Use JSON formatting (for production)
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        self.logger.handlers.clear()  # Remove existing handlers
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        
        if use_json:
            console_handler.setFormatter(JSONFormatter())
        else:
            console_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            console_handler.setFormatter(console_formatter)
        
        self.logger.addHandler(console_handler)
        
        # File handlers if log_dir is specified
        if log_dir:
            log_dir = Path(log_dir)
            log_dir.mkdir(parents=True, exist_ok=True)
            
            # Application log
            app_handler = self._create_file_handler(
                log_dir / "application.log",
                use_json
            )
            self.logger.addHandler(app_handler)
            
            # Trade log
            self.trade_logger = logging.getLogger(f"{name}.trades")
            self.trade_logger.setLevel(logging.INFO)
            trade_handler = self._create_file_handler(
                log_dir / "trades.log",
                use_json
            )
            self.trade_logger.addHandler(trade_handler)
            
            # Order log
            self.order_logger = logging.getLogger(f"{name}.orders")
            self.order_logger.setLevel(logging.INFO)
            order_handler = self._create_file_handler(
                log_dir / "orders.log",
                use_json
            )
            self.order_logger.addHandler(order_handler)
            
            # Error log
            error_handler = self._create_file_handler(
                log_dir / "errors.log",
                use_json
            )
            error_handler.setLevel(logging.ERROR)
            self.logger.addHandler(error_handler)
        else:
            self.trade_logger = self.logger
            self.order_logger = self.logger
    
    def _create_file_handler(
        self,
        filepath: Path,
        use_json: bool
    ) -> logging.FileHandler:
        """Create a file handler with appropriate formatter."""
        handler = logging.FileHandler(filepath)
        
        if use_json:
            handler.setFormatter(JSONFormatter())
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
        
        return handler
    
    def log_order_submission(
        self,
        order_id: UUID,
        symbol: str,
        order_type: str,
        side: str,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        correlation_id: Optional[str] = None,
    ):
        """Log order submission."""
        extra = {
            "order_id": order_id,
            "symbol": symbol,
            "correlation_id": correlation_id or str(order_id),
        }
        
        if price is not None:
            msg = f"Order submitted: {side} {quantity} {symbol} @ {price} ({order_type})"
        else:
            msg = f"Order submitted: {side} {quantity} {symbol} MARKET ({order_type})"
        
        self.order_logger.info(msg, extra=extra)
    
    def log_trade_execution(
        self,
        trade_id: UUID,
        symbol: str,
        price: Decimal,
        quantity: Decimal,
        aggressor_side: str,
        maker_order_id: UUID,
        taker_order_id: UUID,
        execution_time_ms: Optional[float] = None,
    ):
        """Log trade execution."""
        extra = {
            "trade_id": trade_id,
            "symbol": symbol,
            "execution_time_ms": execution_time_ms,
        }
        
        msg = (
            f"Trade executed: {quantity} {symbol} @ {price} "
            f"(aggressor: {aggressor_side}, maker: {maker_order_id}, taker: {taker_order_id})"
        )
        
        self.trade_logger.info(msg, extra=extra)
    
    def log_order_cancellation(
        self,
        order_id: UUID,
        symbol: str,
        reason: str = "User requested",
    ):
        """Log order cancellation."""
        extra = {"order_id": order_id, "symbol": symbol}
        msg = f"Order cancelled: {order_id} ({reason})"
        self.order_logger.info(msg, extra=extra)
    
    def log_performance_metrics(
        self,
        orders_processed: int,
        trades_executed: int,
        avg_latency_ms: float,
        max_latency_ms: float,
    ):
        """Log performance metrics."""
        msg = (
            f"Performance: {orders_processed} orders, {trades_executed} trades, "
            f"avg latency: {avg_latency_ms:.3f}ms, max latency: {max_latency_ms:.3f}ms"
        )
        self.logger.debug(msg)
    
    def log_error(
        self,
        message: str,
        exception: Optional[Exception] = None,
        **kwargs
    ):
        """Log error with optional exception."""
        if exception:
            self.logger.error(message, exc_info=exception, extra=kwargs)
        else:
            self.logger.error(message, extra=kwargs)
    
    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self.logger.debug(message, extra=kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message."""
        self.logger.info(message, extra=kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self.logger.warning(message, extra=kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message."""
        self.logger.error(message, extra=kwargs)


# Global logger instance
_logger: Optional[MatchingEngineLogger] = None


def get_logger(
    name: str = "MatchingEngine",
    log_level: str = "INFO",
    log_dir: Optional[Path] = None,
    use_json: bool = False,
) -> MatchingEngineLogger:
    """
    Get or create the global logger instance.
    
    Args:
        name: Logger name
        log_level: Logging level
        log_dir: Directory for log files
        use_json: Use JSON formatting
        
    Returns:
        MatchingEngineLogger instance
    """
    global _logger
    
    if _logger is None:
        _logger = MatchingEngineLogger(name, log_level, log_dir, use_json)
    
    return _logger

