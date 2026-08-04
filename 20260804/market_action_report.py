# -*- coding: utf-8 -*-
"""코스피·코스닥 통합 매매 실행 리포트 생성기."""

from datetime import datetime
from pathlib import Path

from config import DAILY_BACKTEST_DIR, DB_PATH
from data_loader import DataLoader


def _market_state(row):
    """추세·모멘텀·수급을 한 개의 실행 등급으로 통합한다."""
    trend_up = row['close'] >= row['MA20'] >= row['MA60']
    trend_down = row['close'] < row['MA20'] < row['MA60']
    momentum_up = row['MACD_Hist'] > 0 and row['RSI'] >= 50
    foreign_support = row.get('foreign_5d_cum', 0) > 0
    foreign_pressure = row.get('foreign_20d_cum', 0) < 0

    if trend_up and momentum_up and foreign_support:
        return '매수 가능', '신규 자금은 1차 분할 매수'
    if trend_down and not momentum_up:
        return '관망', '신규 매수 보류, 반등 확인 후 접근'
    if foreign_pressure:
        return '제한적 매수', '확인 조건 충족 시에만 소액 분할 매수'
    return '분할 매수', '지지선에서만 단계적으로 진입'


def _format_flow(value):
    if value is None:
        return '데이터 없음'
    return f'{value:,.0f}억'


def _build_market(market, name):
    loader = DataLoader(DB_PATH)
    data = loader.merge_investor_flow(loader.calculate_indicators(loader.load_market_data(market)), market)
    row = data.iloc[-1]
    price = float(row['close'])
    action, instruction = _market_state(row)

    ma20 = float(row['MA20'])
    ma60 = float(row['MA60'])
    stop = min(ma60, price * 0.95)
    buy_levels = [min(ma20, price * 0.98), min(ma60, price * 0.94), price * 0.88]
    sell_levels = [price * 1.05, price * 1.10, price * 1.15]
    checks = [
        price >= ma20,
        row['RSI'] >= 50,
        row['MACD_Hist'] > 0,
        row.get('foreign_5d_cum', 0) > 0,
    ]
    check_texts = [
        f"종가가 MA20 ({ma20:,.0f}) 위에서 마감",
        f"RSI 50 이상 (현재 {row['RSI']:.1f})",
        f"MACD 히스토그램 양수 전환 (현재 {row['MACD_Hist']:.2f})",
        f"외국인 5일 누적 순매수 (현재 {_format_flow(row.get('foreign_5d_cum'))})",
    ]

    lines = [
        f'## {name}: {action}',
        '',
        f'> **오늘의 행동: {instruction}**',
        '',
        '| 현재 지수 | 추세 | RSI | 외국인 5일 | 외국인 20일 |',
        '|---:|:---|---:|---:|---:|',
        f"| **{price:,.2f}** | MA20 {'상회' if price >= ma20 else '하회'} / MA60 {'상회' if price >= ma60 else '하회'} | {row['RSI']:.1f} | {_format_flow(row.get('foreign_5d_cum'))} | {_format_flow(row.get('foreign_20d_cum'))} |",
        '',
        '### 매수: 언제, 어떻게',
        '',
        f'매수 확인 조건은 **4개 중 {sum(checks)}개 충족**입니다. 3개 이상일 때만 1차 매수를 실행합니다.',
        '',
        '| 단계 | 조건/가격 | 매수 비중 | 이유 |',
        '|:---:|---:|:---:|---|',
        f'| 1차 | {buy_levels[0]:,.0f} 부근 + 확인 조건 3개 | 25% | MA20 지지와 모멘텀 회복 확인 |',
        f'| 2차 | {buy_levels[1]:,.0f} 부근 | 25% | MA60 지지선에서 평균 매입단가 조절 |',
        f'| 3차 | {buy_levels[2]:,.0f} 부근 | 20% | 변동성 확대 구간, 반전 신호 확인 후만 실행 |',
        '| 대기 자금 | - | 30% | 추세 재이탈 또는 급락 대응 |',
        '',
        '### 매도와 방어: 보유자는 이렇게',
        '',
        '| 단계 | 가격/조건 | 행동 | 이유 |',
        '|:---:|---:|:---:|---|',
        f'| 1차 익절 | {sell_levels[0]:,.0f} | 20% 매도 | 현재가 대비 +5%, 1차 이익 확정 |',
        f'| 2차 익절 | {sell_levels[1]:,.0f} | 30% 매도 | 단기 반등 수익 확정 |',
        f'| 3차 익절 | {sell_levels[2]:,.0f} | 30% 매도 | 변동성 확대 전 이익 보호 |',
        f'| 방어선 | 종가 {stop:,.0f} 하회 | 보유분 50% 축소 | MA60 또는 -5% 이탈은 추세 약화 신호 |',
        '',
        '### 매수 재개 체크',
        '',
    ]
    lines.extend(f'- {"[x]" if check else "[ ]"} {text}' for check, text in zip(checks, check_texts))
    return '\n'.join(lines)


def generate_report():
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = Path(DAILY_BACKTEST_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f'통합_매매실행가이드_{timestamp}.md'

    content = [
        '# 코스피·코스닥 통합 매매 실행 가이드',
        '',
        f'**생성 시각**: {datetime.now():%Y년 %m월 %d일 %H:%M}',
        '**판정 기준**: 일일 기술지표·백테스트용 가격 DB + 주간 외국인 수급 DB',
        '',
        '> 이 문서는 매수·매도 시점을 단순화한 실행 가이드입니다. 모든 매수는 확인 조건 충족 후 분할하며, 손실 가능성을 전제로 합니다.',
        '',
        '---',
        '',
        _build_market('kospi', '코스피'),
        '',
        '---',
        '',
        _build_market('kosdaq', '코스닥'),
        '',
        '---',
        '',
        '## 공통 원칙',
        '',
        '1. 확인 조건 3개 미만이면 신규 진입보다 현금 보유를 우선합니다.',
        '2. 한 번에 전액 매수·매도하지 않고, 표의 비중대로 나눕니다.',
        '3. 방어선 종가 이탈 시 반등 기대보다 손실 관리 원칙을 우선합니다.',
    ]
    output.write_text('\n'.join(content) + '\n', encoding='utf-8')
    print(f'[OK] 통합 매매 가이드 생성: {output}')
    return output


if __name__ == '__main__':
    generate_report()