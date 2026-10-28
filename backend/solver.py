"""
Klondike Solitaire Solver Module.

This module implements an automated solver and move recommendation engine for
Klondike Solitaire. It utilizes a priority-based Depth-First Search (DFS) with
domain-specific heuristic evaluation, memoization via state hashing, and beam search
pruning to explore game trees efficiently within defined time and depth budgets.

Features:
- Depth-First Search with heuristic state evaluation and cycle detection
- Intelligent move ordering prioritizing high-value progress (foundations, reveals, freed columns)
- Safe handling of incomplete information (face-down cards with unknown identity)
- Real-time move recommendation engine for interactive play assistance
- Thread-safe search interruption and live progress monitoring
"""

from __future__ import annotations

import copy
import logging
import re
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from backend.cards import Card, CardStack, SUITS, VALUES, VALUE_NAMES, SUIT_COLORS
from backend.game_state import GameState
from backend.rules import RulesEngine, Move, MoveType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Classes: Configuration, Statistics, and Results
# ---------------------------------------------------------------------------

@dataclass
class SolverConfig:
    """Configuration options for the Klondike Solitaire Solver."""
    max_time_seconds: float = 200.0
    max_solutions: int = 5
    max_depth: int = 500
    beam_width: int = 50
    recommendation_max_depth: int = 5
    recommendation_time_limit: float = 2.0

    def to_dict(self) -> dict:
        """Serialize configuration parameters to dictionary format."""
        return {
            "max_time_seconds": self.max_time_seconds,
            "max_solutions": self.max_solutions,
            "max_depth": self.max_depth,
            "beam_width": self.beam_width,
            "recommendation_max_depth": self.recommendation_max_depth,
            "recommendation_time_limit": self.recommendation_time_limit,
        }


@dataclass
class SolverStats:
    """Execution statistics tracked during a solver run."""
    states_explored: int = 0
    solutions_found: int = 0
    best_foundation_count: int = 0
    best_hidden_revealed: int = 0
    elapsed_seconds: float = 0.0
    status: str = "ready"  # 'ready', 'running', 'stopped', 'timeout', 'victory', 'error'

    def to_dict(self) -> dict:
        """Serialize solver statistics to dictionary format."""
        return {
            "states_explored": self.states_explored,
            "solutions_found": self.solutions_found,
            "best_foundation_count": self.best_foundation_count,
            "best_hidden_revealed": self.best_hidden_revealed,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "status": self.status,
        }


@dataclass
class SolverResult:
    """
    Represents a full or partial solution sequence found by the solver.

    Attributes:
        is_winning: True if this sequence leads to a full victory (all 52 cards in foundations).
        moves: Sequence of legal moves leading from the input state to this outcome.
        foundation_count: Total cards placed in foundations at the end of the sequence.
        hidden_revealed: Count of hidden cards revealed throughout the sequence.
        columns_freed: Number of empty tableau columns created.
        score: Heuristic score computed for this sequence.
        description: French human-readable explanation of why this sequence is ranked here.
        requires_reveal: True if continuing this branch requires turning over an unknown hidden card.
        reveal_column: 0-based column index where an unknown card must be revealed.
    """
    is_winning: bool
    moves: list[Move]
    foundation_count: int
    hidden_revealed: int
    columns_freed: int
    score: float
    description: str
    requires_reveal: bool = False
    reveal_column: Optional[int] = None

    def to_dict(self) -> dict:
        """Serialize the solution result to dictionary format."""
        serialized_moves = []
        for m in self.moves:
            if hasattr(m, "to_dict") and callable(m.to_dict):
                serialized_moves.append(m.to_dict())
            else:
                serialized_moves.append(str(m))

        return {
            "is_winning": self.is_winning,
            "moves": serialized_moves,
            "move_count": len(self.moves),
            "foundation_count": self.foundation_count,
            "hidden_revealed": self.hidden_revealed,
            "columns_freed": self.columns_freed,
            "score": round(self.score, 2),
            "description": self.description,
            "requires_reveal": self.requires_reveal,
            "reveal_column": self.reveal_column,
        }


# ---------------------------------------------------------------------------
# Helper Inspection Functions
# ---------------------------------------------------------------------------

def _extract_column_index(pile_identifier: Any) -> Optional[int]:
    """
    Extract a 0-based tableau column index from various pile representation formats.
    Supports integers (0-6), strings ('tableau_0', 'col_2', 'colonne 3'), etc.
    """
    if isinstance(pile_identifier, int):
        if 0 <= pile_identifier <= 6:
            return pile_identifier
        if 1 <= pile_identifier <= 7:
            return pile_identifier - 1
        return None

    if isinstance(pile_identifier, str):
        pile_str = pile_identifier.lower().strip()
        # Look for explicit digit in tableau/column identifier
        match = re.search(r"\d+", pile_str)
        if match:
            idx = int(match.group(0))
            if "colonne" in pile_str or "tableau" in pile_str or "col" in pile_str:
                if 0 <= idx <= 6:
                    return idx
                if 1 <= idx <= 7:
                    return idx - 1
    return None


def _get_columns(state: GameState) -> list:
    """Retrieve the list of tableau columns from a GameState instance."""
    for attr in ("tableau", "columns", "tableaus", "tableau_piles", "piles"):
        val = getattr(state, attr, None)
        if val is not None and isinstance(val, (list, tuple)):
            return list(val)
    return []


