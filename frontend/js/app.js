/**
 * ============================================================================
 * Solitaire Klondike - Assistant de Résolution
 * Frontend Principal (Vanilla JS)
 * ============================================================================
 */

'use strict';

/* ----------------------------------------------------------------------------
 * 1. CONSTANTS & CARD DEFINITIONS
 * ---------------------------------------------------------------------------- */

const SUITS = ['H', 'D', 'C', 'S']; // Hearts, Diamonds, Clubs, Spades
const SUIT_NAMES = {
    H: 'Cœurs',
    D: 'Carreaux',
    C: 'Trèfles',
    S: 'Piques'
};
const SUIT_SYMBOLS = {
    H: '♥',
    D: '♦',
    C: '♣',
    S: '♠'
};
const SUIT_COLORS = {
    H: 'red',
    D: 'red',
    C: 'black',
    S: 'black'
};

const VALUE_NAMES = {
    1: 'A',
    2: '2',
    3: '3',
    4: '4',
    5: '5',
    6: '6',
    7: '7',
    8: '8',
    9: '9',
    10: '10',
    11: 'J',
    12: 'Q',
    13: 'K'
};

/**
 * Returns 52 standard card identifiers: AH, 2H, ..., KD, ..., KS
 */
function getAll52Cards() {
    const deck = [];
    for (const suit of SUITS) {
        for (let val = 1; val <= 13; val++) {
            deck.push({
                value: val,
                suit: suit,
                name: `${VALUE_NAMES[val]}${suit}`
            });
        }
    }
    return deck;
}

/**
 * Parse any card input (string, object with rank/value) into standardized object:
 * { value: 1..13, suit: 'H'|'D'|'C'|'S', name: 'AH', face_up: boolean }
 */
function parseCard(cardInput) {
    if (!cardInput) return null;

    if (typeof cardInput === 'string') {
        const str = cardInput.trim().toUpperCase();
        const match = str.match(/^([1-9]|1[0-3]|[AJQK])([HDCS])$/i);
        if (!match) return null;
        const valStr = match[1];
        const suit = match[2];
        let value = 0;
        if (valStr === 'A') value = 1;
        else if (valStr === 'J') value = 11;
        else if (valStr === 'Q') value = 12;
        else if (valStr === 'K') value = 13;
        else value = parseInt(valStr, 10);

        return {
            value,
            suit,
            name: `${VALUE_NAMES[value]}${suit}`,
            face_up: true
        };
    }

    const suit = (cardInput.suit || '').toUpperCase();
    let value = cardInput.value || cardInput.rank || 0;
    if (!value && cardInput.name) {
        return parseCard(cardInput.name);
    }
    if (value < 1 || value > 13) value = 1;

    const valStr = VALUE_NAMES[value] || String(value);
    const faceUp = cardInput.face_up !== undefined ? Boolean(cardInput.face_up) :
                   (cardInput.faceUp !== undefined ? Boolean(cardInput.faceUp) : true);

    return {
        value,
        suit,
        name: cardInput.name || `${valStr}${suit}`,
        face_up: faceUp
    };
}

function getDisplayValue(value) {
    return VALUE_NAMES[value] || String(value);
}

/* ----------------------------------------------------------------------------
 * 2. APPLICATION STATE MANAGEMENT
 * ---------------------------------------------------------------------------- */

const appState = {
    screen: 'setup', // 'setup' | 'game'

    // Configuration setup state
    setup: {
        activeSlotType: 'col', // 'col' | 'stock'
        activeSlotIndex: 0,
        columnCards: Array(7).fill(null), // 7 visible cards for columns 0..6
        stockCards: Array(24).fill(null), // 24 cards for stock 0..23
    },

    // Active Game State (mirrored from backend)
    gameState: {
        columns: [[], [], [], [], [], [], []],
        foundations: { H: [], D: [], C: [], S: [] },
        stock: { count: 0, empty: true },
        waste: { top: null, count: 0 },
        is_won: false,
        foundation_count: 0,
        hidden_count: 0,
        revealed_pending: null,
    },

    // Current selection for interactive manual move
    selection: null, // { source_type: 'col'|'waste', col_index, card_index, card, card_count }
    dragSelection: null, // for drag and drop

    // Solver state & timers
    solver: {
        isRunning: false,
        status: 'Prête', // 'Prête', 'En cours...', 'Arrêtée', 'Délai atteint', 'Victoire trouvée !', 'Erreur'
        pollTimerId: null,
        stopwatchTimerId: null,
        startTime: null,
        elapsedSeconds: 0,
        statesExplored: 0,
        solutionsCount: 0,
        bestFoundation: 0,
        results: [],
    },

    // Solution Viewer Modal State
    solutionViewer: {
        isOpen: false,
        solution: null,
        steps: [],
        currentStepIndex: 0,
        isPlaying: false,
        playIntervalId: null,
    },

    // Card Reveal Modal State
    revealModal: {
        isOpen: false,
        colIndex: null,
        availableCards: [],
    },

    // Action History
    history: [],
};

/* ----------------------------------------------------------------------------
 * 3. HTTP / REST API CLIENT
 * ---------------------------------------------------------------------------- */

/**
 * Universal async fetch wrapper with robust error handling and JSON parsing
 */
async function apiCall(endpoint, method = 'GET', body = null) {
    const options = {
        method,
        headers: {
            'Accept': 'application/json',
        }
    };

    if (body !== null) {
        options.headers['Content-Type'] = 'application/json';
        options.body = JSON.stringify(body);
    }

    try {
        const response = await fetch(endpoint, options);
        let data = null;
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
            data = await response.json();
        } else {
            const text = await response.text();
            try {
                data = JSON.parse(text);
            } catch {
                data = { message: text };
            }
        }

        if (!response.ok) {
            const errorMsg = data && (data.error || data.message) ? (data.error || data.message) : `Erreur HTTP ${response.status}`;
            return { ok: false, error: errorMsg, status: response.status, data };
        }

        return { ok: true, data };
    } catch (err) {
        console.error(`API Error on ${method} ${endpoint}:`, err);
        return { ok: false, error: `Erreur de connexion au serveur : ${err.message}` };
    }
}

// API endpoint wrappers:
const api = {
    init: (visibleCards, stockCards) => apiCall('/api/init', 'POST', { visible_cards: visibleCards, stock_cards: stockCards }),
    getState: () => apiCall('/api/state', 'GET'),
    move: (moveData) => apiCall('/api/move', 'POST', moveData),
    manualMove: (moveData) => apiCall('/api/manual-move', 'POST', moveData),
    reveal: (col, cardId) => apiCall('/api/reveal', 'POST', { col, card_id: cardId }),
    startSolve: () => apiCall('/api/solve', 'POST', {}),
    getSolverStatus: () => apiCall('/api/solver-status', 'GET'),
    stopSolver: () => apiCall('/api/stop-solver', 'POST', {}),
    getResults: () => apiCall('/api/results', 'GET'),
    undo: () => apiCall('/api/undo', 'POST', {}),
    redo: () => apiCall('/api/redo', 'POST', {}),
    getHistory: () => apiCall('/api/history', 'GET'),
    getAvailableCards: () => apiCall('/api/available-cards', 'GET'),
    draw: () => apiCall('/api/draw', 'POST', {}),
    resetStock: () => apiCall('/api/reset-stock', 'POST', {}),
    confirmMove: (index, moveIdx = 0) => apiCall('/api/confirm-move', 'POST', { result_index: index, move_index: moveIdx }),
};

/* ----------------------------------------------------------------------------
 * 4. NOTIFICATIONS (TOASTS)
 * ---------------------------------------------------------------------------- */

