#!/usr/bin/env python3
"""
Quantitative Trading Model - Command Line Backtest Framework
Usage:
    python backtest_cli.py --ticker NVDA --strategy all --period 2y
    python backtest_cli.py --ticker AAPL --strategy momentum --period 1y
    python backtest_cli.py --ticker TSLA --strategy ml --period 2y
    python backtest_cli.py --ticker SPY --strategy turtle --period 3y
"""

import argparse
import sys
import os
import json
from datetime import datetime

# Add root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.data_loader import fetch_stock_data, get_preset_tickers
from core.backtest_engine import BacktestEngine
from strategies.factor_momentum import MultiFactorMomentumStrategy
from strategies.ml_predictor import MLPredictorStrategy
from strategies.turtle_grid import TurtleGridStrategy
from strategies.chan_strategy import ChanTheoryStrategy

def format_color(text: str, color_code: str) -> str:
    """Helper for terminal color formatting"""
    return f"\033[{color_code}m{text}\033[0m"

def print_banner():
    banner = """
================================================================================
          ALPHAQUANT 股票量化交易与多模型回测系统 (AlphaQuant Engine)          
================================================================================
"""
    print(format_color(banner, "1;36"))

def run_single_strategy(strat_class, df, capital, name, execution_mode="next_open"):
    strat = strat_class()
    signals, meta = strat.generate_signals(df)
    pos_sizes = meta.get("position_sizes") if isinstance(meta, dict) else None
    engine = BacktestEngine(initial_capital=capital, execution_mode=execution_mode)
    result = engine.run(df, signals, position_sizes=pos_sizes)
    result['strategy_name'] = name
    result['meta'] = meta
    return result

def print_metrics_table(metrics: dict, title: str):
    print(format_color(f"\n--- {title} 核心绩效指标 ---", "1;33"))
    print("-" * 65)
    row_fmt = "{:<28} {:<15} {:<18}"
    
    # Colorize returns
    ret_color = "1;32" if metrics.get('total_return_pct', 0) >= 0 else "1;31"
    bench_color = "1;32" if metrics.get('benchmark_return_pct', 0) >= 0 else "1;31"

    print(row_fmt.format("初始资金 / 最终权益", f"${metrics.get('initial_capital', 0):,.2f}", f"${metrics.get('final_equity', 0):,.2f}"))
    print(row_fmt.format("策略累计收益率", format_color(f"{metrics.get('total_return_pct', 0):+.2f}%", ret_color), f"年化 CAGR: {metrics.get('cagr_pct', 0):+.2f}%"))
    print(row_fmt.format("基准(买入持有)收益", format_color(f"{metrics.get('benchmark_return_pct', 0):+.2f}%", bench_color), f"基准年化: {metrics.get('benchmark_cagr_pct', 0):+.2f}%"))
    print(row_fmt.format("夏普比率 (Sharpe)", f"{metrics.get('sharpe_ratio', 0):.2f}", f"索提诺 (Sortino): {metrics.get('sortino_ratio', 0):.2f}"))
    print(row_fmt.format("最大回撤 (Max DD)", format_color(f"-{metrics.get('max_drawdown_pct', 0):.2f}%", "1;31"), f"卡玛比率: {metrics.get('calmar_ratio', 0):.2f}"))
    print(row_fmt.format("年化波动率", f"{metrics.get('annual_volatility_pct', 0):.2f}%", f"Alpha: {metrics.get('alpha_pct', 0):+.2f}%  Beta: {metrics.get('beta', 0):.2f}"))
    print(row_fmt.format("交易胜率 (Win Rate)", f"{metrics.get('win_rate_pct', 0):.2f}%", f"盈亏比: {metrics.get('profit_factor', 0):.2f}"))
    print(row_fmt.format("交易总笔数", f"{metrics.get('total_trades', 0)} 笔", f"盈利/亏损: {metrics.get('winning_trades', 0)} / {metrics.get('losing_trades', 0)}"))
    print(row_fmt.format("平均持仓周期", f"{metrics.get('avg_holding_days', 0):.1f} 天", f"平均单笔盈利: ${metrics.get('avg_win', 0):,.2f}"))
    print("-" * 65)

def print_comparison_matrix(results: list):
    print(format_color("\n===================== 多策略横向对决矩阵 (Multi-Strategy Matrix) =====================", "1;35"))
    headers = ["策略名称", "累计收益", "年化CAGR", "夏普比率", "最大回撤", "胜率", "总交易", "盈亏比"]
    header_str = f"{headers[0]:<18} {headers[1]:<12} {headers[2]:<12} {headers[3]:<10} {headers[4]:<12} {headers[5]:<10} {headers[6]:<8} {headers[7]:<8}"
    print(format_color(header_str, "1;37"))
    print("-" * 92)

    for r in results:
        m = r['metrics']
        ret_val = m['total_return_pct']
        ret_str = f"{ret_val:+.2f}%"
        ret_c = "1;32" if ret_val >= 0 else "1;31"
        colored_ret = format_color(ret_str, ret_c)
        
        mdd_str = f"-{m['max_drawdown_pct']:.2f}%"
        colored_mdd = format_color(mdd_str, "1;31")
        
        cagr_str = f"{m['cagr_pct']:+.2f}%"
        sharpe_str = f"{m['sharpe_ratio']:.2f}"
        win_str = f"{m['win_rate_pct']:.1f}%"
        trades_str = str(m['total_trades'])
        pf_str = f"{m['profit_factor']:.2f}"
        
        line = (
            f"{r['strategy_name']:<18} "
            f"{colored_ret:<21} "
            f"{cagr_str:<12} "
            f"{sharpe_str:<10} "
            f"{colored_mdd:<21} "
            f"{win_str:<10} "
            f"{trades_str:<8} "
            f"{pf_str:<8}"
        )
        print(line)
    print("-" * 92)

