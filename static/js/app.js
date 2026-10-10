/**
 * AlphaQuant Web Application Logic & State Controller
 */

// Application State
const state = {
  ticker: 'AAPL',
  period: '1y',
  strategy: 'momentum',
  capital: 100000,
  stockData: null,
  backtestResult: null,
  comparisonResult: null,
  isLoading: false
};

// Chart Instances
let klineChart = null;
let equityChart = null;
let compareEquityChart = null;
let icChart = null;

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
  const page = document.body.dataset.page;
  if (page) state.strategy = page;
  initCharts();
  initEventHandlers();
  loadPresets();
  loadGlobalConfig();
  runAnalysis();
});

function initCharts() {
  klineChart = new CandlestickChart('kline-canvas', 'kline-tooltip-bar');
  equityChart = new EquityChart('equity-canvas', 'equity-tooltip-bar');
  compareEquityChart = new MultiEquityChart('compare-equity-canvas');
  if (document.getElementById('ic-canvas')) {
    icChart = new RollingICChart('ic-canvas');
  }
}

function initEventHandlers() {
  // Strategy Tab Switching
  document.querySelectorAll('.strat-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      const strat = tab.dataset.strat;
      switchStrategy(strat);
    });
  });

  // Period Selector Buttons
  document.querySelectorAll('.period-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.period = btn.dataset.period;
      runAnalysis();
    });
  });

  // Ticker Search & Autocomplete
  setupSearchAutocomplete();

  // Run Backtest Button
  document.getElementById('run-backtest-btn').addEventListener('click', () => {
    runAnalysis();
  });

  // ML Train Ratio Slider
  const splitSlider = document.getElementById('param-ml-split');
  const splitValDisplay = document.getElementById('train-ratio-val');
  if (splitSlider && splitValDisplay) {
    splitSlider.addEventListener('input', (e) => {
      splitValDisplay.textContent = `${Math.round(e.target.value * 100)}%`;
    });
  }

  // Institutional Factor Weight Sliders
  const factorSliders = [
    { id: 'param-w-mom-12-1', valId: 'w-mom-12-1-val' },
    { id: 'param-w-risk-adj', valId: 'w-risk-adj-val' },
    { id: 'param-w-residual', valId: 'w-residual-val' },
    { id: 'param-w-trend-qual', valId: 'w-trend-qual-val' },
    { id: 'param-w-vol-confirm', valId: 'w-vol-confirm-val' }
  ];
  factorSliders.forEach(item => {
    const el = document.getElementById(item.id);
    const valEl = document.getElementById(item.valId);
    if (el && valEl) {
      el.addEventListener('input', (e) => {
        valEl.textContent = `${Math.round(e.target.value * 100)}%`;
      });
    }
  });

  // Reset Parameters Button
  const resetBtn = document.getElementById('reset-params-btn');
  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      resetParameters();
    });
  }

  // CLI Command Modal Handlers
  const modal = document.getElementById('cli-modal');
  const cliBtn = document.getElementById('cli-view-btn');
  const closeBtn = document.getElementById('close-modal-btn');
  const copyBtn = document.getElementById('copy-cli-btn');

  if (cliBtn && modal) {
    cliBtn.addEventListener('click', () => {
      updateCLIPreview();
      modal.classList.remove('hidden');
    });
  }

  if (closeBtn && modal) {
    closeBtn.addEventListener('click', () => modal.classList.add('hidden'));
    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.classList.add('hidden');
    });
  }

  if (copyBtn) {
    copyBtn.addEventListener('click', () => {
      const cmd = document.getElementById('cli-command-preview').textContent;
      navigator.clipboard.writeText(cmd).then(() => {
        copyBtn.textContent = "已复制!";
        setTimeout(() => copyBtn.textContent = "复制命令", 2000);
      });
    });
  }

  // Export CSV
  const exportBtn = document.getElementById('export-csv-btn');
  if (exportBtn) exportBtn.addEventListener('click', exportTradesCSV);
}

// ==========================================================================
// Yahoo Finance Search & Autocomplete Engine
// ==========================================================================

const FALLBACK_AUTOCOMPLETE_STOCKS = [
  { symbol: "ASX", name: "ASE Technology Holding Co., Ltd.", exchange: "NYSE", price: 46.43, change_pct: 2.04, type: "Equity" },
  { symbol: "AAPL", name: "Apple Inc.", exchange: "NASDAQ", price: 336.64, change_pct: -1.11, type: "Equity" },
  { symbol: "NVDA", name: "NVIDIA Corporation", exchange: "NASDAQ", price: 229.28, change_pct: -0.52, type: "Equity" },
  { symbol: "TSLA", name: "Tesla, Inc.", exchange: "NASDAQ", price: 268.45, change_pct: 2.34, type: "Equity" },
  { symbol: "MSFT", name: "Microsoft Corporation", exchange: "NASDAQ", price: 435.10, change_pct: 0.85, type: "Equity" },
  { symbol: "AMZN", name: "Amazon.com, Inc.", exchange: "NASDAQ", price: 185.30, change_pct: -0.45, type: "Equity" },
  { symbol: "GOOGL", name: "Alphabet Inc.", exchange: "NASDAQ", price: 178.90, change_pct: 1.12, type: "Equity" },
  { symbol: "META", name: "Meta Platforms, Inc.", exchange: "NASDAQ", price: 582.40, change_pct: 1.65, type: "Equity" },
  { symbol: "AMD", name: "Advanced Micro Devices", exchange: "NASDAQ", price: 165.20, change_pct: -1.80, type: "Equity" },
  { symbol: "SPY", name: "SPDR S&P 500 ETF Trust", exchange: "NYSEArca", price: 585.10, change_pct: 0.32, type: "ETF" },
  { symbol: "QQQ", name: "Invesco QQQ Trust", exchange: "NASDAQ", price: 492.60, change_pct: 0.45, type: "ETF" },
  { symbol: "BABA", name: "Alibaba Group Holding", exchange: "NYSE", price: 98.40, change_pct: -0.75, type: "Equity" },
  { symbol: "TSM", name: "Taiwan Semiconductor Mfg", exchange: "NYSE", price: 190.50, change_pct: 1.95, type: "Equity" },
  { symbol: "GS", name: "Goldman Sachs Group, Inc.", exchange: "NYSE", price: 512.30, change_pct: 1.15, type: "Equity" },
  { symbol: "MS", name: "Morgan Stanley", exchange: "NYSE", price: 118.40, change_pct: 0.82, type: "Equity" },
  { symbol: "JPM", name: "JPMorgan Chase & Co.", exchange: "NYSE", price: 222.50, change_pct: 0.65, type: "Equity" },
  { symbol: "PLTR", name: "Palantir Technologies", exchange: "NYSE", price: 43.80, change_pct: 3.45, type: "Equity" },
  { symbol: "COIN", name: "Coinbase Global, Inc.", exchange: "NASDAQ", price: 215.30, change_pct: 4.12, type: "Equity" },
  { symbol: "NFLX", name: "Netflix, Inc.", exchange: "NASDAQ", price: 712.50, change_pct: -0.25, type: "Equity" }
];

const COMPANY_ALIAS_CLIENT_MAP = {
  "日月光": "ASX",
  "日月光投控": "ASX",
  "日月光半导体": "ASX",
  "ase": "ASX",
  "asx": "ASX",
  "ase technology": "ASX",
  "台积电": "TSM",
  "台积": "TSM",
  "tsmc": "TSM",
  "苹果": "AAPL",
  "apple": "AAPL",
  "英伟达": "NVDA",
  "辉达": "NVDA",
  "nvidia": "NVDA",
  "微软": "MSFT",
  "特斯拉": "TSLA",
  "亚马逊": "AMZN",
  "谷歌": "GOOGL",
  "脸书": "META",
  "高盛": "GS",
  "摩根士丹利": "MS",
  "大摩": "MS",
  "摩根大通": "JPM",
  "小摩": "JPM",
  "阿里巴巴": "BABA",
  "阿里": "BABA",
  "腾讯": "TCEHY",
  "超微": "AMD"
};

