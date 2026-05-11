"""
일일 종합 요약 리포트 생성기
- 코스피/코스닥 고점판독 결과를 A4 한 장 분량으로 압축
- 밸류에이션 차트 임베드
- 코스피만, 코스닥만, 혹은 둘 다 가능
"""

import os
from datetime import datetime
from typing import List, Dict, Optional
import pandas as pd
import numpy as np

from config import DAILY_BACKTEST_DIR as REPORTS_DIR
from config import CURRENT_FWD_EPS, CURRENT_FWD_BPS


# ── Forward EPS/BPS는 config.py에서 중앙 관리 ──
FWD_EPS = CURRENT_FWD_EPS
FWD_BPS = CURRENT_FWD_BPS


def _trend_emoji(trend_type: str) -> str:
    return {'bull': '📈', 'sideways': '↔️', 'bear': '📉'}.get(trend_type, '❓')


def _trend_name_short(trend_type: str) -> str:
    return {'bull': '상승장', 'sideways': '횡보장', 'bear': '하락장'}.get(trend_type, '?')


def _trend_color(trend_type: str) -> str:
    return {'bull': '🟢', 'sideways': '🔵', 'bear': '🔴'}.get(trend_type, '⚪')


def _heat_signal(score: float) -> str:
    if score >= 75:
        return '🔴 과열'
    elif score >= 60:
        return '🟡 주의'
    elif score >= 40:
        return '🟢 정상'
    else:
        return '🔵 저평가'


def _calc_overheat(df: pd.DataFrame) -> tuple:
    """과열 점수(0-100)와 과열 지표 목록 반환"""
    if df is None or df.empty:
        return 50, []

    cur = df.iloc[-1]
    scores = []
    hot_indicators = []

    for name, col, lo, hi, threshold in [
        ('RSI', 'RSI', 30, 100, 70),
        ('Stoch', 'Stoch_K', 0, 100, 80),
        ('MFI', 'MFI', 0, 100, 80),
        ('CCI', 'CCI', -200, 200, 100),
    ]:
        val = cur.get(col)
        if val is not None and not pd.isna(val):
            level = min(100, max(0, (val - lo) / (hi - lo) * 100))
            scores.append(level)
            if val >= threshold:
                hot_indicators.append(f'{name} {val:.0f}')

    # BB 위치
    bb_upper = cur.get('BB_upper')
    bb_lower = cur.get('BB_lower')
    close = cur.get('close', 0)
    if bb_upper and bb_lower and not pd.isna(bb_upper):
        bb_range = bb_upper - bb_lower
        if bb_range > 0:
            bb_pos = (close - bb_lower) / bb_range * 100
            bb_pos = min(100, max(0, bb_pos))
            scores.append(bb_pos)
            if bb_pos >= 80:
                hot_indicators.append(f'BB {bb_pos:.0f}%')

    overall = sum(scores) / len(scores) if scores else 50
    return overall, hot_indicators


def _calc_trigger_price(strategy: Dict, df: pd.DataFrame) -> Optional[float]:
    """전략의 발동 목표가 계산"""
    disparity = strategy.get('disparity')
    ma_period = strategy.get('ma_period')
    if disparity is None or ma_period is None or df is None:
        return None
    ma_col = f'MA{ma_period}'
    if ma_col in df.columns:
        ma_val = df[ma_col].iloc[-1]
    else:
        ma_val = df['close'].rolling(window=ma_period).mean().iloc[-1]
    if pd.isna(ma_val):
        return None
    return ma_val * (disparity / 100)


