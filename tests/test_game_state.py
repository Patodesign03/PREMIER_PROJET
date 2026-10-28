"""
Tests for backend/game_state.py
Covers:
- Initial state creation with 7 columns (1 to 7 cards)
- 24 cards in stock in exact order
- Duplicate detection and error reporting
- Cloning and immutability checks
- Memoization hash consistency
"""

import pytest
from backend.cards import Card, CardStack
from backend.game_state import GameState


class TestGameState:
    @pytest.fixture
    def sample_cards(self):
        all_cards = Card.all_cards()
        visible = [c.name for c in all_cards[:7]]
        stock = [c.name for c in all_cards[7:31]]
        return visible, stock

    def test_create_initial_valid(self, sample_cards):
        visible, stock = sample_cards
        state = GameState.create_initial(visible, stock)

        # 7 columns
        assert len(state.columns) == 7

        # Columns have 1 to 7 cards:
        # Col 0: 0 hidden, 1 visible = 1 card
        # Col 1: 1 hidden, 1 visible = 2 cards
        # ...
        # Col 6: 6 hidden, 1 visible = 7 cards
        for i in range(7):
            col = state.columns[i]
            assert len(col) == i + 1
            # Top card is visible
            assert col[-1].face_up is True
            assert col[-1].card.name == visible[i]
            # Previous cards are face-down
            for j in range(i):
                assert col[j].face_up is False
                assert col[j].card is None

        # Stock has exactly 24 cards in exact order
        assert len(state.stock) == 24
        for i in range(24):
            assert state.stock[i].name == stock[i]

        # Waste and foundations empty initially
        assert len(state.waste) == 0
        for suit in ['H', 'D', 'C', 'S']:
            assert len(state.foundations[suit]) == 0

        # Totals
        assert state.foundation_count == 0
        assert state.hidden_count == sum(range(7))  # 0+1+2+3+4+5+6 = 21
        assert state.is_won is False

    def test_create_initial_invalid_counts(self, sample_cards):
        visible, stock = sample_cards
        # Only 6 visible cards
        with pytest.raises(ValueError):
            GameState.create_initial(visible[:6], stock)

        # Only 23 stock cards
        with pytest.raises(ValueError):
            GameState.create_initial(visible, stock[:23])

    def test_create_initial_duplicates(self, sample_cards):
        visible, stock = sample_cards
        # Replace first stock card with first visible card
        bad_stock = [visible[0]] + stock[1:]
        with pytest.raises(ValueError, match=r"[Dd]ouble"):
            GameState.create_initial(visible, bad_stock)

    def test_clone_deep_copy(self, sample_cards):
        visible, stock = sample_cards
        state = GameState.create_initial(visible, stock)
        cloned = state.clone()

        assert cloned.get_state_hash() == state.get_state_hash()
        # Modifying cloned state doesn't affect original
        cloned.stock.pop()
        assert len(cloned.stock) == 23
        assert len(state.stock) == 24
        assert cloned.get_state_hash() != state.get_state_hash()

    def test_hash_consistency_and_uniqueness(self, sample_cards):
        visible, stock = sample_cards
        state1 = GameState.create_initial(visible, stock)
        state2 = GameState.create_initial(visible, stock)

        # Same state produces exact same hash
        assert state1.get_state_hash() == state2.get_state_hash()

        # Changing stock order changes hash
        stock_permuted = list(reversed(stock))
        state3 = GameState.create_initial(visible, stock_permuted)
        assert state1.get_state_hash() != state3.get_state_hash()