function sanitizeTickerClient(raw) {
  if (!raw) return "AAPL";
  let s = String(raw).trim();
  // 1. Bracket extraction: e.g. "ASE Technology Holding Co., Ltd. (ASX）" -> "ASX"
  const m = s.match(/[\(（\[【]([A-Za-z0-9\.\-\^]+)[\)）\]】]/);
  if (m && m[1]) return m[1].toUpperCase().trim();

  // 2. Chinese/English company alias check
  const sClean = s.replace(/['’]/g, '').trim().toLowerCase();
  if (COMPANY_ALIAS_CLIENT_MAP[sClean]) return COMPANY_ALIAS_CLIENT_MAP[sClean];
  for (const [k, v] of Object.entries(COMPANY_ALIAS_CLIENT_MAP)) {
    if (sClean.includes(k) || k.includes(sClean)) return v;
  }

  // 3. Fallback alphanumeric uppercase
  const cleaned = sClean.replace(/[^A-Za-z0-9\.\-\^]/g, '').toUpperCase();
  return cleaned || "AAPL";
}

async function fetchYahooSuggestions(query) {
  if (!query) return [];
  const cleanQ = query.replace(/['’]/g, '').trim();

  // Check if brackets contain ticker
  const bracketMatch = cleanQ.match(/[\(（\[【]([A-Za-z0-9\.\-\^]+)[\)）\]】]/);
  const searchQ = bracketMatch ? bracketMatch[1] : cleanQ;

  try {
    const res = await fetch(`/api/search?q=${encodeURIComponent(searchQ)}`);
    const json = await res.json();
    if (json.status === 'success' && Array.isArray(json.data) && json.data.length > 0) {
      return json.data.slice(0, 5);
    }
  } catch (err) {
    console.warn("Backend /api/search unavailable or timed out, using fallback catalog:", err);
  }

  // Fallback matching with alias support
  const qLower = searchQ.toLowerCase().trim();
  let aliasSym = COMPANY_ALIAS_CLIENT_MAP[qLower];
  if (!aliasSym) {
    for (const [k, v] of Object.entries(COMPANY_ALIAS_CLIENT_MAP)) {
      if (qLower.includes(k) || k.includes(qLower)) {
        aliasSym = v;
        break;
      }
    }
  }

  const matched = [];
  if (aliasSym) {
    const primary = FALLBACK_AUTOCOMPLETE_STOCKS.find(s => s.symbol.toUpperCase() === aliasSym);
    if (primary) matched.push(primary);
  }

  for (const item of FALLBACK_AUTOCOMPLETE_STOCKS) {
    if (matched.includes(item)) continue;
    if (item.symbol.toLowerCase().includes(qLower) || item.name.toLowerCase().includes(qLower)) {
      matched.push(item);
    }
    if (matched.length >= 5) break;
  }

  return matched.slice(0, 5);
}

function setupSearchAutocomplete() {
  const searchInput = document.getElementById('custom-ticker-input');
  const searchBtn = document.getElementById('search-ticker-btn');
  const dropdown = document.getElementById('search-suggestions-dropdown');
  const searchWrap = document.getElementById('search-box-wrap') || (searchInput ? searchInput.closest('.search-box') : null);

  if (!searchInput) return;

  let searchDebounceTimer = null;
  let currentSuggestions = [];
  let selectedIndex = -1;

  const closeDropdown = () => {
    if (dropdown) dropdown.classList.add('hidden');
    selectedIndex = -1;
  };

  const highlightIndex = (idx) => {
    if (!dropdown) return;
    const items = dropdown.querySelectorAll('.suggestion-item');
    items.forEach((item, i) => {
      if (i === idx) {
        item.classList.add('highlighted');
        item.scrollIntoView({ block: 'nearest' });
      } else {
        item.classList.remove('highlighted');
      }
    });
  };

  const selectSuggestion = (item) => {
    if (!item || !item.symbol) return;
    const targetSymbol = sanitizeTickerClient(item.symbol);
    searchInput.value = targetSymbol;
    closeDropdown();
    if (targetSymbol !== state.ticker) {
      state.ticker = targetSymbol;
      updateTickerDisplay();
      runAnalysis();
    }
  };

  const executeSearch = () => {
    const rawVal = searchInput.value.trim();
    if (!rawVal) {
      closeDropdown();
      return;
    }
    const targetSymbol = sanitizeTickerClient(rawVal);
    searchInput.value = targetSymbol;
    if (targetSymbol !== state.ticker) {
      state.ticker = targetSymbol;
      updateTickerDisplay();
      runAnalysis();
    }
    closeDropdown();
  };

  const renderSuggestions = (items, query) => {
    if (!dropdown) return;
    dropdown.innerHTML = '';
    currentSuggestions = items || [];
    selectedIndex = -1;

    if (!items || items.length === 0) {
      dropdown.innerHTML = `<div class="suggestion-empty">未匹配到 "${query}" 相关的 Yahoo 金融标的</div>`;
      dropdown.classList.remove('hidden');
      return;
    }

    const header = document.createElement('div');
    header.className = 'suggestion-header';
    header.innerHTML = `
      <span>Yahoo 金融标的候选 (最多5项)</span>
      <span class="suggestion-source-tag">Live Quotes</span>
    `;
    dropdown.appendChild(header);

    items.slice(0, 5).forEach((item, idx) => {
      const el = document.createElement('div');
      el.className = 'suggestion-item';
      el.dataset.idx = idx;

      const priceStr = item.price !== null && item.price !== undefined ? `$${Number(item.price).toFixed(2)}` : '--';
      let chgHtml = '<span class="suggestion-chg-pill flat">--</span>';
      if (item.change_pct !== null && item.change_pct !== undefined) {
        const val = Number(item.change_pct);
        if (val > 0) {
          chgHtml = `<span class="suggestion-chg-pill pos">+${val.toFixed(2)}%</span>`;
        } else if (val < 0) {
          chgHtml = `<span class="suggestion-chg-pill neg">${val.toFixed(2)}%</span>`;
        } else {
          chgHtml = `<span class="suggestion-chg-pill flat">0.00%</span>`;
        }
      }

      el.innerHTML = `
        <div class="suggestion-left">
          <span class="suggestion-symbol-badge">${item.symbol}</span>
          <div class="suggestion-info">
            <span class="suggestion-name" title="${item.name}">${item.name}</span>
            <span class="suggestion-meta">${item.exchange || ''} · ${item.type || 'Stock'}</span>
          </div>
        </div>
        <div class="suggestion-right">
          <span class="suggestion-price">${priceStr}</span>
          ${chgHtml}
        </div>
      `;

      el.addEventListener('click', (ev) => {
        ev.stopPropagation();
        selectSuggestion(item);
      });

      el.addEventListener('mouseenter', () => {
        selectedIndex = idx;
        highlightIndex(selectedIndex);
      });

      dropdown.appendChild(el);
    });

    dropdown.classList.remove('hidden');
  };

  // Input event with debounce
  searchInput.addEventListener('input', () => {
    clearTimeout(searchDebounceTimer);
    const q = searchInput.value.trim();
    if (!q) {
      closeDropdown();
      return;
    }

    // Show loading spinner
    if (dropdown) {
      dropdown.innerHTML = `
        <div class="suggestion-loading">
          <div class="suggestion-spinner"></div>
          <span>正在从 Yahoo Finance 检索标的与实时涨跌...</span>
        </div>
      `;
      dropdown.classList.remove('hidden');
    }

    searchDebounceTimer = setTimeout(async () => {
      const results = await fetchYahooSuggestions(q);
      renderSuggestions(results, q);
    }, 220);
  });

  // Keyboard navigation
  searchInput.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown') {
      if (dropdown && !dropdown.classList.contains('hidden') && currentSuggestions.length > 0) {
        e.preventDefault();
        selectedIndex = (selectedIndex + 1) % currentSuggestions.length;
        highlightIndex(selectedIndex);
      }
    } else if (e.key === 'ArrowUp') {
      if (dropdown && !dropdown.classList.contains('hidden') && currentSuggestions.length > 0) {
        e.preventDefault();
        selectedIndex = (selectedIndex - 1 + currentSuggestions.length) % currentSuggestions.length;
        highlightIndex(selectedIndex);
      }
    } else if (e.key === 'Enter') {
      if (dropdown && !dropdown.classList.contains('hidden') && selectedIndex >= 0 && currentSuggestions[selectedIndex]) {
        e.preventDefault();
        selectSuggestion(currentSuggestions[selectedIndex]);
      } else {
        executeSearch();
      }
    } else if (e.key === 'Escape') {
      closeDropdown();
    }
  });

  // Re-open on focus if text present
  searchInput.addEventListener('focus', () => {
    const q = searchInput.value.trim();
    if (q && currentSuggestions.length > 0 && dropdown) {
      dropdown.classList.remove('hidden');
    }
  });

  if (searchBtn) {
    searchBtn.addEventListener('click', (ev) => {
      ev.stopPropagation();
      executeSearch();
    });
  }

  // Click outside to dismiss dropdown
  document.addEventListener('click', (e) => {
    if (searchWrap && !searchWrap.contains(e.target)) {
      closeDropdown();
    }
  });
}

// ==========================================================================
// Watchlist & Custom Groups Engine (自选股与自建分组系统)
// ==========================================================================

const WATCHLIST_STORAGE_KEY = 'alphaquant_watchlist_groups';
const ACTIVE_GROUP_STORAGE_KEY = 'alphaquant_active_group_id';

const DEFAULT_WATCHLIST_GROUPS = [
  {
    id: "group-fav",
    name: "⭐ 我的自选",
    tickers: ["AAPL", "NVDA", "TSLA", "MSFT", "AMZN"]
  },
  {
    id: "group-index",
    name: "🏛️ 宽基与ETF",
    tickers: ["SPY", "QQQ", "IWM", "TLT", "GLD"]
  },
  {
    id: "group-tech",
    name: "🤖 科技与AI龙头",
    tickers: ["NVDA", "MSFT", "GOOGL", "META", "AMD", "TSM", "PLTR"]
  },
  {
    id: "group-china",
    name: "🇨🇳 核心中概股",
    tickers: ["BABA", "PDD", "BIDU", "JD", "NIO"]
  }
];

function getWatchlistGroups() {
  try {
    const raw = localStorage.getItem(WATCHLIST_STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length > 0) return parsed;
    }
  } catch (e) {
    console.warn("Failed to load watchlist from localStorage:", e);
  }
  return JSON.parse(JSON.stringify(DEFAULT_WATCHLIST_GROUPS));
}

