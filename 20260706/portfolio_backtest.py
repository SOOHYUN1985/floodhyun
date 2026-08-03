"""
포트폴리오 백테스트 — 선정 전략들의 앙상블 자본 곡선 생성
- 각 매도 신호 시 Half-Kelly 비중만큼 청산
- 신호 없을 때 100% 매수 보유 (벤치마크)
- Drawdown, CAGR, Sharpe 산출
"""

import numpy as np
import pandas as pd
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


def simulate_portfolio(df: pd.DataFrame, strategies: List[Dict],
                        initial_capital: float = 100_000_000,
                        rebuy_after_days: int = 20) -> Dict:
    """
    선정 전략들로 포트폴리오 시뮬레이션.

    규칙:
    - 시작: 100% 매수 보유
    - 매도 신호 발생 시 Half-Kelly만큼 청산 → 현금
    - rebuy_after_days 일 후 재매수
    - 여러 전략이 동시 발동하면 비중 합산 (최대 100%)

    Returns:
        {'equity_curve': pd.Series, 'metrics': dict, 'trades': list}
    """
    if df is None or len(df) == 0 or not strategies:
        return {'equity_curve': None, 'metrics': {}, 'trades': []}

    # 신호 일자 매핑: {date: total_kelly_weight}
    signal_map = {}
    for s in strategies:
        half_k = s.get('half_kelly', 0)
        if half_k <= 0:
            continue
        for fr in s.get('forward_returns', []):
            d = fr['signal_date']
            signal_map[d] = signal_map.get(d, 0) + half_k

    # 클리핑
    for d in signal_map:
        signal_map[d] = min(1.0, signal_map[d])

    # 시뮬레이션
    close = df['close'].values
    dates = df.index
    n = len(close)

    cash = 0.0
    shares = initial_capital / close[0]
    cash_release_day = -1  # 현금화 만료 시점
    pending_cash = 0.0  # 매도 후 재매수 대기 현금

    equity_curve = []
    trades = []

    for i in range(n):
        # 재매수 시점 도래
        if cash_release_day >= 0 and i >= cash_release_day and pending_cash > 0:
            new_shares = pending_cash / close[i]
            shares += new_shares
            trades.append({
                'date': dates[i], 'action': 'REBUY', 'price': close[i],
                'cash_used': pending_cash, 'shares_added': new_shares,
            })
            pending_cash = 0.0
            cash_release_day = -1

        # 매도 신호 처리
        cur_date = dates[i]
        if cur_date in signal_map:
            sell_weight = signal_map[cur_date]
            sell_shares = shares * sell_weight
            sell_cash = sell_shares * close[i] * (1 - 0.00315)  # 거래비용
            shares -= sell_shares
            pending_cash += sell_cash
            cash_release_day = i + rebuy_after_days
            trades.append({
                'date': cur_date, 'action': 'SELL', 'price': close[i],
                'weight': sell_weight, 'shares_sold': sell_shares,
                'cash_received': sell_cash,
            })

        # 현재 자산 평가
        total = shares * close[i] + cash + pending_cash
        equity_curve.append(total)

    eq_series = pd.Series(equity_curve, index=dates)

    # 메트릭 산출
    bench = pd.Series(close / close[0] * initial_capital, index=dates)

    final_ret = (eq_series.iloc[-1] / initial_capital - 1) * 100
    bench_ret = (bench.iloc[-1] / initial_capital - 1) * 100

    # CAGR
    years = (dates[-1] - dates[0]).days / 365.25
    cagr = ((eq_series.iloc[-1] / initial_capital) ** (1/years) - 1) * 100 if years > 0 else 0
    bench_cagr = ((bench.iloc[-1] / initial_capital) ** (1/years) - 1) * 100 if years > 0 else 0

    # MDD
    peak = eq_series.cummax()
    drawdown = (eq_series - peak) / peak * 100
    mdd = drawdown.min()

    bench_peak = bench.cummax()
    bench_dd = (bench - bench_peak) / bench_peak * 100
    bench_mdd = bench_dd.min()

    # 일간 수익률 → Sharpe
    daily_ret = eq_series.pct_change().dropna()
    sharpe = (daily_ret.mean() / daily_ret.std() * np.sqrt(252)) if daily_ret.std() > 0 else 0
    bench_daily = bench.pct_change().dropna()
    bench_sharpe = (bench_daily.mean() / bench_daily.std() * np.sqrt(252)) if bench_daily.std() > 0 else 0

    metrics = {
        'initial_capital': initial_capital,
        'final_value': float(eq_series.iloc[-1]),
        'total_return_pct': float(final_ret),
        'cagr_pct': float(cagr),
        'mdd_pct': float(mdd),
        'sharpe': float(sharpe),
        'n_trades': len(trades),
        'years': float(years),
        # 벤치마크 (Buy & Hold)
        'bench_final': float(bench.iloc[-1]),
        'bench_total_return_pct': float(bench_ret),
        'bench_cagr_pct': float(bench_cagr),
        'bench_mdd_pct': float(bench_mdd),
        'bench_sharpe': float(bench_sharpe),
        # 알파
        'alpha_cagr': float(cagr - bench_cagr),
        'mdd_improvement': float(mdd - bench_mdd),  # 양수면 전략이 더 적은 손실
    }

    return {
        'equity_curve': eq_series,
        'benchmark': bench,
        'metrics': metrics,
        'trades': trades,
    }


def format_portfolio_report(result: Dict) -> str:
    """포트폴리오 결과를 마크다운으로"""
    if not result.get('metrics'):
        return ""
    m = result['metrics']
    text = "### 💼 포트폴리오 백테스트 (선정 전략 통합)\n\n"
    text += f"> Half-Kelly 비중으로 매도 신호 시 청산, 20거래일 후 재매수. 거래비용 0.315% 차감.\n\n"
    text += "| 지표 | 전략 포트폴리오 | Buy & Hold | 알파 |\n"
    text += "|------|---------------:|-----------:|------:|\n"
    text += f"| 총 수익률 | **{m['total_return_pct']:+.1f}%** | {m['bench_total_return_pct']:+.1f}% | {m['total_return_pct']-m['bench_total_return_pct']:+.1f}%p |\n"
    text += f"| CAGR | **{m['cagr_pct']:.2f}%** | {m['bench_cagr_pct']:.2f}% | {m['alpha_cagr']:+.2f}%p |\n"
    text += f"| 최대 낙폭 (MDD) | **{m['mdd_pct']:.1f}%** | {m['bench_mdd_pct']:.1f}% | {m['mdd_improvement']:+.1f}%p |\n"
    text += f"| Sharpe Ratio | **{m['sharpe']:.2f}** | {m['bench_sharpe']:.2f} | {m['sharpe']-m['bench_sharpe']:+.2f} |\n"
    text += f"| 거래 횟수 | {m['n_trades']}회 | — | — |\n"
    text += f"| 백테스트 기간 | {m['years']:.1f}년 | — | — |\n\n"

    if m['alpha_cagr'] > 0:
        text += f"> ✅ **알파 {m['alpha_cagr']:+.2f}%p** — 전략이 시장 대비 초과수익 달성\n\n"
    else:
        text += f"> ⚠️ **알파 {m['alpha_cagr']:+.2f}%p** — 단순 보유 대비 저조 (MDD는 {m['mdd_improvement']:+.1f}%p)\n\n"
    return text
