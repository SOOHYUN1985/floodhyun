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
OUTPUT_DIR = os.path.join(BASE_DIR, 'results', 'daily_position')


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

    # 최근 고점/저점 (최근 6개월)
    six_months_ago = df.index[-1] - pd.Timedelta(days=180)
    recent_peak = df.loc[six_months_ago:, 'high'].max()
    recent_peak_date = df.loc[six_months_ago:, 'high'].idxmax()
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

    # 동적 다음 마일스톤 (현재 순자산 기준 다음 5억 단위)
    next_milestone = float(int(net_asset / 5) * 5 + 5)
    if next_milestone <= net_asset:
        next_milestone += 5
    target_milestone = (next_milestone + loan) / stock_value * kospi_close if stock_value > 0 else 0

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
        'next_milestone': next_milestone,
        'target_milestone': target_milestone,
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
| {a['next_milestone']:.0f}억 도달 | **코스피 {a['target_milestone']:,.0f}pt** | {(a['target_milestone']/k-1)*100:+.1f}% |
| 20억 하회 | 코스피 {a['target_20']:,.0f}pt | {(a['target_20']/k-1)*100:+.1f}% |

---

## 8. 시나리오별 순자산

| 시나리오 | 코스피 | 순자산 | 담보비율 |
|:---|:---:|:---:|:---:|"""

    targets = [
        (a['high_52w'], "전고점"),
        (k * 1.10, "+10%"),
        (a['target_milestone'], f"★ {a['next_milestone']:.0f}억"),
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
  📍 {a['target_milestone']:,.0f}pt → 순자산 {a['next_milestone']:.0f}억 달성
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
| 다음 목표({a['next_milestone']:.0f}억) | **{(a['target_milestone']/k-1)*100:+.1f}% ({a['target_milestone']:,.0f}pt)** |
| 청산선(200%) | **{a['clearing_kospi']:,.0f}pt ({(a['clearing_kospi']/k-1)*100:+.0f}%)** |

---

## TL;DR

**순자산 {na:.1f}억, {a['next_milestone']:.0f}억까지 코스피 {(a['target_milestone']/k-1)*100:+.1f}%({a['target_milestone']:,.0f}pt).** 담보 {a['collateral']:.0f}%로 {'극히 안전' if a['collateral'] > 500 else '안전'}.
시장 국면: 불마켓 {a['bull_prob']}% vs 베어마켓 {a['bear_prob']}%.
**{'보유 유지가 최선.' if a['bull_prob'] >= 60 else '관망 + 방향 확인 후 행동.'}**

---

## 목표 분석

### 핵심 마일스톤

| 목표 | 코스피 | 현재 대비 | 순자산 |
|:---|:---:|:---:|:---:|"""

    # 마일스톤 동적 산출 (현재 순자산 기준 +5억 단위)
    base_milestone = int(na / 5) * 5 + 5  # 다음 5억 단위
    milestones = [
        (float(base_milestone), f"{base_milestone:.0f}억"),
        (float(base_milestone + 5), f"{base_milestone + 5:.0f}억"),
        (float(base_milestone + 10), f"{base_milestone + 10:.0f}억"),
    ]
    # 만약 현재 순자산이 이미 마일스톤 이상이면 위로 올림
    milestones = [(m, l) for m, l in milestones if m > na]
    if not milestones:
        milestones = [(na + 5, f"{na + 5:.0f}억"), (na + 10, f"{na + 10:.0f}억")]
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

    table_targets = [peak_kospi, k * 1.20, k * 1.10, k * 1.05, a['target_milestone'],
                     k, k * 0.95, k * 0.90, k * 0.85, k * 0.80,
                     a['recent_trough'], k * 0.70, a['clearing_kospi']]
    table_targets = sorted(set([round(t, 0) for t in table_targets if t > 0]), reverse=True)

    for t in table_targets:
        ratio = t / k
        n_sv = sv * ratio
        n_na = n_sv - loan
        n_coll = n_sv / loan * 100 if loan > 0 else 9999
        pct = (ratio - 1) * 100
        note = ""
        if abs(t - k) < 5:
            note = "◀ 현재"
        elif abs(n_na - a['next_milestone']) < 0.3:
            note = f"★ {a['next_milestone']:.0f}억"
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

