"""
핵심 모듈 — 과거 유사구간(Analog) 검색 + Forward Return 통계

Look-ahead 방지 원칙:
  - as-of 시점 t 의 유사 사례는 t-buffer 이전 날짜에서만 찾는다.
  - 표준화(스케일링) 통계(median/IQR)는 t 이전 데이터(candidate pool)로만 계산한다.
  - Forward Return 은 유사 사례 날짜 d 로부터 d+h 가 t 이전(이미 실현된 과거)일 때만 통계에 포함한다.
    → 실시간(as-of=오늘) 예측에서도 합성된 미래값이 절대 사용되지 않는다.
  - 유사 사례는 min_gap 거래일 이상 떨어진 것만 선택(같은 이벤트 중복 방지).
"""

import numpy as np
import pandas as pd

import config as C
import regime as _regime


def _robust_stats(mat: np.ndarray):
    med = np.nanmedian(mat, axis=0)
    q1 = np.nanpercentile(mat, 25, axis=0)
    q3 = np.nanpercentile(mat, 75, axis=0)
    iqr = (q3 - q1) / 1.349
    iqr[(iqr == 0) | ~np.isfinite(iqr)] = 1.0
    return med, iqr


def find_analogs(feat: pd.DataFrame, asof_idx: int, feature_cols: list[str],
                 k: int, min_gap: int, buffer: int):
    """
    Returns: (analog_positions: list[int], distances: list[float])
    positions 는 feat 의 정수 위치(iloc 기준).
    """
    cols = [c for c in feature_cols if c in feat.columns]
    X = feat[cols].to_numpy(dtype=float)

    asof_vec = X[asof_idx]
    if np.isnan(asof_vec).any():
        return [], []

    # candidate pool: buffer 이전, 모든 feature 유효
    hi = asof_idx - buffer
    if hi < 60:
        return [], []
    pool_mask = np.zeros(len(X), dtype=bool)
    pool_mask[:hi] = True
    valid = ~np.isnan(X).any(axis=1)
    pool_mask &= valid
    pool_pos = np.where(pool_mask)[0]
    if len(pool_pos) < 100:
        return [], []

    # 표준화: pool 통계로만 fit (미래 미참조)
    med, iqr = _robust_stats(X[pool_pos])
    Z_pool = (X[pool_pos] - med) / iqr
    z_asof = (asof_vec - med) / iqr

    dist = np.sqrt(((Z_pool - z_asof) ** 2).sum(axis=1))
    order = np.argsort(dist)

    # 그리디 선택 + 최소 이격
    chosen, chosen_pos = [], []
    for oi in order:
        pos = int(pool_pos[oi])
        if all(abs(pos - c) >= min_gap for c in chosen_pos):
            chosen.append((pos, float(dist[oi])))
            chosen_pos.append(pos)
        if len(chosen) >= k:
            break
    positions = [p for p, _ in chosen]
    dists = [d for _, d in chosen]
    return positions, dists


def _fwd_return(close: np.ndarray, d: int, h: int):
    j = d + h
    if j >= len(close):
        return None
    return (close[j] / close[d] - 1.0) * 100.0


def forward_stats(close: np.ndarray, positions: list[int], asof_idx: int,
                  horizons: list[int]) -> dict:
    """
    각 horizon 별 Forward Return 분포 통계.
    d+h <= asof_idx 인 실현된 사례만 포함한다.
    """
    stats = {}
    for h in horizons:
        vals = []
        for d in positions:
            if d + h > asof_idx:      # 미래 미실현 → 제외
                continue
            r = _fwd_return(close, d, h)
            if r is not None and np.isfinite(r):
                vals.append(r)
        vals = np.array(vals, dtype=float)
        n = len(vals)
        if n == 0:
            stats[h] = {'n': 0}
            continue
        stats[h] = {
            'n': int(n),
            'mean': float(np.mean(vals)),
            'median': float(np.median(vals)),
            'std': float(np.std(vals, ddof=1)) if n > 1 else 0.0,
            'min': float(np.min(vals)),
            'max': float(np.max(vals)),
            'p10': float(np.percentile(vals, 10)),
            'p25': float(np.percentile(vals, 25)),
            'p75': float(np.percentile(vals, 75)),
            'p90': float(np.percentile(vals, 90)),
            'prob_up': float((vals > 0).mean() * 100),
            'prob_up5': float((vals >= 5).mean() * 100),
            'prob_dn5': float((vals <= -5).mean() * 100),
            'prob_dn10': float((vals <= -10).mean() * 100),
        }
    return stats


def excursion_stats(close: np.ndarray, positions: list[int], asof_idx: int,
                    horizon: int) -> dict:
    """MFE(최대 상승)/MAE(최대 하락) — 최종수익 뒤에 숨은 경로상 위험."""
    mfe, mae = [], []
    for d in positions:
        if d + horizon > asof_idx:
            continue
        seg = close[d:d + horizon + 1]
        if len(seg) < 2:
            continue
        path = (seg / seg[0] - 1.0) * 100.0
        mfe.append(float(np.max(path)))
        mae.append(float(np.min(path)))
    if not mfe:
        return {'n': 0}
    return {
        'n': len(mfe),
        'mfe_mean': float(np.mean(mfe)),
        'mae_mean': float(np.mean(mae)),
        'mae_p10': float(np.percentile(mae, 10)),   # 최악 근처
        'mae_worst': float(np.min(mae)),
    }


