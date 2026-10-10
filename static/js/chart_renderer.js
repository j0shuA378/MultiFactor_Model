/**
 * AlphaQuant Apple Cupertino Financial Canvas Chart Renderer
 * Features: High-DPI Retina support, SF Pro typography, Apple System Financial Palette,
 * Soft-glow equity curves, Candlesticks with iOS Green/Red, Bollinger Bands,
 * Interactive Crosshair with macOS blur tooltips, and Rolling IC Factor Diagnostics.
 */

// Apple System Financial Palette
const APPLE_PALETTE = {
  blue: '#0A84FF',
  green: '#30D158',
  red: '#FF453A',
  orange: '#FF9F0A',
  teal: '#64D2FF',
  purple: '#BF5AF2',
  gray: '#8E8E93',
  grid: 'rgba(255, 255, 255, 0.04)',
  axisText: 'rgba(235, 235, 245, 0.45)',
  fontSans: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", sans-serif',
  fontMono: '"SF Mono", "JetBrains Mono", Menlo, Consolas, monospace'
};

class CandlestickChart {
  constructor(canvasId, tooltipId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.tooltipEl = document.getElementById(tooltipId);
    this.data = [];
    this.signals = [];
    this.hoverIdx = -1;

    this.setupListeners();
  }

  setData(candles, signals = []) {
    this.data = candles || [];
    this.signals = signals || [];
    this.render();
  }

  setupListeners() {
    if (!this.canvas) return;
    window.addEventListener('resize', () => this.render());

    this.canvas.addEventListener('mousemove', (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const total = this.data.length;
      if (total === 0) return;

      const paddingLeft = 50;
      const paddingRight = 70;
      const chartWidth = this.canvas.clientWidth - paddingLeft - paddingRight;
      const barWidth = chartWidth / total;

      const idx = Math.floor((mouseX - paddingLeft) / barWidth);
      if (idx >= 0 && idx < total) {
        this.hoverIdx = idx;
        this.render();
        this.updateTooltip(this.data[idx]);
      }
    });

    this.canvas.addEventListener('mouseleave', () => {
      this.hoverIdx = -1;
      this.render();
      if (this.tooltipEl) {
        this.tooltipEl.textContent = "移动光标查看具体日K线行情与信号";
      }
    });
  }

  updateTooltip(candle) {
    if (!this.tooltipEl || !candle) return;
    const isUp = candle.close >= candle.open;
    const color = isUp ? APPLE_PALETTE.green : APPLE_PALETTE.red;
    const chg = (((candle.close - candle.open) / candle.open) * 100).toFixed(2);
    
    // Check if signal exists on this date
    const sig = this.signals.find(s => s.date === candle.date);
    let sigText = "";
    if (sig) {
      sigText = ` | 信号: [${sig.type === 'BUY' ? '▲ 买入' : '▼ 卖出'} - ${sig.reason}]`;
    }

    this.tooltipEl.innerHTML = `
      日期: <span style="color:#fff">${candle.date}</span> | 
      开: <span style="color:#fff">$${candle.open.toFixed(2)}</span> | 
      高: <span style="color:#fff">$${candle.high.toFixed(2)}</span> | 
      低: <span style="color:#fff">$${candle.low.toFixed(2)}</span> | 
      收: <span style="color:${color};font-weight:600;">$${candle.close.toFixed(2)} (${chg > 0 ? '+' : ''}${chg}%)</span> | 
      量: <span style="color:${APPLE_PALETTE.axisText}">${(candle.volume / 1e6).toFixed(2)}M</span>${sigText}
    `;
  }

