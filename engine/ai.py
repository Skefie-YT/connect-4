from __future__ import annotations

import random
import time
from dataclasses import dataclass

from .bitboard import (
    BOARD_MASK,
    BOTTOM_COL_MASKS,
    CENTER_ORDER,
    COL_MASKS,
    H1,
    HEIGHT,
    SIZE,
    WIDTH,
    Bitboard,
    compute_winning_position,
)

WIN_SCORE = 1_000_000
WIN_THRESHOLD = 900_000

# TT Entry Flags
EXACT = 0
LOWER = 1
UPPER = 2

# Parity masks (0-indexed rows from bottom: 0, 2, 4 are odd 1st/3rd/5th rows for P1)
ODD_ROW_MASK = sum(
    (1 << (c * H1 + r)) for c in range(WIDTH) for r in (0, 2, 4)
)
EVEN_ROW_MASK = sum(
    (1 << (c * H1 + r)) for c in range(WIDTH) for r in (1, 3, 5)
)
CENTER_COL_MASK = COL_MASKS[3]
NEAR_CENTER_MASK = COL_MASKS[2] | COL_MASKS[4]
OUTER_CENTER_MASK = COL_MASKS[1] | COL_MASKS[5]


class SearchTimeout(Exception):
    """Raised when the search time budget expires."""


@dataclass
class SearchResult:
    col: int
    score: int
    depth: int
    nodes: int
    elapsed_ms: float