"""

    # 시나리오 확률 (시장 국면 점수 기반 동적 산출)
    bp = a['bull_prob'] / 100  # 0~1
    scenarios = [
        ('전고점 회복', peak_kospi, 0.15 * bp + 0.05),
        ('강한 상승 (+10%)', k * 1.10, 0.25 * bp + 0.05),
        ('완만 상승 (+5%)', k * 1.05, 0.20),
        ('횡보', k, 0.15),
        ('조정 (-5%)', k * 0.95, 0.20 * (1 - bp) + 0.05),
        ('하락 (-15%)', k * 0.85, 0.15 * (1 - bp) + 0.02),
    ]
    total_prob = sum(p for _, _, p in scenarios)
    scenarios = [(lbl, kp, p / total_prob) for lbl, kp, p in scenarios]

    report += f"""## 수익 기대값 (시장 국면 {a['bull_prob']}% 불 기반)

| 시나리오 | 확률 | 코스피 | 순자산 | 손익 |
|:---|:---:|:---:|:---:|:---:|"""

    exp_na = 0
    for lbl, kp, prob in scenarios:
        s_na = sv * (kp / k) - loan
        report += f"\n| {lbl} | {prob*100:.0f}% | {kp:,.0f} | {s_na:.1f}억 | {s_na - na:+.1f}억 |"
        exp_na += prob * s_na
    report += f"\n| **가중 기대값** | | | **~{exp_na:.1f}억** | **{exp_na - na:+.1f}억** |"

    report += f"""

---

## 한 줄 결론

**대출 {loan:.2f}억, 담보 {a['collateral']:.0f}%. 코스피 {(a['target_milestone']/k-1)*100:+.1f}%({a['target_milestone']:,.0f})면 {a['next_milestone']:.0f}억.**
**{'보유가 최선. 추세 살아있으면 끌고 간다.' if a['bull_prob'] >= 60 else '관망 유지. 방향 확인 후 행동.'}**
**기대 순자산 ~{exp_na:.1f}억.**

---

