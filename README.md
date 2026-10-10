# AlphaQuant Pro - 股票量化交易与多模型智能回测系统

**AlphaQuant Pro** 是一个专业级全栈量化股票交易与策略回测系统。系统同时具备**现代化 Web 交互式可视化分析仪表盘**与**独立纯 Python 命令行量化分析框架**，内嵌三大核心量化交易模型。

---

## 🌟 系统核心特性与模型矩阵

### 1. 经典多因子动量与均值回归策略 (`MultiFactorMomentumStrategy`)
- **趋势因子**：双指数移动平均线金叉与死叉（Fast EMA vs Slow EMA）
- **动量确认**：MACD 柱线加速与零轴动量验证，避免震荡市频繁伪突破
- **振荡因子**：Wilder 经典 RSI(14) 超买（70）与超卖（35）动态回踩过滤
- **均值回归**：布林带（Bollinger Bands, 2.0σ）触底回弹与通道压缩突破

### 2. 机器学习智能预测交易模型 (`MLPredictorStrategy`)
- **时序特征工程**：
  - 多周期收益率滞后特征：1日、3日、5日、10日、20日收益
  - 均线偏离度（Distance to SMA 10/20/50）
  - 振荡指标：RSI(14)、归一化 MACD DIF 与 Histogram
  - 波动率与量价特征：布林带 %B、归一化 ATR(14)、高低价差比（Spread）、20日成交量放大比
- **算法引擎**：支持 **Random Forest（随机森林）** 与 **Gradient Boosting（梯度提升树）** 分类器
- **严谨时序划分**：严格按照时间序列前向划分训练集（如 70%）与测试集（30%），杜绝未来函数与信息泄露
- **模型可解释性**：实时输出 **特征重要性排名（Feature Importance Top Rankings）**、测试集准确率、查准率（Precision）与查全率（Recall）

### 3. 海龟交易法则与动态网格策略 (`TurtleGridStrategy`)
- **突破交易系统**：突破前 20 日唐奇安通道（Donchian Channel）最高价入场
- **动态出场准则**：跌破前 10 日唐奇安通道最低价即刻平仓止盈
- **ATR (N) 波动率仓位管理**：真实波幅度量单份头寸风险（Dollar Volatility）
- **动态风控防线**：$2 \times \text{ATR}(N)$ 严格移动追踪止损保护

### 4. 三大策略横向对决矩阵 (`Model Comparison Matrix`)
- 支持在相同标的、相同时序跨度下，一键运行三大模型
- 同台多曲线叠加对比（Momentum vs ML AI vs Turtle vs Benchmark）
- 全维度量化指标横向对决（累计收益率、CAGR、夏普比率、索提诺比率、最大回撤、交易胜率、盈亏比、Alpha/Beta）

---

## 🚀 快速启动指南

### 方式一：启动 Web 交互式可视化终端（推荐）

1. 进入项目根目录：
   ```bash
   cd c:/Users/joshu/Desktop/anti_ide/trade_website
   ```

2. 启动量化后台服务：
   ```bash
   python server.py
   ```

3. 在任意浏览器打开：
   👉 **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

#### Web 端功能：
- **行情标的切换**：预设包含 `AAPL`、`NVDA`、`TSLA`、`MSFT`、`SPY`、`QQQ`、`AMZN`、`GOOGL`、`AMD`、`BABA` 等热门股票与指数，支持直接在搜索框输入任意美股/全球代码查询。
- **K线与交易标定图**：基于 Canvas 渲染的高清 K 线图，叠加 SMA 20、SMA 50、布林带通道，并在 K 线对应位置精确绘制 **▲ 买入** 与 **▼ 卖出** 信号指示。
- **资金净值曲线与动态回撤**：对比策略净值走势 vs 基准（买入持有）走势，实时展示水下回撤区域（Drawdown Area）。
- **参数动态调节**：支持在左侧面板微调资金、手续费率、滑点比例、均线周期、机器学习决策树数量与测试集占比等，点击 **运行回测** 即时重新推演。
- **成交明细导出**：支持一键导出 CSV 格式交易明细记录。

---

### 方式二：纯 Python 命令行独立运行（量化研究员常用）

