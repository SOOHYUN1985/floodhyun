"""
Walk-forward 포트폴리오 백테스트 (다중 전략 · 민감도 · 부트스트랩)

핵심 원칙(Walk-forward):
  각 리밸런싱 시점 t 에서 t 이전 데이터만으로 유사구간→Forward통계→비중을 산출하고,
  그 비중을 t 이후 구간 시장수익률에 적용한다. 미래 데이터는 절대 사용하지 않는다.
  → 즉 "그 시점에 실제로 알 수 있었던 정보만으로 매번 새로 판단"하는 반복 검증.

효율화: 비용이 큰 유사구간 검색은 (t, 시장)마다 1회만 수행하고,
  그 결과(유사 사례 위치)를 재사용하여 여러 전략/파라미터를 값싸게 파생한다.

수행 전략:
  · 투자성향 3종      : 공격형 / 균형형 / 안정형 (목적함수 차이)
  · 단순방향 baseline : 상승확률만으로 비중 (4요소 모델의 부가가치 확인용)
  · 벤치마크 5종      : 코스피/코스닥 B&H, 50:50, 현금, MA200 추세추종
추가 분석:
  · 파라미터 민감도   : 유사사례 수 K = 20/40/60 (성과 안정성 확인)
  · 거래비용 민감도   : 회전율×수수료 0/0.1/0.2/0.3% (실거래 순성과 확인)
  · 이격도 전략 그리드: 이동평균 4종(20/60/120/200) × 이격도 임계값 3종 (과열회피 노출)
  · 국면별 성과 분해  : 코스피 MA200 상회(추세)/하회(역추세) 구간 비교
  · 연도별 성과       : 균형형 vs 코스피
  · 부트스트랩 신뢰구간: 균형형 CAGR/MDD 의 5~95% 구간
"""

import numpy as np
import pandas as pd

import config as C
import analog
import allocation


# ─────────────────────────── 지표 ───────────────────────────
def _metrics(period_returns: np.ndarray, ppy: float) -> dict:
    r = np.asarray(period_returns, dtype=float)
    if len(r) == 0:
        return {}
    equity = np.cumprod(1 + r)
    total = equity[-1] - 1
    years = len(r) / ppy
    cagr = equity[-1] ** (1 / years) - 1 if years > 0 else 0.0
    vol = r.std(ddof=1) * np.sqrt(ppy) if len(r) > 1 else 0.0
    sharpe = (r.mean() * ppy) / vol if vol > 0 else 0.0
    downside = r[r < 0]
    dvol = downside.std(ddof=1) * np.sqrt(ppy) if len(downside) > 1 else 0.0
    sortino = (r.mean() * ppy) / dvol if dvol > 0 else 0.0
    peak = np.maximum.accumulate(equity)
    mdd = float(((equity - peak) / peak).min() * 100)
    calmar = (cagr * 100) / abs(mdd) if mdd < 0 else 0.0
    return {
        'total_return': round(total * 100, 1),
        'cagr': round(cagr * 100, 2),
        'vol': round(vol * 100, 2),
        'sharpe': round(sharpe, 2),
        'sortino': round(sortino, 2),
        'mdd': round(mdd, 1),
        'calmar': round(calmar, 2),
        'win_rate': round(float((r > 0).mean() * 100), 1),
        'equity': equity.tolist(),
    }