  render() {
    if (!this.canvas) return;
    const dpr = window.devicePixelRatio || 1;
    const width = this.canvas.clientWidth;
    const height = this.canvas.clientHeight;

    this.canvas.width = width * dpr;
    this.canvas.height = height * dpr;
    this.ctx.resetTransform();
    this.ctx.scale(dpr, dpr);

    const ctx = this.ctx;
    ctx.clearRect(0, 0, width, height);

    if (!this.data || this.data.length === 0) {
      ctx.fillStyle = APPLE_PALETTE.axisText;
      ctx.font = `13px ${APPLE_PALETTE.fontSans}`;
      ctx.textAlign = 'center';
      ctx.fillText('暂无行情数据', width / 2, height / 2);
      return;
    }

    const padding = { top: 20, right: 65, bottom: 25, left: 15 };
    const mainHeight = height * 0.72;
    const volHeight = height * 0.20;
    const volTop = height * 0.75;
    const chartWidth = width - padding.left - padding.right;

    // Calculate price range
    let minPrice = Infinity;
    let maxPrice = -Infinity;
    let maxVol = 0;

    for (const c of this.data) {
      if (c.low < minPrice) minPrice = c.low;
      if (c.high > maxPrice) maxPrice = c.high;
      if (c.bb_lower && c.bb_lower < minPrice) minPrice = c.bb_lower;
      if (c.bb_upper && c.bb_upper > maxPrice) maxPrice = c.bb_upper;
      if (c.volume > maxVol) maxVol = c.volume;
    }

    const priceMargin = (maxPrice - minPrice) * 0.08 || 1;
    minPrice -= priceMargin;
    maxPrice += priceMargin;

    const priceToY = (p) => padding.top + (maxPrice - p) / (maxPrice - minPrice) * (mainHeight - padding.top);
    const volToY = (v) => volTop + volHeight - (v / (maxVol || 1)) * volHeight;

    // Draw horizontal grid lines
    ctx.strokeStyle = APPLE_PALETTE.grid;
    ctx.lineWidth = 1;
    const gridSteps = 5;
    ctx.fillStyle = APPLE_PALETTE.axisText;
    ctx.font = `10px ${APPLE_PALETTE.fontMono}`;
    ctx.textAlign = 'left';

    for (let i = 0; i <= gridSteps; i++) {
      const p = minPrice + (maxPrice - minPrice) * (i / gridSteps);
      const y = priceToY(p);
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(width - padding.right, y);
      ctx.stroke();

      ctx.fillText(`$${p.toFixed(2)}`, width - padding.right + 6, y + 3);
    }

    const n = this.data.length;
    const barWidth = chartWidth / n;
    const candleWidth = Math.max(1.5, barWidth * 0.7);

    // Map signals for fast lookup
    const signalMap = {};
    for (const s of this.signals) {
      signalMap[s.date] = s;
    }

    // 1. Draw Bollinger Bands Area
    ctx.fillStyle = 'rgba(191, 90, 242, 0.07)';
    ctx.beginPath();
    let hasBB = false;
    for (let i = 0; i < n; i++) {
      const c = this.data[i];
      if (c.bb_upper && c.bb_lower) {
        const x = padding.left + i * barWidth + barWidth / 2;
        const yUp = priceToY(c.bb_upper);
        if (!hasBB) {
          ctx.moveTo(x, yUp);
          hasBB = true;
        } else {
          ctx.lineTo(x, yUp);
        }
      }
    }
    for (let i = n - 1; i >= 0; i--) {
      const c = this.data[i];
      if (c.bb_upper && c.bb_lower) {
        const x = padding.left + i * barWidth + barWidth / 2;
        const yLow = priceToY(c.bb_lower);
        ctx.lineTo(x, yLow);
      }
    }
    ctx.closePath();
    ctx.fill();

    // 2. Draw Candlesticks & Volume Bars (Apple Green & Red)
    for (let i = 0; i < n; i++) {
      const c = this.data[i];
      const x = padding.left + i * barWidth + barWidth / 2;
      const isUp = c.close >= c.open;
      const color = isUp ? APPLE_PALETTE.green : APPLE_PALETTE.red;

      // Volume bar
      ctx.fillStyle = isUp ? 'rgba(48, 209, 88, 0.35)' : 'rgba(255, 69, 58, 0.35)';
      const vy = volToY(c.volume);
      ctx.fillRect(x - candleWidth / 2, vy, candleWidth, volTop + volHeight - vy);

      // Candlestick Wick (High to Low)
      ctx.strokeStyle = color;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x, priceToY(c.high));
      ctx.lineTo(x, priceToY(c.low));
      ctx.stroke();

      // Candlestick Body (Open to Close)
      const yOpen = priceToY(c.open);
      const yClose = priceToY(c.close);
      const bodyTop = Math.min(yOpen, yClose);
      const bodyHeight = Math.max(1.5, Math.abs(yClose - yOpen));

      ctx.fillStyle = color;
      ctx.fillRect(x - candleWidth / 2, bodyTop, candleWidth, bodyHeight);

      // 3. Trade Signals Marker Overlay
      const sig = signalMap[c.date];
      if (sig) {
        if (sig.type === 'BUY') {
          const markerY = priceToY(c.low) + 14;
          ctx.fillStyle = APPLE_PALETTE.green;
          ctx.beginPath();
          ctx.moveTo(x, markerY - 6);
          ctx.lineTo(x - 5, markerY + 4);
          ctx.lineTo(x + 5, markerY + 4);
          ctx.closePath();
          ctx.fill();
        } else if (sig.type === 'SELL') {
          const markerY = priceToY(c.high) - 14;
          ctx.fillStyle = APPLE_PALETTE.red;
          ctx.beginPath();
          ctx.moveTo(x, markerY + 6);
          ctx.lineTo(x - 5, markerY - 4);
          ctx.lineTo(x + 5, markerY - 4);
          ctx.closePath();
          ctx.fill();
        }
      }
    }

