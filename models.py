"""Data classes for calorie tracker domain objects."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class FoodEntry:
    """A single food/log entry for a given date."""

    id: Optional[int]
    user_id: int
    date: str  # ISO string YYYY-MM-DD
    name: str
    calories: int
    protein: float
    carbs: float
    fat: float
    timestamp: str  # ISO datetime string for ordering


@dataclass
class DailyGoal:
    """Calorie, protein and carbs goal for a specific date."""

    user_id: int
    date: str           # ISO string YYYY-MM-DD
    calorie_goal: int
    protein_goal: float = 0.0   # grams
    carbs_goal: float   = 0.0   # grams


@dataclass
class AiResponseAuditLog:
    """Audit log entry for a parsed AI response."""

    id: Optional[int]
    timestamp: str
    input_text: str
    response_payload: str
    provider: str
    status: str


@dataclass
class PromptVersion:
    """A versioned system prompt snapshot."""

    id: Optional[int]
    name: str
    content: str
    created_at: str
    is_active: bool


@dataclass
class ApiKeyRecord:
    """Stored API key record for external providers."""

    id: Optional[int]
    name: str
    provider: str
    api_key: str
    notes: Optional[str]
    created_at: Optional[str]
