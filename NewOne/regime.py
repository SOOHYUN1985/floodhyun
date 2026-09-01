"""
시장 국면(Regime) 분류 — 검증된 추세 판단 프레임워크 기반

단일 지표 하나로 판단하지 않고, 학계·실무에서 널리 검증된 4개의 독립 프레임워크를
합성하여 국면을 결정한다. 모든 입력은 backward Feature이므로 Look-ahead가 없다.

적용한 근거(프레임워크)
  ① 장기추세 필터 — Meb Faber, "A Quantitative Approach to Tactical Asset
     Allocation"(2007): 종가 대비 200일(≈10개월) 이동평균 위/아래 + MA200 기울기.
     가장 많이 인용되는 추세추종 자산배분 규칙.
  ② 추세 강도 — J. Welles Wilder, "New Concepts in Technical Trading Systems"(1978):
     ADX. '방향'이 아니라 '추세의 힘'을 재어, ADX<20 이면 방향이 어느 쪽이든 '횡보'로
     본다(상승장/횡보장/보합을 가르는 고전적 기준).
  ③ 강세/약세 사이클 — 시장 통용 '20% 룰': 최근 고점 대비 -20% 이하면 약세장(bear),
     최근 저점 대비 +20% 이상이면 강세장(bull)으로 규정.
  ④ 모멘텀 확인 — Jegadeesh & Titman(1993), Gary Antonacci "Dual Momentum"(2014):
     12개월(≈252일) 절대 모멘텀으로 추세 지속성을 교차 확인.

'하락후 반등'(bear-market rally / dead-cat bounce)의 정의
  Dow Theory의 1차 추세 원칙에 따라, 장기추세가 여전히 하락(종가<MA200, MA200 하락)
  이고 20% 룰상 약세장 낙폭에서 벗어나지 못했는데 단기 방향(+DI>-DI, 단기수익률>0)만
  상승으로 튄 경우다. 1차(하락) 추세는 '더 높은 고점'이 확인되기 전까지 유효하므로,
  이 반등을 상승장으로 오인하지 않는다.

반환 라벨:
  강한상승 / 상승 / 상승전환초기 / 횡보 / 하락전환초기 / 하락 / 강한하락
  + 하락후 반등 (약세장 내 되돌림 — 1차 하락추세 미해소)
추가 플래그: 과열 / 과매도침체
"""

import numpy as np
import pandas as pd

# ── 프레임워크 임계값 (근거 문헌의 관례값) ──
ADX_TREND = 25.0        # Wilder: >=25 추세, <20 무추세(횡보)
ADX_NOTREND = 20.0
ADX_STRONG = 40.0       # 매우 강한 추세
BEAR_DD = -20.0         # 20% 룰: 고점 대비 약세장 낙폭
BULL_RALLY = 20.0       # 20% 룰: 저점 대비 강세장 반등


def _trend_score(row) -> float:
    """장기추세 점수 (-100~+100). Faber(200MA) + 정배열 + 중기 이격/기울기."""
    s = 0.0
    # Faber: 종가의 200일선 상단/하단 위치 (핵심 축, 40점)
    disp200 = row.get('close', np.nan) / row.get('ma200', np.nan) * 100.0
    if np.isfinite(disp200):
        s += np.clip(disp200 - 100.0, -10, 10) / 10 * 40
    # 200일선 기울기 방향 (장기추세 진행 방향, 20점)
    s += np.clip(row.get('ma200_slope', 0.0), -4, 4) / 4 * 20
    # 정배열(MA5>20>60>120) (20점)
    s += (row.get('ma_align', 0) - 1.5) / 1.5 * 20
    # 중기 이격/기울기 (20점)
    s += np.clip(row.get('disp60', 100) - 100, -12, 12) / 12 * 12
    s += np.clip(row.get('ma20_slope', 0), -5, 5) / 5 * 8
    return float(np.clip(s, -100, 100))


def _momentum_score(row) -> float:
    """모멘텀 점수 (-100~+100). 12개월 절대모멘텀(Antonacci/JT) + RSI + MACD."""
    s = 0.0
    # 12개월(252일) 절대 모멘텀 — Dual Momentum 핵심 (40점)
    s += np.clip(row.get('ret252', 0.0), -30, 30) / 30 * 40
    # RSI (30점)
    s += np.clip(row.get('rsi14', 50) - 50, -25, 25) / 25 * 30
    # MACD 방향/히스토그램 (30점)
    s += (1 if row.get('macd_up', 0) else -1) * 15
    s += np.clip(row.get('macd_hist_n', 0), -1, 1) * 15
    return float(np.clip(s, -100, 100))


