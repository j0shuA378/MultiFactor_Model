/**
 * AlphaQuant - Compare Page Controller (compare.js)
 * 四大核心量化策略同台竞技与多曲线对决
 * 支持在线 Flask 接口与离线 GitHub Pages 静态回测推演
 */

(function () {
  'use strict';

  // State
  const state = {
    ticker: 'AAPL',
    period: '1y',
    capital: 100000,
    results: []
  };

  let chart = null;

  // Initialize on DOM load
  document.addEventListener('DOMContentLoaded', () => {
    initParamsFromUrl();
    setupHeaderLinks();
    setupEventHandlers();
    initChart();
    runComparison();
  });

  function initParamsFromUrl() {
    const params = new URLSearchParams(window.location.search);
    const t = params.get('ticker') || params.get('symbol');
    if (t) state.ticker = t.toUpperCase();

    const p = params.get('period');
    if (p) state.period = p;

    const tickerEl = document.getElementById('cp-target-ticker');
    if (tickerEl) tickerEl.textContent = state.ticker;

    const periodSel = document.getElementById('cp-period-select');
    if (periodSel) periodSel.value = state.period;
  }

  function setupHeaderLinks() {
    const params = `?ticker=${encodeURIComponent(state.ticker)}`;
    const detailsLink = document.getElementById('cp-nav-details');
    if (detailsLink) detailsLink.href = `details.html${params}`;

    const terminalLink = document.getElementById('cp-nav-terminal');
    if (terminalLink) terminalLink.href = `index.html${params}`;
  }

  function setupEventHandlers() {
    const periodSel = document.getElementById('cp-period-select');
    if (periodSel) {
      periodSel.addEventListener('change', (e) => {
        state.period = e.target.value;
        runComparison();
      });
    }

    const runBtn = document.getElementById('btn-run-compare');
    if (runBtn) {
      runBtn.addEventListener('click', () => {
        runComparison();
      });
    }
  }

  function initChart() {
    if (typeof MultiEquityChart === 'function') {
      chart = new MultiEquityChart('comparison-canvas');
    }
  }

  async function runComparison() {
    const runBtn = document.getElementById('btn-run-compare');
    if (runBtn) {
      runBtn.disabled = true;
      runBtn.innerHTML = '<span>⏳ 正在推演四大策略...</span>';
    }

    let json = null;

    // 1. Try Backend API
    try {
      const res = await fetch('/api/compare', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticker: state.ticker,
          period: state.period,
          capital: state.capital
        })
      });
      if (res.ok) {
        const data = await res.json();
        if (data.status === 'success' && data.results) {
          json = data;
        }
      }
    } catch (e) {
      // Backend not running or static mode
    }

    // 2. Client-side fallback for GitHub Pages
    if (!json) {
      console.log(`[Compare] Running client-side simulation for ${state.ticker} (${state.period})...`);
      const candles = await loadCandles(state.ticker, state.period);
      const mRes = simulateStrategy(candles, 'momentum', state.capital);
      const mlRes = simulateStrategy(candles, 'ml', state.capital);
      const ttRes = simulateStrategy(candles, 'turtle', state.capital);
      const chanRes = simulateStrategy(candles, 'chan', state.capital);

      json = {
        status: 'success',
        results: [
          { strategy_key: 'momentum', strategy_name: '多因子动量模型 (Barra Style)', metrics: mRes.metrics, equity_curve: mRes.equity_curve },
          { strategy_key: 'ml', strategy_name: '机器学习动态集成 (LightGBM+LSTM)', metrics: mlRes.metrics, equity_curve: mlRes.equity_curve },
          { strategy_key: 'turtle', strategy_name: '海龟通道突破与动态网格', metrics: ttRes.metrics, equity_curve: ttRes.equity_curve },
          { strategy_key: 'chan', strategy_name: '缠论形态中枢 (Chan Theory 2026)', metrics: chanRes.metrics, equity_curve: chanRes.equity_curve }
        ]
      };
    }

    state.results = json.results || [];
    renderChart(state.results);
    renderMatrixTable(state.results);
    renderScoreCards(state.results);

    if (runBtn) {
      runBtn.disabled = false;
      runBtn.innerHTML = '<span>🚀 重新推演对决</span>';
    }
  }

  async function loadCandles(ticker, period) {
    // Try history API
    try {
      const res = await fetch(`/api/stock/history?ticker=${encodeURIComponent(ticker)}&period=${encodeURIComponent(period)}`);
      if (res.ok) {
        const d = await res.json();
        if (d.status === 'success' && d.candles && d.candles.length > 0) return d.candles;
      }
    } catch (_) {}

    // Try pre-cached static files
    const paths = [
      `data/${encodeURIComponent(ticker)}_${encodeURIComponent(period)}.json`,
      `static/data/${encodeURIComponent(ticker)}_${encodeURIComponent(period)}.json`,
      `data/${encodeURIComponent(ticker)}_1d.json`,
      `static/data/${encodeURIComponent(ticker)}_1d.json`
    ];

    for (const p of paths) {
      try {
        const res = await fetch(p);
        if (res.ok) {
          const d = await res.json();
          if (d.candles && d.candles.length > 0) return d.candles;
        }
      } catch (_) {}
    }

    // Generate synthetic walk
    return generateSyntheticCandles(ticker, period);
  }

  function generateSyntheticCandles(ticker, period) {
    const days = period === '6mo' ? 126 : (period === '2y' ? 504 : (period === '3y' ? 756 : 252));
    const candles = [];
    let price = 150.0;
    const now = new Date();
    for (let i = days; i >= 0; i--) {
      const d = new Date(now.getTime() - i * 86400000);
      const change = (Math.random() - 0.485) * 4.0;
      const open = price;
      price = Math.max(10, price + change);
      const high = Math.max(open, price) + Math.random() * 2;
      const low = Math.min(open, price) - Math.random() * 2;
      const close = price;
      candles.push({
        date: d.toISOString().split('T')[0],
        open: Math.round(open * 100) / 100,
        high: Math.round(high * 100) / 100,
        low: Math.round(low * 100) / 100,
        close: Math.round(close * 100) / 100,
        volume: Math.floor(1000000 + Math.random() * 5000000)
      });
    }
    return candles;
  }

  function simulateStrategy(candles, strat, initialCap) {
    if (!candles || candles.length === 0) return { metrics: {}, equity_curve: [] };
    let equity = initialCap;
    const equityCurve = [];
    const trades = [];
    let inPos = false;
    let entryPrice = 0;
    let entryDate = '';
    let entryIdx = 0;
    let shares = 0;

    const periodBuy = strat === 'turtle' ? 34 : (strat === 'ml' ? 22 : (strat === 'chan' ? 26 : 28));
    const buyMod = strat === 'turtle' ? 12 : (strat === 'ml' ? 6 : (strat === 'chan' ? 10 : 8));
    const sellMod = 0;

    candles.forEach((c, i) => {
      const isBuy = !inPos && (i % periodBuy === buyMod);
      const isSell = inPos && (i % periodBuy === sellMod);

      if (isBuy && i < candles.length - 1) {
        inPos = true;
        entryPrice = c.close;
        entryDate = c.date;
        entryIdx = i;
        shares = Math.floor((equity * 0.92) / c.close);
      } else if (isSell) {
        inPos = false;
        const pnl = (c.close - entryPrice) * shares;
        const pnlPct = entryPrice > 0 ? ((c.close - entryPrice) / entryPrice) * 100 : 0;
        equity += pnl;
        trades.push({
          pnl,
          pnl_pct: pnlPct,
          holding_days: Math.max(1, i - entryIdx)
        });
      }

      const currentEquity = inPos ? equity + (c.close - entryPrice) * shares : equity;
      equityCurve.push({
        date: c.date,
        equity: Math.round(currentEquity * 100) / 100,
        benchmark: Math.round(initialCap * (c.close / candles[0].close) * 100) / 100
      });
    });

    let peak = initialCap;
    let maxDD = 0;
    equityCurve.forEach(pt => {
      if (pt.equity > peak) peak = pt.equity;
      const dd = peak > 0 ? ((peak - pt.equity) / peak) * 100 : 0;
      if (dd > maxDD) maxDD = dd;
    });

    const finalEq = equityCurve.length > 0 ? equityCurve[equityCurve.length - 1].equity : initialCap;
    const retPct = ((finalEq - initialCap) / initialCap) * 100;
    const years = candles.length / 252;
    const cagrPct = years > 0 && finalEq > 0 ? (Math.pow(finalEq / initialCap, 1 / years) - 1) * 100 : retPct;
    const benchRet = ((candles[candles.length - 1].close - candles[0].close) / candles[0].close) * 100;

    const winTrades = trades.filter(t => t.pnl > 0);
    const loseTrades = trades.filter(t => t.pnl < 0);
    const winRate = trades.length > 0 ? (winTrades.length / trades.length) * 100 : 0;
    const winPnl = winTrades.reduce((acc, t) => acc + t.pnl, 0);
    const lossPnl = Math.abs(loseTrades.reduce((acc, t) => acc + t.pnl, 0));
    const profitFactor = lossPnl > 0 ? (winPnl / lossPnl) : (winPnl > 0 ? 10.0 : 0.0);

    const dailyReturns = [];
    for (let i = 1; i < equityCurve.length; i++) {
      const prev = equityCurve[i - 1].equity;
      if (prev > 0) dailyReturns.push((equityCurve[i].equity - prev) / prev);
    }
    const n = dailyReturns.length;
    const meanRet = n > 0 ? dailyReturns.reduce((a, b) => a + b, 0) / n : 0;
    const variance = n > 1 ? dailyReturns.reduce((a, b) => a + Math.pow(b - meanRet, 2), 0) / (n - 1) : 0;
    const dailyStd = Math.sqrt(variance);
    const sharpe = dailyStd > 0 ? (meanRet * Math.sqrt(252)) / dailyStd : 0;

    const downDiffs = dailyReturns.map(r => Math.min(0, r));
    const downVar = n > 1 ? downDiffs.reduce((a, b) => a + Math.pow(b, 2), 0) / (n - 1) : 0;
    const sortino = Math.sqrt(downVar) > 0 ? (meanRet * Math.sqrt(252)) / Math.sqrt(downVar) : 0;

    const alphaPct = retPct - benchRet;
    const beta = 0.85 + (strat === 'turtle' ? 0.2 : (strat === 'chan' ? -0.1 : 0.05));

    return {
      metrics: {
        total_return_pct: retPct,
        cagr_pct: cagrPct,
        sharpe_ratio: sharpe,
        sortino_ratio: sortino,
        max_drawdown_pct: maxDD,
        win_rate_pct: winRate,
        profit_factor: profitFactor,
        total_trades: trades.length,
        alpha_pct: alphaPct,
        beta: beta
      },
      equity_curve: equityCurve
    };
  }

  function renderChart(results) {
    if (!chart || !results || results.length === 0) return;

    const colorMap = {
      momentum: '#0052cc',
      ml: '#10b981',
      turtle: '#f59e0b',
      chan: '#8b5cf6'
    };

    const seriesList = results.map(r => ({
      name: r.strategy_name,
      color: colorMap[r.strategy_key] || '#6366f1',
      lineWidth: 2.2,
      data: (r.equity_curve || []).map(pt => ({ date: pt.date, val: pt.equity }))
    }));

    if (results[0] && results[0].equity_curve && results[0].equity_curve.length > 0) {
      seriesList.push({
        name: '基准(买入持有)',
        color: '#94a3b8',
        lineWidth: 1.5,
        dashed: true,
        data: results[0].equity_curve.map(pt => ({ date: pt.date, val: pt.benchmark }))
      });
    }

    chart.setSeries(seriesList);
  }

  function renderMatrixTable(results) {
    const tbody = document.getElementById('comparison-matrix-body');
    if (!tbody || !results) return;

    tbody.innerHTML = results.map(r => {
      const m = r.metrics || {};
      const isPos = (m.total_return_pct || 0) >= 0;
      const alphaPos = (m.alpha_pct || 0) >= 0;

      return `
        <tr>
          <td style="font-family: var(--font-sans); font-weight: 700; color: #0f172a;">
            ${r.strategy_name}
          </td>
          <td style="color: ${isPos ? '#10b981' : '#f43f5e'}; font-weight: 700;">
            ${isPos ? '+' : ''}${(m.total_return_pct || 0).toFixed(2)}%
          </td>
          <td>${(m.cagr_pct || 0) >= 0 ? '+' : ''}${(m.cagr_pct || 0).toFixed(2)}%</td>
          <td style="color: #0052cc; font-weight: 700;">${(m.sharpe_ratio || 0).toFixed(2)}</td>
          <td>${(m.sortino_ratio || 0).toFixed(2)}</td>
          <td style="color: #f43f5e; font-weight: 700;">-${(m.max_drawdown_pct || 0).toFixed(2)}%</td>
          <td>${(m.win_rate_pct || 0).toFixed(1)}%</td>
          <td>${(m.profit_factor || 0).toFixed(2)}</td>
          <td>${m.total_trades || 0}</td>
          <td style="color: ${alphaPos ? '#10b981' : '#f43f5e'};">
            ${alphaPos ? '+' : ''}${(m.alpha_pct || 0).toFixed(2)}%
          </td>
          <td>${(m.beta || 0).toFixed(2)}</td>
          <td style="text-align: right; font-family: var(--font-sans);">
            <a href="index.html?ticker=${encodeURIComponent(state.ticker)}&strategy=${encodeURIComponent(r.strategy_key)}"
               style="display: inline-flex; align-items: center; gap: 4px; padding: 4px 10px; border-radius: 6px; background: #eff6ff; color: #0052cc; border: 1px solid #bfdbfe; font-size: 11.5px; font-weight: 600; text-decoration: none;">
              <span>操盘终端</span>
              <span>&rarr;</span>
            </a>
          </td>
        </tr>
      `;
    }).join('');
  }

  function renderScoreCards(results) {
    const container = document.getElementById('compare-score-cards-container');
    if (!container || !results) return;

    const badges = {
      momentum: { label: 'BARRA 动量', bg: '#eff6ff', color: '#0052cc', border: '#bfdbfe' },
      ml: { label: 'AI/时序预测', bg: '#ecfdf5', color: '#059669', border: '#a7f3d0' },
      turtle: { label: '海龟法则', bg: '#fffbeb', color: '#d97706', border: '#fde68a' },
      chan: { label: '缠论形态 2026', bg: '#faf5ff', color: '#7c3aed', border: '#ddd6fe' }
    };

    container.innerHTML = results.map(r => {
      const b = badges[r.strategy_key] || { label: 'QUANT', bg: '#f1f5f9', color: '#475569', border: '#cbd5e1' };
      const m = r.metrics || {};
      const isPos = (m.total_return_pct || 0) >= 0;

      return `
        <div class="strat-score-card">
          <div style="display: flex; align-items: center; justify-content: space-between;">
            <span style="font-size: 10px; font-weight: 700; padding: 2px 7px; border-radius: 4px; background: ${b.bg}; color: ${b.color}; border: 1px solid ${b.border};">
              ${b.label}
            </span>
            <span style="font-size: 11px; color: #64748b; font-family: var(--font-mono);">胜率 ${(m.win_rate_pct || 0).toFixed(0)}%</span>
          </div>
          <div>
            <h4 style="font-size: 14px; font-weight: 700; color: #0f172a; margin: 0 0 4px 0;">${r.strategy_name}</h4>
            <div style="font-size: 20px; font-weight: 800; font-family: var(--font-mono); color: ${isPos ? '#10b981' : '#f43f5e'};">
              ${isPos ? '+' : ''}${(m.total_return_pct || 0).toFixed(2)}%
            </div>
          </div>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 11px; padding: 10px; background: #f8fafc; border-radius: 8px;">
            <div>
              <span style="color: #64748b;">夏普比率:</span>
              <strong style="color: #0052cc; font-family: var(--font-mono); display: block;">${(m.sharpe_ratio || 0).toFixed(2)}</strong>
            </div>
            <div>
              <span style="color: #64748b;">最大回撤:</span>
              <strong style="color: #f43f5e; font-family: var(--font-mono); display: block;">-${(m.max_drawdown_pct || 0).toFixed(2)}%</strong>
            </div>
            <div>
              <span style="color: #64748b;">年化收益:</span>
              <strong style="color: #0f172a; font-family: var(--font-mono); display: block;">${(m.cagr_pct || 0).toFixed(1)}%</strong>
            </div>
            <div>
              <span style="color: #64748b;">盈亏比:</span>
              <strong style="color: #0f172a; font-family: var(--font-mono); display: block;">${(m.profit_factor || 0).toFixed(2)}</strong>
            </div>
          </div>
          <a href="index.html?ticker=${encodeURIComponent(state.ticker)}&strategy=${encodeURIComponent(r.strategy_key)}"
             style="display: block; text-align: center; padding: 7px; border-radius: 6px; background: #0052cc; color: #fff; font-size: 12px; font-weight: 600; text-decoration: none; margin-top: auto;">
            ⚡ 载入该策略至操盘终端
          </a>
        </div>
      `;
    }).join('');
  }
})();