function saveWatchlistGroups(groups) {
  try {
    localStorage.setItem(WATCHLIST_STORAGE_KEY, JSON.stringify(groups));
  } catch (e) {
    console.warn("Failed to save watchlist to localStorage:", e);
  }
}

function getActiveGroupId() {
  return localStorage.getItem(ACTIVE_GROUP_STORAGE_KEY) || "group-fav";
}

function setActiveGroupId(id) {
  try {
    localStorage.setItem(ACTIVE_GROUP_STORAGE_KEY, id);
  } catch (e) {}
}

function loadPresets() {
  initWatchlistModule();
}

function initWatchlistModule() {
  renderWatchlistRibbon();
  initWatchlistEventHandlers();
}

function renderWatchlistRibbon() {
  const groups = getWatchlistGroups();
  let activeId = getActiveGroupId();

  let activeGroup = groups.find(g => g.id === activeId);
  if (!activeGroup) {
    activeGroup = groups[0] || DEFAULT_WATCHLIST_GROUPS[0];
    activeId = activeGroup.id;
    setActiveGroupId(activeId);
  }

  // Populate group select dropdown
  const select = document.getElementById('watchlist-group-select');
  if (select) {
    select.innerHTML = '';
    groups.forEach(g => {
      const opt = document.createElement('option');
      opt.value = g.id;
      opt.textContent = `${g.name} (${g.tickers.length})`;
      if (g.id === activeId) opt.selected = true;
      select.appendChild(opt);
    });
  }

  // Populate ticker chips
  const container = document.getElementById('ticker-presets');
  if (container) {
    container.innerHTML = '';
    if (activeGroup.tickers.length === 0) {
      const emptyHint = document.createElement('span');
      emptyHint.style.cssText = 'font-size:11px; color:var(--text-muted); font-style:italic; padding:4px;';
      emptyHint.textContent = '该分组暂无标的，点击右侧添加';
      container.appendChild(emptyHint);
    } else {
      activeGroup.tickers.forEach(sym => {
        const chip = document.createElement('div');
        chip.className = `ticker-chip ${sym === state.ticker ? 'active' : ''}`;
        chip.dataset.symbol = sym;
        chip.title = `点击分析 ${sym} / 点击 × 从分组移除`;

        const symSpan = document.createElement('span');
        symSpan.className = 'chip-sym';
        symSpan.textContent = sym;
        chip.appendChild(symSpan);

        const delBtn = document.createElement('button');
        delBtn.className = 'chip-remove';
        delBtn.title = `从 ${activeGroup.name} 移除 ${sym}`;
        delBtn.innerHTML = '&times;';
        delBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          removeTickerFromActiveGroup(sym);
        });
        chip.appendChild(delBtn);

        chip.addEventListener('click', () => {
          document.querySelectorAll('.ticker-chip').forEach(c => c.classList.remove('active'));
          chip.classList.add('active');
          state.ticker = sym;
          updateTickerDisplay();
          runAnalysis();
        });

        container.appendChild(chip);
      });
    }
  }

  updateFavoriteStarButton();
}

function updateFavoriteStarButton() {
  const btn = document.getElementById('btn-toggle-favorite');
  const icon = document.getElementById('fav-star-icon');
  const text = document.getElementById('fav-star-text');
  if (!btn) return;

  const groups = getWatchlistGroups();
  const activeId = getActiveGroupId();
  const activeGroup = groups.find(g => g.id === activeId) || groups[0];

  const isFavorited = activeGroup && activeGroup.tickers.includes(state.ticker);
  if (isFavorited) {
    btn.classList.add('active');
    if (icon) icon.textContent = '★';
    if (text) text.textContent = '已自选';
    btn.title = `从当前分组 (${activeGroup ? activeGroup.name : ''}) 移除 ${state.ticker}`;
  } else {
    btn.classList.remove('active');
    if (icon) icon.textContent = '☆';
    if (text) text.textContent = '加自选';
    btn.title = `添加 ${state.ticker} 到当前分组 (${activeGroup ? activeGroup.name : ''})`;
  }
}

function toggleCurrentTickerFavorite() {
  const groups = getWatchlistGroups();
  const activeId = getActiveGroupId();
  const activeGroup = groups.find(g => g.id === activeId) || groups[0];
  if (!activeGroup) return;

  const idx = activeGroup.tickers.indexOf(state.ticker);
  if (idx >= 0) {
    activeGroup.tickers.splice(idx, 1);
  } else {
    activeGroup.tickers.push(state.ticker);
  }

  saveWatchlistGroups(groups);
  renderWatchlistRibbon();
}

function removeTickerFromActiveGroup(sym) {
  const groups = getWatchlistGroups();
  const activeId = getActiveGroupId();
  const activeGroup = groups.find(g => g.id === activeId) || groups[0];
  if (!activeGroup) return;

  const idx = activeGroup.tickers.indexOf(sym);
  if (idx >= 0) {
    activeGroup.tickers.splice(idx, 1);
    saveWatchlistGroups(groups);
    renderWatchlistRibbon();
  }
}

function addTickerToActiveGroup(sym) {
  const cleanSym = sym.trim().toUpperCase();
  if (!cleanSym) return;

  const groups = getWatchlistGroups();
  const activeId = getActiveGroupId();
  const activeGroup = groups.find(g => g.id === activeId) || groups[0];
  if (!activeGroup) return;

  if (!activeGroup.tickers.includes(cleanSym)) {
    activeGroup.tickers.push(cleanSym);
    saveWatchlistGroups(groups);
  }

  state.ticker = cleanSym;
  renderWatchlistRibbon();
  updateTickerDisplay();
  runAnalysis();
}

function quickCreateGroup() {
  const name = prompt("请输入新自选分组名称 (如: 芯片半导体 / 新能源 / 观察仓):");
  if (!name || !name.trim()) return;

  const trimmed = name.trim();
  const groups = getWatchlistGroups();
  const newId = "group-" + Date.now();
  groups.push({
    id: newId,
    name: trimmed,
    tickers: [state.ticker]
  });

  saveWatchlistGroups(groups);
  setActiveGroupId(newId);
  renderWatchlistRibbon();
}

function initWatchlistEventHandlers() {
  // Group dropdown select
  const select = document.getElementById('watchlist-group-select');
  if (select) {
    select.addEventListener('change', () => {
      setActiveGroupId(select.value);
      renderWatchlistRibbon();
    });
  }

  // Quick "+ 分组" button
  const quickBtn = document.getElementById('btn-create-group-quick');
  if (quickBtn) {
    quickBtn.addEventListener('click', quickCreateGroup);
  }

  // Favorite Star Button toggle
  const favBtn = document.getElementById('btn-toggle-favorite');
  if (favBtn) {
    favBtn.addEventListener('click', toggleCurrentTickerFavorite);
  }

  // "+ 添加标的" chip button -> opens modal
  const addChipBtn = document.getElementById('btn-add-ticker-chip');
  const addModal = document.getElementById('add-ticker-modal');
  const closeAddModalBtn = document.getElementById('close-add-ticker-modal-btn');
  const confirmAddBtn = document.getElementById('modal-btn-confirm-add-ticker');
  const tickerInput = document.getElementById('modal-ticker-input');

  if (addChipBtn && addModal) {
    addChipBtn.addEventListener('click', () => {
      const groups = getWatchlistGroups();
      const activeId = getActiveGroupId();
      const activeGroup = groups.find(g => g.id === activeId) || groups[0];
      const targetNameEl = document.getElementById('modal-target-group-name');
      if (targetNameEl && activeGroup) targetNameEl.textContent = activeGroup.name;

      if (tickerInput) {
        tickerInput.value = '';
        setTimeout(() => tickerInput.focus(), 100);
      }
      addModal.classList.remove('hidden');
    });
  }

  if (closeAddModalBtn && addModal) {
    closeAddModalBtn.addEventListener('click', () => addModal.classList.add('hidden'));
    addModal.addEventListener('click', (e) => {
      if (e.target === addModal) addModal.classList.add('hidden');
    });
  }

  if (confirmAddBtn && tickerInput && addModal) {
    const handleConfirm = () => {
      const val = tickerInput.value.trim();
      if (val) {
        addTickerToActiveGroup(val);
        addModal.classList.add('hidden');
      }
    };
    confirmAddBtn.addEventListener('click', handleConfirm);
    tickerInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') handleConfirm();
    });
  }

  // Quick suggestion chips in add modal
  document.querySelectorAll('.tag-suggestion-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      addTickerToActiveGroup(chip.textContent.trim());
      if (addModal) addModal.classList.add('hidden');
    });
  });

  // "管理分组" button -> opens modal
  const manageBtn = document.getElementById('btn-manage-groups');
  const manageModal = document.getElementById('manage-groups-modal');
  const closeManageModalBtn = document.getElementById('close-manage-groups-modal-btn');
  const newGroupNameInput = document.getElementById('modal-new-group-name-input');
  const createGroupBtn = document.getElementById('modal-btn-create-group');
  const resetGroupsBtn = document.getElementById('modal-btn-reset-groups');

  if (manageBtn && manageModal) {
    manageBtn.addEventListener('click', () => {
      renderManageGroupsList();
      if (newGroupNameInput) newGroupNameInput.value = '';
      manageModal.classList.remove('hidden');
    });
  }

  if (closeManageModalBtn && manageModal) {
    closeManageModalBtn.addEventListener('click', () => manageModal.classList.add('hidden'));
    manageModal.addEventListener('click', (e) => {
      if (e.target === manageModal) manageModal.classList.add('hidden');
    });
  }

  if (createGroupBtn && newGroupNameInput) {
    createGroupBtn.addEventListener('click', () => {
      const name = newGroupNameInput.value.trim();
      if (!name) return;

      const groups = getWatchlistGroups();
      const newId = "group-" + Date.now();
      groups.push({
        id: newId,
        name: name,
        tickers: [state.ticker]
      });

      saveWatchlistGroups(groups);
      setActiveGroupId(newId);
      newGroupNameInput.value = '';
      renderManageGroupsList();
      renderWatchlistRibbon();
    });
  }

  if (resetGroupsBtn && manageModal) {
    resetGroupsBtn.addEventListener('click', () => {
      if (confirm("确定要恢复默认自选股与分组配置吗？当前自定义分组将被重置。")) {
        saveWatchlistGroups(DEFAULT_WATCHLIST_GROUPS);
        setActiveGroupId("group-fav");
        renderManageGroupsList();
        renderWatchlistRibbon();
      }
    });
  }
}

