/**
 * AlphaQuant Institutional Financial Canvas Chart Renderer
 * Inspired by Goldman Sachs & Invesco institutional web portals.
 * Features: High-DPI Retina support, Crisp Institutional White Theme,
 * High-legibility typography, Invesco Royal Navy (#0052cc) equity curves,
 * Clean forest-green/crimson candlesticks, and crisp reference axes.
 */

const INSTITUTIONAL_PALETTE = {
  blue: '#0052cc',        // Goldman/Invesco Signature Royal Navy-Blue
  green: '#16a34a',       // Institutional Profit Green (Forest Green)
  red: '#dc2626',         // Institutional Loss Red (Crimson)
  orange: '#d97706',      // Warm Amber (Gold/Bronze)
  teal: '#0284c7',        // Sky Slate
  purple: '#6366f1',      // Refined Indigo
  gray: '#64748b',        // Slate Gray Benchmark
  grayLight: '#94a3b8',   // Light Slate
  grid: '#f1f5f9',        // Light reference grid lines
  gridBorder: '#e2e8f0',  // Chart baseline
  axisText: '#64748b',    // Clear dark slate text
  darkText: '#0f172a',    // Deep Navy-Charcoal Text
  crosshair: 'rgba(15, 23, 42, 0.4)', // Crosshair
  fontSans: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
  fontMono: '"JetBrains Mono", "SF Mono", Menlo, Consolas, monospace'
};

class CandlestickChart {
  constructor(canvasId, tooltipId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.tooltipEl = document.getElementById(tooltipId);
    this.data = [];
    this.signals = [];
    this.predictionLevels = null;
    this.showProjectionLines = true;
    this.padding = { top: 22, right: 86, bottom: 25, left: 15 };
    this.hoverIdx = -1;

    this.setupListeners();
  }

  setData(candles, signals = [], predictionLevels = null) {
    this.data = candles || [];
    this.signals = signals || [];
    if (predictionLevels !== null && predictionLevels !== undefined) {
      this.predictionLevels = predictionLevels;
    }
    this.render();
  }

  setPredictionLevels(predictionLevels) {
    this.predictionLevels = predictionLevels;
    this.render();
  }

  toggleProjectionLines() {
    this.showProjectionLines = !this.showProjectionLines;
    this.render();
    return this.showProjectionLines;
  }

  setupListeners() {
    if (!this.canvas) return;
    window.addEventListener('resize', () => this.render());

    this.canvas.addEventListener('mousemove', (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const total = this.data.length;
      if (total === 0) return;

      const paddingLeft = this.padding.left;
      const paddingRight = this.padding.right;
      const chartWidth = this.canvas.clientWidth - paddingLeft - paddingRight;
      const extraBars = (this.predictionLevels && this.showProjectionLines) ? 7 : 0;
      const barWidth = chartWidth / (total + extraBars);

      const idx = Math.floor((mouseX - paddingLeft) / barWidth);
      if (idx >= 0 && idx < total) {
        this.hoverIdx = idx;
        this.render();
        this.updateTooltip(this.data[idx]);
      } else if (idx >= total && this.predictionLevels) {
        // Hovering over forward projection zone
        this.hoverIdx = -1;
        this.render();
        if (this.tooltipEl) {
          const buyP = Number(this.predictionLevels.expectedBuy ?? this.predictionLevels.expected_buy ?? 0).toFixed(2);
          const tpP = Number(this.predictionLevels.targetProfit ?? this.predictionLevels.target_profit ?? 0).toFixed(2);
          const slP = Number(this.predictionLevels.stopLoss ?? this.predictionLevels.stop_loss ?? 0).toFixed(2);
          this.tooltipEl.innerHTML = `
            <span style="color:#0052cc;font-weight:700;">✦ 前瞻预测:</span> 
            核心买点: <span style="color:#16a34a;font-weight:700;">$${buyP}</span> | 
            止盈目标: <span style="color:#0284c7;font-weight:700;">$${tpP} (${this.predictionLevels.target_gain_pct || ''})</span> | 
            止损防守: <span style="color:#dc2626;font-weight:700;">$${slP} (${this.predictionLevels.stop_loss_pct || ''})</span> | 
            盈亏比: <span style="color:#0f172a;font-weight:700;">${this.predictionLevels.risk_reward_ratio || '1:2.4'}</span>
          `;
        }
      }
    });

    this.canvas.addEventListener('mouseleave', () => {
      this.hoverIdx = -1;
      this.render();
      if (this.tooltipEl) {
        this.tooltipEl.textContent = "移动光标至图表区域查看日K线行情与信号标定";
      }
    });
  }

