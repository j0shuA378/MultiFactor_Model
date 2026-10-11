# AlphaQuant Pro - 机构级量化交易与多策略智能研报系统

<p align="center">
  <img src="https://img.shields.io/badge/Platform-Web%20%7C%20CLI-blue.svg" alt="Platform">
  <img src="https://img.shields.io/badge/Python-3.9%2B-green.svg" alt="Python">
  <img src="https://img.shields.io/badge/TradingView-Standard%20UI-orange.svg" alt="TradingView UI">
  <img src="https://img.shields.io/badge/License-MIT-purple.svg" alt="License">
  <img src="https://img.shields.io/badge/Unit%20Tests-35%2F35%20Passing-brightgreen.svg" alt="Tests">
</p>

**AlphaQuant Pro** 是一个面向专业投资机构与量化研究员的**全栈量化研报、策略推演与交易决策系统**。系统深度参考 **TradingView 桌面终端**的专业交互规范，完美融合**全市场选股池、深度基本面财务与机构预测、四大核心量化模型引擎、前瞻预期买点决策看板与实盘模拟环境**。

---

## 🌟 系统四大核心量化模型引擎

```
                                  AlphaQuant Pro 模型矩阵
                                             │
      ┌──────────────────┬───────────────────┴───────────────────┬──────────────────┐
      │                  │                                       │                  │
┌─────▼──────┐    ┌──────▼──────┐                         ┌──────▼──────┐    ┌──────▼──────┐
│ 多因子动量 │    │ 机器学习 AI │                         │  海龟突破   │    │ 缠论动力学  │
│ Barra/AQR  │    │ Random Forest                         │ Donchian    │    │ 中枢/形态   │
│ 截面残差   │    │ GradientBoost                         │ ATR 仓位风控│    │ 1/2/3类买卖 │
└────────────┘    └─────────────┘                         └─────────────┘    └─────────────┘
```

### 1. Barra / AQR 机构级多因子动量模型 (`MultiFactorMomentumStrategy`)
- **12M-1M 经典截面动量**：剔除最近 1 个月的短期反转噪声，捕捉中长期稳定趋势。
- **特质波动率风险调整**：采用特质波动率（Idiosyncratic Volatility）缩放，惩罚高投机性股票。
- **Beta 中性化残差动量**：通过时间序列回归剥离大盘基准收益，仅提取股票个体的纯 Alpha。
- **路径平滑度确认 ($R^2$)**：计算股价回归拟合优度，滤除脉冲式假突破。
- **动态目标波动率仓位管理 (Volatility Targeting)**：自适应调节杠杆与敞口，平滑资金净值波动。

### 2. 机器学习非线性时序预测模型 (`MLPredictorStrategy`)
- **多维度时序特征工程**：
  - 多周期滞后收益率：1日、3日、5日、10日、20日收益率。
  - 均线偏离度（Distance to SMA 10/20/50）。
  - 振荡指标：Wilder RSI(14)、归一化 MACD DIF 与柱线斜率。
  - 波动率与量价特征：布林带 %B、归一化 ATR(14)、高低价差比（Spread）、20日成交量放大比。
- **集成学习算法**：支持 **Random Forest（随机森林）** 与 **Gradient Boosting（梯度提升树）**。
- **严格时间序列前向验证**：杜绝未来函数（Look-ahead Bias）与信息泄露，真实模拟样本外推演。
- **模型可解释性诊断**：实时输出特征重要性（Feature Importance Rankings）、精确率与召回率。

### 3. 海龟交易法则与动态通道策略 (`TurtleGridStrategy`)
- **双通道突破交易系统**：突破前 20 日唐奇安通道（Donchian Channel）最高价入场，跌破前 10 日通道平仓。
- **真实波幅 ($N$) 仓位风险预算**：以每份头寸最大承受账户本金 1% 波动为基准，自适应分配买入股数。
- **金字塔分批加仓机制**：价格每上涨 $0.5N$ 自动追加一份头寸（最多 4 份）。
- **$2N$ 动态追踪止损**：动态锁住已有浮盈，严格控制单笔交易回撤。