def _bootstrap(period_returns: np.ndarray, ppy: float, n_iter: int = 1000) -> dict:
    """블록 부트스트랩으로 CAGR/MDD 신뢰구간 추정 (경로 의존성 보존)."""
    r = np.asarray(period_returns, dtype=float)
    if len(r) < 20:
        return {}
    rng = np.random.default_rng(42)
    cagrs, mdds = [], []
    block, n = 10, len(r)
    years = n / ppy
    for _ in range(n_iter):
        idx = []
        while len(idx) < n:
            s = rng.integers(0, n)
            idx.extend(range(s, min(s + block, n)))
        rr = r[np.array(idx[:n])]
        eq = np.cumprod(1 + rr)
        cagrs.append(eq[-1] ** (1 / years) - 1)
        peak = np.maximum.accumulate(eq)
        mdds.append(((eq - peak) / peak).min())
    return {
        'cagr_p5': round(float(np.percentile(cagrs, 5)) * 100, 2),
        'cagr_p50': round(float(np.percentile(cagrs, 50)) * 100, 2),
        'cagr_p95': round(float(np.percentile(cagrs, 95)) * 100, 2),
        'mdd_p5': round(float(np.percentile(mdds, 5)) * 100, 1),
        'mdd_p50': round(float(np.percentile(mdds, 50)) * 100, 1),
        'mdd_p95': round(float(np.percentile(mdds, 95)) * 100, 1),
        'n_iter': n_iter,
    }


# ─────────────────────── 비중 파생(값싼 연산) ───────────────────────
def _weight(close: np.ndarray, positions: list[int], t: int,
            K: int, ra: float, tilt: float, cap: float, floor: float) -> float:
    pos = positions[:K]
    if not pos:
        return 0.5
    fwd = analog.forward_stats(close, pos, t, C.FORWARD_HORIZONS)
    exc = analog.excursion_stats(close, pos, t, C.ALLOC['primary_horizon'])
    return allocation.compute(fwd, exc, risk_aversion=ra, tilt=tilt,
                              cap=cap, floor=floor)['weight_pct'] / 100.0


def _weight_direction_only(close: np.ndarray, positions: list[int], t: int) -> float:
    """단순 baseline: 20일 상승확률을 그대로 비중으로."""
    if not positions:
        return 0.5
    fwd = analog.forward_stats(close, positions, t, [C.ALLOC['primary_horizon']])
    s = fwd.get(C.ALLOC['primary_horizon'], {})
    return (s.get('prob_up', 50.0) / 100.0) if s.get('n', 0) else 0.5


def _series(records, close_k, close_q, wfun, thr, return_weights=False):
    """records를 순회하며 전략 기간수익률 시계열 생성 (히스테리시스 포함).
    return_weights=True 면 (수익률, 각 기간의 (wk, wq) 가중치 경로)를 함께 돌려준다."""
    out = []
    wpath = []
    prev_k = prev_q = 0.5
    for rec in records:
        t = rec['t']
        wk = wfun(close_k, rec['pos_k'], t)
        wq = wfun(close_q, rec['pos_q'], t)
        if abs(wk - prev_k) < thr:
            wk = prev_k
        if abs(wq - prev_q) < thr:
            wq = prev_q
        prev_k, prev_q = wk, wq
        out.append(0.5 * wk * rec['rk'] + 0.5 * wq * rec['rq'])
        wpath.append((wk, wq))
    if return_weights:
        return np.array(out), wpath
    return np.array(out)


def _cost_sensitivity(returns: np.ndarray, wpath: list, ppy: float,
                      fees=(0.0, 0.001, 0.002, 0.003)) -> dict:
    """리밸런싱 회전율(turnover)에 수수료+슬리피지를 곱해 순성과를 재계산.
    turnover = 0.5·|Δwk| + 0.5·|Δwq| (두 시장 노출 변화의 합)."""
    turn = []
    pk = pq = 0.5
    for wk, wq in wpath:
        turn.append(0.5 * abs(wk - pk) + 0.5 * abs(wq - pq))
        pk, pq = wk, wq
    turn = np.array(turn)
    result = {}
    for fee in fees:
        m = _metrics(returns - turn * fee, ppy)
        result[fee] = {'cagr': m['cagr'], 'mdd': m['mdd'],
                       'sharpe': m['sharpe'], 'calmar': m['calmar']}
    return result


