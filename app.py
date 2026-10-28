"""
Solitaire Klondike Solver - Flask Application
Main entry point for the web application.

Architecture:
- Serves the frontend static files (HTML/CSS/JS)
- Exposes REST API endpoints for game state management
- Runs the solver in a background thread
- All game state is kept in server memory (single-user local app)

Launch: python app.py
Access: http://localhost:5055
"""

import json
import random
import threading
import time
from flask import Flask, request, jsonify, send_from_directory, abort
from flask_cors import CORS

from backend.cards import Card, CardStack, SUITS, VALUES, VALUE_NAMES, SUIT_NAMES
from backend.game_state import GameState
from backend.rules import RulesEngine, Move, MoveType
from backend.inventory import CardInventory
from backend.history import GameHistory, HistoryEntry
from backend.solver import Solver, SolverConfig, SolverResult, SolverStats

# =============================================================================
# Flask App Configuration
# =============================================================================

app = Flask(__name__, static_folder='frontend', static_url_path='')
CORS(app)

# =============================================================================
# Global Application State (single-user local application)
# =============================================================================

class AppState:
    """Holds the entire application state for the current session."""

    def __init__(self):
        self.game_state: GameState | None = None
        self.inventory: CardInventory | None = None
        self.history: GameHistory | None = None
        self.solver: Solver | None = None
        self.solver_thread: threading.Thread | None = None
        self.solver_results: list[SolverResult] = []
        self.solver_stats: SolverStats | None = None
        self.results_valid: bool = False  # Are results current with game state?
        self.pending_reveal: dict | None = None  # {col: int} if waiting for card ID
        self.recommendations: list[SolverResult] = []

    def reset(self):
        """Reset all state for a new game."""
        if self.solver and self.solver.is_running():
            self.solver.stop()
        self.__init__()


app_state = AppState()

# =============================================================================
# Static File Serving
# =============================================================================

@app.route('/')
def serve_index():
    """Serve the main HTML page."""
    return send_from_directory('frontend', 'index.html')


@app.route('/css/<path:filename>')
def serve_css(filename):
    """Serve CSS files."""
    return send_from_directory('frontend/css', filename)


@app.route('/js/<path:filename>')
def serve_js(filename):
    """Serve JavaScript files."""
    return send_from_directory('frontend/js', filename)


@app.route('/assets/<path:filename>')
def serve_assets(filename):
    """Serve asset files (images, etc.)."""
    return send_from_directory('frontend/assets', filename)


# =============================================================================
# API: Game Initialization
# =============================================================================