### 4. 2026 缠论动力学数学结构引擎 (`ChanStrategy` & `ChanTheoryEngine`)
- **严格 K 线包含关系处理**：结合前后 K 线高低走向，严格区分向上包含与向下包含。
- **分型几何判定**：精确标定顶分型与底分型，结合有效 K 线间距形成合规「笔」（Bi）。
- **特征序列与线段划分**：对笔的延伸、转折及特征序列缺口进行数学验证，合成标准化「线段」（Segment）。
- **走势中枢几何推演**：提取至少三笔重叠区间，计算中枢上轨 $ZG$ 与下轨 $ZD$。
- **三类买卖点严格判定**：
  - **第一类买点**：中枢离开笔出现 MACD 柱线面积显著缩窄的趋势背驰买点。
  - **第二类买点**：突破中枢后的第一次回踩，低点不破第一买点。
  - **第三类买点**：中枢上方回踩次级别低点不进入中枢区间（$\text{Low} > ZG$），强趋势加速买点。
- **前瞻三层风控动态退出机制**：中枢震荡上轨保护、ATR 移动止损与背驰出场。

### 5. 四大策略全景横向对决 (`Model Comparison Matrix`)
- 支持在相同标的、相同时序跨度下，一键运行全部四大策略。
- 同台多曲线叠加对比（Momentum vs ML AI vs Turtle vs Chan Theory vs Benchmark）。
- 全维度横向对比矩阵（累计收益率、CAGR、夏普比率、索提诺比率、最大回撤、交易胜率、盈亏比、Alpha/Beta）。

---

## 🌐 独立专职页面架构 (Multi-Page Architecture)

为了彻底解决单页面过度拥挤、提升专业投研与量化实操体验，系统全面解耦为**独立的专职页面**，并通过顶部统一的**通用分段导航控制器 (Segmented Workspace Control)** 实现流畅串联：

| 专职页面 | 访问路由 (Local Flask / GitHub Pages) | 核心功能与亮点 |
| :--- | :--- | :--- |
| **1. 智能选股大厅** | `/screener` 或 `screener.html` | 宽屏全功能选股池，覆盖 33+ 核心资产（美股科技、黄金ETF、港股互联、A股白马、高股息），支持多维指标排序、关键词极速过滤、双重操盘跳转 |
| **2. 股票基本面透视** | `/details` 或 `details.html` | 专职深度基本面研报：52周价格位阶仪表盘、6大核心估值倍数、华尔街分析师目标价与评级分布直方图、分红派息周期表、公司深度业务护城河 |
| **3. 量化交易终端** | `/terminal` 或 `index.html` | 纯粹专业的 TradingView 级操盘工作台：60fps Canvas K线图、缠论笔/线段/中枢几何形态、前瞻三类买卖点、实时买点决策卡片与回测绩效走势 |
| **4. 四大策略全景对决** | `/compare` 或 `compare.html` | 多模型同台竞技场：多因子动量、机器学习、海龟突破、缠论中枢四大模型同源推演，多资金曲线重叠与横向 KPI 绩效评价矩阵 |
| **5. 实盘模拟交易** | `/paper` 或 `paper_trading.html` | 连续竞价模拟对盘系统、资产负债表与持仓盈亏看板 |
| **6. 参数与风控中心** | `/settings` 或 `settings.html` | 机构预设参数配置、波动率目标与风控止损阈值调节 |

---

## 🖥️ TradingView 级工作流与界面设计

本系统严格按照专业机构级操盘工作流重构，将选股、分析与操盘紧密串联：

```
选股池筛选 ──► 进入个股全景 ──► 策略模型切换 ──► K线与信号标定 ──► 前瞻决策指引
(Screener)    (Fundamentals)   (Strategy Picker)  (Canvas Chart)   (Signal & Action)
```