def _regime_split(returns: np.ndarray, records: list) -> dict:
    """코스피 MA200 상회(추세) / 하회(역추세) 구간으로 성과를 분해한다.
    비연속 구간이므로 회당 평균수익·승률·누적수익으로 요약한다."""
    mask = np.array([r['in_trend'] for r in records])
    out = {}
    for label, m in (('추세장(MA200 상회)', mask), ('역추세장(MA200 하회)', ~mask)):
        r = returns[m]
        if len(r) == 0:
            continue
        out[label] = {
            'n': int(len(r)),
            'avg': round(float(r.mean()) * 100, 2),
            'win_rate': round(float((r > 0).mean()) * 100, 1),
            'cum': round((float(np.prod(1 + r)) - 1) * 100, 1),
        }
    return out


def _disparity_grid(records: list, feat_k: pd.DataFrame, feat_q: pd.DataFrame,
                    ppy: float, periods=(20, 40, 60, 90, 120, 150, 200),
                    thresholds=(105, 110, 115, 120, 125, 130)) -> dict:
    """이격도(가격/이동평균×100) 기반 노출 전략 그리드.
    규칙: 상승추세(가격>MA_p)이면서 과열이 아닐 때(이격도 ≤ θ)만 100% 노출, 아니면 현금.
    여러 이동평균선(p) × 여러 이격도 임계값(θ) 조합을 비교한다(전부 시점 이전값만 사용).
    MA는 종가에서 즉석 계산하므로 20~200 범위 내 임의 기간을 자유롭게 넣을 수 있다."""
    ck = feat_k['close'].to_numpy(float)
    cq = feat_q['close'].to_numpy(float)
    ck_s, cq_s = feat_k['close'], feat_q['close']
    mak = {p: ck_s.rolling(p).mean().to_numpy(float) for p in periods}
    maq = {p: cq_s.rolling(p).mean().to_numpy(float) for p in periods}
    ts = np.array([r['t'] for r in records])
    rk = np.array([r['rk'] for r in records])
    rq = np.array([r['rq'] for r in records])
    out = {}
    for p in periods:
        mk_t, mq_t = mak[p][ts], maq[p][ts]
        ck_t, cq_t = ck[ts], cq[ts]
        dk = np.where(mk_t > 0, ck_t / mk_t * 100, np.inf)
        dq = np.where(mq_t > 0, cq_t / mq_t * 100, np.inf)
        for th in thresholds:
            ek = ((ck_t > mk_t) & (dk <= th)).astype(float)
            eq = ((cq_t > mq_t) & (dq <= th)).astype(float)
            m = _metrics(0.5 * ek * rk + 0.5 * eq * rq, ppy)
            out[f'MA{p}·이격≤{th}'] = {
                'cagr': m['cagr'], 'mdd': m['mdd'],
                'sharpe': m['sharpe'], 'calmar': m['calmar'],
                'invested': round(float(((ek + eq) / 2).mean()) * 100, 0),
            }
    return {'periods': list(periods), 'thresholds': list(thresholds), 'cells': out}


