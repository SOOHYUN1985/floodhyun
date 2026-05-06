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


def _build_market_block(market_name: str, current_price: float,
                        trend_type: str, trend_confidence: int,
                        strategies: List[Dict], df: pd.DataFrame) -> str:
    """한 시장(코스피 or 코스닥)의 요약 블록 생성"""
    heat_score, hot_inds = _calc_overheat(df)

    breakout = [s for s in strategies if s['type'] == 'breakout']
    reversal = [s for s in strategies if s['type'] == 'reversal']

    # 가장 가까운 매도 목표
    nearest = None
    for s in breakout:
        tp = _calc_trigger_price(s, df)
        if tp is not None:
            pct = (tp - current_price) / current_price * 100
            if nearest is None or tp < nearest['price']:
                nearest = {'price': tp, 'pct': pct, 'name': s['name'],
                           'win_rate': s['win_rate']}

    # 이미 발동된 전략
    triggered = []
    for s in breakout:
        tp = _calc_trigger_price(s, df)
        if tp is not None:
            pct = (tp - current_price) / current_price * 100
            if pct <= 0:
                triggered.append({'name': s['name'], 'price': tp, 'pct': pct,
                                  'win_rate': s['win_rate']})

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

    # 상승 시 액션
    lines.append('**📈 상승 시**')
    lines.append('')
    if triggered:
        lines.append('| 🔴 즉시 매도 | 전략 | 승률 |')
        lines.append('|:---:|:---|:---:|')
        for t in triggered:
            lines.append(f'| **{t["price"]:,.0f}** ({t["pct"]:+.1f}%) | {t["name"]} | {t["win_rate"]:.0f}% |')
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

    # 핵심 분할매도 단계 (상위 3개만)
    sell_stages = []
    for s in breakout:
        tp = _calc_trigger_price(s, df)
        if tp is not None:
            pct = (tp - current_price) / current_price * 100
            sell_stages.append({'price': tp, 'pct': pct, 'name': s['name'],
                                'win_rate': s['win_rate']})
    sell_stages.sort(key=lambda x: x['price'])
    sell_stages = sell_stages[:5]

    if sell_stages:
        lines.append('**📍 분할매도 단계**')
        lines.append('')
        lines.append('| 단계 | 목표가 | 등락률 | 전략 | 승률 |')
        lines.append('|:---:|---:|:---:|:---|:---:|')
        for i, st in enumerate(sell_stages, 1):
            status = '🔴' if st['pct'] <= 0 else ('⚡' if st['pct'] < 2 else ('🎯' if st['pct'] < 5 else '⏳'))
            lines.append(f'| {status} {i}단계 | **{st["price"]:,.0f}** | {st["pct"]:+.1f}% | {st["name"]} | {st["win_rate"]:.0f}% |')
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