### 1. 顶部全局导航栏 (Top Bar)
- **代码快速搜索**：内置模糊匹配与热门标的自动联想（支持美股、港股、A股、ETF、黄金等）。
- **实时行情英雄条 (Ticker Hero Strip)**：实时现价、24h 涨跌幅、交易所标定。
- **周期快捷切换**：6M / 1Y / 2Y / 3Y / 5Y 时序区间一键切换。
- **紧凑型策略选择下拉菜单 (`tv-strat-dropdown`)**：
  - 原生 TradingView 风格下拉菜单，告别臃肿按钮折行问题。
  - 点击悬浮卡片直观预览四大模型特性与风控说明。
- **快捷工具入口**：运行模型回测、实盘模拟（Paper Trading）、独立参数中心（Settings）。

### 2. 左侧专业绘图工具栏 (Drawing Toolbar)
- 十字准星标尺（Crosshair）：精准跨轴吸附定位 K 线高低开收与成交量。
- 趋势线绘制（Trendline）：支持自定斜率趋势通道研判。
- 水平支撑阻力射线（Horizontal Ray）：关键价位水平标记。
- 中枢震荡箱体（Rectangle Box）：筹码密集区与缠论中枢可视化框选。
- 做多盈亏比量化测算（Long Risk/Reward）：直观显示止盈目标与防守止损区间。
- 清除绘制标记（Clear Drawings）。

### 3. 中间核心工作区 (Center Workspace)
- **原生 60fps Canvas 高性能 K 线图**：
  - 自适应缩放和平移（鼠标滚轮定点缩放、拖拽平移）。
  - 叠加 SMA 20、SMA 50、布林带轨道。
  - 精确绘制买入（▲）、卖出（▼）信号箭头。
  - 动态渲染**前瞻入场线（绿色虚线）**、**目标止盈线（黄色虚线）**、**防守止损线（红色虚线）**。
- **状态栏防重叠设计**：左侧自动截断图例，右侧独立光标实时报价追踪。

### 4. 底部量化抽屉面板 (Bottom Strategy Drawer)
- **策略净值走势 (Equity Curve)**：量化策略净值 vs 买入持有基准对比，直观渲染水下回撤区域。
- **量化绩效指标 (KPIs)**：累计收益、年化复合回报、夏普、索提诺、最大回撤、盈亏比等。
- **成交明细清单 (Trade Records)**：买卖流水、持仓天数、单笔盈亏，支持一键导出 CSV。
- **四大模型对决矩阵**：同台横向评分与收益率雷达对比。
- **ML 模型特征工程诊断**：时序特征权重分布与模型混淆矩阵。
- **抽屉自由缩放**：支持折叠（32px）、标准（260px）、展开（520px）。

### 5. 右侧全高多功能侧边栏 (Full-Height Right Dock)
- **选股池大厅 (Screener)**：
  - 33+ 核心资产分类切换（美股AI科技、ETF与黄金、港股互联、A股白马、高股息标的）。
  - 代码/板块实时关键词检索，支持市值、涨跌幅、机构看多空间、市盈率、股息率多维排序。
  - 5 列对齐紧凑表格，点击任意标的一键切换分析。
- **深度财务基本面 (Fundamentals - Yahoo Finance 真实数据同步)**：
  - 估值倍数：总市值、企业价值(EV)、静态PE、预期PE、市净率PB、Beta系数。
  - 52周区间仪表尺：当前价位处于 52 周最高/最低的相对位置百分比。
  - 机构预测目标价：华尔街机构目标均价、最高/最低预测价、看多上涨空间（Target Upside %）。
  - 股东回报与分红：股息率、年度每股派息、最新除息日。
  - 机构共识评级分布：买入 / 增持 / 持有 / 减持 / 卖出 柱状分布。
- **预期买点与操盘决策看板 (Signals & Prediction Engine)**：
  - 前瞻入场建议价、目标止盈价、防守止损价、盈亏比测算、建议动态仓位。
  - 智能操盘决策文本指引，助您洞察当前行情结构。