function showToast(message, type = 'info', duration = 3500) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    const icons = {
        success: '✓',
        error: '⚠️',
        warning: '🔔',
        info: 'ℹ️'
    };
    const icon = icons[type] || 'ℹ️';

    toast.innerHTML = `<span class="toast-icon">${icon}</span><span class="toast-text">${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(50px)';
        setTimeout(() => toast.remove(), 250);
    }, duration);
}

/* ----------------------------------------------------------------------------
 * 5. CARD DOM RENDERING HELPERS
 * ---------------------------------------------------------------------------- */

/**
 * Creates a DOM element representing a Klondike card
 * @param {Object|string} card - card representation
 * @param {boolean} faceUp - whether card is face up
 * @param {boolean} clickable - whether card has cursor pointer & hover effect
 * @param {Function} onClick - optional click handler
 */
function createCardElement(cardInput, faceUp = true, clickable = false, onClick = null) {
    const card = parseCard(cardInput);
    const cardEl = document.createElement('div');
    cardEl.className = 'solitaire-card';

    if (!card || !faceUp) {
        cardEl.classList.add('card-back');
        if (clickable && onClick) {
            cardEl.classList.add('clickable');
            cardEl.addEventListener('click', onClick);
        }
        return cardEl;
    }

    cardEl.dataset.cardName = card.name;
    cardEl.dataset.value = card.value;
    cardEl.dataset.suit = card.suit;

    const colorClass = card.suit === 'H' || card.suit === 'D' ? 'suit-red' : 'suit-black';
    cardEl.classList.add(colorClass);

    const symbol = SUIT_SYMBOLS[card.suit] || card.suit;
    const displayVal = getDisplayValue(card.value);

    cardEl.innerHTML = `
        <div class="card-corner card-corner-top">
            <span class="card-val">${displayVal}</span>
            <span class="card-suit-symbol">${symbol}</span>
        </div>
        <div class="card-center">
            <span>${symbol}</span>
        </div>
        <div class="card-corner card-corner-bottom">
            <span class="card-val">${displayVal}</span>
            <span class="card-suit-symbol">${symbol}</span>
        </div>
    `;

    if (clickable) {
        cardEl.classList.add('clickable');
        if (onClick) {
            cardEl.addEventListener('click', onClick);
        }
    }

    return cardEl;
}

/**
 * Renders a standard face-down card DOM element
 */
function renderCardBack() {
    const el = document.createElement('div');
    el.className = 'solitaire-card card-back';
    return el;
}

/* ----------------------------------------------------------------------------
 * 6. SETUP SCREEN CONTROLLER
 * ---------------------------------------------------------------------------- */

/**
 * Returns set of already selected card names in setup
 */
function getAssignedSetupCards() {
    const assigned = new Set();
    appState.setup.columnCards.forEach(c => { if (c) assigned.add(c); });
    appState.setup.stockCards.forEach(c => { if (c) assigned.add(c); });
    return assigned;
}

/**
 * Populates setup slots and the 52-card picker
 */
function initSetupScreen() {
    renderSetupSlots();
    renderCardPickerGrid();
    updateSetupCounters();

    // Setup action buttons
    const btnValidate = document.getElementById('btn-validate-setup');
    if (btnValidate) {
        btnValidate.onclick = handleValidateSetup;
    }

    const btnRandom = document.getElementById('btn-random-fill');
    if (btnRandom) {
        btnRandom.onclick = handleRandomFillSetup;
    }

    const btnReset = document.getElementById('btn-reset-setup');
    if (btnReset) {
        btnReset.onclick = handleResetSetup;
    }
}

/**
 * Renders the 7 column slots and 24 stock slots in setup
 */
function renderSetupSlots() {
    const tableauContainer = document.getElementById('tableau-slots');
    const stockContainer = document.getElementById('stock-slots');

    if (tableauContainer) {
        tableauContainer.innerHTML = '';
        for (let i = 0; i < 7; i++) {
            const cardName = appState.setup.columnCards[i];
            const isActive = appState.setup.activeSlotType === 'col' && appState.setup.activeSlotIndex === i;

            const slotEl = document.createElement('div');
            slotEl.className = `setup-slot-item ${isActive ? 'active' : ''}`;
            slotEl.onclick = (e) => {
                e.stopPropagation();
                setActiveSetupSlot('col', i);
            };

            const labelEl = document.createElement('span');
            labelEl.className = 'setup-slot-label';
            labelEl.textContent = `Colonne ${i + 1}`;

            const boxEl = document.createElement('div');
            boxEl.className = 'setup-slot-box';

            if (cardName) {
                const cardEl = createCardElement(cardName, true, false);
                boxEl.appendChild(cardEl);
            } else {
                boxEl.innerHTML = `<span class="setup-slot-placeholder">+</span>`;
            }

            slotEl.appendChild(labelEl);
            slotEl.appendChild(boxEl);

            if (cardName) {
                const removeBtn = document.createElement('button');
                removeBtn.className = 'setup-slot-remove-btn';
                removeBtn.textContent = '✕';
                removeBtn.title = 'Retirer cette carte';
                removeBtn.onclick = (e) => {
                    e.stopPropagation();
                    removeCardFromSetupSlot('col', i);
                };
                slotEl.appendChild(removeBtn);
            }

            tableauContainer.appendChild(slotEl);
        }
    }

    if (stockContainer) {
        stockContainer.innerHTML = '';
        for (let i = 0; i < 24; i++) {
            const cardName = appState.setup.stockCards[i];
            const isActive = appState.setup.activeSlotType === 'stock' && appState.setup.activeSlotIndex === i;

            const slotEl = document.createElement('div');
            slotEl.className = `setup-slot-item stock-item ${isActive ? 'active' : ''}`;
            slotEl.onclick = (e) => {
                e.stopPropagation();
                setActiveSetupSlot('stock', i);
            };

            const labelEl = document.createElement('span');
            labelEl.className = 'setup-slot-label';
            labelEl.textContent = `${i + 1}`;

            const boxEl = document.createElement('div');
            boxEl.className = 'setup-slot-box';

            if (cardName) {
                const cardEl = createCardElement(cardName, true, false);
                boxEl.appendChild(cardEl);
            } else {
                boxEl.innerHTML = `<span class="setup-slot-placeholder">+</span>`;
            }

            slotEl.appendChild(labelEl);
            slotEl.appendChild(boxEl);

            if (cardName) {
                const removeBtn = document.createElement('button');
                removeBtn.className = 'setup-slot-remove-btn';
                removeBtn.textContent = '✕';
                removeBtn.title = 'Retirer cette carte';
                removeBtn.onclick = (e) => {
                    e.stopPropagation();
                    removeCardFromSetupSlot('stock', i);
                };
                slotEl.appendChild(removeBtn);
            }

            stockContainer.appendChild(slotEl);
        }
    }
}

/**
 * Sets the active slot where next chosen card will go
 */
function setActiveSetupSlot(type, index) {
    appState.setup.activeSlotType = type;
    appState.setup.activeSlotIndex = index;

    const label = document.getElementById('active-slot-label');
    if (label) {
        if (type === 'col') {
            label.textContent = `Colonne ${index + 1}`;
        } else {
            label.textContent = `Pioche #${index + 1}`;
        }
    }

    renderSetupSlots();
}

/**
 * Moves active slot to next empty slot automatically
 */
function advanceToNextEmptySlot() {
    // Check remaining column slots first
    for (let i = 0; i < 7; i++) {
        if (!appState.setup.columnCards[i]) {
            setActiveSetupSlot('col', i);
            return;
        }
    }
    // Then check stock slots
    for (let i = 0; i < 24; i++) {
        if (!appState.setup.stockCards[i]) {
            setActiveSetupSlot('stock', i);
            return;
        }
    }
}

/**
 * Assigns selected card to current active slot
 */
function assignCardToActiveSlot(cardName) {
    const assigned = getAssignedSetupCards();
    if (assigned.has(cardName)) {
        showToast(`La carte ${cardName} est déjà utilisée !`, 'warning');
        return;
    }

    const { activeSlotType, activeSlotIndex } = appState.setup;
    if (activeSlotType === 'col') {
        appState.setup.columnCards[activeSlotIndex] = cardName;
    } else {
        appState.setup.stockCards[activeSlotIndex] = cardName;
    }

    renderSetupSlots();
    renderCardPickerGrid();
    updateSetupCounters();
    advanceToNextEmptySlot();
}

/**
 * Removes card from a slot
 */
function removeCardFromSetupSlot(type, index) {
    if (type === 'col') {
        appState.setup.columnCards[index] = null;
    } else {
        appState.setup.stockCards[index] = null;
    }
    setActiveSetupSlot(type, index);
    renderSetupSlots();
    renderCardPickerGrid();
    updateSetupCounters();
}

/**
 * Renders the 52-card picker grid (4 suits x 13 values)
 */
function renderCardPickerGrid() {
    const gridContainer = document.getElementById('card-picker-grid');
    if (!gridContainer) return;

    const assigned = getAssignedSetupCards();
    gridContainer.innerHTML = '';

    for (const suit of SUITS) {
        const rowEl = document.createElement('div');
        rowEl.className = 'picker-suit-row';

        const suitIndicator = document.createElement('div');
        suitIndicator.className = `picker-suit-indicator ${SUIT_COLORS[suit]}`;
        suitIndicator.textContent = SUIT_SYMBOLS[suit];
        rowEl.appendChild(suitIndicator);

        const cardsRow = document.createElement('div');
        cardsRow.className = 'picker-cards-row';

        for (let val = 1; val <= 13; val++) {
            const cardObj = { value: val, suit, name: `${VALUE_NAMES[val]}${suit}` };
            const isAssigned = assigned.has(cardObj.name);

            const wrapper = document.createElement('div');
            wrapper.className = `picker-card-wrapper ${isAssigned ? 'disabled' : ''}`;
            wrapper.title = `${VALUE_NAMES[val]} de ${SUIT_NAMES[suit]}${isAssigned ? ' (Déjà choisie)' : ''}`;

            const cardEl = createCardElement(cardObj, true, !isAssigned);
            wrapper.appendChild(cardEl);

            if (!isAssigned) {
                wrapper.onclick = () => assignCardToActiveSlot(cardObj.name);
            }

            cardsRow.appendChild(wrapper);
        }

        rowEl.appendChild(cardsRow);
        gridContainer.appendChild(rowEl);
    }
}

/**
 * Updates slot counter indicators
 */
