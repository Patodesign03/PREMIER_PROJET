"""
Tests for backend/cards.py
Covers:
- 52 unique cards
- Card properties (suit, value, color, display names, symbols)
- Tableau stacking rules (alternating colors, descending value by 1)
- Foundation stacking rules (Ace first, same suit, ascending value by 1)
- Parsing and serialization
"""

import pytest
from backend.cards import (
    Card, CardStack, SUITS, VALUES, SUIT_NAMES, SUIT_SYMBOLS, SUIT_COLORS, VALUE_NAMES, VALUE_DISPLAY
)


class TestCards:
    def test_all_cards_count_and_uniqueness(self):
        all_cards = Card.all_cards()
        assert len(all_cards) == 52
        assert len(set(all_cards)) == 52

        # 13 cards per suit
        for suit in SUITS:
            suit_cards = [c for c in all_cards if c.suit == suit]
            assert len(suit_cards) == 13
            values = {c.value for c in suit_cards}
            assert values == set(range(1, 14))

    def test_card_colors(self):
        red_suits = ['H', 'D']
        black_suits = ['C', 'S']

        for s in red_suits:
            c = Card(1, s)
            assert c.color == 'red'
            assert c.is_red is True
            assert c.is_black is False

        for s in black_suits:
            c = Card(1, s)
            assert c.color == 'black'
            assert c.is_red is False
            assert c.is_black is True

    def test_card_from_string_valid(self):
        c1 = Card.from_string("AH")
        assert c1.value == 1 and c1.suit == 'H'
        assert c1.name == "AH"

        c2 = Card.from_string("10S")
        assert c2.value == 10 and c2.suit == 'S'
        assert c2.name == "10S"

        c3 = Card.from_string("KD")
        assert c3.value == 13 and c3.suit == 'D'

        c4 = Card.from_string("qc")  # case-insensitive
        assert c4.value == 12 and c4.suit == 'C'

    def test_card_from_string_invalid(self):
        with pytest.raises(ValueError):
            Card.from_string("14H")
        with pytest.raises(ValueError):
            Card.from_string("0S")
        with pytest.raises(ValueError):
            Card.from_string("AX")
        with pytest.raises(ValueError):
            Card.from_string("")

    def test_tableau_stacking(self):
        black_queen = Card.from_string("QS")
        red_jack = Card.from_string("JH")
        black_jack = Card.from_string("JC")
        red_king = Card.from_string("KD")

        # Red Jack can stack on Black Queen
        assert red_jack.can_stack_on(black_queen) is True
        # Black Jack CANNOT stack on Black Queen (same color)
        assert black_jack.can_stack_on(black_queen) is False
        # Red King CANNOT stack on Black Queen (wrong rank)
        assert red_king.can_stack_on(black_queen) is False

        # Only King can stack on None (empty tableau column)
        assert red_king.can_stack_on(None) is True
        assert black_queen.can_stack_on(None) is False

    def test_foundation_stacking(self):
        ace_hearts = Card.from_string("AH")
        two_hearts = Card.from_string("2H")
        three_hearts = Card.from_string("3H")
        two_spades = Card.from_string("2S")

        # Empty foundation: only Ace of corresponding suit
        assert ace_hearts.can_go_to_foundation(None, 'H') is True
        assert ace_hearts.can_go_to_foundation(None, 'S') is False
        assert two_hearts.can_go_to_foundation(None, 'H') is False

        # Non-empty foundation: same suit, value + 1
        assert two_hearts.can_go_to_foundation(ace_hearts, 'H') is True
        assert three_hearts.can_go_to_foundation(ace_hearts, 'H') is False
        assert two_spades.can_go_to_foundation(ace_hearts, 'H') is False

    def test_card_stack(self):
        card = Card.from_string("7C")
        stack_entry = CardStack(card=card, face_up=True)
        assert stack_entry.face_up is True
        assert stack_entry.card == card
        assert stack_entry.to_dict()["name"] == "7C"

        hidden_entry = CardStack(card=None, face_up=False)
        assert hidden_entry.face_up is False
        assert hidden_entry.card is None
        assert hidden_entry.to_dict()["face_up"] is False
