"""Card representation system for Klondike Solitaire.

Defines card constants, Card class, and CardStack class.
"""

from typing import Optional, Any


# Constants
SUITS = ['H', 'D', 'C', 'S']  # Hearts, Diamonds, Clubs, Spades
SUIT_NAMES = {
    'H': 'Coeurs',
    'D': 'Carreaux',
    'C': 'Trèfles',
    'S': 'Piques'
}
SUIT_SYMBOLS = {
    'H': '♥',
    'D': '♦',
    'C': '♣',
    'S': '♠'
}
SUIT_COLORS = {
    'H': 'red',
    'D': 'red',
    'C': 'black',
    'S': 'black'
}
VALUES = list(range(1, 14))  # 1=Ace through 13=King
VALUE_NAMES = {
    1: 'A', 2: '2', 3: '3', 4: '4', 5: '5', 6: '6', 7: '7',
    8: '8', 9: '9', 10: '10', 11: 'J', 12: 'Q', 13: 'K'
}
VALUE_DISPLAY = {
    1: 'As', 2: '2', 3: '3', 4: '4', 5: '5', 6: '6', 7: '7',
    8: '8', 9: '9', 10: '10', 11: 'Valet', 12: 'Dame', 13: 'Roi'
}

# Reverse lookup for parsing values from string representations
_REV_VALUE_NAMES = {name: val for val, name in VALUE_NAMES.items()}
_REV_VALUE_NAMES['1'] = 1  # Support '1' as Ace if needed