function updateSetupCounters() {
    const colCount = appState.setup.columnCards.filter(Boolean).length;
    const stockCount = appState.setup.stockCards.filter(Boolean).length;

    const colCounterEl = document.getElementById('tableau-slot-counter');
    if (colCounterEl) colCounterEl.textContent = `${colCount} / 7 renseignées`;

    const stockCounterEl = document.getElementById('stock-slot-counter');
    if (stockCounterEl) stockCounterEl.textContent = `${stockCount} / 24 renseignées`;
}

/**
 * Generates a valid random deal (31 distinct cards)
 */
function handleRandomFillSetup() {
    const all = getAll52Cards().map(c => c.name);
    // Fisher-Yates shuffle
    for (let i = all.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [all[i], all[j]] = [all[j], all[i]];
    }

    appState.setup.columnCards = all.slice(0, 7);
    appState.setup.stockCards = all.slice(7, 31);

    renderSetupSlots();
    renderCardPickerGrid();
    updateSetupCounters();
    clearSetupError();
    showToast('Donne aléatoire générée avec 31 cartes uniques !', 'success');
}

/**
 * Clears all setup slots
 */
function handleResetSetup() {
    appState.setup.columnCards = Array(7).fill(null);
    appState.setup.stockCards = Array(24).fill(null);
    setActiveSetupSlot('col', 0);
    renderSetupSlots();
    renderCardPickerGrid();
    updateSetupCounters();
    clearSetupError();
    showToast('Configuration réinitialisée.', 'info');
}

function showSetupError(message) {
    const errorEl = document.getElementById('setup-error');
    if (errorEl) {
        errorEl.textContent = message;
        errorEl.classList.remove('hidden');
    }
}

function clearSetupError() {
    const errorEl = document.getElementById('setup-error');
    if (errorEl) {
        errorEl.textContent = '';
        errorEl.classList.add('hidden');
    }
}

/**
 * Validates setup and sends request to POST /api/init
 */
async function handleValidateSetup() {
    clearSetupError();

    const missingCols = [];
    for (let i = 0; i < 7; i++) {
        if (!appState.setup.columnCards[i]) {
            missingCols.push(i + 1);
        }
    }

    const missingStock = [];
    for (let i = 0; i < 24; i++) {
        if (!appState.setup.stockCards[i]) {
            missingStock.push(i + 1);
        }
    }

    if (missingCols.length > 0) {
        showSetupError(`Veuillez renseigner toutes les colonnes du tableau. Manquante(s) : Colonne(s) ${missingCols.join(', ')}.`);
        return;
    }

    if (missingStock.length > 0) {
        showSetupError(`Veuillez renseigner les 24 cartes de la pioche. Manquante(s) : Emplacement(s) ${missingStock.join(', ')}.`);
        return;
    }

    // Verify uniqueness
    const assigned = new Set();
    const all = [...appState.setup.columnCards, ...appState.setup.stockCards];
    for (const card of all) {
        if (assigned.has(card)) {
            showSetupError(`Carte en double détectée : ${card}. Toutes les cartes doivent être uniques.`);
            return;
        }
        assigned.add(card);
    }

    const btn = document.getElementById('btn-validate-setup');
    if (btn) btn.disabled = true;

    try {
        const res = await api.init(appState.setup.columnCards, appState.setup.stockCards);
        if (!res.ok) {
            showSetupError(`Erreur d'initialisation : ${res.error}`);
            return;
        }

        showToast('Partie initialisée avec succès !', 'success');
        switchToScreen('game');
        await loadGameState();
        await loadHistory();
    } catch (err) {
        showSetupError(`Erreur inattendue : ${err.message}`);
    } finally {
        if (btn) btn.disabled = false;
    }
}

/* ----------------------------------------------------------------------------
 * 7. SCREEN SWITCHER
 * ---------------------------------------------------------------------------- */

function switchToScreen(screenName) {
    appState.screen = screenName;
    const setupScreen = document.getElementById('setup-screen');
    const gameScreen = document.getElementById('game-screen');
    const btnReconf = document.getElementById('btn-header-reconfigure');
    const btnNewGame = document.getElementById('btn-header-new-game');

    if (screenName === 'game') {
        setupScreen.classList.add('hidden');
        gameScreen.classList.remove('hidden');
        if (btnReconf) btnReconf.classList.remove('hidden');
        if (btnNewGame) btnNewGame.classList.remove('hidden');
    } else {
        gameScreen.classList.add('hidden');
        setupScreen.classList.remove('hidden');
        if (btnReconf) btnReconf.classList.add('hidden');
        if (btnNewGame) btnNewGame.classList.add('hidden');
    }
}

/* ----------------------------------------------------------------------------
 * 8. GAME BOARD RENDERING & INTERACTION
 * ---------------------------------------------------------------------------- */

/**
 * Loads current game state from backend and triggers render
 */
async function loadGameState() {
    const res = await api.getState();
    if (!res.ok) {
        showToast(`Impossible de charger l'état du jeu : ${res.error}`, 'error');
        return;
    }

    appState.gameState = res.data;
    renderGameBoard(appState.gameState);

    // Check for win condition
    if (appState.gameState.is_won) {
        showVictoryModal(appState.gameState);
    }

    // Check for pending revealed card
    const pending = appState.gameState.pending_reveal || appState.gameState.revealed_pending;
    if (pending) {
        const pCol = typeof pending === 'object' ? pending.col : pending;
        if (pCol !== undefined && pCol !== null) {
            showRevealDialog(pCol);
        }
    }
}

/**
 * Renders the entire Solitaire game board based on state
 */
function renderGameBoard(state) {
    if (!state) return;

    // 1. Stock Pile
    renderStockPile(state.stock);

    // 2. Waste Pile
    renderWastePile(state.waste);

    // 3. Foundations
    renderFoundations(state.foundations);

    // 4. Tableau Columns
    renderTableauColumns(state.columns);

    // 5. Bottom Stats
    const foundationsCount = state.foundation_count !== undefined ? state.foundation_count : calculateFoundationCount(state.foundations);
    const hiddenCount = state.hidden_count !== undefined ? state.hidden_count : calculateHiddenCount(state.columns);

    const statFoundationsEl = document.getElementById('stat-foundations-count');
    if (statFoundationsEl) statFoundationsEl.textContent = `${foundationsCount} / 52`;

    const statHiddenEl = document.getElementById('stat-hidden-count');
    if (statHiddenEl) statHiddenEl.textContent = `${hiddenCount}`;
}

function calculateFoundationCount(foundations) {
    if (!foundations) return 0;
    let total = 0;
    for (const s of SUITS) {
        if (Array.isArray(foundations[s])) {
            total += foundations[s].length;
        }
    }
    return total;
}

function calculateHiddenCount(columns) {
    if (!columns || !Array.isArray(columns)) return 0;
    let total = 0;
    for (const col of columns) {
        const cards = Array.isArray(col) ? col : (col.cards || []);
        for (const card of cards) {
            const parsed = parseCard(card);
            if (parsed && !parsed.face_up) total++;
        }
    }
    return total;
}

/**
 * Renders the Stock pile
 */
function renderStockPile(stockState) {
    const stockEl = document.getElementById('stock-pile');
    const countEl = document.getElementById('stock-count');
    if (!stockEl) return;

    stockEl.innerHTML = '';
    const count = stockState ? (stockState.count !== undefined ? stockState.count : (Array.isArray(stockState) ? stockState.length : 0)) : 0;
    const isEmpty = stockState ? (stockState.empty !== undefined ? stockState.empty : count === 0) : true;

    if (countEl) countEl.textContent = count;

    if (!isEmpty && count > 0) {
        const cardBack = renderCardBack();
        stockEl.appendChild(cardBack);
        stockEl.title = 'Cliquer pour piocher une carte';
        stockEl.onclick = handleStockDraw;
    } else {
        stockEl.innerHTML = `<span class="stock-empty-indicator" title="Pioche vide - cliquez pour recycler la défausse">↺</span>`;
        stockEl.onclick = handleStockReset;
    }
}

/**
 * Renders the Waste pile
 */
function renderWastePile(wasteState) {
    const wasteEl = document.getElementById('waste-pile');
    const countEl = document.getElementById('waste-count');
    if (!wasteEl) return;

    wasteEl.innerHTML = '';
    let topCard = null;
    let count = 0;

    if (wasteState) {
        if (wasteState.top) {
            topCard = wasteState.top;
            count = wasteState.count || 1;
        } else if (Array.isArray(wasteState)) {
            count = wasteState.length;
            topCard = count > 0 ? wasteState[count - 1] : null;
        }
    }

    if (countEl) countEl.textContent = count;

    if (topCard) {
        const cardObj = parseCard(topCard);
        const isSelected = appState.selection && appState.selection.source_type === 'waste';
        const cardEl = createCardElement(cardObj, true, true, () => handleWasteCardClick(cardObj));
        if (isSelected) {
            cardEl.classList.add('selected');
        }

        // Enable Drag & Drop
        cardEl.draggable = true;
        cardEl.addEventListener('dragstart', (e) => handleDragStart(e, {
            source_type: 'waste',
            card: cardObj,
            card_count: 1
        }));
        cardEl.addEventListener('dragend', handleDragEnd);

        // Double click: auto-move to foundation (or legal tableau column)
        cardEl.addEventListener('dblclick', (e) => {
            e.stopPropagation();
            handleCardDoubleClick(cardObj, 'waste');
        });

        wasteEl.appendChild(cardEl);
        wasteEl.title = 'Défausse : glissez-déposez, double-cliquez ou cliquez pour déplacer';
    } else {
        wasteEl.title = 'Défausse vide';
    }
}