- **策略参数与风控微调 (Params & Friction Hub)**：
  - 初始资金、手续费率、滑点比例、动态目标波动率微调抽屉。

---

## 🚀 快速开始与使用指南

### 运行环境准备
- Python 3.9+ 
- 现代浏览器（Chrome、Edge、Safari、Firefox）

```bash
# 1. 克隆代码仓库
git clone https://github.com/j0shuA378/MultiFactor_Model.git
cd MultiFactor_Model

# 2. 安装 Python 依赖包
pip install -r requirements.txt
```

### 方式一：启动 Web 交互式交易终端（推荐）

```bash
# 启动量化后台 Flask REST API 服务
python server.py
```

在浏览器打开：👉 **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

#### 推荐实战体验流程：
1. **第一步（选股）**：在右侧选股池切换「美股AI科技」或「ETF与黄金」，使用排序器挑选「机构看多空间」最大的标的（如 NVDA 或 PLTR），点击「分析 →」。
2. **第二步（看基本面）**：右侧面板自动切入「基本面」，查看该标的 52 周价位区间、估值倍数以及机构目标均价。
3. **第三步（切策略）**：在顶部策略下拉菜单中选择「缠论形态」或「多因子动量」，点击「运行模型 (Run)」。
4. **第四步（看信号与前瞻买点）**：K 线图实时绘制买卖信号与前瞻入场/止盈/止损线，右侧「买点决策」提供仓位建议与操作指引，底部抽屉可实时审阅回测资金曲线与胜率。

---

### 方式二：纯 Python 命令行独立运行（量化研究员常用）

可在终端直接使用 `backtest_cli.py` 进行独立量化回测与分析，支持终端彩色格式化输出和 JSON 报告导出：

```bash
# 1. 四大策略全景对决回测（默认模式）：
python backtest_cli.py --ticker NVDA --strategy all --period 2y

# 2. 缠论动力学中枢与三类买卖点深度回测：
python backtest_cli.py --ticker AAPL --strategy chan --period 1y

# 3. 经典 Barra/AQR 多因子动量回测：
python backtest_cli.py --ticker TSLA --strategy momentum --period 2y

# 4. 机器学习预测回测：
python backtest_cli.py --ticker MSFT --strategy ml --period 1y

# 5. 海龟法则通道突破回测：
python backtest_cli.py --ticker SPY --strategy turtle --period 3y

# 6. 导出完整量化报告为 JSON 文件：
python backtest_cli.py --ticker NVDA --strategy all --period 1y --export nvda_report.json
```

---

## 🧪 自动化测试验证

系统自带完备的单元测试矩阵，全面覆盖核心量化指标、回测风控、缠论中枢计算与前瞻预测引擎：

```bash
python -m unittest discover -s tests -p "test_*.py"
```

运行输出：
```text
Ran 35 tests in 7.8s
OK (100% tests passing)
```

---

## 📁 项目目录结构