@app.route('/api/init', methods=['POST'])
def api_init():
    """
    Initialize a new game with the provided card configuration.

    Request body:
    {
        "visible_cards": ["AH", "3S", "KD", "7C", "10H", "5D", "JS"],
        "stock_cards": ["2H", "4S", ..., "9C"]  // 24 cards in exact order
    }

    Returns the initial game state.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Corps de la requête manquant"}), 400

        visible_cards = data.get('visible_cards', [])
        stock_cards = data.get('stock_cards', [])

        # Validate counts
        if len(visible_cards) != 7:
            return jsonify({
                "error": f"Il faut exactement 7 cartes visibles, {len(visible_cards)} fournies."
            }), 400

        if len(stock_cards) != 24:
            return jsonify({
                "error": f"Il faut exactement 24 cartes pour la pioche, {len(stock_cards)} fournies."
            }), 400

        # Check for duplicates
        all_cards = visible_cards + stock_cards
        if len(set(all_cards)) != len(all_cards):
            seen = set()
            duplicates = []
            for c in all_cards:
                if c in seen:
                    duplicates.append(c)
                seen.add(c)
            return jsonify({
                "error": f"Cartes en double détectées : {', '.join(duplicates)}"
            }), 400

        # Validate card strings
        for card_str in all_cards:
            try:
                Card.from_string(card_str)
            except (ValueError, KeyError) as e:
                return jsonify({
                    "error": f"Carte invalide : '{card_str}'. {str(e)}"
                }), 400

        # Reset state and create new game
        app_state.reset()

        # Create initial game state
        app_state.game_state = GameState.create_initial(visible_cards, stock_cards)

        # Initialize inventory
        app_state.inventory = CardInventory()
        app_state.inventory.sync_with_state(app_state.game_state)

        # Initialize history
        app_state.history = GameHistory(app_state.game_state)

        # Create solver
        app_state.solver = Solver(SolverConfig())

        return jsonify({
            "success": True,
            "message": "Partie initialisée avec succès.",
            "state": app_state.game_state.to_dict()
        })

    except Exception as e:
        return jsonify({"error": f"Erreur d'initialisation : {str(e)}"}), 500


@app.route('/api/random-deal', methods=['GET'])
def api_random_deal():
    """
    Generate a random deal configuration:
    - 7 visible cards (one for each column)
    - 24 stock cards in exact order
    All 31 cards are guaranteed unique and valid.
    """
    all_cards = Card.all_cards()
    shuffled = [c.name for c in all_cards]
    random.shuffle(shuffled)

    visible_cards = shuffled[:7]
    stock_cards = shuffled[7:31]

    return jsonify({
        "success": True,
        "visible_cards": visible_cards,
        "stock_cards": stock_cards
    })


# =============================================================================
# API: Game State
# =============================================================================

@app.route('/api/state', methods=['GET'])
def api_get_state():
    """Get the current game state."""
    if app_state.game_state is None:
        return jsonify({"error": "Aucune partie en cours. Initialisez d'abord."}), 400

    state_dict = app_state.game_state.to_dict()
    state_dict['results_valid'] = app_state.results_valid
    state_dict['pending_reveal'] = app_state.pending_reveal
    state_dict['can_undo'] = app_state.history.can_undo() if app_state.history else False
    state_dict['can_redo'] = app_state.history.can_redo() if app_state.history else False

    return jsonify(state_dict)


# =============================================================================
# API: Move Execution
# =============================================================================

@app.route('/api/move', methods=['POST'])
def api_execute_move():
    """
    Execute a move on the game board.

    Request body:
    {
        "move_type": "TABLEAU_TO_TABLEAU" | "TABLEAU_TO_FOUNDATION" | etc.,
        "source_col": 0-6 or null,
        "dest_col": 0-6 or null,
        "dest_suit": "H"/"D"/"C"/"S" or null,
        "card_count": 1 (default)
    }
    """
    if app_state.game_state is None:
        return jsonify({"error": "Aucune partie en cours."}), 400

    if app_state.pending_reveal:
        return jsonify({
            "error": f"Veuillez d'abord identifier la carte révélée en colonne {app_state.pending_reveal['col'] + 1}."
        }), 400

    try:
        data = request.get_json() or {}
        move_type_str = str(data.get('move_type', '')).strip().upper()
        source_col = data.get('source_col')
        dest_col = data.get('dest_col')
        dest_suit = data.get('dest_suit')
        card_count = data.get('card_count', 1)

        if source_col is not None:
            source_col = int(source_col)
        if dest_col is not None:
            dest_col = int(dest_col)
        if card_count is not None:
            card_count = int(card_count)

        # Parse move type (case-insensitive)
        try:
            move_type = MoveType[move_type_str]
        except (KeyError, TypeError):
            return jsonify({"error": f"Type de coup invalide : {move_type_str}"}), 400

        # Determine the card being moved
        card = None
        if move_type in (MoveType.TABLEAU_TO_TABLEAU, MoveType.TABLEAU_TO_FOUNDATION):
            if source_col is None or source_col < 0 or source_col > 6:
                return jsonify({"error": "Colonne source invalide (doit être entre 1 et 7)."}), 400
            face_up = app_state.game_state.get_face_up_sequence(source_col)
            if not face_up:
                return jsonify({"error": f"Pas de carte visible en colonne {source_col + 1}."}), 400
            if card_count > len(face_up):
                return jsonify({"error": f"Pas assez de cartes visibles pour déplacer {card_count} cartes."}), 400
            card = face_up[-card_count]  # The bottom card of the sequence being moved
        elif move_type in (MoveType.WASTE_TO_TABLEAU, MoveType.WASTE_TO_FOUNDATION):
            card = app_state.game_state.waste_top
            if card is None:
                return jsonify({"error": "Pas de carte dans la défausse."}), 400

        # If dest_suit is missing for a foundation move, infer it from the card
        if move_type in (MoveType.TABLEAU_TO_FOUNDATION, MoveType.WASTE_TO_FOUNDATION):
            if not dest_suit and card:
                dest_suit = card.suit
            elif dest_suit:
                dest_suit = str(dest_suit).strip().upper()

        # Build Move object
        description = _build_move_description(move_type, card, source_col, dest_col, dest_suit, card_count)
        move = Move(
            type=move_type,
            source_col=source_col,
            dest_col=dest_col,
            dest_suit=dest_suit,
            card_count=card_count,
            card=card,
            description_fr=description
        )

        # Validate the move
        is_valid, error_msg = RulesEngine.validate_move(app_state.game_state, move)
        if not is_valid:
            return jsonify({"error": error_msg}), 400

        # Apply the move
        state_before = app_state.game_state
        new_state, card_revealed = RulesEngine.apply_move(app_state.game_state, move)

        # Record in history
        entry = HistoryEntry(
            action_type='move',
            move=move,
            state_before=state_before,
            state_after=new_state,
            revealed_card=None,
            revealed_position=None,
            timestamp=time.time(),
            description=description
        )
        app_state.history.record(entry)

        # Update state
        app_state.game_state = new_state
        app_state.inventory.sync_with_state(new_state)

        # Invalidate solver results
        app_state.results_valid = False

        # Check if a card was revealed
        response = {
            "success": True,
            "message": f"Coup exécuté : {description}",
            "state": new_state.to_dict(),
            "card_revealed": card_revealed,
            "is_won": new_state.is_won
        }

        if card_revealed:
            # Find which column had a card revealed
            reveal_col = _find_revealed_column(state_before, new_state, move)
            if reveal_col is not None:
                app_state.pending_reveal = {"col": reveal_col}
                response["pending_reveal"] = {"col": reveal_col}
                response["message"] += f" — Une carte cachée est révélée en colonne {reveal_col + 1}."

        response['can_undo'] = app_state.history.can_undo()
        response['can_redo'] = app_state.history.can_redo()
        response['results_valid'] = app_state.results_valid

        return jsonify(response)

    except Exception as e:
        return jsonify({"error": f"Erreur lors de l'exécution du coup : {str(e)}"}), 500


@app.route('/api/draw', methods=['POST'])
def api_draw_card():
    """Draw a card from the stock to the waste."""
    if app_state.game_state is None:
        return jsonify({"error": "Aucune partie en cours."}), 400

    if app_state.pending_reveal:
        return jsonify({
            "error": f"Veuillez d'abord identifier la carte révélée en colonne {app_state.pending_reveal['col'] + 1}."
        }), 400

    if app_state.game_state.stock_empty:
        return jsonify({"error": "La pioche est vide. Recyclez la défausse."}), 400

    move = Move(
        type=MoveType.DRAW_CARD,
        source_col=None,
        dest_col=None,
        dest_suit=None,
        card_count=1,
        card=app_state.game_state.stock[0] if app_state.game_state.stock else None,
        description_fr="Piocher une carte"
    )

    state_before = app_state.game_state
    new_state, _ = RulesEngine.apply_move(app_state.game_state, move)

    entry = HistoryEntry(
        action_type='draw',
        move=move,
        state_before=state_before,
        state_after=new_state,
        revealed_card=None,
        revealed_position=None,
        timestamp=time.time(),
        description="Piocher une carte"
    )
    app_state.history.record(entry)
    app_state.game_state = new_state
    app_state.inventory.sync_with_state(new_state)
    app_state.results_valid = False

    return jsonify({
        "success": True,
        "message": "Carte piochée.",
        "state": new_state.to_dict(),
        "can_undo": app_state.history.can_undo(),
        "can_redo": app_state.history.can_redo(),
        "results_valid": False
    })


@app.route('/api/reset-stock', methods=['POST'])
def api_reset_stock():
    """Reset the stock from the waste pile."""
    if app_state.game_state is None:
        return jsonify({"error": "Aucune partie en cours."}), 400

    if app_state.pending_reveal:
        return jsonify({
            "error": f"Veuillez d'abord identifier la carte révélée en colonne {app_state.pending_reveal['col'] + 1}."
        }), 400

    if not app_state.game_state.stock_empty:
        return jsonify({"error": "La pioche n'est pas encore vide."}), 400

    if not app_state.game_state.waste:
        return jsonify({"error": "La défausse est vide également."}), 400

    move = Move(
        type=MoveType.RESET_STOCK,
        source_col=None,
        dest_col=None,
        dest_suit=None,
        card_count=0,
        card=None,
        description_fr="Retourner la défausse pour reformer la pioche"
    )

    state_before = app_state.game_state
    new_state, _ = RulesEngine.apply_move(app_state.game_state, move)

    entry = HistoryEntry(
        action_type='reset_stock',
        move=move,
        state_before=state_before,
        state_after=new_state,
        revealed_card=None,
        revealed_position=None,
        timestamp=time.time(),
        description="Retourner la défausse pour reformer la pioche"
    )
    app_state.history.record(entry)
    app_state.game_state = new_state
    app_state.inventory.sync_with_state(new_state)
    app_state.results_valid = False

    return jsonify({
        "success": True,
        "message": "Défausse retournée pour reformer la pioche.",
        "state": new_state.to_dict(),
        "can_undo": app_state.history.can_undo(),
        "can_redo": app_state.history.can_redo(),
        "results_valid": False
    })


# =============================================================================
# API: Card Reveal
# =============================================================================

@app.route('/api/reveal', methods=['POST'])
def api_reveal_card():
    """
    Identify a revealed hidden card.

    Request body:
    {
        "col": 3,
        "card_id": "AH"
    }
    """
    if app_state.game_state is None:
        return jsonify({"error": "Aucune partie en cours."}), 400

    data = request.get_json() or {}
    col = data.get('col')
    card_id = data.get('card_id')

    if not app_state.pending_reveal:
        if col is not None and 0 <= int(col) < 7:
            col_idx = int(col)
            column = app_state.game_state.columns[col_idx]
            if column and not column[-1].face_up:
                app_state.pending_reveal = {"col": col_idx}
        if not app_state.pending_reveal:
            return jsonify({"error": "Aucune carte en attente d'identification."}), 400

    try:
        if card_id is None:
            # User chose to defer identification
            return jsonify({
                "success": True,
                "message": "Identification reportée. Les recommandations dépendant de cette carte sont suspendues.",
                "state": app_state.game_state.to_dict(),
                "pending_reveal": app_state.pending_reveal
            })

        # Parse the card
        try:
            revealed_card = Card.from_string(card_id)
        except (ValueError, KeyError) as e:
            return jsonify({"error": f"Carte invalide : '{card_id}'. {str(e)}"}), 400

        # Check if card is available
        if not app_state.inventory.is_card_available(revealed_card):
            location = app_state.inventory.get_card_location(revealed_card)
            return jsonify({
                "error": f"La carte {revealed_card.display_name} est déjà utilisée ({location})."
            }), 400

        # Update the game state with the revealed card
        reveal_col = int(col) if col is not None else app_state.pending_reveal['col']
        new_state = app_state.game_state.clone()

        # Find the face-down card at the top of the column that needs identification
        column = new_state.columns[reveal_col]
        revealed_idx = None
        for i in range(len(column) - 1, -1, -1):
            if not column[i].face_up and column[i].card is None:
                column[i] = CardStack(card=revealed_card, face_up=True)
                revealed_idx = i
                break
            elif not column[i].face_up:
                # This is a face-down card with unknown identity at top
                column[i] = CardStack(card=revealed_card, face_up=True)
                revealed_idx = i
                break

        if revealed_idx is None:
            # Fallback: find the top face-down card
            for i in range(len(column) - 1, -1, -1):
                if not column[i].face_up:
                    column[i] = CardStack(card=revealed_card, face_up=True)
                    revealed_idx = i
                    break

        # Record in history
        state_before = app_state.game_state
        entry = HistoryEntry(
            action_type='reveal',
            move=None,
            state_before=state_before,
            state_after=new_state,
            revealed_card=revealed_card,
            revealed_position=(reveal_col, revealed_idx),
            timestamp=time.time(),
            description=f"Carte révélée en colonne {reveal_col + 1} : {revealed_card.display_name}"
        )
        app_state.history.record(entry)

        # Update state
        app_state.game_state = new_state
        app_state.inventory.sync_with_state(new_state)
        app_state.pending_reveal = None
        app_state.results_valid = False

        return jsonify({
            "success": True,
            "message": f"Carte identifiée : {revealed_card.display_name} en colonne {reveal_col + 1}.",
            "state": new_state.to_dict(),
            "pending_reveal": None,
            "can_undo": app_state.history.can_undo(),
            "can_redo": app_state.history.can_redo(),
            "results_valid": False
        })

    except Exception as e:
        return jsonify({"error": f"Erreur lors de l'identification : {str(e)}"}), 500


@app.route('/api/available-cards', methods=['GET'])
def api_available_cards():
    """Get the list of cards not yet assigned to any position."""
    if app_state.inventory is None:
        # Return all 52 cards if no game started
        all_cards = Card.all_cards()
        return jsonify({
            "cards": [c.to_dict() for c in all_cards]
        })

    available = app_state.inventory.get_available_cards()
    return jsonify({
        "cards": [c.to_dict() for c in available]
    })


# =============================================================================
# API: Solver
# =============================================================================

@app.route('/api/solve', methods=['POST'])
def api_start_solver():
    """Start the solver in a background thread."""
    if app_state.game_state is None:
        return jsonify({"error": "Aucune partie en cours."}), 400

    if app_state.pending_reveal:
        return jsonify({
            "error": f"Veuillez d'abord identifier la carte révélée en colonne {app_state.pending_reveal['col'] + 1}."
        }), 400

    if app_state.solver and app_state.solver.is_running():
        return jsonify({"error": "Une recherche est déjà en cours."}), 400

    # Create a new solver instance
    app_state.solver = Solver(SolverConfig())
    app_state.solver_results = []
    app_state.solver_stats = None
    app_state.results_valid = True

    # Run solver in background thread
    def run_solver():
        try:
            results, stats = app_state.solver.solve(app_state.game_state)
            app_state.solver_results = results
            app_state.solver_stats = stats
        except Exception as e:
            app_state.solver_stats = SolverStats()
            app_state.solver_stats.status = 'error'
            app_state.solver_stats.error_message = str(e)

    app_state.solver_thread = threading.Thread(target=run_solver, daemon=True)
    app_state.solver_thread.start()

    return jsonify({
        "success": True,
        "message": "Recherche lancée."
    })


@app.route('/api/solver-status', methods=['GET'])
def api_solver_status():
    """Get the current solver status and progress."""
    if app_state.solver is None:
        return jsonify({
            "status": "ready",
            "message": "Prête",
            "states_explored": 0,
            "solutions_found": 0,
            "elapsed_seconds": 0,
            "best_foundation_count": 0,
            "best_hidden_revealed": 0
        })

    stats = app_state.solver.get_stats()
    stats_dict = stats.to_dict() if stats else {
        "status": "ready",
        "states_explored": 0,
        "solutions_found": 0,
        "elapsed_seconds": 0,
        "best_foundation_count": 0,
        "best_hidden_revealed": 0
    }

    # Add current partial results count
    current_results = app_state.solver.get_current_results()
    stats_dict['current_results_count'] = len(current_results) if current_results else 0

    return jsonify(stats_dict)


@app.route('/api/stop-solver', methods=['POST'])
def api_stop_solver():
    """Stop the running solver."""
    if app_state.solver is None or not app_state.solver.is_running():
        return jsonify({"message": "Aucune recherche en cours."}), 200

    app_state.solver.stop()

    # Wait briefly for the solver to stop
    if app_state.solver_thread:
        app_state.solver_thread.join(timeout=3.0)

    # Collect results
    app_state.solver_results = app_state.solver.get_current_results()
    app_state.solver_stats = app_state.solver.get_stats()

    return jsonify({
        "success": True,
        "message": "Recherche arrêtée.",
        "stats": app_state.solver_stats.to_dict() if app_state.solver_stats else {}
    })


@app.route('/api/results', methods=['GET'])
def api_get_results():
    """Get the solver results."""
    if not app_state.solver_results and app_state.solver:
        # Try to get current results from running solver
        app_state.solver_results = app_state.solver.get_current_results()

    results = []
    for r in (app_state.solver_results or []):
        results.append(r.to_dict())

    stats = None
    if app_state.solver_stats:
        stats = app_state.solver_stats.to_dict()
    elif app_state.solver:
        s = app_state.solver.get_stats()
        stats = s.to_dict() if s else None

    return jsonify({
        "results": results,
        "stats": stats,
        "results_valid": app_state.results_valid
    })


@app.route('/api/confirm-move', methods=['POST'])
def api_confirm_recommended_move():
    """
    Confirm and execute a recommended move (from solver results).

    Request body:
    {
        "result_index": 0,
        "move_index": 0
    }
    """
    if app_state.game_state is None:
        return jsonify({"error": "Aucune partie en cours."}), 400

    try:
        data = request.get_json() or {}
        result_idx = data.get('result_index')
        if result_idx is None:
            result_idx = data.get('solution_index')
        if result_idx is None:
            result_idx = data.get('move_index', 0)
        move_idx = data.get('move_index', 0) if data.get('result_index') is not None or data.get('solution_index') is not None else 0

        if not app_state.solver_results or result_idx >= len(app_state.solver_results):
            return jsonify({"error": "Résultat de recherche introuvable."}), 400

        result = app_state.solver_results[result_idx]
        if move_idx >= len(result.moves):
            return jsonify({"error": "Coup introuvable dans cette séquence."}), 400

        move = result.moves[move_idx]

        # Validate the move against current state
        is_valid, error_msg = RulesEngine.validate_move(app_state.game_state, move)
        if not is_valid:
            return jsonify({
                "error": f"Ce coup n'est plus valide dans l'état actuel : {error_msg}"
            }), 400

        # Apply the move
        state_before = app_state.game_state
        new_state, card_revealed = RulesEngine.apply_move(app_state.game_state, move)

        entry = HistoryEntry(
            action_type='move',
            move=move,
            state_before=state_before,
            state_after=new_state,
            revealed_card=None,
            revealed_position=None,
            timestamp=time.time(),
            description=move.description_fr
        )
        app_state.history.record(entry)
        app_state.game_state = new_state
        app_state.inventory.sync_with_state(new_state)
        app_state.results_valid = False

        response = {
            "success": True,
            "message": f"Coup confirmé : {move.description_fr}",
            "state": new_state.to_dict(),
            "card_revealed": card_revealed,
            "is_won": new_state.is_won,
            "can_undo": app_state.history.can_undo(),
            "can_redo": app_state.history.can_redo(),
            "results_valid": False
        }

        if card_revealed:
            reveal_col = _find_revealed_column(state_before, new_state, move)
            if reveal_col is not None:
                app_state.pending_reveal = {"col": reveal_col}
                response["pending_reveal"] = {"col": reveal_col}
                response["message"] += f" — Carte révélée en colonne {reveal_col + 1}."

        return jsonify(response)

    except Exception as e:
        return jsonify({"error": f"Erreur : {str(e)}"}), 500


# =============================================================================
# API: Undo / Redo
# =============================================================================

@app.route('/api/undo', methods=['POST'])
def api_undo():
    """Undo the last action."""
    if app_state.history is None:
        return jsonify({"error": "Aucune partie en cours."}), 400

    if not app_state.history.can_undo():
        return jsonify({"error": "Rien à annuler."}), 400

    previous_state = app_state.history.undo()
    if previous_state is None:
        return jsonify({"error": "Impossible d'annuler."}), 400

    app_state.game_state = previous_state
    app_state.inventory.sync_with_state(previous_state)
    app_state.pending_reveal = None
    app_state.results_valid = False

    return jsonify({
        "success": True,
        "message": "Action annulée.",
        "state": previous_state.to_dict(),
        "can_undo": app_state.history.can_undo(),
        "can_redo": app_state.history.can_redo(),
        "results_valid": False
    })


@app.route('/api/redo', methods=['POST'])
def api_redo():
    """Redo the previously undone action."""
    if app_state.history is None:
        return jsonify({"error": "Aucune partie en cours."}), 400

    if not app_state.history.can_redo():
        return jsonify({"error": "Rien à rétablir."}), 400

    next_state = app_state.history.redo()
    if next_state is None:
        return jsonify({"error": "Impossible de rétablir."}), 400

    app_state.game_state = next_state
    app_state.inventory.sync_with_state(next_state)
    app_state.pending_reveal = None
    app_state.results_valid = False

    return jsonify({
        "success": True,
        "message": "Action rétablie.",
        "state": next_state.to_dict(),
        "can_undo": app_state.history.can_undo(),
        "can_redo": app_state.history.can_redo(),
        "results_valid": False
    })


# =============================================================================
# API: History
# =============================================================================

@app.route('/api/history', methods=['GET'])
def api_get_history():
    """Get the action history."""
    if app_state.history is None:
        return jsonify({"entries": [], "current_index": -1})

    return jsonify({
        "entries": app_state.history.get_entries(),
        "current_index": app_state.history.current_index
    })


# =============================================================================
# API: Manual Move (user-specified move)
# =============================================================================

@app.route('/api/manual-move', methods=['POST'])
def api_manual_move():
    """
    Execute a move manually specified by the user.
    Same as /api/move but with a different intent label.
    """
    return api_execute_move()


# =============================================================================
# Helper Functions
# =============================================================================

def _build_move_description(move_type: MoveType, card, source_col, dest_col, dest_suit, card_count) -> str:
    """Build a French description of a move."""
    card_name = card.display_name if card else "?"

    if move_type == MoveType.TABLEAU_TO_TABLEAU:
        if card_count > 1:
            return f"Déplacer {card_count} cartes depuis {card_name} de la colonne {source_col + 1} vers la colonne {dest_col + 1}"
        return f"Déplacer {card_name} de la colonne {source_col + 1} vers la colonne {dest_col + 1}"
    elif move_type == MoveType.TABLEAU_TO_FOUNDATION:
        return f"Placer {card_name} de la colonne {source_col + 1} sur la fondation {SUIT_NAMES.get(dest_suit, dest_suit)}"
    elif move_type == MoveType.WASTE_TO_TABLEAU:
        return f"Placer {card_name} de la défausse sur la colonne {dest_col + 1}"
    elif move_type == MoveType.WASTE_TO_FOUNDATION:
        return f"Placer {card_name} de la défausse sur la fondation {SUIT_NAMES.get(dest_suit, dest_suit)}"
    elif move_type == MoveType.DRAW_CARD:
        return "Piocher une carte"
    elif move_type == MoveType.RESET_STOCK:
        return "Retourner la défausse pour reformer la pioche"
    return "Coup"


def _find_revealed_column(state_before: GameState, state_after: GameState, move: Move) -> int | None:
    """Find which column had a card revealed after a move."""
    # The source column of a tableau move might have revealed a card
    if move.type == MoveType.TABLEAU_TO_TABLEAU:
        col = move.source_col
        if col is not None:
            before_col = state_before.columns[col]
            after_col = state_after.columns[col]
            # Check if a face-down card became the top
            if len(after_col) > 0 and len(before_col) > len(after_col):
                top_after = after_col[-1] if after_col else None
                if top_after and not top_after.face_up:
                    return col
                # Or if we need to check if it was flipped
                # Look at the before state - was there a face-down card under the moved cards?
                cards_removed = len(before_col) - len(after_col)
                if cards_removed > 0 and len(after_col) > 0:
                    # The new top card might have been face-down and auto-flipped
                    new_top_before_idx = len(after_col) - 1
                    if new_top_before_idx < len(before_col):
                        if not before_col[new_top_before_idx].face_up:
                            return col
    elif move.type == MoveType.TABLEAU_TO_FOUNDATION:
        col = move.source_col
        if col is not None:
            after_col = state_after.columns[col]
            before_col = state_before.columns[col]
            if len(after_col) > 0 and len(before_col) > len(after_col):
                new_top_before_idx = len(after_col) - 1
                if new_top_before_idx >= 0 and new_top_before_idx < len(before_col):
                    if not before_col[new_top_before_idx].face_up:
                        return col

    return None


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == '__main__':
    print("=" * 50)
    print("  Solitaire Klondike - Assistant de Résolution")
    print("=" * 50)
    print()
    print("  Ouvrez votre navigateur à l'adresse :")
    print("  http://localhost:5055")
    print()
    print("  Appuyez sur Ctrl+C pour arrêter le serveur")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5055, debug=False, threaded=True)