function renderManageGroupsList() {
  const container = document.getElementById('modal-group-list-container');
  if (!container) return;

  const groups = getWatchlistGroups();
  const activeId = getActiveGroupId();

  container.innerHTML = '';
  groups.forEach((g, idx) => {
    const item = document.createElement('div');
    item.className = 'group-list-item';

    const left = document.createElement('div');
    left.className = 'group-item-left';

    const nameSpan = document.createElement('span');
    nameSpan.className = 'group-item-name';
    nameSpan.textContent = g.name;
    left.appendChild(nameSpan);

    const tickersDiv = document.createElement('div');
    tickersDiv.className = 'group-item-tickers';
    if (g.tickers.length === 0) {
      tickersDiv.textContent = '(暂无标的)';
    } else {
      g.tickers.slice(0, 7).forEach(sym => {
        const badge = document.createElement('span');
        badge.className = 'group-item-badge';
        badge.textContent = sym;
        tickersDiv.appendChild(badge);
      });
      if (g.tickers.length > 7) {
        const more = document.createElement('span');
        more.className = 'group-item-badge';
        more.textContent = `+${g.tickers.length - 7}`;
        tickersDiv.appendChild(more);
      }
    }
    left.appendChild(tickersDiv);
    item.appendChild(left);

    const actions = document.createElement('div');
    actions.className = 'group-item-actions';

    // Switch to this group
    const switchBtn = document.createElement('button');
    switchBtn.className = 'btn-group-switch';
    switchBtn.textContent = g.id === activeId ? '当前生效' : '切换使用';
    if (g.id === activeId) switchBtn.style.background = '#dcfce7';
    switchBtn.addEventListener('click', () => {
      setActiveGroupId(g.id);
      renderManageGroupsList();
      renderWatchlistRibbon();
    });
    actions.appendChild(switchBtn);

    // Delete group (allow if more than 1 group)
    if (groups.length > 1) {
      const delBtn = document.createElement('button');
      delBtn.className = 'btn-group-del';
      delBtn.textContent = '删除';
      delBtn.title = `删除分组: ${g.name}`;
      delBtn.addEventListener('click', () => {
        if (confirm(`确定要删除分组 "${g.name}" 吗？`)) {
          groups.splice(idx, 1);
          saveWatchlistGroups(groups);
          if (g.id === activeId) {
            setActiveGroupId(groups[0].id);
          }
          renderManageGroupsList();
          renderWatchlistRibbon();
        }
      });
      actions.appendChild(delBtn);
    }

    item.appendChild(actions);
    container.appendChild(item);
  });
}

function updateTickerDisplay() {
  const display = document.getElementById('current-ticker-display');
  if (display) display.textContent = state.ticker;
  const ribbonDisplay = document.getElementById('ribbon-ticker-display');
  if (ribbonDisplay) ribbonDisplay.textContent = state.ticker;
  const klineTitle = document.getElementById('kline-chart-title');
  if (klineTitle) klineTitle.textContent = `${state.ticker} 历史行情与交易信号标定 (Candlestick & Signals)`;
  updateActivePresetChip();
  updateFavoriteStarButton();
}

function updateActivePresetChip() {
  document.querySelectorAll('.ticker-chip').forEach(c => {
    if (c.dataset && c.dataset.symbol === state.ticker) c.classList.add('active');
    else if (c.textContent.trim().startsWith(state.ticker)) c.classList.add('active');
    else c.classList.remove('active');
  });
}

function switchStrategy(strat) {
  state.strategy = strat;

  // Update tabs UI
  document.querySelectorAll('.strat-tab').forEach(t => {
    if (t.dataset.strat === strat) t.classList.add('active');
    else t.classList.remove('active');
  });

  // Switch parameter cards
  const groupMomentum = document.getElementById('params-momentum');
  const groupML = document.getElementById('params-ml');
  const groupTurtle = document.getElementById('params-turtle');
  const heading = document.getElementById('param-card-heading');

  if (groupMomentum) groupMomentum.classList.add('hidden');
  if (groupML) groupML.classList.add('hidden');
  if (groupTurtle) groupTurtle.classList.add('hidden');

  if (strat === 'momentum') {
    if (groupMomentum) groupMomentum.classList.remove('hidden');
    if (heading) heading.textContent = '多因子动量模型参数';
  } else if (strat === 'ml') {
    if (groupML) groupML.classList.remove('hidden');
    if (heading) heading.textContent = '机器学习预测模型参数';
  } else if (strat === 'turtle') {
    if (groupTurtle) groupTurtle.classList.remove('hidden');
    if (heading) heading.textContent = '海龟法则与网格风控参数';
  } else if (strat === 'compare') {
    if (heading) heading.textContent = '横向对决通用参数设定';
  }

  // Switch main views
  const singleView = document.getElementById('single-strategy-view');
  const compareView = document.getElementById('comparison-view');
  const mlDiag = document.getElementById('ml-diagnostics-panel');

  if (strat === 'compare') {
    if (singleView) singleView.classList.add('hidden');
    if (compareView) compareView.classList.remove('hidden');
  } else {
    if (singleView) singleView.classList.remove('hidden');
    if (compareView) compareView.classList.add('hidden');
    if (mlDiag) {
      if (strat === 'ml') mlDiag.classList.remove('hidden');
      else mlDiag.classList.add('hidden');
    }
  }

  runAnalysis();
}

async function loadGlobalConfig() {
  try {
    const res = await fetch('/api/config');
    const json = await res.json();
    if (json.status === 'success' && json.data) {
      window.activeConfig = json.data;
      localStorage.setItem('alphaquant_config', JSON.stringify(json.data));
    }
  } catch (e) {
    const local = localStorage.getItem('alphaquant_config');
    if (local) {
      try { window.activeConfig = JSON.parse(local); } catch(ex){}
    }
  }

  updateSidebarActiveProfile();
  initSidebarCollapseAndDrawer();
}

function updateSidebarActiveProfile() {
  const cfg = window.activeConfig || {};
  const mom = cfg.momentum || {};
  const acc = cfg.account || {};

  const tagEl = document.getElementById('sidebar-profile-tag');
  if (tagEl) {
    const pNames = {
      'aqr_momentum': 'AQR 动量优化型',
      'bridgewater_all_weather': '桥水全天候低波型',
      'classic_jegadeesh': '经典 JT 截面动量',
      'goldman_quant': '高盛量化激进型',
      'balanced_institutional': '标准机构平衡型'
    };
    tagEl.textContent = pNames[mom.preset_id] || '当前自定义组合';
  }

  const setMini = (idVal, idBar, val) => {
    const vEl = document.getElementById(idVal);
    const bEl = document.getElementById(idBar);
    if (vEl) vEl.textContent = `${Math.round(val * 100)}%`;
    if (bEl) bEl.style.width = `${Math.round(val * 100)}%`;
  };

  setMini('mini-w-mom-val', 'mini-w-mom-bar', mom.w_mom_12_1 ?? 0.30);
  setMini('mini-w-vol-val', 'mini-w-vol-bar', mom.w_risk_adj ?? 0.25);
  setMini('mini-w-res-val', 'mini-w-res-bar', mom.w_residual ?? 0.20);
  setMini('mini-w-qual-val', 'mini-w-qual-bar', mom.w_trend_qual ?? 0.15);
  setMini('mini-w-conf-val', 'mini-w-conf-bar', mom.w_vol_confirm ?? 0.10);

  const capEl = document.getElementById('sidebar-capital-val');
  if (capEl) capEl.textContent = `$${Number(acc.initial_capital || 100000).toLocaleString()}`;

  const fEl = document.getElementById('sidebar-friction-val');
  if (fEl) fEl.textContent = `${acc.commission_rate ?? 0.05}% / ${acc.slippage_rate ?? 0.05}%`;

  const vEl = document.getElementById('sidebar-vol-val');
  if (vEl) vEl.textContent = mom.use_vol_target !== false ? `开启 (${mom.target_vol ?? 15}% 年化)` : '关闭 (满仓运行)';
}

