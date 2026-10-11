/**
 * AlphaQuant Institutional Paper Trading Desk & Model Ledger
 * 模拟对盘交易引擎与模型性能跟踪前端逻辑
 * 支持后端 API 与 GitHub Pages 纯前端离线持久化双模运行
 */

(function () {
  'use strict';

  const CLIENT_STORAGE_KEY = 'alphaquant_paper_account_state_v1';
  let isClientMode = false;

  // Market Baseline Prices Synced directly from finance.yahoo.com
  const MOCK_MARKET_PRICES = {
    'AAPL': { price: 336.64, name: 'Apple Inc.', change: -3.78, change_pct: -1.11 },
    'NVDA': { price: 229.28, name: 'NVIDIA Corporation', change: -1.20, change_pct: -0.52 },
    'TSLA': { price: 382.70, name: 'Tesla, Inc.', change: 7.70, change_pct: 2.05 },
    'MSFT': { price: 535.07, name: 'Microsoft Corporation', change: 12.46, change_pct: 2.38 },
    'AMZN': { price: 262.43, name: 'Amazon.com, Inc.', change: 8.37, change_pct: 3.29 },
    'GOOGL':{ price: 351.66, name: 'Alphabet Inc.', change: 3.37, change_pct: 0.97 },
    'META': { price: 718.67, name: 'Meta Platforms, Inc.', change: -2.22, change_pct: -0.31 },
    'TSM':  { price: 453.31, name: 'Taiwan Semiconductor', change: -5.88, change_pct: -1.28 },
    'SPY':  { price: 778.57, name: 'SPDR S&P 500 ETF', change: 4.11, change_pct: 0.53 },
    'QQQ':  { price: 751.27, name: 'Invesco QQQ Trust', change: 3.69, change_pct: 0.49 },
    'AMD':  { price: 608.10, name: 'Advanced Micro Devices', change: -12.58, change_pct: -2.03 },
    'PLTR': { price: 209.05, name: 'Palantir Tech', change: 10.27, change_pct: 5.17 },
    'BABA': { price: 111.37, name: 'Alibaba Group', change: 5.67, change_pct: 5.36 },
    'COIN': { price: 179.39, name: 'Coinbase Global', change: 7.39, change_pct: 4.30 },
    'BRK-B':{ price: 515.62, name: 'Berkshire Hathaway', change: 3.63, change_pct: 0.71 },
    'SMCI': { price: 41.86,  name: 'Super Micro Computer', change: -0.91, change_pct: -2.13 },
    'ASX':  { price: 46.43,  name: 'ASE Technology Holding', change: 0.93, change_pct: 2.04 },
    'GLD':  { price: 384.58, name: 'SPDR Gold Shares', change: 5.12, change_pct: 1.35 },
    'XOM':  { price: 168.94, name: 'Exxon Mobil Corp.', change: 0.36, change_pct: 0.21 },
    'JPM':  { price: 332.99, name: 'JPMorgan Chase & Co.', change: 1.24, change_pct: 0.37 },
    'BAC':  { price: 54.32,  name: 'Bank of America', change: 0.70, change_pct: 1.31 },
    'PDD':  { price: 81.35,  name: 'PDD Holdings', change: 3.09, change_pct: 3.95 },
    'BIDU': { price: 85.33,  name: 'Baidu Inc.', change: 1.41, change_pct: 1.68 },
    'JD':   { price: 27.09,  name: 'JD.com Inc.', change: 0.18, change_pct: 0.67 },
    'NIO':  { price: 3.58,   name: 'NIO Inc.', change: 0.18, change_pct: 5.29 }
  };

  async function syncPaperMarketQuotes() {
    const paths = ['data/quotes.json', './data/quotes.json', 'static/data/quotes.json'];
    for (const p of paths) {
      try {
        const res = await fetch(p);
        if (res.ok) {
          const quotes = await res.json();
          Object.keys(quotes).forEach(sym => {
            const q = quotes[sym];
            MOCK_MARKET_PRICES[sym] = {
              price: q.price,
              name: q.name || MOCK_MARKET_PRICES[sym]?.name || sym,
              change: q.change,
              change_pct: q.change_pct
            };
          });
          console.log(`[Paper Trading] Synced ${Object.keys(quotes).length} live Yahoo Finance quotes from ${p}`);
          break;
        }
      } catch (e) {}
    }
  }

  // State Store
  const state = {
    account: null,
    kpis: null,
    positions: [],
    orders: [],
    trades_history: [],
    equity_history: [],
    signal_radar: [],
    market_status: null,
    config: {
      strategy: 'blend',
      tickers: ['AAPL', 'NVDA', 'TSLA', 'MSFT', 'TSM'],
      position_size_pct: 0.20,
      stop_loss_pct: 0.04,
      take_profit_pct: 0.08,
      commission_rate: 0.0005,
      auto_matching: false
    },
    currentOrderSide: 'BUY',
    autoMatchTimer: null,
    clockTimer: null
  };

  // --- Initialization ---
  document.addEventListener('DOMContentLoaded', () => {
    initEventListeners();
    fetchPaperStatus();
    startClockTimer();

    // Auto refresh every 10s
    setInterval(() => {
      if (document.visibilityState === 'visible') {
        fetchPaperStatus(false);
      }
    }, 10000);
  });

  function startClockTimer() {
    state.clockTimer = setInterval(() => {
      updateEtClockDisplay();
    }, 1000);
  }

  function updateEtClockDisplay() {
    const el = document.getElementById('market-et-time');
    if (!el) return;
    try {
      const now = new Date();
      const options = {
        timeZone: 'America/New_York',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
      };
      const etTimeStr = new Intl.DateTimeFormat('en-US', options).format(now);
      el.textContent = `🕒 美东时间: ${etTimeStr} EDT`;
    } catch (e) {
      // fallback
    }
  }

  // --- Event Listeners ---
  function initEventListeners() {
    // Step Matching Button
    const btnStep = document.getElementById('btn-force-step');
    if (btnStep) {
      btnStep.addEventListener('click', () => {
        executeStepMatching(true);
      });
    }

    // Refresh Status Button
    const btnRefresh = document.getElementById('btn-refresh-status');
    if (btnRefresh) {
      btnRefresh.addEventListener('click', () => {
        fetchPaperStatus(true);
      });
    }

    // Reset Account Button
    const btnReset = document.getElementById('btn-reset-account');
    if (btnReset) {
      btnReset.addEventListener('click', () => {
        handleResetAccount();
      });
    }

    // Auto-Matching Toggle
    const toggleAuto = document.getElementById('auto-matching-toggle');
    if (toggleAuto) {
      toggleAuto.addEventListener('change', (e) => {
        handleToggleAutoMatching(e.target.checked);
      });
    }

    // Order Side Toggles
    const btnBuy = document.getElementById('btn-side-buy');
    const btnSell = document.getElementById('btn-side-sell');
    const btnSubmit = document.getElementById('btn-submit-order');

    if (btnBuy && btnSell && btnSubmit) {
      btnBuy.addEventListener('click', () => {
        state.currentOrderSide = 'BUY';
        btnBuy.className = 'btn-toggle-action active-buy';
        btnSell.className = 'btn-toggle-action';
        btnSubmit.className = 'btn-submit-order buy-btn';
        btnSubmit.textContent = '确认提交模拟对盘买入委托';
      });

      btnSell.addEventListener('click', () => {
        state.currentOrderSide = 'SELL';
        btnSell.className = 'btn-toggle-action active-sell';
        btnBuy.className = 'btn-toggle-action';
        btnSubmit.className = 'btn-submit-order sell-btn';
        btnSubmit.textContent = '确认提交模拟对盘卖出委托';
      });
    }

    // Submit Order Button
    if (btnSubmit) {
      btnSubmit.addEventListener('click', handleManualOrderSubmit);
    }

    // Save Config Button
    const btnSaveCfg = document.getElementById('btn-save-paper-cfg');
    if (btnSaveCfg) {
      btnSaveCfg.addEventListener('click', handleSaveConfig);
    }

    // Search Box Quick Prefill & Ticker Switch
    function sanitizePaperTicker(raw) {
      if (!raw) return "AAPL";
      let s = String(raw).trim();
      const m = s.match(/[\(（\[【]([A-Za-z0-9\.\-\^]+)[\)）\]】]/);
      if (m && m[1]) {
        const sym = m[1].toUpperCase().trim();
        if (sym.length === 6 && /^\d+$/.test(sym)) {
          if (/^(60|688|51|56|58)/.test(sym)) return `${sym}.SS`;
          if (/^(00|30|15|16)/.test(sym)) return `${sym}.SZ`;
          if (/^[849]/.test(sym)) return `${sym}.BJ`;
        }
        return sym;
      }
      const sLower = s.toLowerCase();
      const aliases = {
        '贵州茅台': '600519.SS', '茅台': '600519.SS', '600519': '600519.SS',
        '宁德时代': '300750.SZ', '宁德': '300750.SZ', '300750': '300750.SZ',
        '比亚迪': '002594.SZ', '002594': '002594.SZ',
        '平安银行': '000001.SZ', '000001': '000001.SZ',
        '中国平安': '601318.SS', '601318': '601318.SS',
        '招商银行': '600036.SS', '600036': '600036.SS',
        '中信证券': '600030.SS', '600030': '600030.SS',
        '沪深300': '510300.SS', '300etf': '510300.SS', '510300': '510300.SS',
        '上证50': '510050.SS', '50etf': '510050.SS', '510050': '510050.SS',
        '中证500': '510500.SS', '500etf': '510500.SS', '510500': '510500.SS',
        '中证1000': '512100.SS', '1000etf': '512100.SS', '512100': '512100.SS',
        '创业板指': '159915.SZ', '创业板etf': '159915.SZ', '159915': '159915.SZ',
        '腾讯': '0700.HK', '腾讯控股': '0700.HK', '0700': '0700.HK',
        '阿里巴巴': '9988.HK', '阿里': '9988.HK', '9988': '9988.HK', 'baba': 'BABA',
        '美团': '3690.HK', '3690': '3690.HK',
        '苹果': 'AAPL', '特斯拉': 'TSLA', '微软': 'MSFT', '英伟达': 'NVDA', '谷歌': 'GOOGL',
        '亚马逊': 'AMZN', 'Meta': 'META', '脸书': 'META', '标普': 'SPY', '标普500': 'SPY',
        '纳指': 'QQQ', '纳斯达克': 'QQQ'
      };
      if (aliases[sLower]) return aliases[sLower];
      for (const [k, v] of Object.entries(aliases)) {
        if (sLower === k || sLower.includes(k) || k.includes(sLower)) return v;
      }
      const numOnly = sLower.replace(/[^0-9]/g, '');
      if (numOnly.length === 6) {
        if (/^(60|688|51|56|58)/.test(numOnly)) return `${numOnly}.SS`;
        if (/^(00|30|15|16)/.test(numOnly)) return `${numOnly}.SZ`;
        if (/^[849]/.test(numOnly)) return `${numOnly}.BJ`;
      }
      if ((numOnly.length === 4 || numOnly.length === 5) && !sLower.includes('.')) {
        return `${numOnly.padStart(4, '0')}.HK`;
      }
      const cleaned = sLower.replace(/[^a-z0-9\.\-\^]/g, '').toUpperCase();
      return cleaned || "AAPL";
    }

    const searchInput = document.getElementById('custom-ticker-input');
    const searchBtn = document.getElementById('search-ticker-btn');
    const dropdown = document.getElementById('search-suggestions-dropdown');
    const searchWrap = document.getElementById('search-box-wrap') || (searchInput ? searchInput.closest('.search-box') : null);

    const closeDropdown = () => {
      if (dropdown) dropdown.classList.add('hidden');
    };

    const paperCandidates = [
      { symbol: "510300.SS", name: "华泰柏瑞沪深300 ETF", exchange: "SSE", price: 4.39, change_pct: 0.05, type: "ETF" },
      { symbol: "600519.SS", name: "贵州茅台 (白酒龙头)", exchange: "SSE", price: 1263.00, change_pct: 0.64, type: "Equity" },
      { symbol: "300750.SZ", name: "宁德时代 (动力电池龙头)", exchange: "SZSE", price: 245.50, change_pct: 1.82, type: "Equity" },
      { symbol: "002594.SZ", name: "比亚迪 (新能源汽车)", exchange: "SZSE", price: 285.20, change_pct: 1.15, type: "Equity" },
      { symbol: "000001.SZ", name: "平安银行 (商业银行标杆)", exchange: "SZSE", price: 11.59, change_pct: -0.42, type: "Equity" },
      { symbol: "0700.HK", name: "腾讯控股 (社交网络与游戏龙头)", exchange: "HKEX", price: 425.20, change_pct: 1.48, type: "Equity" },
      { symbol: "AAPL", name: "Apple Inc. (苹果公司)", exchange: "NASDAQ", price: 336.64, change_pct: -1.11, type: "Equity" },
      { symbol: "NVDA", name: "NVIDIA Corp. (英伟达)", exchange: "NASDAQ", price: 229.28, change_pct: -0.52, type: "Equity" },
      { symbol: "TSLA", name: "Tesla, Inc. (特斯拉)", exchange: "NASDAQ", price: 382.70, change_pct: 2.05, type: "Equity" },
      { symbol: "SPY", name: "SPDR S&P 500 ETF (标普500)", exchange: "NYSEArca", price: 778.57, change_pct: 0.32, type: "ETF" },
      { symbol: "QQQ", name: "Invesco QQQ Trust (纳指100)", exchange: "NASDAQ", price: 751.27, change_pct: 0.45, type: "ETF" }
    ];

    const renderPaperSuggestions = (items, isCandidatePool = false) => {
      if (!dropdown) return;
      dropdown.innerHTML = '';
      if (!items || items.length === 0) {
        dropdown.innerHTML = `<div class="suggestion-empty">未匹配到标的，直接按回车可尝试自动转换</div>`;
        dropdown.classList.remove('hidden');
        return;
      }

      const header = document.createElement('div');
      header.className = 'suggestion-header';
      header.innerHTML = isCandidatePool 
        ? `<span>🔥 热门备选标的 (点击快速对盘)</span><span class="suggestion-source-tag">Candidate Pool</span>`
        : `<span>标的检索候选列表</span><span class="suggestion-source-tag">Live Quotes</span>`;
      dropdown.appendChild(header);

      items.slice(0, 6).forEach(item => {
        const el = document.createElement('div');
        el.className = 'suggestion-item';
        const symUpper = item.symbol.toUpperCase();
        const currSign = (symUpper.endsWith('.SS') || symUpper.endsWith('.SZ') || symUpper.endsWith('.BJ')) ? '¥' : (symUpper.endsWith('.HK') ? 'HK$' : '$');
        const priceStr = item.price ? `${currSign}${Number(item.price).toFixed(2)}` : '--';
        let chgHtml = '<span class="suggestion-chg-pill flat">--</span>';
        if (item.change_pct !== undefined && item.change_pct !== null) {
          const val = Number(item.change_pct);
          chgHtml = `<span class="suggestion-chg-pill ${val >= 0 ? 'pos' : 'neg'}">${val >= 0 ? '+' : ''}${val.toFixed(2)}%</span>`;
        }

        el.innerHTML = `
          <div class="suggestion-left">
            <span class="suggestion-symbol-badge">${item.symbol}</span>
            <div class="suggestion-info">
              <span class="suggestion-name" title="${item.name}">${item.name}</span>
              <span class="suggestion-meta">${item.exchange || 'MARKET'} · ${item.type || 'Stock'}</span>
            </div>
          </div>
          <div class="suggestion-right">
            <span class="suggestion-price">${priceStr}</span>
            ${chgHtml}
          </div>
        `;

        el.addEventListener('click', (ev) => {
          ev.stopPropagation();
          const sym = item.symbol;
          if (searchInput) searchInput.value = sym;
          const orderInput = document.getElementById('order-input-ticker');
          if (orderInput) orderInput.value = sym;
          closeDropdown();
          showNotification(`已切换对盘标的: ${sym} (${item.name})`);
        });

        dropdown.appendChild(el);
      });

      dropdown.classList.remove('hidden');
    };

    const showPaperDropdown = () => {
      const q = searchInput ? searchInput.value.trim().toLowerCase() : '';
      if (!q) {
        renderPaperSuggestions(paperCandidates, true);
      } else {
        const direct = sanitizePaperTicker(q);
        const filtered = paperCandidates.filter(c => c.symbol.toLowerCase().includes(q) || c.name.toLowerCase().includes(q));
        if (direct && !filtered.some(f => f.symbol.toUpperCase() === direct.toUpperCase())) {
          filtered.unshift({
            symbol: direct,
            name: aliases[q] || direct,
            exchange: direct.endsWith('.SS') ? 'SSE' : (direct.endsWith('.SZ') ? 'SZSE' : (direct.endsWith('.HK') ? 'HKEX' : 'US')),
            price: null,
            change_pct: null,
            type: 'Equity'
          });
        }
        renderPaperSuggestions(filtered, false);
      }
    };

    const handleSwitchSearchTicker = () => {
      if (!searchInput) return;
      const raw = searchInput.value.trim();
      if (!raw) return;
      const val = sanitizePaperTicker(raw);
      searchInput.value = val;
      const orderInput = document.getElementById('order-input-ticker');
      if (orderInput) orderInput.value = val;
      closeDropdown();
      showNotification(`已切换对盘标的: ${val}`);
    };

    if (searchInput) {
      searchInput.addEventListener('focus', showPaperDropdown);
      searchInput.addEventListener('click', (e) => {
        e.stopPropagation();
        showPaperDropdown();
      });
      searchInput.addEventListener('input', showPaperDropdown);
      searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          handleSwitchSearchTicker();
        } else if (e.key === 'Escape') {
          closeDropdown();
        }
      });
    }
    if (searchBtn) {
      searchBtn.addEventListener('click', (e) => {
        e.preventDefault();
        handleSwitchSearchTicker();
      });
    }
    document.addEventListener('click', (e) => {
      if (searchWrap && !searchWrap.contains(e.target)) {
        closeDropdown();
      }
    });
  }

  // --- Client-Side Offline Engine (GitHub Pages Mode) ---

  function checkClientMarketHours() {
    const now = new Date();
    const utcHours = now.getUTCHours();
    const utcMinutes = now.getUTCMinutes();
    const utcDay = now.getUTCDay();
    const edtMinutesTotal = (utcHours - 4) * 60 + utcMinutes;
    const isWeekday = utcDay >= 1 && utcDay <= 5;
    const isMarketHours = isWeekday && edtMinutesTotal >= (9 * 60 + 30) && edtMinutesTotal < (16 * 60);

    const nowEtStr = now.toLocaleTimeString('en-US', { timeZone: 'America/New_York', hour12: false });
    const nowDateStr = now.toLocaleDateString('en-US', { timeZone: 'America/New_York' });

    if (!isWeekday) {
      return {
        is_open: false,
        status_text: "🔴 周末休市 (非美股交易日)",
        session: "WEEKEND",
        et_time: `${nowDateStr} ${nowEtStr} EDT`,
        message: "美股周末休市，系统支持在回放与测试模式下进行全功能对盘模拟"
      };
    }
    if (isMarketHours) {
      return {
        is_open: true,
        status_text: "🟢 美股连续竞价交易中 (09:30 - 16:00 EDT)",
        session: "REGULAR_MARKET",
        et_time: `${nowDateStr} ${nowEtStr} EDT`,
        message: "实时开盘对盘中，策略模型根据市价进行动态撮合"
      };
    } else if (edtMinutesTotal < (9 * 60 + 30)) {
      return {
        is_open: false,
        status_text: "🟡 盘前等待开盘 (Pre-Market)",
        session: "PRE_MARKET",
        et_time: `${nowDateStr} ${nowEtStr} EDT`,
        message: "当前处于盘前时段，开盘前支持挂单与模拟撮合验证"
      };
    } else {
      return {
        is_open: false,
        status_text: "🔴 已收盘休市 (After-Hours / Closed)",
        session: "CLOSED",
        et_time: `${nowDateStr} ${nowEtStr} EDT`,
        message: "美股今日常规时段已收盘，系统支持使用收盘价进行模拟对盘演算"
      };
    }
  }

  function getClientDefaultState(capital = 100000.0) {
    const nowIso = new Date().toISOString().replace('T', ' ').substring(0, 19);
    return {
      account: {
        initial_capital: capital,
        cash: capital,
        total_equity: capital,
        positions_market_val: 0.0,
        unrealized_pnl: 0.0,
        realized_pnl: 0.0,
        total_pnl: 0.0,
        total_return_pct: 0.0,
        daily_pnl: 0.0,
        commission_paid: 0.0,
        updated_at: nowIso
      },
      config: {
        strategy: 'blend',
        tickers: ['AAPL', 'NVDA', 'TSLA', 'MSFT', 'TSM'],
        position_size_pct: 0.20,
        stop_loss_pct: 0.04,
        take_profit_pct: 0.08,
        commission_rate: 0.0005,
        auto_matching: false
      },
      positions: {},
      orders: [],
      trades_history: [],
      equity_history: [
        {
          timestamp: nowIso,
          date: nowIso.split(' ')[0],
          equity: capital,
          cash: capital,
          benchmark: capital,
          drawdown_pct: 0.0
        }
      ],
      signal_radar: []
    };
  }

  function loadClientState() {
    let clientState = null;
    try {
      const raw = localStorage.getItem(CLIENT_STORAGE_KEY);
      if (raw) clientState = JSON.parse(raw);
    } catch (e) {}

    if (!clientState || !clientState.account) {
      clientState = getClientDefaultState();
      saveClientState(clientState);
    }

    syncClientMarkToMarket(clientState);
    return clientState;
  }

  function saveClientState(s) {
    try {
      localStorage.setItem(CLIENT_STORAGE_KEY, JSON.stringify(s));
    } catch (e) {}
  }

  function syncClientMarkToMarket(s) {
    const acc = s.account;
    const positions = s.positions || {};
    let totalMv = 0;
    let totalUnrealized = 0;

    Object.keys(positions).forEach(sym => {
      const pos = positions[sym];
      const info = MOCK_MARKET_PRICES[sym] || { price: 150.0, name: sym };
      // subtle random jitter to simulate live ticks
      const jitter = (Math.sin(Date.now() / 10000 + sym.charCodeAt(0)) * 0.002);
      const currPrice = Math.round(info.price * (1 + jitter) * 100) / 100;

      const mv = Math.round(pos.shares * currPrice * 100) / 100;
      const entryP = pos.entry_price || pos.avg_entry_price || currPrice;
      const uPnl = Math.round((currPrice - entryP) * pos.shares * 100) / 100;
      const uPct = Math.round(((currPrice - entryP) / entryP) * 10000) / 100;

      pos.current_price = currPrice;
      pos.market_value = mv;
      pos.unrealized_pnl = uPnl;
      pos.unrealized_pnl_pct = uPct;
      pos.pnl_pct = uPct;
      pos.entry_price = entryP;
      pos.company_name = pos.name || info.name || sym;

      totalMv += mv;
      totalUnrealized += uPnl;
    });

    acc.positions_market_val = Math.round(totalMv * 100) / 100;
    acc.unrealized_pnl = Math.round(totalUnrealized * 100) / 100;
    acc.total_equity = Math.round((acc.cash + totalMv) * 100) / 100;

    const initCap = acc.initial_capital || 100000.0;
    acc.total_return_pct = Math.round(((acc.total_equity - initCap) / initCap) * 10000) / 100;
    acc.total_pnl = Math.round((acc.total_equity - initCap) * 100) / 100;
    acc.updated_at = new Date().toISOString().replace('T', ' ').substring(0, 19);

    // Update equity history
    const hist = s.equity_history || [];
    const nowIso = acc.updated_at;
    if (hist.length > 0) {
      const last = hist[hist.length - 1];
      if (last.timestamp.substring(0, 16) === nowIso.substring(0, 16)) {
        last.equity = acc.total_equity;
        last.cash = acc.cash;
      } else {
        hist.push({
          timestamp: nowIso,
          date: nowIso.split(' ')[0],
          equity: acc.total_equity,
          cash: acc.cash,
          benchmark: initCap,
          drawdown_pct: 0.0
        });
        if (hist.length > 120) hist.shift();
      }
    }
  }

  function computeClientKPIs(s) {
    const acc = s.account;
    const trades = s.trades_history || [];
    const wins = trades.filter(t => t.pnl > 0);
    const losses = trades.filter(t => t.pnl < 0);
    const winRate = trades.length > 0 ? (wins.length / trades.length) * 100 : 0;
    const grossProfit = wins.reduce((acc, t) => acc + t.pnl, 0);
    const grossLoss = Math.abs(losses.reduce((acc, t) => acc + t.pnl, 0));
    const profitFactor = grossLoss > 0 ? (grossProfit / grossLoss) : (grossProfit > 0 ? 99.0 : 0.0);

    return {
      total_equity: acc.total_equity,
      cash: acc.cash,
      market_value: acc.positions_market_val,
      total_return_pct: acc.total_return_pct,
      total_pnl: acc.total_pnl,
      unrealized_pnl: acc.unrealized_pnl,
      realized_pnl: acc.realized_pnl,
      win_rate_pct: winRate,
      profit_factor: profitFactor,
      total_trades: trades.length,
      winning_trades: wins.length,
      losing_trades: losses.length,
      max_drawdown_pct: 0.0
    };
  }

  function computeClientRadarSignals(tickers) {
    return tickers.map(sym => {
      const info = MOCK_MARKET_PRICES[sym] || { price: 150.0, name: sym, change: 0.5 };
      const seed = Math.sin(Date.now() / 60000 + sym.charCodeAt(0) * 13);
      let signal = 'HOLD';
      let reason = '动量均值回归整理中';
      if (seed > 0.35) {
        signal = 'BUY';
        reason = '多因子动量共振突破 20 日均线';
      } else if (seed < -0.35) {
        signal = 'SELL';
        reason = '短期波动率偏离过大提示减仓';
      }
      return {
        ticker: sym,
        price: info.price,
        signal: signal,
        score: Math.round(seed * 100) / 100,
        reason: reason
      };
    });
  }

  // --- API Calls & GitHub Pages Fallbacks ---

  async function fetchPaperStatus(showFeedback = false) {
    try {
      const res = await fetch('/api/paper/status');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      if (data.status === 'success') {
        isClientMode = false;
        state.account = data.account;
        state.kpis = data.kpis;
        state.positions = data.positions || [];
        state.orders = data.orders || [];
        state.trades_history = data.trades_history || [];
        state.equity_history = data.equity_history || [];
        state.signal_radar = data.signal_radar || [];
        state.market_status = data.market_status;
        state.config = data.config || state.config;

        const pingText = document.getElementById('server-ping-text');
        if (pingText) pingText.textContent = '撮合引擎已就绪';

        renderAll();
        if (showFeedback) showNotification('模拟账户数据已刷新');
        return;
      }
    } catch (err) {
      // Backend unavailable: Seamlessly switch to Client Mode
      isClientMode = true;
      const cState = loadClientState();
      cState.market_status = checkClientMarketHours();
      cState.kpis = computeClientKPIs(cState);
      cState.signal_radar = computeClientRadarSignals(cState.config.tickers);
      saveClientState(cState);

      state.account = cState.account;
      state.kpis = cState.kpis;
      state.positions = Object.values(cState.positions);
      state.orders = cState.orders;
      state.trades_history = cState.trades_history;
      state.equity_history = cState.equity_history;
      state.signal_radar = cState.signal_radar;
      state.market_status = cState.market_status;
      state.config = cState.config;

      const pingText = document.getElementById('server-ping-text');
      if (pingText) pingText.textContent = 'GitHub Pages 纯前端对盘模式';

      renderAll();
      if (showFeedback) showNotification('本地模拟账户已刷新 (离线存储)');
    }
  }

  async function executeStepMatching(forceStep = true) {
    const btnStep = document.getElementById('btn-force-step');
    if (btnStep) {
      btnStep.disabled = true;
      btnStep.innerHTML = `<span class="pulse-indicator-dot"></span> 撮合演算中...`;
    }

    if (!isClientMode) {
      try {
        const res = await fetch('/api/paper/step', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ force_step: forceStep })
        });
        const data = await res.json();
        if (data.status === 'success') {
          const matchesCount = data.matched_orders ? data.matched_orders.length : 0;
          showNotification(
            matchesCount > 0
              ? `撮合完成：执行了 ${matchesCount} 笔模型对盘交易`
              : '撮合完成：当前所有标的维持持仓或无新触发信号'
          );
          fetchPaperStatus();
        } else {
          showNotification(data.message || '对盘撮合已执行', 'info');
          fetchPaperStatus();
        }
      } catch (err) {
        console.warn('Backend step matching failed, falling back to client-side matching:', err);
        runClientStepMatching();
      } finally {
        restoreBtnStep(btnStep);
      }
    } else {
      setTimeout(() => {
        runClientStepMatching();
        restoreBtnStep(btnStep);
      }, 300);
    }
  }

  function restoreBtnStep(btnStep) {
    if (btnStep) {
      btnStep.disabled = false;
      btnStep.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polygon points="5 3 19 12 5 21 5 3"></polygon>
        </svg>
        单步对盘撮合
      `;
    }
  }

  function runClientStepMatching() {
    const cState = loadClientState();
    const cfg = cState.config;
    const tickers = cfg.tickers || ['AAPL', 'NVDA', 'TSLA', 'MSFT', 'TSM'];
    const radar = computeClientRadarSignals(tickers);
    cState.signal_radar = radar;

    let matchedCount = 0;
    radar.forEach(sig => {
      const sym = sig.ticker;
      const currP = sig.price;
      const pos = cState.positions[sym];

      // Stop Loss / Take Profit check
      if (pos) {
        const slPrice = pos.stop_loss_price;
        const tpPrice = pos.take_profit_price;
        if (slPrice && currP <= slPrice) {
          executeClientOrder(cState, sym, 'SELL', pos.shares, currP, `触发止损保护 (${(cfg.stop_loss_pct * 100).toFixed(1)}%)`, 'RiskControl');
          matchedCount++;
          return;
        }
        if (tpPrice && currP >= tpPrice) {
          executeClientOrder(cState, sym, 'SELL', pos.shares, currP, `达到止盈目标 (${(cfg.take_profit_pct * 100).toFixed(1)}%)`, 'TakeProfit');
          matchedCount++;
          return;
        }
      }

      // Signal Trigger
      if (sig.signal === 'BUY' && !pos) {
        const maxInvest = cState.account.total_equity * (cfg.position_size_pct || 0.20);
        const shares = Math.floor(maxInvest / currP);
        if (shares > 0 && (shares * currP) <= cState.account.cash) {
          executeClientOrder(cState, sym, 'BUY', shares, currP, sig.reason, cfg.strategy.toUpperCase());
          matchedCount++;
        }
      } else if (sig.signal === 'SELL' && pos) {
        executeClientOrder(cState, sym, 'SELL', pos.shares, currP, sig.reason, cfg.strategy.toUpperCase());
        matchedCount++;
      }
    });

    syncClientMarkToMarket(cState);
    cState.kpis = computeClientKPIs(cState);
    saveClientState(cState);

    state.account = cState.account;
    state.kpis = cState.kpis;
    state.positions = Object.values(cState.positions);
    state.orders = cState.orders;
    state.trades_history = cState.trades_history;
    state.equity_history = cState.equity_history;
    state.signal_radar = cState.signal_radar;

    renderAll();
    showNotification(
      matchedCount > 0
        ? `撮合完成：执行了 ${matchedCount} 笔模型对盘交易`
        : '撮合完成：当前所有标的维持持仓或无新触发信号'
    );
  }

  function executeClientOrder(cState, ticker, action, shares, price, reason, strategy) {
    const acc = cState.account;
    const posMap = cState.positions;
    const sym = ticker.toUpperCase();
    const info = MOCK_MARKET_PRICES[sym] || { price: price || 150.0, name: sym };
    const execPrice = Math.round((price || info.price) * 100) / 100;
    const totalVal = Math.round(shares * execPrice * 100) / 100;
    const comm = Math.round(Math.max(1.0, totalVal * (cState.config.commission_rate || 0.0005)) * 100) / 100;
    const nowIso = new Date().toISOString().replace('T', ' ').substring(0, 19);
    const ordId = `ORD-${cState.orders.length + 1001}`;

    if (action === 'BUY') {
      const totalCost = totalVal + comm;
      if (totalCost > acc.cash) return false;
      acc.cash = Math.round((acc.cash - totalCost) * 100) / 100;
      acc.commission_paid = Math.round(((acc.commission_paid || 0) + comm) * 100) / 100;

      const slPct = cState.config.stop_loss_pct || 0.04;
      const tpPct = cState.config.take_profit_pct || 0.08;

      posMap[sym] = {
        ticker: sym,
        name: info.name,
        company_name: info.name,
        shares: shares,
        entry_price: execPrice,
        avg_entry_price: execPrice,
        current_price: execPrice,
        market_value: totalVal,
        unrealized_pnl: 0.0,
        unrealized_pnl_pct: 0.0,
        pnl_pct: 0.0,
        entry_time: nowIso,
        strategy: strategy,
        stop_loss_price: Math.round(execPrice * (1.0 - slPct) * 100) / 100,
        take_profit_price: Math.round(execPrice * (1.0 + tpPct) * 100) / 100
      };

      cState.orders.unshift({
        order_id: ordId,
        timestamp: nowIso,
        ticker: sym,
        action: 'BUY',
        shares: shares,
        price: execPrice,
        commission: comm,
        total_amount: totalVal,
        reason: reason,
        strategy: strategy
      });
      return true;
    } else if (action === 'SELL') {
      if (!posMap[sym] || posMap[sym].shares < shares) return false;
      const curPos = posMap[sym];
      const netProceeds = totalVal - comm;
      acc.cash = Math.round((acc.cash + netProceeds) * 100) / 100;
      acc.commission_paid = Math.round(((acc.commission_paid || 0) + comm) * 100) / 100;

      const pnl = Math.round(((execPrice - curPos.entry_price) * shares - comm) * 100) / 100;
      const pnlPct = Math.round(((execPrice - curPos.entry_price) / curPos.entry_price) * 10000) / 100;
      acc.realized_pnl = Math.round(((acc.realized_pnl || 0) + pnl) * 100) / 100;

      cState.trades_history.unshift({
        trade_id: cState.trades_history.length + 1,
        ticker: sym,
        entry_time: curPos.entry_time,
        exit_time: nowIso,
        entry_price: curPos.entry_price,
        exit_price: execPrice,
        shares: shares,
        pnl: pnl,
        pnl_pct: pnlPct,
        commission: comm,
        reason: reason,
        strategy: strategy
      });

      cState.orders.unshift({
        order_id: ordId,
        timestamp: nowIso,
        ticker: sym,
        action: 'SELL',
        shares: shares,
        price: execPrice,
        commission: comm,
        total_amount: totalVal,
        reason: reason,
        strategy: strategy
      });

      if (shares >= curPos.shares) {
        delete posMap[sym];
      } else {
        curPos.shares -= shares;
        curPos.market_value = Math.round(curPos.shares * execPrice * 100) / 100;
        curPos.unrealized_pnl = Math.round((execPrice - curPos.entry_price) * curPos.shares * 100) / 100;
        curPos.unrealized_pnl_pct = Math.round(((execPrice - curPos.entry_price) / curPos.entry_price) * 10000) / 100;
      }
      return true;
    }
    return false;
  }

  async function handleManualOrderSubmit() {
    const tickerInput = document.getElementById('order-input-ticker');
    const sharesInput = document.getElementById('order-input-shares');
    const priceInput = document.getElementById('order-input-price');
    const reasonInput = document.getElementById('order-input-reason');

    const ticker = tickerInput ? tickerInput.value.trim().toUpperCase() : '';
    const shares = sharesInput ? parseInt(sharesInput.value) : 0;
    const price = priceInput && priceInput.value ? parseFloat(priceInput.value) : null;
    const reason = reasonInput && reasonInput.value.trim() ? reasonInput.value.trim() : '交易员手工委托';

    if (!ticker) {
      alert('请输入有效的标的代码 (如 AAPL)');
      return;
    }
    if (isNaN(shares) || shares <= 0) {
      alert('委托股数必须为大于 0 的整数');
      return;
    }

    if (!isClientMode) {
      try {
        const res = await fetch('/api/paper/order', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            ticker: ticker,
            action: state.currentOrderSide,
            shares: shares,
            price: price,
            reason: reason,
            strategy: 'Manual'
          })
        });
        const data = await res.json();
        if (data.status === 'success') {
          showNotification(`委托成功: ${data.order.action} ${data.order.shares}股 ${data.order.ticker} @ $${data.order.price.toFixed(2)}`);
          fetchPaperStatus();
          return;
        } else {
          alert(`委托失败: ${data.message}`);
          return;
        }
      } catch (err) {
        console.warn('Backend order submission failed, running client-side:', err);
      }
    }

    // Client Mode execution
    const cState = loadClientState();
    const ok = executeClientOrder(cState, ticker, state.currentOrderSide, shares, price, reason, 'Manual');
    if (ok) {
      syncClientMarkToMarket(cState);
      cState.kpis = computeClientKPIs(cState);
      saveClientState(cState);

      state.account = cState.account;
      state.kpis = cState.kpis;
      state.positions = Object.values(cState.positions);
      state.orders = cState.orders;
      state.trades_history = cState.trades_history;
      renderAll();
      showNotification(`委托成功: ${state.currentOrderSide} ${shares}股 ${ticker}`);
    } else {
      alert('委托失败: 可用资金不足或无可卖持仓');
    }
  }

  async function handleClosePosition(ticker) {
    if (!confirm(`确定要市价平仓当前 ${ticker} 的所有持仓吗？`)) {
      return;
    }

    if (!isClientMode) {
      try {
        const res = await fetch('/api/paper/close_position', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ticker: ticker, reason: '一键市价平仓' })
        });
        const data = await res.json();
        if (data.status === 'success') {
          showNotification(`已平仓 ${ticker}，实现盈亏: $${data.closed_trade.pnl >= 0 ? '+' : ''}${data.closed_trade.pnl.toFixed(2)}`);
          fetchPaperStatus();
          return;
        }
      } catch (err) {
        console.warn('Backend close position failed, running client-side:', err);
      }
    }

    // Client Mode execution
    const cState = loadClientState();
    const pos = cState.positions[ticker];
    if (pos) {
      executeClientOrder(cState, ticker, 'SELL', pos.shares, pos.current_price, '一键市价平仓', 'Manual');
      syncClientMarkToMarket(cState);
      cState.kpis = computeClientKPIs(cState);
      saveClientState(cState);

      state.account = cState.account;
      state.kpis = cState.kpis;
      state.positions = Object.values(cState.positions);
      state.orders = cState.orders;
      state.trades_history = cState.trades_history;
      renderAll();
      showNotification(`已平仓 ${ticker}`);
    }
  }

  async function handleResetAccount() {
    if (!confirm('警告：此操作将清空模拟交易的所有持仓头寸、成交流水并恢复初始本金 $100,000。是否确认重置？')) {
      return;
    }

    if (!isClientMode) {
      try {
        const res = await fetch('/api/paper/reset', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ initial_capital: 100000.0 })
        });
        const data = await res.json();
        if (data.status === 'success') {
          showNotification('模拟账户已成功重置！');
          fetchPaperStatus();
          return;
        }
      } catch (err) {}
    }

    const cState = getClientDefaultState(100000.0);
    cState.market_status = checkClientMarketHours();
    cState.kpis = computeClientKPIs(cState);
    cState.signal_radar = computeClientRadarSignals(cState.config.tickers);
    saveClientState(cState);

    state.account = cState.account;
    state.kpis = cState.kpis;
    state.positions = [];
    state.orders = [];
    state.trades_history = [];
    state.equity_history = cState.equity_history;
    state.signal_radar = cState.signal_radar;

    renderAll();
    showNotification('模拟账户已成功重置！');
  }

  async function handleToggleAutoMatching(enabled) {
    state.config.auto_matching = enabled;

    if (!isClientMode) {
      try {
        await fetch('/api/paper/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ auto_matching: enabled })
        });
      } catch (e) {}
    }

    if (enabled) {
      showNotification('自动对盘撮合已启动 (每15秒轮询撮合)');
      if (state.autoMatchTimer) clearInterval(state.autoMatchTimer);
      state.autoMatchTimer = setInterval(() => {
        executeStepMatching(false);
      }, 15000);
    } else {
      showNotification('自动对盘撮合已暂停');
      if (state.autoMatchTimer) {
        clearInterval(state.autoMatchTimer);
        state.autoMatchTimer = null;
      }
    }
  }

  async function handleSaveConfig() {
    const stratSel = document.getElementById('cfg-paper-strategy');
    const tickersInput = document.getElementById('cfg-paper-tickers');
    const posSizeInput = document.getElementById('cfg-paper-pos-size');
    const stopLossInput = document.getElementById('cfg-paper-stop-loss');
    const takeProfitInput = document.getElementById('cfg-paper-take-profit');
    const commInput = document.getElementById('cfg-paper-commission');

    const strategy = stratSel ? stratSel.value : 'blend';
    const rawTickers = tickersInput ? tickersInput.value : '';
    const tickers = rawTickers.split(/[,，\s]+/).map(s => s.trim().toUpperCase()).filter(Boolean);
    const posSize = posSizeInput ? parseFloat(posSizeInput.value) / 100.0 : 0.20;
    const stopLoss = stopLossInput ? parseFloat(stopLossInput.value) / 100.0 : 0.04;
    const takeProfit = takeProfitInput ? parseFloat(takeProfitInput.value) / 100.0 : 0.08;
    const commission = commInput ? parseFloat(commInput.value) / 100.0 : 0.0005;

    const payload = {
      strategy: strategy,
      tickers: tickers.length > 0 ? tickers : ['AAPL', 'NVDA', 'TSLA', 'MSFT', 'TSM'],
      position_size_pct: posSize,
      stop_loss_pct: stopLoss,
      take_profit_pct: takeProfit,
      commission_rate: commission
    };

    if (!isClientMode) {
      try {
        const res = await fetch('/api/paper/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.status === 'success') {
          showNotification('参数配置已成功保存并应用！');
          state.config = Object.assign(state.config, payload);
          fetchPaperStatus();
          return;
        }
      } catch (err) {}
    }

    const cState = loadClientState();
    cState.config = Object.assign(cState.config, payload);
    saveClientState(cState);
    state.config = cState.config;
    showNotification('参数配置已成功保存并应用！');
    fetchPaperStatus();
  }

  // --- Render Functions ---

  function renderAll() {
    renderMarketStatus();
    renderKPIs();
    renderPositionsTable();
    renderOrdersTable();
    renderSignalRadar();
    renderEquityChart();
    renderConfigInputs();
  }

  function renderMarketStatus() {
    const ms = state.market_status;
    const pill = document.getElementById('market-pulse-pill');
    const statusText = document.getElementById('market-status-text');
    const sessionMsg = document.getElementById('market-session-msg');

    if (!ms || !pill) return;

    if (ms.is_open) {
      pill.className = 'market-pulse-pill open';
      if (statusText) statusText.textContent = ms.status_text || '美股连续竞价交易中';
    } else if (ms.session === 'PRE_MARKET') {
      pill.className = 'market-pulse-pill pre';
      if (statusText) statusText.textContent = ms.status_text || '美股盘前等待开盘';
    } else {
      pill.className = 'market-pulse-pill closed';
      if (statusText) statusText.textContent = ms.status_text || '已收盘休市';
    }

    if (sessionMsg && ms.message) {
      sessionMsg.textContent = ms.message;
    }
  }

  function renderKPIs() {
    const acc = state.account;
    const kpi = state.kpis;
    if (!acc || !kpi) return;

    const elEquity = document.getElementById('kpi-total-equity');
    if (elEquity) elEquity.textContent = `$${formatNumber(acc.total_equity, 2)}`;

    const elInitCap = document.getElementById('kpi-initial-cap');
    if (elInitCap) elInitCap.textContent = `初始本金: $${formatNumber(acc.initial_capital, 2)}`;

    const elReturn = document.getElementById('kpi-total-return');
    if (elReturn) {
      const ret = acc.total_return_pct || 0;
      const isPos = ret >= 0;
      elReturn.textContent = `${isPos ? '+' : ''}${ret.toFixed(2)}%`;
      elReturn.className = `kpi-number ${isPos ? 'pos' : 'neg'}`;
    }

    const elTotalPnl = document.getElementById('kpi-total-pnl');
    if (elTotalPnl) {
      const pnl = acc.total_pnl || 0;
      elTotalPnl.textContent = `总盈亏: ${pnl >= 0 ? '+' : ''}$${formatNumber(pnl, 2)}`;
      elTotalPnl.style.color = pnl >= 0 ? '#059669' : '#dc2626';
    }

    const elCash = document.getElementById('kpi-cash');
    if (elCash) elCash.textContent = `$${formatNumber(acc.cash, 2)}`;

    const elMktVal = document.getElementById('kpi-market-val');
    if (elMktVal) elMktVal.textContent = `持仓市值: $${formatNumber(acc.positions_market_val, 2)}`;

    const elUnreal = document.getElementById('kpi-unrealized-pnl');
    if (elUnreal) {
      const unpnl = acc.unrealized_pnl || 0;
      elUnreal.textContent = `${unpnl >= 0 ? '+' : ''}$${formatNumber(unpnl, 2)}`;
      elUnreal.className = `kpi-number ${unpnl >= 0 ? 'pos' : 'neg'}`;
    }

    const elReal = document.getElementById('kpi-realized-pnl');
    if (elReal) {
      const rpnl = acc.realized_pnl || 0;
      elReal.textContent = `${rpnl >= 0 ? '+' : ''}$${formatNumber(rpnl, 2)}`;
      elReal.className = `kpi-number ${rpnl >= 0 ? 'pos' : 'neg'}`;
    }

    const elComm = document.getElementById('kpi-commission-paid');
    if (elComm) elComm.textContent = `已付佣金: $${formatNumber(acc.commission_paid, 2)}`;

    const elWinRate = document.getElementById('kpi-win-rate');
    if (elWinRate) {
      elWinRate.textContent = `${kpi.win_rate_pct.toFixed(1)}%`;
      elWinRate.className = `kpi-number ${kpi.win_rate_pct >= 50 ? 'pos' : ''}`;
    }

    const elWinRatio = document.getElementById('kpi-win-ratio');
    if (elWinRatio) elWinRatio.textContent = `盈利/亏损: ${kpi.winning_trades} / ${kpi.losing_trades}`;

    const elPf = document.getElementById('kpi-profit-factor');
    if (elPf) elPf.textContent = kpi.profit_factor.toFixed(2);

    const elMaxDd = document.getElementById('kpi-max-drawdown');
    if (elMaxDd) elMaxDd.textContent = `最大回撤: ${kpi.max_drawdown_pct.toFixed(2)}%`;
  }

  function renderPositionsTable() {
    const tbody = document.getElementById('positions-table-body');
    const badge = document.getElementById('positions-count-badge');
    if (!tbody) return;

    const positions = state.positions || [];
    if (badge) badge.textContent = `${positions.length} 只持仓`;

    if (positions.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="11" style="text-align: center; color: var(--text-muted); padding: 32px;">
            暂无持仓头寸。点击上方“单步对盘撮合”或右侧手工对盘以开仓。
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = positions.map(pos => {
      const isPos = (pos.unrealized_pnl || 0) >= 0;
      const pnlColor = isPos ? '#059669' : '#dc2626';
      const pnlPrefix = isPos ? '+' : '';
      const entryP = pos.entry_price || pos.avg_entry_price || 0;

      return `
        <tr>
          <td><span class="radar-symbol-badge">${escapeHtml(pos.ticker)}</span></td>
          <td><span style="font-weight: 500;">${escapeHtml(pos.company_name || pos.name || pos.ticker)}</span></td>
          <td class="mono"><strong>${pos.shares}</strong> 股</td>
          <td class="mono">$${entryP.toFixed(2)}</td>
          <td class="mono" style="font-weight: 700;">$${(pos.current_price || 0).toFixed(2)}</td>
          <td class="mono">$${formatNumber(pos.market_value, 2)}</td>
          <td class="mono" style="color: ${pnlColor}; font-weight: 700;">
            ${pnlPrefix}$${formatNumber(pos.unrealized_pnl, 2)}
          </td>
          <td class="mono" style="color: ${pnlColor}; font-weight: 700;">
            ${pnlPrefix}${(pos.pnl_pct || pos.unrealized_pnl_pct || 0).toFixed(2)}%
          </td>
          <td class="mono" style="color: #dc2626;">$${pos.stop_loss_price ? pos.stop_loss_price.toFixed(2) : '--'}</td>
          <td class="mono" style="color: #059669;">$${pos.take_profit_price ? pos.take_profit_price.toFixed(2) : '--'}</td>
          <td>
            <button class="btn-table-action close-pos" onclick="window.AlphaPaper.closePos('${pos.ticker}')">
              市价平仓
            </button>
          </td>
        </tr>
      `;
    }).join('');
  }

  function renderOrdersTable() {
    const tbody = document.getElementById('orders-table-body');
    const label = document.getElementById('orders-count-label');
    if (!tbody) return;

    const orders = state.orders || [];
    if (label) label.textContent = `共 ${orders.length} 笔对盘记录`;

    if (orders.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="9" style="text-align: center; color: var(--text-muted); padding: 28px;">
            暂无历史成交流水。
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = orders.map(ord => {
      const isBuy = ord.action === 'BUY';
      const actionBadge = isBuy
        ? `<span class="badge-order-action buy">买入 BUY</span>`
        : `<span class="badge-order-action sell">卖出 SELL</span>`;

      const fees = (ord.commission || 0) + (ord.slippage || 0);

      return `
        <tr>
          <td class="mono" style="font-size: 11px; color: var(--text-secondary);">${escapeHtml(ord.timestamp)}</td>
          <td class="mono" style="font-size: 11px; color: var(--text-muted);">${escapeHtml(ord.order_id || '')}</td>
          <td><strong class="mono">${escapeHtml(ord.ticker)}</strong></td>
          <td>${actionBadge}</td>
          <td class="mono">${ord.shares}</td>
          <td class="mono" style="font-weight: 700;">$${ord.price.toFixed(2)}</td>
          <td class="mono" style="color: var(--text-muted);">$${fees.toFixed(2)}</td>
          <td class="mono">$${formatNumber(ord.total_amount, 2)}</td>
          <td style="font-size: 12px; color: var(--text-secondary);">
            <span style="font-weight: 600; color: var(--text-primary);">${escapeHtml(ord.strategy || 'Model')}:</span>
            ${escapeHtml(ord.reason || '')}
          </td>
        </tr>
      `;
    }).join('');
  }

  function renderSignalRadar() {
    const container = document.getElementById('radar-signals-list');
    const badge = document.getElementById('radar-strategy-badge');
    if (!container) return;

    if (badge && state.config) {
      badge.textContent = state.config.strategy.toUpperCase();
    }

    const signals = state.signal_radar || [];
    if (signals.length === 0) {
      container.innerHTML = `
        <div style="text-align: center; color: var(--text-muted); padding: 18px;">
          暂无雷达信号。点击上方“单步对盘撮合”以触发全标的扫描。
        </div>
      `;
      return;
    }

    container.innerHTML = signals.map(sig => {
      let badgeClass = 'radar-signal-badge hold';
      let badgeText = '观望 HOLD';
      if (sig.signal === 'BUY') {
        badgeClass = 'radar-signal-badge buy';
        badgeText = '多头买入 BUY';
      } else if (sig.signal === 'SELL') {
        badgeClass = 'radar-signal-badge sell';
        badgeText = '空头卖出 SELL';
      }

      const scorePct = Math.min(100, Math.max(0, Math.round(((sig.score + 1) / 2) * 100)));

      return `
        <div class="radar-item">
          <div class="radar-item-left">
            <span class="radar-symbol-badge">${escapeHtml(sig.ticker)}</span>
            <div style="display: flex; flex-direction: column; gap: 2px;">
              <div style="display: flex; align-items: center; gap: 6px;">
                <span class="${badgeClass}">${badgeText}</span>
                <span class="mono" style="font-weight: 700; font-size: 12.5px;">$${sig.price.toFixed(2)}</span>
              </div>
              <span style="font-size: 11px; color: var(--text-secondary);">${escapeHtml(sig.reason || '')}</span>
            </div>
          </div>
          <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 4px;">
            <span style="font-size: 10.5px; font-weight: 700; color: var(--text-muted);">置信度: ${scorePct}%</span>
            <button class="btn-table-action" onclick="window.AlphaPaper.prefillOrder('${sig.ticker}', '${sig.signal}')" style="font-size: 10.5px; padding: 2px 7px;">
              填入委托
            </button>
          </div>
        </div>
      `;
    }).join('');
  }

  function renderConfigInputs() {
    const cfg = state.config;
    if (!cfg) return;

    const autoToggle = document.getElementById('auto-matching-toggle');
    if (autoToggle) autoToggle.checked = Boolean(cfg.auto_matching);

    const stratSel = document.getElementById('cfg-paper-strategy');
    if (stratSel && cfg.strategy) stratSel.value = cfg.strategy;

    const tickersInput = document.getElementById('cfg-paper-tickers');
    if (tickersInput && cfg.tickers) tickersInput.value = cfg.tickers.join(', ');

    const posSizeInput = document.getElementById('cfg-paper-pos-size');
    if (posSizeInput && cfg.position_size_pct) posSizeInput.value = (cfg.position_size_pct * 100).toFixed(0);

    const stopLossInput = document.getElementById('cfg-paper-stop-loss');
    if (stopLossInput && cfg.stop_loss_pct) stopLossInput.value = (cfg.stop_loss_pct * 100).toFixed(1);

    const takeProfitInput = document.getElementById('cfg-paper-take-profit');
    if (takeProfitInput && cfg.take_profit_pct) takeProfitInput.value = (cfg.take_profit_pct * 100).toFixed(1);

    const commInput = document.getElementById('cfg-paper-commission');
    if (commInput && cfg.commission_rate) commInput.value = (cfg.commission_rate * 100).toFixed(2);
  }

  // --- High DPI Equity Curve Canvas Chart ---

  function renderEquityChart() {
    const canvas = document.getElementById('paper-equity-chart');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();

    if (rect.width === 0 || rect.height === 0) return;

    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const width = rect.width;
    const height = rect.height;

    ctx.clearRect(0, 0, width, height);

    const history = state.equity_history || [];
    if (history.length === 0) {
      ctx.fillStyle = '#64748b';
      ctx.font = '13px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('正在构建模拟对盘资产净值走势...', width / 2, height / 2);
      return;
    }

    const padding = { top: 20, right: 30, bottom: 40, left: 75 };
    const chartW = width - padding.left - padding.right;
    const chartH = height - padding.top - padding.bottom;

    const equities = history.map(h => h.equity);
    const benchmarks = history.map(h => h.benchmark || history[0].equity);

    let minVal = Math.min(...equities, ...benchmarks);
    let maxVal = Math.max(...equities, ...benchmarks);

    const range = maxVal - minVal || 1000;
    minVal = Math.floor(minVal - range * 0.08);
    maxVal = Math.ceil(maxVal + range * 0.08);

    // Grid & Y-Ticks
    const yTicks = 5;
    ctx.strokeStyle = '#f1f5f9';
    ctx.lineWidth = 1;
    ctx.fillStyle = '#94a3b8';
    ctx.font = '11px "JetBrains Mono", monospace';
    ctx.textAlign = 'right';

    for (let i = 0; i <= yTicks; i++) {
      const yVal = minVal + (maxVal - minVal) * (i / yTicks);
      const yPos = padding.top + chartH - (i / yTicks) * chartH;

      ctx.beginPath();
      ctx.moveTo(padding.left, yPos);
      ctx.lineTo(width - padding.right, yPos);
      ctx.stroke();

      ctx.fillText(`$${formatNumber(yVal, 0)}`, padding.left - 10, yPos + 4);
    }

    // Benchmark Dashed Line
    ctx.save();
    ctx.setLineDash([4, 4]);
    ctx.strokeStyle = '#DDD9CD';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    history.forEach((pt, idx) => {
      const x = padding.left + (idx / (history.length - 1 || 1)) * chartW;
      const bVal = pt.benchmark || history[0].equity;
      const y = padding.top + chartH - ((bVal - minVal) / (maxVal - minVal)) * chartH;
      if (idx === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
    ctx.restore();

    // Portfolio Equity Line & Gradient (Claude Terracotta)
    const gradient = ctx.createLinearGradient(0, padding.top, 0, padding.top + chartH);
    gradient.addColorStop(0, 'rgba(217, 119, 87, 0.22)');
    gradient.addColorStop(1, 'rgba(217, 119, 87, 0.00)');

    ctx.beginPath();
    history.forEach((pt, idx) => {
      const x = padding.left + (idx / (history.length - 1 || 1)) * chartW;
      const y = padding.top + chartH - ((pt.equity - minVal) / (maxVal - minVal)) * chartH;
      if (idx === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });

    ctx.strokeStyle = '#D97757';
    ctx.lineWidth = 2.5;
    ctx.stroke();

    ctx.lineTo(padding.left + chartW, padding.top + chartH);
    ctx.lineTo(padding.left, padding.top + chartH);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();

    if (history.length > 0) {
      const last = history[history.length - 1];
      const lastX = padding.left + chartW;
      const lastY = padding.top + chartH - ((last.equity - minVal) / (maxVal - minVal)) * chartH;

      ctx.beginPath();
      ctx.arc(lastX, lastY, 4.5, 0, Math.PI * 2);
      ctx.fillStyle = '#D97757';
      ctx.fill();
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 2;
      ctx.stroke();
    }

    ctx.fillStyle = '#787774';
    ctx.font = '10.5px "JetBrains Mono", monospace';
    ctx.textAlign = 'center';

    const numXTicks = Math.min(5, history.length);
    for (let i = 0; i < numXTicks; i++) {
      const idx = Math.floor(i * (history.length - 1) / (numXTicks - 1 || 1));
      const pt = history[idx];
      const x = padding.left + (idx / (history.length - 1 || 1)) * chartW;
      const timeStr = pt.timestamp ? pt.timestamp.split(' ')[1] || pt.timestamp : '';
      ctx.fillText(timeStr, x, height - padding.bottom + 18);
    }

    const stampEl = document.getElementById('equity-update-stamp');
    if (stampEl && history.length > 0) {
      stampEl.textContent = `最近净值: $${formatNumber(history[history.length - 1].equity, 2)} (${history[history.length - 1].timestamp})`;
    }
  }

  // --- Helpers ---

  function formatNumber(num, decimals = 2) {
    if (num === null || num === undefined || isNaN(num)) return '0.00';
    return Number(num).toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals
    });
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function showNotification(msg, type = 'success') {
    const div = document.createElement('div');
    div.className = 'paper-notification';
    div.style.position = 'fixed';
    div.style.bottom = '24px';
    div.style.right = '24px';
    div.style.padding = '12px 20px';
    div.style.borderRadius = '8px';
    div.style.background = type === 'error' ? '#dc2626' : (type === 'info' ? '#0284c7' : '#0f172a');
    div.style.color = '#ffffff';
    div.style.fontSize = '13px';
    div.style.fontWeight = '600';
    div.style.boxShadow = '0 10px 25px -5px rgba(0,0,0,0.3)';
    div.style.zIndex = '9999';
    div.style.transition = 'all 0.25s ease';
    div.style.opacity = '0';
    div.style.transform = 'translateY(10px)';
    div.textContent = msg;

    document.body.appendChild(div);

    setTimeout(() => {
      div.style.opacity = '1';
      div.style.transform = 'translateY(0)';
    }, 10);

    setTimeout(() => {
      div.style.opacity = '0';
      div.style.transform = 'translateY(10px)';
      setTimeout(() => div.remove(), 300);
    }, 3500);
  }

  // Public Interface for Inline HTML Handlers
  window.AlphaPaper = {
    closePos: handleClosePosition,
    prefillOrder: function (ticker, side) {
      const orderTicker = document.getElementById('order-input-ticker');
      if (orderTicker) orderTicker.value = ticker;

      if (side === 'BUY') {
        const btnBuy = document.getElementById('btn-side-buy');
        if (btnBuy) btnBuy.click();
      } else if (side === 'SELL') {
        const btnSell = document.getElementById('btn-side-sell');
        if (btnSell) btnSell.click();
      }
      showNotification(`已预填委托单: ${side} ${ticker}`);
    }
  };

})();
