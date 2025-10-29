"""
Configuration management using Pydantic

This module provides application-wide configuration using Pydantic BaseSettings
with support for environment variables and type validation.
"""

from decimal import Decimal
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """
    Application configuration settings.
    
    All settings can be overridden using environment variables.
    For example, BACKEND_HOST will override backend_host.
    """
    
    # API Configuration
    backend_host: str = Field(default="localhost", description="Backend server host")
    backend_port: int = Field(default=8000, description="Backend server port")
    ws_host: str = Field(default="localhost", description="WebSocket host")
    ws_port: int = Field(default=8000, description="WebSocket port")
    allowed_origins: List[str] = Field(
        default=["*"],
        description="CORS allowed origins"
    )
    
    # Trading Parameters
    min_order_quantity: Decimal = Field(
        default=Decimal("0.00000001"),
        description="Minimum order quantity"
    )
    max_order_quantity: Decimal = Field(
        default=Decimal("1000000"),
        description="Maximum order quantity"
    )
    price_precision: int = Field(
        default=2,
        description="Number of decimal places for prices"
    )
    quantity_precision: int = Field(
        default=8,
        description="Number of decimal places for quantities"
    )
    min_price: Decimal = Field(
        default=Decimal("0.01"),
        description="Minimum acceptable price"
    )
    max_price: Decimal = Field(
        default=Decimal("10000000"),
        description="Maximum acceptable price"
    )
    
    # Supported Trading Symbols
    supported_symbols: List[str] = Field(
        default=["BTC-USDT", "ETH-USDT", "BNB-USDT", "SOL-USDT"],
        description="List of supported trading pairs"
    )
    
    # Performance Settings
    max_orders_per_second: int = Field(
        default=1000,
        description="Maximum orders processed per second"
    )
    websocket_buffer_size: int = Field(
        default=1000,
        description="WebSocket message buffer size"
    )
    max_orderbook_levels: int = Field(
        default=100,
        description="Maximum price levels to maintain in order book"
    )
    
    # WebSocket Configuration
    ws_heartbeat_interval: int = Field(
        default=30,
        description="WebSocket heartbeat interval in seconds"
    )
    ws_max_connections: int = Field(
        default=1000,
        description="Maximum concurrent WebSocket connections"
    )
    
    # Logging Configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    log_dir: str = Field(
        default="logs",
        description="Directory for log files"
    )
    enable_metrics: bool = Field(
        default=True,
        description="Enable performance metrics collection"
    )
    metrics_interval: int = Field(
        default=60,
        description="Metrics collection interval in seconds"
    )
    
    # Testing Configuration
    enable_testing_mode: bool = Field(
        default=False,
        description="Enable testing mode with relaxed constraints"
    )
    
    class Config:
        env_file = "backend/.env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """
    Get the global settings instance.
    
    Returns:
        Settings instance
    """
    return settings