*본 분석은 코스피 연동 가정. 개별 종목 비중/베타에 따라 실제 결과는 다를 수 있음.*
"""
    return report


# ──────────────────────────────────────────────
# 5. 리포트 3: 시나리오 대응 전략
# ──────────────────────────────────────────────

def _compute_probability_data(df, kospi_close):
    """과거 유사 상황 기반 60일 확률 데이터 산출"""
    close = df['close']
    ma60 = close.rolling(60).mean()
    disparity_60 = (close / ma60) * 100
    rally_60d = close.pct_change(60) * 100

    cur_disparity = disparity_60.iloc[-1]
    cur_rally = rally_60d.iloc[-1]

    if pd.isna(cur_disparity) or pd.isna(cur_rally):
        return None

    # 이후 60일 최대상승/최대낙폭
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

    # 유사 상황 필터링
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

    avg_rally = similar['future_rally_60d'].mean()
    med_rally = similar['future_rally_60d'].median()
    avg_mdd = similar['future_mdd_60d'].mean()
    med_mdd = similar['future_mdd_60d'].median()

    prob_up_5 = (similar['future_rally_60d'] >= 5).sum() / len(similar) * 100
    prob_up_10 = (similar['future_rally_60d'] >= 10).sum() / len(similar) * 100
    prob_up_15 = (similar['future_rally_60d'] >= 15).sum() / len(similar) * 100
    prob_up_20 = (similar['future_rally_60d'] >= 20).sum() / len(similar) * 100

    prob_dn_5 = (similar['future_mdd_60d'] <= -5).sum() / len(similar) * 100
    prob_dn_10 = (similar['future_mdd_60d'] <= -10).sum() / len(similar) * 100
    prob_dn_15 = (similar['future_mdd_60d'] <= -15).sum() / len(similar) * 100
    prob_dn_20 = (similar['future_mdd_60d'] <= -20).sum() / len(similar) * 100

    up_ev = avg_rally * (prob_up_5 / 100)
    down_ev = abs(avg_mdd) * (prob_dn_5 / 100)
    risk_reward = up_ev / down_ev if down_ev > 0 else 10.0

    return {
        'n_similar': len(similar),
        'cur_disparity': cur_disparity,
        'cur_rally': cur_rally,
        'avg_rally': avg_rally, 'med_rally': med_rally,
        'avg_mdd': avg_mdd, 'med_mdd': med_mdd,
        'prob_up_5': prob_up_5, 'prob_up_10': prob_up_10,
        'prob_up_15': prob_up_15, 'prob_up_20': prob_up_20,
        'prob_dn_5': prob_dn_5, 'prob_dn_10': prob_dn_10,
        'prob_dn_15': prob_dn_15, 'prob_dn_20': prob_dn_20,
        'up_ev': up_ev, 'down_ev': down_ev, 'risk_reward': risk_reward,
    }


def _calc_overheat_score(df):
    """과열 점수 산출 (RSI + BB 기반)"""
    cur = df.iloc[-1]
    scores = []

    rsi = cur.get('RSI')
    if rsi is not None and not pd.isna(rsi):
        scores.append(min(100, max(0, (rsi - 30) / 70 * 100)))

    bb_upper = cur.get('BB_upper')
    bb_lower = cur.get('BB_lower')
    close = cur.get('close', 0)
    if bb_upper and bb_lower and not pd.isna(bb_upper):
        bb_range = bb_upper - bb_lower
        if bb_range > 0:
            bb_pos = (close - bb_lower) / bb_range * 100
            scores.append(min(100, max(0, bb_pos)))

    # MA20 이격도 기반 과열
    ma20 = cur.get('MA20')
    if ma20 and not pd.isna(ma20) and ma20 > 0:
        disp20 = (close / ma20 - 1) * 100
        disp_score = min(100, max(0, disp20 / 20 * 100))  # 20% 이격 = 100점
        scores.append(disp_score)

    return sum(scores) / len(scores) if scores else 50


def generate_scenario_response_report(a, df, date_str):
    """시나리오 대응 전략 리포트 생성"""
    k = a['kospi']
    sv = a['stock_value']
    na = a['net_asset']
    loan = a['loan']

    # 확률 데이터 산출
    prob = _compute_probability_data(df, k)
    overheat = _calc_overheat_score(df)

    # PER 밴드 (config에서 가져오기)
    try:
        from config import CURRENT_FWD_EPS
        per_5y_avg = 10.2
        per_1sigma = 11.4
        per_neg1sigma = 9.0
        per_neg2sigma = 7.8
        fair_value = CURRENT_FWD_EPS * per_5y_avg
        upper_1s = CURRENT_FWD_EPS * per_1sigma
        lower_1s = CURRENT_FWD_EPS * per_neg1sigma
        lower_2s = CURRENT_FWD_EPS * per_neg2sigma
    except ImportError:
        fair_value = k * 1.10
        upper_1s = k * 1.24
        lower_1s = k * 0.97
        lower_2s = k * 0.85

    # 담보비율
    collateral_pct = a['collateral']

    # 목표가 설정
    peak_kospi = a['high_52w']

    # 확률 기반 매도/손절 구간 결정
    if prob:
        # 50% 이상 확률로 도달 가능한 최대 상승폭
        target_pct = 0
        for pct, p in [(20, prob['prob_up_20']), (15, prob['prob_up_15']),
                       (10, prob['prob_up_10']), (5, prob['prob_up_5'])]:
            if p >= 50:
                target_pct = pct
                break
        # 50% 이상 확률로 발생하는 최대 하락폭
        stop_pct = 0
        for pct, p in [(20, prob['prob_dn_20']), (15, prob['prob_dn_15']),
                       (10, prob['prob_dn_10']), (5, prob['prob_dn_5'])]:
            if p >= 50:
                stop_pct = pct
                break
        risk_reward = prob['risk_reward']
    else:
        target_pct = 10
        stop_pct = 5
        risk_reward = 2.0

    # 익절/손절 가격
    target_price = k * (1 + target_pct / 100)
    stop_price = k * (1 - stop_pct / 100)

    # 분할 매도 단계
    sell_stages = []
    if target_pct >= 5:
        sell_stages.append((5, k * 1.05, 15))
    if target_pct >= 10:
        sell_stages.append((10, k * 1.10, 25))
    if target_pct >= 15:
        sell_stages.append((15, k * 1.15, 20))
    if target_pct >= 20:
        sell_stages.append((20, k * 1.20, 25))
    # 보너스: 60일 중위 상승폭
    if prob and prob['med_rally'] > target_pct + 5:
        bonus_pct = prob['med_rally']
        sell_stages.append((bonus_pct, k * (1 + bonus_pct / 100), 15))

    # 남은 비중 조정 (합이 100이 되도록)
    total_sell = sum(s[2] for s in sell_stages)
    if total_sell < 100 and sell_stages:
        sell_stages[-1] = (sell_stages[-1][0], sell_stages[-1][1], sell_stages[-1][2] + (100 - total_sell))

    # 손절 단계
    stop_stages = [
        (3, k * 0.97, 30, "기술적 하락확인 (MACD데드+RSI하락)"),
        (stop_pct if stop_pct >= 5 else 5, stop_price if stop_pct >= 5 else k * 0.95, 30, "종가 이탈 확인"),
        (max(stop_pct + 3, 8), k * (1 - max(stop_pct + 3, 8) / 100), 40, "추세 전환 확인"),
    ]

    # ── 리포트 생성 ──
    report = f"""# 🎯 포지션 전략 시나리오 대응 — {date_str}

