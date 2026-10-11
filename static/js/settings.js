/**
 * AlphaQuant Institutional Strategy & Risk Settings Controller
 */

let currentConfig = null;
let currentPresets = [];

document.addEventListener('DOMContentLoaded', () => {
  if (document.body.dataset.page === 'settings') {
    initSettingsPage();
  }
});

async function initSettingsPage() {
  await fetchConfigFromBackend();
  bindSettingsInputs();
  bindActionButtons();
  bindSettingsSearchHeader();
}

async function fetchConfigFromBackend() {
  const statusEl = document.getElementById('config-sync-status');
  try {
    const res = await fetch('/api/config');
    const json = await res.json();
    if (json.status === 'success' && json.data) {
      currentConfig = json.data;
      currentPresets = json.presets || [];
      if (statusEl) statusEl.textContent = '后端配置已同步';
      populateFormFields(currentConfig);
      renderPresets(currentPresets, currentConfig.momentum?.preset_id);
      updateStackedWeightsBar();
      return;
    }
  } catch (err) {
    console.warn("Could not fetch /api/config (GitHub Pages mode or network err), using local storage:", err);
    if (statusEl) statusEl.textContent = '本地配置模式 (Local)';
  }

  // Fallback to localStorage or defaults
  const saved = localStorage.getItem('alphaquant_config');
  if (saved) {
    try {
      currentConfig = JSON.parse(saved);
    } catch (e) {}
  }

  if (!currentConfig) {
    currentConfig = {
      account: { initial_capital: 100000, commission_rate: 0.05, slippage_rate: 0.05, stop_loss_pct: null, take_profit_pct: null },
      momentum: {
        preset_id: 'aqr_momentum',
        w_mom_12_1: 0.30, w_risk_adj: 0.25, w_residual: 0.20, w_trend_qual: 0.15, w_vol_confirm: 0.10,
        use_vol_target: true, target_vol: 15, z_win: 30, alpha_th: 0.30, exit_th: -0.20, fast_ma: 10, slow_ma: 30
      },
      ml: { model_type: 'rf', prob_threshold: 0.55 },
      turtle: { donchian_entry: 20, stop_loss_n: 2.0 }
    };
  }

  currentPresets = [
    {
      id: "aqr_momentum",
      name: "AQR 动量优化型 (低波动缩放 + 残差Alpha)",
      tag: "AQR Style",
      description: "重仓特质波动率缩放与残差动量，开启动态波动率目标仓位管理，平滑回撤。",
      config: { w_mom_12_1: 0.30, w_risk_adj: 0.25, w_residual: 0.20, w_trend_qual: 0.15, w_vol_confirm: 0.10, use_vol_target: true, target_vol: 15.0, alpha_th: 0.30, exit_th: -0.20, fast_ma: 10, slow_ma: 30 }
    },
    {
      id: "bridgewater_all_weather",
      name: "桥水全天候风险平价型 (注重路径平滑度 R²)",
      tag: "Bridgewater Style",
      description: "大幅增加波动率调整与 R² 路径平滑度权重，目标年化波动率收敛至 12%。",
      config: { w_mom_12_1: 0.20, w_risk_adj: 0.35, w_residual: 0.15, w_trend_qual: 0.20, w_vol_confirm: 0.10, use_vol_target: true, target_vol: 12.0, alpha_th: 0.25, exit_th: -0.15, fast_ma: 12, slow_ma: 36 }
    },
    {
      id: "classic_jegadeesh",
      name: "经典 JT 12M-1M 动量 (学术截面基准)",
      tag: "Jegadeesh & Titman",
      description: "以 12M-1M 纯动量为主导核心 (55%)，纯净捕捉中长期截面动量溢价。",
      config: { w_mom_12_1: 0.55, w_risk_adj: 0.15, w_residual: 0.10, w_trend_qual: 0.10, w_vol_confirm: 0.10, use_vol_target: false, target_vol: 18.0, alpha_th: 0.35, exit_th: -0.25, fast_ma: 10, slow_ma: 30 }
    },
    {
      id: "goldman_quant",
      name: "高盛量化激进趋势型 (量价协同 + 敏捷Alpha)",
      tag: "Goldman Sachs Quant",
      description: "调高量价放量协同 (25%) 与纯截面动量 (35%)，缩短 EMA 快慢线均线滤波。",
      config: { w_mom_12_1: 0.35, w_risk_adj: 0.15, w_residual: 0.15, w_trend_qual: 0.10, w_vol_confirm: 0.25, use_vol_target: true, target_vol: 20.0, alpha_th: 0.40, exit_th: -0.30, fast_ma: 8, slow_ma: 24 }
    },
    {
      id: "balanced_institutional",
      name: "标准机构平衡配置 (五大支柱均权)",
      tag: "Standard Balanced",
      description: "五大动量支柱各按 20% 均匀配置，兼具稳定性与 Alpha 捕捉能力。",
      config: { w_mom_12_1: 0.20, w_risk_adj: 0.20, w_residual: 0.20, w_trend_qual: 0.20, w_vol_confirm: 0.20, use_vol_target: true, target_vol: 15.0, alpha_th: 0.30, exit_th: -0.20, fast_ma: 10, slow_ma: 30 }
    }
  ];

  populateFormFields(currentConfig);
  renderPresets(currentPresets, currentConfig.momentum?.preset_id);
  updateStackedWeightsBar();
}

