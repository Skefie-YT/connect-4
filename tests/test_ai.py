from __future__ import annotations

import pytest

from app import app
from engine import Bitboard, Connect4AI, HEIGHT, WIDTH
from engine.bitboard import has_won


def empty_grid() -> list[list[int]]:
    return [[0] * WIDTH for _ in range(HEIGHT)]


def test_bitboard_win_detection_directions():
    # Horizontal
    g = empty_grid()
    for c in range(4):
        g[5][c] = 1
    b = Bitboard.from_grid(g, current_player=1)
    assert has_won(b.position)

    # Vertical
    g = empty_grid()
    for r in range(2, 6):
        g[r][3] = 2
    b = Bitboard.from_grid(g, current_player=2)
    assert has_won(b.position)

    # Diagonal /
    g = empty_grid()
    g[5][0] = 1
    g[4][1] = 1
    g[3][2] = 1
    g[2][3] = 1
    b = Bitboard.from_grid(g, current_player=1)
    assert has_won(b.position)

    # Diagonal \
    g = empty_grid()
    g[2][0] = 1
    g[3][1] = 1
    g[4][2] = 1
    g[5][3] = 1
    b = Bitboard.from_grid(g, current_player=1)
    assert has_won(b.position)


def test_bitboard_no_wraparound_false_positive():
    # Sentinel bit must prevent column wrap-around false positives
    g = empty_grid()
    g[0][0] = 1
    g[1][0] = 1
    g[5][1] = 1
    g[4][1] = 1
    b = Bitboard.from_grid(g, current_player=1)
    assert not has_won(b.position)


def test_ai_takes_immediate_win():
    g = empty_grid()
    g[5][0] = 2
    g[5][1] = 2
    g[5][2] = 2
    g[4][0] = 1
    g[4][1] = 1
    g[5][6] = 1

    b = Bitboard.from_grid(g, current_player=2)
    ai = Connect4AI()
    res = ai.choose_move(b, difficulty="unbeatable")
    assert res.col == 3


def test_ai_blocks_immediate_threat():
    g = empty_grid()
    g[5][1] = 1
    g[5][2] = 1
    g[5][3] = 1
    g[4][1] = 2
    g[4][2] = 2

    b = Bitboard.from_grid(g, current_player=2)
    ai = Connect4AI()
    res = ai.choose_move(b, difficulty="unbeatable")
    assert res.col in (0, 4)


def test_ai_prefers_center_on_opening():
    b = Bitboard()
    ai = Connect4AI()
    res = ai.choose_move(b, difficulty="unbeatable")
    assert res.col == 3


def test_ai_avoids_handing_win_above():
    # If player 1 threatens (row 4, col 5) horizontally: (4,2), (4,3), (4,4)
    # and col 5 currently has 0 pieces, playing col 5 (row 5) lets P1 win at (4,5) immediately.
    g = empty_grid()
    # Build support under cols 2, 3, 4
    g[5][2] = 2
    g[5][3] = 1
    g[5][4] = 2
    # P1 has 3 in a row at row 4: cols 2, 3, 4
    g[4][2] = 1
    g[4][3] = 1
    g[4][4] = 1
    # P2 has 2 pieces in col 0
    g[5][0] = 2
    g[4][0] = 2

    b = Bitboard.from_grid(g, current_player=2)
    ai = Connect4AI()
    res = ai.choose_move(b, difficulty="unbeatable")
    # Playing col 5 would allow P1 to win on top at (4,5); col 1 is a direct win-blocker? No, (4,1) isn't reachable yet.
    # Col 5 must NOT be chosen!
    assert res.col != 5


def test_flask_api_move():
    client = app.test_client()
    g = empty_grid()
    g[5][3] = 1

    resp = client.post(
        "/api/move",
        json={"board": g, "ai_player": 2, "difficulty": "unbeatable"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["col"] == 3
    assert data["row"] == 4
    assert data["winner"] is None
    assert data["is_draw"] is False


def test_flask_api_invalid_board():
    client = app.test_client()
    resp = client.post("/api/move", json={"board": [[0]], "ai_player": 2})
    assert resp.status_code == 400