> **기준**: 코스피 {k:,.1f}pt | 평가 {sv:.1f}억 | 순자산 {na:.1f}억 | 대출 {loan:.2f}억 | 담보 {collateral_pct:,.0f}%
> **목표**: 코스피 {target_price:,.0f}pt (+{target_pct}%) | 예상 순자산 ~{sv*(1+target_pct/100)-loan:.1f}억
> **핵심 판단**: 60일내 +{target_pct}% 도달 확률 **{prob[f'prob_up_{target_pct}']:.0f}%**{f', -{stop_pct}% 이탈 확률 **{prob["prob_dn_" + str(stop_pct)]:.0f}%**' if prob and stop_pct > 0 else ''}

---

## ★ 전략 요약 (한눈에)

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  목표: {target_price:,.0f}pt (+{target_pct}%) — 순자산 {sv*(1+target_pct/100)-loan:.1f}억{' ':>10}│
│  손절: {stop_price:,.0f}pt (-{stop_pct}%) — 순자산 {sv*(1-stop_pct/100)-loan:.1f}억{' ':>10}│
│                                                             │"""

    remain = 100
    for pct, price, portion in sell_stages:
        remain -= portion
        na_at = sv * (1 + pct / 100) - loan
        report += f"\n│  ① {price:,.0f} (+{pct:.0f}%) → {portion}% 매도  │ 순자산 {na_at:.1f}억{' ':>16}│"

    report += f"""
│                                                             │
│  🛑 손절:{'':>52}│"""

    for pct, price, portion, desc in stop_stages:
        na_at = sv * (1 - pct / 100) - loan
        report += f"\n│  ① {price:,.0f} (-{pct:.0f}%) → {portion}% 매도  │ 순자산 {na_at:.1f}억{' ':>16}│"

    report += f"""
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 1. 현재 상황 진단

### 시장 상태

