"""
포지션 분석 + 시장 국면 판단 자동 리포트 생성기
- 코스피 DB에서 기술적 지표 계산
- 사용자 포지션(순자산, 평가금) 입력 받아 분석
- 두 가지 리포트 자동 생성:
  1) 코스피_시장국면판단_베어vs불_{날짜}.md
  2) 투자전략_시나리오분석_{날짜}.md
"""

import os
import sys
import sqlite3
import argparse
import pandas as pd
import numpy as np
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'data', 'market_data.db')
OUTPUT_DIR = os.path.join(BASE_DIR, 'results', 'analysis')


# ──────────────────────────────────────────────
# 1. 데이터 로드 + 기술적 지표 계산
# ──────────────────────────────────────────────

def load_kospi():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM index_data WHERE index_name='KS11' ORDER BY date", conn)
    conn.close()
    df['date'] = pd.to_datetime(df['date'])
    df.set_index('date', inplace=True)
    df.columns = [c.lower() for c in df.columns]
    return df


def calc_indicators(df):
    for p in [5, 10, 20, 60, 120, 200]:
        df[f'MA{p}'] = df['close'].rolling(window=p).mean()

    # RSI
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df['RSI'] = 100 - (100 / (1 + rs))

    # MACD
    exp12 = df['close'].ewm(span=12, adjust=False).mean()
    exp26 = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp12 - exp26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

    # Bollinger Bands
    df['BB_mid'] = df['close'].rolling(20).mean()
    bb_std = df['close'].rolling(20).std()
    df['BB_upper'] = df['BB_mid'] + 2 * bb_std
    df['BB_lower'] = df['BB_mid'] - 2 * bb_std

    # ADX / DMI (Wilder method: mutual exclusivity)
    period = 14
    high, low, close = df['high'], df['low'], df['close']
    plus_dm = high.diff()
    minus_dm = -low.diff()
    mask_plus = (plus_dm > minus_dm) & (plus_dm > 0)
    mask_minus = (minus_dm > plus_dm) & (minus_dm > 0)
    plus_dm = plus_dm.where(mask_plus, 0.0)
    minus_dm = minus_dm.where(mask_minus, 0.0)
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(period).mean().replace(0, np.nan)
    df['+DI'] = 100 * plus_dm.rolling(period).mean() / atr
    df['-DI'] = 100 * minus_dm.rolling(period).mean() / atr
    di_sum = (df['+DI'] + df['-DI']).replace(0, np.nan)
    dx = 100 * (df['+DI'] - df['-DI']).abs() / di_sum
    df['ADX'] = dx.rolling(period).mean()

    # 변동성
    daily_ret = df['close'].pct_change()
    df['vol_20d'] = daily_ret.rolling(20).std() * np.sqrt(252) * 100
    df['vol_60d'] = daily_ret.rolling(60).std() * np.sqrt(252) * 100

    return df


# ──────────────────────────────────────────────
# 2. 분석 로직
# ──────────────────────────────────────────────

