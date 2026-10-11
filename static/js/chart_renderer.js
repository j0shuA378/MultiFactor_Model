/**
 * AlphaQuant Institutional Financial Canvas Chart Renderer
 * Inspired by Goldman Sachs & Invesco institutional web portals.
 * Features: High-DPI Retina support, Crisp Institutional White Theme,
 * High-legibility typography, Invesco Royal Navy (#0052cc) equity curves,
 * Clean forest-green/crimson candlesticks, and crisp reference axes.
 */

const INSTITUTIONAL_PALETTE = {
  blue: '#D97757',        // Anthropic Claude Terracotta
  green: '#237852',       // Claude Naturalist Sage Profit Green
  red: '#C53929',         // Claude Naturalist Crimson Loss Red
  orange: '#C97D30',      // Warm Ochre / Amber
  teal: '#2B7A78',        // Literary Teal
  purple: '#7E57C2',      // Refined Violet
  gray: '#787774',        // Warm Graphite Benchmark
  grayLight: '#DDD9CD',   // Warm Stone
  grid: '#F3F1EA',        // Soft Warm Reference Grid Lines
  gridBorder: '#E8E6DC',  // Warm Baseline
  axisText: '#787774',    // Clear Warm Graphite Text
  darkText: '#141413',    // Claude Carbon Ink
  crosshair: 'rgba(20, 20, 19, 0.35)', // Crosshair
  fontSans: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
  fontMono: '"JetBrains Mono", "SF Mono", Menlo, Consolas, monospace',
  fontSerif: "'Newsreader', Georgia, 'Times New Roman', serif"
};