    // 4. Draw EMA Fast (Apple Orange)
    this.drawLineSeries(ctx, this.data.map((c, i) => ({
      x: padding.left + i * barWidth + barWidth / 2,
      y: c.sma_20 ? priceToY(c.sma_20) : null
    })), APPLE_PALETTE.orange, 1.5);

    // 5. Draw EMA Slow (Apple Teal)
    this.drawLineSeries(ctx, this.data.map((c, i) => ({
      x: padding.left + i * barWidth + barWidth / 2,
      y: c.sma_50 ? priceToY(c.sma_50) : null
    })), APPLE_PALETTE.teal, 1.5);

    // 6. Crosshair if hovered
    if (this.hoverIdx >= 0 && this.hoverIdx < n) {
      const hx = padding.left + this.hoverIdx * barWidth + barWidth / 2;
      const hc = this.data[this.hoverIdx];
      const hy = priceToY(hc.close);

      ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(hx, padding.top);
      ctx.lineTo(hx, height - padding.bottom);
      ctx.moveTo(padding.left, hy);
      ctx.lineTo(width - padding.right, hy);
      ctx.stroke();
      ctx.setLineDash([]);
    }
  }

  drawLineSeries(ctx, points, color, lineWidth = 1.5) {
    ctx.strokeStyle = color;
    ctx.lineWidth = lineWidth;
    ctx.beginPath();
    let started = false;

    for (const pt of points) {
      if (pt.y !== null && !isNaN(pt.y)) {
        if (!started) {
          ctx.moveTo(pt.x, pt.y);
          started = true;
        } else {
          ctx.lineTo(pt.x, pt.y);
        }
      }
    }
    ctx.stroke();
  }
}


class EquityChart {
  constructor(canvasId, tooltipId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.tooltipEl = document.getElementById(tooltipId);
    this.records = [];
    this.hoverIdx = -1;

    this.setupListeners();
  }

  setData(records) {
    this.records = records || [];
    this.render();
  }

  setupListeners() {
    if (!this.canvas) return;
    window.addEventListener('resize', () => this.render());

    this.canvas.addEventListener('mousemove', (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const total = this.records.length;
      if (total === 0) return;

      const paddingLeft = 60;
      const paddingRight = 70;
      const chartWidth = this.canvas.clientWidth - paddingLeft - paddingRight;
      const barWidth = chartWidth / total;

      const idx = Math.floor((mouseX - paddingLeft) / barWidth);
      if (idx >= 0 && idx < total) {
        this.hoverIdx = idx;
        this.render();
        this.updateTooltip(this.records[idx]);
      }
    });

    this.canvas.addEventListener('mouseleave', () => {
      this.hoverIdx = -1;
      this.render();
      if (this.tooltipEl) {
        this.tooltipEl.textContent = "资金曲线追踪与动态回撤";
      }
    });
  }

  updateTooltip(rec) {
    if (!this.tooltipEl || !rec) return;
    const stratRet = (((rec.equity - this.records[0].equity) / this.records[0].equity) * 100).toFixed(2);
    const benchRet = (((rec.benchmark - this.records[0].benchmark) / this.records[0].benchmark) * 100).toFixed(2);
    const dd = rec.drawdown_pct ? rec.drawdown_pct.toFixed(2) : '0.00';

    this.tooltipEl.innerHTML = `
      日期: <span style="color:#fff">${rec.date}</span> | 
      策略净值: <span style="color:${APPLE_PALETTE.blue};font-weight:600;">$${rec.equity.toLocaleString()} (${stratRet > 0 ? '+' : ''}${stratRet}%)</span> | 
      基准净值: <span style="color:${APPLE_PALETTE.axisText}">$${rec.benchmark.toLocaleString()} (${benchRet > 0 ? '+' : ''}${benchRet}%)</span> | 
      回撤: <span style="color:${APPLE_PALETTE.red}">-${dd}%</span>
    `;
  }