def _calc_data_driven_targets(df: pd.DataFrame, current_price: float) -> Optional[Dict]:
    """
    과거 유사 상황에서의 실제 상승폭 기반으로 단계별 매도 목표 산출.
    - 10일 내 P50 (단기 목표, 가까운 1차)
    - 20일 내 P50 (중기 목표, 2차)
    - 60일 내 P25 (장기 보수적, 3차)
    추가: 볼린저밴드 상단, ATR 기반 기술적 저항도 참고
    """
    if df is None or len(df) < 200:
        return None

    close = df['close']
    ma60 = close.rolling(60).mean()
    disparity_60 = (close / ma60) * 100
    rally_60d = close.pct_change(60) * 100

    cur_disparity = disparity_60.iloc[-1]
    cur_rally = rally_60d.iloc[-1]

    if pd.isna(cur_disparity) or pd.isna(cur_rally):
        return None

    close_arr = close.values
    n = len(close_arr)

    # 10일/20일/60일 내 최대 상승폭 계산
    future_10d = np.full(n, np.nan)
    future_20d = np.full(n, np.nan)
    future_60d = np.full(n, np.nan)
    for i in range(n - 60):
        future_10d[i] = (close_arr[i+1:i+11].max() / close_arr[i] - 1) * 100
        future_20d[i] = (close_arr[i+1:i+21].max() / close_arr[i] - 1) * 100
        future_60d[i] = (close_arr[i+1:i+61].max() / close_arr[i] - 1) * 100

    df_temp = pd.DataFrame({
        'disparity_60': disparity_60.values,
        'rally_60d': rally_60d.values,
        'future_10d': future_10d,
        'future_20d': future_20d,
        'future_60d': future_60d
    }, index=df.index)
    df_temp = df_temp.dropna()

    # 유사 상황 필터
    disp_lo = max(cur_disparity - 5, 105)
    disp_hi = cur_disparity + 5
    rally_lo = cur_rally - 10
    rally_hi = cur_rally + 10

    similar = df_temp[
        (df_temp['disparity_60'] >= disp_lo) &
        (df_temp['disparity_60'] <= disp_hi) &
        (df_temp['rally_60d'] >= rally_lo) &
        (df_temp['rally_60d'] <= rally_hi)
    ]

    if len(similar) < 30:
        disp_lo = max(cur_disparity - 10, 100)
        disp_hi = cur_disparity + 10
        rally_lo = cur_rally - 15
        rally_hi = cur_rally + 15
        similar = df_temp[
            (df_temp['disparity_60'] >= disp_lo) &
            (df_temp['disparity_60'] <= disp_hi) &
            (df_temp['rally_60d'] >= rally_lo) &
            (df_temp['rally_60d'] <= rally_hi)
        ]

    if len(similar) < 10:
        return None

    # 시간대별 중위 상승폭
    p50_10d = np.percentile(similar['future_10d'], 50)
    p50_20d = np.percentile(similar['future_20d'], 50)
    p50_60d = np.percentile(similar['future_60d'], 50)

    # 기술적 저항선: 볼린저밴드 상단 (2σ)
    bb_upper = None
    if 'BB_upper' in df.columns:
        bb_val = df['BB_upper'].iloc[-1]
        if not pd.isna(bb_val) and bb_val > current_price:
            bb_pct = (bb_val / current_price - 1) * 100
            bb_upper = {'price': bb_val, 'pct': bb_pct}

    # 단계 목록 (가까운 것부터 먼 것 순으로, 중복 제거)
    targets = []

    # 1차: 10일 내 중위 상승폭 또는 볼린저 상단 중 가까운 것
    if bb_upper and bb_upper['pct'] < p50_10d and bb_upper['pct'] > 0.5:
        targets.append({
            'pct': bb_upper['pct'],
            'price': bb_upper['price'],
            'label': f'BB상단 도달 (10일내 50%확률)',
            'prob': 50
        })
    elif p50_10d > 0.5:
        targets.append({
            'pct': p50_10d,
            'price': current_price * (1 + p50_10d / 100),
            'label': f'10일내 중위 상승폭 (확률 50%)',
            'prob': 50
        })

    # 2차: 20일 내 중위 상승폭 (1차보다 2%p 이상 높아야 의미 있음)
    if p50_20d > (targets[0]['pct'] + 2 if targets else 0):
        targets.append({
            'pct': p50_20d,
            'price': current_price * (1 + p50_20d / 100),
            'label': f'20일내 중위 상승폭 (확률 50%)',
            'prob': 50
        })

    # 3차: 60일 내 하위25% 상승폭 (보수적 장기, 2차보다 3%p 이상 높아야)
    p25_60d = np.percentile(similar['future_60d'], 25)
    last_pct = targets[-1]['pct'] if targets else 0
    if p25_60d > (last_pct + 3):
        targets.append({
            'pct': p25_60d,
            'price': current_price * (1 + p25_60d / 100),
            'label': f'60일내 보수적 상승폭 (확률 75%)',
            'prob': 75
        })

    # 4차: 60일 내 중위 상승폭 (낙관, 3차보다 5%p 이상 높아야)
    last_pct = targets[-1]['pct'] if targets else 0
    if p50_60d > (last_pct + 5):
        targets.append({
            'pct': p50_60d,
            'price': current_price * (1 + p50_60d / 100),
            'label': f'60일내 중위 상승폭 (확률 50%)',
            'prob': 50
        })

    if not targets:
        return None

    return {'targets': targets}


