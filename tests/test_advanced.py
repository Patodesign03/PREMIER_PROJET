"""
Advanced integration tests covering:
- Card reveal workflow (API + backend)
- Deferring card identification
- Preventing selection of already-assigned cards during revelation
- Reset stock legality checks
- Complex multi-step tableau manipulation
"""

import pytest
from app import app, app_state
from backend.cards import Card, CardStack
from backend.game_state import GameState
from backend.rules import RulesEngine, Move, MoveType
from backend.inventory import CardInventory
from backend.history import GameHistory, HistoryEntry


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestAdvancedWorkflow:
    def test_reveal_workflow(self, client):
        all_cards = Card.all_cards()
        visible = [c.name for c in all_cards[:7]]
        stock = [c.name for c in all_cards[7:31]]

        client.post('/api/init', json={
            "visible_cards": visible,
            "stock_cards": stock
        })

        # Set up a situation where col 1 has a hidden card under visible[1]
        # and visible[1] can move to col 0
        state = app_state.game_state
        state.columns[0] = [CardStack(card=Card.from_string("9S"), face_up=True)]
        state.columns[1] = [
            CardStack(card=None, face_up=False),
            CardStack(card=Card.from_string("8H"), face_up=True)
        ]

        # Execute move: 8H from col 1 to col 0
        move_resp = client.post('/api/move', json={
            "move_type": "TABLEAU_TO_TABLEAU",
            "source_col": 1,
            "dest_col": 0,
            "card_count": 1
        })
        assert move_resp.status_code == 200
        move_data = move_resp.get_json()
        assert move_data["card_revealed"] is True
        assert app_state.pending_reveal == {"col": 1}

        # Attempt to make another move while reveal is pending -> must be blocked
        draw_blocked = client.post('/api/draw')
        assert draw_blocked.status_code == 400
        assert "identifier la carte révélée" in draw_blocked.get_json()["error"]

        # Attempt to reveal with a card that is already used (e.g. 9S) -> must be rejected
        dup_reveal = client.post('/api/reveal', json={
            "col": 1,
            "card_id": "9S"
        })
        assert dup_reveal.status_code == 400
        assert "déjà utilisée" in dup_reveal.get_json()["error"]

        # Reveal with an available card (e.g. 32nd card in all_cards)
        available_card = all_cards[31].name
        valid_reveal = client.post('/api/reveal', json={
            "col": 1,
            "card_id": available_card
        })
        assert valid_reveal.status_code == 200
        assert app_state.pending_reveal is None

        # The revealed card should now be visible on col 1
        curr_state = app_state.game_state
        assert curr_state.columns[1][-1].face_up is True
        assert curr_state.columns[1][-1].card.name == available_card

    def test_defer_reveal(self, client):
        all_cards = Card.all_cards()
        visible = [c.name for c in all_cards[:7]]
        stock = [c.name for c in all_cards[7:31]]

        client.post('/api/init', json={
            "visible_cards": visible,
            "stock_cards": stock
        })

        # Set pending reveal manually
        app_state.pending_reveal = {"col": 2}

        # User chooses to defer (card_id is None)
        defer_resp = client.post('/api/reveal', json={
            "col": 2,
            "card_id": None
        })
        assert defer_resp.status_code == 200
        assert "reportée" in defer_resp.get_json()["message"]
        # Pending reveal remains in place so solver knows identity is deferred
        assert app_state.pending_reveal == {"col": 2}

    def test_reset_stock_invalid_when_stock_not_empty(self, client):
        all_cards = Card.all_cards()
        visible = [c.name for c in all_cards[:7]]
        stock = [c.name for c in all_cards[7:31]]

        client.post('/api/init', json={
            "visible_cards": visible,
            "stock_cards": stock
        })

        # Reset stock while stock still has 24 cards -> must fail
        reset_resp = client.post('/api/reset-stock')
        assert reset_resp.status_code == 400
        assert "pas encore vide" in reset_resp.get_json()["error"]
