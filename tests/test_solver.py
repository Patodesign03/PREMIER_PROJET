"""
Tests for backend/solver.py
Covers:
- Solver initialization and configuration
- Recognition of a winning game
- Solving an endgame state (victory sequence discovery)
- Ranking of partial solutions
- Stop mechanism and statistics reporting
"""

import pytest
from backend.cards import Card, CardStack, SUITS
from backend.game_state import GameState
from backend.rules import RulesEngine, Move, MoveType
from backend.solver import Solver, SolverConfig, SolverResult, SolverStats


class TestSolver:
    @pytest.fixture
    def almost_won_state(self):
        """Create a state where 51 cards are in foundations, and the King of Spades is on Col 0."""
        columns = [[] for _ in range(7)]
        foundations = {'H': [], 'D': [], 'C': [], 'S': []}

        # Put 1 to 13 of Hearts, Diamonds, Clubs in foundations
        for s in ['H', 'D', 'C']:
            for val in range(1, 14):
                foundations[s].append(Card(val, s))

        # Put 1 to 12 of Spades in Spades foundation
        for val in range(1, 13):
            foundations['S'].append(Card(val, 'S'))

        # Put KS on Col 0
        ks = Card(13, 'S')
        columns[0].append(CardStack(card=ks, face_up=True))

        return GameState(columns=columns, stock=[], foundations=foundations, waste=[])

    def test_solver_detects_winning_state(self, almost_won_state):
        # Already has 51 in foundation, 1 move to win
        config = SolverConfig(max_time_seconds=5.0)
        solver = Solver(config)

        results, stats = solver.solve(almost_won_state)

        assert len(results) > 0
        first_result = results[0]
        assert first_result.is_winning is True
        assert len(first_result.moves) == 1
        assert first_result.moves[0].type == MoveType.TABLEAU_TO_FOUNDATION
        assert first_result.moves[0].dest_suit == 'S'
        assert stats.solutions_found >= 1

    def test_solver_stop_mechanism(self, almost_won_state):
        config = SolverConfig(max_time_seconds=60.0)
        solver = Solver(config)
        # Verify stop flag works
        assert solver.is_running() is False
        solver.stop()
        # When stopped immediately, solve should return quickly
        results, stats = solver.solve(almost_won_state)
        assert stats.elapsed_seconds < 5.0

    def test_solver_recommendations(self, almost_won_state):
        solver = Solver()
        recs = solver.get_recommendations(almost_won_state, max_count=3)
        assert len(recs) > 0
        assert recs[0].moves[0].type == MoveType.TABLEAU_TO_FOUNDATION
