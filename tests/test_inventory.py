"""
Tests for backend/inventory.py
Covers:
- Central card inventory of 52 cards
- Available cards calculation
- Rejection of double-assignment
- Synchronization with GameState
"""

import pytest
from backend.cards import Card
from backend.game_state import GameState
from backend.inventory import CardInventory


class TestCardInventory:
    def test_inventory_initial(self):
        inv = CardInventory()
        assert len(inv.all_cards) == 52
        assert len(inv.get_available_cards()) == 52
        assert len(inv.assigned_cards) == 0

    def test_assign_and_unassign(self):
        inv = CardInventory()
        card = Card.from_string("AH")

        # Assign to column 0
        success = inv.assign_card(card, "column_0")
        assert success is True
        assert inv.is_card_available(card) is False
        assert len(inv.get_available_cards()) == 51
        assert inv.get_card_location(card) == "column_0"

        # Double assignment must fail
        duplicate_success = inv.assign_card(card, "stock")
        assert duplicate_success is False

        # Unassign
        inv.unassign_card(card)
        assert inv.is_card_available(card) is True
        assert len(inv.get_available_cards()) == 52

    def test_sync_with_game_state(self):
        all_cards = Card.all_cards()
        visible = [c.name for c in all_cards[:7]]
        stock = [c.name for c in all_cards[7:31]]

        state = GameState.create_initial(visible, stock)
        inv = CardInventory()
        inv.sync_with_state(state)

        # 31 cards assigned: 7 in columns, 24 in stock
        assert len(inv.assigned_cards) == 31
        # 52 - 31 = 21 cards available (these are the hidden cards in columns)
        assert len(inv.get_available_cards()) == 21

        # Visible cards are assigned to columns
        for i, card_name in enumerate(visible):
            c = Card.from_string(card_name)
            assert inv.is_card_available(c) is False
            assert inv.get_card_location(c) == f"column_{i}"

        # Stock cards are assigned to stock
        for card_name in stock:
            c = Card.from_string(card_name)
            assert inv.is_card_available(c) is False
            assert inv.get_card_location(c) == "stock"
