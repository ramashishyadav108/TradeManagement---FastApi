"""
BBO (Best Bid Offer) calculation and tracking

This module manages the best bid and offer prices with change tracking
and notification capabilities using the observer pattern.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Callable, Dict, List


class BBOManager:
    """
    Manages Best Bid and Offer (BBO) tracking with change notifications.
    
    This class implements the observer pattern to notify subscribers
    when the BBO changes, enabling real-time market data distribution.
    
    Attributes:
        current_bbo: Current best bid and offer
        previous_bbo: Previous best bid and offer
        update_count: Number of BBO updates
        last_update_time: Timestamp of last update
    """
    
    def __init__(self, symbol: str):
        """
        Initialize BBO manager for a symbol.
        
        Args:
            symbol: Trading pair symbol
        """
        self.symbol: str = symbol
        self.current_bbo: Dict[str, Optional[Decimal]] = {
            "best_bid": None,
            "best_ask": None,
            "spread": None,
            "mid_price": None,
        }
        self.previous_bbo: Dict[str, Optional[Decimal]] = {
            "best_bid": None,
            "best_ask": None,
            "spread": None,
            "mid_price": None,
        }
        self.update_count: int = 0
        self.last_update_time: Optional[datetime] = None
        self._observers: List[Callable] = []
    
    def update_bbo(
        self,
        best_bid: Optional[Decimal],
        best_ask: Optional[Decimal]
    ) -> bool:
        """
        Update the BBO with new values.
        
        Args:
            best_bid: New best bid price
            best_ask: New best ask price
            
        Returns:
            True if BBO changed, False otherwise
        """
        # Store previous values
        self.previous_bbo = self.current_bbo.copy()
        
        # Calculate spread and mid price
        spread = None
        mid_price = None
        
        if best_bid is not None and best_ask is not None:
            spread = best_ask - best_bid
            mid_price = (best_bid + best_ask) / Decimal("2")
        
        # Update current BBO
        self.current_bbo = {
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": spread,
            "mid_price": mid_price,
        }
        
        self.update_count += 1
        self.last_update_time = datetime.now(timezone.utc)
        
        # Check if BBO actually changed
        changed = self.has_changed()
        
        # Notify observers if changed
        if changed:
            self._notify_observers()
        
        return changed
    
    def get_bbo(self) -> Dict[str, Optional[Decimal]]:
        """
        Get current BBO.
        
        Returns:
            Dictionary with best_bid, best_ask, spread, mid_price
        """
        return self.current_bbo.copy()
    
    def has_changed(self) -> bool:
        """
        Check if BBO changed from previous update.
        
        Returns:
            True if best_bid or best_ask changed
        """
        return (
            self.current_bbo["best_bid"] != self.previous_bbo["best_bid"] or
            self.current_bbo["best_ask"] != self.previous_bbo["best_ask"]
        )
    
    def register_observer(self, callback: Callable) -> None:
        """
        Register an observer to be notified of BBO changes.
        
        Args:
            callback: Function to call when BBO changes
        """
        if callback not in self._observers:
            self._observers.append(callback)
    
    def unregister_observer(self, callback: Callable) -> None:
        """
        Unregister an observer.
        
        Args:
            callback: Function to remove from observers
        """
        if callback in self._observers:
            self._observers.remove(callback)
    
    def _notify_observers(self) -> None:
        """Notify all observers of BBO change."""
        bbo_data = self.to_dict()
        for observer in self._observers:
            try:
                observer(bbo_data)
            except Exception as e:
                # Log error but don't fail on observer errors
                print(f"Error notifying BBO observer: {e}")
    
    def to_dict(self) -> dict:
        """
        Convert BBO to dictionary for serialization.
        
        Returns:
            Dictionary representation of BBO
        """
        return {
            "symbol": self.symbol,
            "best_bid": str(self.current_bbo["best_bid"]) if self.current_bbo["best_bid"] else None,
            "best_ask": str(self.current_bbo["best_ask"]) if self.current_bbo["best_ask"] else None,
            "spread": str(self.current_bbo["spread"]) if self.current_bbo["spread"] else None,
            "mid_price": str(self.current_bbo["mid_price"]) if self.current_bbo["mid_price"] else None,
            "timestamp": self.last_update_time.isoformat() + "Z" if self.last_update_time else None,
            "update_count": self.update_count,
        }
    
    def __repr__(self) -> str:
        """String representation of BBO."""
        bid = self.current_bbo["best_bid"]
        ask = self.current_bbo["best_ask"]
        return f"BBO({self.symbol}: bid={bid}, ask={ask}, updates={self.update_count})"