def _get_stack_cards(stack: Any) -> list:
    """Extract individual card items from a stack or collection object."""
    if stack is None:
        return []
    if isinstance(stack, list):
        return stack
    if hasattr(stack, "cards") and isinstance(stack.cards, list):
        return stack.cards
    if hasattr(stack, "__iter__"):
        try:
            return list(stack)
        except TypeError:
            pass
    return []


def _get_top_card(stack: Any) -> Optional[Any]:
    """Return the top (playable/exposed) card from a stack or column."""
    if stack is None:
        return None
    if hasattr(stack, "top"):
        top_prop = stack.top
        return top_prop() if callable(top_prop) else top_prop
    cards = _get_stack_cards(stack)
    return cards[-1] if cards else None


def _get_empty_columns(state: GameState) -> int:
    """Count empty tableau columns in the given GameState."""
    if hasattr(state, "empty_columns_count"):
        try:
            return int(state.empty_columns_count)
        except (ValueError, TypeError):
            pass
    if hasattr(state, "empty_columns"):
        ec = state.empty_columns
        return len(ec) if isinstance(ec, (list, tuple, set)) else int(ec)

    cols = _get_columns(state)
    if cols:
        count = 0
        for col in cols:
            if col is None:
                count += 1
            elif hasattr(col, "is_empty"):
                if col.is_empty:
                    count += 1
            elif len(_get_stack_cards(col)) == 0:
                count += 1
        return count
    return 0


def _get_stock_waste_count(state: GameState) -> int:
    """Count total cards currently remaining in stock and waste piles."""
    total = 0
    # Stock cards
    if hasattr(state, "stock_count"):
        try:
            total += int(state.stock_count)
        except (ValueError, TypeError):
            pass
    elif hasattr(state, "stock"):
        total += len(_get_stack_cards(state.stock))

    # Waste cards
    if hasattr(state, "waste_count"):
        try:
            total += int(state.waste_count)
        except (ValueError, TypeError):
            pass
    elif hasattr(state, "waste"):
        total += len(_get_stack_cards(state.waste))

    return total


def _get_accessible_aces_and_twos(state: GameState) -> int:
    """
    Count Aces and Twos that are currently accessible on column tops or waste top.
    These are high-priority cards for building foundations.
    """
    count = 0
    # Check top card of each tableau column
    for col in _get_columns(state):
        top_c = _get_top_card(col)
        if top_c is not None:
            val = getattr(top_c, "value", None) or getattr(top_c, "rank", None)
            if val in (1, 2) or str(val).upper() in ("1", "2", "A", "ACE"):
                count += 1

    # Check top card of waste pile
    if hasattr(state, "waste"):
        waste_top = _get_top_card(state.waste)
        if waste_top is not None:
            val = getattr(waste_top, "value", None) or getattr(waste_top, "rank", None)
            if val in (1, 2) or str(val).upper() in ("1", "2", "A", "ACE"):
                count += 1

    return count


def _is_foundation_move(move: Move) -> bool:
    """Determine whether a move targets a foundation pile."""
    m_type = getattr(move, "move_type", None)
    if m_type is not None:
        if m_type == getattr(MoveType, "TABLEAU_TO_FOUNDATION", None):
            return True
        if m_type == getattr(MoveType, "WASTE_TO_FOUNDATION", None):
            return True
        if m_type == getattr(MoveType, "FOUNDATION", None):
            return True
        name_str = getattr(m_type, "name", str(m_type)).upper()
        if "FOUNDATION" in name_str:
            return True

    dest = str(
        getattr(move, "to_pile", "")
        or getattr(move, "destination", "")
        or getattr(move, "target", "")
    ).lower()
    return "foundation" in dest


def _is_draw_or_recycle_move(move: Move) -> tuple[bool, bool]:
    """
    Check if a move is a stock draw or a stock recycle/reset.
    Returns:
        (is_draw, is_recycle)
    """
    m_type = getattr(move, "move_type", None)
    name_str = getattr(m_type, "name", str(m_type)).upper() if m_type else ""
    from_pile = str(getattr(move, "from_pile", "") or getattr(move, "source", "")).lower()
    to_pile = str(getattr(move, "to_pile", "") or getattr(move, "destination", "")).lower()

    is_recycle = (
        "RECYCLE" in name_str
        or "RESET" in name_str
        or (from_pile.startswith("waste") and to_pile.startswith("stock"))
    )
    is_draw = (
        "DRAW" in name_str
        or "DEAL" in name_str
        or (from_pile.startswith("stock") and to_pile.startswith("waste"))
    )
    return is_draw, is_recycle