def _build_market_block(market_name: str, current_price: float,
                        trend_type: str, trend_confidence: int,
                        strategies: List[Dict], df: pd.DataFrame) -> str:
    """한 시장(코스피 or 코스닥)의 요약 블록 생성"""
    heat_score, hot_inds = _calc_overheat(df)

    breakout = [s for s in strategies if s['type'] == 'breakout']
    reversal = [s for s in strategies if s['type'] == 'reversal']

    # 가장 가까운 매도 목표 (현재가 이상)
    nearest = None
    next_above = None  # 현재가보다 위에 있는 가장 가까운 목표
    for s in breakout:
        tp = _calc_trigger_price(s, df)
        if tp is not None:
            pct = (tp - current_price) / current_price * 100
            if nearest is None or tp < nearest['price']:
                nearest = {'price': tp, 'pct': pct, 'name': s['name'],
                           'win_rate': s['win_rate']}
            if pct > 0:
                if next_above is None or tp < next_above['price']:
                    next_above = {'price': tp, 'pct': pct, 'name': s['name'],
                                  'win_rate': s['win_rate']}

    # 이미 발동된 전략
    triggered = []
    for s in breakout:
        tp = _calc_trigger_price(s, df)
        if tp is not None:
            pct = (tp - current_price) / current_price * 100
            if pct <= 0:
                # 틀렸을 때(매도 후 상승) 정보 추가
                fr = s.get('forward_returns', [])
                wrong_returns = [r['return_20d'] for r in fr if r.get('return_20d') is not None and r['return_20d'] > 0]
                avg_upside_when_wrong = np.mean(wrong_returns) if wrong_returns else 0
                max_upside_when_wrong = max(wrong_returns) if wrong_returns else 0
                triggered.append({'name': s['name'], 'price': tp, 'pct': pct,
                                  'win_rate': s['win_rate'],
                                  'max_adverse': s.get('max_adverse', 0),
                                  'avg_upside_wrong': avg_upside_when_wrong,
                                  'max_upside_wrong': max_upside_when_wrong})

    # 1차 방어선
    defense = current_price * 0.97

    lines = []
    tc = _trend_color(trend_type)
    te = _trend_emoji(trend_type)
    tn = _trend_name_short(trend_type)
    hs = _heat_signal(heat_score)

    lines.append(f'### {tc} {market_name} {current_price:,.2f}  —  {te} {tn} (신뢰도 {trend_confidence}%)')
    lines.append('')
    lines.append(f'| 과열 점수 | {heat_score:.0f}/100 {hs} |')
    lines.append('|:---:|:---|')

    # 과열 지표 경고
    if hot_inds:
        lines.append(f'| ⚠️ 과열 지표 | {", ".join(hot_inds)} |')

    lines.append('')

    # ── 즉시 행동 요약 (원라인) ──
    # 이미 초과된 전략 수 파악
    _all_targets = []
    for s in breakout:
        tp = _calc_trigger_price(s, df)
        if tp is not None:
            pct = (tp - current_price) / current_price * 100
            _all_targets.append(pct)
    _exceeded = sum(1 for p in _all_targets if p <= 0)
    _total = len(_all_targets)

    if _total > 0 and _exceeded == _total:
        lines.append(f'> 🚨 **매도 목표 전 {_exceeded}단계 초과 — 보유분 즉시 축소 권장**')
        lines.append('')
    elif _exceeded > 0:
        _next = min((p for p in _all_targets if p > 0), default=None)
        _next_price = current_price * (1 + _next / 100) if _next else 0
        lines.append(f'> ⚠️ **{_exceeded}/{_total}단계 초과 — 초과분 매도 실행, 다음 목표 {_next_price:,.0f}(+{_next:.1f}%) 대기**')
        lines.append('')
    elif _total > 0:
        _first = min(_all_targets)
        _first_price = current_price * (1 + _first / 100)
        lines.append(f'> ✅ **다음 매도 목표 {_first_price:,.0f}({_first:+.1f}%) 대기**')
        lines.append('')

    # 상승 시 액션
    lines.append('**📈 상승 시**')
    lines.append('')
    if triggered:
        lines.append('| 단계 | 매도가 | 등락률 | 전략 | 승률 | 틀렸을 때 |')
        lines.append('|:---:|---:|:---:|:---|:---:|:---|')
        for i, t in enumerate(triggered, 1):
            wrong_info = f'평균+{t["avg_upside_wrong"]:.1f}%' if t['avg_upside_wrong'] > 0 else '-'
            lines.append(f'| 🔴 {i}단계 | **{t["price"]:,.0f}** | {t["pct"]:+.1f}% | {t["name"]} | {t["win_rate"]:.0f}% | {wrong_info} |')
        # 다음 매도 목표 (현재가보다 위)
        next_stage = len(triggered) + 1
        if next_above:
            lines.append(f'| ▶ {next_stage}단계 | **{next_above["price"]:,.0f}** | {next_above["pct"]:+.1f}% | {next_above["name"]} | {next_above["win_rate"]:.0f}% | 잔여분 매도 |')
        else:
            # 과거 유사 상황에서의 실제 상승폭 기반 목표 산출
            _next_targets = _calc_data_driven_targets(df, current_price)
            if _next_targets and _next_targets['targets']:
                for j, tgt in enumerate(_next_targets['targets']):
                    lines.append(f'| ▶ {next_stage + j}단계 | **{tgt["price"]:,.0f}** | {tgt["pct"]:+.1f}% | {tgt["label"]} | - | 잔여분 익절 |')
            else:
                lines.append(f'| ▶ {next_stage}단계 | - | - | 전략 소진·데이터 부족 | - | 상세 리포트 참고 |')
        lines.append('')
        lines.append(f'> 💡 🔴 = 이미 초과 (즉시 축소). ▶ = 과거 유사 상황의 실제 상승폭 기반 목표.')
    elif nearest:
        lines.append(f'| 다음 매도 목표 | **{nearest["price"]:,.0f}** ({nearest["pct"]:+.1f}%) → {nearest["name"]} (승률 {nearest["win_rate"]:.0f}%) |')
        lines.append('|:---:|:---|')
    else:
        lines.append('> 상향돌파 목표가 미산출 — 상세 리포트 참고')
    lines.append('')

    # 하락 시 액션
    lines.append('**📉 하락 시**')
    lines.append('')
    if reversal:
        top_rev = reversal[0]
        lines.append(f'| 1차 방어선 | **{defense:,.0f}** (-3%) → 30% 손절 |')
        lines.append('|:---:|:---|')
        lines.append(f'| 핵심 하락감지 | {top_rev["name"]} (승률 {top_rev["win_rate"]:.0f}%) |')
        if len(reversal) >= 2:
            lines.append(f'| 강력 매도 | 하락반전 {len(reversal)}개 중 2개+ 동시 발동 시 → 50% 청산 |')
    else:
        lines.append(f'| 1차 방어선 | **{defense:,.0f}** (-3%) → 30% 손절 |')
        lines.append('|:---:|:---|')
    lines.append('')

    # 핵심 분할매도 단계 — 이미 초과된 것과 미래 목표를 분리
    sell_stages = []
    for s in breakout:
        tp = _calc_trigger_price(s, df)
        if tp is not None:
            pct = (tp - current_price) / current_price * 100
            fr = s.get('forward_returns', [])
            wrong_returns = [r['return_20d'] for r in fr if r.get('return_20d') is not None and r['return_20d'] > 0]
            avg_up = np.mean(wrong_returns) if wrong_returns else 0
            max_up = max(wrong_returns) if wrong_returns else 0
            sell_stages.append({'price': tp, 'pct': pct, 'name': s['name'],
                                'win_rate': s['win_rate'],
                                'avg_upside_wrong': avg_up,
                                'max_upside_wrong': max_up})
    sell_stages.sort(key=lambda x: x['price'])
    sell_stages = sell_stages[:5]

    future_stages = [st for st in sell_stages if st['pct'] > 0]

    if not sell_stages:
        pass  # 아무것도 안 함
    elif not future_stages:
        # 모든 목표가 초과 — 경고 표시
        lines.append('**📍 분할매도 단계**')
        lines.append('')
        lines.append(f'> 🚨 **전 {len(sell_stages)}단계 매도 목표 초과** — 보유분 즉시 축소 권장')
        lines.append('')
    else:
        lines.append('**📍 분할매도 단계**')
        lines.append('')
        lines.append('| 단계 | 목표가 | 등락률 | 전략 | 승률 | 틀렸을 때 |')
        lines.append('|:---:|---:|:---:|:---|:---:|:---|')
        for i, st in enumerate(future_stages, 1):
            status = '⚡' if st['pct'] < 2 else ('🎯' if st['pct'] < 5 else '⏳')
            wrong_info = f'평균+{st["avg_upside_wrong"]:.0f}%' if st['avg_upside_wrong'] > 0 else '-'
            lines.append(f'| {status} {i}단계 | **{st["price"]:,.0f}** | {st["pct"]:+.1f}% | {st["name"]} | {st["win_rate"]:.0f}% | {wrong_info} |')
        lines.append('')

    # 핵심 손절 단계 (상위 3개)
    if reversal:
        lines.append('**🛑 손절 단계**')
        lines.append('')
        lines.append('| 단계 | 손절가 | 비중 | 전략 | 승률 |')
        lines.append('|:---:|---:|:---:|:---|:---:|')
        stop_levels = [(-3, 30), (-5, 30), (-8, 40)]
        for i, ((pct, ratio), s) in enumerate(
                zip(stop_levels, reversal[:3]), 1):
            price = current_price * (1 + pct / 100)
            lines.append(f'| {i}단계 | **{price:,.0f}** ({pct}%) | {ratio}% | {s["name"]} | {s["win_rate"]:.0f}% |')
        lines.append('')

    return '\n'.join(lines)