function initSidebarCollapseAndDrawer() {
  const toggleBtn = document.getElementById('btn-toggle-sidebar');
  const workspace = document.querySelector('.main-workspace');

  if (toggleBtn && workspace) {
    const isSavedCollapsed = localStorage.getItem('alphaquant_sidebar_collapsed') === 'true';
    if (isSavedCollapsed) workspace.classList.add('sidebar-collapsed');

    toggleBtn.addEventListener('click', () => {
      workspace.classList.toggle('sidebar-collapsed');
      const collapsed = workspace.classList.contains('sidebar-collapsed');
      localStorage.setItem('alphaquant_sidebar_collapsed', collapsed ? 'true' : 'false');
      setTimeout(() => {
        if (klineChart && typeof klineChart.resize === 'function') klineChart.resize();
        if (equityChart && typeof equityChart.resize === 'function') equityChart.resize();
      }, 200);
    });
  }

  // Quick Drawer handlers
  const openDrawerBtn = document.getElementById('btn-open-quick-drawer');
  const closeDrawerBtn = document.getElementById('btn-close-quick-drawer');
  const drawerModal = document.getElementById('quick-drawer-modal');
  const applyDrawerBtn = document.getElementById('btn-drawer-apply-backtest');

  if (openDrawerBtn && drawerModal) {
    openDrawerBtn.addEventListener('click', () => {
      drawerModal.classList.remove('hidden');
    });
  }

  if (closeDrawerBtn && drawerModal) {
    closeDrawerBtn.addEventListener('click', () => {
      drawerModal.classList.add('hidden');
    });
  }

  if (drawerModal) {
    drawerModal.addEventListener('click', (e) => {
      if (e.target === drawerModal) drawerModal.classList.add('hidden');
    });
  }

  if (applyDrawerBtn) {
    applyDrawerBtn.addEventListener('click', () => {
      drawerModal?.classList.add('hidden');
      updateSidebarActiveProfile();
      runAnalysis();
    });
  }
}

function collectBacktestParams() {
  const cfg = window.activeConfig || {};
  const acc = cfg.account || {};
  const momCfg = cfg.momentum || {};

  const capEl = document.getElementById('initial-capital');
  const commEl = document.getElementById('commission-rate');
  const slipEl = document.getElementById('slippage-rate');
  const slEl = document.getElementById('stop-loss');
  const tpEl = document.getElementById('take-profit');

  const capital = (capEl && capEl.value) ? parseFloat(capEl.value) : (acc.initial_capital || 100000);
  const comm = (commEl && commEl.value) ? parseFloat(commEl.value) / 100 : (acc.commission_rate ? acc.commission_rate / 100 : 0.0005);
  const slip = (slipEl && slipEl.value) ? parseFloat(slipEl.value) / 100 : (acc.slippage_rate ? acc.slippage_rate / 100 : 0.0005);
  const sl = (slEl && slEl.value) ? parseFloat(slEl.value) : (acc.stop_loss_pct || null);
  const tp = (tpEl && tpEl.value) ? parseFloat(tpEl.value) : (acc.take_profit_pct || null);

  const params = {};
  if (state.strategy === 'momentum') {
    const w12_1 = document.getElementById('param-w-mom-12-1');
    const wRisk = document.getElementById('param-w-risk-adj');
    const wRes = document.getElementById('param-w-residual');
    const wQual = document.getElementById('param-w-trend-qual');
    const wVol = document.getElementById('param-w-vol-confirm');
    const useVolTarget = document.getElementById('param-use-vol-target');
    const targetVol = document.getElementById('param-target-vol');
    const alphaTh = document.getElementById('param-alpha-th');
    const exitTh = document.getElementById('param-exit-th');
    const fastMa = document.getElementById('param-fast-ma');
    const slowMa = document.getElementById('param-slow-ma');
    const zWin = document.getElementById('param-z-win');

    params.w_mom_12_1 = w12_1 ? parseFloat(w12_1.value) : (momCfg.w_mom_12_1 ?? 0.30);
    params.w_risk_adj = wRisk ? parseFloat(wRisk.value) : (momCfg.w_risk_adj ?? 0.25);
    params.w_residual = wRes ? parseFloat(wRes.value) : (momCfg.w_residual ?? 0.20);
    params.w_trend_qual = wQual ? parseFloat(wQual.value) : (momCfg.w_trend_qual ?? 0.15);
    params.w_vol_confirm = wVol ? parseFloat(wVol.value) : (momCfg.w_vol_confirm ?? 0.10);
    params.use_vol_targeting = useVolTarget ? useVolTarget.checked : (momCfg.use_vol_target !== false);
    params.target_vol_annual = targetVol ? parseFloat(targetVol.value) / 100.0 : ((momCfg.target_vol || 15) / 100.0);
    params.alpha_threshold = alphaTh ? parseFloat(alphaTh.value) : (momCfg.alpha_th ?? 0.30);
    params.exit_threshold = exitTh ? parseFloat(exitTh.value) : (momCfg.exit_th ?? -0.20);
    params.fast_ma = fastMa ? parseInt(fastMa.value) : (momCfg.fast_ma || 10);
    params.slow_ma = slowMa ? parseInt(slowMa.value) : (momCfg.slow_ma || 30);
    params.zscore_window = zWin ? parseInt(zWin.value) : (momCfg.z_win || 30);

    // Legacy fallback if elements exist on index.html
    const rsiOverS = document.getElementById('param-rsi-oversold');
    const rsiOverB = document.getElementById('param-rsi-overbought');
    const useMacd = document.getElementById('param-use-macd');
    const useBb = document.getElementById('param-use-bb');
    if (rsiOverS) params.rsi_oversold = parseFloat(rsiOverS.value);
    if (rsiOverB) params.rsi_overbought = parseFloat(rsiOverB.value);
    if (useMacd) params.use_macd = useMacd.checked;
    if (useBb) params.use_bb = useBb.checked;
  } else if (state.strategy === 'ml') {
    params.model_type = document.getElementById('param-ml-model') ? document.getElementById('param-ml-model').value : 'rf';
    params.n_estimators = document.getElementById('param-ml-estimators') ? parseInt(document.getElementById('param-ml-estimators').value) || 100 : 100;
    params.max_depth = document.getElementById('param-ml-depth') ? parseInt(document.getElementById('param-ml-depth').value) || 5 : 5;
    params.horizon = document.getElementById('param-ml-horizon') ? parseInt(document.getElementById('param-ml-horizon').value) || 2 : 2;
    params.prob_threshold = document.getElementById('param-ml-threshold') ? parseFloat(document.getElementById('param-ml-threshold').value) || 0.53 : 0.53;
    params.train_ratio = document.getElementById('param-ml-split') ? parseFloat(document.getElementById('param-ml-split').value) || 0.70 : 0.70;
  } else if (state.strategy === 'turtle') {
    params.entry_period = document.getElementById('param-turtle-entry') ? parseInt(document.getElementById('param-turtle-entry').value) || 20 : 20;
    params.exit_period = document.getElementById('param-turtle-exit') ? parseInt(document.getElementById('param-turtle-exit').value) || 10 : 10;
    params.stop_loss_n = document.getElementById('param-turtle-stop') ? parseFloat(document.getElementById('param-turtle-stop').value) || 2.0 : 2.0;
    params.atr_period = document.getElementById('param-turtle-atr') ? parseInt(document.getElementById('param-turtle-atr').value) || 20 : 20;
  }

  return {
    ticker: state.ticker,
    period: state.period,
    strategy: state.strategy,
    capital,
    commission_rate: comm,
    slippage_rate: slip,
    stop_loss_pct: sl,
    take_profit_pct: tp,
    params
  };
}

async function runAnalysis() {
  if (state.isLoading) return;
  setLoadingState(true);

  try {
    if (state.strategy === 'compare') {
      await runComparison();
    } else {
      await runSingleBacktest();
    }
  } catch (err) {
    console.error("Backtest error:", err);
    showStatus(`回测发生异常: ${err.message}`, true);
  } finally {
    setLoadingState(false);
  }
}

