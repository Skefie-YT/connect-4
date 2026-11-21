# Connect 4 — Grandmaster AI

A web-based Python Connect 4 game with a nearly unbeatable bitboard AI engine.

- **Play Online (GitHub Pages):** Runs the exact Python `engine/` in your browser via Pyodide WebAssembly in a Web Worker.
- **Run Locally (Flask):** Serves the UI and runs the AI on a local Python/Flask backend.

## Features
- **64-bit Bitboard Engine** (`engine/bitboard.py`) with $O(1)$ bitwise win and threat detection.
- **Negamax + Alpha-Beta AI** (`engine/ai.py`) with iterative deepening, collision-free transposition table (`position + mask`), center-first move ordering, non-losing move pruning, and odd-even parity evaluation.
- **Difficulty Levels:** Unbeatable (default), Master, and Casual.
- **Controls:** Click any column or use keys `1`–`7` / `←` `→` + `Enter`. Supports Undo, side switching (Red 1st / Yellow 2nd), and persistent score tracking.

## Local Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open `http://localhost:5000` in your browser.

## Tests

```bash
python -m pytest -v
```
