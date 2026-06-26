"""Abstract AI provider interface for food nutrition parsing."""

from abc import ABC, abstractmethod
from typing import Dict, Any


class AIProvider(ABC):
    """Abstract base class for AI providers."""

    @abstractmethod
    def parse_food(self, text: str) -> Dict[str, Any]:
        """
        Parse natural language food description.

        Args:
            text: Natural language input like "1 roti, 1 cup dal, 100g rice"

        Returns:
            dict with keys:
                - items: list of {name, portion, calories, protein, carbs, fat}
                - total: {calories, protein, carbs, fat}
                - error: error message if failed
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Return the provider name."""
        pass