def _direction_up(row) -> bool:
    """Wilder DMI 방향: +DI가 -DI 이상이면 상승 방향."""
    return float(row.get('plus_di14', 0.0)) >= float(row.get('minus_di14', 0.0))


def classify_row(row) -> dict:
    trend = _trend_score(row)
    mom = _momentum_score(row)
    composite = 0.6 * trend + 0.4 * mom

    rsi = row.get('rsi14', 50.0)
    disp20 = row.get('disp20', 100.0)
    mdd120 = row.get('mdd120', 0.0)
    mdd252 = row.get('mdd252', 0.0)
    rally252 = row.get('rally252', 0.0)
    ret20 = row.get('ret20', 0.0)
    ret252 = row.get('ret252', 0.0)
    adx = float(row.get('adx14', 0.0) or 0.0)
    vol_pct = row.get('vol_pctile', 50.0)

    close = row.get('close', np.nan)
    ma200 = row.get('ma200', np.nan)
    above_ma200 = bool(np.isfinite(close) and np.isfinite(ma200) and close >= ma200)
    ma200_up = float(row.get('ma200_slope', 0.0) or 0.0) >= 0.0
    dir_up = _direction_up(row)

    # ── ② 추세 강도(ADX) : 무추세면 방향 무관하게 '횡보/보합' ──
    trending = adx >= ADX_TREND
    weak_trend = ADX_NOTREND <= adx < ADX_TREND

    # ── ①③④ 장기추세·강세/약세·모멘텀 종합 라벨 ──
    if adx > 0 and not trending:
        # ADX 낮음: 방향성 약함 → 횡보 계열
        if weak_trend and composite >= 12 and above_ma200:
            label = '상승전환초기'
        elif weak_trend and composite <= -12 and not above_ma200:
            label = '하락전환초기'
        else:
            label = '횡보'
    else:
        # 추세장(ADX 충분) 또는 데이터 초기: 방향+강도로 등급화
        if above_ma200 and dir_up:
            if adx >= ADX_STRONG or composite >= 55:
                label = '강한상승'
            elif composite >= 20:
                label = '상승'
            else:
                label = '상승전환초기'
        elif (not above_ma200) and (not dir_up):
            if adx >= ADX_STRONG or composite <= -55:
                label = '강한하락'
            elif composite <= -20:
                label = '하락'
            else:
                label = '하락전환초기'
        else:
            # 장기추세와 단기방향 불일치 → 전환 초기
            label = '상승전환초기' if dir_up else '하락전환초기'

    # ── '하락후 반등' 판정 (Dow 1차추세 + 20% 룰 + Faber 필터) ──
    long_downtrend = (not above_ma200) and (not ma200_up)
    bear_market = (mdd252 <= BEAR_DD) or (ret252 < 0 and mdd120 <= -15)
    not_confirmed_bull = rally252 < BULL_RALLY   # 저점 대비 +20% 강세전환 미확인
    short_up = (composite >= 5) or dir_up or (ret20 > 0)
    rebound = long_downtrend and bear_market and not_confirmed_bull and short_up
    if rebound and label in ('강한상승', '상승', '상승전환초기'):
        label = '하락후 반등'

    # 추세 강도 라벨 (표시용)
    if adx >= ADX_STRONG:
        strength = '강한추세'
    elif adx >= ADX_TREND:
        strength = '추세'
    elif adx >= ADX_NOTREND:
        strength = '추세형성'
    else:
        strength = '무추세(횡보)'

    overheated = bool(rsi >= 75 or disp20 >= 110)
    oversold = bool((rsi <= 30 or disp20 <= 92) and mdd120 <= -10)

    return {
        'regime': label,
        'trend_score': round(trend, 1),
        'momentum_score': round(mom, 1),
        'composite_score': round(composite, 1),
        'adx': round(adx, 1),
        'trend_strength': strength,
        'above_ma200': above_ma200,
        'dmi_up': bool(dir_up),
        'overheated': overheated,
        'oversold': oversold,
        'vol_regime': ('고변동' if vol_pct >= 70 else '저변동' if vol_pct <= 30 else '보통'),
    }


def classify_series(feat: pd.DataFrame) -> pd.DataFrame:
    """전체 기간에 대해 국면 라벨 시계열 생성 (국면별 통계용)."""
    recs = feat.apply(classify_row, axis=1, result_type='expand')
    return recs