```text
trade_website/
├── core/                       # 核心量化算法库
│   ├── __init__.py
│   ├── data_loader.py          # Yahoo Finance 数据引擎（实时请求、本地缓存与容灾机制）
│   ├── indicators.py           # 向量化技术指标计算库（SMA, EMA, MACD, RSI, BB, ATR, Donchian）
│   ├── chan_theory.py          # 2026 缠论动力学数学结构引擎（K线包含、笔、线段、中枢、背驰）
│   ├── prediction_engine.py    # 前瞻性预期买点、止盈止损与仓位决策引擎
│   ├── backtest_engine.py      # 考虑手续费、滑点、仓位分配与熔断机制的高保真回测撮合引擎
│   ├── risk_manager.py         # 动态波动率目标管理与账户最大回撤熔断风控
│   └── metrics.py              # 专业量化绩效评估（CAGR, Sharpe, Sortino, MDD, Win Rate, Calmar）
├── strategies/                 # 量化交易策略集
│   ├── __init__.py
│   ├── base_strategy.py        # 策略抽象基类与接口规范
│   ├── factor_momentum.py      # 策略一：Barra / AQR 机构级多因子动量模型
│   ├── ml_predictor.py         # 策略二：时序机器学习分类预测交易模型
│   ├── turtle_grid.py          # 策略三：海龟唐奇安通道法则与动态风控策略
│   └── chan_strategy.py        # 策略四：缠论中枢形态量化交易策略
├── static/                     # 现代 Web 前端应用
│   ├── css/
│   │   └── style.css           # TradingView 标准样式系统、高阶组件与响应式布局
│   ├── js/
│   │   ├── chart_renderer.js   # 60fps Canvas K线图、资金曲线与交互式绘图引擎
│   │   ├── fundamentals_data.js# 预置高可信度全市场核心资产财务档案数据库
│   │   └── app.js              # 前端交互中枢、工作流控制器与 WebSocket/REST 连接器
│   ├── index.html              # TradingView 主终端页面
│   ├── paper_trading.html      # 实盘模拟交易控制面板
│   └── settings.html           # 独立参数中心与多因子微调配置面板
├── tests/                      # 自动化单元测试集
│   ├── test_indicators.py      # 指标精度测试
│   ├── test_strategies.py      # 四大模型回测逻辑测试
│   ├── test_chan_theory.py     # 缠论几何算法与买卖点判定测试
│   └── test_prediction_engine.py# 前瞻预测与风控决策测试
├── backtest_cli.py             # 纯 Python 命令行独立分析与报告生成工具
├── server.py                   # Flask REST API 后台服务
├── requirements.txt            # 项目依赖清单
└── README.md                   # 官方使用与架构说明文档
```

---

## 📊 专业量化绩效指标计算规范

| 指标名称 | 计算公式 / 核心逻辑 | 业务量化含义 |
| :--- | :--- | :--- |
| **累计收益率 (Total Return)** | $\frac{P_{\text{final}} - P_{\text{initial}}}{P_{\text{initial}}} \times 100\%$ | 回测区间内资产整体资本增值幅度 |
| **年化复合收益 (CAGR)** | $\left(\frac{P_{\text{final}}}{P_{\text{initial}}}\right)^{\frac{252}{N}} - 1$ | 消除时序跨度影响的标准年化复利收益 |
| **夏普比率 (Sharpe Ratio)** | $\frac{\text{CAGR} - R_f}{\sigma_{\text{ann}}}$ | 承担单位总波动率所获取的超额回报 |
| **索提诺比率 (Sortino Ratio)** | $\frac{\text{CAGR} - R_f}{\sigma_{\text{downside}}}$ | 剔除有益上行波动，专注度量下行亏损风险的回报比 |
| **最大回撤 (Max Drawdown)** | $\max_{t} \left(\frac{\max_{\tau \le t} P_\tau - P_t}{\max_{\tau \le t} P_\tau}\right)$ | 历史峰值到谷底的最大浮亏深度（衡量极端压力） |
| **卡玛比率 (Calmar Ratio)** | $\frac{\text{CAGR}}{\|\text{Max Drawdown}\|}$ | 年化收益与极端回撤的风险承受性价比 |
| **Alpha & Beta** | $R_p - R_f = \alpha + \beta (R_m - R_f) + \epsilon$ | 剥离系统性市场贝塔后的纯 Alpha 选股超额收益 |
| **交易胜率 (Win Rate)** | $\frac{N_{\text{profitable}}}{N_{\text{trades}}} \times 100\%$ | 盈利交易次数占总交易次数比例 |
| **盈亏比 (Profit / Loss Ratio)**| $\frac{\text{Avg Profit}}{\|\text{Avg Loss}\|}$ | 平均每笔盈利金额与平均每笔亏损金额的比值 |

---

## ⚖️ 免责声明 (Disclaimer)

本项目所有量化模型、指标计算、前瞻买点推演与历史回测仅供量化研究与学术交流使用，不构成任何实质性投资建议或操盘保证。金融市场具有不确定性与高风险性，历史表现不代表未来收益，请投资者独立决策并理性控制风险。