class Connect4AI:
    """High-speed Bitboard Negamax + Alpha-Beta + TT Connect 4 AI."""

    DIFFICULTY_SETTINGS = {
        "unbeatable": {"max_depth": 42, "time_limit": 1.25},
        "hard": {"max_depth": 7, "time_limit": 0.45},
        "casual": {"max_depth": 3, "time_limit": 0.15},
    }

    def __init__(self) -> None:
        # Transposition table: key -> (flag, score, best_col, depth)
        self.tt: dict[int, tuple[int, int, int, int]] = {}
        self._nodes = 0
        self._deadline = 0.0

    def choose_move(
        self, board: Bitboard, difficulty: str = "unbeatable"
    ) -> SearchResult:
        start = time.perf_counter()
        settings = self.DIFFICULTY_SETTINGS.get(
            difficulty, self.DIFFICULTY_SETTINGS["unbeatable"]
        )
        max_depth = min(settings["max_depth"], SIZE - board.moves)
        time_limit = settings["time_limit"]

        # 1. Opening book: center column on move 0 or 1
        if board.moves <= 1 and board.can_play(3):
            return SearchResult(
                col=3,
                score=0,
                depth=1,
                nodes=1,
                elapsed_ms=(time.perf_counter() - start) * 1000,
            )

        possible = board.possible_mask()
        if possible == 0:
            raise ValueError("No legal moves available")

        # 2. Immediate winning move check
        my_wins = possible & compute_winning_position(board.position, board.mask)
        if my_wins:
            for col in CENTER_ORDER:
                if my_wins & COL_MASKS[col]:
                    return SearchResult(
                        col=col,
                        score=WIN_SCORE - board.moves - 1,
                        depth=1,
                        nodes=1,
                        elapsed_ms=(time.perf_counter() - start) * 1000,
                    )

        # 3. Single forced blocking move check
        opp = board.position ^ board.mask
        opp_wins = compute_winning_position(opp, board.mask)
        forced = possible & opp_wins
        if forced and (forced & (forced - 1)) == 0:
            for col in CENTER_ORDER:
                if forced & COL_MASKS[col]:
                    return SearchResult(
                        col=col,
                        score=0,
                        depth=1,
                        nodes=1,
                        elapsed_ms=(time.perf_counter() - start) * 1000,
                    )

        # Casual mode: occasionally pick between top legal moves
        if difficulty == "casual":
            legal_cols = [c for c in CENTER_ORDER if board.can_play(c)]
            if len(legal_cols) > 1 and random.random() < 0.25:
                safe = possible & ~(opp_wins >> 1)
                safe_cols = [c for c in legal_cols if safe & COL_MASKS[c]]
                pool = safe_cols if safe_cols else legal_cols
                chosen = random.choice(pool[: min(3, len(pool))])
                return SearchResult(
                    col=chosen,
                    score=0,
                    depth=1,
                    nodes=1,
                    elapsed_ms=(time.perf_counter() - start) * 1000,
                )

        # Clear TT if it grows too large
        if len(self.tt) > 600_000:
            self.tt.clear()

        self._nodes = 0
        self._deadline = start + time_limit

        best_col = next(c for c in CENTER_ORDER if board.can_play(c))
        best_score = 0
        completed_depth = 0

        # 4. Iterative Deepening
        for depth in range(2, max_depth + 1):
            try:
                score, col = self._search_root(board, depth)
                best_col = col
                best_score = score
                completed_depth = depth
                # Stop early if we found a forced win
                if score >= WIN_THRESHOLD:
                    break
            except SearchTimeout:
                break

        elapsed_ms = (time.perf_counter() - start) * 1000
        return SearchResult(
            col=best_col,
            score=best_score,
            depth=completed_depth,
            nodes=self._nodes,
            elapsed_ms=elapsed_ms,
        )

    def _search_root(self, board: Bitboard, depth: int) -> tuple[int, int]:
        pos = board.position
        mask = board.mask
        moves = board.moves
        possible = (mask + 0x40810204081) & BOARD_MASK  # BOTTOM_MASK

        opp = pos ^ mask
        opp_wins = compute_winning_position(opp, mask)
        forced = possible & opp_wins
        if forced:
            search_mask = forced
        else:
            safe = possible & ~(opp_wins >> 1)
            search_mask = safe if safe else possible

        tt_entry = self.tt.get(pos + mask)
        tt_col = tt_entry[2] if tt_entry is not None else -1

        ordered_cols: list[int] = []
        if tt_col != -1 and (search_mask & COL_MASKS[tt_col]):
            ordered_cols.append(tt_col)
        for col in CENTER_ORDER:
            if col != tt_col and (search_mask & COL_MASKS[col]):
                ordered_cols.append(col)

        alpha = -WIN_SCORE - 100
        beta = WIN_SCORE + 100
        best_col = ordered_cols[0]
        best_score = -WIN_SCORE - 100

        for col in ordered_cols:
            new_pos = pos ^ mask
            new_mask = mask | (mask + BOTTOM_COL_MASKS[col])
            score = -self._negamax(new_pos, new_mask, moves + 1, depth - 1, -beta, -alpha)
            if score > best_score:
                best_score = score
                best_col = col
            if score > alpha:
                alpha = score

        self.tt[pos + mask] = (EXACT, best_score, best_col, depth)
        return best_score, best_col

    def _negamax(
        self,
        pos: int,
        mask: int,
        moves: int,
        depth: int,
        alpha: int,
        beta: int,
    ) -> int:
        self._nodes += 1
        if (self._nodes & 2047) == 0 and time.perf_counter() >= self._deadline:
            raise SearchTimeout

        if moves == SIZE:
            return 0

        possible = (mask + 0x40810204081) & BOARD_MASK

        # Immediate win in 1 ply
        if possible & compute_winning_position(pos, mask):
            return WIN_SCORE - moves - 1

        # Opponent immediate threats
        opp = pos ^ mask
        opp_wins = compute_winning_position(opp, mask)
        forced = possible & opp_wins
        if forced:
            # Double threat -> opponent wins on next turn
            if forced & (forced - 1):
                return -(WIN_SCORE - moves - 2)
            search_mask = forced
        else:
            safe = possible & ~(opp_wins >> 1)
            if not safe:
                return -(WIN_SCORE - moves - 2)
            search_mask = safe

        # Upper bound pruning: best possible score is winning in moves + 3
        max_possible = WIN_SCORE - moves - 3
        if beta > max_possible:
            beta = max_possible
            if alpha >= beta:
                return beta

        if depth <= 0:
            return self._evaluate(pos, opp, mask, moves)

        key = pos + mask
        tt_entry = self.tt.get(key)
        tt_col = -1
        if tt_entry is not None:
            flag, tt_score, tt_col, tt_depth = tt_entry
            if tt_depth >= depth:
                if flag == EXACT:
                    return tt_score
                if flag == LOWER and tt_score > alpha:
                    alpha = tt_score
                elif flag == UPPER and tt_score < beta:
                    beta = tt_score
                if alpha >= beta:
                    return tt_score

        orig_alpha = alpha
        best_col = -1
        best_score = -WIN_SCORE - 100

        # Explore TT move first, then center-out
        if tt_col != -1 and (search_mask & COL_MASKS[tt_col]):
            new_pos = opp
            new_mask = mask | (mask + BOTTOM_COL_MASKS[tt_col])
            score = -self._negamax(new_pos, new_mask, moves + 1, depth - 1, -beta, -alpha)
            best_score = score
            best_col = tt_col
            if score > alpha:
                alpha = score
            if alpha >= beta:
                self.tt[key] = (LOWER, best_score, best_col, depth)
                return best_score

        for col in CENTER_ORDER:
            if col == tt_col or not (search_mask & COL_MASKS[col]):
                continue
            new_pos = opp
            new_mask = mask | (mask + BOTTOM_COL_MASKS[col])
            score = -self._negamax(new_pos, new_mask, moves + 1, depth - 1, -beta, -alpha)
            if score > best_score:
                best_score = score
                best_col = col
            if score > alpha:
                alpha = score
            if alpha >= beta:
                break

        if best_score <= orig_alpha:
            flag = UPPER
        elif best_score >= beta:
            flag = LOWER
        else:
            flag = EXACT

        self.tt[key] = (flag, best_score, best_col, depth)
        return best_score

    @staticmethod
    def _evaluate(pos: int, opp: int, mask: int, moves: int) -> int:
        """Fast bitboard heuristic with threats, parity, and center control."""
        my_threats = compute_winning_position(pos, mask)
        opp_threats = compute_winning_position(opp, mask)

        score = (my_threats.bit_count() - opp_threats.bit_count()) * 50

        # Parity bonus: P1 wants threats on odd rows (0, 2, 4), P2 on even (1, 3, 5)
        if (moves & 1) == 0:
            # Current player is Player 1
            score += (my_threats & ODD_ROW_MASK).bit_count() * 30
            score -= (opp_threats & EVEN_ROW_MASK).bit_count() * 30
        else:
            # Current player is Player 2
            score += (my_threats & EVEN_ROW_MASK).bit_count() * 30
            score -= (opp_threats & ODD_ROW_MASK).bit_count() * 30

        # Positional center control
        score += (
            (pos & CENTER_COL_MASK).bit_count()
            - (opp & CENTER_COL_MASK).bit_count()
        ) * 8
        score += (
            (pos & NEAR_CENTER_MASK).bit_count()
            - (opp & NEAR_CENTER_MASK).bit_count()
        ) * 4
        score += (
            (pos & OUTER_CENTER_MASK).bit_count()
            - (opp & OUTER_CENTER_MASK).bit_count()
        ) * 2

        return score
