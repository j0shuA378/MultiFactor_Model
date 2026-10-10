from abc import ABC, abstractmethod
import pandas as pd
from typing import Dict, Any, Tuple

class BaseStrategy(ABC):
    def __init__(self, name: str, params: Dict[str, Any] = None):
        self.name = name
        self.params = params or {}

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> Tuple[pd.Series, Dict[str, Any]]:
        """
        Takes OHLCV DataFrame, returns:
        1. pd.Series of integer signals (1 for BUY, -1 for SELL, 0 for HOLD) indexed by Date
        2. dict of strategy-specific metadata (indicators, model diagnostics, etc.)
        """
        pass