def _card_name_fr(card: Any) -> str:
    """Format a Card instance into a natural French description."""
    if card is None:
        return "une carte cachée"

    val = getattr(card, "value", None) or getattr(card, "rank", None)
    suit = getattr(card, "suit", None)

    val_map = {
        1: "l'As",
        2: "le 2",
        3: "le 3",
        4: "le 4",
        5: "le 5",
        6: "le 6",
        7: "le 7",
        8: "le 8",
        9: "le 9",
        10: "le 10",
        11: "le Valet",
        12: "la Dame",
        13: "le Roi",
    }
    if isinstance(val, str):
        val_upper = val.upper()
        str_val_map = {"A": "l'As", "J": "le Valet", "Q": "la Dame", "K": "le Roi"}
        val_name = str_val_map.get(val_upper, f"le {val}")
    else:
        val_name = val_map.get(val, f"le {val}" if val is not None else "la carte")

    suit_map = {
        "hearts": "de Cœur",
        "diamonds": "de Carreau",
        "clubs": "de Trèfle",
        "spades": "de Pique",
        "heart": "de Cœur",
        "diamond": "de Carreau",
        "club": "de Trèfle",
        "spade": "de Pique",
        "coeur": "de Cœur",
        "carreau": "de Carreau",
        "trefle": "de Trèfle",
        "pique": "de Pique",
        "♥": "de Cœur",
        "♦": "de Carreau",
        "♣": "de Trèfle",
        "♠": "de Pique",
        "h": "de Cœur",
        "d": "de Carreau",
        "c": "de Trèfle",
        "s": "de Pique",
    }
    suit_name = suit_map.get(str(suit).lower() if suit else "", "")
    if not suit_name and suit:
        suit_name = f"de {suit}"

    return f"{val_name} {suit_name}".strip()


# ---------------------------------------------------------------------------
# Main Solver Class
# ---------------------------------------------------------------------------