  updateTooltip(candle) {
    if (!this.tooltipEl || !candle) return;
    const isUp = candle.close >= candle.open;
    const color = isUp ? INSTITUTIONAL_PALETTE.green : INSTITUTIONAL_PALETTE.red;
    const chg = (((candle.close - candle.open) / candle.open) * 100).toFixed(2);
    
    // Check if signal exists on this date
    const sig = this.signals.find(s => s.date === candle.date);
    let sigText = "";
    if (sig) {
      const sigColor = sig.type === 'BUY' ? INSTITUTIONAL_PALETTE.green : INSTITUTIONAL_PALETTE.red;
      sigText = ` | <span style="color:${sigColor};font-weight:700;">[${sig.type === 'BUY' ? '▲ 买入' : '▼ 卖出'} - ${sig.reason}]</span>`;
    }

    this.tooltipEl.innerHTML = `
      日期: <span style="color:${INSTITUTIONAL_PALETTE.darkText};font-weight:600;">${candle.date}</span> | 
      开: <span style="color:${INSTITUTIONAL_PALETTE.darkText}">$${candle.open.toFixed(2)}</span> | 
      高: <span style="color:${INSTITUTIONAL_PALETTE.darkText}">$${candle.high.toFixed(2)}</span> | 
      低: <span style="color:${INSTITUTIONAL_PALETTE.darkText}">$${candle.low.toFixed(2)}</span> | 
      收: <span style="color:${color};font-weight:700;">$${candle.close.toFixed(2)} (${chg > 0 ? '+' : ''}${chg}%)</span> | 
      量: <span style="color:${INSTITUTIONAL_PALETTE.axisText}">${(candle.volume / 1e6).toFixed(2)}M</span>${sigText}
    `;
  }