def analyze(df, kospi_close, stock_value, net_asset):
    """모든 분석값을 딕셔너리로 반환"""
    loan = stock_value - net_asset
    collateral = stock_value / loan * 100 if loan > 0 else 9999
    clearing_kospi = loan * 2 / stock_value * kospi_close if loan > 0 else 0

    cur = df.iloc[-1]

    # 이동평균선
    mas = {}
    for p in [5, 10, 20, 60, 120, 200]:
        v = cur[f'MA{p}']
        diff_pct = (kospi_close / v - 1) * 100 if not pd.isna(v) else 0
        above = kospi_close > v
        mas[p] = {'val': v, 'diff': diff_pct, 'above': above}

    # MA200 기울기
    ma200_now = df['MA200'].iloc[-1]
    ma200_20d = df['MA200'].iloc[-21] if len(df) > 21 else ma200_now
    ma200_slope = (ma200_now - ma200_20d) / ma200_20d * 100

    # 52주 고점
    high_52w = df['high'].iloc[-252:].max()
    high_52w_date = df['high'].iloc[-252:].idxmax()
    drawdown_52w = (kospi_close / high_52w - 1) * 100

    # 최근 고점/저점 (2025-12 이후)
    recent_peak = df.loc['2025-12-01':, 'high'].max()
    recent_peak_date = df.loc['2025-12-01':, 'high'].idxmax()
    recent_trough = df.loc[recent_peak_date:, 'low'].min()
    recent_trough_date = df.loc[recent_peak_date:, 'low'].idxmin()
    decline_pct = (recent_trough / recent_peak - 1) * 100
    bounce_pct = (kospi_close / recent_trough - 1) * 100
    retracement = bounce_pct / abs(decline_pct) * 100 if decline_pct != 0 else 0

    # 직전 주요 고점 (반등 고점) - 최근 20거래일 내 고점
    recent_20 = df.tail(20)
    prev_high = recent_20['high'].max()

    # 수익률
    returns = {}
    for name, days in {'5d': 5, '10d': 10, '20d': 20, '60d': 60, '120d': 120}.items():
        if len(df) > days:
            returns[name] = (df['close'].iloc[-1] / df['close'].iloc[-(days + 1)] - 1) * 100

    # 가격 패턴
    r20 = df.tail(20)
    h1 = r20.iloc[:10]['high'].max()
    h2 = r20.iloc[10:]['high'].max()
    l1 = r20.iloc[:10]['low'].min()
    l2 = r20.iloc[10:]['low'].min()
    pattern_hh = h2 > h1  # Higher High
    pattern_hl = l2 > l1  # Higher Low

    # 불마켓 체크리스트
    bull_checks = {
        'ma20': kospi_close > cur['MA20'] if not pd.isna(cur['MA20']) else False,
        'prev_high': kospi_close > prev_high * 0.998,  # 약간의 여유
        'macd_hist': cur['MACD_Hist'] > 0 if not pd.isna(cur['MACD_Hist']) else False,
        'dmi': cur['+DI'] > cur['-DI'] if not pd.isna(cur['+DI']) else False,
        'vol': cur['vol_20d'] < 35 if not pd.isna(cur['vol_20d']) else False,
        'rsi': cur['RSI'] > 50 if not pd.isna(cur['RSI']) else False,
    }
    bull_count = sum(bull_checks.values())

    # 베어마켓 체크리스트
    bear_checks = {
        'below_ma200': kospi_close < cur['MA200'] if not pd.isna(cur['MA200']) else False,
        'ma200_slope': ma200_slope < 0,
        'new_low': kospi_close < recent_trough,
        'adx_bear': (cur['ADX'] > 30 and cur['-DI'] > cur['+DI']) if not (pd.isna(cur['ADX']) or pd.isna(cur['-DI'])) else False,
        'ret60_neg': returns.get('60d', 0) < 0,
    }
    bear_count = sum(bear_checks.values())

    # 불마켓 확률 계산 (기본 50 → 가감점)
    bull_score = 50
    ma200_dist = mas[200]['diff']  # 현재가 - MA200 %

    # ── 장기 구조 (최대 +25) ──
    if mas[200]['above']:
        bull_score += 10
        if ma200_dist > 30:
            bull_score += 5   # 30% 이상 상회 = 강한 불구조
        elif ma200_dist > 15:
            bull_score += 3
    else:
        bull_score -= 10
    if ma200_slope > 5:
        bull_score += 10
    elif ma200_slope > 2:
        bull_score += 7
    elif ma200_slope > 0:
        bull_score += 3
    else:
        bull_score -= 5

    # ── 중기 수익률 (±10) ──
    ret120 = returns.get('120d', 0)
    if ret120 > 30:
        bull_score += 10
    elif ret120 > 10:
        bull_score += 5
    elif ret120 > 0:
        bull_score += 2
    elif ret120 > -10:
        bull_score -= 3
    else:
        bull_score -= 7

    # ── 조정 성격 판단 (±8) ──
    if abs(decline_pct) < 25:  # -25% 미만 = 정상 조정 범위
        bull_score += 5
    else:
        bull_score -= 5
    if retracement > 50:
        bull_score += 3
    elif retracement > 30:
        bull_score += 1

    # ── 단기 시그널 (±10) ──
    if bull_checks['ma20']:
        bull_score += 5
    else:
        bull_score -= 2  # MA20 하회는 약한 감점 (단기)
    if bull_checks['prev_high']:
        bull_score += 5
    if not pd.isna(cur['MACD_Hist']) and cur['MACD_Hist'] > 0:
        bull_score += 3
    elif not pd.isna(cur['MACD_Hist']) and cur['MACD_Hist'] < 0:
        bull_score -= 2

    # ── RSI (±3) ──
    rsi_val = cur['RSI'] if not pd.isna(cur['RSI']) else 50
    if rsi_val > 60:
        bull_score += 3
    elif rsi_val > 50:
        bull_score += 1
    elif rsi_val > 40:
        bull_score -= 1
    else:
        bull_score -= 3

    # ── DMI (±3) ──
    if not pd.isna(cur['+DI']) and not pd.isna(cur['-DI']):
        if cur['+DI'] > cur['-DI']:
            bull_score += 3
        else:
            bull_score -= 2

    # ── 변동성 (±3) ──
    vol = cur['vol_20d'] if not pd.isna(cur['vol_20d']) else 20
    if vol < 25:
        bull_score += 3
    elif vol < 35:
        bull_score += 0
    elif vol < 50:
        bull_score -= 2
    else:
        bull_score -= 3  # 크래시급 변동성이지만 구조 우세 시 완만 감점
    if not pattern_hh and not pattern_hl:
        bull_score -= 5

    bull_prob = max(40, min(95, bull_score))
    bear_prob = 100 - bull_prob

    # 25억 도달 코스피
    target_25 = (25.0 + loan) / stock_value * kospi_close if stock_value > 0 else 0
    target_20 = (20.0 + loan) / stock_value * kospi_close if stock_value > 0 else 0

    # BB 위치
    bb_range = cur['BB_upper'] - cur['BB_lower'] if not pd.isna(cur['BB_upper']) else 1
    bb_pos = (kospi_close - cur['BB_lower']) / bb_range * 100 if bb_range > 0 else 50

    return {
        'kospi': kospi_close,
        'stock_value': stock_value,
        'net_asset': net_asset,
        'loan': loan,
        'collateral': collateral,
        'clearing_kospi': clearing_kospi,
        'mas': mas,
        'ma200_slope': ma200_slope,
        'high_52w': high_52w,
        'high_52w_date': high_52w_date,
        'drawdown_52w': drawdown_52w,
        'recent_peak': recent_peak,
        'recent_peak_date': recent_peak_date,
        'recent_trough': recent_trough,
        'recent_trough_date': recent_trough_date,
        'decline_pct': decline_pct,
        'bounce_pct': bounce_pct,
        'retracement': retracement,
        'prev_high': prev_high,
        'rsi': cur['RSI'],
        'macd': cur['MACD'],
        'macd_signal': cur['MACD_Signal'],
        'macd_hist': cur['MACD_Hist'],
        'adx': cur['ADX'],
        'plus_di': cur['+DI'],
        'minus_di': cur['-DI'],
        'vol_20d': cur['vol_20d'],
        'vol_60d': cur['vol_60d'],
        'bb_upper': cur['BB_upper'],
        'bb_mid': cur['BB_mid'],
        'bb_lower': cur['BB_lower'],
        'bb_pos': bb_pos,
        'returns': returns,
        'pattern_hh': pattern_hh,
        'pattern_hl': pattern_hl,
        'h1': h1, 'h2': h2, 'l1': l1, 'l2': l2,
        'bull_checks': bull_checks,
        'bear_checks': bear_checks,
        'bull_count': bull_count,
        'bear_count': bear_count,
        'bull_prob': bull_prob,
        'bear_prob': bear_prob,
        'target_25': target_25,
        'target_20': target_20,
    }


