"""
리스크 메트릭 모듈
- Sharpe / Sortino / Calmar Ratio
- Monte Carlo 부트스트랩 신뢰구간
- Kelly Criterion 권고 비중
- 신호 빈도 평가
- 거래비용 차감
- ATR 동적 손절가
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 거래 비용
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def apply_trading_costs(returns: List[float], cost_pct: float = 0.315,
                         direction: str = 'short') -> List[float]:
    """
    Forward returns에 거래비용 차감.
    - short(매도): 음수=이익이므로 +cost 더하면 이익 작아짐
    - long(매수): 양수=이익이므로 -cost 빼면 이익 작아짐
    """
    if direction == 'long':
        return [r - cost_pct for r in returns]
    return [r + cost_pct for r in returns]


def calc_sharpe(returns: List[float], periods_per_year: float = 12.6,
                 direction: str = 'short') -> float:
    """Sharpe Ratio. direction에 따라 수익부호 해석"""
    if len(returns) < 2:
        return 0.0
    arr = np.array(returns) if direction == 'long' else -np.array(returns)
    mean = arr.mean()
    std = arr.std(ddof=1)
    if std == 0:
        return 0.0
    return float(mean / std * np.sqrt(periods_per_year))


def calc_sortino(returns: List[float], periods_per_year: float = 12.6,
                  direction: str = 'short') -> float:
    """Sortino Ratio: 하방 변동성만 사용"""
    if len(returns) < 2:
        return 0.0
    arr = np.array(returns) if direction == 'long' else -np.array(returns)
    mean = arr.mean()
    downside = arr[arr < 0]
    if len(downside) < 1:
        return float('inf') if mean > 0 else 0.0
    downside_std = np.sqrt(np.mean(downside ** 2))
    if downside_std == 0:
        return 0.0
    return float(mean / downside_std * np.sqrt(periods_per_year))


def calc_calmar(returns: List[float], periods_per_year: float = 12.6,
                 direction: str = 'short') -> float:
    """Calmar Ratio: 연환산 수익률 / 최대낙폭"""
    if len(returns) < 2:
        return 0.0
    arr = np.array(returns) if direction == 'long' else -np.array(returns)
    mean = arr.mean() * periods_per_year
    cumret = np.cumsum(arr)
    peak = np.maximum.accumulate(cumret)
    drawdown = cumret - peak
    max_dd = abs(drawdown.min())
    if max_dd < 0.1:
        return float('inf') if mean > 0 else 0.0
    return float(mean / max_dd)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Monte Carlo 부트스트랩
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def bootstrap_winrate_ci(returns: List[float], n_iter: int = 1000,
                          confidence: float = 0.95,
                          direction: str = 'short') -> Tuple[float, float, float]:
    """
    부트스트랩으로 승률의 신뢰구간 추정.
    short: 음수=승리, long: 양수=승리
    """
    if len(returns) < 3:
        arr = np.array(returns)
        wins = (np.sum(arr > 0) if direction == 'long' else np.sum(arr < 0))
        wr = (wins / len(arr)) * 100 if len(arr) else 0
        return wr, max(0, wr - 30), min(100, wr + 30)

    arr = np.array(returns)
    n = len(arr)
    rng = np.random.default_rng(42)

    win_rates = []
    for _ in range(n_iter):
        sample = rng.choice(arr, size=n, replace=True)
        wins = (np.sum(sample > 0) if direction == 'long' else np.sum(sample < 0))
        wr = (wins / n) * 100
        win_rates.append(wr)

    win_rates = np.array(win_rates)
    alpha = (1 - confidence) / 2
    lower = np.percentile(win_rates, alpha * 100)
    upper = np.percentile(win_rates, (1 - alpha) * 100)
    wins = (np.sum(arr > 0) if direction == 'long' else np.sum(arr < 0))
    point = (wins / n) * 100
    return float(point), float(lower), float(upper)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Kelly Criterion
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def kelly_fraction(returns: List[float], direction: str = 'short') -> float:
    """
    Kelly 권고 비중.
    f* = (p*W - q*L) / W
    """
    if len(returns) < 3:
        return 0.0
    arr = np.array(returns)
    if direction == 'long':
        wins = arr[arr > 0]
        losses = arr[arr <= 0]
        if len(wins) == 0 or len(losses) == 0:
            return 0.0
        p = len(wins) / len(arr)
        q = 1 - p
        avg_win = wins.mean()
        avg_loss = abs(losses.mean())
    else:
        wins = arr[arr < 0]
        losses = arr[arr >= 0]
        if len(wins) == 0 or len(losses) == 0:
            return 0.0
        p = len(wins) / len(arr)
        q = 1 - p
        avg_win = abs(wins.mean())
        avg_loss = losses.mean()
    if avg_win == 0:
        return 0.0
    kelly = (p * avg_win - q * avg_loss) / avg_win
    return float(max(0.0, min(1.0, kelly)))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 신호 빈도 평가
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def calc_signal_interval(forward_returns: List[Dict], total_days: int) -> Dict:
    """
    신호 간 평균 간격 계산.
    """
    if len(forward_returns) < 2:
        return {'avg_interval': total_days, 'frequency_score': 0, 'rating': '드묾'}

    dates = sorted([fr['signal_date'] for fr in forward_returns])
    intervals = [(dates[i+1] - dates[i]).days for i in range(len(dates) - 1)]
    avg_interval = float(np.mean(intervals))

    # 적정 범위: 30~250일 = 점수 100, 외곽일수록 감점
    if 30 <= avg_interval <= 250:
        score = 100
        rating = '적정'
    elif avg_interval < 30:
        score = max(0, 100 - (30 - avg_interval) * 3)
        rating = '잦음(노이즈 가능)'
    else:  # > 250
        score = max(0, 100 - (avg_interval - 250) * 0.3)
        if avg_interval > 750:
            rating = '매우 드묾'
        else:
            rating = '드묾'

    return {
        'avg_interval': avg_interval,
        'frequency_score': float(score),
        'rating': rating,
        'signals_per_year': 252 / avg_interval if avg_interval > 0 else 0,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ATR 동적 손절/익절
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def calc_atr(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """평균진폭(ATR) 계산"""
    high = df['high']
    low = df['low']
    close = df['close']
    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr


def atr_stop_levels(price: float, atr_value: float, stop_mult: float = 2.0,
                     target_mult: float = 3.0, direction: str = 'long') -> Dict:
    """
    ATR 기반 동적 손절/익절 레벨.

    Args:
        direction: 'long'(매수 후) 또는 'short'(매도 신호 = 가격 하락 기대)
    """
    if pd.isna(atr_value) or atr_value <= 0:
        return {'stop': None, 'target': None}

    if direction == 'long':
        stop = price - stop_mult * atr_value
        target = price + target_mult * atr_value
    else:  # short / 매도 신호 (가격 하락 기대)
        stop = price + stop_mult * atr_value  # 추가 상승 시 손절
        target = price - target_mult * atr_value  # 하락 시 익절

    return {
        'stop': float(stop),
        'target': float(target),
        'stop_pct': (stop - price) / price * 100,
        'target_pct': (target - price) / price * 100,
        'risk_reward': target_mult / stop_mult,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 수익률 분포 (분위수)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def return_distribution(returns: List[float]) -> Dict:
    """
    수익률 분포 통계 (5/25/50/75/95 분위수).

    매도 신호 기준: 음수=하락(원하던 방향), 양수=상승(반대)

    Returns:
        {'p5','p25','median','p75','p95','mean','std','best','worst'}
        값은 % 단위. best/worst는 매도 전략 관점:
          - best: 가장 큰 하락 (가장 음수)
          - worst: 가장 큰 상승 (가장 양수)
    """
    if not returns:
        return {}
    arr = np.array(returns)
    return {
        'p5': float(np.percentile(arr, 5)),
        'p25': float(np.percentile(arr, 25)),
        'median': float(np.percentile(arr, 50)),
        'p75': float(np.percentile(arr, 75)),
        'p95': float(np.percentile(arr, 95)),
        'mean': float(arr.mean()),
        'std': float(arr.std(ddof=1)) if len(arr) > 1 else 0.0,
        'best': float(arr.min()),    # 가장 큰 하락
        'worst': float(arr.max()),   # 가장 큰 상승 (매도 후 반대로 감)
        'n': len(arr),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 전략 메트릭 일괄 산출
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def enrich_strategy_metrics(strategy: Dict, total_days: int = 7000,
                              apply_costs: bool = True,
                              cost_pct: float = 0.315,
                              run_monte_carlo: bool = True,
                              n_mc_iter: int = 1000) -> Dict:
    """
    전략에 모든 리스크 지표 추가 (in-place).
    strategy['direction'] ('short'/'long')에 따라 자동 적용.
    """
    direction = strategy.get('direction', 'short')

    # 20일 후 수익률 추출
    returns_20d = []
    for fr in strategy.get('forward_returns', []):
        r = fr.get('return_20d')
        if r is not None:
            returns_20d.append(r)

    if not returns_20d:
        return strategy

    # 1) 거래비용 차감
    if apply_costs:
        returns_20d_net = apply_trading_costs(returns_20d, cost_pct, direction=direction)
        strategy['returns_20d_gross'] = returns_20d
        strategy['returns_20d_net'] = returns_20d_net
        if direction == 'long':
            wins_net = sum(1 for r in returns_20d_net if r > 0)
            gain_net = sum(r for r in returns_20d_net if r > 0)
            loss_net = sum(abs(r) for r in returns_20d_net if r <= 0)
        else:
            wins_net = sum(1 for r in returns_20d_net if r < 0)
            gain_net = sum(abs(r) for r in returns_20d_net if r < 0)
            loss_net = sum(r for r in returns_20d_net if r >= 0)
        strategy['win_rate_net'] = (wins_net / len(returns_20d_net)) * 100
        strategy['profit_factor_net'] = (gain_net / loss_net) if loss_net > 0 else float('inf')
        strategy['avg_return_net'] = float(np.mean(returns_20d_net))
        returns_for_calc = returns_20d_net
    else:
        returns_for_calc = returns_20d

    # 2) 리스크 조정 지표
    strategy['sharpe_ratio'] = calc_sharpe(returns_for_calc, direction=direction)
    strategy['sortino_ratio'] = calc_sortino(returns_for_calc, direction=direction)
    strategy['calmar_ratio'] = calc_calmar(returns_for_calc, direction=direction)

    # 3) Kelly Criterion
    strategy['kelly_fraction'] = kelly_fraction(returns_for_calc, direction=direction)
    strategy['half_kelly'] = strategy['kelly_fraction'] / 2

    # 4) 신호 빈도
    freq = calc_signal_interval(strategy.get('forward_returns', []), total_days)
    strategy['signal_interval'] = freq

    # 5) Monte Carlo 신뢰구간
    if run_monte_carlo:
        point, lo, hi = bootstrap_winrate_ci(returns_for_calc, n_iter=n_mc_iter, direction=direction)
        strategy['win_rate_ci'] = {'point': point, 'lower': lo, 'upper': hi}

    # 6) 수익률 분포 (분위수)
    strategy['return_distribution'] = return_distribution(returns_for_calc)
    multi_horizon = {}
    for days in [5, 10, 15, 20]:
        rs = [fr.get(f'return_{days}d') for fr in strategy.get('forward_returns', [])
              if fr.get(f'return_{days}d') is not None]
        if rs:
            multi_horizon[f'{days}d'] = return_distribution(rs)
    strategy['multi_horizon_distribution'] = multi_horizon

    return strategy