可在终端直接使用 `backtest_cli.py` 进行独立量化回测与分析，支持终端彩色格式化输出和 JSON 报告导出：

1. **三大模型横向对决回测（默认模式）：**
   ```bash
   python backtest_cli.py --ticker NVDA --strategy all --period 2y
   ```

2. **单策略深度回测（多因子动量）：**
   ```bash
   python backtest_cli.py --ticker AAPL --strategy momentum --period 1y
   ```

3. **机器学习模型预测回测：**
   ```bash
   python backtest_cli.py --ticker TSLA --strategy ml --period 2y
   ```

4. **海龟突破法则回测：**
   ```bash
   python backtest_cli.py --ticker SPY --strategy turtle --period 3y
   ```

5. **导出完整回测报告为 JSON 文件：**
   ```bash
   python backtest_cli.py --ticker NVDA --strategy all --period 1y --export nvda_report.json
   ```

---

## 📁 项目目录结构

```
trade_website/
├── core/
│   ├── __init__.py
│   ├── data_loader.py          # 行情数据获取（Yahoo Finance + 缓存与合成兜底机制）
│   ├── indicators.py           # 纯向量化技术指标计算（SMA, EMA, MACD, RSI, BB, ATR, Donchian）
│   ├── backtest_engine.py      # 考虑手续费、滑点、仓位分配与风控的逼真撮合回测引擎
│   └── metrics.py              # 专业量化绩效评估（CAGR, Sharpe, Sortino, MDD, Win Rate, Alpha, Beta）
├── strategies/
│   ├── __init__.py
│   ├── base_strategy.py        # 策略抽象基类规范
│   ├── factor_momentum.py      # 策略一：经典多因子动量与均值回归策略
│   ├── ml_predictor.py         # 策略二：随机森林/梯度提升机器学习预测交易模型
│   └── turtle_grid.py          # 策略三：海龟通道突破法则与动态网格风控
├── static/                     # 现代化 Web 前端看板资源
│   ├── css/
│   │   └── style.css           # 深色金融终端设计系统与 Glassmorphism 样式
│   ├── js/
│   │   ├── chart_renderer.js   # 基于 Canvas 渲染的 60fps 动态 K 线图与收益率曲线
│   │   └── app.js              # 前端交互与回测数据控制器
│   └── index.html              # 响应式 Web 仪表盘主页
├── backtest_cli.py             # 纯 Python 命令行量化分析与回测脚本
├── server.py                   # Flask REST API 服务端
├── requirements.txt            # 项目依赖清单
└── README.md                   # 项目使用与架构说明文档
```

---

## 📊 绩效指标计算公式说明

| 指标名称 | 计算公式 / 逻辑 | 业务含义 |
| :--- | :--- | :--- |
| **累计收益率 (Total Return)** | $\frac{P_{\text{final}} - P_{\text{initial}}}{P_{\text{initial}}} \times 100\%$ | 回测区间内资产整体增值幅度 |
| **年化复合收益 (CAGR)** | $\left(\frac{P_{\text{final}}}{P_{\text{initial}}}\right)^{\frac{252}{N}} - 1$ | 标准化为年化视角的复利增长率 |
| **夏普比率 (Sharpe)** | $\frac{\text{CAGR} - R_f}{\sigma_{\text{ann}}}$ | 每承担一单位总波动所获取的超额回报 |
| **索提诺比率 (Sortino)** | $\frac{\text{CAGR} - R_f}{\sigma_{\text{downside}}}$ | 剔除上行波动，专注度量下行亏损风险的回报比 |
| **最大回撤 (Max Drawdown)** | $\max_{t} \left(\frac{\max_{\tau \le t} P_\tau - P_t}{\max_{\tau \le t} P_\tau}\right)$ | 历史峰值到低谷的最大资金跌幅 |
| **卡玛比率 (Calmar)** | $\frac{\text{CAGR}}{\|\text{Max Drawdown}\|}$ | 收益与极端风险的抗压比 |
| **Alpha & Beta** | $R_p - R_f = \alpha + \beta (R_m - R_f) + \epsilon$ | 衡量相对于市场基准的超额选股能力与系统性风险敞口 |
