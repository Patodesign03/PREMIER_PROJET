"""History and undo/redo management for Klondike Solitaire.

Tracks state transitions, card revelations, user corrections,
and provides full undo/redo capabilities.
"""

from typing import Optional, Any
import time

try:
    from backend.cards import Card
    from backend.game_state import GameState
    from backend.rules import Move
except ImportError:
    from cards import Card
    from game_state import GameState
    from rules import Move


class HistoryEntry:
    """Represents a single historical action or state transition.

    Attributes:
        action_type: Type of action ('move', 'reveal', 'correction', 'draw', 'reset_stock').
        move: Associated Move instance if applicable, else None.
        state_before: GameState before the action.
        state_after: GameState after the action.
        revealed_card: Card revealed by this action if any, else None.
        revealed_position: Tuple (col_idx, card_idx) where card was revealed, or None.
        timestamp: Unix timestamp when action occurred.
        description: French human-readable description of the action.
    """

    def __init__(
        self,
        action_type: str,
        state_before: GameState,
        state_after: GameState,
        move: Optional[Move] = None,
        revealed_card: Optional[Card] = None,
        revealed_position: Optional[tuple[int, int]] = None,
        timestamp: Optional[float] = None,
        description: str = "",
    ) -> None:
        self.action_type: str = action_type
        self.move: Optional[Move] = move
        self.state_before: GameState = state_before.clone()
        self.state_after: GameState = state_after.clone()
        self.revealed_card: Optional[Card] = revealed_card
        self.revealed_position: Optional[tuple[int, int]] = revealed_position
        self.timestamp: float = timestamp if timestamp is not None else time.time()
        self.description: str = description

    def to_dict(self) -> dict[str, Any]:
        """Serialize history entry to JSON-compatible dictionary."""
        return {
            'action_type': self.action_type,
            'move': self.move.to_dict() if self.move else None,
            'state_before': self.state_before.to_dict(),
            'state_after': self.state_after.to_dict(),
            'revealed_card': self.revealed_card.to_dict() if self.revealed_card else None,
            'revealed_position': list(self.revealed_position) if self.revealed_position else None,
            'timestamp': self.timestamp,
            'description': self.description,
        }

    def __repr__(self) -> str:
        """Detailed representation of history entry."""
        return (
            f"HistoryEntry(type={self.action_type!r}, desc={self.description!r}, "
            f"ts={self.timestamp:.2f})"
        )


class GameHistory:
    """Manages undo/redo stacks and full timeline of game state transitions.

    Attributes:
        entries: Ordered list of HistoryEntry objects.
        current_index: Pointer to current position in history (-1 if at initial_state).
        initial_state: Baseline GameState at the beginning of the timeline.
    """

    def __init__(self, initial_state: GameState) -> None:
        """Initialize history with the given initial state.

        Args:
            initial_state: Baseline game state.
        """
        self.initial_state: GameState = initial_state.clone()
        self.entries: list[HistoryEntry] = []
        self.current_index: int = -1

    def record(self, entry: HistoryEntry) -> None:
        """Record a new history entry, discarding any redo future.

        Args:
            entry: HistoryEntry to record.
        """
        if self.current_index < len(self.entries) - 1:
            self.clear_future()
        self.entries.append(entry)
        self.current_index += 1

    def undo(self) -> Optional[GameState]:
        """Undo the most recent action and revert to previous state.

        Returns:
            The previous GameState, or None if at initial state (nothing to undo).
        """
        if not self.can_undo():
            return None

        previous_state = self.entries[self.current_index].state_before.clone()
        self.current_index -= 1
        return previous_state

    def redo(self) -> Optional[GameState]:
        """Redo the previously undone action and advance to next state.

        Returns:
            The next GameState, or None if at tip of timeline (nothing to redo).
        """
        if not self.can_redo():
            return None

        self.current_index += 1
        return self.entries[self.current_index].state_after.clone()

    def can_undo(self) -> bool:
        """Check if an undo operation is possible."""
        return self.current_index >= 0

    def can_redo(self) -> bool:
        """Check if a redo operation is possible."""
        return self.current_index < len(self.entries) - 1

    def get_current_state(self) -> GameState:
        """Get a copy of the current active GameState.

        Returns:
            Current GameState.
        """
        if self.current_index == -1:
            return self.initial_state.clone()
        return self.entries[self.current_index].state_after.clone()

    def get_entries(self) -> list[dict[str, Any]]:
        """Get all recorded history entries as serialized dictionaries.

        Returns:
            List of entry dictionaries.
        """
        return [entry.to_dict() for entry in self.entries]

    def clear_future(self) -> None:
        """Discard all entries ahead of the current_index (after an undo branch)."""
        self.entries = self.entries[: self.current_index + 1]

    def reset(self, new_initial_state: Optional[GameState] = None) -> None:
        """Reset the history timeline to initial state or a new state.

        Args:
            new_initial_state: Optional new GameState to replace the initial state.
        """
        if new_initial_state is not None:
            self.initial_state = new_initial_state.clone()
        self.entries.clear()
        self.current_index = -1

    def to_dict(self) -> dict[str, Any]:
        """Serialize entire GameHistory to JSON-compatible dictionary."""
        return {
            'initial_state': self.initial_state.to_dict(),
            'current_index': self.current_index,
            'can_undo': self.can_undo(),
            'can_redo': self.can_redo(),
            'entries': self.get_entries(),
        }
