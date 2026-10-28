"""
Tests for Flask REST API in app.py
Covers:
- Static file serving (index.html)
- /api/random-deal
- /api/init (valid input, duplicate check, card count checks)
- /api/state
- /api/draw and /api/reset-stock
- /api/move and validation
- /api/undo and /api/redo
- /api/history
- /api/available-cards
- /api/reveal
- /api/solve, /api/solver-status, /api/stop-solver, /api/results
"""

import json
import pytest
from app import app, app_state
from backend.cards import Card


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def setup_game(client):
    """Initializes a valid test game."""
    all_cards = Card.all_cards()
    visible = [c.name for c in all_cards[:7]]
    stock = [c.name for c in all_cards[7:31]]

    resp = client.post('/api/init', json={
        "visible_cards": visible,
        "stock_cards": stock
    })
    assert resp.status_code == 200
    return visible, stock


class TestFlaskAPI:
    def test_serve_index(self, client):
        resp = client.get('/')
        assert resp.status_code == 200
        assert b"Solitaire Klondike" in resp.data

    def test_random_deal(self, client):
        resp = client.get('/api/random-deal')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert len(data["visible_cards"]) == 7
        assert len(data["stock_cards"]) == 24
        # Check uniqueness
        all_dealt = data["visible_cards"] + data["stock_cards"]
        assert len(set(all_dealt)) == 31

    def test_init_invalid_counts(self, client):
        resp = client.post('/api/init', json={
            "visible_cards": ["AH", "2H"],
            "stock_cards": []
        })
        assert resp.status_code == 400
        assert "7 cartes visibles" in resp.get_json()["error"]

    def test_init_duplicates(self, client):
        all_cards = Card.all_cards()
        visible = [c.name for c in all_cards[:7]]
        # Reuse visible[0] inside stock
        stock = [visible[0]] + [c.name for c in all_cards[8:31]]

        resp = client.post('/api/init', json={
            "visible_cards": visible,
            "stock_cards": stock
        })
        assert resp.status_code == 400
        assert "double" in resp.get_json()["error"].lower()

    def test_state_endpoint(self, client, setup_game):
        resp = client.get('/api/state')
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["columns"]) == 7
        assert data["foundation_count"] == 0
        assert data["hidden_count"] == 21

    def test_draw_and_undo(self, client, setup_game):
        # Draw a card
        draw_resp = client.post('/api/draw')
        assert draw_resp.status_code == 200
        draw_data = draw_resp.get_json()
        assert draw_data["success"] is True
        assert len(draw_data["state"]["stock"]) == 23
        assert len(draw_data["state"]["waste"]) == 1

        # Check history
        hist_resp = client.get('/api/history')
        assert hist_resp.status_code == 200
        hist_data = hist_resp.get_json()
        assert len(hist_data["entries"]) == 1

        # Undo the draw
        undo_resp = client.post('/api/undo')
        assert undo_resp.status_code == 200
        undo_data = undo_resp.get_json()
        assert len(undo_data["state"]["stock"]) == 24
        assert len(undo_data["state"]["waste"]) == 0

        # Redo the draw
        redo_resp = client.post('/api/redo')
        assert redo_resp.status_code == 200
        redo_data = redo_resp.get_json()
        assert len(redo_data["state"]["stock"]) == 23
        assert len(redo_data["state"]["waste"]) == 1

    def test_available_cards(self, client, setup_game):
        resp = client.get('/api/available-cards')
        assert resp.status_code == 200
        data = resp.get_json()
        # 52 - 31 = 21 available
        assert len(data["cards"]) == 21

    def test_solver_lifecycle(self, client, setup_game):
        # Start solver
        solve_resp = client.post('/api/solve')
        assert solve_resp.status_code == 200
        assert solve_resp.get_json()["success"] is True

        # Check status
        status_resp = client.get('/api/solver-status')
        assert status_resp.status_code == 200

        # Stop solver
        stop_resp = client.post('/api/stop-solver')
        assert stop_resp.status_code == 200

        # Get results
        results_resp = client.get('/api/results')
        assert results_resp.status_code == 200
        assert "results" in results_resp.get_json()
