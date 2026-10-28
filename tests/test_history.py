"""
Tests for backend/history.py
Covers:
- Action recording (moves, draws, reveals)
- Undo and state restoration
- Redo
- Clearing forward history when new action performed after undo
"""

import time
import pytest
from backend.cards import Card
from backend.game_state import GameState
from backend.rules import RulesEngine, Move, MoveType
from backend.history import GameHistory, HistoryEntry


class TestGameHistory:
    @pytest.fixture
    def initial_game(self):
        all_cards = Card.all_cards()
        visible = [c.name for c in all_cards[:7]]
        stock = [c.name for c in all_cards[7:31]]
        state = GameState.create_initial(visible, stock)
        history = GameHistory(state)
        return state, history

    def test_record_and_undo_draw(self, initial_game):
        state, history = initial_game
        assert history.can_undo() is False
        assert history.can_redo() is False

        # Apply draw move
        draw_move = Move(type=MoveType.DRAW_CARD)
        new_state, _ = RulesEngine.apply_move(state, draw_move)

        entry = HistoryEntry(
            action_type='draw',
            move=draw_move,
            state_before=state,
            state_after=new_state,
            revealed_card=None,
            revealed_position=None,
            timestamp=time.time(),
            description="Piocher une carte"
        )
        history.record(entry)

        assert history.can_undo() is True
        assert history.can_redo() is False

        # Undo
        restored = history.undo()
        assert restored is not None
        assert restored.get_state_hash() == state.get_state_hash()
        assert len(restored.stock) == 24
        assert len(restored.waste) == 0
        assert history.can_undo() is False
        assert history.can_redo() is True

        # Redo
        redone = history.redo()
        assert redone is not None
        assert redone.get_state_hash() == new_state.get_state_hash()
        assert len(redone.stock) == 23
        assert len(redone.waste) == 1
        assert history.can_undo() is True
        assert history.can_redo() is False

    def test_branching_clears_future(self, initial_game):
        state, history = initial_game
        draw_move = Move(type=MoveType.DRAW_CARD)
        s1, _ = RulesEngine.apply_move(state, draw_move)

        history.record(HistoryEntry(
            action_type='draw',
            move=draw_move,
            state_before=state,
            state_after=s1,
            revealed_card=None,
            revealed_position=None,
            timestamp=time.time(),
            description="Draw 1"
        ))

        # Undo back to initial
        history.undo()
        assert history.can_redo() is True

        # Now perform a different action (e.g. record a simulated action)
        s2 = state.clone()
        history.record(HistoryEntry(
            action_type='draw',
            move=draw_move,
            state_before=state,
            state_after=s2,
            revealed_card=None,
            revealed_position=None,
            timestamp=time.time(),
            description="New branch action"
        ))

        # Redo should no longer be possible
        assert history.can_redo() is False