def _build_pattern_analog_block(df: pd.DataFrame, market_name: str, current_price: float) -> str:
    """
    과거 유사 패턴 분석 블록
    현재 시점의 기술적 상태(20일 가격패턴 + 지표)와 가장 유사했던 과거 시점을 찾아
    그 이후 실제 등락을 보여준다.
    """
    if df is None or len(df) < 300:
        return ''

    close = df['close'].values
    n = len(close)

    # ── 특성 벡터 구성: 20일 수익률 패턴 + 기술적 지표 ──
    window = 20
    # 20일 수익률 시계열 (정규화)
    ret_20d = np.zeros((n, window))
    for i in range(window, n):
        segment = close[i - window:i + 1]
        pct_series = np.diff(segment) / segment[:-1] * 100
        ret_20d[i] = pct_series

    # 기술적 지표 수집
    rsi = df['RSI'].values if 'RSI' in df.columns else np.full(n, 50)
    stoch = df['Stoch_K'].values if 'Stoch_K' in df.columns else np.full(n, 50)
    atr_pct = df['ATR_pct'].values if 'ATR_pct' in df.columns else np.full(n, 1.5)

    # 60일 이격도
    ma60 = pd.Series(close).rolling(60).mean().values
    disparity_60 = np.where(ma60 > 0, close / ma60 * 100, 100)

    # 20일 수익률
    ret_20 = np.zeros(n)
    for i in range(20, n):
        ret_20[i] = (close[i] / close[i - 20] - 1) * 100

    # ── 현재 시점 특성 벡터 ──
    cur_idx = n - 1
    if cur_idx < window + 60:
        return ''

    cur_pattern = ret_20d[cur_idx]  # 20일 수익률 패턴
    cur_rsi = rsi[cur_idx]
    cur_stoch = stoch[cur_idx]
    cur_atr = atr_pct[cur_idx]
    cur_disp = disparity_60[cur_idx]
    cur_ret20 = ret_20[cur_idx]

    if np.isnan(cur_rsi) or np.isnan(cur_disp):
        return ''

    # ── 유사도 계산 (코사인 유사도 + 지표 거리) ──
    # 최소 60일 이후부터, 미래 40일 확보 가능한 시점까지만
    start_idx = max(window + 60, 120)
    end_idx = n - 40  # 미래 40일 필요

    if end_idx <= start_idx:
        return ''

    similarities = []
    cur_norm = np.linalg.norm(cur_pattern)
    if cur_norm == 0:
        return ''

    for i in range(start_idx, end_idx):
        pat = ret_20d[i]
        pat_norm = np.linalg.norm(pat)
        if pat_norm == 0:
            continue

        # 코사인 유사도 (패턴 모양)
        cos_sim = np.dot(cur_pattern, pat) / (cur_norm * pat_norm)

        # 지표 유사도 (거리 기반, 정규화)
        rsi_diff = abs(rsi[i] - cur_rsi) / 100
        stoch_diff = abs(stoch[i] - cur_stoch) / 100
        disp_diff = abs(disparity_60[i] - cur_disp) / 30
        ret_diff = abs(ret_20[i] - cur_ret20) / 30

        indicator_dist = (rsi_diff + stoch_diff + disp_diff + ret_diff) / 4
        indicator_sim = 1 - min(indicator_dist, 1.0)

        # 종합 유사도: 패턴 60% + 지표 40%
        total_sim = cos_sim * 0.6 + indicator_sim * 0.4
        similarities.append((i, total_sim))

    if not similarities:
        return ''

    # 상위 20개 유사 시점 선택 (최소 유사도 0.7 이상)
    similarities.sort(key=lambda x: x[1], reverse=True)
    top_analogs = [(idx, sim) for idx, sim in similarities[:30] if sim >= 0.65]

    if len(top_analogs) < 5:
        return ''

    top_analogs = top_analogs[:20]

    # ── 유사 시점 이후 경로 분석 (향후 40일) ──
    fwd_days = 40
    max_rallies = []  # 각 analog에서 향후 최대 상승폭
    max_drops = []    # 각 analog에서 향후 최대 하락폭
    rally_then_drop = []  # 최고점 도달 후 반락폭
    drop_then_rally = []  # 최저점 도달 후 반등폭
    paths = []        # 전체 경로 저장

    index_arr = df.index
    analog_dates = []

    for idx, sim in top_analogs:
        future_close = close[idx:idx + fwd_days + 1]
        if len(future_close) < fwd_days + 1:
            continue

        base_price = future_close[0]
        returns_path = (future_close[1:] / base_price - 1) * 100
        paths.append(returns_path)

        max_rally = returns_path.max()
        max_drop = returns_path.min()
        max_rallies.append(max_rally)
        max_drops.append(max_drop)

        # 최고점까지 며칠, 그 후 하락
        peak_day = np.argmax(returns_path)
        if peak_day < fwd_days - 5:
            after_peak = returns_path[peak_day:].min() - returns_path[peak_day]
            rally_then_drop.append(after_peak)

        # 최저점까지 며칠, 그 후 반등
        trough_day = np.argmin(returns_path)
        if trough_day < fwd_days - 5:
            after_trough = returns_path[trough_day:].max() - returns_path[trough_day]
            drop_then_rally.append(after_trough)

        analog_dates.append(index_arr[idx])

    if len(max_rallies) < 5:
        return ''

    # ── 통계 산출 ──
    avg_max_rally = np.mean(max_rallies)
    med_max_rally = np.median(max_rallies)
    avg_max_drop = np.mean(max_drops)
    med_max_drop = np.median(max_drops)
    best_case = max(max_rallies)
    worst_case = min(max_drops)

    avg_rally_then_drop = np.mean(rally_then_drop) if rally_then_drop else 0
    avg_drop_then_rally = np.mean(drop_then_rally) if drop_then_rally else 0

    # 경로 중위값 (대표 경로)
    paths_arr = np.array(paths)
    median_path = np.median(paths_arr, axis=0)
    p25_path = np.percentile(paths_arr, 25, axis=0)
    p75_path = np.percentile(paths_arr, 75, axis=0)

    # 10일/20일/40일 후 수익률 분포
    ret_10d = paths_arr[:, 9] if paths_arr.shape[1] >= 10 else paths_arr[:, -1]
    ret_20d_fwd = paths_arr[:, 19] if paths_arr.shape[1] >= 20 else paths_arr[:, -1]
    ret_40d_fwd = paths_arr[:, -1]

    # 상승 vs 하락 확률
    prob_up_10 = (ret_10d > 0).sum() / len(ret_10d) * 100
    prob_up_20 = (ret_20d_fwd > 0).sum() / len(ret_20d_fwd) * 100
    prob_up_40 = (ret_40d_fwd > 0).sum() / len(ret_40d_fwd) * 100

    # 평균 유사도
    avg_sim = np.mean([s for _, s in top_analogs])

    # ── 리포트 생성 ──
    lines = []
    lines.append(f'### 🔮 {market_name} 과거 유사 패턴 분석')
    lines.append('')
    lines.append(f'> 💡 현재와 가격 움직임 + 기술적 지표가 비슷했던 과거 **{len(paths)}개 시점** 발견 (평균 유사도 {avg_sim:.0%})')
    lines.append(f'> → 그 시점 이후 40일간 실제로 어떻게 움직였는지 통계')
    lines.append('')

    # 핵심 요약
    lines.append(f'**📊 유사 패턴 이후 40일간 등락 범위:**')
    lines.append('')
    lines.append(f'| 구분 | 평균 | 중위값 | 지수 환산 |')
    lines.append(f'|:---|:---:|:---:|---:|')
    lines.append(f'| 📈 최대 상승폭 | **{avg_max_rally:+.1f}%** | {med_max_rally:+.1f}% | {current_price * (1 + med_max_rally/100):,.0f} |')
    lines.append(f'| 📉 최대 하락폭 | **{avg_max_drop:+.1f}%** | {med_max_drop:+.1f}% | {current_price * (1 + med_max_drop/100):,.0f} |')
    lines.append(f'| 🚀 최고 사례 | {best_case:+.1f}% | - | {current_price * (1 + best_case/100):,.0f} |')
    lines.append(f'| 💥 최악 사례 | {worst_case:+.1f}% | - | {current_price * (1 + worst_case/100):,.0f} |')
    lines.append('')

    # 반전 패턴
    lines.append(f'**🔄 반전 패턴:**')
    lines.append('')
    lines.append(f'| 패턴 | 평균 크기 | 해석 |')
    lines.append(f'|:---|:---:|:---|')
    if avg_rally_then_drop != 0:
        lines.append(f'| 고점 찍고 반락 | **{avg_rally_then_drop:.1f}%** | 상승 후 평균 이만큼 되돌림 |')
    if avg_drop_then_rally != 0:
        lines.append(f'| 저점 찍고 반등 | **+{avg_drop_then_rally:.1f}%** | 하락 후 평균 이만큼 회복 |')
    lines.append('')

    # 시간별 방향 확률
    lines.append(f'**⏰ 시간대별 상승 확률:**')
    lines.append('')
    lines.append(f'| 기간 | 상승 확률 | 평균 수익률 | 예상 지수 |')
    lines.append(f'|:---|:---:|:---:|---:|')
    lines.append(f'| 10일 후 | **{prob_up_10:.0f}%** | {np.mean(ret_10d):+.1f}% | {current_price * (1 + np.mean(ret_10d)/100):,.0f} |')
    lines.append(f'| 20일 후 | **{prob_up_20:.0f}%** | {np.mean(ret_20d_fwd):+.1f}% | {current_price * (1 + np.mean(ret_20d_fwd)/100):,.0f} |')
    lines.append(f'| 40일 후 | **{prob_up_40:.0f}%** | {np.mean(ret_40d_fwd):+.1f}% | {current_price * (1 + np.mean(ret_40d_fwd)/100):,.0f} |')
    lines.append('')

    # 대표 경로 (중위값 기준)
    lines.append(f'**📈 대표 경로 (중위값):**')
    lines.append('')
    lines.append(f'| 시점 | 낙관(상위25%) | 중립(중위) | 비관(하위25%) | 중립 지수 |')
    lines.append(f'|:---|:---:|:---:|:---:|---:|')
    for d in [5, 10, 20, 30, 40]:
        if d <= len(median_path):
            i = d - 1
            lines.append(f'| {d}일 후 | {p75_path[i]:+.1f}% | {median_path[i]:+.1f}% | {p25_path[i]:+.1f}% | {current_price * (1 + median_path[i]/100):,.0f} |')
    lines.append('')

    # 유사 시점 날짜 (최근 5개만)
    recent_analogs = sorted(analog_dates, reverse=True)[:5]
    lines.append(f'**📅 가장 유사했던 과거 시점 (최근 5개):**')
    lines.append('')
    for i, (idx, sim) in enumerate(sorted(top_analogs, key=lambda x: x[0], reverse=True)[:5]):
        date = index_arr[idx]
        date_str = str(date)[:10] if hasattr(date, 'strftime') else str(date)[:10]
        price_then = close[idx]
        # 이후 실제 경로
        fwd = close[idx:idx + fwd_days + 1]
        max_r = (fwd.max() / fwd[0] - 1) * 100
        min_r = (fwd.min() / fwd[0] - 1) * 100
        final_r = (fwd[-1] / fwd[0] - 1) * 100
        lines.append(f'- **{date_str}** (유사도 {sim:.0%}) — 지수 {price_then:,.0f} → 40일간 최대+{max_r:.1f}%, 최대{min_r:.1f}%, 최종{final_r:+.1f}%')
    lines.append('')

    return '\n'.join(lines)