/**
 * Renders the 4 Foundation piles (H, D, C, S)
 */
function renderFoundations(foundations) {
    for (const suit of SUITS) {
        const pileEl = document.getElementById(`foundation-${suit}`);
        if (!pileEl) continue;

        pileEl.innerHTML = '';
        const cards = foundations ? (Array.isArray(foundations[suit]) ? foundations[suit] : []) : [];
        const topCard = cards.length > 0 ? cards[cards.length - 1] : null;

        if (topCard) {
            const cardObj = parseCard(topCard);
            const cardEl = createCardElement(cardObj, true, false, null);
            cardEl.title = `${cardObj.display_name} en fondation (verrouillée définitivement)`;
            pileEl.appendChild(cardEl);
        } else {
            const symbol = SUIT_SYMBOLS[suit];
            const colorClass = SUIT_COLORS[suit];
            pileEl.innerHTML = `<span class="foundation-watermark ${colorClass}">${symbol}</span>`;
            pileEl.title = `Fondation ${SUIT_NAMES[suit]} vide (accepte l'As)`;
        }

        // Click on foundation
        pileEl.onclick = () => handleFoundationClick(suit, topCard);

        // Drag & drop target
        pileEl.ondragover = (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            pileEl.classList.add('drop-target-active');
        };
        pileEl.ondragleave = () => {
            pileEl.classList.remove('drop-target-active');
        };
        pileEl.ondrop = async (e) => {
            e.preventDefault();
            pileEl.classList.remove('drop-target-active');
            if (appState.dragSelection) {
                await executeManualMoveToFoundation(suit, appState.dragSelection);
                appState.dragSelection = null;
            }
        };
    }
}

/**
 * Renders 7 Tableau Columns
 */
function renderTableauColumns(columns) {
    const container = document.getElementById('tableau-columns');
    if (!container) return;

    for (let colIdx = 0; colIdx < 7; colIdx++) {
        const colEl = document.getElementById(`col-${colIdx}`);
        if (!colEl) continue;

        const cardsContainer = colEl.querySelector('.col-cards');
        if (!cardsContainer) continue;

        cardsContainer.innerHTML = '';
        const rawCol = columns ? columns[colIdx] : null;
        const cards = Array.isArray(rawCol) ? rawCol : (rawCol && rawCol.cards ? rawCol.cards : []);

        // Drag & Drop target on the column container
        colEl.ondragover = (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            colEl.classList.add('drop-target-active');
        };
        colEl.ondragleave = (e) => {
            if (!colEl.contains(e.relatedTarget)) {
                colEl.classList.remove('drop-target-active');
            }
        };
        colEl.ondrop = async (e) => {
            e.preventDefault();
            colEl.classList.remove('drop-target-active');
            if (appState.dragSelection) {
                await executeManualMoveToColumn(colIdx, appState.dragSelection);
                appState.dragSelection = null;
            }
        };

        // Update column header with purple reveal option for columns 2 to 7 (colIdx >= 1)
        const headerEl = colEl.querySelector('.col-header');
        const hasHiddenCards = cards.some(c => c && c.face_up === false);
        const topCardIsHidden = cards.length > 0 && cards[cards.length - 1].face_up === false;
        const pendingReveal = appState.gameState && appState.gameState.pending_reveal;
        const isThisColPending = pendingReveal && (pendingReveal.col === colIdx || pendingReveal === colIdx);

        if (headerEl) {
            headerEl.innerHTML = '';
            const numSpan = document.createElement('span');
            numSpan.className = 'col-num';
            numSpan.textContent = colIdx + 1;
            headerEl.appendChild(numSpan);

            // Columns 2 to 7 (indices 1 to 6) get the purple reveal button
            if (colIdx >= 1 && (hasHiddenCards || isThisColPending || topCardIsHidden)) {
                const revealBtn = document.createElement('button');
                revealBtn.className = `col-reveal-btn ${isThisColPending || topCardIsHidden ? 'pending-action' : ''}`;
                revealBtn.innerHTML = isThisColPending || topCardIsHidden ? '👁 Révéler !' : '👁 Révéler';
                revealBtn.title = `Cliquer pour choisir la carte révélée en colonne ${colIdx + 1}`;
                revealBtn.onclick = (e) => {
                    e.stopPropagation();
                    showRevealDialog(colIdx);
                };
                headerEl.appendChild(revealBtn);
            }
        }

        if (!cards || cards.length === 0) {
            // Empty column slot: accepts King
            const emptySlot = document.createElement('div');
            emptySlot.className = 'col-empty-slot';
            emptySlot.textContent = 'K';
            emptySlot.title = 'Colonne vide (accepte un Roi ou une suite avec un Roi)';
            emptySlot.onclick = () => handleEmptyColumnClick(colIdx);
            cardsContainer.appendChild(emptySlot);
            cardsContainer.style.height = '84px';
            continue;
        }

        let currentTop = 0;
        cards.forEach((rawCard, cardIdx) => {
            const card = parseCard(rawCard);
            const isFaceUp = card.face_up !== false;
            const isTopCard = cardIdx === cards.length - 1;

            const wrapper = document.createElement('div');
            wrapper.className = 'tableau-card-wrapper';
            wrapper.style.top = `${currentTop}px`;
            wrapper.style.zIndex = cardIdx + 1;

            // Clickable face-up cards
            const cardEl = createCardElement(card, isFaceUp, isFaceUp, (e) => {
                e.stopPropagation();
                handleTableauCardClick(colIdx, cardIdx, card);
            });

            // If the top card of this column is face-down, allow clicking it directly to reveal!
            if (!isFaceUp && isTopCard) {
                cardEl.classList.add('card-top-hidden-revealing');
                cardEl.classList.add('clickable');
                cardEl.title = 'Carte découverte : cliquez pour identifier la carte';
                cardEl.onclick = (e) => {
                    e.stopPropagation();
                    showRevealDialog(colIdx);
                };
            }

            // Enable Drag & Drop and Double Click on face-up cards
            if (isFaceUp) {
                cardEl.draggable = true;
                const cardCount = cards.length - cardIdx;

                cardEl.addEventListener('dragstart', (e) => {
                    handleDragStart(e, {
                        source_type: 'col',
                        col_index: colIdx,
                        card_index: cardIdx,
                        card: card,
                        card_count: cardCount
                    });
                });
                cardEl.addEventListener('dragend', handleDragEnd);

                cardEl.addEventListener('dblclick', (e) => {
                    e.stopPropagation();
                    handleCardDoubleClick(card, 'col', colIdx, cardIdx, cardCount);
                });
            }

            // Highlight selected card and stack beneath it
            if (appState.selection &&
                appState.selection.source_type === 'col' &&
                appState.selection.col_index === colIdx &&
                cardIdx >= appState.selection.card_index) {
                cardEl.classList.add('selected');
            }

            wrapper.appendChild(cardEl);
            cardsContainer.appendChild(wrapper);

            // Overlap: show ~18px for face-down, ~24px for face-up
            currentTop += isFaceUp ? 24 : 18;
        });

        cardsContainer.style.height = `${Math.max(84, currentTop + 60)}px`;
    }
}

/* ----------------------------------------------------------------------------
 * 9. MANUAL MOVE SYSTEM & DRAG & DROP
 * ---------------------------------------------------------------------------- */

/**
 * Drag & Drop Start
 */
function handleDragStart(e, selection) {
    appState.dragSelection = selection;
    appState.selection = null; // Clear click selection when dragging
    if (e.target && e.target.classList) {
        e.target.classList.add('dragging');
    }
    e.dataTransfer.effectAllowed = 'move';
    try {
        e.dataTransfer.setData('text/plain', JSON.stringify({
            source_type: selection.source_type,
            col_index: selection.col_index,
            card_count: selection.card_count
        }));
    } catch (_) {}
}

/**
 * Drag & Drop End
 */
function handleDragEnd(e) {
    if (e.target && e.target.classList) {
        e.target.classList.remove('dragging');
    }
    document.querySelectorAll('.drop-target-active').forEach(el => el.classList.remove('drop-target-active'));
}

/**
 * Double-click automatic move:
 * 1. Checks if eligible for foundation (Ace or next rank of same suit)
 * 2. If not, checks if it can stack onto an available tableau column
 */