  render() {
    if (!this.canvas) return;
    const dpr = window.devicePixelRatio || 1;
    const width = this.canvas.clientWidth;
    const height = this.canvas.clientHeight;
    if (width <= 0 || height <= 0) return;

    this.canvas.width = width * dpr;
    this.canvas.height = height * dpr;
    this.ctx.resetTransform();
    this.ctx.scale(dpr, dpr);

    const ctx = this.ctx;
    ctx.clearRect(0, 0, width, height);

    if (!this.data || this.data.length === 0) {
      ctx.fillStyle = INSTITUTIONAL_PALETTE.axisText;
      ctx.font = `13px ${INSTITUTIONAL_PALETTE.fontSans}`;
      ctx.textAlign = 'center';
      ctx.fillText('暂无行情数据', width / 2, height / 2);
      return;
    }

    const padding = this.padding;
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

    // Include prediction levels in visible y-scale
    if (this.predictionLevels && this.showProjectionLines) {
      const pred = this.predictionLevels;
      const buyP = Number(pred.expectedBuy ?? pred.expected_buy);
      const tpP = Number(pred.targetProfit ?? pred.target_profit);
      const slP = Number(pred.stopLoss ?? pred.stop_loss);
      if (!isNaN(buyP) && buyP > 0) {
        minPrice = Math.min(minPrice, buyP);
        maxPrice = Math.max(maxPrice, buyP);
      }
      if (!isNaN(tpP) && tpP > 0) {
        maxPrice = Math.max(maxPrice, tpP);
      }
      if (!isNaN(slP) && slP > 0) {
        minPrice = Math.min(minPrice, slP);
      }
    }

    const priceMargin = (maxPrice - minPrice) * 0.08 || 1;
    minPrice -= priceMargin;
    maxPrice += priceMargin;

    const priceToY = (p) => padding.top + (maxPrice - p) / (maxPrice - minPrice) * (mainHeight - padding.top);
    const volToY = (v) => volTop + volHeight - (v / (maxVol || 1)) * volHeight;

    // Draw horizontal grid lines
    ctx.strokeStyle = INSTITUTIONAL_PALETTE.grid;
    ctx.lineWidth = 1;
    const gridSteps = 5;
    ctx.fillStyle = INSTITUTIONAL_PALETTE.axisText;
    ctx.font = `11px ${INSTITUTIONAL_PALETTE.fontMono}`;
    ctx.textAlign = 'left';

    const activeBadgeYs = [];
    if (this.predictionLevels && this.showProjectionLines) {
      const pred = this.predictionLevels;
      const bP = Number(pred.expectedBuy ?? pred.expected_buy);
      const tP = Number(pred.targetProfit ?? pred.target_profit);
      const sP = Number(pred.stopLoss ?? pred.stop_loss);
      if (!isNaN(bP)) activeBadgeYs.push(priceToY(bP));
      if (!isNaN(tP)) activeBadgeYs.push(priceToY(tP));
      if (!isNaN(sP)) activeBadgeYs.push(priceToY(sP));
    }

    for (let i = 0; i <= gridSteps; i++) {
      const p = minPrice + (maxPrice - minPrice) * (i / gridSteps);
      const y = priceToY(p);
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(width - padding.right, y);
      ctx.stroke();

      const collides = activeBadgeYs.some(by => Math.abs(by - y) < 14);
      if (!collides) {
        ctx.fillText(`$${p.toFixed(2)}`, width - padding.right + 6, y + 4);
      }
    }

    const n = this.data.length;
    const extraBars = (this.predictionLevels && this.showProjectionLines) ? 7 : 0;
    const barWidth = chartWidth / (n + extraBars);
    const candleWidth = Math.max(1.8, barWidth * 0.7);

    // Map signals for fast lookup
    const signalMap = {};
    for (const s of this.signals) {
      signalMap[s.date] = s;
    }

    // 1. Draw Bollinger Bands Area
    ctx.fillStyle = 'rgba(99, 102, 241, 0.06)';
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

    // 2. Draw Candlesticks & Volume Bars
    for (let i = 0; i < n; i++) {
      const c = this.data[i];
      const x = padding.left + i * barWidth + barWidth / 2;
      const isUp = c.close >= c.open;
      const color = isUp ? INSTITUTIONAL_PALETTE.green : INSTITUTIONAL_PALETTE.red;

      // Volume bar
      ctx.fillStyle = isUp ? 'rgba(22, 163, 74, 0.22)' : 'rgba(220, 38, 38, 0.22)';
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
      const bodyHeight = Math.max(1.8, Math.abs(yClose - yOpen));

      ctx.fillStyle = color;
      ctx.fillRect(x - candleWidth / 2, bodyTop, candleWidth, bodyHeight);

      // 3. Trade Signals Marker Overlay
      const sig = signalMap[c.date];
      if (sig) {
        if (sig.type === 'BUY') {
          const markerY = priceToY(c.low) + 14;
          ctx.fillStyle = INSTITUTIONAL_PALETTE.green;
          ctx.beginPath();
          ctx.moveTo(x, markerY - 7);
          ctx.lineTo(x - 5, markerY + 4);
          ctx.lineTo(x + 5, markerY + 4);
          ctx.closePath();
          ctx.fill();
        } else if (sig.type === 'SELL') {
          const markerY = priceToY(c.high) - 14;
          ctx.fillStyle = INSTITUTIONAL_PALETTE.red;
          ctx.beginPath();
          ctx.moveTo(x, markerY + 7);
          ctx.lineTo(x - 5, markerY - 4);
          ctx.lineTo(x + 5, markerY - 4);
          ctx.closePath();
          ctx.fill();
        }
      }
    }

    // 4. Draw EMA Fast (Institutional Amber)
    this.drawLineSeries(ctx, this.data.map((c, i) => ({
      x: padding.left + i * barWidth + barWidth / 2,
      y: c.sma_20 ? priceToY(c.sma_20) : null
    })), INSTITUTIONAL_PALETTE.orange, 1.8);

    // 5. Draw EMA Slow (Institutional Sky Blue)
    this.drawLineSeries(ctx, this.data.map((c, i) => ({
      x: padding.left + i * barWidth + barWidth / 2,
      y: c.sma_50 ? priceToY(c.sma_50) : null
    })), INSTITUTIONAL_PALETTE.teal, 1.8);

    // 6. Draw Forward Trade Predictions & Buy Point Overlays (Cirled Area on Right)
    if (this.predictionLevels && this.showProjectionLines && n > 0) {
      this.drawPredictionOverlay(ctx, width, height, padding, priceToY, minPrice, maxPrice, barWidth, n);
    }

    // 7. Crosshair if hovered
    if (this.hoverIdx >= 0 && this.hoverIdx < n) {
      const hx = padding.left + this.hoverIdx * barWidth + barWidth / 2;
      const hc = this.data[this.hoverIdx];
      const hy = priceToY(hc.close);

      ctx.strokeStyle = INSTITUTIONAL_PALETTE.crosshair;
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

  drawPredictionOverlay(ctx, width, height, padding, priceToY, minPrice, maxPrice, barWidth, n) {
    const pred = this.predictionLevels;
    const cLast = this.data[n - 1];
    const xLast = padding.left + (n - 1) * barWidth + barWidth / 2;
    const yLast = priceToY(cLast.close);
    const rightEdge = width - padding.right;
    const zoneLeft = Math.max(padding.left, xLast - barWidth * 12);

    const buyPrice = Number(pred.expectedBuy ?? pred.expected_buy);
    const tpPrice = Number(pred.targetProfit ?? pred.target_profit);
    const slPrice = Number(pred.stopLoss ?? pred.stop_loss);
    const buyMin = Number(pred.buy_range_min || buyPrice * 0.992);
    const buyMax = Number(pred.buy_range_max || buyPrice * 1.008);

    // 1. Shaded Accumulation Zone for Expected Buy
    if (!isNaN(buyMin) && !isNaN(buyMax)) {
      const yMax = priceToY(buyMax);
      const yMin = priceToY(buyMin);
      ctx.fillStyle = 'rgba(22, 163, 74, 0.08)';
      ctx.fillRect(zoneLeft, Math.min(yMax, yMin), rightEdge - zoneLeft, Math.max(4, Math.abs(yMin - yMax)));

      ctx.strokeStyle = 'rgba(22, 163, 74, 0.28)';
      ctx.lineWidth = 1;
      ctx.setLineDash([2, 2]);
      ctx.strokeRect(zoneLeft, Math.min(yMax, yMin), rightEdge - zoneLeft, Math.max(4, Math.abs(yMin - yMax)));
      ctx.setLineDash([]);
    }

    // 2. Expected Buy Point Horizontal Line
    if (!isNaN(buyPrice)) {
      const yBuy = priceToY(buyPrice);
      ctx.strokeStyle = '#16a34a';
      ctx.lineWidth = 1.8;
      ctx.setLineDash([6, 3]);
      ctx.beginPath();
      ctx.moveTo(zoneLeft, yBuy);
      ctx.lineTo(rightEdge, yBuy);
      ctx.stroke();
      ctx.setLineDash([]);

      this.drawAxisBadge(ctx, rightEdge + 3, yBuy, `🟢买点 $${buyPrice.toFixed(2)}`, '#16a34a');
    }

    // 3. Target Profit Horizontal Line
    if (!isNaN(tpPrice)) {
      const yTp = priceToY(tpPrice);
      ctx.strokeStyle = '#0284c7';
      ctx.lineWidth = 1.6;
      ctx.setLineDash([6, 3]);
      ctx.beginPath();
      ctx.moveTo(xLast, yTp);
      ctx.lineTo(rightEdge, yTp);
      ctx.stroke();
      ctx.setLineDash([]);

      this.drawAxisBadge(ctx, rightEdge + 3, yTp, `🎯止盈 $${tpPrice.toFixed(2)}`, '#0284c7');
    }

    // 4. Stop Loss Horizontal Line
    if (!isNaN(slPrice)) {
      const ySl = priceToY(slPrice);
      ctx.strokeStyle = '#dc2626';
      ctx.lineWidth = 1.6;
      ctx.setLineDash([5, 3]);
      ctx.beginPath();
      ctx.moveTo(xLast, ySl);
      ctx.lineTo(rightEdge, ySl);
      ctx.stroke();
      ctx.setLineDash([]);

      this.drawAxisBadge(ctx, rightEdge + 3, ySl, `🛡️止损 $${slPrice.toFixed(2)}`, '#dc2626');
    }

    // 5. Future 5-Day Forward Forecast Cone & Arrow Trajectory
    const futureX = Math.min(rightEdge - 6, xLast + barWidth * 5);
    const targetY = (pred.status === 'WAITING_BUY' && buyPrice < cLast.close)
      ? priceToY(buyPrice)
      : priceToY(tpPrice);

    // Shaded forecast cone
    ctx.fillStyle = 'rgba(22, 163, 74, 0.07)';
    ctx.beginPath();
    ctx.moveTo(xLast, yLast);
    ctx.lineTo(futureX, targetY - 14);
    ctx.lineTo(futureX, targetY + 14);
    ctx.closePath();
    ctx.fill();

    // Dotted projection ray
    ctx.strokeStyle = '#16a34a';
    ctx.lineWidth = 1.8;
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(xLast, yLast);
    ctx.lineTo(futureX, targetY);
    ctx.stroke();
    ctx.setLineDash([]);

    // Future endpoint marker dot
    ctx.fillStyle = '#16a34a';
    ctx.beginPath();
    ctx.arc(futureX, targetY, 3.5, 0, Math.PI * 2);
    ctx.fill();

    // Text label for forward forecast
    ctx.font = `bold 10px ${INSTITUTIONAL_PALETTE.fontSans}`;
    ctx.fillStyle = '#0f172a';
    ctx.textAlign = 'right';
    ctx.fillText('✦ 5日预期通道', futureX - 6, targetY - 6);
  }

  drawAxisBadge(ctx, x, y, text, bgColor) {
    const w = 78;
    const h = 18;
    const radius = 3;
    const top = y - h / 2;

    ctx.fillStyle = bgColor;
    ctx.beginPath();
    ctx.moveTo(x + radius, top);
    ctx.lineTo(x + w - radius, top);
    ctx.quadraticCurveTo(x + w, top, x + w, top + radius);
    ctx.lineTo(x + w, top + h - radius);
    ctx.quadraticCurveTo(x + w, top + h, x + w - radius, top + h);
    ctx.lineTo(x + radius, top + h);
    ctx.quadraticCurveTo(x, top + h, x, top + h - radius);
    ctx.lineTo(x, top + radius);
    ctx.quadraticCurveTo(x, top, x + radius, top);
    ctx.closePath();
    ctx.fill();

    ctx.fillStyle = '#ffffff';
    ctx.font = `bold 9.5px ${INSTITUTIONAL_PALETTE.fontMono}`;
    ctx.textAlign = 'center';
    ctx.fillText(text, x + w / 2, y + 3.5);
  }

  drawLineSeries(ctx, points, color, lineWidth = 1.8) {
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
    this.padding = { top: 20, right: 75, bottom: 25, left: 20 };
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

      const paddingLeft = this.padding.left;
      const paddingRight = this.padding.right;
      const chartWidth = this.canvas.clientWidth - paddingLeft - paddingRight;
      const stepX = chartWidth / (total - 1 || 1);

      const idx = Math.max(0, Math.min(total - 1, Math.round((mouseX - paddingLeft) / stepX)));
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
        this.tooltipEl.textContent = "多因子投资组合净值走势与动态基准对比";
      }
    });
  }

  updateTooltip(rec) {
    if (!this.tooltipEl || !rec) return;
    const stratRet = (((rec.equity - this.records[0].equity) / this.records[0].equity) * 100).toFixed(2);
    const benchRet = (((rec.benchmark - this.records[0].benchmark) / this.records[0].benchmark) * 100).toFixed(2);
    const dd = rec.drawdown_pct ? rec.drawdown_pct.toFixed(2) : '0.00';

    this.tooltipEl.innerHTML = `
      日期: <span style="color:${INSTITUTIONAL_PALETTE.darkText};font-weight:600;">${rec.date}</span> | 
      策略净值: <span style="color:${INSTITUTIONAL_PALETTE.blue};font-weight:700;">$${rec.equity.toLocaleString()} (${stratRet > 0 ? '+' : ''}${stratRet}%)</span> | 
      基准净值: <span style="color:${INSTITUTIONAL_PALETTE.axisText}">$${rec.benchmark.toLocaleString()} (${benchRet > 0 ? '+' : ''}${benchRet}%)</span> | 
      回撤: <span style="color:${INSTITUTIONAL_PALETTE.red};font-weight:600;">-${dd}%</span>
    `;
  }

  render() {
    if (!this.canvas) return;
    const dpr = window.devicePixelRatio || 1;
    const width = this.canvas.clientWidth;
    const height = this.canvas.clientHeight;
    if (width <= 0 || height <= 0) return;

    this.canvas.width = width * dpr;
    this.canvas.height = height * dpr;
    this.ctx.resetTransform();
    this.ctx.scale(dpr, dpr);

    const ctx = this.ctx;
    ctx.clearRect(0, 0, width, height);

    if (!this.records || this.records.length === 0) {
      ctx.fillStyle = INSTITUTIONAL_PALETTE.axisText;
      ctx.font = `13px ${INSTITUTIONAL_PALETTE.fontSans}`;
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
      const eq = Number(r.equity);
      const bn = Number(r.benchmark);
      if (!isNaN(eq)) {
        if (eq < minVal) minVal = eq;
        if (eq > maxVal) maxVal = eq;
      }
      if (!isNaN(bn)) {
        if (bn < minVal) minVal = bn;
        if (bn > maxVal) maxVal = bn;
      }
    }

    if (!isFinite(minVal) || !isFinite(maxVal) || minVal >= maxVal) {
      minVal = 95000;
      maxVal = 105000;
    }

    const margin = (maxVal - minVal) * 0.1 || 1000;
    minVal -= margin;
    maxVal += margin;

    const valToY = (v) => padding.top + (maxVal - v) / (maxVal - minVal) * chartHeight;

    // Grid lines
    ctx.strokeStyle = INSTITUTIONAL_PALETTE.grid;
    ctx.lineWidth = 1;
    ctx.fillStyle = INSTITUTIONAL_PALETTE.axisText;
    ctx.font = `11px ${INSTITUTIONAL_PALETTE.fontMono}`;
    ctx.textAlign = 'left';

    const gridSteps = 4;
    for (let i = 0; i <= gridSteps; i++) {
      const v = minVal + (maxVal - minVal) * (i / gridSteps);
      const y = valToY(v);
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(width - padding.right, y);
      ctx.stroke();

      ctx.fillText(`$${(v / 1000).toFixed(1)}k`, width - padding.right + 8, y + 4);
    }

    const n = this.records.length;
    const stepX = chartWidth / (n - 1 || 1);

    // 1. Draw Benchmark Line (Muted Institutional Slate)
    ctx.strokeStyle = INSTITUTIONAL_PALETTE.grayLight;
    ctx.lineWidth = 1.8;
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

    // 2. Draw Strategy Area Gradient (Invesco Royal Blue Soft Fade)
    const grad = ctx.createLinearGradient(0, padding.top, 0, height);
    grad.addColorStop(0, 'rgba(0, 82, 204, 0.12)');
    grad.addColorStop(1, 'rgba(0, 82, 204, 0.00)');

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

    // 3. Draw Strategy Solid Line (Institutional Navy-Blue #0052cc)
    ctx.strokeStyle = INSTITUTIONAL_PALETTE.blue;
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const x = padding.left + i * stepX;
      const y = valToY(this.records[i].equity);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // 4. Crosshair indicator
    if (this.hoverIdx >= 0 && this.hoverIdx < n) {
      const hx = padding.left + this.hoverIdx * stepX;
      const hy = valToY(this.records[this.hoverIdx].equity);

      ctx.strokeStyle = INSTITUTIONAL_PALETTE.crosshair;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(hx, padding.top);
      ctx.lineTo(hx, height - padding.bottom);
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.fillStyle = INSTITUTIONAL_PALETTE.blue;
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
    this.padding = { top: 20, right: 75, bottom: 25, left: 20 };
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
    if (width <= 0 || height <= 0) return;

    this.canvas.width = width * dpr;
    this.canvas.height = height * dpr;
    this.ctx.resetTransform();
    this.ctx.scale(dpr, dpr);

    const ctx = this.ctx;
    ctx.clearRect(0, 0, width, height);

    if (!this.seriesList || this.seriesList.length === 0) return;

    const padding = this.padding;
    const chartHeight = height - padding.top - padding.bottom;
    const chartWidth = width - padding.left - padding.right;

    let minVal = Infinity;
    let maxVal = -Infinity;

    // Collect and sort all unique dates across series to build a unified chronological timeline
    const dateSet = new Set();
    for (const s of this.seriesList) {
      for (const pt of (s.data || [])) {
        if (pt.date) dateSet.add(pt.date);
        const v = Number(pt.val);
        if (!isNaN(v)) {
          if (v < minVal) minVal = v;
          if (v > maxVal) maxVal = v;
        }
      }
    }

    const allDates = Array.from(dateSet).sort();
    const dateMap = {};
    allDates.forEach((d, idx) => { dateMap[d] = idx; });
    const totalDates = allDates.length;
    const stepX = chartWidth / (totalDates - 1 || 1);

    if (!isFinite(minVal) || !isFinite(maxVal) || minVal >= maxVal) {
      minVal = 95000;
      maxVal = 105000;
    }

    const margin = (maxVal - minVal) * 0.1 || 1000;
    minVal -= margin;
    maxVal += margin;

    const valToY = (v) => padding.top + (maxVal - v) / (maxVal - minVal) * chartHeight;

    // Grid lines
    ctx.strokeStyle = INSTITUTIONAL_PALETTE.grid;
    ctx.lineWidth = 1;
    ctx.fillStyle = INSTITUTIONAL_PALETTE.axisText;
    ctx.font = `11px ${INSTITUTIONAL_PALETTE.fontMono}`;
    ctx.textAlign = 'left';

    const gridSteps = 4;
    for (let i = 0; i <= gridSteps; i++) {
      const v = minVal + (maxVal - minVal) * (i / gridSteps);
      const y = valToY(v);
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(width - padding.right, y);
      ctx.stroke();

      ctx.fillText(`$${(v / 1000).toFixed(1)}k`, width - padding.right + 8, y + 4);
    }

    // Draw each series accurately aligned by date
    for (const s of this.seriesList) {
      const pts = s.data || [];
      if (pts.length < 2) continue;

      ctx.strokeStyle = s.color || INSTITUTIONAL_PALETTE.blue;
      ctx.lineWidth = s.lineWidth || 2;
      if (s.dashed) ctx.setLineDash([3, 3]);
      else ctx.setLineDash([]);

      ctx.beginPath();
      let first = true;
      for (let i = 0; i < pts.length; i++) {
        const pt = pts[i];
        const dateIdx = (pt.date && dateMap[pt.date] !== undefined) ? dateMap[pt.date] : i;
        const x = padding.left + dateIdx * stepX;
        const y = valToY(pt.val);
        if (first) {
          ctx.moveTo(x, y);
          first = false;
        } else {
          ctx.lineTo(x, y);
        }
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
    if (width <= 0 || height <= 0) return;

    this.canvas.width = width * dpr;
    this.canvas.height = height * dpr;
    this.ctx.resetTransform();
    this.ctx.scale(dpr, dpr);

    const ctx = this.ctx;
    ctx.clearRect(0, 0, width, height);

    if (!this.data || this.data.length === 0) {
      ctx.fillStyle = INSTITUTIONAL_PALETTE.axisText;
      ctx.font = `12px ${INSTITUTIONAL_PALETTE.fontSans}`;
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
    ctx.strokeStyle = INSTITUTIONAL_PALETTE.grid;
    ctx.lineWidth = 1;
    ctx.fillStyle = INSTITUTIONAL_PALETTE.axisText;
    ctx.font = `10px ${INSTITUTIONAL_PALETTE.fontMono}`;
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
    ctx.strokeStyle = INSTITUTIONAL_PALETTE.gridBorder;
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.moveTo(padding.left, zeroY);
    ctx.lineTo(width - padding.right, zeroY);
    ctx.stroke();

    // 3. Positive / Negative Bars (Institutional Green & Red)
    for (let i = 0; i < n; i++) {
      const x = padding.left + i * stepX;
      const v = this.data[i].ic;
      const y = valToY(v);
      const isPos = v >= 0;

      const barW = Math.max(2, (chartWidth / n) * 0.7);
      ctx.fillStyle = isPos ? 'rgba(22, 163, 74, 0.65)' : 'rgba(220, 38, 38, 0.65)';
      ctx.fillRect(x - barW / 2, Math.min(y, zeroY), barW, Math.abs(y - zeroY));
    }

    // 4. Smooth trend line (Invesco Navy-Blue)
    ctx.strokeStyle = INSTITUTIONAL_PALETTE.blue;
    ctx.lineWidth = 2;
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const x = padding.left + i * stepX;
      const y = valToY(this.data[i].ic);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // 5. Mean IC dashed benchmark line (Warm Amber)
    const meanY = valToY(this.overallIC);
    ctx.strokeStyle = INSTITUTIONAL_PALETTE.orange;
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(padding.left, meanY);
    ctx.lineTo(width - padding.right, meanY);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = INSTITUTIONAL_PALETTE.orange;
    ctx.fillText(`均值: ${this.overallIC >= 0 ? '+' : ''}${this.overallIC.toFixed(3)}`, padding.left + 5, meanY - 4);

    // 6. Hover indicator
    if (this.hoverIdx >= 0 && this.hoverIdx < n) {
      const item = this.data[this.hoverIdx];
      const hx = padding.left + this.hoverIdx * stepX;
      const hy = valToY(item.ic);

      ctx.strokeStyle = INSTITUTIONAL_PALETTE.crosshair;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(hx, padding.top);
      ctx.lineTo(hx, height - padding.bottom);
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.fillStyle = item.ic >= 0 ? INSTITUTIONAL_PALETTE.green : INSTITUTIONAL_PALETTE.red;
      ctx.beginPath();
      ctx.arc(hx, hy, 4.5, 0, Math.PI * 2);
      ctx.fill();

      // Tooltip box (Institutional floating card)
      const text = `${item.date}: IC ${item.ic >= 0 ? '+' : ''}${item.ic.toFixed(3)}`;
      ctx.font = `11px ${INSTITUTIONAL_PALETTE.fontMono}`;
      const tw = ctx.measureText(text).width;
      const tx = Math.min(width - padding.right - tw - 10, Math.max(padding.left, hx - tw / 2));
      const ty = Math.max(padding.top + 14, hy - 10);

      ctx.fillStyle = '#0f172a';
      ctx.fillRect(tx - 6, ty - 12, tw + 12, 18);
      ctx.fillStyle = '#ffffff';
      ctx.fillText(text, tx, ty);
    }
  }
}
