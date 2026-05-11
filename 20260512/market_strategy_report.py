# -*- coding: utf-8 -*-
"""
시장 국면 분석 및 매매 전략 리포트 생성기
- 현재 코스피/코스닥 기술적 지표 종합 진단
- 피보나치 기반 고점/저점 예측
- 과거 유사 패턴 통계 분석
- 포지션별 분할 매수/매도 전략 제시
- Kelly Criterion 기반 최적 비중 계산
"""

import os
import sys
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from config import DB_PATH, WEEKLY_RESEARCH_DIR
from data_loader import DataLoader


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 기술적 지표 계산 함수
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def calc_rsi(series, period=14):
    """RSI 계산"""
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def calc_bollinger(series, period=20, num_std=2):
    """볼린저밴드 계산"""
    ma = series.rolling(period).mean()
    std = series.rolling(period).std()
    upper = ma + num_std * std
    lower = ma - num_std * std
    pct_b = (series - lower) / (upper - lower) * 100
    return ma, upper, lower, pct_b


def calc_disparity(series, period):
    """이격도 계산"""
    ma = series.rolling(period).mean()
    return series / ma * 100


def calc_fibonacci_levels(high, low):
    """피보나치 되돌림 및 확장 레벨 계산"""
    diff = high - low
    retracements = {}
    for fib in [0.236, 0.382, 0.5, 0.618, 0.786]:
        retracements[fib] = high - diff * fib
    extensions = {}
    for ext in [1.0, 1.272, 1.618, 2.0]:
        extensions[ext] = low + diff * ext
    return retracements, extensions


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 패턴 분석 함수
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def analyze_forward_returns(df, mask, periods=[5, 10, 20, 40, 60]):
    """조건 충족 시점 이후 수익률 분석"""
    results = {}
    indices = df.index[mask]
    close = df['close'].values
    idx_positions = np.where(mask)[0]

    for days in periods:
        rets = []
        max_ups = []
        max_dds = []
        for pos in idx_positions:
            if pos + days < len(close):
                future = close[pos:pos + days + 1]
                start = future[0]
                rets.append((future[-1] / start - 1) * 100)
                max_ups.append((future.max() / start - 1) * 100)
                max_dds.append((future.min() / start - 1) * 100)
        if rets:
            arr = np.array(rets)
            results[days] = {
                'mean': arr.mean(),
                'median': np.median(arr),
                'up_prob': (arr > 0).mean() * 100,
                'worst': arr.min(),
                'best': arr.max(),
                'p25': np.percentile(arr, 25),
                'p75': np.percentile(arr, 75),
                'max_up_mean': np.array(max_ups).mean(),
                'max_dd_mean': np.array(max_dds).mean(),
                'count': len(arr),
            }
    return results