async function handleCardDoubleClick(card, sourceType, colIdx = null, cardIdx = null, cardCount = 1) {
    if (!card) return;

    // 1. First priority: Try sending to matching foundation
    let foundationPayload = {
        dest_suit: card.suit,
        card_count: 1
    };
    if (sourceType === 'col') {
        foundationPayload.move_type = 'TABLEAU_TO_FOUNDATION';
        foundationPayload.source_col = colIdx;
    } else if (sourceType === 'waste') {
        foundationPayload.move_type = 'WASTE_TO_FOUNDATION';
    }

    let res = await api.manualMove(foundationPayload);
    if (!res.ok) {
        res = await api.move(foundationPayload);
    }

    if (res.ok) {
        showToast(`Carte ${card.name} envoyée sur la fondation !`, 'success');
        appState.selection = null;
        await loadGameState();
        await loadHistory();
        if (res.data && res.data.pending_reveal) {
            showRevealDialog(res.data.pending_reveal.col);
        }
        return;
    }

    // 2. Second priority: If only 1 card or top of stack, try legal tableau columns
    if (appState.gameState && appState.gameState.columns) {
        for (let dstCol = 0; dstCol < 7; dstCol++) {
            if (sourceType === 'col' && dstCol === colIdx) continue;
            const targetTop = getColumnTopCard(dstCol);
            if (isValidTableauPlacement(card, targetTop)) {
                let tableauPayload = {
                    dest_col: dstCol,
                    card_count: cardCount
                };
                if (sourceType === 'col') {
                    tableauPayload.move_type = 'TABLEAU_TO_TABLEAU';
                    tableauPayload.source_col = colIdx;
                } else if (sourceType === 'waste') {
                    tableauPayload.move_type = 'WASTE_TO_TABLEAU';
                }

                let tRes = await api.manualMove(tableauPayload);
                if (!tRes.ok) tRes = await api.move(tableauPayload);
                if (tRes.ok) {
                    showToast(`Déplacé vers la colonne ${dstCol + 1} !`, 'success');
                    appState.selection = null;
                    await loadGameState();
                    await loadHistory();
                    if (tRes.data && tRes.data.pending_reveal) {
                        showRevealDialog(tRes.data.pending_reveal.col);
                    }
                    return;
                }
            }
        }
    }

    // If neither works, show a helpful message
    showToast(res.error || 'Aucun déplacement possible pour cette carte.', 'warning');
}

/**
 * Returns top card of a tableau column
 */
function getColumnTopCard(colIdx) {
    if (!appState.gameState || !appState.gameState.columns) return null;
    const cards = getColumnCards(colIdx);
    if (!cards || cards.length === 0) return null;
    const topStack = cards[cards.length - 1];
    return topStack && topStack.face_up !== false ? parseCard(topStack) : null;
}

/**
 * Checks if lead card can be stacked on target card
 */
function isValidTableauPlacement(leadCard, targetTopCard) {
    if (!leadCard) return false;
    // Empty column accepts King only
    if (!targetTopCard) {
        return leadCard.value === 13;
    }
    // Opposite color and descending by 1
    const isLeadRed = leadCard.suit === 'H' || leadCard.suit === 'D';
    const isTargetRed = targetTopCard.suit === 'H' || targetTopCard.suit === 'D';
    return isLeadRed !== isTargetRed && leadCard.value === targetTopCard.value - 1;
}

/**
 * Handles clicking on a Tableau card
 */
async function handleTableauCardClick(colIdx, cardIdx, card) {
    if (!card.face_up) {
        showToast('Cette carte est face cachée.', 'warning');
        return;
    }

    // 1. If no card is selected, select this card (and all cards below it in column)
    if (!appState.selection) {
        const colCards = getColumnCards(colIdx);
        const cardCount = colCards.length - cardIdx;

        appState.selection = {
            source_type: 'col',
            col_index: colIdx,
            card_index: cardIdx,
            card: card,
            card_count: cardCount
        };
        renderGameBoard(appState.gameState);
        return;
    }

    // 2. If clicking the exact same card, cancel selection
    if (appState.selection.source_type === 'col' &&
        appState.selection.col_index === colIdx &&
        appState.selection.card_index === cardIdx) {
        appState.selection = null;
        renderGameBoard(appState.gameState);
        return;
    }

    // 3. User selected a destination column!
    const destCol = colIdx;
    await executeManualMoveToColumn(destCol);
}

/**
 * Handles clicking on empty column slot
 */
async function handleEmptyColumnClick(colIdx) {
    if (!appState.selection) return;
    await executeManualMoveToColumn(colIdx);
}

/**
 * Handles clicking on Waste top card
 */
function handleWasteCardClick(wasteCard) {
    if (!appState.selection) {
        appState.selection = {
            source_type: 'waste',
            card: wasteCard,
            card_count: 1
        };
        renderGameBoard(appState.gameState);
    } else if (appState.selection.source_type === 'waste') {
        appState.selection = null;
        renderGameBoard(appState.gameState);
    } else {
        // Waste cannot be a destination
        appState.selection = null;
        renderGameBoard(appState.gameState);
    }
}

/**
 * Handles clicking on Foundation slot (destination only per absolute rule)
 */
async function handleFoundationClick(suit, topCard) {
    // If we have a selection, attempt to move to this foundation
    if (appState.selection) {
        await executeManualMoveToFoundation(suit);
        return;
    }

    // Per Klondike rules: cards placed in foundations cannot be retrieved
    if (topCard) {
        showToast('Règle absolue : une carte envoyée aux fondations ne peut plus en être retirée.', 'info');
    }
}

/**
 * Returns array of cards in a tableau column
 */
function getColumnCards(colIdx) {
    const rawCol = appState.gameState.columns[colIdx];
    return Array.isArray(rawCol) ? rawCol : (rawCol && rawCol.cards ? rawCol.cards : []);
}

/**
 * Dispatches move to column
 */
async function executeManualMoveToColumn(destCol, customSel = null) {
    const sel = customSel || appState.selection;
    if (!sel) return;

    let movePayload = {};

    if (sel.source_type === 'col') {
        if (sel.col_index === destCol) {
            appState.selection = null;
            renderGameBoard(appState.gameState);
            return;
        }
        movePayload = {
            move_type: 'TABLEAU_TO_TABLEAU',
            source_col: sel.col_index,
            dest_col: destCol,
            card_count: sel.card_count
        };
    } else if (sel.source_type === 'waste') {
        movePayload = {
            move_type: 'WASTE_TO_TABLEAU',
            dest_col: destCol,
            card_count: 1
        };
    }

    appState.selection = null;

    // Send move to backend
    let res = await api.manualMove(movePayload);
    if (!res.ok) {
        res = await api.move(movePayload);
    }

    if (!res.ok) {
        showToast(res.error || 'Coup non autorisé.', 'error');
        renderGameBoard(appState.gameState);
        return;
    }

    showToast('Coup exécuté avec succès !', 'success');
    await loadGameState();
    await loadHistory();
    if (res.data && res.data.pending_reveal) {
        showRevealDialog(res.data.pending_reveal.col);
    }
}

/**
 * Dispatches move to foundation
 */
async function executeManualMoveToFoundation(destSuit, customSel = null) {
    const sel = customSel || appState.selection;
    if (!sel) return;

    let movePayload = {};

    if (sel.source_type === 'col') {
        movePayload = {
            move_type: 'TABLEAU_TO_FOUNDATION',
            source_col: sel.col_index,
            dest_suit: destSuit,
            card_count: 1
        };
    } else if (sel.source_type === 'waste') {
        movePayload = {
            move_type: 'WASTE_TO_FOUNDATION',
            dest_suit: destSuit,
            card_count: 1
        };
    } else {
        appState.selection = null;
        renderGameBoard(appState.gameState);
        return;
    }

    appState.selection = null;

    let res = await api.manualMove(movePayload);
    if (!res.ok) {
        res = await api.move(movePayload);
    }

    if (!res.ok) {
        showToast(res.error || 'Impossible de placer cette carte sur la fondation.', 'error');
        renderGameBoard(appState.gameState);
        return;
    }

    showToast('Carte placée sur la fondation !', 'success');
    await loadGameState();
    await loadHistory();
    if (res.data && res.data.pending_reveal) {
        showRevealDialog(res.data.pending_reveal.col);
    }
}

/**
 * Stock draw action
 */
async function handleStockDraw() {
    appState.selection = null;
    const res = await api.draw();
    if (!res.ok) {
        showToast(res.error || 'Impossible de piocher.', 'error');
        return;
    }
    await loadGameState();
    await loadHistory();
}

/**
 * Stock reset action
 */
async function handleStockReset() {
    appState.selection = null;
    const res = await api.resetStock();
    if (!res.ok) {
        showToast(res.error || 'Impossible de recycler la défausse.', 'error');
        return;
    }
    showToast('Pioche recyclée depuis la défausse !', 'info');
    await loadGameState();
    await loadHistory();
}

/* ----------------------------------------------------------------------------
 * 10. CARD REVEAL DIALOG & FLOW
 * ---------------------------------------------------------------------------- */

/**
 * Shows the Card Reveal modal when a hidden card is turned up
 */