def future_path(close: np.ndarray, positions: list[int], asof_idx: int,
                horizon: int) -> dict:
    """유사 사례들의 D0~D+H 누적수익 경로 분위수."""
    paths = []
    for d in positions:
        if d + horizon > asof_idx:
            continue
        seg = close[d:d + horizon + 1]
        if len(seg) == horizon + 1:
            paths.append((seg / seg[0] - 1.0) * 100.0)
    if not paths:
        return {}
    arr = np.vstack(paths)
    return {
        'days': list(range(horizon + 1)),
        'median': np.median(arr, axis=0).tolist(),
        'p25': np.percentile(arr, 25, axis=0).tolist(),
        'p75': np.percentile(arr, 75, axis=0).tolist(),
        'p10': np.percentile(arr, 10, axis=0).tolist(),
        'p90': np.percentile(arr, 90, axis=0).tolist(),
        'n': len(paths),
        'paths': arr.tolist(),   # 개별 유사사례 경로(부록 시각화용)
    }


def discriminator(feat: pd.DataFrame, close: np.ndarray, positions: list[int],
                  asof_idx: int, horizon: int, feature_cols: list[str]) -> pd.DataFrame:
    """
    유사 사례를 이후 상승/하락으로 나누고, 그 둘을 가른 Feature 차이를 분석한다.
    (요구사항 26·55: '상승/하락을 가른 변수' 분석)
    """
    rows_up, rows_dn = [], []
    for d in positions:
        if d + horizon > asof_idx:
            continue
        r = _fwd_return(close, d, horizon)
        if r is None:
            continue
        (rows_up if r > 0 else rows_dn).append(d)

    cols = [c for c in feature_cols if c in feat.columns]
    if len(rows_up) < 3 or len(rows_dn) < 3:
        return pd.DataFrame()

    up = feat.iloc[rows_up][cols]
    dn = feat.iloc[rows_dn][cols]
    tbl = pd.DataFrame({
        '상승사례_평균': up.mean(),
        '하락사례_평균': dn.mean(),
    })
    pooled = feat.iloc[rows_up + rows_dn][cols].std().replace(0, np.nan)
    tbl['표준화차이'] = (tbl['상승사례_평균'] - tbl['하락사례_평균']) / pooled
    tbl['구분력'] = tbl['표준화차이'].abs()
    tbl = tbl.sort_values('구분력', ascending=False)
    tbl.attrs['n_up'] = len(rows_up)
    tbl.attrs['n_dn'] = len(rows_dn)
    return tbl


def analyze(feat: pd.DataFrame, asof_idx: int, full: bool = True) -> dict:
    """as-of 시점의 종합 유사구간 분석."""
    close = feat['close'].to_numpy(dtype=float)
    positions, dists = find_analogs(
        feat, asof_idx, C.ANALOG_FEATURES,
        C.ANALOG['k'], C.ANALOG['min_gap_days'], C.ANALOG['asof_buffer_days'],
    )
    result = {
        'asof_idx': asof_idx,
        'asof_date': feat.index[asof_idx],
        'n_analogs': len(positions),
        'positions': positions,
        'distances': dists,
        'forward': forward_stats(close, positions, asof_idx, C.FORWARD_HORIZONS),
    }
    if full and positions:
        h = C.ALLOC['primary_horizon']
        result['excursion'] = excursion_stats(close, positions, asof_idx, h)
        result['path60'] = future_path(close, positions, asof_idx, 60)
        result['discriminator'] = discriminator(
            feat, close, positions, asof_idx, h, C.ANALOG_FEATURES)
        result['analog_dates'] = [feat.index[p] for p in positions]
        # 각 유사 사례가 '어떤 날짜의 어떤 상황'이었고 이후 실제로 어떻게 됐는지
        detail = []
        for p, dist in zip(positions, dists):
            row = feat.iloc[p]

            def _g(col):
                v = row.get(col, float('nan'))
                return None if v is None or (isinstance(v, float) and np.isnan(v)) else float(v)

            fwd = {h: _fwd_return(close, p, h) if p + h <= asof_idx else None
                   for h in (5, 10, 20, 60, 120)}
            detail.append({
                'date': feat.index[p],
                'distance': dist,
                'regime': _regime.classify_row(row)['regime'],
                'ret20': fwd[20],
                'ret60': fwd[60],
                'forward': fwd,                    # 부록 상세용 다구간 실제결과
                'indicators': {                    # 그날의 시장 상태 스냅샷
                    'rsi14': _g('rsi14'),
                    'disp20': _g('disp20'),
                    'disp60': _g('disp60'),
                    'disp120': _g('disp120'),
                    'mdd120': _g('mdd120'),
                    'vol20': _g('vol20'),
                    'foreign_z20': _g('foreign_z20'),
                    'inst_z20': _g('inst_z20'),
                },
            })
        result['analog_detail'] = detail
    return result