class Card:
    """Represents a standard playing card in Klondike Solitaire.

    Attributes:
        value: Integer from 1 (Ace) to 13 (King).
        suit: Character 'H', 'D', 'C', or 'S'.
    """

    def __init__(self, value: int, suit: str) -> None:
        """Initialize a Card with a value and suit.

        Args:
            value: Integer between 1 (Ace) and 13 (King).
            suit: Suit character ('H', 'D', 'C', 'S').

        Raises:
            ValueError: If value is not in 1..13 or suit not in SUITS.
        """
        suit_upper = suit.upper()
        if value not in VALUES:
            raise ValueError(f"Valeur de carte invalide: {value} (doit être entre 1 et 13)")
        if suit_upper not in SUITS:
            raise ValueError(f"Couleur de carte invalide: {suit} (doit être l'un de {SUITS})")

        self._value: int = value
        self._suit: str = suit_upper

    @property
    def value(self) -> int:
        """Card value from 1 (Ace) to 13 (King)."""
        return self._value

    @property
    def suit(self) -> str:
        """Card suit ('H', 'D', 'C', 'S')."""
        return self._suit

    @property
    def color(self) -> str:
        """Color of the suit: 'red' for Hearts/Diamonds, 'black' for Clubs/Spades."""
        return SUIT_COLORS[self._suit]

    @property
    def name(self) -> str:
        """Standard short card name, e.g. 'AH', '10S', 'KD'."""
        return f"{VALUE_NAMES[self._value]}{self._suit}"

    @property
    def display_name(self) -> str:
        """French display name, e.g. 'As de Coeurs'."""
        return f"{VALUE_DISPLAY[self._value]} de {SUIT_NAMES[self._suit]}"

    @property
    def symbol(self) -> str:
        """Suit Unicode symbol (♥, ♦, ♣, ♠)."""
        return SUIT_SYMBOLS[self._suit]

    @property
    def is_red(self) -> bool:
        """True if the card is red (Hearts or Diamonds)."""
        return self.color == 'red'

    @property
    def is_black(self) -> bool:
        """True if the card is black (Clubs or Spades)."""
        return self.color == 'black'

    def can_stack_on(self, other_card: Optional['Card']) -> bool:
        """Check if this card can be stacked on other_card in the tableau.

        Tableau stacking rule:
        - If target column is empty (other_card is None): only King (value 13) can be placed.
        - If target is a card: must alternate color and value must be descending by 1 (this.value == other.value - 1).

        Args:
            other_card: Target card, or None if column is empty.

        Returns:
            True if placement is legal, False otherwise.
        """
        if other_card is None:
            return self._value == 13
        return (self.color != other_card.color) and (self._value == other_card.value - 1)

    def can_go_to_foundation(
        self,
        foundation_top_card_or_none: Optional['Card'],
        suit: Optional[str] = None
    ) -> bool:
        """Check if this card can be placed on a foundation pile.

        Foundation rule:
        - Must match the foundation suit (if specified, otherwise matching card's suit).
        - If foundation is empty (None): only Ace (value 1) can be placed.
        - If foundation is not empty: must be the same suit and value must increment by 1 (this.value == top.value + 1).

        Args:
            foundation_top_card_or_none: Current top card of foundation, or None if empty.
            suit: Suit of the target foundation (defaults to self.suit).

        Returns:
            True if placement is legal, False otherwise.
        """
        target_suit = suit.upper() if suit is not None else self._suit
        if self._suit != target_suit:
            return False

        if foundation_top_card_or_none is None:
            return self._value == 1
        return (
            foundation_top_card_or_none.suit == self._suit
            and self._value == foundation_top_card_or_none.value + 1
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize card to dictionary for JSON output."""
        return {
            'value': self._value,
            'suit': self._suit,
            'name': self.name,
            'color': self.color,
            'display_name': self.display_name,
            'symbol': self.symbol,
            'is_red': self.is_red,
            'is_black': self.is_black,
        }

    @staticmethod
    def from_string(s: str) -> 'Card':
        """Parse card from string representation like 'AH', '10S', 'kd'.

        Args:
            s: Short string representation of the card.

        Returns:
            Card instance.

        Raises:
            ValueError: If string format is invalid.
        """
        if not s or not isinstance(s, str):
            raise ValueError(f"Représentation de carte invalide: {s!r}")

        cleaned = s.strip().upper()
        if len(cleaned) < 2:
            raise ValueError(f"Chaîne de carte trop courte: '{s}'")

        suit = cleaned[-1]
        val_str = cleaned[:-1]

        if suit not in SUITS:
            raise ValueError(f"Couleur inconnue '{suit}' dans '{s}'. Couleurs valides: {SUITS}")

        if val_str in _REV_VALUE_NAMES:
            val = _REV_VALUE_NAMES[val_str]
        else:
            try:
                val = int(val_str)
                if val not in VALUES:
                    raise ValueError
            except ValueError:
                raise ValueError(f"Valeur de carte inconnue '{val_str}' dans '{s}'")

        return Card(value=val, suit=suit)

    @staticmethod
    def all_cards() -> list['Card']:
        """Generate all 52 standard playing cards.

        Returns:
            List of 52 Card objects ordered by suit and value.
        """
        return [Card(val, suit) for suit in SUITS for val in VALUES]

    def __str__(self) -> str:
        """Card string representation, e.g. 'AH', '10S'."""
        return self.name

    def __repr__(self) -> str:
        """Card representation string."""
        return f"Card('{self.name}')"

    def __eq__(self, other: object) -> bool:
        """Equality comparison based on value and suit."""
        if not isinstance(other, Card):
            return False
        return self._value == other.value and self._suit == other.suit

    def __hash__(self) -> int:
        """Hash code for use in sets and dicts."""
        return hash((self._value, self._suit))


class CardStack:
    """Represents a card in a tableau column, tracking whether it is face up.

    Attributes:
        card: Card instance, or None if the card is hidden and identity unknown.
        face_up: True if visible/face up, False if face down.
    """

    def __init__(self, card: Optional[Card] = None, face_up: bool = False) -> None:
        """Initialize CardStack entry.

        Args:
            card: Card object or None.
            face_up: Visibility boolean.
        """
        self.card: Optional[Card] = card
        self.face_up: bool = face_up

    def clone(self) -> 'CardStack':
        """Create a copy of this CardStack entry."""
        return CardStack(card=self.card, face_up=self.face_up)

    def to_dict(self) -> dict[str, Any]:
        """Serialize CardStack to dictionary for JSON output."""
        return {
            'card': self.card.to_dict() if self.card else None,
            'face_up': self.face_up,
            'name': self.card.name if self.card else None,
        }

    def __str__(self) -> str:
        """String representation of stack entry."""
        if self.face_up:
            return self.card.name if self.card else '??'
        return f"[{self.card.name if self.card else '?'}]"

    def __repr__(self) -> str:
        """Detailed representation of stack entry."""
        return f"CardStack(card={self.card!r}, face_up={self.face_up})"

    def __eq__(self, other: object) -> bool:
        """Equality check."""
        if not isinstance(other, CardStack):
            return False
        return self.card == other.card and self.face_up == other.face_up