# ──────────────────────────────────────────────
# 3. 리포트 1: 시장 국면 판단
# ──────────────────────────────────────────────

def generate_market_report(a, date_str):
    k = a['kospi']
    ma20_status = "✅ 돌파" if a['bull_checks']['ma20'] else "❌ 하회"
    prev_h_status = "✅ 돌파" if a['bull_checks']['prev_high'] else "❌ 하회"

    def chk(v): return "✅" if v else "❌"

    # 되돌림 구간 판정
    if a['retracement'] >= 62:
        retrace_label = "V자 반등 (거의 확실)"
    elif a['retracement'] >= 50:
        retrace_label = "건강한 반등"
    elif a['retracement'] >= 30:
        retrace_label = "보통 반등 (추가 확인 필요)"
    else:
        retrace_label = "데드캣 바운스 가능성"

    # 판단 텍스트
    if a['bull_prob'] >= 80:
        verdict = "불마켓 조정 후 회복 진행 중 (강한 확신)"
    elif a['bull_prob'] >= 70:
        verdict = "불마켓 조정 후 회복 진행 중"
    elif a['bull_prob'] >= 60:
        verdict = "불마켓 조정 가능성이 높으나 불확실"
    elif a['bull_prob'] >= 50:
        verdict = "방향 미결정 — No Man's Land"
    else:
        verdict = "베어마켓 전환 경계 필요"

    report = f"""# 📊 코스피 시장 국면 판단: 베어마켓 랠리 vs 불마켓 조정

> **기준일**: {date_str} 장마감 | **코스피**: {k:,.1f}pt
> **포지션**: 순자산 {a['net_asset']:.1f}억 / 투자금 {a['stock_value']:.2f}억 / 대출 {a['loan']:.2f}억 / 담보 {a['collateral']:.0f}%
> **자동 생성**: position_report.py

---

## ★ 결론

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│  판단: {verdict:<55s}│
│                                                                  │
│  ★ "불마켓 조정" {a['bull_prob']}% vs "베어마켓 전환" {a['bear_prob']}%{' ' * (26 - len(str(a['bull_prob'])) - len(str(a['bear_prob'])))}│
│                                                                  │
│  핵심 지표:                                                       │
│    · MA20({a['mas'][20]['val']:,.0f}) {ma20_status}{' ' * max(0, 50 - len(ma20_status) - len(f"MA20({a['mas'][20]['val']:,.0f})"))}│
│    · 직전고점({a['prev_high']:,.0f}) {prev_h_status}{' ' * max(0, 46 - len(prev_h_status) - len(f"직전고점({a['prev_high']:,.0f})"))}│
│    · 되돌림 {a['retracement']:.0f}% — {retrace_label}{' ' * max(0, 48 - len(retrace_label) - len(f"되돌림 {a['retracement']:.0f}%"))}│
│    · 200일선 +{a['mas'][200]['diff']:.0f}%, 기울기 {a['ma200_slope']:+.1f}%{' ' * max(0, 39 - len(f"200일선 +{a['mas'][200]['diff']:.0f}%, 기울기 {a['ma200_slope']:+.1f}%"))}│
│    · 불마켓 체크리스트 {a['bull_count']}/6 충족{' ' * max(0, 40 - len(f"불마켓 체크리스트 {a['bull_count']}/6 충족"))}│
│                                                                  │
│  포지션: 담보 {a['collateral']:.0f}%로 {'극히 안전' if a['collateral'] > 500 else '안전' if a['collateral'] > 300 else '주의'}{' ' * max(0, 42 - len(f"담보 {a['collateral']:.0f}%로 {'극히 안전' if a['collateral'] > 500 else '안전' if a['collateral'] > 300 else '주의'}"))}│
│  → 청산선 코스피 {a['clearing_kospi']:,.0f}pt ({(a['clearing_kospi']/k-1)*100:+.0f}%){' ' * max(0, 39 - len(f"청산선 코스피 {a['clearing_kospi']:,.0f}pt ({(a['clearing_kospi']/k-1)*100:+.0f}%)"))}│
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 1. 시장 좌표

| 항목 | 값 | 비고 |
|:---|---:|:---|
| 현재 종가 | **{k:,.1f}pt** | |
| 52주 최고점 | {a['high_52w']:,.1f}pt | {a['high_52w_date'].strftime('%Y-%m-%d')} |
| 고점 대비 | **{a['drawdown_52w']:+.1f}%** | {'정상 조정' if a['drawdown_52w'] > -20 else '약세장 경계'} |
| 최근 저점 | {a['recent_trough']:,.1f}pt | {a['recent_trough_date'].strftime('%Y-%m-%d')} |
| 고점→저점 최대하락 | {a['decline_pct']:.1f}% | |
| 저점→현재 반등 | **+{a['bounce_pct']:.1f}%** | 하락폭의 **{a['retracement']:.0f}%** 되돌림 |
| MA200 | {a['mas'][200]['val']:,.0f}pt | 현재가 **{a['mas'][200]['diff']:+.1f}%** 상회 |

---

## 2. 이동평균선 구조

| 이동평균 | 값 | 현재가 대비 | 해석 |
|:---|---:|---:|:---|
| MA5 | {a['mas'][5]['val']:,.0f} | {'▲' if a['mas'][5]['above'] else '▼'} {a['mas'][5]['diff']:+.1f}% | |
| MA10 | {a['mas'][10]['val']:,.0f} | {'▲' if a['mas'][10]['above'] else '▼'} {a['mas'][10]['diff']:+.1f}% | |
| **MA20** | **{a['mas'][20]['val']:,.0f}** | **{'▲' if a['mas'][20]['above'] else '▼'} {a['mas'][20]['diff']:+.1f}%** | **{ma20_status}** |
| MA60 | {a['mas'][60]['val']:,.0f} | {'▲' if a['mas'][60]['above'] else '▼'} {a['mas'][60]['diff']:+.1f}% | |
| MA120 | {a['mas'][120]['val']:,.0f} | {'▲' if a['mas'][120]['above'] else '▼'} {a['mas'][120]['diff']:+.1f}% | |
| **MA200** | **{a['mas'][200]['val']:,.0f}** | **▲ {a['mas'][200]['diff']:+.1f}%** | **기울기 {a['ma200_slope']:+.2f}%** |

---

## 3. 기술적 지표

| 지표 | 값 | 해석 |
|:---|---:|:---|
| RSI(14) | **{a['rsi']:.1f}** | {'상승 모멘텀' if a['rsi'] > 50 else '약세 구간'} |
| MACD | {a['macd']:.2f} | {'0선 위' if a['macd'] > 0 else '0선 아래'} |
| MACD Signal | {a['macd_signal']:.2f} | |
| MACD Hist | **{a['macd_hist']:.2f}** | {'✅ 양전환' if a['macd_hist'] > 0 else '❌ 음영역'} |
| ADX | {a['adx']:.1f} | {'강한 추세' if a['adx'] > 25 else '추세 약함'} |
| +DI / -DI | {a['plus_di']:.0f} / {a['minus_di']:.0f} | {'상승 우위' if a['plus_di'] > a['minus_di'] else '하락 우위'} |
| 20일 변동성 | {a['vol_20d']:.1f}% | {'정상' if a['vol_20d'] < 25 else '경계' if a['vol_20d'] < 40 else '위기 수준'} |
| BB 위치 | {a['bb_pos']:.0f}% | |

---

## 4. 수익률

| 기간 | 수익률 |
|:---|---:|
| 5일 | {a['returns'].get('5d', 0):+.2f}% |
| 10일 | {a['returns'].get('10d', 0):+.2f}% |
| 20일 | {a['returns'].get('20d', 0):+.2f}% |
| 60일 | {a['returns'].get('60d', 0):+.2f}% |
| 120일 | {a['returns'].get('120d', 0):+.2f}% |

---

## 5. 가격 패턴 (최근 20거래일)

```
전반(10일) 고점: {a['h1']:,.0f}  /  후반(10일) 고점: {a['h2']:,.0f}  → {'Higher High ✅' if a['pattern_hh'] else 'Lower High ⚠️'}
전반(10일) 저점: {a['l1']:,.0f}  /  후반(10일) 저점: {a['l2']:,.0f}  → {'Higher Low ✅' if a['pattern_hl'] else 'Lower Low ⚠️'}
```

---

## 6. 전환 시그널 체크리스트

### 🟢 불마켓 확인 조건 (3개 이상 충족 시)

| # | 조건 | 기준 | 현재 | 충족 |
|:---:|:---|:---|:---|:---:|
| 1 | 코스피 > MA20 | > {a['mas'][20]['val']:,.0f} | {k:,.0f} | {chk(a['bull_checks']['ma20'])} |
| 2 | 직전 High 돌파 | > {a['prev_high']:,.0f} | {k:,.0f} | {chk(a['bull_checks']['prev_high'])} |
| 3 | MACD Hist > 0 | > 0 | {a['macd_hist']:.1f} | {chk(a['bull_checks']['macd_hist'])} |
| 4 | +DI > -DI | +DI > -DI | {a['plus_di']:.0f} vs {a['minus_di']:.0f} | {chk(a['bull_checks']['dmi'])} |
| 5 | 변동성 < 35% | < 35% | {a['vol_20d']:.0f}% | {chk(a['bull_checks']['vol'])} |
| 6 | RSI > 50 | > 50 | {a['rsi']:.0f} | {chk(a['bull_checks']['rsi'])} |

> **{a['bull_count']}/6 충족.**{' 불마켓 복귀 확인!' if a['bull_count'] >= 3 else f" 3개 달성까지 {3 - a['bull_count']}개 남음."}

### 🔴 베어마켓 확인 조건

| # | 조건 | 현재 | 충족 |
|:---:|:---|:---|:---:|
| 1 | < MA200({a['mas'][200]['val']:,.0f}) | {k:,.0f} | {chk(a['bear_checks']['below_ma200'])} |
| 2 | MA200 기울기 < 0 | {a['ma200_slope']:+.2f}% | {chk(a['bear_checks']['ma200_slope'])} |
| 3 | 저점 갱신 < {a['recent_trough']:,.0f} | {k:,.0f} | {chk(a['bear_checks']['new_low'])} |
| 4 | ADX > 30 + -DI 우위 | ADX={a['adx']:.0f} | {chk(a['bear_checks']['adx_bear'])} |
| 5 | 60일 수익률 < 0 | {a['returns'].get('60d', 0):+.1f}% | {chk(a['bear_checks']['ret60_neg'])} |

> **{a['bear_count']}/5 충족.**

---

## 7. 포지션 안전 진단

| 항목 | 값 | 판단 |
|:---|---:|:---|
| 순자산 | **{a['net_asset']:.1f}억** | |
| 대출 | **{a['loan']:.2f}억** | |
| 담보비율 | **{a['collateral']:.0f}%** | {'🟢 매우 안전' if a['collateral'] > 500 else '🟡 안전' if a['collateral'] > 300 else '🔴 주의'} |
| 청산선(200%) | **코스피 {a['clearing_kospi']:,.0f}pt** | {(a['clearing_kospi']/k-1)*100:+.0f}% |
| 25억 도달 | **코스피 {a['target_25']:,.0f}pt** | {(a['target_25']/k-1)*100:+.1f}% |
| 20억 하회 | 코스피 {a['target_20']:,.0f}pt | {(a['target_20']/k-1)*100:+.1f}% |

---

## 8. 시나리오별 순자산

| 시나리오 | 코스피 | 순자산 | 담보비율 |
|:---|:---:|:---:|:---:|"""

    targets = [
        (a['high_52w'], "전고점"),
        (6000, ""),
        (a['target_25'], "★ 25억"),
        (k * 1.05, "+5%"),
        (k, "◀ 현재"),
        (k * 0.95, "-5%"),
        (a['mas'][20]['val'], "MA20"),
        (a['recent_trough'], "직전 저점"),
        (k * 0.85, "-15%"),
        (a['mas'][200]['val'], "MA200"),
    ]
    # 중복 제거 및 정렬
    seen = set()
    unique_targets = []
    for val, label in targets:
        rounded = round(val, 0)
        if rounded not in seen:
            seen.add(rounded)
            unique_targets.append((val, label))
    unique_targets.sort(key=lambda x: -x[0])

    for t, label in unique_targets:
        ratio = t / k
        ns = a['stock_value'] * ratio - a['loan']
        nc = a['stock_value'] * ratio / a['loan'] * 100 if a['loan'] > 0 else 9999
        pct = (ratio - 1) * 100
        lbl = f" {label}" if label else ""
        report += f"\n| {lbl} | {t:,.0f} ({pct:+.1f}%) | **{ns:.1f}억** | {nc:.0f}% |"

    report += f"""

---

## 9. 실행 지침

```
보유 전략:
  {'✅ MA20 위에 있는 한 보유 유지' if a['bull_checks']['ma20'] else '⚠️ MA20 하회 — 단기 약세, 관망 또는 소폭 방어 검토'}
  ✅ 담보 {a['collateral']:.0f}%로 {'극히 안전' if a['collateral'] > 500 else '안전'} — 서두를 이유 없음

매도 검토:
  📍 {a['target_25']:,.0f}pt → 순자산 25억 달성
  📍 {a['recent_peak']:,.0f}pt (전고점) → 단계적 대출 축소

관찰 포인트:
  📍 MA20({a['mas'][20]['val']:,.0f}) 지지 여부
  📍 MACD Hist 양전환 여부 (현재 {a['macd_hist']:.1f})
  📍 RSI 50 돌파 여부 (현재 {a['rsi']:.0f})

하면 안 되는 것:
  ❌ 패닉 매도 (장기 추세 살아있고 담보 {a['collateral']:.0f}%)
  ❌ 레버리지 추가 (변동성 {a['vol_20d']:.0f}% {'아직 높음' if a['vol_20d'] > 30 else ''})
```

---

> ⚠️ **면책**: 본 분석은 과거 데이터와 기술적 지표에 기반한 자동 생성 참고 자료입니다.
> 투자 판단의 최종 책임은 투자자 본인에게 있습니다.
"""
    return report


