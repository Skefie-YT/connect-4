from __future__ import annotations

WIDTH = 7
HEIGHT = 6
H1 = HEIGHT + 1  # 7 bits per column (6 rows + 1 sentinel bit)
SIZE = WIDTH * HEIGHT  # 42

# Bitmasks for board geometry
BOTTOM_MASK = sum(1 << (c * H1) for c in range(WIDTH))
BOARD_MASK = BOTTOM_MASK * ((1 << HEIGHT) - 1)
COL_MASKS = [((1 << HEIGHT) - 1) << (c * H1) for c in range(WIDTH)]
TOP_MASKS = [1 << (c * H1 + HEIGHT - 1) for c in range(WIDTH)]
BOTTOM_COL_MASKS = [1 << (c * H1) for c in range(WIDTH)]

# Center-first column exploration order
CENTER_ORDER = (3, 2, 4, 1, 5, 0, 6)

# Precompute all 69 four-in-a-row bitmasks for heuristic evaluation
WINNING_WINDOWS: list[int] = []

# Horizontal (4 per row * 6 rows = 24)
for r in range(HEIGHT):
    for c in range(WIDTH - 3):
        WINNING_WINDOWS.append(
            (1 << (c * H1 + r))
            | (1 << ((c + 1) * H1 + r))
            | (1 << ((c + 2) * H1 + r))
            | (1 << ((c + 3) * H1 + r))
        )

# Vertical (3 per col * 7 cols = 21)
for c in range(WIDTH):
    for r in range(HEIGHT - 3):
        WINNING_WINDOWS.append(
            (1 << (c * H1 + r))
            | (1 << (c * H1 + r + 1))
            | (1 << (c * H1 + r + 2))
            | (1 << (c * H1 + r + 3))
        )

# Diagonal / (4 * 3 = 12)
for c in range(WIDTH - 3):
    for r in range(HEIGHT - 3):
        WINNING_WINDOWS.append(
            (1 << (c * H1 + r))
            | (1 << ((c + 1) * H1 + r + 1))
            | (1 << ((c + 2) * H1 + r + 2))
            | (1 << ((c + 3) * H1 + r + 3))
        )

# Diagonal \ (4 * 3 = 12)
for c in range(WIDTH - 3):
    for r in range(3, HEIGHT):
        WINNING_WINDOWS.append(
            (1 << (c * H1 + r))
            | (1 << ((c + 1) * H1 + r - 1))
            | (1 << ((c + 2) * H1 + r - 2))
            | (1 << ((c + 3) * H1 + r - 3))
        )


def has_won(pos: int) -> bool:
    """Return True if the bitboard `pos` contains 4 in a row."""
    # Horizontal
    m = pos & (pos >> H1)
    if m & (m >> (2 * H1)):
        return True
    # Diagonal \
    m = pos & (pos >> (H1 - 1))
    if m & (m >> (2 * (H1 - 1))):
        return True
    # Diagonal /
    m = pos & (pos >> (H1 + 1))
    if m & (m >> (2 * (H1 + 1))):
        return True
    # Vertical
    m = pos & (pos >> 1)
    if m & (m >> 2):
        return True
    return False


def compute_winning_position(pos: int, mask: int) -> int:
    """Return a bitmask of all empty cells that complete 4-in-a-row for `pos`."""
    # Vertical
    r = (pos << 1) & (pos << 2) & (pos << 3)

    # Horizontal
    p = (pos << H1) & (pos << (2 * H1))
    r |= p & (pos << (3 * H1))
    r |= p & (pos >> H1)
    p = (pos >> H1) & (pos >> (2 * H1))
    r |= p & (pos << H1)
    r |= p & (pos >> (3 * H1))

    # Diagonal \
    d = H1 - 1
    p = (pos << d) & (pos << (2 * d))
    r |= p & (pos << (3 * d))
    r |= p & (pos >> d)
    p = (pos >> d) & (pos >> (2 * d))
    r |= p & (pos << d)
    r |= p & (pos >> (3 * d))

    # Diagonal /
    d = H1 + 1
    p = (pos << d) & (pos << (2 * d))
    r |= p & (pos << (3 * d))
    r |= p & (pos >> d)
    p = (pos >> d) & (pos >> (2 * d))
    r |= p & (pos << d)
    r |= p & (pos >> (3 * d))

    return r & (BOARD_MASK ^ mask)


class Bitboard:
    """Immutable-style 64-bit bitboard representation of Connect 4."""

    __slots__ = ("position", "mask", "moves")

    def __init__(self, position: int = 0, mask: int = 0, moves: int = 0) -> None:
        self.position = position
        self.mask = mask
        self.moves = moves

    @classmethod
    def from_grid(cls, grid: list[list[int]], current_player: int) -> Bitboard:
        """Build a Bitboard from a 6x7 row-major grid (row 0 = top, row 5 = bottom).

        Cell values: 0 = empty, 1 = player 1, 2 = player 2.
        """
        position = 0
        mask = 0
        moves = 0
        for c in range(WIDTH):
            for r_from_bottom in range(HEIGHT):
                grid_row = HEIGHT - 1 - r_from_bottom
                val = grid[grid_row][c]
                if val != 0:
                    bit = 1 << (c * H1 + r_from_bottom)
                    mask |= bit
                    moves += 1
                    if val == current_player:
                        position |= bit
        return cls(position=position, mask=mask, moves=moves)

    def can_play(self, col: int) -> bool:
        return (self.mask & TOP_MASKS[col]) == 0

    def play_col(self, col: int) -> Bitboard:
        new_pos = self.position ^ self.mask
        new_mask = self.mask | (self.mask + BOTTOM_COL_MASKS[col])
        return Bitboard(new_pos, new_mask, self.moves + 1)

    def is_winning_move(self, col: int) -> bool:
        pos = self.position | ((self.mask + BOTTOM_COL_MASKS[col]) & COL_MASKS[col])
        return has_won(pos)

    def possible_mask(self) -> int:
        return (self.mask + BOTTOM_MASK) & BOARD_MASK

    def key(self) -> int:
        """Unique 49-bit integer key for the current board position."""
        return self.position + self.mask

    def winning_line(self, player_pos: int) -> list[tuple[int, int]] | None:
        """Return list of (grid_row, col) for a 4-in-a-row in `player_pos`, if any."""
        if not has_won(player_pos):
            return None
        for window in WINNING_WINDOWS:
            if (player_pos & window) == window:
                coords: list[tuple[int, int]] = []
                for c in range(WIDTH):
                    for r_from_bottom in range(HEIGHT):
                        if window & (1 << (c * H1 + r_from_bottom)):
                            coords.append((HEIGHT - 1 - r_from_bottom, c))
                return coords
        return None