function populateFormFields(cfg) {
  if (!cfg) return;
  const acc = cfg.account || {};
  const mom = cfg.momentum || {};
  const ml = cfg.ml || {};
  const turtle = cfg.turtle || {};

  // Account
  setVal('cfg-initial-capital', acc.initial_capital ?? 100000);
  setVal('cfg-commission-rate', acc.commission_rate ?? 0.05);
  setVal('cfg-slippage-rate', acc.slippage_rate ?? 0.05);
  setVal('cfg-stop-loss', acc.stop_loss_pct ?? '');
  setVal('cfg-take-profit', acc.take_profit_pct ?? '');

  // Momentum Weights
  setSliderVal('cfg-w-mom-12-1', 'cfg-w-mom-12-1-val', mom.w_mom_12_1 ?? 0.30);
  setSliderVal('cfg-w-risk-adj', 'cfg-w-risk-adj-val', mom.w_risk_adj ?? 0.25);
  setSliderVal('cfg-w-residual', 'cfg-w-residual-val', mom.w_residual ?? 0.20);
  setSliderVal('cfg-w-trend-qual', 'cfg-w-trend-qual-val', mom.w_trend_qual ?? 0.15);
  setSliderVal('cfg-w-vol-confirm', 'cfg-w-vol-confirm-val', mom.w_vol_confirm ?? 0.10);

  // Execution & Vol Target
  const volCheck = document.getElementById('cfg-use-vol-target');
  if (volCheck) volCheck.checked = Boolean(mom.use_vol_target !== false);
  setVal('cfg-target-vol', mom.target_vol ?? 15);
  setVal('cfg-z-win', mom.z_win ?? 30);
  setVal('cfg-alpha-th', mom.alpha_th ?? 0.30);
  setVal('cfg-exit-th', mom.exit_th ?? -0.20);
  setVal('cfg-fast-ma', mom.fast_ma ?? 10);
  setVal('cfg-slow-ma', mom.slow_ma ?? 30);

  // ML & Turtle
  setVal('cfg-ml-model', ml.model_type ?? 'rf');
  setVal('cfg-ml-prob-th', ml.prob_threshold ?? 0.55);
  setVal('cfg-donchian-entry', turtle.donchian_entry ?? 20);
  setVal('cfg-stop-loss-n', turtle.stop_loss_n ?? 2.0);
}

function setVal(id, val) {
  const el = document.getElementById(id);
  if (el) el.value = val;
}