| 항목 | 값 | 판단 |
|:---|:---:|:---|
| 코스피 | {k:,.1f}pt | {'52주 신고가 부근' if a['drawdown_52w'] > -3 else f'52주 고점 대비 {a["drawdown_52w"]:.1f}%'} |
| 과열점수 | {overheat:.0f}/100 {'🔴' if overheat >= 80 else '🟡' if overheat >= 60 else '🟢'} | {'극도 과열' if overheat >= 80 else '과열 주의' if overheat >= 60 else '정상'} |
| 시장국면 | 불마켓 {a['bull_prob']}% | {'강한 상승 추세' if a['bull_prob'] >= 80 else '상승 우위' if a['bull_prob'] >= 60 else '중립'} |
| 밸류에이션 (Fwd PER) | {k/fair_value*per_5y_avg:.1f}배 | {'저평가 🟢' if k < fair_value else '적정 🟡' if k < upper_1s else '과열 🔴'} |
| PER 5Y평균 적정가 | {fair_value:,.0f}pt | {(fair_value/k-1)*100:+.1f}% |
| PER +1σ 상단 | {upper_1s:,.0f}pt | {(upper_1s/k-1)*100:+.1f}% |

### 포지션 상태

| 항목 | 값 |
|:---|---:|
| 주식 평가 | **{sv:.1f}억** |
| 담보대출 | **{loan:.2f}억** |
| 순자산 | **{na:.1f}억** |
| 담보비율 | **{collateral_pct:,.0f}%** ({'극히 안전' if collateral_pct > 500 else '안전' if collateral_pct > 300 else '주의'}) |
| 레버리지 | {sv/na:.2f}x |
| 청산선 | 코스피 ~{a['clearing_kospi']:,.0f}pt ({(a['clearing_kospi']/k-1)*100:+.0f}%) |"""

    if prob:
        report += f"""

### 확률 분석 (과거 유사 상황 {prob['n_similar']}회 기반)

| 시나리오 | 확률 | 지수 | 순자산 |
|:---|:---:|---:|---:|
| +20% 도달 | **{prob['prob_up_20']:.0f}%** | {k*1.20:,.0f} | {sv*1.20-loan:.1f}억 |
| +10% 도달 | **{prob['prob_up_10']:.0f}%** | {k*1.10:,.0f} | {sv*1.10-loan:.1f}억 |
| +5% 도달 | **{prob['prob_up_5']:.0f}%** | {k*1.05:,.0f} | {sv*1.05-loan:.1f}억 |
| -5% 이탈 | **{prob['prob_dn_5']:.0f}%** | {k*0.95:,.0f} | {sv*0.95-loan:.1f}억 |
| -10% 이탈 | **{prob['prob_dn_10']:.0f}%** | {k*0.90:,.0f} | {sv*0.90-loan:.1f}억 |
| -15% 이탈 | **{prob['prob_dn_15']:.0f}%** | {k*0.85:,.0f} | {sv*0.85-loan:.1f}억 |
| -20% 이탈 | **{prob['prob_dn_20']:.0f}%** | {k*0.80:,.0f} | {sv*0.80-loan:.1f}억 |

> **핵심**: 상승 기대값({prob['up_ev']:.1f})이 하락 기대값({prob['down_ev']:.1f})의 **{risk_reward:.1f}배** → {'보유 우위' if risk_reward >= 1.5 else '중립' if risk_reward >= 0.8 else '방어 우위'}{'이나, 과열 극심으로 분할 대응 필수.' if overheat >= 70 else '.'}"""

    report += f"""

---

## 2. 상승 시나리오 — 분할 익절 전략

### 원칙
- 과열도 {overheat:.0f}점{'에서 한 번에 전량 보유는 리스크가 큼' if overheat >= 70 else '으로 보유 유지 적절'}
- +{target_pct}% 도달 확률 {prob[f'prob_up_{target_pct}']:.0f}%이므로 **핵심 물량은 끝까지 가져간다**
- 단, 중간 익절로 확정 수익 확보 + 재매수 실탄 마련

### 📈 분할 매도 계획

| 단계 | 조건 | 코스피 | 매도 비중 | 잔여 비중 | 예상 순자산 | 행동 |
|:---:|:---|---:|:---:|:---:|---:|:---|""" if prob else f"""