function easeOutCubic(t) {
  return 1 - Math.pow(1 - t, 3);
}

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
    
    // TradingView Viewport State Machine
    this.visibleBars = 90;            // Number of bars visible in viewport (zoom)
    this.viewOffset = 0;              // Offset from newest bar (pan)
    this.priceScaleFactor = 1.0;       // Vertical price stretch/compress
    this.priceOffset = 0;             // Vertical price translation
    this.hoverIdx = -1;
    this.crosshairPos = null;         // { x, y }
    this.animProgress = 1.0;
    this.isAnimating = false;
    this.animFrameId = null;

    // Interaction & Drag State
    this.isDragging = false;
    this.dragMode = null;             // 'pan_chart' | 'scale_price' | 'drawing'
    this.dragStartX = 0;
    this.dragStartY = 0;
    this.dragStartOffset = 0;
    this.dragStartScale = 1.0;

    // TradingView Professional Drawing Tools
    this.activeTool = 'crosshair';     // 'crosshair' | 'trendline' | 'horizontal' | 'rect' | 'risk_reward' | 'eraser'
    this.drawings = [];               // Persisted user drawings in data coordinates
    this.currentDrawing = null;        // In-progress drawing
    this.magnetMode = true;           // Snap to high/low/close of nearest candle
    this.chartType = 'candles';        // 'candles' | 'hollow' | 'line' | 'area'
    this.showMa = true;
    this.showBb = true;

    this.setupListeners();
  }

  animate(duration = 750) {
    if (this.animFrameId) {
      cancelAnimationFrame(this.animFrameId);
      this.animFrameId = null;
    }
    const startTime = performance.now();
    this.isAnimating = true;

    const frame = (now) => {
      const elapsed = now - startTime;
      const t = Math.min(1, elapsed / duration);
      const progress = easeOutCubic(t);
      this.animProgress = progress;
      this.render(progress);

      if (t < 1) {
        this.animFrameId = requestAnimationFrame(frame);
      } else {
        this.isAnimating = false;
        this.animFrameId = null;
        this.animProgress = 1.0;
        this.render(1.0);
      }
    };

    this.animFrameId = requestAnimationFrame(frame);
  }

  setData(candles, signals = [], predictionLevels = null, animate = true) {
    this.data = candles || [];
    this.signals = signals || [];
    if (predictionLevels !== null && predictionLevels !== undefined) {
      this.predictionLevels = predictionLevels;
    }
    this.visibleBars = Math.min(this.data.length, Math.max(25, Math.min(120, this.data.length)));
    this.viewOffset = 0;
    this.priceScaleFactor = 1.0;
    this.priceOffset = 0;

    if (animate && this.data.length > 0) {
      this.animate(750);
    } else {
      this.animProgress = 1.0;
      this.render(1.0);
    }
  }

  setPredictionLevels(predictionLevels) {
    this.predictionLevels = predictionLevels;
    this.render(this.animProgress);
  }

  toggleProjectionLines() {
    this.showProjectionLines = !this.showProjectionLines;
    this.render(this.animProgress);
    return this.showProjectionLines;
  }

  setTool(tool) {
    if (tool === 'clear') {
      this.clearDrawings();
      this.activeTool = 'crosshair';
      return;
    }
    this.activeTool = tool;
    this.currentDrawing = null;
    if (this.canvas) {
      this.canvas.style.cursor = 'crosshair';
    }
    this.render();
  }

  clearDrawings() {
    this.drawings = [];
    this.currentDrawing = null;
    this.render();
  }

  setChartType(type) {
    this.chartType = type;
    this.render();
  }

  toggleMa() {
    this.showMa = !this.showMa;
    this.render();
    return this.showMa;
  }

  toggleBb() {
    this.showBb = !this.showBb;
    this.render();
    return this.showBb;
  }

  setupListeners() {
    if (!this.canvas) return;

    window.addEventListener('resize', () => {
      if (this.animFrameId) {
        cancelAnimationFrame(this.animFrameId);
        this.animFrameId = null;
        this.isAnimating = false;
      }
      this.animProgress = 1.0;
      this.render(1.0);
    });

    // 1. Mouse Wheel: Zoom in / Zoom out anchored on cursor position (TradingView style)
    this.canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      if (!this.data || this.data.length === 0) return;

      const rect = this.canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const chartWidth = this.canvas.clientWidth - this.padding.left - this.padding.right;
      if (mouseX < this.padding.left || mouseX > this.canvas.clientWidth - this.padding.right) return;

      const zoomFactor = e.deltaY < 0 ? 0.82 : 1.22;
      const oldVisible = this.visibleBars;
      const newVisible = Math.max(15, Math.min(this.data.length, Math.round(oldVisible * zoomFactor)));
      if (newVisible === oldVisible) return;

      const ratio = Math.max(0, Math.min(1, (mouseX - this.padding.left) / chartWidth));
      const delta = newVisible - oldVisible;
      const newOffset = Math.round(this.viewOffset - delta * (1 - ratio));
      const maxOffset = Math.max(0, this.data.length - newVisible);
      this.viewOffset = Math.max(-10, Math.min(maxOffset, newOffset));
      this.visibleBars = newVisible;

      if (this.isAnimating) {
        cancelAnimationFrame(this.animFrameId);
        this.animFrameId = null;
        this.isAnimating = false;
        this.animProgress = 1.0;
      }
      this.render();
    }, { passive: false });

    // 2. Mouse Down: Pan chart, drag price axis, or initiate drawing
    this.canvas.addEventListener('mousedown', (e) => {
      if (e.button !== 0) return;
      const rect = this.canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      if (mouseX >= this.canvas.clientWidth - this.padding.right) {
        this.isDragging = true;
        this.dragMode = 'scale_price';
        this.dragStartY = mouseY;
        this.dragStartScale = this.priceScaleFactor;
        return;
      }

      if (this.activeTool !== 'crosshair' && this.activeTool !== 'eraser') {
        this.handleDrawingMouseDown(mouseX, mouseY);
        return;
      }

      if (this.activeTool === 'eraser') {
        this.handleEraserClick(mouseX, mouseY);
        return;
      }

      this.isDragging = true;
      this.dragMode = 'pan_chart';
      this.dragStartX = mouseX;
      this.dragStartOffset = this.viewOffset;
      this.canvas.style.cursor = 'grabbing';
    });

    // 3. Mouse Move: Crosshair tracking, panning, price scaling, or drawing preview
    this.canvas.addEventListener('mousemove', (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      this.crosshairPos = { x: mouseX, y: mouseY };

      if (this.isDragging && this.dragMode === 'scale_price') {
        const deltaY = mouseY - this.dragStartY;
        const newScale = Math.max(0.2, Math.min(5.0, this.dragStartScale * (1 + deltaY * 0.005)));
        this.priceScaleFactor = newScale;
        this.render();
        return;
      }

      if (this.isDragging && this.dragMode === 'pan_chart') {
        const chartWidth = this.canvas.clientWidth - this.padding.left - this.padding.right;
        const barWidth = chartWidth / (this.visibleBars + (this.predictionLevels && this.showProjectionLines ? 8 : 2));
        const deltaBars = Math.round((mouseX - this.dragStartX) / (barWidth || 1));
        const maxOffset = Math.max(0, this.data.length - this.visibleBars);
        this.viewOffset = Math.max(-15, Math.min(maxOffset, this.dragStartOffset + deltaBars));
        this.render();
        return;
      }

      if (this.currentDrawing) {
        this.handleDrawingMouseMove(mouseX, mouseY);
        return;
      }

      this.updateCursorHover(mouseX, mouseY);
    });

    // 4. Mouse Up
    window.addEventListener('mouseup', () => {
      if (this.isDragging) {
        this.isDragging = false;
        this.dragMode = null;
        if (this.canvas) {
          this.canvas.style.cursor = 'crosshair';
        }
      }
    });

    // 5. Double Click: Auto-fit view
    this.canvas.addEventListener('dblclick', () => {
      this.viewOffset = 0;
      this.priceScaleFactor = 1.0;
      this.priceOffset = 0;
      this.visibleBars = Math.min(this.data.length, 90);
      this.render();
    });

    // 6. Mouse Leave
    this.canvas.addEventListener('mouseleave', () => {
      if (!this.isDragging) {
        this.crosshairPos = null;
        this.hoverIdx = -1;
        this.render();
        if (this.tooltipEl) {
          this.tooltipEl.textContent = "移动光标至图表区域查看日K线行情与信号标定";
        }
      }
    });
  }

  handleDrawingMouseDown(x, y) {
    const pt = this.canvasPointToData(x, y);
    if (!pt) return;

    if (this.activeTool === 'horizontal') {
      this.drawings.push({
        id: Date.now(),
        type: 'horizontal',
        price: pt.price,
        color: '#0052cc',
        date: pt.date
      });
      this.render();
      return;
    }

    if (this.activeTool === 'risk_reward') {
      const entryPrice = pt.price;
      const targetProfit = entryPrice * 1.055;
      const stopLoss = entryPrice * 0.975;
      this.drawings.push({
        id: Date.now(),
        type: 'risk_reward',
        entryPrice,
        targetProfit,
        stopLoss,
        date: pt.date
      });
      this.render();
      return;
    }

    if (!this.currentDrawing) {
      this.currentDrawing = {
        id: Date.now(),
        type: this.activeTool,
        p1: pt,
        p2: pt,
        color: this.activeTool === 'rect' ? '#6366f1' : '#d97757'
      };
      this.render();
    } else {
      this.currentDrawing.p2 = pt;
      this.drawings.push({ ...this.currentDrawing });
      this.currentDrawing = null;
      this.render();
    }
  }

  handleDrawingMouseMove(x, y) {
    if (!this.currentDrawing) return;
    const pt = this.canvasPointToData(x, y);
    if (pt) {
      this.currentDrawing.p2 = pt;
      this.render();
    }
  }

  handleEraserClick(x, y) {
    const pt = this.canvasPointToData(x, y);
    if (!pt || this.drawings.length === 0) return;

    let closestIdx = -1;
    let minDiff = Infinity;
    for (let i = 0; i < this.drawings.length; i++) {
      const d = this.drawings[i];
      let pPrice = d.price || d.entryPrice || (d.p1 ? d.p1.price : 0);
      const diff = Math.abs(pPrice - pt.price);
      if (diff < minDiff) {
        minDiff = diff;
        closestIdx = i;
      }
    }
    if (closestIdx >= 0) {
      this.drawings.splice(closestIdx, 1);
      this.render();
    }
  }

  canvasPointToData(x, y) {
    if (!this.data || this.data.length === 0) return null;
    const slice = this.getVisibleSlice();
    if (slice.candles.length === 0) return null;

    const chartWidth = this.canvas.clientWidth - this.padding.left - this.padding.right;
    const extraBars = (this.predictionLevels && this.showProjectionLines) ? 8 : 2;
    const barWidth = chartWidth / (slice.candles.length + extraBars);

    const relX = x - this.padding.left;
    const localIdx = Math.floor(relX / barWidth);
    const candleIdx = Math.max(0, Math.min(slice.candles.length - 1, localIdx));
    const candle = slice.candles[candleIdx];

    const mainHeight = this.canvas.clientHeight * 0.72;
    const { minPrice, maxPrice } = this.calculatePriceBounds(slice.candles);
    const priceRatio = (mainHeight - y) / (mainHeight - this.padding.top);
    const rawPrice = minPrice + priceRatio * (maxPrice - minPrice);

    let price = rawPrice;
    if (this.magnetMode && candle) {
      const snapCandidates = [candle.high, candle.low, candle.close, candle.open];
      let closest = snapCandidates[0];
      let minDelta = Math.abs(rawPrice - closest);
      for (const c of snapCandidates) {
        const d = Math.abs(rawPrice - c);
        if (d < minDelta) {
          minDelta = d;
          closest = c;
        }
      }
      if (minDelta / (maxPrice - minPrice) < 0.05) {
        price = closest;
      }
    }

    return {
      index: slice.startIndex + candleIdx,
      date: candle ? candle.date : '',
      price: Math.round(price * 100) / 100
    };
  }

  getVisibleSlice() {
    const total = this.data.length;
    if (total === 0) return { candles: [], startIndex: 0, endIndex: 0 };

    const visibleCount = Math.min(total, Math.max(15, this.visibleBars));
    const offset = Math.max(-15, Math.min(total - visibleCount, this.viewOffset));
    const endIndex = Math.min(total, total - offset);
    const startIndex = Math.max(0, endIndex - visibleCount);
    const candles = this.data.slice(startIndex, endIndex);

    return { candles, startIndex, endIndex };
  }

  calculatePriceBounds(visibleCandles) {
    let minPrice = Infinity;
    let maxPrice = -Infinity;
    let maxVol = 0;

    for (const c of visibleCandles) {
      if (c.low < minPrice) minPrice = c.low;
      if (c.high > maxPrice) maxPrice = c.high;
      if (c.bb_lower && c.bb_lower < minPrice) minPrice = c.bb_lower;
      if (c.bb_upper && c.bb_upper > maxPrice) maxPrice = c.bb_upper;
      if (c.volume > maxVol) maxVol = c.volume;
    }

    if (this.predictionLevels && this.showProjectionLines) {
      const pred = this.predictionLevels;
      const bP = Number(pred.expectedBuy ?? pred.expected_buy);
      const tP = Number(pred.targetProfit ?? pred.target_profit);
      const sP = Number(pred.stopLoss ?? pred.stop_loss);
      if (!isNaN(bP) && bP > 0) {
        minPrice = Math.min(minPrice, bP);
        maxPrice = Math.max(maxPrice, bP);
      }
      if (!isNaN(tP) && tP > 0) maxPrice = Math.max(maxPrice, tP);
      if (!isNaN(sP) && sP > 0) minPrice = Math.min(minPrice, sP);
    }

    if (!isFinite(minPrice) || !isFinite(maxPrice) || minPrice >= maxPrice) {
      minPrice = 100;
      maxPrice = 110;
    }

    const margin = (maxPrice - minPrice) * 0.08 || 1;
    minPrice -= margin;
    maxPrice += margin;

    const center = (minPrice + maxPrice) / 2 + this.priceOffset;
    const halfSpan = ((maxPrice - minPrice) / 2) * (1 / (this.priceScaleFactor || 1));
    minPrice = center - halfSpan;
    maxPrice = center + halfSpan;

    return { minPrice, maxPrice, maxVol };
  }

  updateCursorHover(mouseX, mouseY) {
    const slice = this.getVisibleSlice();
    const n = slice.candles.length;
    if (n === 0) return;

    const chartWidth = this.canvas.clientWidth - this.padding.left - this.padding.right;
    const extraBars = (this.predictionLevels && this.showProjectionLines) ? 8 : 2;
    const barWidth = chartWidth / (n + extraBars);

    const relX = mouseX - this.padding.left;
    const localIdx = Math.floor(relX / barWidth);

    if (localIdx >= 0 && localIdx < n) {
      this.hoverIdx = localIdx;
      this.updateTooltip(slice.candles[localIdx]);
      this.render();
    } else if (localIdx >= n && this.predictionLevels) {
      this.hoverIdx = -1;
      this.updatePredictionTooltip();
      this.render();
    } else {
      this.hoverIdx = -1;
      this.render();
    }
  }

  updateTooltip(candle) {
    if (!this.tooltipEl || !candle) return;
    const isUp = candle.close >= candle.open;
    const color = isUp ? INSTITUTIONAL_PALETTE.green : INSTITUTIONAL_PALETTE.red;
    const chg = (((candle.close - candle.open) / candle.open) * 100).toFixed(2);

    this.tooltipEl.innerHTML = `
      日期: <span style="color:${INSTITUTIONAL_PALETTE.darkText};font-weight:600;">${candle.date}</span> | 
      开: <span style="color:${INSTITUTIONAL_PALETTE.darkText}">$${candle.open.toFixed(2)}</span> | 
      高: <span style="color:${INSTITUTIONAL_PALETTE.darkText}">$${candle.high.toFixed(2)}</span> | 
      低: <span style="color:${INSTITUTIONAL_PALETTE.darkText}">$${candle.low.toFixed(2)}</span> | 
      收: <span style="color:${color};font-weight:700;">$${candle.close.toFixed(2)} (${chg > 0 ? '+' : ''}${chg}%)</span> | 
      量: <span style="color:${INSTITUTIONAL_PALETTE.axisText}">${(candle.volume / 1e6).toFixed(2)}M</span>
    `;
  }

  updatePredictionTooltip() {
    if (!this.tooltipEl || !this.predictionLevels) return;
    const buyP = Number(this.predictionLevels.expectedBuy ?? this.predictionLevels.expected_buy ?? 0).toFixed(2);
    const tpP = Number(this.predictionLevels.targetProfit ?? this.predictionLevels.target_profit ?? 0).toFixed(2);
    const slP = Number(this.predictionLevels.stopLoss ?? this.predictionLevels.stop_loss ?? 0).toFixed(2);
    this.tooltipEl.innerHTML = `
      <span style="color:#0052cc;font-weight:700;">前瞻预测:</span> 
      核心买点: <span style="color:#16a34a;font-weight:700;">$${buyP}</span> | 
      止盈目标: <span style="color:#0284c7;font-weight:700;">$${tpP} (${this.predictionLevels.target_gain_pct || ''})</span> | 
      止损防守: <span style="color:#dc2626;font-weight:700;">$${slP} (${this.predictionLevels.stop_loss_pct || ''})</span> | 
      盈亏比: <span style="color:#0f172a;font-weight:700;">${this.predictionLevels.risk_reward_ratio || '1:2.4'}</span>
    `;
  }

  render(progress = (this.animProgress !== undefined ? this.animProgress : 1.0)) {
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
      ctx.font = '13px ' + INSTITUTIONAL_PALETTE.fontSans;
      ctx.textAlign = 'center';
      ctx.fillText('暂无行情数据', width / 2, height / 2);
      return;
    }

    const slice = this.getVisibleSlice();
    const visibleCandles = slice.candles;
    const n = visibleCandles.length;
    if (n === 0) return;

    const padding = this.padding;
    const mainHeight = height * 0.72;
    const volHeight = height * 0.20;
    const volTop = height * 0.75;
    const chartWidth = width - padding.left - padding.right;

    const { minPrice, maxPrice, maxVol } = this.calculatePriceBounds(visibleCandles);
    const priceToY = (p) => padding.top + (maxPrice - p) / (maxPrice - minPrice) * (mainHeight - padding.top);
    const volToY = (v) => volTop + volHeight - (v / (maxVol || 1)) * volHeight;

    const extraBars = (this.predictionLevels && this.showProjectionLines) ? 8 : 2;
    const barWidth = chartWidth / (n + extraBars);
    const candleWidth = Math.max(1.8, barWidth * 0.72);

    // 1. Draw Grid Lines
    ctx.strokeStyle = INSTITUTIONAL_PALETTE.grid;
    ctx.lineWidth = 1;
    const gridSteps = 5;
    ctx.fillStyle = INSTITUTIONAL_PALETTE.axisText;
    ctx.font = '11px ' + INSTITUTIONAL_PALETTE.fontMono;
    ctx.textAlign = 'left';

    for (let i = 0; i <= gridSteps; i++) {
      const p = minPrice + (maxPrice - minPrice) * (i / gridSteps);
      const y = priceToY(p);
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(width - padding.right, y);
      ctx.stroke();

      ctx.fillText('$' + p.toFixed(2), width - padding.right + 6, y + 4);
    }

    // 2. Progressive Sweep Mask if animating
    const currentX = padding.left + chartWidth * Math.min(1.0, progress);
    ctx.save();
    ctx.beginPath();
    ctx.rect(padding.left, 0, chartWidth * Math.min(1.0, progress), height);
    ctx.clip();

    // 3. Bollinger Bands Cloud (if enabled)
    if (this.showBb) {
      ctx.fillStyle = 'rgba(99, 102, 241, 0.06)';
      ctx.beginPath();
      let hasBB = false;
      for (let i = 0; i < n; i++) {
        const c = visibleCandles[i];
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
        const c = visibleCandles[i];
        if (c.bb_upper && c.bb_lower) {
          const x = padding.left + i * barWidth + barWidth / 2;
          const yLow = priceToY(c.bb_lower);
          ctx.lineTo(x, yLow);
        }
      }
      ctx.closePath();
      ctx.fill();
    }

    // 4. Candlesticks / Volume Bars / Alternative Chart Types
    for (let i = 0; i < n; i++) {
      const c = visibleCandles[i];
      const x = padding.left + i * barWidth + barWidth / 2;
      const isUp = c.close >= c.open;
      const color = isUp ? INSTITUTIONAL_PALETTE.green : INSTITUTIONAL_PALETTE.red;

      ctx.fillStyle = isUp ? 'rgba(35, 120, 82, 0.22)' : 'rgba(197, 57, 41, 0.22)';
      const vy = volToY(c.volume);
      ctx.fillRect(x - candleWidth / 2, vy, candleWidth, volTop + volHeight - vy);

      if (this.chartType === 'candles') {
        ctx.strokeStyle = color;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(x, priceToY(c.high));
        ctx.lineTo(x, priceToY(c.low));
        ctx.stroke();

        const yOpen = priceToY(c.open);
        const yClose = priceToY(c.close);
        const bodyTop = Math.min(yOpen, yClose);
        const bodyHeight = Math.max(1.8, Math.abs(yClose - yOpen));
        ctx.fillStyle = color;
        ctx.fillRect(x - candleWidth / 2, bodyTop, candleWidth, bodyHeight);
      } else if (this.chartType === 'hollow') {
        ctx.strokeStyle = color;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(x, priceToY(c.high));
        ctx.lineTo(x, priceToY(c.low));
        ctx.stroke();

        const yOpen = priceToY(c.open);
        const yClose = priceToY(c.close);
        const bodyTop = Math.min(yOpen, yClose);
        const bodyHeight = Math.max(1.8, Math.abs(yClose - yOpen));
        if (isUp) {
          ctx.strokeRect(x - candleWidth / 2, bodyTop, candleWidth, bodyHeight);
        } else {
          ctx.fillStyle = color;
          ctx.fillRect(x - candleWidth / 2, bodyTop, candleWidth, bodyHeight);
        }
      }
    }

    if (this.chartType === 'line' || this.chartType === 'area') {
      ctx.beginPath();
      for (let i = 0; i < n; i++) {
        const x = padding.left + i * barWidth + barWidth / 2;
        const y = priceToY(visibleCandles[i].close);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.strokeStyle = '#0052cc';
      ctx.lineWidth = 2.2;
      ctx.stroke();

      if (this.chartType === 'area') {
        ctx.lineTo(padding.left + (n - 1) * barWidth + barWidth / 2, mainHeight);
        ctx.lineTo(padding.left + barWidth / 2, mainHeight);
        ctx.closePath();
        const areaGrad = ctx.createLinearGradient(0, padding.top, 0, mainHeight);
        areaGrad.addColorStop(0, 'rgba(0, 82, 204, 0.20)');
        areaGrad.addColorStop(1, 'rgba(0, 82, 204, 0.00)');
        ctx.fillStyle = areaGrad;
        ctx.fill();
      }
    }

    // 5. Moving Averages (SMA20 / SMA50)
    if (this.showMa) {
      this.drawLineSeries(ctx, visibleCandles.map((c, i) => ({
        x: padding.left + i * barWidth + barWidth / 2,
        y: c.sma_20 ? priceToY(c.sma_20) : null
      })), INSTITUTIONAL_PALETTE.orange, 1.8);

      this.drawLineSeries(ctx, visibleCandles.map((c, i) => ({
        x: padding.left + i * barWidth + barWidth / 2,
        y: c.sma_50 ? priceToY(c.sma_50) : null
      })), INSTITUTIONAL_PALETTE.teal, 1.8);
    }

    ctx.restore();

    // 6. Draw User Drawings (TradingView Trendlines, Horizontal Rays, Boxes, Risk/Reward Tool)
    this.drawUserDrawings(ctx, visibleCandles, slice.startIndex, priceToY, barWidth);

    // 7. Dynamic Laser Scanning Tracer
    if (progress < 1.0 && progress > 0.02) {
      const sweepX = currentX;
      ctx.strokeStyle = 'rgba(0, 82, 204, 0.85)';
      ctx.lineWidth = 1.8;
      ctx.beginPath();
      ctx.moveTo(sweepX, padding.top);
      ctx.lineTo(sweepX, height - padding.bottom);
      ctx.stroke();

      if (n > 0) {
        const curIdx = Math.min(n - 1, Math.max(0, Math.floor(n * progress)));
        const sparkY = priceToY(visibleCandles[curIdx].close);
        ctx.fillStyle = '#0052cc';
        ctx.beginPath();
        ctx.arc(sweepX, sparkY, 4, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // 8. Forward Trade Predictions & Overlay (Strictly in forward margin)
    if (this.predictionLevels && this.showProjectionLines && n > 0) {
      if (progress >= 0.70) {
        const predProgress = Math.min(1.0, (progress - 0.70) / 0.30);
        this.drawPredictionOverlay(ctx, width, height, padding, priceToY, minPrice, maxPrice, barWidth, n, predProgress, visibleCandles);
      }
    }

    // 9. TradingView Crosshair with Sticky Axis Tags
    if (!this.isAnimating && this.crosshairPos && this.crosshairPos.x >= padding.left && this.crosshairPos.x <= width - padding.right) {
      this.drawCrosshairWithAxisTags(ctx, width, height, padding, priceToY, minPrice, maxPrice, visibleCandles, barWidth);
    }
  }

  drawUserDrawings(ctx, visibleCandles, startIdx, priceToY, barWidth) {
    const padding = this.padding;
    const allDrawings = [...this.drawings];
    if (this.currentDrawing) allDrawings.push(this.currentDrawing);

    for (const d of allDrawings) {
      if (d.type === 'horizontal') {
        const y = priceToY(d.price);
        ctx.strokeStyle = d.color || '#0052cc';
        ctx.lineWidth = 1.5;
        ctx.setLineDash([5, 4]);
        ctx.beginPath();
        ctx.moveTo(padding.left, y);
        ctx.lineTo(this.canvas.clientWidth - padding.right, y);
        ctx.stroke();
        ctx.setLineDash([]);
        this.drawAxisBadge(ctx, this.canvas.clientWidth - padding.right + 2, y, '标线', '$' + d.price.toFixed(2), '#0052cc');
      } else if (d.type === 'trendline' && d.p1 && d.p2) {
        const i1 = d.p1.index - startIdx;
        const i2 = d.p2.index - startIdx;
        const x1 = padding.left + i1 * barWidth + barWidth / 2;
        const y1 = priceToY(d.p1.price);
        const x2 = padding.left + i2 * barWidth + barWidth / 2;
        const y2 = priceToY(d.p2.price);

        ctx.strokeStyle = d.color || '#d97757';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();

        ctx.fillStyle = d.color || '#d97757';
        ctx.beginPath();
        ctx.arc(x1, y1, 3.5, 0, Math.PI * 2);
        ctx.arc(x2, y2, 3.5, 0, Math.PI * 2);
        ctx.fill();
      } else if (d.type === 'rect' && d.p1 && d.p2) {
        const i1 = Math.min(d.p1.index, d.p2.index) - startIdx;
        const i2 = Math.max(d.p1.index, d.p2.index) - startIdx;
        const x1 = padding.left + i1 * barWidth;
        const x2 = padding.left + (i2 + 1) * barWidth;
        const yTop = Math.min(priceToY(d.p1.price), priceToY(d.p2.price));
        const yBottom = Math.max(priceToY(d.p1.price), priceToY(d.p2.price));

        ctx.fillStyle = 'rgba(99, 102, 241, 0.12)';
        ctx.fillRect(x1, yTop, x2 - x1, yBottom - yTop);
        ctx.strokeStyle = '#6366f1';
        ctx.lineWidth = 1.2;
        ctx.strokeRect(x1, yTop, x2 - x1, yBottom - yTop);
      } else if (d.type === 'risk_reward') {
        const i1 = (d.date ? visibleCandles.findIndex(c => c.date === d.date) : visibleCandles.length - 12);
        const startX = padding.left + Math.max(0, i1) * barWidth;
        const boxWidth = Math.max(100, barWidth * 16);
        const yEntry = priceToY(d.entryPrice);
        const yTp = priceToY(d.targetProfit);
        const ySl = priceToY(d.stopLoss);

        ctx.fillStyle = 'rgba(22, 163, 74, 0.18)';
        ctx.fillRect(startX, yTp, boxWidth, yEntry - yTp);
        ctx.strokeStyle = '#16a34a';
        ctx.lineWidth = 1.2;
        ctx.strokeRect(startX, yTp, boxWidth, yEntry - yTp);

        ctx.fillStyle = 'rgba(220, 38, 38, 0.18)';
        ctx.fillRect(startX, yEntry, boxWidth, ySl - yEntry);
        ctx.strokeStyle = '#dc2626';
        ctx.lineWidth = 1.2;
        ctx.strokeRect(startX, yEntry, boxWidth, ySl - yEntry);

        ctx.strokeStyle = '#0f172a';
        ctx.lineWidth = 1.8;
        ctx.beginPath();
        ctx.moveTo(startX, yEntry);
        ctx.lineTo(startX + boxWidth, yEntry);
        ctx.stroke();

        const rr = ((d.targetProfit - d.entryPrice) / Math.max(0.01, d.entryPrice - d.stopLoss)).toFixed(2);
        ctx.fillStyle = '#0f172a';
        ctx.font = 'bold 9.5px ' + INSTITUTIONAL_PALETTE.fontSans;
        ctx.fillText(`盈亏比: 1 : ${rr}`, startX + 6, yEntry - 4);
      }
    }
  }

  drawCrosshairWithAxisTags(ctx, width, height, padding, priceToY, minPrice, maxPrice, visibleCandles, barWidth) {
    const x = this.crosshairPos.x;
    const y = this.crosshairPos.y;

    ctx.strokeStyle = INSTITUTIONAL_PALETTE.crosshair;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(x, padding.top);
    ctx.lineTo(x, height - padding.bottom);
    ctx.moveTo(padding.left, y);
    ctx.lineTo(width - padding.right, y);
    ctx.stroke();
    ctx.setLineDash([]);

    const mainHeight = height * 0.72;
    if (y >= padding.top && y <= mainHeight) {
      const priceRatio = (mainHeight - y) / (mainHeight - padding.top);
      const cursorPrice = minPrice + priceRatio * (maxPrice - minPrice);
      this.drawAxisBadge(ctx, width - padding.right + 2, y, '现价', '$' + cursorPrice.toFixed(2), '#1e293b');
    }

    const relX = x - padding.left;
    const idx = Math.floor(relX / barWidth);
    if (idx >= 0 && idx < visibleCandles.length) {
      const dateText = visibleCandles[idx].date;
      const tagW = 74;
      const tagH = 18;
      const tagX = Math.max(padding.left, Math.min(width - padding.right - tagW, x - tagW / 2));
      const tagY = height - padding.bottom + 4;

      ctx.fillStyle = '#1e293b';
      ctx.beginPath();
      ctx.roundRect ? ctx.roundRect(tagX, tagY, tagW, tagH, 3) : ctx.rect(tagX, tagY, tagW, tagH);
      ctx.fill();

      ctx.fillStyle = '#ffffff';
      ctx.font = '600 9.5px ' + INSTITUTIONAL_PALETTE.fontMono;
      ctx.textAlign = 'center';
      ctx.fillText(dateText, tagX + tagW / 2, tagY + 12.5);
    }
  }

  drawPredictionOverlay(ctx, width, height, padding, priceToY, minPrice, maxPrice, barWidth, n, predProgress = 1.0, visibleCandles = this.data) {
    if (predProgress <= 0) return;
    ctx.save();
    ctx.globalAlpha = Math.min(1.0, Math.max(0, predProgress));
    const slideOffset = (1.0 - predProgress) * 20;

    const pred = this.predictionLevels;
    const cLast = visibleCandles[n - 1];
    const xLast = padding.left + (n - 1) * barWidth + barWidth / 2;
    const yLast = priceToY(cLast.close);
    const rightEdge = width - padding.right;
    const zoneLeft = xLast;

    const buyPrice = Number(pred.expectedBuy ?? pred.expected_buy);
    const tpPrice = Number(pred.targetProfit ?? pred.target_profit);
    const slPrice = Number(pred.stopLoss ?? pred.stop_loss);
    const buyMin = Number(pred.buy_range_min || buyPrice * 0.992);
    const buyMax = Number(pred.buy_range_max || buyPrice * 1.008);

    if (!isNaN(buyMin) && !isNaN(buyMax)) {
      const yMax = priceToY(buyMax);
      const yMin = priceToY(buyMin);
      ctx.fillStyle = 'rgba(22, 163, 74, 0.08)';
      ctx.fillRect(zoneLeft, Math.min(yMax, yMin), rightEdge - zoneLeft, Math.max(4, Math.abs(yMin - yMax)));

      ctx.strokeStyle = 'rgba(22, 163, 74, 0.35)';
      ctx.lineWidth = 1;
      ctx.setLineDash([2, 2]);
      ctx.strokeRect(zoneLeft, Math.min(yMax, yMin), rightEdge - zoneLeft, Math.max(4, Math.abs(yMin - yMax)));
      ctx.setLineDash([]);
    }

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

      this.drawAxisBadge(ctx, rightEdge + 3 + slideOffset, yBuy, '买点', '$' + buyPrice.toFixed(2), '#16a34a');
    }

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

      this.drawAxisBadge(ctx, rightEdge + 3 + slideOffset, yTp, '止盈', '$' + tpPrice.toFixed(2), '#0284c7');
    }

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

      this.drawAxisBadge(ctx, rightEdge + 3 + slideOffset, ySl, '止损', '$' + slPrice.toFixed(2), '#dc2626');
    }

    const futureX = Math.min(rightEdge - 6, xLast + barWidth * 5);
    const targetY = (pred.status === 'WAITING_BUY' && buyPrice < cLast.close)
      ? priceToY(buyPrice)
      : priceToY(tpPrice);

    ctx.fillStyle = 'rgba(22, 163, 74, 0.07)';
    ctx.beginPath();
    ctx.moveTo(xLast, yLast);
    ctx.lineTo(futureX, targetY - 12);
    ctx.lineTo(futureX, targetY + 12);
    ctx.closePath();
    ctx.fill();

    ctx.strokeStyle = '#16a34a';
    ctx.lineWidth = 1.6;
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(xLast, yLast);
    ctx.lineTo(futureX, targetY);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.fillStyle = '#16a34a';
    ctx.beginPath();
    ctx.arc(futureX, targetY, 3, 0, Math.PI * 2);
    ctx.fill();

    ctx.restore();
  }

  drawAxisBadge(ctx, x, y, label, priceStr, bgColor) {
    const w = 84;
    const h = 20;
    const radius = 3;
    const top = y - h / 2;

    ctx.save();
    ctx.fillStyle = bgColor;
    ctx.beginPath();
    ctx.moveTo(x + 5, top);
    ctx.lineTo(x + w - radius, top);
    ctx.quadraticCurveTo(x + w, top, x + w, top + radius);
    ctx.lineTo(x + w, top + h - radius);
    ctx.quadraticCurveTo(x + w, top + h, x + w - radius, top + h);
    ctx.lineTo(x + 5, top + h);
    ctx.lineTo(x, y);
    ctx.closePath();
    ctx.fill();

    ctx.strokeStyle = 'rgba(255, 255, 255, 0.28)';
    ctx.lineWidth = 0.8;
    ctx.stroke();

    ctx.fillStyle = '#ffffff';
    ctx.font = '600 9.5px ' + INSTITUTIONAL_PALETTE.fontSans;
    ctx.textAlign = 'left';
    ctx.fillText(label, x + 8, y + 3.5);

    ctx.font = '700 10px ' + INSTITUTIONAL_PALETTE.fontMono;
    ctx.textAlign = 'right';
    ctx.fillText(priceStr, x + w - 5, y + 3.5);
    ctx.restore();
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
    this.animProgress = 1.0;
    this.isAnimating = false;
    this.animFrameId = null;

    this.setupListeners();
  }

  animate(duration = 750) {
    if (this.animFrameId) {
      cancelAnimationFrame(this.animFrameId);
      this.animFrameId = null;
    }
    const startTime = performance.now();
    this.isAnimating = true;

    const frame = (now) => {
      const elapsed = now - startTime;
      const t = Math.min(1, elapsed / duration);
      const progress = easeOutCubic(t);
      this.animProgress = progress;
      this.render(progress);

      if (t < 1) {
        this.animFrameId = requestAnimationFrame(frame);
      } else {
        this.isAnimating = false;
        this.animFrameId = null;
        this.animProgress = 1.0;
        this.render(1.0);
      }
    };

    this.animFrameId = requestAnimationFrame(frame);
  }

  setData(records, animate = true) {
    this.records = records || [];
    if (animate && this.records.length > 0) {
      this.animate(750);
    } else {
      this.animProgress = 1.0;
      this.render(1.0);
    }
  }

  setupListeners() {
    if (!this.canvas) return;
    window.addEventListener('resize', () => {
      if (this.animFrameId) {
        cancelAnimationFrame(this.animFrameId);
        this.animFrameId = null;
        this.isAnimating = false;
      }
      this.animProgress = 1.0;
      this.render(1.0);
    });

    this.canvas.addEventListener('mousemove', (e) => {
      if (this.isAnimating) {
        if (this.animFrameId) {
          cancelAnimationFrame(this.animFrameId);
          this.animFrameId = null;
        }
        this.isAnimating = false;
        this.animProgress = 1.0;
      }
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
        this.render(1.0);
        this.updateTooltip(this.records[idx]);
      }
    });

    this.canvas.addEventListener('mouseleave', () => {
      this.hoverIdx = -1;
      this.render(1.0);
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

  render(progress = (this.animProgress !== undefined ? this.animProgress : 1.0)) {
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

    // --- Progressive Left-to-Right Clipping Mask ---
    const currentX = padding.left + chartWidth * Math.min(1.0, progress);

    ctx.save();
    ctx.beginPath();
    ctx.rect(padding.left, 0, chartWidth * Math.min(1.0, progress), height);
    ctx.clip();

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

    ctx.restore();

    // --- Dynamic Scanning Guide & Leading Tracer Pulse Dot ---
    if (progress < 1.0 && progress > 0.02 && n > 0) {
      const sweepX = currentX;
      const sweepIdx = Math.min(n - 1, Math.max(0, Math.floor((n - 1) * progress)));
      const curEquity = this.records[sweepIdx].equity;
      const dotY = valToY(curEquity);

      const beamW = Math.min(32, sweepX - padding.left);
      if (beamW > 0) {
        const beamGrad = ctx.createLinearGradient(sweepX - beamW, 0, sweepX, 0);
        beamGrad.addColorStop(0, 'rgba(0, 82, 204, 0.00)');
        beamGrad.addColorStop(1, 'rgba(0, 82, 204, 0.16)');
        ctx.fillStyle = beamGrad;
        ctx.fillRect(sweepX - beamW, padding.top, beamW, chartHeight);
      }

      ctx.strokeStyle = 'rgba(0, 82, 204, 0.7)';
      ctx.lineWidth = 1.5;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(sweepX, padding.top);
      ctx.lineTo(sweepX, height - padding.bottom);
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.fillStyle = 'rgba(0, 82, 204, 0.25)';
      ctx.beginPath();
      ctx.arc(sweepX, dotY, 9, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = INSTITUTIONAL_PALETTE.blue;
      ctx.beginPath();
      ctx.arc(sweepX, dotY, 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }

    // 4. Crosshair indicator
    if (!this.isAnimating && this.hoverIdx >= 0 && this.hoverIdx < n) {
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
    this.animProgress = 1.0;
    this.isAnimating = false;
    this.animFrameId = null;

    window.addEventListener('resize', () => {
      this.animProgress = 1.0;
      this.render(1.0);
    });
  }

  animate(duration = 800) {
    if (this.animFrameId) {
      cancelAnimationFrame(this.animFrameId);
      this.animFrameId = null;
    }
    const startTime = performance.now();
    this.isAnimating = true;

    const frame = (now) => {
      const elapsed = now - startTime;
      const t = Math.min(1, elapsed / duration);
      const progress = easeOutCubic(t);
      this.animProgress = progress;
      this.render(progress);

      if (t < 1) {
        this.animFrameId = requestAnimationFrame(frame);
      } else {
        this.isAnimating = false;
        this.animFrameId = null;
        this.animProgress = 1.0;
        this.render(1.0);
      }
    };

    this.animFrameId = requestAnimationFrame(frame);
  }

  setSeries(seriesList, animate = true) {
    this.seriesList = seriesList || [];
    if (animate && this.seriesList.length > 0) {
      this.animate(800);
    } else {
      this.animProgress = 1.0;
      this.render(1.0);
    }
  }

  render(progress = (this.animProgress !== undefined ? this.animProgress : 1.0)) {
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

    // --- Progressive Left-to-Right Clipping Mask ---
    ctx.save();
    ctx.beginPath();
    ctx.rect(padding.left, 0, chartWidth * Math.min(1.0, progress), height);
    ctx.clip();

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

    ctx.restore();

    if (progress < 1.0 && progress > 0.02) {
      const sweepX = padding.left + chartWidth * progress;
      ctx.strokeStyle = 'rgba(0, 82, 204, 0.6)';
      ctx.lineWidth = 1.5;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(sweepX, padding.top);
      ctx.lineTo(sweepX, height - padding.bottom);
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
    this.animProgress = 1.0;
    this.isAnimating = false;
    this.animFrameId = null;

    window.addEventListener('resize', () => {
      this.animProgress = 1.0;
      this.render(1.0);
    });
    this.setupListeners();
  }

  animate(duration = 700) {
    if (this.animFrameId) {
      cancelAnimationFrame(this.animFrameId);
      this.animFrameId = null;
    }
    const startTime = performance.now();
    this.isAnimating = true;

    const frame = (now) => {
      const elapsed = now - startTime;
      const t = Math.min(1, elapsed / duration);
      const progress = easeOutCubic(t);
      this.animProgress = progress;
      this.render(progress);

      if (t < 1) {
        this.animFrameId = requestAnimationFrame(frame);
      } else {
        this.isAnimating = false;
        this.animFrameId = null;
        this.animProgress = 1.0;
        this.render(1.0);
      }
    };

    this.animFrameId = requestAnimationFrame(frame);
  }

  setData(data, overallIC = 0.0, animate = true) {
    this.data = data || [];
    this.overallIC = overallIC;
    if (animate && this.data.length > 0) {
      this.animate(700);
    } else {
      this.animProgress = 1.0;
      this.render(1.0);
    }
  }

  setupListeners() {
    if (!this.canvas) return;
    this.canvas.addEventListener('mousemove', (e) => {
      if (this.isAnimating) {
        if (this.animFrameId) {
          cancelAnimationFrame(this.animFrameId);
          this.animFrameId = null;
        }
        this.isAnimating = false;
        this.animProgress = 1.0;
      }
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
        this.render(1.0);
      }
    });

    this.canvas.addEventListener('mouseleave', () => {
      this.hoverIdx = -1;
      this.render(1.0);
    });
  }

  render(progress = (this.animProgress !== undefined ? this.animProgress : 1.0)) {
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

    // 3. Positive / Negative Bars with growing height animation
    const barProgress = Math.min(1.0, progress * 1.25);
    for (let i = 0; i < n; i++) {
      const x = padding.left + i * stepX;
      const v = this.data[i].ic * barProgress;
      const y = valToY(v);
      const isPos = this.data[i].ic >= 0;

      const barW = Math.max(2, (chartWidth / n) * 0.7);
      ctx.fillStyle = isPos ? 'rgba(22, 163, 74, 0.65)' : 'rgba(220, 38, 38, 0.65)';
      ctx.fillRect(x - barW / 2, Math.min(y, zeroY), barW, Math.abs(y - zeroY));
    }

    // 4. Smooth trend line (clipped left to right)
    ctx.save();
    ctx.beginPath();
    ctx.rect(padding.left, 0, chartWidth * Math.min(1.0, progress), height);
    ctx.clip();

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

    ctx.restore();

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
    if (!this.isAnimating && this.hoverIdx >= 0 && this.hoverIdx < n) {
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