class Solver:
    """
    Automated Klondike Solitaire solver using priority-based Depth-First Search
    with heuristic evaluation, state memoization, and live control.
    """

    def __init__(self, config: Optional[SolverConfig] = None) -> None:
        """
        Initialize the solver with configuration options.

        Args:
            config: Optional SolverConfig instance. If None, default configuration is used.
        """
        self.config = config if config is not None else SolverConfig()
        self._stop_event = threading.Event()
        self._is_running = False
        self._lock = threading.Lock()

        # Search runtime state
        self._start_time: float = 0.0
        self._stats = SolverStats()
        self._visited: Dict[str, int] = {}  # state_hash -> shallowest depth reached
        self._winning_solutions: list[SolverResult] = []
        self._partial_solutions: list[SolverResult] = []
        self._best_partial_score: float = -float("inf")
        self._initial_hidden_count: int = 0

    # -----------------------------------------------------------------------
    # External Control and Monitoring API
    # -----------------------------------------------------------------------

    def stop(self) -> None:
        """Signal the solver to immediately halt search execution."""
        self._stop_event.set()

    def is_running(self) -> bool:
        """Return True if a search is actively running in this solver instance."""
        return self._is_running

    def get_stats(self) -> SolverStats:
        """
        Retrieve a snapshot of current search statistics.
        Can be safely called concurrently while a search is running.
        """
        with self._lock:
            stats_copy = copy.copy(self._stats)
            if self._is_running and self._start_time > 0.0:
                stats_copy.elapsed_seconds = time.perf_counter() - self._start_time
            return stats_copy

    def get_current_results(self) -> list[SolverResult]:
        """
        Retrieve the current best solution results found so far.
        Returns winning solutions first, followed by highest-scoring partial solutions.
        """
        with self._lock:
            return list(self._finalize_results())

    # -----------------------------------------------------------------------
    # Core Solving Entry Point
    # -----------------------------------------------------------------------

    def solve(self, state: GameState) -> tuple[list[SolverResult], SolverStats]:
        """
        Main entry point to solve a Klondike Solitaire game state.

        Args:
            state: The initial GameState to solve.

        Returns:
            A tuple of (results, stats), where results is a list of SolverResult instances
            (winning solutions first, then partial solutions ranked by score) and stats
            contains runtime execution metrics.
        """
        # Ensure recursion limit is sufficient for max_depth
        current_limit = sys.getrecursionlimit()
        required_limit = max(1000, self.config.max_depth + 200)
        if current_limit < required_limit:
            sys.setrecursionlimit(required_limit)

        with self._lock:
            self._is_running = True
            self._stop_event.clear()
            self._start_time = time.perf_counter()
            self._stats = SolverStats(status="running")
            self._visited.clear()
            self._winning_solutions.clear()
            self._partial_solutions.clear()
            self._best_partial_score = -float("inf")

        self._initial_hidden_count = getattr(state, "hidden_count", 0)
        initial_foundations = getattr(state, "foundation_count", 0)
        self._stats.best_foundation_count = initial_foundations

        # Check immediate victory condition
        if getattr(state, "is_won", False):
            win_result = SolverResult(
                is_winning=True,
                moves=[],
                foundation_count=52,
                hidden_revealed=self._initial_hidden_count,
                columns_freed=_get_empty_columns(state),
                score=10000.0,
                description="Partie déjà gagnée ! Toutes les cartes sont sur les fondations.",
            )
            with self._lock:
                self._winning_solutions.append(win_result)
                self._stats.solutions_found = 1
                self._stats.status = "victory"
                self._stats.elapsed_seconds = time.perf_counter() - self._start_time
                self._is_running = False
            return [win_result], self._stats

        # Launch depth-first search
        try:
            self._search(state, [], 0)
        except Exception as exc:
            logger.error("Erreur inattendue dans le solveur : %s", exc, exc_info=True)
            with self._lock:
                self._stats.status = "error"
        finally:
            with self._lock:
                self._stats.elapsed_seconds = time.perf_counter() - self._start_time
                self._is_running = False

                if self._stats.status not in ("victory", "timeout", "stopped", "error"):
                    if len(self._winning_solutions) > 0:
                        self._stats.status = "victory"
                    elif self._stop_event.is_set():
                        self._stats.status = "stopped"
                    elif self._stats.elapsed_seconds >= self.config.max_time_seconds:
                        self._stats.status = "timeout"
                    else:
                        self._stats.status = "ready"

        results = self._finalize_results()
        return results, self._stats

    # -----------------------------------------------------------------------
    # Recursive DFS with Pruning and Unknown-Card Branching
    # -----------------------------------------------------------------------

    def _search(self, state: GameState, moves_so_far: list[Move], depth: int) -> None:
        """
        Internal recursive Depth-First Search procedure with memoization.
        """
        # 1. Check termination flags and time limits
        if self._stop_event.is_set():
            self._stats.status = "stopped"
            return

        elapsed = time.perf_counter() - self._start_time
        if elapsed >= self.config.max_time_seconds:
            self._stats.status = "timeout"
            return

        if len(self._winning_solutions) >= self.config.max_solutions:
            return

        if depth > self.config.max_depth:
            return

        # 2. State hashing and memoization check
        state_hash = state.get_state_hash() if hasattr(state, "get_state_hash") else str(id(state))
        if state_hash in self._visited and self._visited[state_hash] <= depth:
            return
        self._visited[state_hash] = depth

        self._stats.states_explored += 1

        # Track progression metrics
        foundations_count = getattr(state, "foundation_count", 0)
        hidden_count = getattr(state, "hidden_count", 0)
        hidden_revealed = max(0, self._initial_hidden_count - hidden_count)

        if foundations_count > self._stats.best_foundation_count:
            self._stats.best_foundation_count = foundations_count
        if hidden_revealed > self._stats.best_hidden_revealed:
            self._stats.best_hidden_revealed = hidden_revealed

        # 3. Check for winning state
        if getattr(state, "is_won", False):
            self._stats.solutions_found += 1
            self._stats.status = "victory"
            win_result = SolverResult(
                is_winning=True,
                moves=list(moves_so_far),
                foundation_count=52,
                hidden_revealed=self._initial_hidden_count,
                columns_freed=_get_empty_columns(state),
                score=10000.0 - (len(moves_so_far) * 0.5),
                description=f"Solution gagnante en {len(moves_so_far)} coups",
            )
            self._winning_solutions.append(win_result)
            return

        # 4. Generate and evaluate legal moves
        try:
            legal_moves = RulesEngine.get_legal_moves(state)
        except Exception as exc:
            logger.debug("Échec de get_legal_moves : %s", exc)
            legal_moves = []

        score = self._score_state(state, legal_moves=legal_moves)

        # Update candidate partial solutions
        if len(moves_so_far) > 0:
            self._update_best_partial(state, moves_so_far, score, hidden_revealed)

        if not legal_moves:
            return

        # 5. Order moves by priority
        ordered_moves = self._order_moves(state, legal_moves)

        # Apply beam width limit if configured
        if self.config.beam_width and len(ordered_moves) > self.config.beam_width:
            ordered_moves = ordered_moves[: self.config.beam_width]

        # 6. Branch exploration
        for move in ordered_moves:
            if self._stop_event.is_set():
                self._stats.status = "stopped"
                break

            if (time.perf_counter() - self._start_time) >= self.config.max_time_seconds:
                self._stats.status = "timeout"
                break

            if len(self._winning_solutions) >= self.config.max_solutions:
                break

            # Apply move
            try:
                new_state, revealed = RulesEngine.apply_move(state, move)
            except Exception as exc:
                logger.debug("apply_move a échoué pour le coup %s : %s", move, exc)
                continue

            # 7. Handling unknown hidden cards:
            # If a card was revealed and its identity is unknown (None), stop this branch
            # and record it as an informative partial result.
            if revealed:
                if self._revealed_card_is_unknown(state, new_state, move):
                    rev_col = self._identify_revealed_column(state, new_state, move)
                    col_num = (rev_col + 1) if rev_col is not None else 1
                    rev_moves = moves_so_far + [move]
                    rev_score = self._score_state(new_state) + 50.0  # Heuristic bonus for reveal
                    rev_hidden = hidden_revealed + 1
                    rev_fc = getattr(new_state, "foundation_count", foundations_count)

                    reveal_result = SolverResult(
                        is_winning=False,
                        moves=rev_moves,
                        foundation_count=rev_fc,
                        hidden_revealed=rev_hidden,
                        columns_freed=_get_empty_columns(new_state),
                        score=rev_score,
                        description=f"Révèle une carte cachée en colonne {col_num}, permettant de nouvelles possibilités",
                        requires_reveal=True,
                        reveal_column=rev_col,
                    )
                    self._add_partial_solution(reveal_result)
                    # Stop exploring this branch since unknown card prevents reliable forward search
                    continue

            # Recurse with known state
            self._search(new_state, moves_so_far + [move], depth + 1)

    # -----------------------------------------------------------------------
    # Heuristic Scoring Function
    # -----------------------------------------------------------------------

    def _score_state(
        self,
        state: GameState,
        legal_moves: Optional[list[Move]] = None,
    ) -> float:
        """
        Compute the heuristic evaluation score for a GameState.
        Higher score represents a more promising position.

        HEURISTIC COMPONENTS (Strategic evaluations, not win probabilities):
        - +100 per card placed in foundations (direct, irreversible victory progress)
        - +50 per hidden card revealed compared to initial state (uncovers options)
        - +30 per empty tableau column created (maneuvering room for Kings and stacking)
        - +10 per card that can immediately go to a foundation (immediate tactical opportunity)
        - -5 per card remaining in waste or stock (penalizes idle, locked cards)
        - +20 per Ace or 2 accessible on column tops or waste top (critical foundational cards)
        - +1000 if the game is fully won

        Args:
            state: GameState to evaluate.
            legal_moves: Optional pre-computed list of legal moves to avoid re-calculation.

        Returns:
            Floating-point heuristic score.
        """
        score = 0.0

        # 1. Foundations progress (+100 per card)
        foundation_count = getattr(state, "foundation_count", 0)
        score += 100.0 * foundation_count

        # 2. Hidden cards revealed (+50 per card compared to initial state)
        current_hidden = getattr(state, "hidden_count", 0)
        hidden_revealed = max(0, self._initial_hidden_count - current_hidden)
        score += 50.0 * hidden_revealed

        # 3. Empty tableau columns (+30 per column)
        empty_columns = _get_empty_columns(state)
        score += 30.0 * empty_columns

        # 4. Immediate foundation moves (+10 per playable card)
        if legal_moves is None:
            try:
                legal_moves = RulesEngine.get_legal_moves(state)
            except Exception:
                legal_moves = []
        immediate_foundation_count = sum(1 for m in legal_moves if _is_foundation_move(m))
        score += 10.0 * immediate_foundation_count

        # 5. Penalize unplayed cards in stock and waste (-5 per card)
        stock_waste_count = _get_stock_waste_count(state)
        score -= 5.0 * stock_waste_count

        # 6. Accessible Aces and Twos (+20 per accessible card)
        accessible_aces_twos = _get_accessible_aces_and_twos(state)
        score += 20.0 * accessible_aces_twos

        # 7. Full victory bonus (+1000)
        if getattr(state, "is_won", False):
            score += 1000.0

        return score

    # -----------------------------------------------------------------------
    # Move Ordering
    # -----------------------------------------------------------------------

    def _order_moves(self, state: GameState, moves: list[Move]) -> list[Move]:
        """
        Order legal moves by priority to explore the most promising branches first.

        Ordering Hierarchy:
        1. Foundation moves (first priority: advances win condition)
           - Aces and 2s first within foundation moves
           - Tableau-to-foundation preferred over waste-to-foundation
        2. Moves that reveal hidden cards (second priority: uncovers unknown possibilities)
        3. Moves that free empty tableau columns (third priority: enables King moves)
        4. General tableau-to-tableau moves (preserves options)
        5. Waste-to-tableau moves
        6. Stock draw moves (last before recycle)
        7. Stock reset/recycle moves (lowest priority to prevent infinite cycle loops)

        Args:
            state: The GameState before move execution.
            moves: List of candidate Move objects.

        Returns:
            Sorted list of Move objects from highest to lowest priority.
        """
        if not moves:
            return []

        def move_priority(m: Move) -> float:
            # 1. Foundation moves
            if _is_foundation_move(m):
                prio = 10000.0
                card = getattr(m, "card", None)
                if card is not None:
                    val = getattr(card, "value", None) or getattr(card, "rank", None)
                    if val == 1 or str(val).upper() in ("1", "A"):
                        prio += 200.0  # Aces to foundation immediately
                    elif val == 2:
                        prio += 100.0  # Twos to foundation
                # Moving from tableau is better than waste as it can expose cards below
                from_p = str(getattr(m, "from_pile", "")).lower()
                if "tableau" in from_p or "col" in from_p:
                    prio += 50.0
                return prio

            # 2. Stock draws and recycles
            is_draw, is_recycle = _is_draw_or_recycle_move(m)
            if is_recycle:
                return 10.0  # Lowest priority to avoid useless recycling
            if is_draw:
                return 150.0

            # 3. Tableau & Waste moves
            from_col = _extract_column_index(getattr(m, "from_pile", None))
            to_col = _extract_column_index(getattr(m, "to_pile", None))

            # Check if this move reveals a hidden card
            reveals_hidden = self._predict_move_reveals_hidden(state, m, from_col)
            if reveals_hidden:
                return 5000.0

            # Check if this move frees an entire column
            frees_col = self._predict_move_frees_column(state, m, from_col)
            if frees_col:
                # Moving King from one empty column to another empty column is a useless cycle
                card = getattr(m, "card", None)
                val = getattr(card, "value", None) if card else None
                if val in (13, "K", "King") and to_col is not None:
                    cols = _get_columns(state)
                    if 0 <= to_col < len(cols) and len(_get_stack_cards(cols[to_col])) == 0:
                        return -500.0  # Penalize King shuffling between empty columns
                return 3000.0

            # King placed on an empty column
            if to_col is not None:
                cols = _get_columns(state)
                if 0 <= to_col < len(cols) and len(_get_stack_cards(cols[to_col])) == 0:
                    card = getattr(m, "card", None)
                    val = getattr(card, "value", None) if card else None
                    if val in (13, "K", "King"):
                        return 2000.0

            # General tableau-to-tableau moves
            if from_col is not None and to_col is not None:
                # Prefer moving larger stacks of cards
                count = getattr(m, "card_count", 1) or len(getattr(m, "cards", [])) or 1
                return 1000.0 + (count * 10.0)

            # Waste to tableau
            from_p = str(getattr(m, "from_pile", "")).lower()
            if "waste" in from_p and to_col is not None:
                return 800.0

            return 500.0

        return sorted(moves, key=move_priority, reverse=True)

    # -----------------------------------------------------------------------
    # Move Prediction and Reveal Detection Helpers
    # -----------------------------------------------------------------------

    def _predict_move_reveals_hidden(
        self,
        state: GameState,
        move: Move,
        from_col: Optional[int],
    ) -> bool:
        """Predict whether a move will reveal a face-down card in its source column."""
        if getattr(move, "reveals_card", False) or getattr(move, "reveals_hidden", False):
            return True

        if from_col is None:
            return False

        cols = _get_columns(state)
        if not (0 <= from_col < len(cols)):
            return False

        col_cards = _get_stack_cards(cols[from_col])
        if not col_cards:
            return False

        # Count face-down cards
        face_down_count = sum(1 for c in col_cards if not getattr(c, "is_face_up", True))
        if face_down_count == 0:
            return False

        # Count face-up cards
        face_up_count = len(col_cards) - face_down_count

        # Number of cards moved
        cards_moved = getattr(move, "card_count", 1) or len(getattr(move, "cards", [])) or 1

        # If all face-up cards are moved, the top face-down card will be exposed
        return cards_moved >= face_up_count

    def _predict_move_frees_column(
        self,
        state: GameState,
        move: Move,
        from_col: Optional[int],
    ) -> bool:
        """Predict whether a move will completely empty its source column."""
        if from_col is None:
            return False

        cols = _get_columns(state)
        if not (0 <= from_col < len(cols)):
            return False

        col_cards = _get_stack_cards(cols[from_col])
        if not col_cards:
            return False

        # If any hidden cards exist, emptying is impossible
        if any(not getattr(c, "is_face_up", True) for c in col_cards):
            return False

        cards_moved = getattr(move, "card_count", 1) or len(getattr(move, "cards", [])) or 1
        return cards_moved >= len(col_cards)

    def _revealed_card_is_unknown(
        self,
        old_state: GameState,
        new_state: GameState,
        move: Move,
    ) -> bool:
        """
        Check if a card newly exposed by a move has an unknown identity (e.g. Card is None,
        or value/suit is None).
        """
        col_idx = self._identify_revealed_column(old_state, new_state, move)
        if col_idx is not None:
            new_cols = _get_columns(new_state)
            if 0 <= col_idx < len(new_cols):
                top_card = _get_top_card(new_cols[col_idx])
                if top_card is None:
                    return True
                if getattr(top_card, "value", None) is None:
                    return True
                if getattr(top_card, "is_unknown", False):
                    return True

            # Also check old_state column cards under the moved stack
            old_cols = _get_columns(old_state)
            if 0 <= col_idx < len(old_cols):
                cards = _get_stack_cards(old_cols[col_idx])
                for c in cards:
                    if c is None or (not getattr(c, "is_face_up", True) and getattr(c, "value", None) is None):
                        return True

        # Fallback inspection of move attributes
        if getattr(move, "card_is_unknown", False):
            return True

        return False

    def _identify_revealed_column(
        self,
        old_state: GameState,
        new_state: GameState,
        move: Move,
    ) -> Optional[int]:
        """Identify which tableau column experienced a card reveal after a move."""
        # 1. From move pile identifier
        from_col = _extract_column_index(getattr(move, "from_pile", None))
        if from_col is not None:
            return from_col

        source = _extract_column_index(getattr(move, "source", None))
        if source is not None:
            return source

        # 2. By comparing column differences between old and new state
        old_cols = _get_columns(old_state)
        new_cols = _get_columns(new_state)

        min_len = min(len(old_cols), len(new_cols))
        for i in range(min_len):
            old_cards = _get_stack_cards(old_cols[i])
            new_cards = _get_stack_cards(new_cols[i])
            old_hidden = sum(1 for c in old_cards if not getattr(c, "is_face_up", True))
            new_hidden = sum(1 for c in new_cards if not getattr(c, "is_face_up", True))
            if old_hidden > new_hidden:
                return i

        return None

    # -----------------------------------------------------------------------
    # Solution Tracking and Formatting
    # -----------------------------------------------------------------------

    def _update_best_partial(
        self,
        state: GameState,
        moves_so_far: list[Move],
        score: float,
        hidden_revealed: int,
    ) -> None:
        """Update the collection of best partial solutions found during search."""
        foundations_count = getattr(state, "foundation_count", 0)
        empty_cols = _get_empty_columns(state)

        # Retain if it made meaningful progress or achieved a top score
        if foundations_count > 0 or hidden_revealed > 0 or empty_cols > 0 or score > self._best_partial_score:
            if score > self._best_partial_score:
                self._best_partial_score = score

            desc = self._create_partial_description(moves_so_far, foundations_count, hidden_revealed, empty_cols, score)
            partial = SolverResult(
                is_winning=False,
                moves=list(moves_so_far),
                foundation_count=foundations_count,
                hidden_revealed=hidden_revealed,
                columns_freed=empty_cols,
                score=score,
                description=desc,
            )
            self._add_partial_solution(partial)

    def _add_partial_solution(self, solution: SolverResult) -> None:
        """Add a partial solution while keeping list bounded and diverse."""
        # Check for near-duplicate move sequence lengths and scores to maintain diversity
        for existing in self._partial_solutions:
            if existing.description == solution.description and len(existing.moves) == len(solution.moves):
                if solution.score > existing.score:
                    existing.score = solution.score
                    existing.moves = solution.moves
                return

        self._partial_solutions.append(solution)
        # Keep top 20 partial candidates sorted by score
        self._partial_solutions.sort(key=lambda s: s.score, reverse=True)
        if len(self._partial_solutions) > 20:
            self._partial_solutions.pop()

    def _create_partial_description(
        self,
        moves: list[Move],
        foundations: int,
        hidden: int,
        freed: int,
        score: float,
    ) -> str:
        """Generate a natural French description summarizing a partial sequence."""
        parts = []
        if foundations > 0:
            parts.append(f"{foundations} carte{'s' if foundations > 1 else ''} aux fondations")
        if hidden > 0:
            parts.append(f"{hidden} carte{'s' if hidden > 1 else ''} cachée{'s' if hidden > 1 else ''} révélée{'s' if hidden > 1 else ''}")
        if freed > 0:
            parts.append(f"{freed} colonne{'s' if freed > 1 else ''} libérée{'s' if freed > 1 else ''}")

        if parts:
            return f"Séquence partielle ({len(moves)} coups) : " + ", ".join(parts)
        return f"Séquence de {len(moves)} coups (score heuristique : {score:.1f})"

    def _finalize_results(self) -> list[SolverResult]:
        """Sort and limit final results according to solver specifications."""
        # Winning solutions first, sorted by fewest moves
        sorted_winning = sorted(
            self._winning_solutions,
            key=lambda r: len(r.moves),
        )

        # Partial solutions sorted by score descending
        sorted_partials = sorted(
            self._partial_solutions,
            key=lambda r: r.score,
            reverse=True,
        )

        combined = sorted_winning + sorted_partials
        max_allowed = max(1, self.config.max_solutions)
        return combined[:max_allowed]

    # -----------------------------------------------------------------------
    # Move Recommendation Engine
    # -----------------------------------------------------------------------

    def get_recommendations(
        self,
        state: GameState,
        max_count: int = 5,
    ) -> list[SolverResult]:
        """
        Produce a rapid recommendation of the best immediate moves from the current state.
        Executes a fast, shallow search (depth 1 to 5 moves) within a tight time budget.
        Each recommendation represents a distinct strategic option for the player.

        Args:
            state: Current GameState to analyze.
            max_count: Maximum number of distinct recommendations to return (default 5).

        Returns:
            List of SolverResult instances with moves sequence (1-5 moves) and French explanations.
        """
        try:
            legal_moves = RulesEngine.get_legal_moves(state)
        except Exception as exc:
            logger.debug("Échec de get_legal_moves dans get_recommendations : %s", exc)
            return []

        if not legal_moves:
            return []

        # Order moves according to strategic heuristic
        ordered_moves = self._order_moves(state, legal_moves)

        recommendations: list[SolverResult] = []
        start_time = time.perf_counter()
        time_limit = self.config.recommendation_time_limit
        max_depth = self.config.recommendation_max_depth

        for move in ordered_moves:
            if (time.perf_counter() - start_time) >= time_limit:
                break

            try:
                next_state, revealed = RulesEngine.apply_move(state, move)
            except Exception as exc:
                logger.debug("apply_move échoué lors de la recommandation : %s", exc)
                continue

            # Case A: Move immediately reveals an unknown card
            if revealed and self._revealed_card_is_unknown(state, next_state, move):
                rev_col = self._identify_revealed_column(state, next_state, move)
                col_num = (rev_col + 1) if rev_col is not None else 1
                desc = self._describe_move_fr(state, move, next_state, reveals_hidden=True, rev_col=col_num)
                score = self._score_state(next_state) + 50.0

                recommendations.append(
                    SolverResult(
                        is_winning=False,
                        moves=[move],
                        foundation_count=getattr(next_state, "foundation_count", 0),
                        hidden_revealed=1,
                        columns_freed=_get_empty_columns(next_state),
                        score=score,
                        description=desc,
                        requires_reveal=True,
                        reveal_column=rev_col,
                    )
                )
                continue

            # Case B: Direct winning move
            if getattr(next_state, "is_won", False):
                recommendations.append(
                    SolverResult(
                        is_winning=True,
                        moves=[move],
                        foundation_count=52,
                        hidden_revealed=0,
                        columns_freed=7,
                        score=10000.0,
                        description="Coup gagnant direct vers la fondation !",
                    )
                )
                continue

            # Case C: Perform a shallow continuation search (up to remaining depth)
            best_seq, final_state, best_score = self._quick_continuation(
                next_state,
                current_depth=1,
                max_depth=max_depth,
                deadline=min(start_time + time_limit, time.perf_counter() + 0.35),
            )

            full_sequence = [move] + best_seq
            if len(full_sequence) == 1:
                desc = self._describe_move_fr(state, move, next_state)
            else:
                desc = self._describe_sequence_fr(state, full_sequence, final_state)

            recommendations.append(
                SolverResult(
                    is_winning=getattr(final_state, "is_won", False),
                    moves=full_sequence,
                    foundation_count=getattr(final_state, "foundation_count", 0),
                    hidden_revealed=max(0, getattr(state, "hidden_count", 0) - getattr(final_state, "hidden_count", 0)),
                    columns_freed=_get_empty_columns(final_state),
                    score=best_score,
                    description=desc,
                )
            )

        # Sort recommendations by heuristic score descending and return top max_count
        recommendations.sort(key=lambda r: (1 if r.is_winning else 0, r.score), reverse=True)
        return recommendations[:max_count]

    def _quick_continuation(
        self,
        state: GameState,
        current_depth: int,
        max_depth: int,
        deadline: float,
    ) -> tuple[list[Move], GameState, float]:
        """Quick shallow DFS continuation to evaluate a move's multi-step payoff."""
        base_score = self._score_state(state)
        if current_depth >= max_depth or time.perf_counter() >= deadline:
            return [], state, base_score

        try:
            moves = RulesEngine.get_legal_moves(state)
        except Exception:
            return [], state, base_score

        if not moves:
            return [], state, base_score

        ordered = self._order_moves(state, moves)[:6]  # Highly restricted beam for real-time speed

        best_seq: list[Move] = []
        best_state: GameState = state
        best_score = base_score

        for m in ordered:
            if time.perf_counter() >= deadline:
                break
            try:
                next_s, revealed = RulesEngine.apply_move(state, m)
            except Exception:
                continue

            if revealed and self._revealed_card_is_unknown(state, next_s, m):
                score = self._score_state(next_s) + 50.0
                if score > best_score:
                    best_score = score
                    best_seq = [m]
                    best_state = next_s
                continue

            sub_seq, sub_final, sub_score = self._quick_continuation(
                next_s,
                current_depth + 1,
                max_depth,
                deadline,
            )
            if sub_score > best_score:
                best_score = sub_score
                best_seq = [m] + sub_seq
                best_state = sub_final

        return best_seq, best_state, best_score

    # -----------------------------------------------------------------------
    # Natural Language French Explanations
    # -----------------------------------------------------------------------

    def _describe_move_fr(
        self,
        before_state: GameState,
        move: Move,
        after_state: GameState,
        reveals_hidden: bool = False,
        rev_col: Optional[int] = None,
    ) -> str:
        """Generate a natural French explanation for a single move."""
        card = getattr(move, "card", None)
        card_name = _card_name_fr(card)

        # 1. Foundation move
        if _is_foundation_move(move):
            return f"Placer {card_name} sur la fondation"

        # 2. Revealing a hidden card
        if reveals_hidden:
            col_display = rev_col if rev_col is not None else 1
            return f"Déplacer {card_name} pour révéler la carte cachée en colonne {col_display}"

        # 3. Stock draw and recycle
        is_draw, is_recycle = _is_draw_or_recycle_move(move)
        if is_recycle:
            return "Retourner la défausse dans le talon"
        if is_draw:
            return "Piocher une carte du talon"

        # 4. Column freed
        from_col = _extract_column_index(getattr(move, "from_pile", None))
        to_col = _extract_column_index(getattr(move, "to_pile", None))
        to_col_disp = (to_col + 1) if to_col is not None else "?"

        if from_col is not None:
            from_col_disp = from_col + 1
            if self._predict_move_frees_column(before_state, move, from_col):
                return f"Déplacer {card_name} vers la colonne {to_col_disp} et libérer la colonne {from_col_disp}"

        # 5. King placed on an empty column
        if to_col is not None:
            before_cols = _get_columns(before_state)
            if 0 <= to_col < len(before_cols) and len(_get_stack_cards(before_cols[to_col])) == 0:
                val = getattr(card, "value", None) if card else None
                if val in (13, "K", "King"):
                    return f"Placer {card_name} sur la colonne libre {to_col_disp}"

        # 6. Waste to tableau
        from_pile = str(getattr(move, "from_pile", "")).lower()
        if "waste" in from_pile:
            return f"Jouer {card_name} de la défausse sur la colonne {to_col_disp}"

        # 7. Standard tableau move
        return f"Déplacer {card_name} vers la colonne {to_col_disp}"

    def _describe_sequence_fr(
        self,
        initial_state: GameState,
        moves: list[Move],
        final_state: GameState,
    ) -> str:
        """Generate a natural French explanation for a multi-step sequence."""
        first_desc = self._describe_move_fr(initial_state, moves[0], final_state)
        n = len(moves)

        init_foundations = getattr(initial_state, "foundation_count", 0)
        final_foundations = getattr(final_state, "foundation_count", 0)
        foundations_gain = final_foundations - init_foundations

        init_empty = _get_empty_columns(initial_state)
        final_empty = _get_empty_columns(final_state)
        empty_gain = final_empty - init_empty

        if foundations_gain > 0:
            return f"Séquence en {n} coups : {first_desc}, envoyant {foundations_gain} carte{'s' if foundations_gain > 1 else ''} aux fondations"
        if empty_gain > 0:
            return f"Séquence en {n} coups : {first_desc}, permettant de libérer une colonne"

        return f"Séquence en {n} coups : commencer par {first_desc}"