async function runSingleBacktest() {
  showStatus(`正在拉取 ${state.ticker} 行情并计算技术指标...`);
  
  // 1. Fetch candlestick & indicators (with GitHub Pages fallback)
  let histJson;
  try {
    const histRes = await fetch(`/api/stock/history?ticker=${state.ticker}&period=${state.period}`);
    histJson = await histRes.json();
    if (histJson.status !== 'success') throw new Error(histJson.message);
  } catch (err) {
    console.warn("Backend API unavailable, using client-side simulated market data (GitHub Pages Mode):", err);
    histJson = generateClientStockData(state.ticker, state.period);
  }
  state.stockData = histJson;

  // 2. Post Backtest (with GitHub Pages fallback)
  showStatus(`执行 ${state.strategy.toUpperCase()} 量化模型运算与撮合...`);
  const payload = collectBacktestParams();
  let btJson;
  try {
    const btRes = await fetch('/api/backtest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    btJson = await btRes.json();
    if (btJson.status !== 'success') throw new Error(btJson.message);
  } catch (err) {
    console.warn("Backtest API unavailable, using client-side simulation engine (GitHub Pages Mode):", err);
    btJson = runClientSimulation(histJson, payload);
  }
  state.backtestResult = btJson;

  // 3. Render charts and stats
  renderKPIs(btJson.metrics);
  klineChart.setData(histJson.candles, btJson.signals);
  equityChart.setData(btJson.equity_curve);
  renderTradesTable(btJson.trades);

  // If ML strategy, render diagnostics
  if (state.strategy === 'ml' && btJson.meta) {
    renderMLDiagnostics(btJson.meta);
  }
  // If Momentum strategy, render factor diagnostics
  if (state.strategy === 'momentum' && btJson.meta) {
    renderFactorDiagnostics(btJson.meta, btJson.metrics);
  }

  showStatus(`回测完成 · ${state.ticker} [${state.period}] · 交易日: ${histJson.total_bars}天`);
}

async function runComparison() {
  showStatus(`正在对 ${state.ticker} 同时运行三大策略对比测试...`);
  const capEl = document.getElementById('initial-capital');
  const capital = (capEl && capEl.value) ? parseFloat(capEl.value) : 100000;

  const res = await fetch('/api/compare', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ticker: state.ticker,
      period: state.period,
      capital: capital
    })
  });
  const json = await res.json();
  if (json.status !== 'success') throw new Error(json.message);

  state.comparisonResult = json.results;
  renderComparisonCards(json.results);
  renderComparisonMatrixTable(json.results);

  // Overlay Equity Curves
  const colors = {
    momentum: '#f59e0b',
    ml: '#00f2fe',
    turtle: '#10b981'
  };

  const seriesList = [];
  json.results.forEach(r => {
    seriesList.push({
      name: r.strategy_name,
      color: colors[r.strategy_key] || '#6366f1',
      lineWidth: 2.2,
      data: r.equity_curve.map(pt => ({ date: pt.date, val: pt.equity }))
    });
  });

  // Benchmark line from first result
  if (json.results.length > 0 && json.results[0].equity_curve.length > 0) {
    seriesList.push({
      name: 'Benchmark',
      color: '#64748b',
      lineWidth: 1.5,
      dashed: true,
      data: json.results[0].equity_curve.map(pt => ({ date: pt.date, val: pt.benchmark }))
    });
  }

  compareEquityChart.setSeries(seriesList);
  showStatus(`三大策略横向对决回测完成 · ${state.ticker}`);
}

function renderKPIs(m) {
  if (!m) return;
  const kpiReturn = document.getElementById('kpi-return');
  const kpiCagr = document.getElementById('kpi-cagr');
  const kpiBench = document.getElementById('kpi-bench-return');

  if (kpiReturn) {
    kpiReturn.textContent = `${m.total_return_pct >= 0 ? '+' : ''}${m.total_return_pct.toFixed(2)}%`;
    kpiReturn.className = `kpi-value ${m.total_return_pct >= 0 ? 'positive' : 'negative'}`;
  }
  if (kpiCagr) kpiCagr.textContent = `CAGR ${m.cagr_pct >= 0 ? '+' : ''}${m.cagr_pct.toFixed(2)}%`;
  if (kpiBench) kpiBench.textContent = `基准 (买入持有): ${m.benchmark_return_pct >= 0 ? '+' : ''}${m.benchmark_return_pct.toFixed(2)}%`;

  const kpiSharpe = document.getElementById('kpi-sharpe');
  if (kpiSharpe) kpiSharpe.textContent = m.sharpe_ratio.toFixed(2);
  const kpiSortino = document.getElementById('kpi-sortino');
  if (kpiSortino) kpiSortino.textContent = `Sortino ${m.sortino_ratio.toFixed(2)}`;
  const kpiVol = document.getElementById('kpi-volatility');
  if (kpiVol) kpiVol.textContent = `年化总波动率: ${m.annual_volatility_pct.toFixed(2)}%`;

  const kpiMdd = document.getElementById('kpi-mdd');
  if (kpiMdd) kpiMdd.textContent = `-${m.max_drawdown_pct.toFixed(2)}%`;
  const kpiCalmar = document.getElementById('kpi-calmar');
  if (kpiCalmar) kpiCalmar.textContent = `Calmar ${m.calmar_ratio.toFixed(2)}`;
  const kpiAlphaBeta = document.getElementById('kpi-alpha-beta');
  if (kpiAlphaBeta) kpiAlphaBeta.textContent = `Alpha: ${m.alpha_pct >= 0 ? '+' : ''}${m.alpha_pct.toFixed(2)}% · Beta: ${m.beta.toFixed(2)}`;

  const kpiWin = document.getElementById('kpi-winrate');
  if (kpiWin) kpiWin.textContent = `${m.win_rate_pct.toFixed(1)}%`;
  const kpiPf = document.getElementById('kpi-profit-factor');
  if (kpiPf) kpiPf.textContent = `盈亏比 ${m.profit_factor.toFixed(2)}`;
  const kpiTrades = document.getElementById('kpi-trades-count');
  if (kpiTrades) kpiTrades.textContent = `总交易: ${m.total_trades} 笔 (胜 ${m.winning_trades} / 负 ${m.losing_trades})`;
}

function renderFactorDiagnostics(meta, metrics) {
  if (!meta) return;

  // 1. Rolling IC Canvas
  if (icChart && meta.recent_rolling_ic) {
    icChart.setData(meta.recent_rolling_ic, meta.overall_ic || 0.0);
  }

  // 2. KPI Cards
  const kpiIc = document.getElementById('kpi-ic');
  if (kpiIc && meta.overall_ic !== undefined) {
    const icVal = meta.overall_ic;
    kpiIc.textContent = `${icVal >= 0 ? '+' : ''}${icVal.toFixed(3)}`;
    kpiIc.style.color = icVal >= 0 ? 'var(--apple-blue)' : 'var(--apple-red)';
  }
  const kpiIr = document.getElementById('kpi-ir');
  if (kpiIr && meta.factor_ir !== undefined) {
    kpiIr.textContent = `IR: ${meta.factor_ir >= 0 ? '+' : ''}${meta.factor_ir.toFixed(2)}`;
  }
  const kpiTstat = document.getElementById('kpi-tstat');
  if (kpiTstat && meta.ic_t_stat !== undefined) {
    kpiTstat.textContent = `t-统计量: ${meta.ic_t_stat} | IC均值: ${meta.ic_mean >= 0 ? '+' : ''}${meta.ic_mean}`;
  }
  const kpiGkVol = document.getElementById('kpi-gk-vol');
  if (kpiGkVol && meta.avg_gk_vol !== undefined) {
    kpiGkVol.textContent = `GK日内年化波动: ${meta.avg_gk_vol}%`;
  }
  const kpiVar = document.getElementById('kpi-var');
  const kpiCvar = document.getElementById('kpi-cvar');
  if (meta.risk_measures) {
    if (kpiVar) kpiVar.textContent = `-${meta.risk_measures.var_95_pct}%`;
    if (kpiCvar) kpiCvar.textContent = `CVaR -${meta.risk_measures.cvar_95_pct}%`;
  }

  // 3. Stat pills
  const diagIcVal = document.getElementById('diag-ic-val');
  if (diagIcVal) diagIcVal.textContent = `${meta.ic_mean >= 0 ? '+' : ''}${meta.ic_mean} / ${meta.factor_ir}`;

  const diagTstat = document.getElementById('diag-tstat-val');
  if (diagTstat) diagTstat.textContent = `${meta.ic_t_stat}`;

  const diagSpread = document.getElementById('diag-spread-val');
  if (diagSpread && meta.quintile_spread) {
    const sp = meta.quintile_spread.spread;
    diagSpread.textContent = `${sp >= 0 ? '+' : ''}${sp.toFixed(2)}%`;
    diagSpread.style.color = sp >= 0 ? 'var(--apple-green)' : 'var(--apple-red)';
  }

  const diagGk = document.getElementById('diag-gk-val');
  if (diagGk) diagGk.textContent = `${meta.avg_gk_vol}%`;

  const diagVolSizing = document.getElementById('diag-vol-sizing-val');
  if (diagVolSizing) {
    diagVolSizing.textContent = meta.use_vol_targeting ? `动态目标 (${Math.round((meta.target_vol_annual || 0.15) * 100)}%)` : '全仓 (100%)';
    diagVolSizing.style.color = meta.use_vol_targeting ? 'var(--apple-green)' : 'var(--text-muted)';
  }

  const diagWin = document.getElementById('diag-win-val');
  if (diagWin && metrics) {
    diagWin.textContent = `${metrics.win_rate_pct.toFixed(1)}%`;
  }

  // 4. Sub-factor IC breakdown bars
  const subfactorList = document.getElementById('subfactor-bars-list');
  if (subfactorList && meta.sub_factor_ics) {
    subfactorList.innerHTML = '';
    for (const [name, ic] of Object.entries(meta.sub_factor_ics)) {
      const icVal = typeof ic === 'number' ? ic : 0.0;
      const isPos = icVal >= 0;
      const pctBar = Math.min(100, Math.max(8, Math.abs(icVal) * 350));
      const row = document.createElement('div');
      row.style.cssText = 'display:flex; align-items:center; justify-content:space-between; font-size:11px; padding:3px 0;';
      row.innerHTML = `
        <span style="color:var(--text-secondary); width:135px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${name}</span>
        <div style="flex:1; height:5px; background:rgba(255,255,255,0.06); border-radius:3px; margin:0 10px; position:relative; overflow:hidden;">
          <div style="position:absolute; ${isPos ? 'left:50%' : 'right:50%'}; width:${pctBar / 2}%; height:100%; background:${isPos ? 'var(--apple-blue)' : 'var(--apple-red)'}; border-radius:2px;"></div>
        </div>
        <span style="font-family:var(--font-mono); font-size:10.5px; color:${isPos ? 'var(--apple-blue)' : 'var(--apple-red)'}; min-width:48px; text-align:right;">
          ${isPos ? '+' : ''}${icVal.toFixed(3)}
        </span>
      `;
      subfactorList.appendChild(row);
    }
  }

  // 5. IC Decay chips
  const decayChipsContainer = document.getElementById('ic-decay-chips');
  if (decayChipsContainer && meta.ic_decay) {
    decayChipsContainer.innerHTML = '';
    for (const [horizon, ic] of Object.entries(meta.ic_decay)) {
      const icVal = typeof ic === 'number' ? ic : 0.0;
      const isPos = icVal >= 0;
      const chip = document.createElement('div');
      chip.style.cssText = `
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid ${isPos ? 'rgba(10, 132, 255, 0.3)' : 'rgba(255, 69, 58, 0.3)'};
        padding: 2px 10px;
        border-radius: var(--radius-full);
        font-size: 10.5px;
        font-family: var(--font-mono);
        color: ${isPos ? 'var(--apple-blue)' : 'var(--apple-red)'};
      `;
      chip.innerHTML = `<span style="color:var(--text-muted)">${horizon}:</span> ${isPos ? '+' : ''}${icVal.toFixed(3)}`;
      decayChipsContainer.appendChild(chip);
    }
  }
}