def print_recent_trades(trades: list, limit: int = 5):
    if not trades:
        print("\n无已完成交易记录。")
        return
    print(format_color(f"\n--- 最近 {min(limit, len(trades))} 笔交易明细 ---", "1;34"))
    t_header = f"{'编号':<6} {'入场日期':<12} {'出场日期':<12} {'入场价':<10} {'出场价':<10} {'盈亏($)':<12} {'盈亏(%)':<10} {'出场原因'}"
    print(t_header)
    print("-" * 80)
    for t in trades[-limit:]:
        pnl = t['pnl']
        pnl_pct = t['pnl_pct']
        pnl_c = "1;32" if pnl >= 0 else "1;31"
        pnl_str = format_color(f"${pnl:>+9.2f}", pnl_c)
        pct_str = format_color(f"{pnl_pct:>+6.2f}%", pnl_c)
        print(
            f"#{t['trade_id']:<5} "
            f"{t['entry_date']:<12} "
            f"{t['exit_date']:<12} "
            f"${t['entry_price']:<9.2f} "
            f"${t['exit_price']:<9.2f} "
            f"{pnl_str:<21} "
            f"{pct_str:<19} "
            f"{t['exit_reason']}"
        )
    print("-" * 80)

def main():
    parser = argparse.ArgumentParser(description="AlphaQuant 股票量化多模型回测系统")
    parser.add_argument("--ticker", type=str, default="NVDA", help="股票代码 (如 AAPL, NVDA, TSLA, SPY)")
    parser.add_argument("--strategy", type=str, choices=["momentum", "ml", "turtle", "chan", "all"], default="all", help="交易模型策略")
    parser.add_argument("--period", type=str, choices=["6mo", "1y", "2y", "3y", "5y"], default="2y", help="回测时间跨度")
    parser.add_argument("--execution-mode", type=str, choices=["next_open", "same_close"], default="next_open", help="撮合成交模式: next_open (次日开盘实盘时序, 杜绝未来函数) 或 same_close")
    parser.add_argument("--capital", type=float, default=100000.0, help="初始回测资金 (美元)")
    parser.add_argument("--export", type=str, default=None, help="导出回测结果 JSON 文件路径")

    args = parser.parse_args()

    print_banner()
    print(f"[*] 标的代码: {format_color(args.ticker.upper(), '1;32')} | 跨度: {args.period} | 成交模式: {args.execution_mode} | 初始资金: ${args.capital:,.2f}")
    print("[*] 正在拉取历史行情数据与计算技术指标...")

    df = fetch_stock_data(args.ticker, args.period)
    print(f"[+] 数据加载成功: 交易日天数 = {len(df)} | 区间: {df.index[0]} 至 {df.index[-1]}")

    results = []

    strategies_to_run = []
    if args.strategy in ["momentum", "all"]:
        strategies_to_run.append((MultiFactorMomentumStrategy, "多因子动量策略 (Momentum)"))
    if args.strategy in ["ml", "all"]:
        strategies_to_run.append((MLPredictorStrategy, "机器学习预测模型 (ML AI)"))
    if args.strategy in ["turtle", "all"]:
        strategies_to_run.append((TurtleGridStrategy, "海龟法则与网格 (Turtle/Grid)"))
    if args.strategy in ["chan", "all"]:
        strategies_to_run.append((ChanTheoryStrategy, "缠论形态中枢 (Chan Theory)"))

    for strat_cls, name in strategies_to_run:
        print(f"\n[*] 正在运行策略模型: {format_color(name, '1;36')} ...")
        res = run_single_strategy(strat_cls, df, args.capital, name, execution_mode=args.execution_mode)
        results.append(res)
        print_metrics_table(res['metrics'], name)

        # If ML model, print diagnostics
        if "ML" in name and "feature_importances" in res['meta']:
            print(format_color("\n  [ML 诊断] 特征重要性排名 (Top 5 Features):", "1;36"))
            for item in res['meta']['feature_importances'][:5]:
                print(f"    - {item['feature']:<16}: {item['importance']*100:.2f}%")
            print(f"  [ML 诊断] 测试集样本数: {res['meta']['test_samples']} | 验证集准确率: {res['meta']['accuracy']}%")

        print_recent_trades(res['trades'], limit=4)

    if len(results) > 1:
        print_comparison_matrix(results)

    if args.export:
        export_data = {
            "ticker": args.ticker,
            "period": args.period,
            "date_range": [df.index[0], df.index[-1]],
            "runs": [
                {
                    "strategy": r['strategy_name'],
                    "metrics": r['metrics'],
                    "trades_count": len(r['trades'])
                }
                for r in results
            ]
        }
        with open(args.export, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        print(format_color(f"\n[+] 回测报告已成功导出至: {args.export}", "1;32"))

if __name__ == "__main__":
    main()