def _build_conditional_mdd_block(df: pd.DataFrame, market_name: str, current_price: float) -> str:
    """
    조건부 MDD 예측 블록
    현재 급등도(60일 상승률 + 이격도)를 기반으로 역사적 유사 상황에서의
    향후 MDD 분포를 산출한다.
    """
    if df is None or len(df) < 200:
        return ''

    close = df['close']
    ma60 = close.rolling(60).mean()
    disparity_60 = (close / ma60) * 100
    rally_60d = close.pct_change(60) * 100

    cur_disparity = disparity_60.iloc[-1]
    cur_rally = rally_60d.iloc[-1]

    if pd.isna(cur_disparity) or pd.isna(cur_rally):
        return ''

    # 이후 60일 MDD 및 최대 상승폭 계산 (벡터화)
    close_arr = close.values
    n = len(close_arr)
    future_mdd_60 = np.full(n, np.nan)
    future_max_rally_60 = np.full(n, np.nan)
    for i in range(n - 60):
        future_window = close_arr[i+1:i+61]
        future_mdd_60[i] = (future_window.min() / close_arr[i] - 1) * 100
        future_max_rally_60[i] = (future_window.max() / close_arr[i] - 1) * 100

    df_temp = pd.DataFrame({
        'disparity_60': disparity_60.values,
        'rally_60d': rally_60d.values,
        'future_mdd_60d': future_mdd_60,
        'future_rally_60d': future_max_rally_60
    }, index=df.index)
    df_temp = df_temp.dropna()

    # 현재 조건과 유사한 상황 필터링 (이격도 ±5%p, 상승률 ±10%p)
    disp_lo = max(cur_disparity - 5, 105)
    disp_hi = cur_disparity + 5
    rally_lo = cur_rally - 10
    rally_hi = cur_rally + 10

    similar = df_temp[
        (df_temp['disparity_60'] >= disp_lo) &
        (df_temp['disparity_60'] <= disp_hi) &
        (df_temp['rally_60d'] >= rally_lo) &
        (df_temp['rally_60d'] <= rally_hi)
    ]

    # 샘플 부족 시 조건 완화
    if len(similar) < 30:
        disp_lo = max(cur_disparity - 10, 100)
        disp_hi = cur_disparity + 10
        rally_lo = cur_rally - 15
        rally_hi = cur_rally + 15
        similar = df_temp[
            (df_temp['disparity_60'] >= disp_lo) &
            (df_temp['disparity_60'] <= disp_hi) &
            (df_temp['rally_60d'] >= rally_lo) &
            (df_temp['rally_60d'] <= rally_hi)
        ]

    if len(similar) < 10:
        return ''

    # 대조군: 정상 구간
    normal = df_temp[
        (df_temp['disparity_60'] >= 95) &
        (df_temp['disparity_60'] <= 105) &
        (df_temp['rally_60d'] >= -5) &
        (df_temp['rally_60d'] <= 5)
    ]

    avg_mdd = similar['future_mdd_60d'].mean()
    med_mdd = similar['future_mdd_60d'].median()
    worst_mdd = similar['future_mdd_60d'].min()
    prob_10 = (similar['future_mdd_60d'] <= -10).sum() / len(similar) * 100
    prob_15 = (similar['future_mdd_60d'] <= -15).sum() / len(similar) * 100
    prob_20 = (similar['future_mdd_60d'] <= -20).sum() / len(similar) * 100

    normal_avg = normal['future_mdd_60d'].mean() if len(normal) > 0 else -6.0
    amplification = avg_mdd / normal_avg if normal_avg != 0 else 1.0

    # 위험도 판단
    if avg_mdd <= -12:
        risk_signal = '🔴 고위험'
    elif avg_mdd <= -8:
        risk_signal = '🟠 주의'
    elif avg_mdd <= -6:
        risk_signal = '🟡 보통'
    else:
        risk_signal = '🟢 안전'

    lines = []
    lines.append(f'### � {market_name} 향후 60일 등락 위험 분석')
    lines.append('')
    lines.append(f'> 💡 과거 30년간 지금과 비슷했던 상황(이격도 {cur_disparity:.0f}%, 2개월 상승률 {cur_rally:+.0f}%) **{len(similar)}번** 발생')
    lines.append(f'> → 그때 이후 2개월간 실제로 얼마나 올랐고 빠졌는지 통계')
    lines.append('')

    # ── 상승 분석 ──
    avg_rally = similar['future_rally_60d'].mean()
    med_rally = similar['future_rally_60d'].median()
    best_rally = similar['future_rally_60d'].max()
    prob_up_5 = (similar['future_rally_60d'] >= 5).sum() / len(similar) * 100
    prob_up_10 = (similar['future_rally_60d'] >= 10).sum() / len(similar) * 100
    prob_up_15 = (similar['future_rally_60d'] >= 15).sum() / len(similar) * 100
    prob_up_20 = (similar['future_rally_60d'] >= 20).sum() / len(similar) * 100

    lines.append(f'**📈 상승 가능성:**')
    lines.append('')
    lines.append(f'| 항목 | 결과 | 해석 |')
    lines.append(f'|:---|:---:|:---|')
    lines.append(f'| **2개월 내 평균 최대상승폭** | **+{avg_rally:.1f}%** | 중위값 +{med_rally:.1f}% |')
    lines.append(f'| 역대 최고 사례 | +{best_rally:.1f}% | 지수 {current_price * (1 + best_rally/100):,.0f} |')
    lines.append('')
    lines.append(f'| 상승폭 | 발생 확률 | 그때 지수 |')
    lines.append(f'|:---|:---:|---:|')
    lines.append(f'| +5% 이상 상승 | **{prob_up_5:.0f}%** | {current_price * 1.05:,.0f} |')
    lines.append(f'| +10% 이상 상승 | **{prob_up_10:.0f}%** | {current_price * 1.10:,.0f} |')
    lines.append(f'| +15% 이상 상승 | **{prob_up_15:.0f}%** | {current_price * 1.15:,.0f} |')
    lines.append(f'| +20% 이상 상승 | **{prob_up_20:.0f}%** | {current_price * 1.20:,.0f} |')
    lines.append('')

    # ── 하락 분석 ──
    lines.append(f'**📉 하락 위험:** {risk_signal}')
    lines.append('')
    lines.append(f'| 항목 | 결과 | 해석 |')
    lines.append(f'|:---|:---:|:---|')
    lines.append(f'| **2개월 내 평균 최대낙폭** | **{avg_mdd:.1f}%** | 중위값 {med_mdd:.1f}% |')
    lines.append(f'| 역대 최악의 경우 | {worst_mdd:.1f}% | 지수 {current_price * (1 + worst_mdd/100):,.0f} |')
    if amplification >= 1.3:
        lines.append(f'| ⚠️ 평소보다 위험한 정도 | **{amplification:.1f}배** | 평소보다 {amplification:.1f}배 더 빠질 수 있음 |')
    elif amplification <= 0.8:
        lines.append(f'| 평소보다 위험한 정도 | {amplification:.1f}배 | 평소보다 오히려 안전 |')
    else:
        lines.append(f'| 평소보다 위험한 정도 | {amplification:.1f}배 | 평소와 비슷한 수준 |')
    lines.append('')
    prob_5 = (similar['future_mdd_60d'] <= -5).sum() / len(similar) * 100
    lines.append(f'**2개월 내 하락 확률과 예상 지수:**')
    lines.append('')
    lines.append(f'| 하락폭 | 발생 확률 | 그때 지수 |')
    lines.append(f'|:---|:---:|---:|')
    lines.append(f'| -5% 이상 하락 | **{prob_5:.0f}%** | {current_price * 0.95:,.0f} |')
    lines.append(f'| -10% 이상 하락 | **{prob_10:.0f}%** | {current_price * 0.90:,.0f} |')
    lines.append(f'| -15% 이상 하락 | **{prob_15:.0f}%** | {current_price * 0.85:,.0f} |')
    lines.append(f'| -20% 이상 하락 | **{prob_20:.0f}%** | {current_price * 0.80:,.0f} |')
    lines.append('')

    # ── 확률 기반 액션 결론 ──
    # 기대값 관점: 상승 확률 높은 구간 vs 하락 확률 높은 구간의 경계점 산출
    # "50% 이상 확률로 도달하는 상승폭" = 매도 타겟 참고선
    # "50% 이상 확률로 도달하는 하락폭" = 손절/익절 참고선

    # 상승측: 확률 50% 이상인 가장 높은 구간
    up_levels = [(5, prob_up_5), (10, prob_up_10), (15, prob_up_15), (20, prob_up_20)]
    best_up_target = 0
    for pct, prob in up_levels:
        if prob >= 50:
            best_up_target = pct

    # 하락측: 확률 50% 이상인 가장 큰 하락 구간
    down_levels = [(5, prob_5), (10, prob_10), (15, prob_15), (20, prob_20)]
    likely_drop = 0
    for pct, prob in down_levels:
        if prob >= 50:
            likely_drop = pct

    # 기대수익률 산출 (상승 평균 x 확률 vs 하락 평균 x 확률)
    up_ev = avg_rally * (prob_up_5 / 100)
    down_ev = abs(avg_mdd) * (prob_5 / 100)
    risk_reward = up_ev / down_ev if down_ev > 0 else float('inf')

    lines.append(f'**💡 확률 기반 판단:**')
    lines.append('')

    if best_up_target > 0 and likely_drop > 0:
        target_price = current_price * (1 + best_up_target / 100)
        stop_price = current_price * (1 - likely_drop / 100)
        lines.append(f'> 과거 유사 상황에서 **+{best_up_target}%까지 상승할 확률이 50% 이상**이었고,')
        lines.append(f'> 동시에 **-{likely_drop}%까지 하락할 확률도 50% 이상**이었습니다.')
        lines.append(f'>')
        if risk_reward >= 1.5:
            lines.append(f'> 📌 **상승 기대값({up_ev:.1f})이 하락 기대값({down_ev:.1f})보다 크므로 ({risk_reward:.1f}배)**,')
            lines.append(f'> **{target_price:,.0f}**(+{best_up_target}%)까지 보유 후 익절하되, **{stop_price:,.0f}**(-{likely_drop}%) 이탈 시 손절이 합리적')
        elif risk_reward >= 1.0:
            lines.append(f'> 📌 상승·하락 기대값이 비슷합니다 (상승 {up_ev:.1f} vs 하락 {down_ev:.1f}).')
            lines.append(f'> 현재가 부근에서 **분할 익절** 추천. 목표 **{target_price:,.0f}**(+{best_up_target}%), 손절 **{stop_price:,.0f}**(-{likely_drop}%)')
        else:
            lines.append(f'> 📌 **하락 기대값({down_ev:.1f})이 상승 기대값({up_ev:.1f})보다 큽니다 ({1/risk_reward:.1f}배)**.')
            lines.append(f'> **비중 축소 우선**. 보유 시 **{stop_price:,.0f}**(-{likely_drop}%) 반드시 손절, 목표 **{target_price:,.0f}**(+{best_up_target}%)')
    elif best_up_target > 0:
        target_price = current_price * (1 + best_up_target / 100)
        lines.append(f'> 📌 +{best_up_target}% 상승 확률이 높고 큰 하락 확률은 낮습니다.')
        lines.append(f'> **{target_price:,.0f}**(+{best_up_target}%)까지 보유 후 익절 추천')
    elif likely_drop > 0:
        stop_price = current_price * (1 - likely_drop / 100)
        lines.append(f'> 📌 -{likely_drop}% 하락 확률이 높고 큰 상승 확률은 낮습니다.')
        lines.append(f'> **비중 축소** 후 **{stop_price:,.0f}**(-{likely_drop}%) 이탈 시 전량 손절 추천')
    else:
        lines.append(f'> 📌 뚜렷한 방향성 없음. 현재 비중 유지하며 추이 관망')

    lines.append('')

    return '\n'.join(lines)