function renderMLDiagnostics(meta) {
  const container = document.getElementById('feature-importance-bars');
  const tagsContainer = document.getElementById('ml-meta-tags');
  if (!container || !meta) return;

  tagsContainer.innerHTML = `
    <span class="ml-tag">模型: ${meta.model_type}</span>
    <span class="ml-tag">训练样本: ${meta.train_samples}</span>
    <span class="ml-tag">测试样本: ${meta.test_samples}</span>
  `;

  document.getElementById('ml-acc-val').textContent = `${meta.accuracy}%`;
  document.getElementById('ml-prec-val').textContent = `${meta.precision}%`;
  document.getElementById('ml-rec-val').textContent = `${meta.recall}%`;

  container.innerHTML = '';
  const features = meta.feature_importances || [];
  const maxImp = features.length > 0 ? features[0].importance : 1;

  features.slice(0, 6).forEach(f => {
    const pct = ((f.importance / maxImp) * 100).toFixed(1);
    const item = document.createElement('div');
    item.className = 'feature-bar-item';
    item.innerHTML = `
      <div class="feature-meta">
        <span>${f.feature}</span>
        <span>${(f.importance * 100).toFixed(2)}%</span>
      </div>
      <div class="feature-track">
        <div class="feature-fill" style="width: ${pct}%"></div>
      </div>
    `;
    container.appendChild(item);
  });
}

function renderTradesTable(trades) {
  const tbody = document.getElementById('trades-table-body');
  if (!tbody) return;

  if (!trades || trades.length === 0) {
    tbody.innerHTML = `<tr><td colspan="11" class="empty-state">当前参数区间内无触发交易订单</td></tr>`;
    return;
  }

  tbody.innerHTML = trades.slice().reverse().map(t => {
    const isWin = t.pnl >= 0;
    const pnlColor = isWin ? '#10b981' : '#f43f5e';
    const reasonMap = {
      'SIGNAL_SELL': '信号死叉离场',
      'STOP_LOSS': '止损线触发平仓',
      'TAKE_PROFIT': '止盈线触发平仓',
      'END_OF_PERIOD': '回测期末清仓'
    };
    const reasonText = reasonMap[t.exit_reason] || t.exit_reason;

    return `
      <tr>
        <td>#${t.trade_id}</td>
        <td><span class="tag-badge long">LONG</span></td>
        <td>${t.entry_date}</td>
        <td>$${t.entry_price.toFixed(2)}</td>
        <td>${t.exit_date}</td>
        <td>$${t.exit_price.toFixed(2)}</td>
        <td>${t.shares.toLocaleString()}</td>
        <td>${t.holding_days} 天</td>
        <td style="color:${pnlColor}">$${t.pnl >= 0 ? '+' : ''}${t.pnl.toFixed(2)}</td>
        <td style="color:${pnlColor}">${t.pnl_pct >= 0 ? '+' : ''}${t.pnl_pct.toFixed(2)}%</td>
        <td><span class="tag-reason">${reasonText}</span></td>
      </tr>
    `;
  }).join('');
}

function renderComparisonCards(results) {
  const container = document.getElementById('comparison-cards-grid');
  if (!container || !results) return;

  container.innerHTML = '';
  results.forEach(r => {
    const m = r.metrics;
    const card = document.createElement('div');
    card.className = `comp-card ${m.total_return_pct > 20 ? 'highlight' : ''}`;
    card.innerHTML = `
      <div class="comp-card-badge">${r.strategy_key.toUpperCase()}</div>
      <h4 class="comp-title">${r.strategy_name}</h4>
      <div class="comp-stat-grid">
        <div class="comp-stat-item">
          <span class="cs-label">累计收益率</span>
          <span class="cs-val" style="color:${m.total_return_pct >= 0 ? '#10b981' : '#f43f5e'}">
            ${m.total_return_pct >= 0 ? '+' : ''}${m.total_return_pct.toFixed(2)}%
          </span>
        </div>
        <div class="comp-stat-item">
          <span class="cs-label">夏普比率 (Sharpe)</span>
          <span class="cs-val" style="color:#00f2fe">${m.sharpe_ratio.toFixed(2)}</span>
        </div>
        <div class="comp-stat-item">
          <span class="cs-label">最大回撤 (MDD)</span>
          <span class="cs-val" style="color:#f43f5e">-${m.max_drawdown_pct.toFixed(2)}%</span>
        </div>
        <div class="comp-stat-item">
          <span class="cs-label">交易胜率 / 交易笔数</span>
          <span class="cs-val">${m.win_rate_pct.toFixed(1)}% / ${m.total_trades}笔</span>
        </div>
      </div>
    `;
    container.appendChild(card);
  });
}

function renderComparisonMatrixTable(results) {
  const tbody = document.getElementById('comparison-matrix-body');
  if (!tbody || !results) return;

  tbody.innerHTML = results.map(r => {
    const m = r.metrics;
    const isPos = m.total_return_pct >= 0;
    return `
      <tr>
        <td style="font-weight:700; color:#fff">${r.strategy_name}</td>
        <td style="color:${isPos ? '#10b981' : '#f43f5e'}">${isPos ? '+' : ''}${m.total_return_pct.toFixed(2)}%</td>
        <td>${m.cagr_pct >= 0 ? '+' : ''}${m.cagr_pct.toFixed(2)}%</td>
        <td style="color:#00f2fe">${m.sharpe_ratio.toFixed(2)}</td>
        <td>${m.sortino_ratio.toFixed(2)}</td>
        <td style="color:#f43f5e">-${m.max_drawdown_pct.toFixed(2)}%</td>
        <td>${m.win_rate_pct.toFixed(1)}%</td>
        <td>${m.profit_factor.toFixed(2)}</td>
        <td>${m.total_trades}</td>
        <td style="color:${m.alpha_pct >= 0 ? '#10b981' : '#f43f5e'}">${m.alpha_pct >= 0 ? '+' : ''}${m.alpha_pct.toFixed(2)}%</td>
        <td>${m.beta.toFixed(2)}</td>
      </tr>
    `;
  }).join('');
}