async function showRevealDialog(colIndex, availableCards = null) {
    appState.revealModal.isOpen = true;
    appState.revealModal.colIndex = colIndex;

    // Highlight the column with pulsating animation
    const colEl = document.getElementById(`col-${colIndex}`);
    if (colEl) colEl.classList.add('reveal-pulse');

    const modal = document.getElementById('reveal-modal');
    const titleEl = document.getElementById('reveal-modal-title');
    const gridEl = document.getElementById('reveal-cards-grid');

    if (titleEl) {
        titleEl.textContent = `Carte révélée en colonne ${colIndex + 1}`;
    }

    if (!availableCards) {
        const res = await api.getAvailableCards();
        if (res.ok && res.data && Array.isArray(res.data.cards)) {
            availableCards = res.data.cards;
        } else if (res.ok && Array.isArray(res.data)) {
            availableCards = res.data;
        } else if (res.ok && res.data && Array.isArray(res.data.available_cards)) {
            availableCards = res.data.available_cards;
        } else {
            // Compute available cards locally if endpoint fails
            availableCards = computeLocallyAvailableCards();
        }
    }

    appState.revealModal.availableCards = availableCards;

    if (gridEl) {
        gridEl.innerHTML = '';
        availableCards.forEach(cardInput => {
            const cardObj = parseCard(cardInput);
            const cardEl = createCardElement(cardObj, true, true, () => handleSelectRevealedCard(colIndex, cardObj.name));
            gridEl.appendChild(cardEl);
        });
    }

    const deferBtn = document.getElementById('btn-reveal-defer');
    if (deferBtn) {
        deferBtn.onclick = handleDeferReveal;
    }

    if (modal) modal.classList.remove('hidden');
}

/**
 * Sends POST /api/reveal with selected card
 */
async function handleSelectRevealedCard(colIndex, cardId) {
    const res = await api.reveal(colIndex, cardId);
    closeRevealDialog();

    if (!res.ok) {
        showToast(`Erreur lors de la révélation : ${res.error}`, 'error');
        return;
    }

    showToast(`Carte ${cardId} révélée en colonne ${colIndex + 1} !`, 'success');
    await loadGameState();
    await loadHistory();
}

/**
 * Defers card reveal
 */
function handleDeferReveal() {
    closeRevealDialog();
    showToast('Révélation de la carte reportée.', 'info');
}

/**
 * Closes the Card Reveal modal
 */
function closeRevealDialog() {
    appState.revealModal.isOpen = false;
    const colIndex = appState.revealModal.colIndex;
    if (colIndex !== null) {
        const colEl = document.getElementById(`col-${colIndex}`);
        if (colEl) colEl.classList.remove('reveal-pulse');
    }
    const modal = document.getElementById('reveal-modal');
    if (modal) modal.classList.add('hidden');
}

/**
 * Helper to compute available unrevealed cards
 */
function computeLocallyAvailableCards() {
    const all = getAll52Cards().map(c => c.name);
    const visibleCards = new Set();

    // From columns
    if (appState.gameState.columns) {
        for (const col of appState.gameState.columns) {
            const cards = Array.isArray(col) ? col : (col.cards || []);
            for (const c of cards) {
                const parsed = parseCard(c);
                if (parsed && parsed.face_up) visibleCards.add(parsed.name);
            }
        }
    }
    // From foundations
    if (appState.gameState.foundations) {
        for (const s of SUITS) {
            const arr = appState.gameState.foundations[s] || [];
            for (const c of arr) {
                const parsed = parseCard(c);
                if (parsed) visibleCards.add(parsed.name);
            }
        }
    }
    // From waste
    if (appState.gameState.waste && appState.gameState.waste.top) {
        const parsed = parseCard(appState.gameState.waste.top);
        if (parsed) visibleCards.add(parsed.name);
    }

    return all.filter(c => !visibleCards.has(c));
}

/* ----------------------------------------------------------------------------
 * 11. SOLVER CONTROLS & STATUS POLLING
 * ---------------------------------------------------------------------------- */

/**
 * Starts solver and sets up polling
 */
async function startSolver() {
    const btnStart = document.getElementById('btn-start-solver');
    const btnStop = document.getElementById('btn-stop-solver');

    appState.solver.isRunning = true;
    appState.solver.status = 'En cours...';
    appState.solver.startTime = Date.now();
    appState.solver.elapsedSeconds = 0;

    updateSolverUI();

    if (btnStart) btnStart.classList.add('hidden');
    if (btnStop) {
        btnStop.classList.remove('hidden');
        btnStop.disabled = false;
    }

    startSolverTimer();

    const res = await api.startSolve();
    if (!res.ok) {
        stopSolverSession('Erreur');
        showToast(`Impossible de lancer le solveur : ${res.error}`, 'error');
        return;
    }

    showToast('Recherche de solution démarrée...', 'info');

    // Poll status every 500ms
    if (appState.solver.pollTimerId) clearInterval(appState.solver.pollTimerId);
    appState.solver.pollTimerId = setInterval(pollSolverStatus, 500);
}

/**
 * Polls GET /api/solver-status
 */
async function pollSolverStatus() {
    if (!appState.solver.isRunning) return;

    const res = await api.getSolverStatus();
    if (!res.ok) {
        console.warn('Polling solver status warning:', res.error);
        return;
    }

    const data = res.data;
    const states = data.states_explored !== undefined ? data.states_explored : (data.statesExplored || 0);
    const solutions = data.solutions_count !== undefined ? data.solutions_count : (data.solutionsCount || (data.solutions ? data.solutions.length : 0));
    const bestScore = data.best_foundation !== undefined ? data.best_foundation : (data.bestFoundation || 0);
    const isRunning = data.is_running !== undefined ? data.is_running : (data.isRunning !== undefined ? data.isRunning : true);
    const statusText = data.status || (isRunning ? 'En cours...' : 'Terminée');

    appState.solver.statesExplored = states;
    appState.solver.solutionsCount = solutions;
    appState.solver.bestFoundation = bestScore;

    if (!isRunning || statusText === 'completed' || statusText === 'stopped' || statusText === 'timeout' || statusText === 'victory') {
        let finalStatus = 'Prête';
        if (statusText === 'victory' || solutions > 0) finalStatus = 'Victoire trouvée !';
        else if (statusText === 'timeout') finalStatus = 'Délai atteint';
        else if (statusText === 'stopped') finalStatus = 'Arrêtée';

        stopSolverSession(finalStatus);
        await fetchSolverResults();
    } else {
        appState.solver.status = 'En cours...';
        updateSolverUI();
    }
}

/**
 * Stops the solver manually
 */
async function stopSolver() {
    const btnStop = document.getElementById('btn-stop-solver');
    if (btnStop) btnStop.disabled = true;

    await api.stopSolver();
    stopSolverSession('Arrêtée');
    await fetchSolverResults();
    showToast('Recherche arrêtée par l\'utilisateur.', 'warning');
}

/**
 * Cleans up solver timers and restores buttons
 */
function stopSolverSession(finalStatus) {
    appState.solver.isRunning = false;
    appState.solver.status = finalStatus || 'Prête';

    if (appState.solver.pollTimerId) {
        clearInterval(appState.solver.pollTimerId);
        appState.solver.pollTimerId = null;
    }
    if (appState.solver.stopwatchTimerId) {
        clearInterval(appState.solver.stopwatchTimerId);
        appState.solver.stopwatchTimerId = null;
    }

    const btnStart = document.getElementById('btn-start-solver');
    const btnStop = document.getElementById('btn-stop-solver');

    if (btnStart) btnStart.classList.remove('hidden');
    if (btnStop) {
        btnStop.classList.add('hidden');
        btnStop.disabled = true;
    }

    updateSolverUI();
}

/**
 * Updates stopwatch timer
 */
function startSolverTimer() {
    if (appState.solver.stopwatchTimerId) clearInterval(appState.solver.stopwatchTimerId);

    appState.solver.stopwatchTimerId = setInterval(() => {
        if (!appState.solver.isRunning) return;
        const elapsed = (Date.now() - appState.solver.startTime) / 1000;
        appState.solver.elapsedSeconds = elapsed;
        const timeEl = document.getElementById('metric-solver-time');
        if (timeEl) timeEl.textContent = formatTime(elapsed);
    }, 100);
}