def _build_valuation_block(current_kospi: float) -> str:
    """코스피 밸류에이션 요약 블록 (코스피 분석 시에만)"""
    fwd_per = current_kospi / FWD_EPS
    pbr = current_kospi / FWD_BPS

    # PER 판단
    if fwd_per <= 8.5:
        per_judge = '극저평가 🟢🟢'
    elif fwd_per <= 9.5:
        per_judge = '저평가 🟢'
    elif fwd_per <= 10.5:
        per_judge = '적정 ⚪'
    elif fwd_per <= 11.5:
        per_judge = '고평가 🟡'
    else:
        per_judge = '과열 🔴'

    # PBR 판단
    if pbr <= 0.9:
        pbr_judge = '극저평가 🟢🟢'
    elif pbr <= 1.1:
        pbr_judge = '저평가 🟢'
    elif pbr <= 1.3:
        pbr_judge = '적정 ⚪'
    elif pbr <= 1.5:
        pbr_judge = '고평가 🟡'
    else:
        pbr_judge = '과열 🔴'

    # PER 밴드별 적정지수
    per_bands = [
        ('-2σ', 7.8), ('-1σ', 9.0), ('5Y평균', 10.2),
        ('+1σ', 11.4), ('+2σ', 12.6)
    ]

    lines = []
    lines.append('### 📊 코스피 밸류에이션')
    lines.append('')
    lines.append(f'| 지표 | 현재 | 22Y평균 | 판단 |')
    lines.append('|:---:|:---:|:---:|:---|')
    lines.append(f'| **Fwd PER** | **{fwd_per:.1f}배** | 9.9배 | {per_judge} |')
    lines.append(f'| **PBR** | **{pbr:.2f}배** | 1.14배 | {pbr_judge} |')
    lines.append(f'| Fwd EPS | {FWD_EPS:.0f} | - | BPS {FWD_BPS:.0f} |')
    lines.append('')

    lines.append('| PER 밴드 | 적정지수 | 괴리 |')
    lines.append('|:---:|---:|:---:|')
    for label, per in per_bands:
        implied = FWD_EPS * per
        gap = (implied - current_kospi) / current_kospi * 100
        marker = ' ◀' if abs(gap) < 5 else ''
        lines.append(f'| {label} ({per}) | {implied:,.0f} | {gap:+.1f}%{marker} |')
    lines.append('')

    return '\n'.join(lines)