function exportTradesCSV() {
  if (!state.backtestResult || !state.backtestResult.trades || state.backtestResult.trades.length === 0) {
    alert("暂无可导出的交易记录");
    return;
  }
  const trades = state.backtestResult.trades;
  const headers = ["Trade_ID", "Type", "Entry_Date", "Entry_Price", "Exit_Date", "Exit_Price", "Shares", "Holding_Days", "PnL", "PnL_Pct", "Exit_Reason"];
  const rows = trades.map(t => [
    t.trade_id,
    t.type,
    t.entry_date,
    t.entry_price,
    t.exit_date,
    t.exit_price,
    t.shares,
    t.holding_days,
    t.pnl,
    t.pnl_pct,
    t.exit_reason
  ]);

  const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows.map(e => e.join(","))].join("\n");
  const encodedUri = encodeURI(csvContent);
  const link = document.createElement("a");
  link.setAttribute("href", encodedUri);
  link.setAttribute("download", `trades_${state.ticker}_${state.strategy}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

function updateCLIPreview() {
  const stratArg = state.strategy === 'compare' ? 'all' : state.strategy;
  const cmd = `python backtest_cli.py --ticker ${state.ticker} --strategy ${stratArg} --period ${state.period} --capital ${state.capital}`;
  const el = document.getElementById('cli-command-preview');
  if (el) el.textContent = cmd;
}

function resetParameters() {
  const setVal = (id, val) => { const el = document.getElementById(id); if (el) el.value = val; };
  const setCheck = (id, checked) => { const el = document.getElementById(id); if (el) el.checked = checked; };
  const setText = (id, text) => { const el = document.getElementById(id); if (el) el.textContent = text; };

  setVal('initial-capital', '100000');
  setVal('commission-rate', '0.05');
  setVal('slippage-rate', '0.05');
  setVal('stop-loss', '');
  setVal('take-profit', '');

  // Institutional Momentum sliders
  setVal('param-w-mom-12-1', '0.30'); setText('w-mom-12-1-val', '30%');
  setVal('param-w-risk-adj', '0.25'); setText('w-risk-adj-val', '25%');
  setVal('param-w-residual', '0.20'); setText('w-residual-val', '20%');
  setVal('param-w-trend-qual', '0.15'); setText('w-trend-qual-val', '15%');
  setVal('param-w-vol-confirm', '0.10'); setText('w-vol-confirm-val', '10%');
  setCheck('param-use-vol-target', true);
  setVal('param-target-vol', '15');
  setVal('param-alpha-th', '0.30');
  setVal('param-exit-th', '-0.20');

  setVal('param-fast-ma', '10');
  setVal('param-slow-ma', '30');
  setVal('param-z-win', '30');
  setVal('param-rsi-oversold', '35');
  setVal('param-rsi-overbought', '70');
  setCheck('param-use-macd', true);
  setCheck('param-use-bb', true);

  setVal('param-ml-model', 'rf');
  setVal('param-ml-estimators', '100');
  setVal('param-ml-depth', '5');
  setVal('param-ml-horizon', '2');
  setVal('param-ml-threshold', '0.53');
  setVal('param-ml-split', '0.70');
  setText('train-ratio-val', '70%');

  setVal('param-turtle-entry', '20');
  setVal('param-turtle-exit', '10');
  setVal('param-turtle-stop', '2.0');
  setVal('param-turtle-atr', '20');

  runAnalysis();
}

function setLoadingState(isLoading) {
  state.isLoading = isLoading;
  const btn = document.getElementById('run-backtest-btn');
  if (!btn) return;
  if (isLoading) {
    btn.innerHTML = `<span class="btn-icon">⏳</span><span class="btn-label">回测计算中...</span>`;
    btn.style.opacity = '0.75';
    btn.style.pointerEvents = 'none';
  } else {
    btn.innerHTML = `<span class="btn-icon">⚡</span><span class="btn-label">运行回测 (Run Model)</span>`;
    btn.style.opacity = '1';
    btn.style.pointerEvents = 'auto';
  }
}

function showStatus(msg, isError = false) {
  const el = document.getElementById('status-text');
  if (el) {
    el.textContent = msg;
    el.style.color = isError ? '#f43f5e' : '#94a3b8';
  }
}

// Client-Side Simulation Engine for GitHub Pages Live Demo
function generateClientStockData(ticker, period) {
  const daysMap = { '6mo': 126, '1y': 252, '2y': 504, '3y': 756, '5y': 1260 };
  const n = daysMap[period] || 252;
  const candles = [];
  let price = ticker === 'NVDA' ? 120 : (ticker === 'TSLA' ? 240 : (ticker === 'SPY' ? 520 : 180));
  const now = new Date();

  for (let i = n; i >= 0; i--) {
    const d = new Date(now.getTime() - i * 24 * 3600 * 1000);
    const dateStr = d.toISOString().split('T')[0];
    const change = (Math.random() - 0.48) * 0.03 * price;
    const open = Math.round(price * 100) / 100;
    price = Math.max(10, price + change);
    const close = Math.round(price * 100) / 100;
    const high = Math.round((Math.max(open, close) + Math.random() * 0.015 * price) * 100) / 100;
    const low = Math.round((Math.min(open, close) - Math.random() * 0.015 * price) * 100) / 100;
    const vol = Math.floor(Math.random() * 20000000 + 10000000);

    candles.push({
      date: dateStr, open, high, low, close, volume: vol,
      sma_20: Math.round(close * (1 + (Math.random() - 0.5) * 0.02) * 100) / 100,
      sma_50: Math.round(close * (1 + (Math.random() - 0.5) * 0.04) * 100) / 100,
      rsi_14: Math.round((50 + Math.sin(i / 10) * 20) * 10) / 10,
      bb_upper: Math.round(high * 1.02 * 100) / 100,
      bb_lower: Math.round(low * 0.98 * 100) / 100
    });
  }

  return {
    status: 'success',
    ticker, period, total_bars: candles.length,
    latest_price: candles[candles.length - 1].close,
    change_pct: 1.25,
    candles
  };
}

function runClientSimulation(stockData, payload) {
  const candles = stockData.candles;
  const initialCap = payload.capital || 100000;
  let equity = initialCap;
  const equityCurve = [];
  const signals = [];
  const trades = [];
  let inPos = false;
  let entryPrice = 0;
  let entryDate = '';
  let shares = 0;

  candles.forEach((c, i) => {
    const isBuy = !inPos && (i % 32 === 12);
    const isSell = inPos && (i % 32 === 0);

    if (isBuy && i < candles.length - 1) {
      inPos = true;
      entryPrice = c.close;
      entryDate = c.date;
      shares = Math.floor((equity * 0.9) / c.close);
      signals.push({ date: c.date, price: c.close, type: 'BUY', reason: 'Alpha触发买入' });
    } else if (isSell) {
      inPos = false;
      const pnl = (c.close - entryPrice) * shares;
      const pnlPct = ((c.close - entryPrice) / entryPrice) * 100;
      equity += pnl;
      signals.push({ date: c.date, price: c.close, type: 'SELL', reason: '信号止盈平仓' });
      trades.push({
        trade_id: trades.length + 1,
        type: 'LONG',
        entry_date: entryDate,
        exit_date: c.date,
        entry_price: entryPrice,
        exit_price: c.close,
        shares,
        holding_days: 20,
        pnl: Math.round(pnl * 100) / 100,
        pnl_pct: Math.round(pnlPct * 100) / 100,
        exit_reason: 'SIGNAL_SELL'
      });
    }

    const currentEquity = inPos ? equity + (c.close - entryPrice) * shares : equity;
    equityCurve.push({
      date: c.date,
      equity: Math.round(currentEquity * 100) / 100,
      benchmark: Math.round(initialCap * (c.close / candles[0].close) * 100) / 100,
      drawdown_pct: 4.2
    });
  });

  const finalEq = equityCurve[equityCurve.length - 1].equity;
  const retPct = ((finalEq - initialCap) / initialCap) * 100;
  const benchRet = ((candles[candles.length - 1].close - candles[0].close) / candles[0].close) * 100;

  return {
    status: 'success',
    ticker: payload.ticker,
    period: payload.period,
    strategy: payload.strategy,
    metrics: {
      initial_capital: initialCap,
      final_equity: finalEq,
      total_return_pct: Math.round(retPct * 100) / 100,
      cagr_pct: Math.round(retPct * 0.95 * 100) / 100,
      benchmark_return_pct: Math.round(benchRet * 100) / 100,
      sharpe_ratio: 1.48,
      sortino_ratio: 1.76,
      max_drawdown_pct: 7.2,
      calmar_ratio: 1.82,
      annual_volatility_pct: 12.8,
      win_rate_pct: 66.7,
      profit_factor: 2.35,
      total_trades: trades.length,
      winning_trades: Math.ceil(trades.length * 0.67),
      losing_trades: Math.floor(trades.length * 0.33),
      alpha_pct: 6.4,
      beta: 0.38
    },
    meta: {
      overall_ic: 0.086,
      ic_mean: 0.072,
      factor_ir: 0.45,
      ic_t_stat: 2.31,
      avg_gk_vol: 14.8,
      use_vol_targeting: true,
      target_vol_annual: 0.15,
      sub_factor_ics: {
        '12M-1M Momentum': 0.072,
        'Risk-Adjusted Vol': 0.058,
        'Residual Alpha': 0.118,
        'Trend Quality': 0.052,
        'Volume-Confirmed': 0.041
      },
      ic_decay: { '1D': 0.098, '3D': 0.086, '5D': 0.072, '10D': 0.045, '20D': 0.018 },
      quintile_spread: { q5_return: 2.15, q1_return: 0.45, spread: 1.70 },
      risk_measures: { var_95_pct: 1.78, cvar_95_pct: 2.54, skewness: -0.12, kurtosis: 3.1, tail_ratio: 1.18 },
      recent_rolling_ic: equityCurve.slice(-40).map(pt => ({
        date: pt.date,
        ic: Math.round((Math.sin(new Date(pt.date).getTime() / 1e9) * 0.14 + 0.06) * 1000) / 1000
      }))
    },
    equity_curve: equityCurve,
    signals,
    trades
  };
}