  render() {
    if (!this.canvas) return;
    const dpr = window.devicePixelRatio || 1;
    const width = this.canvas.clientWidth;
    const height = this.canvas.clientHeight;

    this.canvas.width = width * dpr;
    this.canvas.height = height * dpr;
    this.ctx.resetTransform();
    this.ctx.scale(dpr, dpr);

    const ctx = this.ctx;
    ctx.clearRect(0, 0, width, height);

    if (!this.records || this.records.length === 0) {
      ctx.fillStyle = APPLE_PALETTE.axisText;
      ctx.font = `13px ${APPLE_PALETTE.fontSans}`;
      ctx.textAlign = 'center';
      ctx.fillText('等待回测启动生成净值曲线', width / 2, height / 2);
      return;
    }

    const padding = { top: 20, right: 75, bottom: 25, left: 20 };
    const chartHeight = height - padding.top - padding.bottom;
    const chartWidth = width - padding.left - padding.right;

    let minVal = Infinity;
    let maxVal = -Infinity;

    for (const r of this.records) {
      if (r.equity < minVal) minVal = r.equity;
      if (r.equity > maxVal) maxVal = r.equity;
      if (r.benchmark < minVal) minVal = r.benchmark;
      if (r.benchmark > maxVal) maxVal = r.benchmark;
    }

    const margin = (maxVal - minVal) * 0.1 || 1000;
    minVal -= margin;
    maxVal += margin;

    const valToY = (v) => padding.top + (maxVal - v) / (maxVal - minVal) * chartHeight;

    // Grid lines
    ctx.strokeStyle = APPLE_PALETTE.grid;
    ctx.lineWidth = 1;
    ctx.fillStyle = APPLE_PALETTE.axisText;
    ctx.font = `10px ${APPLE_PALETTE.fontMono}`;
    ctx.textAlign = 'left';

    const gridSteps = 4;
    for (let i = 0; i <= gridSteps; i++) {
      const v = minVal + (maxVal - minVal) * (i / gridSteps);
      const y = valToY(v);
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(width - padding.right, y);
      ctx.stroke();

      ctx.fillText(`$${(v / 1000).toFixed(1)}k`, width - padding.right + 6, y + 3);
    }

    const n = this.records.length;
    const stepX = chartWidth / (n - 1 || 1);

    // 1. Draw Benchmark Line (Muted Apple Gray)
    ctx.strokeStyle = 'rgba(142, 142, 147, 0.65)';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const x = padding.left + i * stepX;
      const y = valToY(this.records[i].benchmark);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.setLineDash([]);

    // 2. Draw Strategy Area Gradient (Apple Blue Soft Fade)
    const grad = ctx.createLinearGradient(0, padding.top, 0, height);
    grad.addColorStop(0, 'rgba(10, 132, 255, 0.22)');
    grad.addColorStop(1, 'rgba(10, 132, 255, 0.00)');

    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.moveTo(padding.left, height - padding.bottom);
    for (let i = 0; i < n; i++) {
      const x = padding.left + i * stepX;
      const y = valToY(this.records[i].equity);
      ctx.lineTo(x, y);
    }
    ctx.lineTo(padding.left + (n - 1) * stepX, height - padding.bottom);
    ctx.closePath();
    ctx.fill();

    // 3. Draw Strategy Glowing Line (Apple Blue)
    ctx.strokeStyle = APPLE_PALETTE.blue;
    ctx.lineWidth = 2.5;
    ctx.shadowColor = 'rgba(10, 132, 255, 0.4)';
    ctx.shadowBlur = 6;
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const x = padding.left + i * stepX;
      const y = valToY(this.records[i].equity);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.shadowBlur = 0;

    // 4. Crosshair indicator
    if (this.hoverIdx >= 0 && this.hoverIdx < n) {
      const hx = padding.left + this.hoverIdx * stepX;
      const hy = valToY(this.records[this.hoverIdx].equity);

      ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(hx, padding.top);
      ctx.lineTo(hx, height - padding.bottom);
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.fillStyle = APPLE_PALETTE.blue;
      ctx.beginPath();
      ctx.arc(hx, hy, 4.5, 0, Math.PI * 2);
      ctx.fill();
    }
  }
}


