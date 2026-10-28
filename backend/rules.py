"""Move validation and execution engine for Klondike Solitaire.

Defines MoveType enum, Move representation class, and RulesEngine.
"""

from enum import Enum
from typing import Optional, Any

try:
    from backend.cards import Card, CardStack, SUITS, SUIT_NAMES
    from backend.game_state import GameState
except ImportError:
    from cards import Card, CardStack, SUITS, SUIT_NAMES
    from game_state import GameState


class MoveType(Enum):
    """Enumeration of legal Klondike Solitaire move types."""
    TABLEAU_TO_TABLEAU = 'TABLEAU_TO_TABLEAU'
    TABLEAU_TO_FOUNDATION = 'TABLEAU_TO_FOUNDATION'
    WASTE_TO_TABLEAU = 'WASTE_TO_TABLEAU'
    WASTE_TO_FOUNDATION = 'WASTE_TO_FOUNDATION'
    DRAW_CARD = 'DRAW_CARD'
    RESET_STOCK = 'RESET_STOCK'


class Move:
    """Represents a discrete move in Klondike Solitaire.

    Attributes:
        type: MoveType enum indicating the action.
        source_col: Origin column index (0-6) for tableau moves, or None.
        dest_col: Destination column index (0-6) for tableau moves, or None.
        dest_suit: Destination suit ('H', 'D', 'C', 'S') for foundation moves, or None.
        card_count: Number of cards moved together (for sequence moves).
        card: The leading card being moved (or top card for single moves).
        description_fr: Human-readable French description of the move for the UI.
    """

    def __init__(
        self,
        type: MoveType,
        source_col: Optional[int] = None,
        dest_col: Optional[int] = None,
        dest_suit: Optional[str] = None,
        card_count: int = 1,
        card: Optional[Card] = None,
        description_fr: str = "",
    ) -> None:
        self.type: MoveType = type
        self.source_col: Optional[int] = source_col
        self.dest_col: Optional[int] = dest_col
        self.dest_suit: Optional[str] = dest_suit.upper() if dest_suit is not None else None
        self.card_count: int = card_count
        self.card: Optional[Card] = card
        self.description_fr: str = description_fr

    def to_dict(self) -> dict[str, Any]:
        """Serialize move to dictionary for JSON output."""
        return {
            'type': self.type.value,
            'source_col': self.source_col,
            'dest_col': self.dest_col,
            'dest_suit': self.dest_suit,
            'card_count': self.card_count,
            'card': self.card.to_dict() if self.card else None,
            'description_fr': self.description_fr,
        }

    def __repr__(self) -> str:
        """Detailed representation of Move."""
        return (
            f"Move(type={self.type.value}, src={self.source_col}, dst={self.dest_col}, "
            f"dest_suit={self.dest_suit}, count={self.card_count}, card={self.card})"
        )

    def __eq__(self, other: object) -> bool:
        """Check equality between two Move instances."""
        if not isinstance(other, Move):
            return False
        return (
            self.type == other.type
            and self.source_col == other.source_col
            and self.dest_col == other.dest_col
            and self.dest_suit == other.dest_suit
            and self.card_count == other.card_count
            and self.card == other.card
        )

    def __hash__(self) -> int:
        """Hash code for sets/dicts."""
        card_key = (self.card.value, self.card.suit) if self.card else None
        return hash((self.type, self.source_col, self.dest_col, self.dest_suit, self.card_count, card_key))