def generate_summary(market_results: List[Dict]) -> str:
    """
    일일 종합 요약 리포트 생성

    Args:
        market_results: list of dict, 각 dict는:
            - market: 'kospi' | 'kosdaq'
            - market_name: '코스피' | '코스닥'
            - current_price: float
            - trend_type: str
            - trend_confidence: int
            - selected_strategies: list
            - df: DataFrame
            - report_path: str (상세 리포트 경로)

    Returns:
        요약 리포트 파일 경로
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    today_display = datetime.now().strftime('%Y-%m-%d %H:%M')

    lines = []
    lines.append(f'# 📋 MarketTop 일일 종합 ({today_display})')
    lines.append('')
    lines.append('> A4 한 장 요약 — 상세는 각 시장 리포트 참조')
    lines.append('')
    lines.append('---')
    lines.append('')

    kospi_price = None

    for mr in market_results:
        block = _build_market_block(
            market_name=mr['market_name'],
            current_price=mr['current_price'],
            trend_type=mr['trend_type'],
            trend_confidence=mr['trend_confidence'],
            strategies=mr['selected_strategies'],
            df=mr['df'],
        )
        lines.append(block)
        lines.append('---')
        lines.append('')

        if mr['market'] == 'kospi':
            kospi_price = mr['current_price']

    # 밸류에이션 블록 (코스피가 있을 때만)
    if kospi_price is not None:
        val_block = _build_valuation_block(kospi_price)
        lines.append(val_block)

        # 밸류에이션 차트 임베드 (같은 폴더 내 최신 차트 찾기)
        chart_pattern = '코스피_밸류에이션차트_'
        try:
            chart_files = [f for f in os.listdir(REPORTS_DIR)
                           if f.startswith(chart_pattern) and f.endswith('.png')]
            if chart_files:
                latest_chart = sorted(chart_files)[-1]
                lines.append(f'![밸류에이션 차트]({latest_chart})')
                lines.append('')
        except OSError:
            pass

        lines.append('---')
        lines.append('')

    # 조건부 MDD 예측 블록 (각 시장별)
    for mr in market_results:
        mdd_block = _build_conditional_mdd_block(
            mr['df'], mr['market_name'], mr['current_price']
        )
        if mdd_block:
            lines.append(mdd_block)

    if any(_build_conditional_mdd_block(mr['df'], mr['market_name'], mr['current_price']) for mr in market_results):
        lines.append('---')
        lines.append('')

    # 과거 유사 패턴 분석 블록 (각 시장별)
    for mr in market_results:
        analog_block = _build_pattern_analog_block(
            mr['df'], mr['market_name'], mr['current_price']
        )
        if analog_block:
            lines.append(analog_block)

    if any(_build_pattern_analog_block(mr['df'], mr['market_name'], mr['current_price']) for mr in market_results):
        lines.append('---')
        lines.append('')

    # 상세 리포트 링크
    lines.append('### 📎 상세 리포트')
    lines.append('')
    for mr in market_results:
        rp = mr.get('report_path', '')
        basename = os.path.basename(rp) if rp else ''
        lines.append(f'- {mr["market_name"]}: [{basename}]({basename})')
    lines.append('')

    # 면책 조항
    lines.append('---')
    lines.append('')
    lines.append('*본 리포트는 백테스트 기반 참고용이며, 투자 판단의 최종 책임은 투자자 본인에게 있습니다.*')

    # 저장
    os.makedirs(REPORTS_DIR, exist_ok=True)
    filename = f'일일종합_{timestamp}.md'
    filepath = os.path.join(REPORTS_DIR, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f'\n✅ 일일 종합 요약 저장: {filepath}')
    return filepath