# ──────────────────────────────────────────────
# 4. 리포트 2: 투자 전략 시나리오
# ──────────────────────────────────────────────

def generate_strategy_report(a, date_str):
    k = a['kospi']
    loan = a['loan']
    sv = a['stock_value']
    na = a['net_asset']

    report = f"""# 투자 전략 — {date_str} 장마감

> **기준**: {date_str} 종가 | 코스피 {k:,.1f}pt | 평가 {sv:.2f}억, 순자산 {na:.1f}억, 대출 {loan:.2f}억
> **자동 생성**: position_report.py

---

## 현재 포지션

| 항목 | 값 |
|:---|---:|
| 주식 평가금액 | **{sv:.2f}억** |
| 담보 대출 | **{loan:.2f}억** |
| 순자산 | **{na:.1f}억** |
| 담보비율 | **{a['collateral']:.0f}%** |
| 코스피 | **{k:,.1f}pt** |
| 25억까지 | **{(a['target_25']/k-1)*100:+.1f}% ({a['target_25']:,.0f}pt)** |
| 청산선(200%) | **{a['clearing_kospi']:,.0f}pt ({(a['clearing_kospi']/k-1)*100:+.0f}%)** |

---

## TL;DR

**순자산 {na:.1f}억, 25억까지 코스피 {(a['target_25']/k-1)*100:+.1f}%({a['target_25']:,.0f}pt).** 담보 {a['collateral']:.0f}%로 {'극히 안전' if a['collateral'] > 500 else '안전'}.
시장 국면: 불마켓 {a['bull_prob']}% vs 베어마켓 {a['bear_prob']}%.
**{'보유 유지가 최선.' if a['bull_prob'] >= 60 else '관망 + 방향 확인 후 행동.'}**

---

## 목표 분석

### 핵심 마일스톤

| 목표 | 코스피 | 현재 대비 | 순자산 |
|:---|:---:|:---:|:---:|"""

    milestones = [
        (25.0, "25억"),
        (26.0, "26억"),
        (27.0, "27억"),
    ]
    for m_na, m_label in milestones:
        m_kospi = (m_na + loan) / sv * k if sv > 0 else 0
        m_pct = (m_kospi / k - 1) * 100
        report += f"\n| **{m_label}** | **{m_kospi:,.0f}** | **{m_pct:+.1f}%** | {m_na:.1f}억 |"

    # 전고점
    peak_kospi = a['high_52w']
    peak_na = sv * (peak_kospi / k) - loan
    peak_pct = (peak_kospi / k - 1) * 100
    report += f"\n| **전고점** | **{peak_kospi:,.0f}** | **{peak_pct:+.1f}%** | **{peak_na:.1f}억** |"

    report += f"""

---

## 지수별 순자산 시뮬레이션

| 코스피 | 등락률 | 평가금액 | 순자산 | 담보비율 | 비고 |
|:---:|---:|---:|---:|---:|:---|"""

    table_targets = [6500, peak_kospi, 6200, 6000, 5800, a['target_25'], k, 5400, 5200,
                     a['recent_trough'], 4800, 4500, 4000, a['clearing_kospi']]
    table_targets = sorted(set([round(t, 0) for t in table_targets]), reverse=True)

    for t in table_targets:
        ratio = t / k
        n_sv = sv * ratio
        n_na = n_sv - loan
        n_coll = n_sv / loan * 100 if loan > 0 else 9999
        pct = (ratio - 1) * 100
        note = ""
        if abs(t - k) < 5:
            note = "◀ 현재"
        elif abs(n_na - 25.0) < 0.3:
            note = "★ 25억"
        elif abs(t - peak_kospi) < 5:
            note = "전고점"
        elif abs(t - a['recent_trough']) < 5:
            note = "직전 저점"
        elif abs(t - a['clearing_kospi']) < 5:
            note = "청산선"
        report += f"\n| {t:,.0f} | {pct:+.1f}% | {n_sv:.1f}억 | **{n_na:.1f}억** | {n_coll:.0f}% | {note} |"

    report += f"""

---

## 리스크 관리

### 담보비율 안전 마진

| 상황 | 코스피 | 하락폭 | 담보비율 | 순자산 |
|:---|:---:|:---:|:---:|:---:|
| **현재** | **{k:,.0f}** | - | **{a['collateral']:.0f}%** | **{na:.1f}억** |"""

    risk_levels = [
        (k * 0.9, "-10%"),
        (k * 0.8, "-20%"),
        (k * 0.7, "-30%"),
    ]
    for rk, rlabel in risk_levels:
        r_sv = sv * (rk / k)
        r_na = r_sv - loan
        r_coll = r_sv / loan * 100 if loan > 0 else 9999
        report += f"\n| {rlabel} | {rk:,.0f} | {rlabel} | {r_coll:.0f}% | {r_na:.1f}억 |"

    report += f"\n| 청산 | **{a['clearing_kospi']:,.0f}** | **{(a['clearing_kospi']/k-1)*100:+.0f}%** | 200% | {loan:.1f}억 |"

    report += f"""

> **코스피 -30%까지 담보 {sv * 0.7 / loan * 100 if loan > 0 else 9999:.0f}%.** 강제청산과 거리가 멀다.

---

## 수익 기대값 (확률 가중)

| 시나리오 | 확률 | 코스피 | 순자산 | 손익 |
|:---|:---:|:---:|:---:|:---:|
| 전고점 회복 | 20% | {peak_kospi:,.0f} | {peak_na:.1f}억 | {peak_na - na:+.1f}억 |
| 강한 반등 | 30% | {k*1.07:,.0f} | {sv*1.07-loan:.1f}억 | {sv*1.07-loan-na:+.1f}억 |
| 보통 반등 | 25% | {k*1.03:,.0f} | {sv*1.03-loan:.1f}억 | {sv*1.03-loan-na:+.1f}억 |
| 횡보 | 15% | {k:,.0f} | {na:.1f}억 | 0 |
| 조정 | 7% | {k*0.93:,.0f} | {sv*0.93-loan:.1f}억 | {sv*0.93-loan-na:+.1f}억 |
| 하락 | 3% | {k*0.85:,.0f} | {sv*0.85-loan:.1f}억 | {sv*0.85-loan-na:+.1f}억 |"""

    # 가중 기대값
    exp_na = (0.20 * peak_na + 0.30 * (sv * 1.07 - loan) + 0.25 * (sv * 1.03 - loan)
              + 0.15 * na + 0.07 * (sv * 0.93 - loan) + 0.03 * (sv * 0.85 - loan))
    report += f"\n| **가중 기대값** | | | **~{exp_na:.1f}억** | **{exp_na - na:+.1f}억** |"

    report += f"""

---

## 한 줄 결론

**대출 {loan:.2f}억, 담보 {a['collateral']:.0f}%. 코스피 {(a['target_25']/k-1)*100:+.1f}%({a['target_25']:,.0f})면 25억.**
**{'보유가 최선. 추세 살아있으면 끌고 간다.' if a['bull_prob'] >= 60 else '관망 유지. 방향 확인 후 행동.'}**
**기대 순자산 ~{exp_na:.1f}억.**

---

*본 분석은 코스피 연동 가정. 개별 종목 비중/베타에 따라 실제 결과는 다를 수 있음.*
"""
    return report