class RulesEngine:
    """Core rule validation and state transition engine for Klondike Solitaire."""

    @staticmethod
    def is_valid_tableau_placement(card: Card, target_card_or_none: Optional[Card]) -> bool:
        """Validate if a card can be placed on a tableau column.

        Rules:
        - If the target column is empty (target_card_or_none is None), only a King (value 13) can be placed.
        - If the column is non-empty, the card must alternate colors and have a value exactly 1 less than the target card.

        Args:
            card: The card to place.
            target_card_or_none: Top card of the target column, or None if column is empty.

        Returns:
            True if placement is valid, False otherwise.
        """
        if target_card_or_none is None:
            return card.value == 13
        return (card.color != target_card_or_none.color) and (card.value == target_card_or_none.value - 1)

    @staticmethod
    def is_valid_foundation_placement(
        card: Card,
        foundation_top_or_none: Optional[Card],
        suit: Optional[str] = None
    ) -> bool:
        """Validate if a card can be placed on a foundation pile.

        Rules:
        - The card suit must match the foundation suit.
        - If foundation is empty (foundation_top_or_none is None), only an Ace (value 1) is allowed.
        - If non-empty, card must match the foundation suit and have a value exactly 1 higher than the current top.

        Args:
            card: The card to place.
            foundation_top_or_none: Top card of the foundation pile, or None if empty.
            suit: Suit of the target foundation (defaults to card.suit).

        Returns:
            True if placement is valid, False otherwise.
        """
        expected_suit = suit.upper() if suit is not None else card.suit
        if card.suit != expected_suit:
            return False

        if foundation_top_or_none is None:
            return card.value == 1

        return (
            foundation_top_or_none.suit == card.suit
            and card.value == foundation_top_or_none.value + 1
        )

    @staticmethod
    def get_legal_moves(state: GameState) -> list[Move]:
        """Generate all legal moves from the current GameState.

        Categories generated:
        1. Moving face-up sequences from one tableau column to another.
        2. Moving top cards from tableau columns to matching foundations.
        3. Moving top waste card to tableau columns.
        4. Moving top waste card to matching foundation.
        5. Drawing a card from stock to waste.
        6. Resetting the stock pile from waste when stock is empty.

        Important invariants:
        - Cards are NEVER removed from foundations (strict rule).
        - Obviously useless moves (e.g. moving a King with no hidden cards beneath to an empty column) are excluded.

        Args:
            state: Current GameState.

        Returns:
            List of legal Move objects.
        """
        moves: list[Move] = []

        # 1. Tableau to Tableau moves
        for src_col in range(7):
            seq = state.get_face_up_sequence(src_col)
            if not seq:
                continue

            num_hidden = len(state.columns[src_col]) - len(seq)

            # Any subsequence starting at index i (0 <= i < len(seq))
            for i, sub_card in enumerate(seq):
                count = len(seq) - i

                for dst_col in range(7):
                    if dst_col == src_col:
                        continue

                    target_top = state.get_column_top(dst_col)

                    # Prune useless move: moving a King with no hidden cards beneath it to an empty column
                    if target_top is None and sub_card.value == 13 and i == 0 and num_hidden == 0:
                        continue

                    if RulesEngine.is_valid_tableau_placement(sub_card, target_top):
                        if count == 1:
                            desc = f"Déplacer {sub_card.display_name} de la colonne {src_col + 1} vers la colonne {dst_col + 1}"
                        else:
                            desc = (
                                f"Déplacer la suite commençant par {sub_card.display_name} "
                                f"({count} cartes) de la colonne {src_col + 1} vers la colonne {dst_col + 1}"
                            )

                        moves.append(Move(
                            type=MoveType.TABLEAU_TO_TABLEAU,
                            source_col=src_col,
                            dest_col=dst_col,
                            card_count=count,
                            card=sub_card,
                            description_fr=desc,
                        ))

        # 2. Tableau to Foundation moves
        for src_col in range(7):
            col_top = state.get_column_top(src_col)
            if col_top is not None:
                fnd_top = state.get_foundation_top(col_top.suit)
                if RulesEngine.is_valid_foundation_placement(col_top, fnd_top, col_top.suit):
                    suit_name = SUIT_NAMES[col_top.suit]
                    desc = f"Placer {col_top.display_name} de la colonne {src_col + 1} sur la fondation {suit_name}"
                    moves.append(Move(
                        type=MoveType.TABLEAU_TO_FOUNDATION,
                        source_col=src_col,
                        dest_suit=col_top.suit,
                        card_count=1,
                        card=col_top,
                        description_fr=desc,
                    ))

        # 3. Waste to Tableau moves
        waste_card = state.waste_top
        if waste_card is not None:
            for dst_col in range(7):
                target_top = state.get_column_top(dst_col)
                if RulesEngine.is_valid_tableau_placement(waste_card, target_top):
                    desc = f"Déplacer {waste_card.display_name} de la défausse vers la colonne {dst_col + 1}"
                    moves.append(Move(
                        type=MoveType.WASTE_TO_TABLEAU,
                        dest_col=dst_col,
                        card_count=1,
                        card=waste_card,
                        description_fr=desc,
                    ))

        # 4. Waste to Foundation moves
        if waste_card is not None:
            fnd_top = state.get_foundation_top(waste_card.suit)
            if RulesEngine.is_valid_foundation_placement(waste_card, fnd_top, waste_card.suit):
                suit_name = SUIT_NAMES[waste_card.suit]
                desc = f"Placer {waste_card.display_name} de la défausse sur la fondation {suit_name}"
                moves.append(Move(
                    type=MoveType.WASTE_TO_FOUNDATION,
                    dest_suit=waste_card.suit,
                    card_count=1,
                    card=waste_card,
                    description_fr=desc,
                ))

        # 5. Draw Card from stock
        if not state.stock_empty:
            moves.append(Move(
                type=MoveType.DRAW_CARD,
                card_count=1,
                card=state.stock[0] if state.stock else None,
                description_fr="Piocher une carte",
            ))

        # 6. Reset Stock when empty and waste has cards
        if state.stock_empty and len(state.waste) > 0:
            moves.append(Move(
                type=MoveType.RESET_STOCK,
                card_count=len(state.waste),
                description_fr="Retourner la défausse pour reformer la pioche",
            ))

        return moves

    @staticmethod
    def apply_move(state: GameState, move: Move) -> tuple[GameState, bool]:
        """Apply a move to produce a new GameState and indicate if a card was revealed.

        Invariants:
        - Returns a brand new GameState instance (pure immutable transition).
        - NEVER removes a card from a foundation.
        - For RESET_STOCK: waste order is reversed (top of waste becomes bottom of new stock,
          so bottom of waste becomes top of stock and drawn first).
        - card_revealed is True if a hidden card became the new top card of a column.

        Args:
            state: Current GameState.
            move: Move to execute.

        Returns:
            Tuple of (new_state, card_revealed).

        Raises:
            ValueError: If the move cannot be applied to the current state.
        """
        is_valid, err_msg = RulesEngine.validate_move(state, move)
        if not is_valid:
            raise ValueError(f"Coup illégal: {err_msg}")

        new_state = state.clone()
        card_revealed = False

        if move.type == MoveType.TABLEAU_TO_TABLEAU:
            assert move.source_col is not None
            assert move.dest_col is not None
            src = move.source_col
            dst = move.dest_col
            count = move.card_count

            moving_cards = new_state.columns[src][-count:]
            new_state.columns[src] = new_state.columns[src][:-count]
            new_state.columns[dst].extend(moving_cards)

            if new_state.columns[src]:
                new_top = new_state.columns[src][-1]
                if not new_top.face_up:
                    card_revealed = True
                    if new_top.card is not None:
                        new_top.face_up = True

        elif move.type == MoveType.TABLEAU_TO_FOUNDATION:
            assert move.source_col is not None
            src = move.source_col
            top_stack = new_state.columns[src].pop()
            assert top_stack.card is not None
            suit = move.dest_suit or top_stack.card.suit
            new_state.foundations[suit].append(top_stack.card)

            if new_state.columns[src]:
                new_top = new_state.columns[src][-1]
                if not new_top.face_up:
                    card_revealed = True
                    if new_top.card is not None:
                        new_top.face_up = True

        elif move.type == MoveType.WASTE_TO_TABLEAU:
            assert move.dest_col is not None
            dst = move.dest_col
            card = new_state.waste.pop()
            new_state.columns[dst].append(CardStack(card=card, face_up=True))

        elif move.type == MoveType.WASTE_TO_FOUNDATION:
            card = new_state.waste.pop()
            suit = move.dest_suit or card.suit
            new_state.foundations[suit].append(card)

        elif move.type == MoveType.DRAW_CARD:
            card = new_state.stock.pop(0)
            new_state.waste.append(card)

        elif move.type == MoveType.RESET_STOCK:
            new_state.stock = list(reversed(new_state.waste))
            new_state.waste = []

        return new_state, card_revealed

    @staticmethod
    def validate_move(state: GameState, move: Move) -> tuple[bool, str]:
        """Validate whether a move is legally playable on the given GameState.

        Args:
            state: Current GameState.
            move: Move to validate.

        Returns:
            Tuple of (is_valid: bool, error_message: str).
            If valid, error_message is empty string.
        """
        if move.type == MoveType.TABLEAU_TO_TABLEAU:
            if move.source_col is None or not (0 <= move.source_col < 7):
                return False, "Colonne source invalide (doit être entre 0 et 6)."
            if move.dest_col is None or not (0 <= move.dest_col < 7):
                return False, "Colonne destination invalide (doit être entre 0 et 6)."
            if move.source_col == move.dest_col:
                return False, "La colonne source et la colonne destination doivent être différentes."

            src_col = state.columns[move.source_col]
            count = move.card_count
            if count < 1 or len(src_col) < count:
                return False, f"Pas assez de cartes dans la colonne source ({len(src_col)} disponible(s), {count} demandée(s))."

            moving_subseq = src_col[-count:]
            for stack in moving_subseq:
                if not stack.face_up or stack.card is None:
                    return False, "La séquence à déplacer contient des cartes cachées ou non identifiées."

            lead_card = moving_subseq[0].card
            assert lead_card is not None
            if move.card is not None and lead_card != move.card:
                return False, f"La carte spécifiée ({move.card.name}) ne correspond pas à la tête de séquence ({lead_card.name})."

            target_top = state.get_column_top(move.dest_col)
            if not RulesEngine.is_valid_tableau_placement(lead_card, target_top):
                if target_top is None:
                    return False, f"Seul un Roi peut être placé sur une colonne vide (tentative avec {lead_card.display_name})."
                return (
                    False,
                    f"Placement invalide: {lead_card.display_name} ne peut pas être placé sur {target_top.display_name} "
                    f"(couleurs alternées et valeur -1 requises)."
                )

            return True, ""

        elif move.type == MoveType.TABLEAU_TO_FOUNDATION:
            if move.source_col is None or not (0 <= move.source_col < 7):
                return False, "Colonne source invalide (doit être entre 0 et 6)."

            src_col = state.columns[move.source_col]
            if not src_col:
                return False, f"La colonne source {move.source_col + 1} est vide."

            top_stack = src_col[-1]
            if not top_stack.face_up or top_stack.card is None:
                return False, f"La carte du dessus de la colonne {move.source_col + 1} est cachée ou non identifiée."

            card = top_stack.card
            if move.card is not None and card != move.card:
                return False, f"La carte spécifiée ({move.card.name}) ne correspond pas au sommet de la colonne ({card.name})."

            suit = move.dest_suit or card.suit
            target_top = state.get_foundation_top(suit)
            if not RulesEngine.is_valid_foundation_placement(card, target_top, suit):
                suit_name = SUIT_NAMES.get(suit, suit)
                if target_top is None:
                    return False, f"Seul un As de {suit_name} peut être placé sur cette fondation vide."
                return (
                    False,
                    f"Impossible de placer {card.display_name} sur la fondation {suit_name} "
                    f"(sommet actuel: {target_top.display_name})."
                )

            return True, ""

        elif move.type == MoveType.WASTE_TO_TABLEAU:
            if not state.waste:
                return False, "La défausse est vide."

            waste_card = state.waste_top
            assert waste_card is not None
            if move.card is not None and waste_card != move.card:
                return False, f"La carte spécifiée ({move.card.name}) ne correspond pas au sommet de la défausse ({waste_card.name})."

            if move.dest_col is None or not (0 <= move.dest_col < 7):
                return False, "Colonne destination invalide (doit être entre 0 et 6)."

            target_top = state.get_column_top(move.dest_col)
            if not RulesEngine.is_valid_tableau_placement(waste_card, target_top):
                if target_top is None:
                    return False, f"Seul un Roi peut être placé sur une colonne vide (tentative avec {waste_card.display_name})."
                return (
                    False,
                    f"Placement invalide: {waste_card.display_name} ne peut pas être placé sur {target_top.display_name}."
                )

            return True, ""

        elif move.type == MoveType.WASTE_TO_FOUNDATION:
            if not state.waste:
                return False, "La défausse est vide."

            waste_card = state.waste_top
            assert waste_card is not None
            if move.card is not None and waste_card != move.card:
                return False, f"La carte spécifiée ({move.card.name}) ne correspond pas au sommet de la défausse ({waste_card.name})."

            suit = move.dest_suit or waste_card.suit
            target_top = state.get_foundation_top(suit)
            if not RulesEngine.is_valid_foundation_placement(waste_card, target_top, suit):
                suit_name = SUIT_NAMES.get(suit, suit)
                if target_top is None:
                    return False, f"Seul un As de {suit_name} peut être placé sur cette fondation vide."
                return (
                    False,
                    f"Impossible de placer {waste_card.display_name} sur la fondation {suit_name}."
                )

            return True, ""

        elif move.type == MoveType.DRAW_CARD:
            if state.stock_empty:
                return False, "Impossible de piocher: la pioche est vide."
            return True, ""

        elif move.type == MoveType.RESET_STOCK:
            if not state.stock_empty:
                return False, "Impossible de réinitialiser la pioche: la pioche contient encore des cartes."
            if len(state.waste) == 0:
                return False, "Impossible de réinitialiser la pioche: la défausse est vide."
            return True, ""

        return False, f"Type de coup inconnu: {move.type}"