# ─────────────────────────── 메인 ───────────────────────────
def run(feat_kospi: pd.DataFrame, feat_kosdaq: pd.DataFrame) -> dict:
    """두 시장은 동일한 날짜 인덱스로 정렬되어 있다고 가정한다."""
    idx = feat_kospi.index
    close_k = feat_kospi['close'].to_numpy(float)
    close_q = feat_kosdaq['close'].to_numpy(float)
    ma200_k = feat_kospi['ma200'].to_numpy(float)

    step = C.BACKTEST['rebalance_days']
    ppy = C.BACKTEST['trading_days_per_year'] / step
    start_pos = max(int(idx.searchsorted(pd.Timestamp(C.BACKTEST['start']))), 260)
    grid = list(range(start_pos, len(idx) - 1, step))
    Kmax = C.ANALOG['k']

    # ── Phase 1: (t, 시장)마다 유사구간 검색 1회 (비용 큰 부분) ──
    records = []
    for gi in range(len(grid) - 1):
        t, t2 = grid[gi], grid[gi + 1]
        pk, _ = analog.find_analogs(feat_kospi, t, C.ANALOG_FEATURES,
                                    Kmax, C.ANALOG['min_gap_days'], C.ANALOG['asof_buffer_days'])
        pq, _ = analog.find_analogs(feat_kosdaq, t, C.ANALOG_FEATURES,
                                    Kmax, C.ANALOG['min_gap_days'], C.ANALOG['asof_buffer_days'])
        records.append({
            't': t, 'date': idx[t],
            'rk': close_k[t2] / close_k[t] - 1,
            'rq': close_q[t2] / close_q[t] - 1,
            'in_trend': bool(close_k[t] > ma200_k[t]),
            'pos_k': pk, 'pos_q': pq,
        })

    thr = C.ALLOC['change_threshold']
    P = allocation.PROFILES

    # ── Phase 2: 전략 파생 (값싼 연산, 동일 유사구간 재사용) ──
    def mk(K, prof):
        p = P[prof]
        return lambda close, pos, t: _weight(close, pos, t, K,
                                              p['risk_aversion'], p['tilt'], p['cap'], p['floor'])

    strat_returns = {
        '공격형': _series(records, close_k, close_q, mk(Kmax, '공격형'), thr),
        '균형형': _series(records, close_k, close_q, mk(Kmax, '균형형'), thr),
        '안정형': _series(records, close_k, close_q, mk(Kmax, '안정형'), thr),
        '단순방향(baseline)': _series(records, close_k, close_q, _weight_direction_only, thr),
    }
    # 균형형은 가중치 경로까지 확보해 거래비용·국면분해에 재사용
    bal_ret, bal_wpath = _series(records, close_k, close_q, mk(Kmax, '균형형'),
                                 thr, return_weights=True)
    strat_returns['균형형'] = bal_ret

    rk = np.array([r['rk'] for r in records])
    rq = np.array([r['rq'] for r in records])
    trend = np.array([r['rk'] if r['in_trend'] else 0.0 for r in records])
    bench_returns = {
        '코스피 B&H': rk,
        '코스닥 B&H': rq,
        '50:50 B&H': 0.5 * rk + 0.5 * rq,
        '현금 100%': np.zeros_like(rk),
        'MA200 추세추종': trend,
    }

    metrics = {name: _metrics(r, ppy) for name, r in {**strat_returns, **bench_returns}.items()}

    # ── 파라미터 민감도 (균형형, K=20/40/60) ──
    sensitivity = {}
    for K in (20, 40, 60):
        m = _metrics(_series(records, close_k, close_q, mk(K, '균형형'), thr), ppy)
        sensitivity[K] = {'cagr': m['cagr'], 'mdd': m['mdd'],
                          'sharpe': m['sharpe'], 'calmar': m['calmar']}

    # ── 연도별 성과 (균형형 vs 코스피) ──
    dates = pd.to_datetime([r['date'] for r in records])
    bal = strat_returns['균형형']
    df_ann = pd.DataFrame({'year': dates.year, 'bal': bal, 'kospi': rk})
    annual = {}
    for y, g in df_ann.groupby('year'):
        annual[int(y)] = {
            'bal': round((np.prod(1 + g['bal'].values) - 1) * 100, 1),
            'kospi': round((np.prod(1 + g['kospi'].values) - 1) * 100, 1),
        }

    boot = _bootstrap(bal, ppy)
    cost = _cost_sensitivity(bal_ret, bal_wpath, ppy)
    regime_perf = _regime_split(bal_ret, records)
    disparity = _disparity_grid(records, feat_kospi, feat_kosdaq, ppy)
    n_reb = len(records)
    return {
        'metrics': metrics,
        'dates': [r['date'].strftime('%Y-%m-%d') for r in records],
        'period': f"{idx[start_pos].date()} ~ {idx[-1].date()}",
        'rebalance_days': step,
        'n_rebalances': n_reb,
        'n_analog_searches': n_reb * 2,
        'n_strategy_sims': len(metrics) + len(sensitivity) + len(cost) + len(disparity['cells']),
        'sensitivity': sensitivity,
        'annual': annual,
        'bootstrap': boot,
        'cost': cost,
        'regime': regime_perf,
        'disparity': disparity,
        'main_strategy': '균형형',
    }