class MultiEquityChart {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.seriesList = [];
    window.addEventListener('resize', () => this.render());
  }

  setSeries(seriesList) {
    this.seriesList = seriesList || [];
    this.render();
  }

  render() {
    if (!this.canvas) return;
    const dpr = window.devicePixelRatio || 1;
    const width = this.canvas.clientWidth;
    const height = this.canvas.clientHeight;

    this.canvas.width = width * dpr;
    this.canvas.height = height * dpr;
    this.ctx.resetTransform();
    this.ctx.scale(dpr, dpr);

    const ctx = this.ctx;
    ctx.clearRect(0, 0, width, height);

    if (!this.seriesList || this.seriesList.length === 0) return;

    const padding = { top: 20, right: 75, bottom: 25, left: 20 };
    const chartHeight = height - padding.top - padding.bottom;
    const chartWidth = width - padding.left - padding.right;

    let minVal = Infinity;
    let maxVal = -Infinity;

    for (const s of this.seriesList) {
      for (const pt of s.data) {
        if (pt.val < minVal) minVal = pt.val;
        if (pt.val > maxVal) maxVal = pt.val;
      }
    }

    const margin = (maxVal - minVal) * 0.1 || 1000;
    minVal -= margin;
    maxVal += margin;

    const valToY = (v) => padding.top + (maxVal - v) / (maxVal - minVal) * chartHeight;

    // Grid lines
    ctx.strokeStyle = APPLE_PALETTE.grid;
    ctx.lineWidth = 1;
    ctx.fillStyle = APPLE_PALETTE.axisText;
    ctx.font = `10px ${APPLE_PALETTE.fontMono}`;
    ctx.textAlign = 'left';

    const gridSteps = 4;
    for (let i = 0; i <= gridSteps; i++) {
      const v = minVal + (maxVal - minVal) * (i / gridSteps);
      const y = valToY(v);
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(width - padding.right, y);
      ctx.stroke();

      ctx.fillText(`$${(v / 1000).toFixed(1)}k`, width - padding.right + 6, y + 3);
    }

    // Draw each series
    for (const s of this.seriesList) {
      const pts = s.data;
      const n = pts.length;
      if (n < 2) continue;
      const stepX = chartWidth / (n - 1);

      ctx.strokeStyle = s.color;
      ctx.lineWidth = s.lineWidth || 2;
      if (s.dashed) ctx.setLineDash([3, 3]);
      else ctx.setLineDash([]);

      ctx.beginPath();
      for (let i = 0; i < n; i++) {
        const x = padding.left + i * stepX;
        const y = valToY(pts[i].val);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
      ctx.setLineDash([]);
    }
  }
}