function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    const tenths = Math.floor((seconds % 1) * 10);
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}.${tenths}`;
}

/**
 * Updates UI badge, progress bar, metrics
 */
function updateSolverUI() {
    const badge = document.getElementById('solver-status-badge');
    if (badge) {
        badge.textContent = appState.solver.status;
        badge.className = 'status-badge';
        if (appState.solver.status === 'Prête') badge.classList.add('status-ready');
        else if (appState.solver.status === 'En cours...') badge.classList.add('status-running');
        else if (appState.solver.status === 'Arrêtée') badge.classList.add('status-stopped');
        else if (appState.solver.status === 'Délai atteint') badge.classList.add('status-timeout');
        else if (appState.solver.status === 'Victoire trouvée !') badge.classList.add('status-victory');
        else if (appState.solver.status === 'Erreur') badge.classList.add('status-error');
    }

    const statesEl = document.getElementById('metric-states-explored');
    if (statesEl) statesEl.textContent = Number(appState.solver.statesExplored).toLocaleString('fr-FR');

    const solutionsEl = document.getElementById('metric-solutions-count');
    if (solutionsEl) solutionsEl.textContent = appState.solver.solutionsCount;

    const bestScoreEl = document.getElementById('metric-best-score');
    if (bestScoreEl) bestScoreEl.textContent = `${appState.solver.bestFoundation} / 52`;

    const progressBar = document.getElementById('solver-progress-bar');
    if (progressBar) {
        const pct = Math.min(100, Math.round((appState.solver.bestFoundation / 52) * 100));
        progressBar.style.width = `${pct}%`;
    }
}

/**
 * Fetches and renders results from GET /api/results
 */
async function fetchSolverResults() {
    const res = await api.getResults();
    if (!res.ok) {
        showToast(`Erreur lors de la récupération des résultats : ${res.error}`, 'error');
        return;
    }

    let results = [];
    if (Array.isArray(res.data)) {
        results = res.data;
    } else if (res.data && Array.isArray(res.data.results)) {
        results = res.data.results;
    } else if (res.data && Array.isArray(res.data.solutions)) {
        results = res.data.solutions;
    }

    appState.solver.results = results;
    renderSolverResults(results);
}

/**
 * Renders the results and recommendations in sidebar
 */
function renderSolverResults(results) {
    const container = document.getElementById('solver-results-list');
    if (!container) return;

    container.innerHTML = '';

    if (!results || results.length === 0) {
        container.innerHTML = `
            <p class="results-empty-hint">
                Aucune solution trouvée dans le délai imparti. Cela ne signifie pas que la partie est impossible.
            </p>
        `;
        return;
    }

    results.forEach((sol, idx) => {
        const rank = sol.rank || (idx + 1);
        const isWin = sol.type === 'win' || sol.is_win || sol.foundation_count === 52;
        const typeLabel = isWin ? 'Solution gagnante' : 'Séquence partielle';
        const typeClass = isWin ? 'win' : 'partial';
        const moveCount = sol.move_count || (sol.steps ? sol.steps.length : (sol.moves ? sol.moves.length : '?'));
        const foundationCount = sol.foundation_count !== undefined ? sol.foundation_count : (isWin ? 52 : '?');
        const desc = sol.description || (sol.first_move ? `Premier coup recommandé : ${formatMoveDescription(sol.first_move)}` : `Séquence de ${moveCount} coups`);

        const itemEl = document.createElement('div');
        itemEl.className = 'solution-result-item';

        itemEl.innerHTML = `
            <div class="solution-item-header">
                <span class="solution-rank">#${rank}</span>
                <span class="solution-type-badge ${typeClass}">${typeLabel}</span>
            </div>
            <div class="solution-item-details">
                <span><strong>${moveCount}</strong> coups</span>
                <span>Fondations : <strong>${foundationCount} / 52</strong></span>
            </div>
            <div class="solution-item-desc">${desc}</div>
            <div class="solution-item-actions">
                <button class="btn btn-small btn-success btn-confirm-move" title="Exécuter immédiatement ce coup">
                    ✓ Confirmer ce coup
                </button>
                <button class="btn btn-small btn-secondary btn-view-solution" title="Ouvrir la visionneuse de solution">
                    👁 Voir
                </button>
            </div>
        `;

        const btnConfirm = itemEl.querySelector('.btn-confirm-move');
        if (btnConfirm) {
            btnConfirm.onclick = () => handleConfirmRecommendedMove(sol, idx);
        }

        const btnView = itemEl.querySelector('.btn-view-solution');
        if (btnView) {
            btnView.onclick = () => openSolutionViewer(sol);
        }

        container.appendChild(itemEl);
    });
}

function formatMoveDescription(move) {
    if (!move) return 'Coup recommandé';
    if (typeof move === 'string') return move;
    if (move.description) return move.description;
    if (move.source_col !== undefined && move.dest_col !== undefined) {
        return `Déplacer de Colonne ${move.source_col + 1} vers Colonne ${move.dest_col + 1}`;
    }
    if (move.dest_suit) {
        return `Placer sur la Fondation ${SUIT_NAMES[move.dest_suit] || move.dest_suit}`;
    }
    return 'Coup recommandé';
}

/**
 * Confirms and applies recommended first move to the live game
 */
async function handleConfirmRecommendedMove(solution, solutionIndex) {
    const res = await api.confirmMove(solutionIndex);
    if (!res.ok) {
        // If API expects direct move execution
        if (solution.first_move) {
            const fallbackRes = await api.move(solution.first_move);
            if (!fallbackRes.ok) {
                showToast(`Impossible de confirmer le coup : ${fallbackRes.error}`, 'error');
                return;
            }
        } else {
            showToast(`Erreur de confirmation : ${res.error}`, 'error');
            return;
        }
    }

    showToast('Coup confirmé et appliqué !', 'success');
    await loadGameState();
    await loadHistory();
}

/* ----------------------------------------------------------------------------
 * 12. SOLUTION VIEWER MODAL
 * ---------------------------------------------------------------------------- */

/**
 * Opens Solution Viewer modal for step-by-step playback
 */
function openSolutionViewer(solution) {
    appState.solutionViewer.isOpen = true;
    appState.solutionViewer.solution = solution;
    appState.solutionViewer.steps = solution.steps || solution.moves || [solution.first_move || { description: 'Position initiale' }];
    appState.solutionViewer.currentStepIndex = 0;
    appState.solutionViewer.isPlaying = false;

    const modal = document.getElementById('solution-modal');
    if (modal) modal.classList.remove('hidden');

    renderSolutionStep();

    // Attach control handlers
    const btnClose = document.getElementById('btn-close-solution');
    if (btnClose) btnClose.onclick = closeSolutionViewer;

    const btnRestart = document.getElementById('btn-sol-restart');
    if (btnRestart) btnRestart.onclick = restartSolutionPlayback;

    const btnPrev = document.getElementById('btn-sol-prev');
    if (btnPrev) btnPrev.onclick = prevSolutionStep;

    const btnNext = document.getElementById('btn-sol-next');
    if (btnNext) btnNext.onclick = nextSolutionStep;

    const btnPlay = document.getElementById('btn-sol-play');
    if (btnPlay) {
        btnPlay.textContent = '▶ Lecture';
        btnPlay.onclick = toggleSolutionPlay;
    }

    const btnApplyFirst = document.getElementById('btn-sol-apply-first');
    if (btnApplyFirst) {
        btnApplyFirst.onclick = async () => {
            closeSolutionViewer();
            await handleConfirmRecommendedMove(solution, 0);
        };
    }
}

/**
 * Closes the Solution Viewer modal
 */
function closeSolutionViewer() {
    appState.solutionViewer.isOpen = false;
    if (appState.solutionViewer.playIntervalId) {
        clearInterval(appState.solutionViewer.playIntervalId);
        appState.solutionViewer.playIntervalId = null;
    }
    const modal = document.getElementById('solution-modal');
    if (modal) modal.classList.add('hidden');
}

/**
 * Toggles auto-playback
 */
function toggleSolutionPlay() {
    const btnPlay = document.getElementById('btn-sol-play');
    if (appState.solutionViewer.isPlaying) {
        // Pause
        appState.solutionViewer.isPlaying = false;
        if (appState.solutionViewer.playIntervalId) {
            clearInterval(appState.solutionViewer.playIntervalId);
            appState.solutionViewer.playIntervalId = null;
        }
        if (btnPlay) btnPlay.textContent = '▶ Lecture';
    } else {
        // Play
        appState.solutionViewer.isPlaying = true;
        if (btnPlay) btnPlay.textContent = '⏸ Pause';

        appState.solutionViewer.playIntervalId = setInterval(() => {
            if (appState.solutionViewer.currentStepIndex < appState.solutionViewer.steps.length - 1) {
                appState.solutionViewer.currentStepIndex++;
                renderSolutionStep();
            } else {
                // End reached
                toggleSolutionPlay();
            }
        }, 1000);
    }
}

function prevSolutionStep() {
    if (appState.solutionViewer.currentStepIndex > 0) {
        appState.solutionViewer.currentStepIndex--;
        renderSolutionStep();
    }
}

function nextSolutionStep() {
    if (appState.solutionViewer.currentStepIndex < appState.solutionViewer.steps.length - 1) {
        appState.solutionViewer.currentStepIndex++;
        renderSolutionStep();
    }
}

function restartSolutionPlayback() {
    appState.solutionViewer.currentStepIndex = 0;
    renderSolutionStep();
}

/**
 * Renders the preview at current step index
 */
function renderSolutionStep() {
    const { steps, currentStepIndex } = appState.solutionViewer;
    const totalSteps = steps.length;
    const currentStep = steps[currentStepIndex];

    const counterEl = document.getElementById('solution-step-counter');
    if (counterEl) counterEl.textContent = `Coup ${currentStepIndex + 1} / ${totalSteps}`;

    const descEl = document.getElementById('solution-step-desc');
    if (descEl) {
        descEl.textContent = currentStep ? (currentStep.description || formatMoveDescription(currentStep)) : 'Position';
    }

    // Mini board visual preview
    renderMiniBoardPreview(currentStep ? currentStep.state : null);
}

/**
 * Renders the mini board state inside Solution Viewer
 */
function renderMiniBoardPreview(stateSnapshot) {
    const container = document.getElementById('solution-board-preview');
    if (!container) return;

    // Use snapshot if provided, otherwise fallback to current game state
    const state = stateSnapshot || appState.gameState;

    container.innerHTML = `
        <div class="board-top-row">
            <div class="stock-waste-group">
                <div class="pile-container">
                    <span class="pile-label">Pioche</span>
                    <div class="card-slot">${(state.stock && state.stock.count > 0) ? '<div class="solitaire-card card-back"></div>' : '<span class="stock-empty-indicator">↺</span>'}</div>
                </div>
                <div class="pile-container">
                    <span class="pile-label">Défausse</span>
                    <div class="card-slot">${state.waste && state.waste.top ? '' : ''}</div>
                </div>
            </div>
            <div class="top-row-spacer"></div>
            <div class="foundations-group">
                ${SUITS.map(s => {
                    const top = state.foundations && state.foundations[s] && state.foundations[s].length > 0 ?
                                state.foundations[s][state.foundations[s].length - 1] : null;
                    return `
                        <div class="pile-container">
                            <span class="pile-label">${SUIT_SYMBOLS[s]}</span>
                            <div class="card-slot foundation-pile" data-suit="${s}">
                                ${top ? '' : `<span class="foundation-watermark ${SUIT_COLORS[s]}">${SUIT_SYMBOLS[s]}</span>`}
                            </div>
                        </div>
                    `;
                }).join('')}
            </div>
        </div>
        <div class="tableau-area" style="min-height: 260px; margin-top: 14px;">
            <div class="tableau-columns-container">
                ${[0, 1, 2, 3, 4, 5, 6].map(idx => `
                    <div class="tableau-col" id="mini-col-${idx}">
                        <div class="col-header">${idx + 1}</div>
                        <div class="col-cards" style="position: relative;"></div>
                    </div>
                `).join('')}
            </div>
        </div>
    `;

    // Populate top waste card if present
    if (state.waste && state.waste.top) {
        const wasteSlot = container.querySelector('.stock-waste-group .pile-container:nth-child(2) .card-slot');
        if (wasteSlot) {
            wasteSlot.appendChild(createCardElement(state.waste.top, true, false));
        }
    }

    // Populate foundations top cards
    SUITS.forEach(s => {
        if (state.foundations && state.foundations[s] && state.foundations[s].length > 0) {
            const top = state.foundations[s][state.foundations[s].length - 1];
            const pile = container.querySelector(`.foundation-pile[data-suit="${s}"]`);
            if (pile) {
                pile.innerHTML = '';
                pile.appendChild(createCardElement(top, true, false));
            }
        }
    });

    // Populate columns
    if (state.columns) {
        for (let colIdx = 0; colIdx < 7; colIdx++) {
            const rawCol = state.columns[colIdx];
            const cards = Array.isArray(rawCol) ? rawCol : (rawCol && rawCol.cards ? rawCol.cards : []);
            const colCardsContainer = container.querySelector(`#mini-col-${colIdx} .col-cards`);
            if (!colCardsContainer) continue;

            let currentTop = 0;
            cards.forEach((rawCard, cIdx) => {
                const card = parseCard(rawCard);
                const isFaceUp = card.face_up !== false;
                const wrapper = document.createElement('div');
                wrapper.className = 'tableau-card-wrapper';
                wrapper.style.top = `${currentTop}px`;
                wrapper.style.zIndex = cIdx + 1;
                wrapper.appendChild(createCardElement(card, isFaceUp, false));
                colCardsContainer.appendChild(wrapper);
                currentTop += isFaceUp ? 20 : 14;
            });
            colCardsContainer.style.height = `${Math.max(84, currentTop + 50)}px`;
        }
    }
}

