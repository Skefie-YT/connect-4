/* Web Worker running the Python bitboard Connect 4 AI via Pyodide */
importScripts("https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.js");

let pyodideInstance = null;
let initPromise = null;

async function ensureReady(baseUrl) {
  if (pyodideInstance) return pyodideInstance;
  if (!initPromise) {
    initPromise = (async () => {
      const pyodide = await loadPyodide();
      pyodide.FS.mkdirTree("/app/engine");

      const files = ["engine/__init__.py", "engine/bitboard.py", "engine/ai.py"];
      for (const file of files) {
        const resp = await fetch(`${baseUrl}${file}`);
        if (!resp.ok) {
          throw new Error(`Failed to load ${file} (${resp.status})`);
        }
        const text = await resp.text();
        pyodide.FS.writeFile(`/app/${file}`, text);
      }

      await pyodide.runPythonAsync(`
import json
import sys
sys.path.insert(0, "/app")
from engine import Bitboard, Connect4AI, HEIGHT, WIDTH
from engine.bitboard import has_won

_ai = Connect4AI()

def compute_ai_move_json(payload_json):
    payload = json.loads(payload_json)
    grid = payload["board"]
    ai_player = int(payload["ai_player"])
    difficulty = str(payload.get("difficulty", "unbeatable")).lower()

    human_player = 2 if ai_player == 1 else 1
    board = Bitboard.from_grid(grid, current_player=ai_player)

    human_pos = board.position ^ board.mask
    if has_won(human_pos):
        return json.dumps({
            "col": None,
            "row": None,
            "winner": human_player,
            "winning_line": board.winning_line(human_pos),
            "is_draw": False,
        })

    if board.moves >= WIDTH * HEIGHT:
        return json.dumps({
            "col": None,
            "row": None,
            "winner": None,
            "winning_line": None,
            "is_draw": True,
        })

    result = _ai.choose_move(board, difficulty=difficulty)
    col = result.col
    row = -1
    for r in range(HEIGHT - 1, -1, -1):
        if grid[r][col] == 0:
            row = r
            break

    grid[row][col] = ai_player
    after_board = Bitboard.from_grid(grid, current_player=human_player)
    ai_pos = after_board.position ^ after_board.mask

    winner = None
    winning_line = None
    is_draw = False
    if has_won(ai_pos):
        winner = ai_player
        winning_line = after_board.winning_line(ai_pos)
    elif after_board.moves >= WIDTH * HEIGHT:
        is_draw = True

    return json.dumps({
        "col": col,
        "row": row,
        "winner": winner,
        "winning_line": winning_line,
        "is_draw": is_draw,
        "stats": {
            "depth": result.depth,
            "nodes": result.nodes,
            "elapsed_ms": round(result.elapsed_ms, 1),
            "score": result.score,
        },
    })
      `);
      pyodideInstance = pyodide;
      return pyodide;
    })();
  }
  return initPromise;
}

self.onmessage = async (event) => {
  const { id, type, baseUrl, payload } = event.data;
  try {
    if (type === "init") {
      await ensureReady(baseUrl);
      self.postMessage({ id, ok: true });
      return;
    }
    if (type === "move") {
      const pyodide = await ensureReady(baseUrl);
      const fn = pyodide.globals.get("compute_ai_move_json");
      const resultJson = fn(JSON.stringify(payload));
      self.postMessage({ id, ok: true, data: JSON.parse(resultJson) });
    }
  } catch (err) {
    self.postMessage({ id, ok: false, error: err.message || String(err) });
  }
};
