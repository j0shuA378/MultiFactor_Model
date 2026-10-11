// AlphaQuant Screener Controller
(function() {
  'use strict';

  let screenerData = [];
  let currentCategory = 'all';

  async function initScreener() {
    // 1. Fetch from server
    try {
      const res = await fetch('/api/screener');
      if (res.ok) {
        const json = await res.json();
        if (json.status === 'success' && Array.isArray(json.stocks)) {
          screenerData = json.stocks;
          renderTable();
          return;
        }
      }
    } catch (e) {}

    // 2. Fetch from static JSON catalog
    const staticPaths = ['data/screener_catalog.json', './data/screener_catalog.json', '../data/screener_catalog.json'];
    for (const p of staticPaths) {
      try {
        const res = await fetch(p);
        if (res.ok) {
          const list = await res.json();
          if (Array.isArray(list) && list.length > 0) {
            screenerData = list;
            renderTable();
            return;
          }
        }
      } catch (err) {}
    }

    // 3. Fallback from PRESET_FUNDAMENTALS_DB
    if (window.PRESET_FUNDAMENTALS_DB) {
      screenerData = Object.keys(window.PRESET_FUNDAMENTALS_DB).map(sym => {
        const item = window.PRESET_FUNDAMENTALS_DB[sym];
        const p = item.profile || {};
        const pr = item.price_overview || {};
        const v = item.valuation || {};
        const ana = item.analysts || {};
        const div = item.dividends || {};

        let cat = 'us_tech';
        let catLabel = '美股科技';
        if (sym.includes('.SS') || sym.includes('.SZ')) {
          cat = 'a_shares';
          catLabel = 'A股核心';
        } else if (sym.includes('.HK')) {
          cat = 'china_hk';
          catLabel = '港股互联';
        } else if (['GLD', 'IAUM', 'SPY', 'QQQ', 'TLT', 'IWM', '510300.SS'].includes(sym)) {
          cat = 'etf_gold';
          catLabel = 'ETF与黄金';
        } else if (['JNJ', 'KO', 'XOM', '600036.SS'].includes(sym)) {
          cat = 'high_dividend';
          catLabel = '高股息';
        }

        return {
          symbol: sym,
          name: p.name || sym,
          category: cat,
          category_label: catLabel,
          sector: p.sector || '科技',
          price: pr.current_price || 100,
          change_pct: pr.change_pct || 0,
          market_cap_fmt: pr.market_cap_fmt || '--',
          pe: v.trailing_pe || 25,
          target_upside_pct: ana.target_upside_pct || 10,
          analyst_rating: ana.consensus_rating || '买入',
          div_yield_pct: div.dividend_yield_pct || 0
        };
      });
      renderTable();
    }
  }

  function renderTable() {
    const tbody = document.getElementById('sc-table-body');
    if (!tbody || !screenerData) return;

    let list = [...screenerData];

    // Filter by Category
    if (currentCategory && currentCategory !== 'all') {
      list = list.filter(s => s.category === currentCategory);
    }

    // Filter by Keyword
    const kw = (document.getElementById('sc-keyword-input')?.value || '').trim().toLowerCase();
    if (kw) {
      list = list.filter(s =>
        (s.symbol && s.symbol.toLowerCase().includes(kw)) ||
        (s.name && s.name.toLowerCase().includes(kw)) ||
        (s.sector && s.sector.toLowerCase().includes(kw))
      );
    }

    // Sort
    const sortVal = document.getElementById('sc-sort-select')?.value || 'market_cap_desc';
    list.sort((a, b) => {
      if (sortVal === 'change_desc') return (b.change_pct || 0) - (a.change_pct || 0);
      if (sortVal === 'change_asc') return (a.change_pct || 0) - (b.change_pct || 0);
      if (sortVal === 'target_upside_desc') return (b.target_upside_pct || 0) - (a.target_upside_pct || 0);
      if (sortVal === 'pe_asc') return (a.pe || 999) - (b.pe || 999);
      if (sortVal === 'div_desc') return (b.div_yield_pct || 0) - (a.div_yield_pct || 0);
      return 0;
    });

    if (list.length === 0) {
      tbody.innerHTML = `<tr><td colspan="11" style="text-align:center; padding:30px; color:#94a3b8;">未找到匹配 "${kw}" 的标的</td></tr>`;
      return;
    }

    tbody.innerHTML = list.map(stock => {
      const isPos = (stock.change_pct || 0) >= 0;
      const isUp = (stock.target_upside_pct || 0) >= 0;
      const sym = stock.symbol;

      return `
        <tr style="cursor: pointer;" onclick="if(event.target.tagName!=='A'&&event.target.tagName!=='BUTTON') window.location.href='details.html?ticker=${sym}'">
          <td>
            <div style="display:flex; flex-direction:column; gap:2px;">
              <span style="font-family:var(--font-mono); font-weight:800; font-size:14px; color:#0f172a;">${sym}</span>
              <span style="font-size:12px; color:#64748b;">${stock.name}</span>
            </div>
          </td>
          <td><span style="font-size:11px; font-weight:600; padding:2px 6px; border-radius:4px; background:#f1f5f9; color:#475569;">${stock.category_label || '核心'}</span></td>
          <td style="color:#64748b;">${stock.sector || '--'}</td>
          <td style="font-family:var(--font-mono); font-weight:700; color:#0f172a; font-size:13.5px;">$${Number(stock.price || 0).toFixed(2)}</td>
          <td>
            <span style="font-family:var(--font-mono); font-weight:700; font-size:12px; padding:2px 6px; border-radius:4px; background:${isPos ? '#ecfdf5' : '#fef2f2'}; color:${isPos ? '#059669' : '#dc2626'};">
              ${isPos ? '+' : ''}${Number(stock.change_pct || 0).toFixed(2)}%
            </span>
          </td>
          <td style="font-family:var(--font-mono); font-weight:600;">${stock.market_cap_fmt || '--'}</td>
          <td style="font-family:var(--font-mono);">${stock.pe ? `${Number(stock.pe).toFixed(1)}x` : '--'}</td>
          <td style="font-family:var(--font-mono); font-weight:700; color:${isUp ? '#059669' : '#dc2626'};">
            ${isUp ? '+' : ''}${Number(stock.target_upside_pct || 0).toFixed(1)}%
          </td>
          <td>
            <span style="font-size:11px; font-weight:600; padding:2px 6px; border-radius:4px; background:#eff6ff; color:#0052cc;">
              ${stock.analyst_rating || '买入'}
            </span>
          </td>
          <td style="font-family:var(--font-mono);">${stock.div_yield_pct > 0 ? `${Number(stock.div_yield_pct).toFixed(2)}%` : '--'}</td>
          <td style="text-align: right; white-space: nowrap;">
            <a href="details.html?ticker=${sym}" class="btn-action-details" title="查看深度财务与机构预测">
              <span>📊 深度基本面</span>
            </a>
            <a href="index.html?ticker=${sym}" class="btn-action-terminal" style="margin-left:6px;" title="进入量化交易终端">
              <span>⚡ 量化操盘</span>
            </a>
          </td>
        </tr>
      `;
    }).join('');
  }

  function setupEvents() {
    // Category pills
    const catBtns = document.querySelectorAll('.sc-pill-btn');
    catBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        catBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentCategory = btn.dataset.category || 'all';
        renderTable();
      });
    });

    // Keyword search
    const kwInput = document.getElementById('sc-keyword-input');
    if (kwInput) {
      kwInput.addEventListener('input', () => {
        renderTable();
      });
    }

    // Sort select
    const sortSelect = document.getElementById('sc-sort-select');
    if (sortSelect) {
      sortSelect.addEventListener('change', () => {
        renderTable();
      });
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    setupEvents();
    initScreener();
  });
})();