# ──────────────────────────────────────────────
# 5. 메인
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='포지션 분석 리포트 자동 생성')
    parser.add_argument('--net', type=float, required=True, help='순자산 (억 단위, 예: 23.0)')
    parser.add_argument('--stock', type=float, required=True, help='주식 평가금액 (억 단위, 예: 27.85)')
    parser.add_argument('--date', type=str, default=None, help='기준일 (YYYYMMDD, 기본: 오늘)')
    args = parser.parse_args()

    if args.date:
        date_str = f"{args.date[:4]}-{args.date[4:6]}-{args.date[6:8]}"
        date_file = args.date
    else:
        today = datetime.now()
        date_str = today.strftime('%Y-%m-%d')
        date_file = today.strftime('%Y%m%d')

    print(f"=" * 60)
    print(f"  포지션 분석 리포트 생성기")
    print(f"  기준일: {date_str}")
    print(f"  순자산: {args.net}억 / 평가: {args.stock}억 / 대출: {args.stock - args.net:.2f}억")
    print(f"=" * 60)

    # 데이터 로드
    print("\n[1/4] 코스피 데이터 로드 중...")
    df = load_kospi()
    kospi_close = df.iloc[-1]['close']
    print(f"  DB 마지막: {df.index[-1].strftime('%Y-%m-%d')} | 종가: {kospi_close:,.1f}pt")

    # 지표 계산
    print("[2/4] 기술적 지표 계산 중...")
    df = calc_indicators(df)

    # 분석
    print("[3/4] 분석 수행 중...")
    a = analyze(df, kospi_close, args.stock, args.net)
    print(f"  불마켓 {a['bull_prob']}% vs 베어마켓 {a['bear_prob']}%")
    print(f"  체크리스트: 불 {a['bull_count']}/6, 베어 {a['bear_count']}/5")
    print(f"  담보비율: {a['collateral']:.0f}%")

    # 리포트 생성
    print("[4/4] 리포트 생성 중...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 리포트 1: 시장 국면 판단
    report1 = generate_market_report(a, date_str)
    file1 = os.path.join(OUTPUT_DIR, f"코스피_시장국면판단_베어vs불_{date_file}.md")
    with open(file1, 'w', encoding='utf-8') as f:
        f.write(report1)
    print(f"  ✅ {os.path.basename(file1)}")

    # 리포트 2: 투자 전략
    report2 = generate_strategy_report(a, date_str)
    file2 = os.path.join(OUTPUT_DIR, f"투자전략_시나리오분석_{date_file}.md")
    with open(file2, 'w', encoding='utf-8') as f:
        f.write(report2)
    print(f"  ✅ {os.path.basename(file2)}")

    print(f"\n{'=' * 60}")
    print(f"  완료! 생성된 파일:")
    print(f"  1) {file1}")
    print(f"  2) {file2}")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()
