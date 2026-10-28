"""Game state representation and management for Klondike Solitaire.

Defines the GameState class capturing tableau columns, foundations,
stock, and waste piles, with serialization and state hashing.
"""

from typing import Optional, Any
import hashlib

try:
    from backend.cards import Card, CardStack, SUITS
except ImportError:
    from cards import Card, CardStack, SUITS


class GameState:
    """Represents a complete snapshot of a Klondike Solitaire game.

    Attributes:
        columns: List of 7 lists, each containing CardStack objects (bottom to top).
        foundations: Dict with keys 'H','D','C','S', each containing a list of Card objects.
        stock: List of Card objects representing the draw pile (in exact draw order).
        waste: List of Card objects representing the discard pile (top card is last element).
    """

    def __init__(
        self,
        columns: list[list[CardStack]],
        stock: list[Card],
        foundations: Optional[dict[str, list[Card]]] = None,
        waste: Optional[list[Card]] = None,
    ) -> None:
        """Initialize a new GameState.

        Args:
            columns: List of 7 column stacks (each list contains CardStack objects).
            stock: List of Card objects in the stock pile.
            foundations: Optional dictionary mapping suit -> list of Card objects.
            waste: Optional list of Card objects in the waste pile.
        """
        if len(columns) != 7:
            raise ValueError(f"Klondike Solitaire requiert exactement 7 colonnes, reçu: {len(columns)}")

        self.columns: list[list[CardStack]] = columns
        self.stock: list[Card] = list(stock)

        if foundations is None:
            self.foundations: dict[str, list[Card]] = {suit: [] for suit in SUITS}
        else:
            self.foundations = {suit: list(foundations.get(suit, [])) for suit in SUITS}

        self.waste: list[Card] = list(waste) if waste is not None else []

    @property
    def foundation_count(self) -> int:
        """Total number of cards placed in all foundations."""
        return sum(len(pile) for pile in self.foundations.values())

    @property
    def is_won(self) -> bool:
        """True if all 52 cards are on the foundations."""
        return self.foundation_count == 52

    @property
    def hidden_count(self) -> int:
        """Number of face-down cards remaining in the tableau columns."""
        return sum(1 for col in self.columns for stack in col if not stack.face_up)

    @property
    def waste_top(self) -> Optional[Card]:
        """Top card of the waste pile, or None if the waste is empty."""
        return self.waste[-1] if self.waste else None

    @property
    def stock_empty(self) -> bool:
        """True if the stock pile is empty."""
        return len(self.stock) == 0

    def clone(self) -> 'GameState':
        """Create a deep copy of this GameState.

        Returns:
            A new, independent GameState instance.
        """
        cloned_columns = [
            [stack.clone() for stack in col]
            for col in self.columns
        ]
        cloned_foundations = {
            suit: list(cards)
            for suit, cards in self.foundations.items()
        }
        cloned_stock = list(self.stock)
        cloned_waste = list(self.waste)

        return GameState(
            columns=cloned_columns,
            stock=cloned_stock,
            foundations=cloned_foundations,
            waste=cloned_waste,
        )

    def canonical_string(self) -> str:
        """Generate a canonical deterministic string representing the full state."""
        col_parts: list[str] = []
        for i, col in enumerate(self.columns):
            items = []
            for stack in col:
                c_name = stack.card.name if stack.card else '?'
                items.append(f"+{c_name}" if stack.face_up else f"-{c_name}")
            col_parts.append(f"C{i}:" + ",".join(items))

        fnd_parts: list[str] = []
        for suit in sorted(SUITS):
            cards = self.foundations.get(suit, [])
            fnd_parts.append(f"{suit}:" + ",".join(c.name for c in cards))

        stock_part = ",".join(c.name for c in self.stock)
        waste_part = ",".join(c.name for c in self.waste)

        return (
            f"COLS:{';'.join(col_parts)}|"
            f"FND:{';'.join(fnd_parts)}|"
            f"STK:{stock_part}|"
            f"WST:{waste_part}"
        )

    def get_state_hash(self) -> str:
        """Compute unique deterministic SHA-256 hash of the canonical state representation.

        Returns:
            64-character hex string representing the exact game state.
        """
        canon = self.canonical_string()
        return hashlib.sha256(canon.encode('utf-8')).hexdigest()

    def get_column_top(self, col_idx: int) -> Optional[Card]:
        """Get the face-up top card of a column, or None if empty or face-down.

        Args:
            col_idx: Column index (0 to 6).

        Returns:
            The Card on top of the column if visible, else None.
        """
        if 0 <= col_idx < len(self.columns):
            col = self.columns[col_idx]
            if col and col[-1].face_up and col[-1].card is not None:
                return col[-1].card
        return None

    def get_face_up_sequence(self, col_idx: int) -> list[Card]:
        """Get the consecutive face-up cards at the top of a column in bottom-to-top order.

        Args:
            col_idx: Column index (0 to 6).

        Returns:
            List of Card objects from deepest face-up card to the column top card.
        """
        if not (0 <= col_idx < len(self.columns)):
            return []

        col = self.columns[col_idx]
        seq: list[Card] = []
        for stack in reversed(col):
            if stack.face_up and stack.card is not None:
                seq.append(stack.card)
            else:
                break
        seq.reverse()
        return seq

    def get_foundation_top(self, suit: str) -> Optional[Card]:
        """Get the top card of a foundation pile for a given suit.

        Args:
            suit: Suit character ('H', 'D', 'C', 'S').

        Returns:
            Top Card of the suit foundation, or None if empty.
        """
        suit_upper = suit.upper()
        cards = self.foundations.get(suit_upper)
        if cards:
            return cards[-1]
        return None

    def reveal_column_top(self, col_idx: int, card: Card) -> bool:
        """Reveal an unknown face-down card at the top of a column.

        Args:
            col_idx: Column index (0 to 6).
            card: The revealed Card object.

        Returns:
            True if a card was revealed, False if column was empty or already face up.
        """
        if not (0 <= col_idx < len(self.columns)):
            return False
        col = self.columns[col_idx]
        if not col:
            return False
        top = col[-1]
        if not top.face_up:
            top.card = card
            top.face_up = True
            return True
        return False

    def to_dict(self) -> dict[str, Any]:
        """Serialize full GameState to JSON-compatible dictionary."""
        return {
            'columns': [[stack.to_dict() for stack in col] for col in self.columns],
            'foundations': {
                suit: [card.to_dict() for card in cards]
                for suit, cards in self.foundations.items()
            },
            'stock': [card.to_dict() for card in self.stock],
            'waste': [card.to_dict() for card in self.waste],
            'foundation_count': self.foundation_count,
            'is_won': self.is_won,
            'hidden_count': self.hidden_count,
            'waste_top': self.waste_top.to_dict() if self.waste_top else None,
            'stock_empty': self.stock_empty,
            'state_hash': self.get_state_hash(),
        }

    @staticmethod
    def create_initial(visible_cards: list[str], stock_cards: list[str]) -> 'GameState':
        """Create an initial Klondike game state from visible cards and stock cards.

        Tableau setup:
        - Column 0: 0 hidden cards, 1 visible card (visible_cards[0])
        - Column 1: 1 hidden card, 1 visible card (visible_cards[1])
        - ...
        - Column 6: 6 hidden cards, 1 visible card (visible_cards[6])
        Total 21 hidden cards + 7 visible cards = 28 tableau cards.
        Stock setup:
        - 24 cards in exact order (stock_cards).
        Total 31 known cards must be provided and must not contain duplicates.

        Args:
            visible_cards: List of 7 card strings for columns 0 to 6.
            stock_cards: List of 24 card strings for the stock pile.

        Returns:
            Configured GameState.

        Raises:
            ValueError: If lengths do not match or if duplicates are detected.
        """
        if len(visible_cards) != 7:
            raise ValueError(
                f"Configuration initiale invalide: 7 cartes visibles requises pour le tableau, "
                f"{len(visible_cards)} reçues."
            )

        if len(stock_cards) != 24:
            raise ValueError(
                f"Configuration initiale invalide: 24 cartes requises pour la pioche, "
                f"{len(stock_cards)} reçues."
            )

        parsed_visible: list[Card] = [Card.from_string(s) for s in visible_cards]
        parsed_stock: list[Card] = [Card.from_string(s) for s in stock_cards]

        all_known = parsed_visible + parsed_stock
        seen: set[Card] = set()
        duplicates: list[str] = []
        for card in all_known:
            if card in seen:
                duplicates.append(card.name)
            seen.add(card)

        if duplicates:
            raise ValueError(
                f"Cartes en double détectées dans la configuration initiale: {', '.join(duplicates)}"
            )

        # Build columns: col i has i hidden cards (card=None, face_up=False) and 1 visible top card
        columns: list[list[CardStack]] = []
        for i in range(7):
            col: list[CardStack] = [CardStack(card=None, face_up=False) for _ in range(i)]
            col.append(CardStack(card=parsed_visible[i], face_up=True))
            columns.append(col)

        return GameState(
            columns=columns,
            stock=parsed_stock,
            foundations={suit: [] for suit in SUITS},
            waste=[],
        )

    def __repr__(self) -> str:
        """Short representation of game state."""
        return (
            f"GameState(foundations={self.foundation_count}/52, "
            f"hidden={self.hidden_count}, stock={len(self.stock)}, waste={len(self.waste)})"
        )