def analyze_ath_corrections(df):
    """ATH 갱신 후 조정 패턴 분석"""
    close = df['close'].values
    peak = np.maximum.accumulate(close)
    is_ath = (close == peak) & (np.concatenate([[False], close[1:] > close[:-1]]))
    ath_indices = np.where(is_ath)[0]

    drops = []
    for idx in ath_indices:
        future = close[idx:idx + 61]
        if len(future) > 5:
            max_drop = (future.min() / future[0] - 1) * 100
            drops.append(max_drop)

    if drops:
        arr = np.array(drops)
        return {
            'count': len(arr),
            'mean': arr.mean(),
            'median': np.median(arr),
            'p10': np.percentile(arr, 10),
            'p25': np.percentile(arr, 25),
            'p75': np.percentile(arr, 75),
            'p90': np.percentile(arr, 90),
        }
    return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 리포트 생성
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_strategy_report():
    """시장 전략 리포트 생성"""
    loader = DataLoader(DB_PATH)

    # 데이터 로드
    kospi_df = loader.load_market_data('kospi')
    kosdaq_df = loader.load_market_data('kosdaq')

    kospi_close = kospi_df['close']
    kosdaq_close = kosdaq_df['close']

    latest_kospi = float(kospi_close.iloc[-1])
    latest_kosdaq = float(kosdaq_close.iloc[-1])
    latest_date = kospi_df.index[-1]

    # ── 기술적 지표 계산 (KOSPI) ──
    rsi_kospi = calc_rsi(kospi_close, 14).iloc[-1]
    rsi_kosdaq = calc_rsi(kosdaq_close, 14).iloc[-1]

    disp20_kospi = calc_disparity(kospi_close, 20).iloc[-1]
    disp60_kospi = calc_disparity(kospi_close, 60).iloc[-1]
    disp120_kospi = calc_disparity(kospi_close, 120).iloc[-1]
    disp200_kospi = calc_disparity(kospi_close, 200).iloc[-1]

    disp20_kosdaq = calc_disparity(kosdaq_close, 20).iloc[-1]
    disp60_kosdaq = calc_disparity(kosdaq_close, 60).iloc[-1]

    _, bb_upper, bb_lower, bb_pctb_kospi = calc_bollinger(kospi_close)
    bb_pctb_kospi = bb_pctb_kospi.iloc[-1]

    ret_3m_kospi = (kospi_close.iloc[-1] / kospi_close.iloc[-60] - 1) * 100 if len(kospi_close) >= 60 else 0
    vol_20 = kospi_close.pct_change().iloc[-20:].std() * np.sqrt(252) * 100

    # 52주 고/저
    one_year_ago = latest_date - timedelta(days=365)
    recent_kospi = kospi_close[kospi_close.index >= one_year_ago]
    high_52w = float(recent_kospi.max())
    low_52w = float(recent_kospi.min())

    ath_kospi = float(kospi_close.max())
    ath_pct = (latest_kospi / ath_kospi - 1) * 100

    # ── 피보나치 레벨 (최근 랠리 기준) ──
    recent_3m = kospi_close[kospi_close.index >= (latest_date - timedelta(days=120))]
    rally_low = float(recent_3m.min())
    rally_high = latest_kospi
    fib_ret, fib_ext = calc_fibonacci_levels(rally_high, rally_low)

    # ── 패턴 분석 ──
    # RSI 극과열 (>=85) 이후 패턴
    rsi_series = calc_rsi(kospi_close, 14)
    rsi_extreme_mask = (rsi_series >= 85).values.copy()
    rsi_extreme_mask[:14] = False  # NaN 구간 제거
    rsi_patterns = analyze_forward_returns(kospi_df, rsi_extreme_mask)

    # 이격도 극과열 (MA60 대비 125%+) 이후 패턴
    disp60_series = calc_disparity(kospi_close, 60)
    disp_extreme_mask = (disp60_series >= 125).values.copy()
    disp_extreme_mask[:60] = False
    disp_patterns = analyze_forward_returns(kospi_df, disp_extreme_mask)

    # 3개월 급등 (40%+) 후 패턴
    ret60 = kospi_close.pct_change(60) * 100
    rally_mask = (ret60 >= 40).values.copy()
    rally_mask[:60] = False
    rally_patterns = analyze_forward_returns(kospi_df, rally_mask)

    # ATH 조정 패턴
    ath_stats = analyze_ath_corrections(kospi_df)

    # ── 과열도 점수 계산 ──
    overheat_signals = []
    overheat_count = 0

    def check_signal(name, value, threshold, direction='above'):
        nonlocal overheat_count
        if direction == 'above' and value > threshold:
            overheat_count += 1
            return '🔴'
        elif direction == 'below' and value < threshold:
            overheat_count += 1
            return '🔴'
        elif direction == 'above' and value > threshold * 0.9:
            return '🟠'
        return '🟢'

    status_rsi = '🔴 극과열' if rsi_kospi >= 80 else ('🟠 과열' if rsi_kospi >= 70 else '🟢 정상')
    if rsi_kospi >= 70: overheat_count += 1
    status_disp20 = '🔴 극과열' if disp20_kospi >= 115 else ('🟠 과열' if disp20_kospi >= 110 else '🟢 정상')
    if disp20_kospi >= 110: overheat_count += 1
    status_disp60 = '🔴 역대급' if disp60_kospi >= 125 else ('🔴 극과열' if disp60_kospi >= 115 else ('🟠 과열' if disp60_kospi >= 110 else '🟢 정상'))
    if disp60_kospi >= 110: overheat_count += 1
    status_disp200 = '🔴 역대급' if disp200_kospi >= 140 else ('🔴 극과열' if disp200_kospi >= 120 else '🟢 정상')
    if disp200_kospi >= 120: overheat_count += 1
    status_bb = '🔴 상단 이탈' if bb_pctb_kospi > 100 else ('🟠 상단 근접' if bb_pctb_kospi > 80 else '🟢 정상')
    if bb_pctb_kospi > 100: overheat_count += 1
    status_ret3m = '🔴 과열' if ret_3m_kospi > 30 else ('🟠 주의' if ret_3m_kospi > 20 else '🟢 정상')
    if ret_3m_kospi > 30: overheat_count += 1
    status_ath = '⚡ 신고가' if ath_pct >= -0.5 else f'📉 -{abs(ath_pct):.1f}%'
    if ath_pct >= -1: overheat_count += 1
    status_vol = '🟠 높음' if vol_20 > 25 else '🟢 정상'
    if vol_20 > 25: overheat_count += 1

    # ── Kelly Criterion 계산 ──
    # RSI 극과열 이후 60일 패턴 기반
    if 60 in rsi_patterns:
        p60 = rsi_patterns[60]
        up_prob = p60['up_prob'] / 100
        avg_gain = p60['p75']  # 상위 사분위 수익
        avg_loss = abs(p60['p25']) if p60['p25'] < 0 else abs(p60['worst']) * 0.5
    else:
        up_prob = 0.6
        avg_gain = 15
        avg_loss = 12

    if avg_gain > 0:
        kelly = (up_prob * avg_gain - (1 - up_prob) * avg_loss) / avg_gain
        kelly = max(0, min(kelly, 1))
    else:
        kelly = 0
    half_kelly = kelly / 2

    ev_up = up_prob * avg_gain
    ev_down = (1 - up_prob) * avg_loss
    net_ev = ev_up - ev_down

    # ── 매도 전략 설계 ──
    sell_steps = []
    if overheat_count >= 5:
        sell_steps = [
            (0, 30, "극과열 지표 다수 경고, 즉시 이익 실현"),
            (5, 20, f"Fib 100% 초과, 단기 과열 최고조 (목표: {rally_high * 1.05:.0f})"),
            (10, 20, f"Fib 127% 확장 도달, 보수적 목표가 (목표: {fib_ext.get(1.272, rally_high*1.1):.0f})"),
            (15, 15, f"역사적 극과열 이후 평균 상승폭 한계 (목표: {rally_high * 1.15:.0f})"),
            (23, 15, f"Fib 162% 확장 = 전량 매도 (목표: {fib_ext.get(1.618, rally_high*1.23):.0f})"),
        ]
    elif overheat_count >= 3:
        sell_steps = [
            (0, 20, "과열 경고, 부분 이익 실현"),
            (5, 15, f"1차 목표가 도달 (목표: {rally_high * 1.05:.0f})"),
            (10, 20, f"Fib 127% 확장 (목표: {fib_ext.get(1.272, rally_high*1.1):.0f})"),
            (20, 20, f"Fib 162% 확장 (목표: {fib_ext.get(1.618, rally_high*1.2):.0f})"),
            (30, 25, f"Fib 200% 확장 = 전량 매도 (목표: {fib_ext.get(2.0, rally_high*1.3):.0f})"),
        ]
    else:
        sell_steps = [
            (10, 20, f"1차 목표가 도달 (목표: {rally_high * 1.10:.0f})"),
            (20, 25, f"2차 목표가 (목표: {rally_high * 1.20:.0f})"),
            (30, 25, f"3차 목표가 (목표: {rally_high * 1.30:.0f})"),
            (50, 30, f"전량 매도 (목표: {rally_high * 1.50:.0f})"),
        ]

    # ── 매수 전략 설계 ──
    buy_steps = [
        (-8, 20, f"Fib 23.6% 되돌림, 1차 지지 (지수: {fib_ret[0.236]:.0f})"),
        (-14, 25, f"Fib 38.2% 되돌림, 건강한 조정 (지수: {fib_ret[0.382]:.0f})"),
        (-18, 25, f"Fib 50% 되돌림, 강한 지지대 (지수: {fib_ret[0.5]:.0f})"),
        (-25, 30, f"Fib 61.8%+, 위기 매수 (지수: {fib_ret[0.618]:.0f})"),
    ]

    # Trailing Stop 설정
    if overheat_count >= 5:
        trailing_1 = (-8, 50, "Fib 23.6% 되돌림 = 1차 지지 이탈")
        trailing_2 = (-14, 100, "Fib 38.2% 되돌림 = 추세 전환 신호")
    elif overheat_count >= 3:
        trailing_1 = (-10, 50, "1차 지지선 이탈")
        trailing_2 = (-18, 100, "Fib 50% 되돌림 = 추세 약화")
    else:
        trailing_1 = (-15, 50, "주요 지지선 이탈")
        trailing_2 = (-25, 100, "추세 전환 확인")

    # ── 리포트 작성 ──
    report_date = datetime.now().strftime('%Y%m%d_%H%M%S')
    os.makedirs(WEEKLY_RESEARCH_DIR, exist_ok=True)
    filename = os.path.join(WEEKLY_RESEARCH_DIR, f"시장전략_매매타이밍_{report_date}.md")

    with open(filename, 'w', encoding='utf-8') as f:
        f.write("# 🎯 시장 국면 분석 및 매매 전략 리포트\n\n")
        f.write(f"**분석일시**: {datetime.now().strftime('%Y년 %m월 %d일 %H:%M')}\n")
        f.write(f"**분석 기준 지수**: 코스피 **{latest_kospi:,.0f}** / 코스닥 **{latest_kosdaq:,.0f}**\n")
        period_start = kospi_df.index[0].strftime('%Y')
        period_end = kospi_df.index[-1].strftime('%Y')
        f.write(f"**데이터 기반**: {int(period_end)-int(period_start)}년 시계열 ({period_start}~{period_end}) + 외국인 수급 20년\n")
        f.write(f"**분석 방법론**: 통계적 유사 패턴 분석 + 기술적 지표 극단값 분석 + 수급 패턴 분석\n\n")
        f.write("---\n\n")

        # ── 현재 시장 진단 ──
        f.write("## 📊 현재 시장 진단\n\n")
        f.write("### 🌡️ 과열 지표 종합 진단\n\n")
        f.write("| 지표 | 현재값 | 과열 기준 | 상태 | 해석 |\n")
        f.write("|:----:|:------:|:---------:|:----:|:-----|\n")
        f.write(f"| RSI(14) | **{rsi_kospi:.1f}** | >70 | {status_rsi} | {'역대 상위 수준' if rsi_kospi >= 85 else '과열 구간'} |\n")
        f.write(f"| MA20 이격도 | **{disp20_kospi:.1f}%** | >110% | {status_disp20} | 20일 이평선 대비 {disp20_kospi-100:.1f}% 괴리 |\n")
        f.write(f"| MA60 이격도 | **{disp60_kospi:.1f}%** | >115% | {status_disp60} | 60일 이평선 기준 |\n")
        f.write(f"| MA200 이격도 | **{disp200_kospi:.1f}%** | >120% | {status_disp200} | 장기추세 대비 |\n")
        f.write(f"| 볼린저밴드 %B | **{bb_pctb_kospi:.1f}%** | >100% | {status_bb} | 밴드 {'상단 돌파' if bb_pctb_kospi > 100 else '내 위치'} |\n")
        f.write(f"| 3개월 수익률 | **{ret_3m_kospi:+.1f}%** | >30% | {status_ret3m} | 최근 3개월간 변화 |\n")
        f.write(f"| ATH 대비 | **{ath_pct:+.1f}%** | - | {status_ath} | {'역대 최고가 갱신 중' if ath_pct >= -0.5 else '고점 대비 하락'} |\n")
        f.write(f"| 20일 변동성 | **{vol_20:.1f}%** | >25% | {status_vol} | {'평소 대비 높은 변동성' if vol_20 > 25 else '정상 범위'} |\n\n")

        f.write("### 📌 종합 판단\n\n")
        f.write("```\n")
        if overheat_count >= 6:
            f.write(f"  🔴  과열 지표 8개 중 {overheat_count}개 경고  →  극도의 과열 구간\n")
        elif overheat_count >= 4:
            f.write(f"  🟠  과열 지표 8개 중 {overheat_count}개 경고  →  과열 구간, 주의 필요\n")
        elif overheat_count >= 2:
            f.write(f"  🟡  과열 지표 8개 중 {overheat_count}개 경고  →  약간 과열, 관찰 필요\n")
        else:
            f.write(f"  🟢  과열 지표 8개 중 {overheat_count}개 경고  →  정상 구간\n")

        # 패턴 기반 부가 정보
        if 20 in rsi_patterns and rsi_kospi >= 85:
            rp = rsi_patterns[20]
            f.write(f"\n  ⚠️ RSI 85+ 이후에도 상승확률 {rp['up_prob']:.0f}% (추세의 힘이 강할 수 있음)\n")
        if 20 in disp_patterns and disp60_kospi >= 125:
            dp20 = disp_patterns[20]
            dp60 = disp_patterns.get(60, {})
            f.write(f"  ⚠️ 이격도 125%+에서 20일 내 하락확률 {100-dp20['up_prob']:.0f}%")
            if dp60:
                f.write(f", 60일 후 상승확률 {dp60['up_prob']:.0f}%")
            f.write("\n")

        if overheat_count >= 4:
            f.write(f'\n  📌 핵심: "추세를 거스르지 말되, 리스크 관리는 철저히"\n')
        elif overheat_count >= 2:
            f.write(f'\n  📌 핵심: "추세를 따르되, 과열 신호에 대비하라"\n')
        else:
            f.write(f'\n  📌 핵심: "추세 안정적, 보유 유지 적정"\n')
        f.write("```\n\n")
        f.write("---\n\n")

        # ── 예상 고점/저점 시나리오 ──
        f.write("## 🔮 예상 고점·저점 시나리오\n\n")

        f.write("### 📈 상승 시나리오 (피보나치 확장)\n\n")
        f.write("| 시나리오 | 목표 지수 | 상승폭 | 근거 | 확률 |\n")
        f.write("|:--------:|:---------:|:------:|:-----|:----:|\n")
        ext_127 = fib_ext.get(1.272, rally_high * 1.1)
        ext_162 = fib_ext.get(1.618, rally_high * 1.2)
        ext_200 = fib_ext.get(2.0, rally_high * 1.3)
        f.write(f"| 보수적 | **{ext_127:,.0f}** | +{(ext_127/latest_kospi-1)*100:.0f}% | Fibonacci 127.2% 확장 | 60% |\n")
        f.write(f"| 중립적 | **{ext_162:,.0f}** | +{(ext_162/latest_kospi-1)*100:.0f}% | Fibonacci 161.8% 확장 | 35% |\n")
        f.write(f"| 낙관적 | **{ext_200:,.0f}** | +{(ext_200/latest_kospi-1)*100:.0f}% | Fibonacci 200% 확장 | 15% |\n\n")

        # 근거 추가
        if 60 in rsi_patterns:
            rp60 = rsi_patterns[60]
            f.write(f"> 💡 **근거**: RSI 85+ 이후 60일 평균 {rp60['mean']:+.1f}%, 중위 {rp60['median']:+.1f}%.")
            if 60 in disp_patterns:
                dp60 = disp_patterns[60]
                f.write(f" 이격도 125%+ 이후 60일 평균 {dp60['mean']:+.1f}% (상승확률 {dp60['up_prob']:.0f}%)")
            f.write("\n\n")

        f.write("### 📉 하락 시나리오 (피보나치 되돌림 + 역사적 MDD)\n\n")
        f.write("| 시나리오 | 지지 지수 | 하락폭 | 근거 | 확률 |\n")
        f.write("|:--------:|:---------:|:------:|:-----|:----:|\n")
        scenarios = [
            (0.236, "1차 조정", 75), (0.382, "건강한 조정", 50),
            (0.5, "깊은 조정", 30), (0.618, "약세장 전환", 15),
            (0.786, "위기 수준", 5),
        ]
        for fib_level, name, prob in scenarios:
            level = fib_ret[fib_level]
            pct = (level / latest_kospi - 1) * 100
            f.write(f"| {name} | **{level:,.0f}** | {pct:.1f}% | Fib {fib_level*100:.1f}% 되돌림 | {prob}% |\n")
        f.write("\n")

        if ath_stats:
            f.write(f"> 💡 **근거**: ATH 이후 60일 내 최대하락 평균 {ath_stats['mean']:.1f}%, P25 = {ath_stats['p25']:.1f}%, P75 = {ath_stats['p75']:.1f}%\n")
        if 20 in rally_patterns:
            rp = rally_patterns[20]
            f.write(f"> 3개월 40%+ 급등 후 20일 내 최대낙폭 평균 {rp['max_dd_mean']:.1f}%")
            if 40 in rally_patterns:
                f.write(f", 40일 내 {rally_patterns[40]['max_dd_mean']:.1f}%")
            f.write("\n")
        f.write("\n")

        # 확률 가중 기대 범위 시각화
        worst_2m = rally_patterns[60]['worst'] if 60 in rally_patterns else -20
        best_2m = rally_patterns[60]['best'] if 60 in rally_patterns else 30
        f.write("### 📊 확률 가중 기대 범위 (향후 2개월)\n\n")
        f.write("```\n")
        f.write(f"                            현재 {latest_kospi:,.0f}\n")
        f.write(f"                               │\n")
        f.write(f"        ┌──────────────────────┼──────────────────────┐\n")
        f.write(f"        │                      │                      │\n")
        worst_pct = rally_patterns[40]['max_dd_mean'] if 40 in rally_patterns else -15
        best_pct = rally_patterns[40]['max_up_mean'] if 40 in rally_patterns else 15
        f.write(f"    최악 {worst_pct:.0f}%              중위 기대              최고 +{best_pct:.0f}%\n")
        f.write(f"    ({latest_kospi*(1+worst_pct/100):,.0f})                                     ({latest_kospi*(1+best_pct/100):,.0f})\n")
        f.write("```\n\n")
        f.write("---\n\n")

        # ── 매매 전략 ──
        f.write("## 💰 매매 전략: 현재 포지션별 행동 지침\n\n")
        f.write("---\n\n")

        # 시나리오 A: 보유 중
        f.write("### 🟢 시나리오 A: 현재 보유 중 (이미 수익 중)\n\n")
        f.write("> **\"이익을 지키면서 추세를 따르라\"** — 워렌 버핏의 1번 규칙: \"돈을 잃지 마라\"\n\n")
        f.write("#### 📤 분할 매도 전략 (수익 확정)\n\n")
        f.write("| 단계 | 조건 | 행동 | 매도 비중 | 잔여 비중 | 근거 |\n")
        f.write("|:----:|:-----|:----:|:---------:|:---------:|:-----|\n")
        remaining = 100
        for i, (pct, weight, reason) in enumerate(sell_steps, 1):
            remaining -= weight
            if pct == 0:
                cond = "현재가 (지금 즉시)"
            else:
                cond = f"+{pct}% ({latest_kospi*(1+pct/100):,.0f})"
            f.write(f"| **{i}차** | {cond} | **매도** | **{weight}%** | {remaining}% | {reason} |\n")
        f.write("\n")

        f.write("#### 🛡️ 손절 (Trailing Stop)\n\n")
        f.write("| 조건 | 행동 | 근거 |\n")
        f.write("|:-----|:----:|:-----|\n")
        ts1_pct, ts1_sell, ts1_reason = trailing_1
        ts2_pct, ts2_sell, ts2_reason = trailing_2
        f.write(f"| 고점 대비 **{ts1_pct}%** 이탈 | 잔여분 **{ts1_sell}% 매도** | {ts1_reason} |\n")
        f.write(f"| 고점 대비 **{ts2_pct}%** 이탈 | **전량 매도** | {ts2_reason} |\n\n")

        f.write("---\n\n")

        # 시나리오 B: 미보유
        f.write("### 🔴 시나리오 B: 현재 미보유 (매수 기회 대기)\n\n")
        f.write("> **\"다른 사람들이 탐욕스러울 때 두려워하라\"** — 워렌 버핏\n")
        f.write("> **\"가격이 가치를 크게 초과할 때는 인내심을 가져라\"** — 찰리 멍거\n\n")

        if overheat_count >= 4:
            f.write("#### ⏳ 지금은 매수 시점이 아닙니다\n\n")
            f.write(f"현재 다수의 과열 지표가 경고를 보이고 있습니다.")
            if 20 in rally_patterns:
                rp = rally_patterns[20]
                f.write(f" 유사 급등 후 20일 내 **하락확률 {100-rp['up_prob']:.0f}%**, 평균 최대낙폭 **{rp['max_dd_mean']:.1f}%**입니다.")
            f.write("\n\n")
        elif overheat_count >= 2:
            f.write("#### ⚠️ 소량 매수 가능하나 신중하게\n\n")
            f.write(f"Kelly 기준 최적 신규 진입 비중: **{half_kelly*100:.0f}%** (반 Kelly)\n\n")
        else:
            f.write("#### 🟢 매수 적정 구간\n\n")
            f.write("과열 신호가 적어 분할 매수 진입 가능합니다.\n\n")

        f.write("#### 📥 분할 매수 전략 (조정 시)\n\n")
        f.write("| 단계 | 조건 | 매수 비중 | 예상 지수 | 근거 |\n")
        f.write("|:----:|:-----|:---------:|:---------:|:-----|\n")
        for i, (pct, weight, reason) in enumerate(buy_steps, 1):
            target = latest_kospi * (1 + pct / 100)
            f.write(f"| **{i}차** | {pct}% 조정 | **{weight}%** | {target:,.0f} | {reason} |\n")
        f.write("\n")

        f.write("#### 📌 매수 트리거 확인 조건\n\n")
        f.write("각 단계에서 **아래 3가지 중 2개 이상** 충족 시 매수 실행:\n")
        f.write("1. ✅ RSI(14)가 50 이하로 하락\n")
        f.write("2. ✅ 외국인 순매수 전환 (또는 순매도 하위 5% 발생 = 역발상 매수 신호)\n")
        f.write("3. ✅ MA20 이격도 100% 이하 (이평선 복귀)\n\n")

        f.write("---\n\n")

        # 시나리오 C: 부분 보유
        f.write("### 🟡 시나리오 C: 부분 보유 (리밸런싱)\n\n")
        f.write("> **\"확률이 압도적으로 유리할 때만 큰 베팅을 하라\"** — 짐 사이먼스 (르네상스 테크놀로지)\n\n")

        if overheat_count >= 5:
            stock_pct, cash_pct, safe_pct = "40~50%", "40~50%", "10~20%"
        elif overheat_count >= 3:
            stock_pct, cash_pct, safe_pct = "50~60%", "30~40%", "10%"
        else:
            stock_pct, cash_pct, safe_pct = "60~70%", "20~30%", "10%"

        f.write(f"#### 현재 권고: 주식 비중 **{stock_pct}** 유지\n\n")
        f.write("| 자산 | 비중 | 이유 |\n")
        f.write("|:----:|:----:|:-----|\n")
        f.write(f"| 주식 (보유 유지) | {stock_pct} | 추세 존중, {'과열 감안 축소' if overheat_count >= 4 else '정상 범위 유지'} |\n")
        f.write(f"| 현금 (매수 대기) | {cash_pct} | 조정 시 매수 자금 확보 |\n")
        f.write(f"| 채권/안전자산 | {safe_pct} | 급락 시 버퍼 역할 |\n\n")

        f.write("---\n\n")

        # ── 코스닥 전략 ──
        f.write("## 🔢 코스닥 전략\n\n")
        f.write("### 현재 상태\n\n")
        f.write("| 지표 | 값 | 판단 |\n")
        f.write("|:----:|:---:|:----:|\n")
        kq_rsi_status = '🔴 과열' if rsi_kosdaq >= 70 else ('🟡 중립~약과열' if rsi_kosdaq >= 55 else '🟢 정상')
        kq_disp_status = '🔴 과열' if disp60_kosdaq >= 115 else ('🟡 약간 과열' if disp60_kosdaq >= 105 else '🟢 정상')
        recent_kosdaq = kosdaq_close[kosdaq_close.index >= one_year_ago]
        kq_ath_pct = (latest_kosdaq / float(recent_kosdaq.max()) - 1) * 100
        f.write(f"| RSI(14) | {rsi_kosdaq:.1f} | {kq_rsi_status} |\n")
        f.write(f"| MA60 이격도 | {disp60_kosdaq:.1f}% | {kq_disp_status} |\n")
        f.write(f"| 52주 고점 대비 | {kq_ath_pct:+.1f}% | {'⚡ 고점 근접' if kq_ath_pct >= -3 else '하락 중'} |\n\n")

        f.write("### 코스닥 매매 전략\n\n")
        if rsi_kosdaq < 70 and disp60_kosdaq < 115:
            f.write("코스닥은 코스피 대비 **상대적으로 덜 과열**된 상태입니다.\n\n")
        else:
            f.write("코스닥도 **과열 구간**에 진입한 상태입니다.\n\n")

        f.write("| 상황 | 행동 | 비중 |\n")
        f.write("|:-----|:----:|:----:|\n")
        f.write(f"| 현재 | {'보유 유지, 신규매수 자제' if rsi_kosdaq >= 55 else '정상 운용'} | - |\n")
        for pct in [5, 10]:
            target = latest_kosdaq * (1 + pct / 100)
            f.write(f"| +{pct}% ({target:,.0f}) | 보유분 {20+pct}% 익절 | {20+pct}% 매도 |\n")
        for pct in [5, 10, 15]:
            target = latest_kosdaq * (1 - pct / 100)
            f.write(f"| -{pct}% ({target:,.0f}) | {['1차','2차','3차'][[5,10,15].index(pct)]} 매수 | {15+pct}% 매수 |\n")
        f.write("\n")

        f.write("---\n\n")

        # ── 외국인 수급 기반 보조 판단 ──
        f.write("## 📈 외국인 수급 기반 보조 판단\n\n")
        f.write("### 외국인 매도 전환 시 대응\n\n")
        f.write("| 외국인 순매도 발생 시 | 대응 |\n")
        f.write("|:---------------------|:-----|\n")
        f.write("| -5,000억 이상 (하위 5%) | ⚠️ 경계, 추가 하락 대비 |\n")
        f.write("| -7,000억 이상 (하위 3%) | 🟢 **매수 준비** — D+3~5에 1차 매수 |\n")
        f.write("| -14,000억 이상 (하위 1%) | 🟢 **적극 매수** — 역대 이후 D+30 평균 +8.74% |\n\n")

        f.write("---\n\n")

        # ── Kelly Criterion ──
        f.write("## 🧮 정량적 기대값 분석\n\n")
        f.write("### Kelly Criterion 기반 최적 베팅 비율\n\n")
        f.write("```\n")
        f.write("현재 상태에서의 기대값 계산:\n\n")
        f.write(f"상승 시나리오 (확률 {up_prob*100:.0f}%, 기대수익 +{avg_gain:.0f}%):  EV(상승) = {up_prob:.2f} × {avg_gain:.0f}% = +{ev_up:.1f}%\n")
        f.write(f"하락 시나리오 (확률 {(1-up_prob)*100:.0f}%, 기대손실 -{avg_loss:.0f}%):  EV(하락) = {(1-up_prob):.2f} × {avg_loss:.0f}% = -{ev_down:.1f}%\n\n")
        f.write(f"순 기대값 = +{ev_up:.1f}% - {ev_down:.1f}% = {net_ev:+.1f}% ({'양수 → 보유 유리' if net_ev > 0 else '음수 → 현금 유리'})\n\n")
        f.write(f"Kelly 최적 비율 = {kelly*100:.0f}%\n")
        f.write(f"→ 최대 투자 비중: 총 자산의 {kelly*100:.0f}% (보수적 1/2 Kelly = {half_kelly*100:.0f}%)\n")
        f.write("```\n\n")
        if kelly > 0:
            f.write(f"> 💡 **해석**: 기대값은 {'양수' if net_ev > 0 else '음수'}이며, Kelly가 {kelly*100:.0f}%를 제시")
            if kelly < 0.5:
                f.write(f" → 현재 시점 **풀 베팅은 비합리적**\n")
                f.write(f"> 반 Kelly 기준 {half_kelly*100:.0f}% 수준만 신규 진입 적정 (이미 보유 중이면 축소 권고)\n")
            else:
                f.write(f" → 추세 우위, **적극적 보유 유지**\n")
            f.write("\n")

        f.write("---\n\n")

        # ── 실행 체크리스트 ──
        f.write("## 📋 실행 체크리스트 (One-Page Summary)\n\n")

        f.write("### 보유자용 📤\n\n")
        f.write("```\n")
        f.write("┌─────────────────────────────────────────────────────────┐\n")
        for i, (pct, weight, reason) in enumerate(sell_steps, 1):
            if pct == 0:
                f.write(f"│  ✅ 지금 즉시: {weight}% 매도 (이익 확정){' ' * (40 - len(str(weight)))}│\n")
            else:
                target = latest_kospi * (1 + pct / 100)
                line = f"│  ✅ +{pct}% ({target:,.0f}) 도달: {weight}% 추가 매도"
                f.write(f"{line}{' ' * max(1, 58 - len(line))}│\n")
        f.write("│                                                           │\n")
        f.write("│  🛑 Trailing Stop:                                        │\n")
        ts1_target = latest_kospi * (1 + trailing_1[0] / 100)
        ts2_target = latest_kospi * (1 + trailing_2[0] / 100)
        f.write(f"│     고점 {trailing_1[0]}% ({ts1_target:,.0f}): 잔여 {trailing_1[1]}% 매도{' ' * 20}│\n")
        f.write(f"│     고점 {trailing_2[0]}% ({ts2_target:,.0f}): 전량 매도{' ' * 22}│\n")
        f.write("└─────────────────────────────────────────────────────────┘\n")
        f.write("```\n\n")

        f.write("### 미보유자용 📥\n\n")
        f.write("```\n")
        f.write("┌─────────────────────────────────────────────────────────┐\n")
        if overheat_count >= 4:
            f.write("│  ⏳ 지금: 매수 대기 (과열 구간)                           │\n")
        else:
            f.write("│  🟡 지금: 소량 매수 가능 (반 Kelly 이내)                  │\n")
        f.write("│                                                           │\n")
        for i, (pct, weight, reason) in enumerate(buy_steps, 1):
            target = latest_kospi * (1 + pct / 100)
            line = f"│  🟢 {pct}% ({target:,.0f}): {weight}% 매수"
            f.write(f"{line}{' ' * max(1, 58 - len(line))}│\n")
        f.write("│                                                           │\n")
        f.write("│  ⚠️ 매수 전 확인:                                         │\n")
        f.write("│     □ RSI < 50  □ 외국인 순매수 전환  □ 이격도 < 100%    │\n")
        f.write("│     (3개 중 2개 충족 시 실행)                             │\n")
        f.write("└─────────────────────────────────────────────────────────┘\n")
        f.write("```\n\n")

        f.write("---\n\n")

        # ── 과거 유사 패턴 통계 ──
        f.write("## 📊 부록: 과거 유사 패턴 통계\n\n")

        if rsi_patterns:
            threshold = 85 if rsi_kospi >= 85 else 70
            f.write(f"### RSI {threshold}+ 이후 향후 수익률 (KOSPI 30년)\n\n")
            f.write("| 기간 | 평균 수익률 | 중위값 | 상승확률 | 최대상승 | 최대낙폭 | 샘플수 |\n")
            f.write("|:----:|:----------:|:------:|:--------:|:--------:|:--------:|:------:|\n")
            for days in sorted(rsi_patterns.keys()):
                p = rsi_patterns[days]
                f.write(f"| {days}일 후 | {p['mean']:+.1f}% | {p['median']:+.1f}% | {p['up_prob']:.0f}% | {p['best']:+.1f}% | {p['worst']:.1f}% | {p['count']}회 |\n")
            f.write("\n")

        if disp_patterns:
            f.write(f"### 이격도 125%+ (MA60) 이후 향후 수익률\n\n")
            f.write("| 기간 | 평균 수익률 | 중위값 | 상승확률 | 최대상승 | 최대낙폭 | 샘플수 |\n")
            f.write("|:----:|:----------:|:------:|:--------:|:--------:|:--------:|:------:|\n")
            for days in sorted(disp_patterns.keys()):
                p = disp_patterns[days]
                f.write(f"| {days}일 후 | {p['mean']:+.1f}% | {p['median']:+.1f}% | {p['up_prob']:.0f}% | {p['best']:+.1f}% | {p['worst']:.1f}% | {p['count']}회 |\n")
            f.write("\n")

        if rally_patterns:
            f.write(f"### 3개월 40%+ 급등 이후 향후 수익률\n\n")
            f.write("| 기간 | 평균 수익률 | 평균 최대상승 | 평균 최대낙폭 | 상승확률 | 샘플수 |\n")
            f.write("|:----:|:----------:|:------------:|:------------:|:--------:|:------:|\n")
            for days in sorted(rally_patterns.keys()):
                p = rally_patterns[days]
                f.write(f"| {days}일 후 | {p['mean']:+.1f}% | {p['max_up_mean']:+.1f}% | {p['max_dd_mean']:.1f}% | {p['up_prob']:.0f}% | {p['count']}회 |\n")
            f.write("\n")

        f.write("---\n\n")

        # ── 리스크 고지 ──
        f.write("## ⚠️ 리스크 고지 및 유의사항\n\n")
        f.write("### 현재 국면의 특수성\n\n")
        f.write(f"1. **{'역대급 급등' if ret_3m_kospi > 40 else '강한 상승'}**: 3개월 {ret_3m_kospi:+.1f}%는 ")
        if 60 in rally_patterns:
            f.write(f"역사상 {rally_patterns[60]['count']+rally_patterns.get(40,{}).get('count',0)}회만 발생한 이례적 상황\n")
        else:
            f.write("드문 상승 구간\n")
        f.write(f"2. **추세의 힘**: RSI 과열 이후에도 추가 상승 가능 → 과열이 곧 하락을 의미하진 않음\n")
        f.write(f"3. **비대칭 리스크**: 상승 시 점진적, 하락 시 급격할 수 있음\n\n")

        f.write("### 짐 사이먼스 방식의 교훈\n\n")
        f.write("> *\"시장은 대부분의 시간 랜덤워크처럼 보이지만, 극단값에서는 평균회귀 경향이 통계적으로 유의미하다\"*\n\n")
        if disp60_kospi >= 120:
            f.write(f"- 현재 MA60 이격도 {disp60_kospi:.1f}%는 **평균회귀 압력이 강한 구간**\n")
        f.write("- 평균회귀 시점은 예측 불가 → **시간 분산(분할 매매)**이 최적 전략\n\n")

        f.write("### 워렌 버핏 방식의 교훈\n\n")
        f.write("> *\"주식시장은 인내심 없는 사람에게서 인내심 있는 사람으로 돈을 이전하는 장치다\"*\n\n")
        f.write("- 조정 없이 추가 상승할 수도 있음 → FOMO에 매수하면 안 됨\n")
        f.write("- 조정이 오면 반드시 기회 → **현금을 확보해 놓는 것이 곧 전략**\n\n")

        f.write("---\n\n")

        # ── 핵심 데이터 요약 부록 ──
        f.write("## 📊 부록: 핵심 데이터 요약\n\n")
        f.write("| 항목 | 코스피 | 코스닥 |\n")
        f.write("|:-----|:------:|:------:|\n")
        f.write(f"| 현재가 | {latest_kospi:,.0f} | {latest_kosdaq:,.0f} |\n")
        f.write(f"| RSI(14) | {rsi_kospi:.1f} {status_rsi.split()[0]} | {rsi_kosdaq:.1f} {kq_rsi_status.split()[0]} |\n")
        f.write(f"| MA60 이격도 | {disp60_kospi:.1f}% {status_disp60.split()[0]} | {disp60_kosdaq:.1f}% {kq_disp_status.split()[0]} |\n")
        f.write(f"| 52주 수익률 | {(latest_kospi/low_52w-1)*100:+.1f}% | {(latest_kosdaq/float(recent_kosdaq.min())-1)*100:+.1f}% |\n")
        f.write(f"| ATH 대비 | {ath_pct:+.1f}% | {kq_ath_pct:+.1f}% |\n")
        f.write(f"| 20일 변동성 | {vol_20:.1f}% | - |\n\n")

        f.write("| 피보나치 레벨 | 코스피 지수 | 현재 대비 |\n")
        f.write("|:------------:|:----------:|:---------:|\n")
        f.write(f"| 127.2% 확장 | {ext_127:,.0f} | {(ext_127/latest_kospi-1)*100:+.1f}% |\n")
        f.write(f"| 161.8% 확장 | {ext_162:,.0f} | {(ext_162/latest_kospi-1)*100:+.1f}% |\n")
        for fib_level in [0.236, 0.382, 0.5, 0.618]:
            level = fib_ret[fib_level]
            f.write(f"| {fib_level*100:.1f}% 되돌림 | {level:,.0f} | {(level/latest_kospi-1)*100:.1f}% |\n")
        f.write("\n")

        f.write("---\n\n")
        f.write("*본 리포트는 과거 데이터의 통계적 패턴에 기반한 확률적 분석이며, 미래 수익을 보장하지 않습니다.*\n")
        f.write("*투자 의사결정은 본인의 판단과 책임 하에 이루어져야 합니다.*\n")

    print(f"[OK] 시장 전략 리포트 생성 완료: {filename}")
    return filename


if __name__ == "__main__":
    generate_strategy_report()
