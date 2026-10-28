"""
Tests for backend/rules.py
Covers:
- Legal and illegal moves on tableau (alternating color, descending rank)
- Sequence moves across columns
- King placement on empty column
- Foundation progression and absolute rule (cards never leave foundation)
- Stock drawing, waste top accessibility, and stock reset reversal
- Card revelation detection
"""

import pytest
from backend.cards import Card, CardStack
from backend.game_state import GameState
from backend.rules import RulesEngine, Move, MoveType


class TestRulesEngine:
    @pytest.fixture
    def empty_state(self):
        columns = [[] for _ in range(7)]
        foundations = {'H': [], 'D': [], 'C': [], 'S': []}
        return GameState(columns=columns, stock=[], foundations=foundations, waste=[])

    def test_tableau_move_valid_and_invalid(self, empty_state):
        state = empty_state
        # Col 0: 8 of Spades (black)
        state.columns[0].append(CardStack(card=Card.from_string("8S"), face_up=True))
        # Col 1: 7 of Hearts (red)
        state.columns[1].append(CardStack(card=Card.from_string("7H"), face_up=True))
        # Col 2: 7 of Clubs (black)
        state.columns[2].append(CardStack(card=Card.from_string("7C"), face_up=True))

        # 7H onto 8S (valid: red 7 on black 8)
        valid_move = Move(
            type=MoveType.TABLEAU_TO_TABLEAU,
            source_col=1,
            dest_col=0,
            card_count=1,
            card=Card.from_string("7H")
        )
        is_valid, _ = RulesEngine.validate_move(state, valid_move)
        assert is_valid is True

        # 7C onto 8S (invalid: black 7 on black 8)
        invalid_move = Move(
            type=MoveType.TABLEAU_TO_TABLEAU,
            source_col=2,
            dest_col=0,
            card_count=1,
            card=Card.from_string("7C")
        )
        is_valid, error = RulesEngine.validate_move(state, invalid_move)
        assert is_valid is False
        assert "couleur" in error.lower() or "alternance" in error.lower()

    def test_sequence_move(self, empty_state):
        state = empty_state
        # Col 0: 10 of Hearts
        state.columns[0].append(CardStack(card=Card.from_string("10H"), face_up=True))
        # Col 1: 9 of Spades, 8 of Diamonds
        state.columns[1].append(CardStack(card=Card.from_string("9S"), face_up=True))
        state.columns[1].append(CardStack(card=Card.from_string("8D"), face_up=True))

        # Move sequence [9S, 8D] from Col 1 to Col 0
        seq_move = Move(
            type=MoveType.TABLEAU_TO_TABLEAU,
            source_col=1,
            dest_col=0,
            card_count=2,
            card=Card.from_string("9S")
        )
        is_valid, _ = RulesEngine.validate_move(state, seq_move)
        assert is_valid is True

        new_state, revealed = RulesEngine.apply_move(state, seq_move)
        assert len(new_state.columns[1]) == 0
        assert len(new_state.columns[0]) == 3
        assert new_state.columns[0][-1].card == Card.from_string("8D")

    def test_king_on_empty_column(self, empty_state):
        state = empty_state
        state.columns[0].append(CardStack(card=Card.from_string("KS"), face_up=True))
        state.columns[1].append(CardStack(card=Card.from_string("QS"), face_up=True))

        # King to empty col 2: VALID
        move_king = Move(
            type=MoveType.TABLEAU_TO_TABLEAU,
            source_col=0,
            dest_col=2,
            card_count=1,
            card=Card.from_string("KS")
        )
        is_valid, _ = RulesEngine.validate_move(state, move_king)
        assert is_valid is True

        # Queen to empty col 2: INVALID
        move_queen = Move(
            type=MoveType.TABLEAU_TO_TABLEAU,
            source_col=1,
            dest_col=2,
            card_count=1,
            card=Card.from_string("QS")
        )
        is_valid, error = RulesEngine.validate_move(state, move_queen)
        assert is_valid is False
        assert "roi" in error.lower()

    def test_foundation_rules_and_immutability(self, empty_state):
        state = empty_state
        state.columns[0].append(CardStack(card=Card.from_string("AH"), face_up=True))
        state.columns[1].append(CardStack(card=Card.from_string("2H"), face_up=True))

        # Move Ace to empty hearts foundation: VALID
        move_ace = Move(
            type=MoveType.TABLEAU_TO_FOUNDATION,
            source_col=0,
            dest_suit='H',
            card=Card.from_string("AH")
        )
        is_valid, _ = RulesEngine.validate_move(state, move_ace)
        assert is_valid is True

        state_after_ace, _ = RulesEngine.apply_move(state, move_ace)
        assert len(state_after_ace.foundations['H']) == 1

        # Move 2H to hearts foundation: VALID
        move_2h = Move(
            type=MoveType.TABLEAU_TO_FOUNDATION,
            source_col=1,
            dest_suit='H',
            card=Card.from_string("2H")
        )
        is_valid, _ = RulesEngine.validate_move(state_after_ace, move_2h)
        assert is_valid is True

        state_after_2h, _ = RulesEngine.apply_move(state_after_ace, move_2h)
        assert len(state_after_2h.foundations['H']) == 2
        assert state_after_2h.foundation_count == 2

        # Verify that get_legal_moves NEVER offers moves from foundations
        legal_moves = RulesEngine.get_legal_moves(state_after_2h)
        for m in legal_moves:
            assert "FOUNDATION_TO" not in m.type.name

    def test_stock_and_waste_mechanics(self, empty_state):
        state = empty_state
        # Stock has [card1, card2, card3] (card3 on top)
        c1 = Card.from_string("AS")
        c2 = Card.from_string("2S")
        c3 = Card.from_string("3S")
        state.stock = [c1, c2, c3]

        # Draw 1 card: card1 goes to waste
        draw_move = Move(type=MoveType.DRAW_CARD)
        state_after_draw, _ = RulesEngine.apply_move(state, draw_move)
        assert len(state_after_draw.stock) == 2
        assert len(state_after_draw.waste) == 1
        assert state_after_draw.waste[-1] == c1

        # Draw remaining 2 cards
        state_after_draw2, _ = RulesEngine.apply_move(state_after_draw, draw_move)
        state_after_draw3, _ = RulesEngine.apply_move(state_after_draw2, draw_move)

        assert len(state_after_draw3.stock) == 0
        assert len(state_after_draw3.waste) == 3
        # Waste is [c1, c2, c3], top of waste is c3
        assert state_after_draw3.waste_top == c3

        # Reset stock: turns waste over
        # Reversal rule: [c1, c2, c3] reversed -> stock becomes [c3, c2, c1]
        # So c3 will be drawn first next time (top of waste becomes top of stock)
        reset_move = Move(type=MoveType.RESET_STOCK)
        is_valid, _ = RulesEngine.validate_move(state_after_draw3, reset_move)
        assert is_valid is True

        state_after_reset, _ = RulesEngine.apply_move(state_after_draw3, reset_move)
        assert len(state_after_reset.waste) == 0
        assert len(state_after_reset.stock) == 3
        assert state_after_reset.stock == [c3, c2, c1]

    def test_card_revelation_on_tableau_move(self, empty_state):
        state = empty_state
        # Col 0 has 1 hidden card and 1 visible card on top
        state.columns[0].append(CardStack(card=None, face_up=False))
        state.columns[0].append(CardStack(card=Card.from_string("KD"), face_up=True))

        # Col 1 is empty
        move_king = Move(
            type=MoveType.TABLEAU_TO_TABLEAU,
            source_col=0,
            dest_col=1,
            card_count=1,
            card=Card.from_string("KD")
        )
        new_state, revealed = RulesEngine.apply_move(state, move_king)
        assert revealed is True
        assert len(new_state.columns[0]) == 1
        # The hidden card is now at the top of Col 0
        assert new_state.columns[0][0].face_up is False