---

## 2. 상승 시나리오 — 분할 익절 전략

### 📈 분할 매도 계획

| 단계 | 조건 | 코스피 | 매도 비중 | 잔여 비중 | 예상 순자산 | 행동 |
|:---:|:---|---:|:---:|:---:|---:|:---|"""

    remain = 100
    for i, (pct, price, portion) in enumerate(sell_stages, 1):
        remain -= portion
        na_at = sv * (1 + pct / 100) - loan
        sell_amt = sv * portion / 100
        if i == 1 and loan > 0:
            action = f"대출 {loan:.1f}억 상환 + 현금화"
        elif i == len(sell_stages):
            action = "잔여분 전량 청산" if remain <= 0 else "핵심만 보유 유지"
        else:
            action = "수익 확정"
        report += f"\n| **{i}차** | +{pct:.0f}% 도달 | **{price:,.0f}** | **{portion}%** ({sell_amt:.1f}억) | {remain}% | {na_at:.1f}억 | {action} |"

    report += f"""

### 단계별 세부 설명"""

    remain = 100
    for i, (pct, price, portion) in enumerate(sell_stages, 1):
        remain -= portion
        na_at = sv * (1 + pct / 100) - loan
        sell_amt = sv * portion / 100
        if i == 1 and loan > 0:
            after_loan = sell_amt - loan
            report += f"""

#### {i}차 매도 (+{pct:.0f}%, {price:,.0f}pt) — 대출 상환 + 안전마진 확보

**실행:**
```
매도 금액: 평가의 {portion}% = 약 {sell_amt:.1f}억
→ 대출 {loan:.2f}억 상환 (레버리지 해소)
→ 잔여 {after_loan:.1f}억 현금 보유 (하락 시 재매수 실탄)
결과: 순자산 {na_at:.1f}억, 주식 {sv*(1+pct/100)*(remain/100):.1f}억, 현금 {after_loan:.1f}억, 대출 0
```"""
        else:
            report += f"""

#### {i}차 매도 (+{pct:.0f}%, {price:,.0f}pt) — {'목표 도달' if pct >= target_pct else '수익 확정'}

**실행:**
```
매도 금액: 원래 평가의 {portion}% = 약 {sell_amt:.1f}억
→ 전액 현금화
결과: 잔여 주식비중 {remain}%
```"""

    report += f"""

---

## 3. 하락 시나리오 — 손절 전략

### 원칙
- {'과열 구간에서 조정은 높은 확률로 온다' if overheat >= 70 else '현재 과열도가 높지 않아 깊은 하락 가능성 낮음'}
- 불마켓 구조({a['bull_prob']}%) → {'건전한 조정 후 반등 가능성 높음' if a['bull_prob'] >= 70 else '방향성 불확실'}
- 핵심: **-{stop_pct}% 이탈 시 즉시 방어**, 추세 붕괴 시 과감한 청산

### 🛑 손절 계획

| 단계 | 조건 | 코스피 | 매도 비중 | 잔여 | 순자산 | 재진입 조건 |
|:---:|:---|---:|:---:|:---:|---:|:---|"""

    remain = 100
    reentry_conditions = [
        "RSI 50 회복 + MA20 돌파",
        "MA20 위 2일 연속 종가",
        "MA60 돌파 + MACD 골든크로스",
    ]
    for i, (pct, price, portion, desc) in enumerate(stop_stages):
        remain -= portion
        na_at = sv * (1 - pct / 100) - loan
        report += f"\n| **{i+1}차** | -{pct}% + {desc} | **{price:,.0f}** | **{portion}%** | {remain}% | {na_at:.1f}억 | {reentry_conditions[i]} |"

    report += f"""

### 중요 원칙

> ⚠️ 단순 하락만으로는 매도하지 않음. **기술적 하락확인 신호가 반드시 필요.**
> 급락 당일 매도는 **최악의 타이밍**. 불마켓에서 급락 후 반등 확률 높음.
> 패닉셀 대신 **다음날 반등 없으면** 매도.

---

## 4. 횡보 시나리오

### 대응 (1차 익절 미도달 + 1차 손절 미발동 시)

| 기간 | 행동 |
|:---|:---|
| 1~2주 횡보 | 관망 (보유 유지) |
| 3주 횡보 | 15% 트레일링 스탑 설정 (고점 대비 -3% 이탈 시 매도) |
| 4주+ 횡보 | 추가 15% 매도 + 현금 확보, 남은 물량 장기 보유 전환 |

---

## 5. 급등/급락 대응

### 🚀 급등 (+5% 이상 하루 상승)

| 상황 | 행동 |
|:---|:---|
| 갭상승 +5% 이상 (지수 {k*1.05:,.0f}+) | 즉시 20% 매도 (1~2차 합산 선실행) |
| 갭상승 +10% 이상 (지수 {k*1.10:,.0f}+) | 즉시 40% 매도 |
| 장중 급등 후 윗꼬리 양봉 | 추가 10% 매도 (과열 분출 신호) |

### 💥 급락 (-5% 이상 하루 하락)

| 상황 | 행동 |
|:---|:---|
| 갭하락 -3~5% | 장 마감까지 관망 → 종가 {k*0.95:,.0f} 이하면 30% 매도 |
| 갭하락 -5% 이상 (블랙스완) | **매도 금지** — 패닉셀 방지, 다음날 판단 |
| 2일 연속 -3% 이상 | 50% 매도 (추세 붕괴 의심) |

---

## 6. 자금 관리 계획

### 매도 후 자금 운용

| 순서 | 금액 | 용도 |
|:---|---:|:---|
| 1순위 | {loan:.1f}억 | 대출 상환 (이자 절감, 최우선) |
| 2순위 | {na*0.15:.1f}억 | MMF/RP (재매수 실탄, 즉시 인출 가능) |
| 3순위 | 나머지 | 예금/채권 (안전자산) |

### 재진입 조건 (전량 매도 후)

| 조건 | 코스피 | 매수 비중 |
|:---|---:|:---:|
| MA20 돌파 + RSI 50 회복 | ~{k*0.95:,.0f}~{k*0.97:,.0f} | 30% |
| MA60 돌파 + MACD 골든 | ~{k*0.88:,.0f}~{k*0.95:,.0f} | 추가 30% |
| PER -2σ 도달 | {lower_2s:,.0f} | 풀 매수 |

---

## 7. 시나리오별 최종 순자산 기대값

| 시나리오 | 확률 | 최종 순자산 | 원금 대비 |
|:---|:---:|---:|:---:|"""

    # 시나리오 가중 기대값
    if prob:
        sc_list = [
            (f'🎯 목표 도달 (+{target_pct}%)', prob[f'prob_up_{target_pct}'] / 100 * 0.5, sv * (1 + target_pct / 100) - loan),
            ('📈 중간 익절 (+10%)', 0.25, sv * 1.10 - loan),
            ('📊 소폭 상승 (+5%)', 0.15, sv * 1.05 - loan),
            ('➡️ 횡보', 0.05, na),
            ('📉 조정 (-5~10%)', 0.10, sv * 0.925 - loan),
            ('💥 큰 하락 (-15%+)', 0.05, sv * 0.85 - loan),
        ]
        # 정규화
        total_p = sum(p for _, p, _ in sc_list)
        sc_list = [(lbl, p / total_p, na_at) for lbl, p, na_at in sc_list]
    else:
        sc_list = [
            ('🎯 목표 도달', 0.35, sv * (1 + target_pct / 100) - loan),
            ('📈 중간 익절', 0.25, sv * 1.05 - loan),
            ('➡️ 횡보', 0.15, na),
            ('📉 조정', 0.15, sv * 0.93 - loan),
            ('💥 하락', 0.10, sv * 0.85 - loan),
        ]

    exp_total = 0
    for lbl, p, na_at in sc_list:
        report += f"\n| {lbl} | {p*100:.0f}% | **{na_at:.1f}억** | {na_at - na:+.1f}억 |"
        exp_total += p * na_at
    report += f"\n| **가중 기대값** | 100% | **~{exp_total:.1f}억** | **{exp_total - na:+.1f}억** |"

    report += f"""

---

## 8. 체크리스트 (매일 확인)

```
□ 코스피 종가 확인
□ RSI / MACD 상태 확인
□ 매도/손절 트리거 해당 여부 체크:"""

    for i, (pct, price, portion) in enumerate(sell_stages, 1):
        report += f"\n  - {price:,.0f} 도달? → {i}차 익절 {portion}%"
    for i, (pct, price, portion, desc) in enumerate(stop_stages, 1):
        report += f"\n  - {price:,.0f} + {desc}? → {i}차 손절 {portion}%"

    report += f"""
□ 급등/급락 발생 시 해당 프로토콜 실행
□ 매주 금요일: 전략 유효성 재검토
```

---

## 9. 핵심 가격대 정리

```
─── 상승 ───────────────────────────────────────"""

    all_levels = []
    for pct, price, portion in sell_stages:
        all_levels.append((price, f"{len(all_levels)+1}차 익절 - {portion}% 매도 (+{pct:.0f}%)"))
    all_levels.append((upper_1s, f"PER +1σ - 과열 경고선"))
    all_levels.append((fair_value, f"PER 5Y평균 적정가"))
    all_levels = sorted(all_levels, key=lambda x: -x[0])
    for price, desc in all_levels:
        if price > k:
            report += f"\n  {price:>7,.0f}  (+{(price/k-1)*100:.0f}%) │ {desc}"

    report += f"""
─── 현재 ───────────────────────────────────────
  {k:>7,.0f}   (0%)  │ ◀ 현재
─── 하락 ───────────────────────────────────────"""

    for i, (pct, price, portion, desc) in enumerate(stop_stages, 1):
        report += f"\n  {price:>7,.0f}  (-{pct}%) │ {i}차 손절 - {portion}%"

    report += f"""
  {lower_2s:>7,.0f}  ({(lower_2s/k-1)*100:+.0f}%) │ PER -2σ - 풀 매수 구간
─── 청산선 ─────────────────────────────────────
  {a['clearing_kospi']:>7,.0f}  ({(a['clearing_kospi']/k-1)*100:+.0f}%) │ 강제청산 (사실상 불가능)
```

---

## 10. 한 줄 요약

> **{prob[f'prob_up_{target_pct}']:.0f}% 확률로 {target_price:,.0f} 간다. 가는 동안 분할 익절하되,
> {stop_price:,.0f} 종가 이탈 시 과감히 30% 던진다. 가중 기대값 {exp_total:.1f}억.**""" if prob else f"""

---

## 10. 한 줄 요약

> **목표 {target_price:,.0f}. 분할 익절하되,
> {stop_price:,.0f} 이탈 시 과감히 30% 던진다. 가중 기대값 {exp_total:.1f}억.**"""

    report += f"""

---

*{date_str} 생성 | 기반: 유사패턴 확률분석 + PER밴드 + 시장국면판단*
*시장 상황 변화 시 주 1회 재검토 권장*
"""
    return report


# ──────────────────────────────────────────────
# 6. 메인
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
    print("[4/5] 리포트 생성 중...")
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

    # 리포트 3: 시나리오 대응 전략
    print("[5/5] 시나리오 대응 전략 생성 중...")
    report3 = generate_scenario_response_report(a, df, date_str)
    file3 = os.path.join(OUTPUT_DIR, f"투자전략_시나리오대응_{date_file}.md")
    with open(file3, 'w', encoding='utf-8') as f:
        f.write(report3)
    print(f"  ✅ {os.path.basename(file3)}")

    print(f"\n{'=' * 60}")
    print(f"  완료! 생성된 파일:")
    print(f"  1) {file1}")
    print(f"  2) {file2}")
    print(f"  3) {file3}")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()
