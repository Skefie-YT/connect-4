(() => {
  const ROWS = 6;
  const COLS = 7;

  const boardGridEl = document.getElementById("board-grid");
  const previewSlots = Array.from(document.querySelectorAll(".preview-slot"));
  const difficultySelect = document.getElementById("difficulty-select");
  const sideSelect = document.getElementById("side-select");
  const turnDotEl = document.getElementById("turn-dot");
  const statusTextEl = document.getElementById("status-text");
  const telemetryEl = document.getElementById("engine-telemetry");
  const undoBtn = document.getElementById("undo-btn");
  const newGameBtn = document.getElementById("new-game-btn");
  const scoreHumanEl = document.getElementById("score-human");
  const scoreDrawsEl = document.getElementById("score-draws");
  const scoreAiEl = document.getElementById("score-ai");
  const humanScoreLabelEl = document.getElementById("human-score-label");
  const aiScoreLabelEl = document.getElementById("ai-score-label");

  const STORAGE_KEY = "connect4_ai_scores_v1";

  let board = createEmptyBoard();
  let humanPlayer = 1; // 1 = Red (first), 2 = Yellow (second)
  let aiPlayer = 2;
  let currentTurn = 1;
  let gameOver = false;
  let isThinking = false;
  let activeCol = 3;
  let gameId = 0;
  let history = [];
  let scores = loadScores();

  function createEmptyBoard() {
    return Array.from({ length: ROWS }, () => Array(COLS).fill(0));
  }

  function cloneBoard(b) {
    return b.map((row) => row.slice());
  }

  function loadScores() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        return {
          human: Number(parsed.human) || 0,
          draws: Number(parsed.draws) || 0,
          ai: Number(parsed.ai) || 0,
        };
      }
    } catch {
      // Ignore storage errors
    }
    return { human: 0, draws: 0, ai: 0 };
  }

  function saveScores() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(scores));
    } catch {
      // Ignore storage errors
    }
  }

  function renderScores() {
    scoreHumanEl.textContent = String(scores.human);
    scoreDrawsEl.textContent = String(scores.draws);
    scoreAiEl.textContent = String(scores.ai);
    const humanColor = humanPlayer === 1 ? "Red" : "Yellow";
    const aiColor = aiPlayer === 1 ? "Red" : "Yellow";
    humanScoreLabelEl.textContent = `You (${humanColor})`;
    aiScoreLabelEl.textContent = `AI (${aiColor})`;
  }

  function buildGridDOM() {
    boardGridEl.innerHTML = "";
    for (let r = 0; r < ROWS; r++) {
      for (let c = 0; c < COLS; c++) {
        const cell = document.createElement("div");
        cell.className = "cell";
        cell.dataset.row = String(r);
        cell.dataset.col = String(c);
        cell.setAttribute("role", "gridcell");
        cell.setAttribute("aria-label", `Row ${r + 1}, Column ${c + 1}`);

        cell.addEventListener("mouseenter", () => {
          setHoveredColumn(c);
        });
        cell.addEventListener("click", () => {
          handleHumanMove(c);
        });

        boardGridEl.appendChild(cell);
      }
    }

    boardGridEl.addEventListener("mouseleave", () => {
      clearColumnHover();
    });
  }

  function getCellEl(row, col) {
    return boardGridEl.children[row * COLS + col];
  }

  function colorClass(player) {
    return player === 1 ? "red" : "yellow";
  }

  function getDropRow(col) {
    for (let r = ROWS - 1; r >= 0; r--) {
      if (board[r][col] === 0) return r;
    }
    return -1;
  }

  function setHoveredColumn(col) {
    activeCol = col;
    for (let r = 0; r < ROWS; r++) {
      for (let c = 0; c < COLS; c++) {
        getCellEl(r, c).classList.toggle("col-hover", c === col && !gameOver && !isThinking);
      }
    }
    updatePreviewRail();
  }

  function clearColumnHover() {
    for (let r = 0; r < ROWS; r++) {
      for (let c = 0; c < COLS; c++) {
        getCellEl(r, c).classList.remove("col-hover");
      }
    }
    previewSlots.forEach((slot) => slot.classList.remove("active"));
  }

  function updatePreviewRail() {
    const canDrop = !gameOver && !isThinking && currentTurn === humanPlayer && getDropRow(activeCol) !== -1;
    previewSlots.forEach((slot, idx) => {
      const disc = slot.querySelector(".preview-disc");
      disc.className = `preview-disc ${colorClass(humanPlayer)}`;
      slot.classList.toggle("active", canDrop && idx === activeCol);
    });
  }

  function placeDiscDOM(row, col, player, animate = true) {
    const cell = getCellEl(row, col);
    cell.innerHTML = "";
    const disc = document.createElement("div");
    disc.className = `disc ${colorClass(player)}`;
    if (animate) {
      const dropRows = row + 1.2;
      disc.style.setProperty("--drop-start", `${-dropRows * 112}%`);
      disc.style.setProperty("--drop-duration", `${180 + row * 38}ms`);
      disc.classList.add("dropping");
    }
    cell.appendChild(disc);
  }

  function redrawBoard() {
    for (let r = 0; r < ROWS; r++) {
      for (let c = 0; c < COLS; c++) {
        const cell = getCellEl(r, c);
        cell.innerHTML = "";
        cell.classList.toggle("disabled", gameOver || isThinking);
        if (board[r][c] !== 0) {
          placeDiscDOM(r, c, board[r][c], false);
        }
      }
    }
  }

  function highlightWinningLine(winningLine) {
    if (!winningLine) return;
    const winSet = new Set(winningLine.map(([r, c]) => `${r},${c}`));
    for (let r = 0; r < ROWS; r++) {
      for (let c = 0; c < COLS; c++) {
        const disc = getCellEl(r, c).querySelector(".disc");
        if (!disc) continue;
        if (winSet.has(`${r},${c}`)) {
          disc.classList.add("winner");
        } else {
          disc.classList.add("dimmed");
        }
      }
    }
  }

  function setStatus(text, dotColor, thinking = false) {
    statusTextEl.textContent = text;
    turnDotEl.className = `turn-dot ${dotColor}${thinking ? " thinking" : ""}`;
  }

  function updateUndoButton() {
    undoBtn.disabled = isThinking || history.length === 0;
  }

  function formatNodes(n) {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
    return String(n);
  }

  async function handleHumanMove(col) {
    if (gameOver || isThinking || currentTurn !== humanPlayer) return;
    const row = getDropRow(col);
    if (row === -1) return;

    // Save snapshot before human + AI turn for Undo
    history.push(cloneBoard(board));
    updateUndoButton();

    board[row][col] = humanPlayer;
    placeDiscDOM(row, col, humanPlayer, true);
    currentTurn = aiPlayer;
    updatePreviewRail();

    await requestAIMove();
  }

  // Engine backend: Flask /api/move when running locally, Pyodide Web Worker on static hosts (GitHub Pages / custom domain)
  const isLocalHost = ["localhost", "127.0.0.1", ""].includes(window.location.hostname);
  let useWorker = !isLocalHost;
  let worker = null;
  let workerMsgId = 0;
  const workerPending = new Map();

  function getBaseUrl() {
    const url = new URL(window.location.href);
    let path = url.pathname;
    if (!path.endsWith("/") && !path.split("/").pop().includes(".")) {
      path += "/";
    } else if (!path.endsWith("/")) {
      path = path.substring(0, path.lastIndexOf("/") + 1);
    }
    return `${url.origin}${path}`;
  }

  function ensureWorker() {
    if (!worker) {
      const baseUrl = getBaseUrl();
      worker = new Worker(`${baseUrl}static/js/ai-worker.js`);
      worker.onmessage = (event) => {
        const { id, ok, data, error } = event.data;
        const pending = workerPending.get(id);
        if (!pending) return;
        workerPending.delete(id);
        if (ok) pending.resolve(data);
        else pending.reject(new Error(error));
      };
      worker.onerror = (err) => {
        for (const [, pending] of workerPending) {
          pending.reject(new Error(err.message || "AI Worker error"));
        }
        workerPending.clear();
      };
    }
    return worker;
  }

  function callWorker(type, payload = null) {
    return new Promise((resolve, reject) => {
      const w = ensureWorker();
      const id = ++workerMsgId;
      workerPending.set(id, { resolve, reject });
      w.postMessage({ id, type, baseUrl: getBaseUrl(), payload });
    });
  }

  async function fetchAIMove(payload) {
    if (!useWorker) {
      try {
        const response = await fetch("/api/move", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (response.status === 404 || response.status === 405) {
          useWorker = true;
        } else if (!response.ok) {
          throw new Error(`Server error (${response.status})`);
        } else {
          return await response.json();
        }
      } catch (err) {
        if (err instanceof TypeError) {
          useWorker = true;
        } else {
          throw err;
        }
      }
    }

    telemetryEl.textContent = "Running Python AI (WASM)…";
    return await callWorker("move", payload);
  }

  async function requestAIMove() {
    const thisGameId = gameId;
    isThinking = true;
    setStatus(
      useWorker ? "Python AI (WASM) is calculating…" : "AI is calculating…",
      colorClass(aiPlayer),
      true
    );
    updatePreviewRail();
    updateUndoButton();

    try {
      const data = await fetchAIMove({
        board,
        ai_player: aiPlayer,
        difficulty: difficultySelect.value,
      });
      if (thisGameId !== gameId) return; // Stale response after reset/undo

      if (data.stats) {
        telemetryEl.textContent = `Depth ${data.stats.depth} · ${formatNodes(data.stats.nodes)} nodes · ${data.stats.elapsed_ms}ms`;
      }

      if (data.col !== null && data.row !== null) {
        board[data.row][data.col] = aiPlayer;
        placeDiscDOM(data.row, data.col, aiPlayer, true);
      }

      if (data.winner !== null) {
        gameOver = true;
        highlightWinningLine(data.winning_line);
        if (data.winner === humanPlayer) {
          scores.human += 1;
          setStatus("You win! Impressive!", colorClass(humanPlayer), false);
        } else {
          scores.ai += 1;
          setStatus("AI wins — four in a row!", colorClass(aiPlayer), false);
        }
        saveScores();
        renderScores();
      } else if (data.is_draw) {
        gameOver = true;
        scores.draws += 1;
        setStatus("Draw — board is full!", colorClass(humanPlayer), false);
        saveScores();
        renderScores();
      } else {
        currentTurn = humanPlayer;
        setStatus("Your turn — drop a disc", colorClass(humanPlayer), false);
      }
    } catch (err) {
      if (thisGameId !== gameId) return;
      setStatus(`Error: ${err.message}`, colorClass(humanPlayer), false);
      // Rollback last human move on error
      if (history.length > 0) {
        board = history.pop();
        redrawBoard();
        currentTurn = humanPlayer;
      }
    } finally {
      if (thisGameId === gameId) {
        isThinking = false;
        updateUndoButton();
        updatePreviewRail();
      }
    }
  }

  function startNewGame() {
    gameId += 1;
    board = createEmptyBoard();
    history = [];
    gameOver = false;
    isThinking = false;
    humanPlayer = Number(sideSelect.value);
    aiPlayer = humanPlayer === 1 ? 2 : 1;
    currentTurn = 1;

    telemetryEl.textContent = "Ready";
    redrawBoard();
    renderScores();
    updateUndoButton();

    if (currentTurn === aiPlayer) {
      requestAIMove();
    } else {
      setStatus("Your turn — drop a disc", colorClass(humanPlayer), false);
      updatePreviewRail();
    }
  }

  function handleUndo() {
    if (isThinking || history.length === 0) return;
    gameId += 1;
    board = history.pop();
    gameOver = false;
    currentTurn = humanPlayer;
    redrawBoard();
    setStatus("Your turn — move undone", colorClass(humanPlayer), false);
    updateUndoButton();
    updatePreviewRail();
  }

  // Event listeners
  newGameBtn.addEventListener("click", startNewGame);
  undoBtn.addEventListener("click", handleUndo);
  sideSelect.addEventListener("change", startNewGame);

  document.addEventListener("keydown", (e) => {
    if (e.target.tagName === "SELECT") return;
    if (e.key >= "1" && e.key <= "7") {
      const col = Number(e.key) - 1;
      setHoveredColumn(col);
      handleHumanMove(col);
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      setHoveredColumn((activeCol + COLS - 1) % COLS);
    } else if (e.key === "ArrowRight") {
      e.preventDefault();
      setHoveredColumn((activeCol + 1) % COLS);
    } else if (e.key === "Enter" || e.key === " ") {
      if (document.activeElement.tagName !== "BUTTON") {
        e.preventDefault();
        handleHumanMove(activeCol);
      }
    }
  });

  // Init
  buildGridDOM();
  if (useWorker) {
    callWorker("init").catch(() => {});
  }
  startNewGame();
})();