/* ----------------------------------------------------------------------------
 * 13. ACTION HISTORY & UNDO/REDO
 * ---------------------------------------------------------------------------- */

/**
 * Fetches and renders action history from GET /api/history
 */
async function loadHistory() {
    const res = await api.getHistory();
    if (!res.ok) return;

    let items = [];
    if (Array.isArray(res.data)) {
        items = res.data;
    } else if (res.data && Array.isArray(res.data.entries)) {
        items = res.data.entries;
    } else if (res.data && Array.isArray(res.data.history)) {
        items = res.data.history;
    }

    appState.history = items;
    const movesCountEl = document.getElementById('stat-moves-count');
    if (movesCountEl) {
        movesCountEl.textContent = items.length;
    }
    renderHistory(items);
}

/**
 * Renders the scrollable history list
 */
function renderHistory(items) {
    const container = document.getElementById('history-list');
    if (!container) return;

    container.innerHTML = '';

    if (!items || items.length === 0) {
        container.innerHTML = `<p class="history-empty-hint">Aucune action enregistrée pour le moment.</p>`;
        return;
    }

    items.forEach((item, idx) => {
        const itemEl = document.createElement('div');
        itemEl.className = 'history-item';

        const icon = item.icon || '🂠';
        const desc = item.description || item.action || `Action #${idx + 1}`;
        const time = item.timestamp || '';

        itemEl.innerHTML = `
            <div class="history-item-left">
                <span class="history-icon">${icon}</span>
                <span class="history-desc">${desc}</span>
            </div>
            <span class="history-time">${time}</span>
        `;

        container.appendChild(itemEl);
    });

    // Auto-scroll to bottom of history
    container.scrollTop = container.scrollHeight;
}

/**
 * Undo last action
 */
async function handleUndo() {
    const res = await api.undo();
    if (!res.ok) {
        showToast(res.error || 'Impossible d\'annuler.', 'warning');
        return;
    }
    showToast('Action annulée', 'info');
    await loadGameState();
    await loadHistory();
}

/**
 * Redo last action
 */
async function handleRedo() {
    const res = await api.redo();
    if (!res.ok) {
        showToast(res.error || 'Impossible de rétablir.', 'warning');
        return;
    }
    showToast('Action rétablie', 'info');
    await loadGameState();
    await loadHistory();
}

/* ----------------------------------------------------------------------------
 * 14. VICTORY CELEBRATION MODAL
 * ---------------------------------------------------------------------------- */

function showVictoryModal(state) {
    const modal = document.getElementById('victory-modal');
    if (!modal) return;

    const statsEl = document.getElementById('victory-stats');
    if (statsEl) {
        statsEl.innerHTML = `
            <div><strong>52 / 52</strong><br><small>Cartes placées</small></div>
            <div><strong>100%</strong><br><small>Complété</small></div>
        `;
    }

    modal.classList.remove('hidden');

    const btnNewGame = document.getElementById('btn-victory-new-game');
    if (btnNewGame) {
        btnNewGame.onclick = () => {
            modal.classList.add('hidden');
            switchToScreen('setup');
        };
    }

    const btnClose = document.getElementById('btn-victory-close');
    if (btnClose) {
        btnClose.onclick = () => modal.classList.add('hidden');
    }
}

/* ----------------------------------------------------------------------------
 * 15. INITIALIZATION & EVENT LISTENERS
 * ---------------------------------------------------------------------------- */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Initialize Setup Screen
    initSetupScreen();

    // 2. Global Header actions
    const btnReconf = document.getElementById('btn-header-reconfigure');
    if (btnReconf) {
        btnReconf.onclick = () => switchToScreen('setup');
    }

    const btnNewGame = document.getElementById('btn-header-new-game');
    if (btnNewGame) {
        btnNewGame.onclick = () => {
            handleResetSetup();
            switchToScreen('setup');
        };
    }

    // 3. Board Bottom Bar Controls
    const btnBoardUndo = document.getElementById('btn-board-undo');
    if (btnBoardUndo) btnBoardUndo.onclick = handleUndo;

    const btnBoardRedo = document.getElementById('btn-board-redo');
    if (btnBoardRedo) btnBoardRedo.onclick = handleRedo;

    const btnBoardDraw = document.getElementById('btn-board-draw');
    if (btnBoardDraw) btnBoardDraw.onclick = handleStockDraw;

    // 4. Sidebar Undo/Redo
    const btnHistUndo = document.getElementById('btn-history-undo');
    if (btnHistUndo) btnHistUndo.onclick = handleUndo;

    const btnHistRedo = document.getElementById('btn-history-redo');
    if (btnHistRedo) btnHistRedo.onclick = handleRedo;

    // 5. Solver Controls
    const btnStartSolver = document.getElementById('btn-start-solver');
    if (btnStartSolver) btnStartSolver.onclick = startSolver;

    const btnStopSolver = document.getElementById('btn-stop-solver');
    if (btnStopSolver) btnStopSolver.onclick = stopSolver;

    // 6. Global click outside cards clears selection
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.solitaire-card') &&
            !e.target.closest('.card-slot') &&
            !e.target.closest('.tableau-col') &&
            !e.target.closest('.btn')) {
            if (appState.selection) {
                appState.selection = null;
                renderGameBoard(appState.gameState);
            }
        }
    });

    console.log('Solitaire Klondike - Assistant de Résolution initialisé avec succès.');
});
