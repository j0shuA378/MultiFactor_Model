// AlphaQuant Details & Fundamentals Controller
(function() {
  'use strict';

  function getQueryParam(name) {
    const params = new URLSearchParams(window.location.search);
    return params.get(name);
  }

  let currentTicker = (getQueryParam('ticker') || 'AAPL').toUpperCase();

  async function loadDetails(ticker) {
    currentTicker = ticker.toUpperCase();
    document.title = `${currentTicker} 深度财务基本面与机构预测研报 | AlphaQuant`;

    // Update navigation links to carry the current ticker
    const btnTerminal = document.getElementById('btn-enter-terminal');
    if (btnTerminal) btnTerminal.href = `index.html?ticker=${currentTicker}`;
    const topNavTerminal = document.getElementById('top-nav-to-terminal');
    if (topNavTerminal) topNavTerminal.href = `index.html?ticker=${currentTicker}`;
    const topNavCompare = document.getElementById('top-nav-to-compare');
    if (topNavCompare) topNavCompare.href = `compare.html?ticker=${currentTicker}`;

    const linkMom = document.getElementById('link-strat-mom');
    if (linkMom) linkMom.href = `index.html?ticker=${currentTicker}&strat=momentum`;
    const linkML = document.getElementById('link-strat-ml');
    if (linkML) linkML.href = `index.html?ticker=${currentTicker}&strat=ml`;
    const linkTurtle = document.getElementById('link-strat-turtle');
    if (linkTurtle) linkTurtle.href = `index.html?ticker=${currentTicker}&strat=turtle`;
    const linkChan = document.getElementById('link-strat-chan');
    if (linkChan) linkChan.href = `index.html?ticker=${currentTicker}&strat=chan`;

    // Try API first, fallback to preset database
    let data = null;
    try {
      const res = await fetch(`/api/fundamentals?ticker=${encodeURIComponent(currentTicker)}`);
      if (res.ok) {
        const json = await res.json();
        if (json.status === 'success' && json.profile) {
          data = json;
        }
      }
    } catch (e) {
      // Backend offline / static mode
    }

    if (!data && window.PRESET_FUNDAMENTALS_DB && window.PRESET_FUNDAMENTALS_DB[currentTicker]) {
      data = window.PRESET_FUNDAMENTALS_DB[currentTicker];
    }

    if (!data) {
      // Generic fallback
      data = {
        profile: { symbol: currentTicker, name: currentTicker, exchange: 'US', sector: 'General', industry: 'General', quote_type: 'EQUITY', employees: 10000, website: '#', summary: '暂无详细业务介绍，正在持续同步机构资料。' },
        price_overview: { current_price: 100.0, change: 0, change_pct: 0, market_cap_fmt: '--', enterprise_value_fmt: '--', volume: 1000000 },
        valuation: { trailing_pe: 25.0, forward_pe: 22.0, price_to_book: 3.5, beta: 1.0, fifty_two_week_high: 120.0, fifty_two_week_low: 80.0, range_52w_position_pct: 50.0 },
        financials: { revenue_fmt: '--', net_income_fmt: '--', revenue_growth_pct: 10.0, gross_margins_pct: 40.0, profit_margins_pct: 20.0, return_on_equity_pct: 25.0 },
        dividends: { dividend_yield_pct: 1.0, annual_payout: 1.0, ex_dividend_date: '--', payout_ratio_pct: 20.0 },
        analysts: { target_mean: 110.0, target_high: 130.0, target_low: 90.0, target_upside_pct: 10.0, consensus_rating: '买入', num_analysts: 20, recommendations: { strong_buy: 8, buy: 7, hold: 4, underperform: 1, sell: 0 } }
      };
    }

    renderData(data);
  }

  function renderData(data) {
    const prof = data.profile || {};
    const price = data.price_overview || {};
    const val = data.valuation || {};
    const fin = data.financials || {};
    const div = data.dividends || {};
    const ana = data.analysts || {};

    // Hero Section
    const setTxt = (id, txt) => {
      const el = document.getElementById(id);
      if (el) el.textContent = txt;
    };

    setTxt('d-symbol', prof.symbol || currentTicker);
    setTxt('d-name', prof.name || currentTicker);
    setTxt('d-exchange', prof.exchange || 'US');
    setTxt('d-sector', prof.sector || '科技');
    setTxt('d-industry', prof.industry || '综合');
    setTxt('d-quote-type', prof.quote_type || 'EQUITY');

    const curPrice = Number(price.current_price || 0);
    setTxt('d-price', curPrice > 0 ? `$${curPrice.toFixed(2)}` : '--');

    const chgPct = Number(price.change_pct || 0);
    const chgVal = Number(price.change || 0);
    const chgEl = document.getElementById('d-change');
    if (chgEl) {
      const isPos = chgPct >= 0;
      chgEl.className = `dh-change ${isPos ? 'positive' : 'negative'}`;
      chgEl.style.color = isPos ? '#059669' : '#dc2626';
      chgEl.style.background = isPos ? '#ecfdf5' : '#fef2f2';
      chgEl.textContent = `${isPos ? '+' : ''}${chgPct.toFixed(2)}% (${isPos ? '+' : ''}$${Math.abs(chgVal).toFixed(2)})`;
    }

    setTxt('d-mktcap', price.market_cap_fmt || '--');
    setTxt('d-volume', price.volume ? `${(price.volume / 10000).toFixed(0)}万股` : '--');

    // 52-Week Range
    const l52 = Number(val.fifty_two_week_low || 0);
    const h52 = Number(val.fifty_two_week_high || 0);
    setTxt('d-52l', l52 > 0 ? `$${l52.toFixed(2)}` : '--');
    setTxt('d-52h', h52 > 0 ? `$${h52.toFixed(2)}` : '--');
    const pos52 = Math.max(0, Math.min(100, Number(val.range_52w_position_pct || 50)));
    setTxt('d-52pos', `${pos52.toFixed(1)}%`);
    const thumb = document.getElementById('d-52thumb');
    if (thumb) thumb.style.left = `${pos52}%`;

    // Valuation Multiples
    setTxt('vm-mktcap', price.market_cap_fmt || '--');
    setTxt('vm-entval', price.enterprise_value_fmt || '--');
    setTxt('vm-pe', val.trailing_pe ? `${Number(val.trailing_pe).toFixed(1)}x` : '--');
    setTxt('vm-fwd-pe', val.forward_pe ? `${Number(val.forward_pe).toFixed(1)}x` : '--');
    setTxt('vm-pb', val.price_to_book ? `${Number(val.price_to_book).toFixed(1)}x` : '--');
    setTxt('vm-beta', val.beta ? `${Number(val.beta).toFixed(2)}` : '--');

    // Analyst Consensus & Price Targets
    setTxt('d-target-mean', ana.target_mean ? `$${Number(ana.target_mean).toFixed(2)}` : '--');
    setTxt('d-target-high', ana.target_high ? `$${Number(ana.target_high).toFixed(2)}` : '--');
    setTxt('d-target-low', ana.target_low ? `$${Number(ana.target_low).toFixed(2)}` : '--');

    const upside = Number(ana.target_upside_pct || 0);
    const upEl = document.getElementById('d-target-upside');
    if (upEl) {
      const isUp = upside >= 0;
      upEl.style.color = isUp ? '#059669' : '#dc2626';
      upEl.textContent = `${isUp ? '+' : ''}${upside.toFixed(2)}%`;
    }

    setTxt('d-consensus-badge', ana.consensus_rating || '良好');
    setTxt('d-num-analysts', ana.num_analysts || '30+');

    // Recommendations Bar
    const rec = ana.recommendations || { strong_buy: 15, buy: 12, hold: 5, underperform: 2, sell: 1 };
    const totalRec = (rec.strong_buy || 0) + (rec.buy || 0) + (rec.hold || 0) + (rec.underperform || 0) + (rec.sell || 0) || 1;
    const setRecBar = (prefix, val) => {
      setTxt(`rb-cnt-${prefix}`, val || 0);
      const fill = document.getElementById(`rb-${prefix}`);
      if (fill) fill.style.width = `${Math.round(((val || 0) / totalRec) * 100)}%`;
    };
    setRecBar('strong-buy', rec.strong_buy);
    setRecBar('buy', rec.buy);
    setRecBar('hold', rec.hold);
    setRecBar('underperform', rec.underperform);
    setRecBar('sell', rec.sell);

    // Dividends
    setTxt('div-yield', div.dividend_yield_pct ? `${Number(div.dividend_yield_pct).toFixed(2)}%` : '0.00%');
    setTxt('div-payout', div.annual_payout ? `$${Number(div.annual_payout).toFixed(2)}` : '--');
    setTxt('div-ex-date', div.ex_dividend_date || '无派息');
    setTxt('div-payout-ratio', div.payout_ratio_pct ? `${Number(div.payout_ratio_pct).toFixed(1)}%` : '--');

    // Financials
    setTxt('fin-revenue', fin.revenue_fmt || '--');
    setTxt('fin-rev-growth', fin.revenue_growth_pct ? `+${Number(fin.revenue_growth_pct).toFixed(1)}%` : '--');
    setTxt('fin-net-income', fin.net_income_fmt || '--');
    setTxt('fin-net-margin', fin.profit_margins_pct ? `${Number(fin.profit_margins_pct).toFixed(1)}%` : '--');
    setTxt('fin-gross-margin', fin.gross_margins_pct ? `${Number(fin.gross_margins_pct).toFixed(1)}%` : '--');
    setTxt('fin-roe', fin.return_on_equity_pct ? `${Number(fin.return_on_equity_pct).toFixed(1)}%` : '--');

    // Company Summary
    setTxt('d-employees', prof.employees ? `${Number(prof.employees).toLocaleString()} 人` : '规模化跨国企业');
    const webEl = document.getElementById('d-website');
    if (webEl && prof.website) {
      webEl.href = prof.website;
      webEl.textContent = `${prof.website.replace(/^https?:\/\//, '')} \u2192`;
    }
    setTxt('d-summary', prof.summary || '暂无详细介绍。');
  }

  // Setup search input
  function setupSearch() {
    const input = document.getElementById('custom-ticker-input');
    const btn = document.getElementById('search-ticker-btn');
    const dropdown = document.getElementById('search-suggestions-dropdown');

    const doSwitch = (sym) => {
      if (!sym) return;
      const clean = sym.trim().toUpperCase();
      window.location.search = `?ticker=${encodeURIComponent(clean)}`;
    };

    if (input) {
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          doSwitch(input.value);
        }
      });
    }

    if (btn) {
      btn.addEventListener('click', () => {
        if (input) doSwitch(input.value);
      });
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    setupSearch();
    loadDetails(currentTicker);
  });
})();