function setSliderVal(sliderId, displayId, val) {
  const el = document.getElementById(sliderId);
  const disp = document.getElementById(displayId);
  if (el) el.value = val;
  if (disp) disp.textContent = `${Math.round(val * 100)}%`;
}

function renderPresets(presets, activeId) {
  const container = document.getElementById('presets-grid');
  if (!container) return;
  container.innerHTML = '';

  presets.forEach(p => {
    const isAct = p.id === activeId;
    const card = document.createElement('div');
    card.className = `preset-card ${isAct ? 'active' : ''}`;
    card.style.cssText = `
      background: ${isAct ? '#eff6ff' : '#ffffff'};
      border: 1px solid ${isAct ? '#0052cc' : 'var(--border-subtle)'};
      border-radius: var(--radius-sm);
      padding: 14px;
      cursor: pointer;
      display: flex;
      flex-direction: column;
      gap: 6px;
      transition: all 0.15s ease;
      box-shadow: ${isAct ? '0 2px 8px rgba(0,82,204,0.15)' : 'none'};
    `;

    card.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: flex-start;">
        <span style="font-size: 13px; font-weight: 700; color: ${isAct ? '#0052cc' : 'var(--text-primary)'};">${p.name}</span>
        <span style="font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 4px; background: ${isAct ? '#bfdbfe' : '#f1f5f9'}; color: ${isAct ? '#0052cc' : 'var(--text-muted)'}; white-space: nowrap;">
          ${p.tag}
        </span>
      </div>
      <p style="font-size: 11px; color: var(--text-muted); margin: 0; line-height: 1.4;">${p.description}</p>
      <div style="margin-top: 6px; font-size: 11px; font-weight: 600; color: var(--text-secondary);">
        12M-1M: ${Math.round((p.config.w_mom_12_1||0)*100)}% · 低波: ${Math.round((p.config.w_risk_adj||0)*100)}% · 残差: ${Math.round((p.config.w_residual||0)*100)}%
      </div>
    `;

    card.addEventListener('click', () => {
      applyPresetSelection(p);
    });

    container.appendChild(card);
  });

  const badge = document.getElementById('active-preset-badge');
  const actPreset = presets.find(p => p.id === activeId);
  if (badge && actPreset) {
    badge.textContent = `当前使用：${actPreset.name}`;
  }
}

function applyPresetSelection(preset) {
  if (!preset || !preset.config) return;
  if (!currentConfig) currentConfig = {};
  if (!currentConfig.momentum) currentConfig.momentum = {};

  Object.assign(currentConfig.momentum, preset.config);
  currentConfig.momentum.preset_id = preset.id;

  populateFormFields(currentConfig);
  renderPresets(currentPresets, preset.id);
  updateStackedWeightsBar();
  showFloatingToast(`已应用方案：${preset.name}`);
}

function bindSettingsInputs() {
  const sliders = [
    { id: 'cfg-w-mom-12-1', disp: 'cfg-w-mom-12-1-val', bar: 'bar-mom' },
    { id: 'cfg-w-risk-adj', disp: 'cfg-w-risk-adj-val', bar: 'bar-vol' },
    { id: 'cfg-w-residual', disp: 'cfg-w-residual-val', bar: 'bar-res' },
    { id: 'cfg-w-trend-qual', disp: 'cfg-w-trend-qual-val', bar: 'bar-qual' },
    { id: 'cfg-w-vol-confirm', disp: 'cfg-w-vol-confirm-val', bar: 'bar-conf' }
  ];

  sliders.forEach(s => {
    const el = document.getElementById(s.id);
    const disp = document.getElementById(s.disp);
    if (el) {
      el.addEventListener('input', () => {
        if (disp) disp.textContent = `${Math.round(el.value * 100)}%`;
        updateStackedWeightsBar();
        // Update preset badge to custom
        const badge = document.getElementById('active-preset-badge');
        if (badge) badge.textContent = `当前使用：自定义参数组合`;
        document.querySelectorAll('.preset-card').forEach(c => {
          c.classList.remove('active');
          c.style.background = '#ffffff';
          c.style.borderColor = 'var(--border-subtle)';
        });
      });
    }
  });

  const btnNorm = document.getElementById('btn-normalize-weights');
  if (btnNorm) {
    btnNorm.addEventListener('click', () => {
      sliders.forEach(s => {
        setSliderVal(s.id, s.disp, 0.20);
      });
      updateStackedWeightsBar();
      showFloatingToast('已将五大支柱权重均匀配置为 20%');
    });
  }
}

function updateStackedWeightsBar() {
  const w1 = parseFloat(document.getElementById('cfg-w-mom-12-1')?.value || 0);
  const w2 = parseFloat(document.getElementById('cfg-w-risk-adj')?.value || 0);
  const w3 = parseFloat(document.getElementById('cfg-w-residual')?.value || 0);
  const w4 = parseFloat(document.getElementById('cfg-w-trend-qual')?.value || 0);
  const w5 = parseFloat(document.getElementById('cfg-w-vol-confirm')?.value || 0);

  const total = w1 + w2 + w3 + w4 + w5;
  const totDisplay = document.getElementById('total-weights-display');
  if (totDisplay) {
    totDisplay.textContent = `${Math.round(total * 100)}%`;
    totDisplay.style.color = Math.abs(total - 1.0) < 0.01 ? '#0052cc' : (total > 1.0 ? '#dc2626' : '#f59e0b');
  }

  const base = total > 0 ? total : 1.0;
  const setBar = (id, w) => {
    const el = document.getElementById(id);
    if (el) el.style.width = `${((w / base) * 100).toFixed(1)}%`;
  };

  setBar('bar-mom', w1);
  setBar('bar-vol', w2);
  setBar('bar-res', w3);
  setBar('bar-qual', w4);
  setBar('bar-conf', w5);
}

function gatherConfigFromInputs() {
  return {
    account: {
      initial_capital: parseFloat(document.getElementById('cfg-initial-capital')?.value || 100000),
      commission_rate: parseFloat(document.getElementById('cfg-commission-rate')?.value || 0.05),
      slippage_rate: parseFloat(document.getElementById('cfg-slippage-rate')?.value || 0.05),
      stop_loss_pct: document.getElementById('cfg-stop-loss')?.value ? parseFloat(document.getElementById('cfg-stop-loss').value) : null,
      take_profit_pct: document.getElementById('cfg-take-profit')?.value ? parseFloat(document.getElementById('cfg-take-profit').value) : null
    },
    momentum: {
      preset_id: currentConfig?.momentum?.preset_id || 'custom',
      w_mom_12_1: parseFloat(document.getElementById('cfg-w-mom-12-1')?.value || 0.30),
      w_risk_adj: parseFloat(document.getElementById('cfg-w-risk-adj')?.value || 0.25),
      w_residual: parseFloat(document.getElementById('cfg-w-residual')?.value || 0.20),
      w_trend_qual: parseFloat(document.getElementById('cfg-w-trend-qual')?.value || 0.15),
      w_vol_confirm: parseFloat(document.getElementById('cfg-w-vol-confirm')?.value || 0.10),
      use_vol_target: Boolean(document.getElementById('cfg-use-vol-target')?.checked),
      target_vol: parseFloat(document.getElementById('cfg-target-vol')?.value || 15),
      z_win: parseInt(document.getElementById('cfg-z-win')?.value || 30, 10),
      alpha_th: parseFloat(document.getElementById('cfg-alpha-th')?.value || 0.30),
      exit_th: parseFloat(document.getElementById('cfg-exit-th')?.value || -0.20),
      fast_ma: parseInt(document.getElementById('cfg-fast-ma')?.value || 10, 10),
      slow_ma: parseInt(document.getElementById('cfg-slow-ma')?.value || 30, 10)
    },
    ml: {
      model_type: document.getElementById('cfg-ml-model')?.value || 'rf',
      prob_threshold: parseFloat(document.getElementById('cfg-ml-prob-th')?.value || 0.55)
    },
    turtle: {
      donchian_entry: parseInt(document.getElementById('cfg-donchian-entry')?.value || 20, 10),
      stop_loss_n: parseFloat(document.getElementById('cfg-stop-loss-n')?.value || 2.0)
    }
  };
}

function bindActionButtons() {
  const btnSave = document.getElementById('btn-save-settings');
  if (btnSave) {
    btnSave.addEventListener('click', async () => {
      const cfg = gatherConfigFromInputs();
      btnSave.disabled = true;
      btnSave.textContent = '💾 正在同步保存...';

      try {
        const res = await fetch('/api/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(cfg)
        });
        const json = await res.json();
        if (json.status === 'success') {
          currentConfig = json.data;
          localStorage.setItem('alphaquant_config', JSON.stringify(json.data));
          showFloatingToast('✅ 配置已成功保存至后端并对所有回测模型全局生效！');
        } else {
          throw new Error(json.message || '保存失败');
        }
      } catch (err) {
        console.warn("Backend save failed, saved to localStorage:", err);
        localStorage.setItem('alphaquant_config', JSON.stringify(cfg));
        showFloatingToast('✅ 配置已保存至本地存储');
      } finally {
        btnSave.disabled = false;
        btnSave.textContent = '💾 保存配置至后端';
      }
    });
  }

  const btnReset = document.getElementById('btn-reset-settings');
  if (btnReset) {
    btnReset.addEventListener('click', async () => {
      if (!confirm('确定将所有模型与风控参数恢复为机构出厂默认配置吗？')) return;
      btnReset.disabled = true;
      try {
        const res = await fetch('/api/config/reset', { method: 'POST' });
        const json = await res.json();
        if (json.status === 'success') {
          currentConfig = json.data;
          localStorage.setItem('alphaquant_config', JSON.stringify(json.data));
          populateFormFields(currentConfig);
          renderPresets(currentPresets, currentConfig.momentum?.preset_id);
          updateStackedWeightsBar();
          showFloatingToast('🔄 已恢复机构出厂默认配置');
        }
      } catch (err) {
        console.warn("Reset error:", err);
      } finally {
        btnReset.disabled = false;
      }
    });
  }

  const btnDismiss = document.getElementById('btn-floating-dismiss');
  if (btnDismiss) {
    btnDismiss.addEventListener('click', () => {
      document.getElementById('settings-floating-bar')?.classList.add('hidden');
    });
  }
}

function showFloatingToast(msg) {
  const bar = document.getElementById('settings-floating-bar');
  const txt = document.getElementById('floating-bar-text');
  if (bar && txt) {
    txt.textContent = msg;
    bar.classList.remove('hidden');
    clearTimeout(window._toastTimer);
    window._toastTimer = setTimeout(() => {
      bar.classList.add('hidden');
    }, 3500);
  }
}

function bindSettingsSearchHeader() {
  const searchInput = document.getElementById('custom-ticker-input');
  const searchBtn = document.getElementById('search-ticker-btn');
  const dropdown = document.getElementById('search-suggestions-dropdown');
  const searchWrap = document.getElementById('search-box-wrap') || (searchInput ? searchInput.closest('.search-box') : null);

  if (!searchInput) return;

  const closeDropdown = () => {
    if (dropdown) dropdown.classList.add('hidden');
  };

  const candidates = [
    { symbol: "510300.SS", name: "华泰柏瑞沪深300 ETF", exchange: "SSE", price: 4.39, change_pct: 0.05 },
    { symbol: "600519.SS", name: "贵州茅台 (白酒龙头)", exchange: "SSE", price: 1263.00, change_pct: 0.64 },
    { symbol: "300750.SZ", name: "宁德时代 (动力电池龙头)", exchange: "SZSE", price: 245.50, change_pct: 1.82 },
    { symbol: "002594.SZ", name: "比亚迪 (新能源汽车)", exchange: "SZSE", price: 285.20, change_pct: 1.15 },
    { symbol: "000001.SZ", name: "平安银行 (商业银行标杆)", exchange: "SZSE", price: 11.59, change_pct: -0.42 },
    { symbol: "0700.HK", name: "腾讯控股 (社交网络与游戏龙头)", exchange: "HKEX", price: 425.20, change_pct: 1.48 },
    { symbol: "AAPL", name: "Apple Inc. (苹果公司)", exchange: "NASDAQ", price: 336.64, change_pct: -1.11 },
    { symbol: "NVDA", name: "NVIDIA Corp. (英伟达)", exchange: "NASDAQ", price: 229.28, change_pct: -0.52 },
    { symbol: "TSLA", name: "Tesla, Inc. (特斯拉)", exchange: "NASDAQ", price: 382.70, change_pct: 2.05 },
    { symbol: "SPY", name: "SPDR S&P 500 ETF (标普500)", exchange: "NYSEArca", price: 778.57, change_pct: 0.32 },
    { symbol: "QQQ", name: "Invesco QQQ Trust (纳指100)", exchange: "NASDAQ", price: 751.27, change_pct: 0.45 }
  ];

  const renderDropdown = (items, isPool = false) => {
    if (!dropdown) return;
    dropdown.innerHTML = '';
    if (!items || items.length === 0) {
      dropdown.innerHTML = `<div class="suggestion-empty">未匹配到标的，回车自动跳转分析</div>`;
      dropdown.classList.remove('hidden');
      return;
    }

    const header = document.createElement('div');
    header.className = 'suggestion-header';
    header.innerHTML = isPool 
      ? `<span>🔥 热门备选标的 (点击直接进入分析)</span><span class="suggestion-source-tag">Candidate Pool</span>`
      : `<span>标的检索结果 (点击切换)</span><span class="suggestion-source-tag">Live Quotes</span>`;
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
            <span class="suggestion-meta">${item.exchange || 'MARKET'}</span>
          </div>
        </div>
        <div class="suggestion-right">
          <span class="suggestion-price">${priceStr}</span>
          ${chgHtml}
        </div>
      `;

      el.addEventListener('click', (ev) => {
        ev.stopPropagation();
        selectAndNavigate(item.symbol);
      });

      dropdown.appendChild(el);
    });

    dropdown.classList.remove('hidden');
  };

  const selectAndNavigate = (sym) => {
    let clean = sym.trim().toUpperCase();
    if (clean.length === 6 && /^\d+$/.test(clean)) {
      if (/^(60|688|51|56|58)/.test(clean)) clean = `${clean}.SS`;
      else if (/^(00|30|15|16)/.test(clean)) clean = `${clean}.SZ`;
      else if (/^[849]/.test(clean)) clean = `${clean}.BJ`;
    }
    localStorage.setItem('alphaquant_active_ticker', clean);
    closeDropdown();
    window.location.href = `factor_model.html`;
  };

  const showDropdown = () => {
    const q = searchInput.value.trim().toLowerCase();
    if (!q) {
      renderDropdown(candidates, true);
    } else {
      const filtered = candidates.filter(c => c.symbol.toLowerCase().includes(q) || c.name.toLowerCase().includes(q));
      renderDropdown(filtered, false);
    }
  };

  searchInput.addEventListener('focus', showDropdown);
  searchInput.addEventListener('click', (e) => {
    e.stopPropagation();
    showDropdown();
  });
  searchInput.addEventListener('input', showDropdown);
  searchInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      const val = searchInput.value.trim();
      if (val) selectAndNavigate(val);
    } else if (e.key === 'Escape') {
      closeDropdown();
    }
  });

  if (searchBtn) {
    searchBtn.addEventListener('click', (e) => {
      e.preventDefault();
      const val = searchInput.value.trim();
      if (val) selectAndNavigate(val);
      else showDropdown();
    });
  }

  document.addEventListener('click', (e) => {
    if (searchWrap && !searchWrap.contains(e.target)) {
      closeDropdown();
    }
  });
}
