"""Card inventory and tracking management for Klondike Solitaire.

Tracks all 52 standard playing cards, their current locations,
and positions of unknown hidden cards.
"""

from typing import Optional, Any

try:
    from backend.cards import Card, SUITS
    from backend.game_state import GameState
except ImportError:
    from cards import Card, SUITS
    from game_state import GameState


# Valid location identifiers
VALID_LOCATIONS = (
    [f"column_{i}" for i in range(7)]
    + ['stock', 'waste']
    + [f"foundation_{suit}" for suit in SUITS]
)


class CardInventory:
    """Manages the full 52-card inventory and prevents duplicates.

    Attributes:
        all_cards: Set of all 52 Card objects.
        assigned_cards: Mapping from Card -> location identifier string.
        unknown_hidden: List of (col_idx, card_idx) tuples for unknown cards.
    """

    def __init__(self) -> None:
        """Initialize an empty inventory of 52 standard playing cards."""
        self.all_cards: set[Card] = set(Card.all_cards())
        self.assigned_cards: dict[Card, str] = {}
        self.unknown_hidden: list[tuple[int, int]] = []

    def assign_card(self, card: Card, location: str) -> bool:
        """Assign a card to a specific location in the game.

        Args:
            card: Card instance to assign.
            location: Destination location string (e.g. 'column_0', 'stock', 'foundation_H').

        Returns:
            True if assignment succeeded.
            False if card is already assigned to a DIFFERENT location.
        """
        if card not in self.all_cards:
            return False

        if card in self.assigned_cards:
            if self.assigned_cards[card] == location:
                return True
            return False

        self.assigned_cards[card] = location
        return True

    def unassign_card(self, card: Card) -> bool:
        """Remove a card assignment from the inventory.

        Args:
            card: Card to unassign.

        Returns:
            True if the card was assigned and now removed, False otherwise.
        """
        if card in self.assigned_cards:
            del self.assigned_cards[card]
            return True
        return False

    def get_available_cards(self) -> list[Card]:
        """Get all cards that are not currently assigned to any location.

        Returns:
            List of unassigned Card objects, deterministically sorted by suit and value.
        """
        unassigned = [c for c in self.all_cards if c not in self.assigned_cards]
        return sorted(unassigned, key=lambda c: (SUITS.index(c.suit), c.value))

    def is_card_available(self, card: Card) -> bool:
        """Check if a card has not yet been assigned to any location.

        Args:
            card: Card instance to check.

        Returns:
            True if unassigned, False if already in play.
        """
        return card not in self.assigned_cards

    def get_card_location(self, card: Card) -> Optional[str]:
        """Get current location of a card.

        Args:
            card: Card instance.

        Returns:
            Location string or None if unassigned.
        """
        return self.assigned_cards.get(card)

    def sync_with_state(self, state: GameState) -> None:
        """Rebuild inventory state completely from a GameState instance.

        Args:
            state: GameState to extract card placements from.
        """
        self.assigned_cards.clear()
        self.unknown_hidden.clear()

        # Tableau columns
        for col_idx, col in enumerate(state.columns):
            for card_idx, stack in enumerate(col):
                if stack.card is not None:
                    self.assigned_cards[stack.card] = f"column_{col_idx}"
                else:
                    self.unknown_hidden.append((col_idx, card_idx))

        # Stock
        for card in state.stock:
            self.assigned_cards[card] = "stock"

        # Waste
        for card in state.waste:
            self.assigned_cards[card] = "waste"

        # Foundations
        for suit, pile in state.foundations.items():
            for card in pile:
                self.assigned_cards[card] = f"foundation_{suit}"

    def validate(self) -> tuple[bool, list[str]]:
        """Validate integrity of the card inventory.

        Checks:
        - That no card is outside the 52 standard cards.
        - That total assigned cards plus unknown hidden cards does not exceed 52.
        - Flags any missing cards if a full game state is expected.

        Returns:
            Tuple of (is_valid: bool, error_messages: list[str]).
        """
        errors: list[str] = []

        # Check for invalid cards
        for card in self.assigned_cards:
            if card not in self.all_cards:
                errors.append(f"Carte invalide détectée dans l'inventaire: {card.name}")

        total_assigned = len(self.assigned_cards)
        total_unknown = len(self.unknown_hidden)
        total_cards = total_assigned + total_unknown

        if total_cards > 52:
            errors.append(
                f"Nombre total de cartes invalide: {total_assigned} assignées + "
                f"{total_unknown} cachées inconnues = {total_cards} > 52."
            )

        if total_cards < 52:
            missing = 52 - total_cards
            errors.append(
                f"Inventaire incomplet: {missing} carte(s) manquante(s) pour atteindre 52 cartes."
            )

        return len(errors) == 0, errors

    def to_dict(self) -> dict[str, Any]:
        """Serialize inventory to JSON-compatible dictionary."""
        return {
            'assigned_cards': {
                card.name: loc for card, loc in self.assigned_cards.items()
            },
            'available_cards': [c.name for c in self.get_available_cards()],
            'unknown_hidden': [
                {'column': col, 'card_index': idx} for col, idx in self.unknown_hidden
            ],
            'total_assigned': len(self.assigned_cards),
            'total_available': len(self.get_available_cards()),
            'total_unknown': len(self.unknown_hidden),
        }