class RollingICChart {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.data = [];
    this.overallIC = 0.0;
    this.hoverIdx = -1;
    window.addEventListener('resize', () => this.render());
    this.setupListeners();
  }

  setData(data, overallIC = 0.0) {
    this.data = data || [];
    this.overallIC = overallIC;
    this.render();
  }

  setupListeners() {
    if (!this.canvas) return;
    this.canvas.addEventListener('mousemove', (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const total = this.data.length;
      if (total === 0) return;

      const paddingLeft = 35;
      const paddingRight = 55;
      const chartWidth = this.canvas.clientWidth - paddingLeft - paddingRight;
      const stepX = chartWidth / (total - 1 || 1);

      const idx = Math.round((mouseX - paddingLeft) / stepX);
      if (idx >= 0 && idx < total) {
        this.hoverIdx = idx;
        this.render();
      }
    });

    this.canvas.addEventListener('mouseleave', () => {
      this.hoverIdx = -1;
      this.render();
    });
  }

  render() {
    if (!this.canvas) return;
    const dpr = window.devicePixelRatio || 1;
    const width = this.canvas.clientWidth;
    const height = this.canvas.clientHeight;

    this.canvas.width = width * dpr;
    this.canvas.height = height * dpr;
    this.ctx.resetTransform();
    this.ctx.scale(dpr, dpr);

    const ctx = this.ctx;
    ctx.clearRect(0, 0, width, height);

    if (!this.data || this.data.length === 0) {
      ctx.fillStyle = APPLE_PALETTE.axisText;
      ctx.font = `12px ${APPLE_PALETTE.fontSans}`;
      ctx.textAlign = 'center';
      ctx.fillText('暂无滚动 IC 因子诊断数据', width / 2, height / 2);
      return;
    }

    const padding = { top: 18, right: 55, bottom: 22, left: 35 };
    const chartHeight = height - padding.top - padding.bottom;
    const chartWidth = width - padding.left - padding.right;
    const n = this.data.length;

    let minIC = -0.3;
    let maxIC = 0.3;
    for (const d of this.data) {
      if (d.ic < minIC) minIC = Math.floor(d.ic * 10) / 10 - 0.05;
      if (d.ic > maxIC) maxIC = Math.ceil(d.ic * 10) / 10 + 0.05;
    }

    minIC = Math.min(minIC, -0.2);
    maxIC = Math.max(maxIC, 0.2);

    const valToY = (v) => padding.top + (maxIC - v) / (maxIC - minIC) * chartHeight;
    const stepX = chartWidth / (n - 1 || 1);
    const zeroY = valToY(0);

    // 1. Grid & Y-Axis labels
    ctx.strokeStyle = APPLE_PALETTE.grid;
    ctx.lineWidth = 1;
    ctx.fillStyle = APPLE_PALETTE.axisText;
    ctx.font = `10px ${APPLE_PALETTE.fontMono}`;
    ctx.textAlign = 'left';

    const levels = [minIC, minIC / 2, 0, maxIC / 2, maxIC];
    for (const lvl of levels) {
      const y = valToY(lvl);
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(width - padding.right, y);
      ctx.stroke();
      ctx.fillText(lvl.toFixed(2), width - padding.right + 5, y + 3);
    }

    // 2. Zero baseline highlight
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.moveTo(padding.left, zeroY);
    ctx.lineTo(width - padding.right, zeroY);
    ctx.stroke();

    // 3. Positive / Negative Bars (Apple Green & Red)
    for (let i = 0; i < n; i++) {
      const x = padding.left + i * stepX;
      const v = this.data[i].ic;
      const y = valToY(v);
      const isPos = v >= 0;

      const barW = Math.max(2, (chartWidth / n) * 0.7);
      ctx.fillStyle = isPos ? 'rgba(48, 209, 88, 0.65)' : 'rgba(255, 69, 58, 0.65)';
      ctx.fillRect(x - barW / 2, Math.min(y, zeroY), barW, Math.abs(y - zeroY));
    }

    // 4. Smooth trend line (Apple Blue)
    ctx.strokeStyle = APPLE_PALETTE.blue;
    ctx.lineWidth = 2;
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const x = padding.left + i * stepX;
      const y = valToY(this.data[i].ic);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // 5. Mean IC dashed benchmark line (Apple Orange)
    const meanY = valToY(this.overallIC);
    ctx.strokeStyle = APPLE_PALETTE.orange;
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(padding.left, meanY);
    ctx.lineTo(width - padding.right, meanY);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = APPLE_PALETTE.orange;
    ctx.fillText(`均值: ${this.overallIC >= 0 ? '+' : ''}${this.overallIC.toFixed(3)}`, padding.left + 5, meanY - 4);

    // 6. Hover indicator
    if (this.hoverIdx >= 0 && this.hoverIdx < n) {
      const item = this.data[this.hoverIdx];
      const hx = padding.left + this.hoverIdx * stepX;
      const hy = valToY(item.ic);

      ctx.strokeStyle = 'rgba(255, 255, 255, 0.5)';
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(hx, padding.top);
      ctx.lineTo(hx, height - padding.bottom);
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.fillStyle = item.ic >= 0 ? APPLE_PALETTE.green : APPLE_PALETTE.red;
      ctx.beginPath();
      ctx.arc(hx, hy, 4.5, 0, Math.PI * 2);
      ctx.fill();

      // Tooltip box (Apple Frosted Glass style)
      const text = `${item.date}: IC ${item.ic >= 0 ? '+' : ''}${item.ic.toFixed(3)}`;
      ctx.font = `10.5px ${APPLE_PALETTE.fontMono}`;
      const tw = ctx.measureText(text).width;
      const tx = Math.min(width - padding.right - tw - 10, Math.max(padding.left, hx - tw / 2));
      const ty = Math.max(padding.top + 14, hy - 10);

      ctx.fillStyle = 'rgba(28, 28, 32, 0.92)';
      ctx.fillRect(tx - 6, ty - 12, tw + 12, 18);
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.15)';
      ctx.strokeRect(tx - 6, ty - 12, tw + 12, 18);
      ctx.fillStyle = '#fff';
      ctx.fillText(text, tx, ty);
    }
  }
}
