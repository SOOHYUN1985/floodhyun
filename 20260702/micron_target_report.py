"""
마이크론 EPS 기반 삼성전자·SK하이닉스 목표주가 산출 리포트 생성기

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ★★★ EPS 수정 방법 ★★★

  아래 '■ EPS 입력 구역' 안의 값만 수정하면 됩니다.

  필수 수정 항목:
    MICRON_EPS          ← 마이크론 발표 EPS (USD)
    MICRON_STOCK_PRICE  ← 마이크론 현재 주가 (USD, 실시간으로 업데이트)
    MICRON_PRICE_DATE   ← 마이크론 주가 기준일 (메모용)
    SAMSUNG_EPS         ← 삼성전자 연간 EPS (원)
    HYNIX_EPS           ← SK하이닉스 연간 EPS (원)

  삼성전자/SK하이닉스 현재 주가는 기본적으로 네이버 금융에서 자동 조회합니다.
  자동 조회가 실패하면 SAMSUNG_PRICE_OVERRIDE / HYNIX_PRICE_OVERRIDE 에
  직접 숫자를 입력하세요 (예: 307_000).
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import sys
import re
import requests
from datetime import datetime
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
from config import WEEKLY_RESEARCH_DIR

# ========================================================================
# ■ EPS 입력 구역  ← 여기만 수정하세요
# ========================================================================

MICRON_EPS         = 116         # 마이크론 연간 EPS (USD)
MICRON_STOCK_PRICE = 1133.99       # 마이크론 현재 주가 (USD)  ← 발표 때마다 업데이트
MICRON_PRICE_DATE  = '2026-06-19' # 마이크론 주가 기준일 (메모용)

SAMSUNG_EPS        = 58_697      # 삼성전자 연간 EPS (원)
HYNIX_EPS          = 419_183      # SK하이닉스 연간 EPS (원)

# 현재 주가 수동 지정 (None → 네이버 금융에서 자동 조회)
# 자동 조회 실패 시 아래 값을 직접 입력하세요.
SAMSUNG_PRICE_OVERRIDE = None     # 예: 307_000   (원)
HYNIX_PRICE_OVERRIDE   = None     # 예: 2_244_000 (원)

# ========================================================================
# ■ 분석 파라미터  (변경 필요 시에만 수정)
# ========================================================================

PER_MIN  = 7.00    # PER 분석 시작값
PER_MAX  = 10.00   # PER 분석 종료값
PER_STEP = 0.25    # PER 분석 간격

# 할인율 테이블: 마이크론 PER 대비 한국 반도체 적용 비율
# (rate=0.20 → 마이크론 PER × 0.80, rate=0.30 → 마이크론 PER × 0.70)
DISCOUNT_TABLES = [
    {'rate': 0.20, 'section': '반도체 3사 PER 기반 적정가 산출표'},
    {'rate': 0.30, 'section': '[추가] PER 30% 할인 적용 시 적정가 산출표'},
]

# ========================================================================

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/125.0.0.0 Safari/537.36'
    ),
    'Referer': 'https://finance.naver.com/',
    'Accept-Language': 'ko-KR,ko;q=0.9',
}


# ────────────────────────────────────────────────────────────
# 네이버 금융 현재 주가 조회
# ────────────────────────────────────────────────────────────

def fetch_naver_price(code):
    """네이버 금융 coinfo 페이지에서 현재 주가 조회 (원)."""
    url = f'https://finance.naver.com/item/coinfo.naver?code={code}'
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.encoding = 'euc-kr'
        soup = BeautifulSoup(r.text, 'html.parser')
        for klass in ('no_up', 'no_dn', 'no_stay'):
            tag = soup.find(class_=klass)
            if tag:
                raw = tag.get_text()
                m = re.search(r'\d{1,3}(?:,\d{3})+', raw)
                if m:
                    val = int(m.group(0).replace(',', ''))
                    if val > 0:
                        return val
    except Exception as e:
        print(f'  [WARN] 주가 조회 실패 ({code}): {e}')
    return None


# ────────────────────────────────────────────────────────────
# PER 구간별 목표주가 행 계산
# ────────────────────────────────────────────────────────────

def build_per_rows(samsung_price, hynix_price, mult):
    """
    PER 구간(PER_MIN~PER_MAX, step PER_STEP)별 삼성/하이닉스 목표주가 행 생성.
    마이크론 실제 PER 행은 해당 위치에 자동으로 삽입됩니다.

    Returns:
        rows (list[dict]), actual_per (float)
    """
    actual_per   = MICRON_STOCK_PRICE / MICRON_EPS
    actual_per_r = round(actual_per, 4)

    # 기본 PER 리스트
    per_list = []
    p = PER_MIN
    while p <= PER_MAX + 1e-9:
        per_list.append(round(p, 4))
        p = round(p + PER_STEP, 4)

    # 실제 PER 삽입 (범위 내이며 기존 값과 0.005 이상 차이나는 경우)
    if not any(abs(x - actual_per_r) < 0.005 for x in per_list):
        if PER_MIN <= actual_per_r <= PER_MAX:
            per_list.append(actual_per_r)
            per_list.sort()

    rows = []
    for per in per_list:
        applied_per    = per * mult
        micron_target  = MICRON_EPS * per
        samsung_target = SAMSUNG_EPS * applied_per
        hynix_target   = HYNIX_EPS * applied_per
        samsung_upside = (samsung_target - samsung_price) / samsung_price * 100
        hynix_upside   = (hynix_target  - hynix_price)  / hynix_price  * 100
        is_actual      = abs(per - actual_per_r) < 0.005

        rows.append({
            'per':            per,
            'applied_per':    applied_per,
            'micron_target':  micron_target,
            'samsung_target': samsung_target,
            'hynix_target':   hynix_target,
            'samsung_upside': samsung_upside,
            'hynix_upside':   hynix_upside,
            'is_actual':      is_actual,
        })
    return rows, actual_per


# ────────────────────────────────────────────────────────────
# 마크다운 표 출력
# ────────────────────────────────────────────────────────────

def write_table(f, rows, mult_pct_label):
    """PER 기반 적정가 마크다운 표를 파일에 씁니다."""
    f.write(
        f'| 마이크론 PER | 마이크론 적정가({MICRON_EPS}×PER) | '
        f'삼성·하이닉스 적용 PER({mult_pct_label}) | '
        f'삼성전자 적정가 | SK하이닉스 적정가 | '
        f'삼성전자 상승여력(%) | 하이닉스 상승여력(%) |\n'
    )
    f.write(
        '| -------: | ---------------------: | ------------------: | '
        '-------------: | --------------: | -------------------: | -------------------: |\n'
    )

    for r in rows:
        per_s    = f'{r["per"]:.2f}'
        app_s    = f'{r["applied_per"]:.2f}'
        mic_s    = f'{int(r["micron_target"])}'
        sam_s    = f'{int(r["samsung_target"]):,}원'
        hyn_s    = f'{int(r["hynix_target"]):,}원'
        sam_up   = f'{r["samsung_upside"]:+.1f}%'
        hyn_up   = f'{r["hynix_upside"]:+.1f}%'

        if r['is_actual']:
            f.write(
                f'| 🟢 **{per_s}** | **{mic_s}** | **{app_s}** | '
                f'**{sam_s}** | **{hyn_s}** | **{sam_up}** | **{hyn_up}** |\n'
            )
        else:
            f.write(
                f'| {per_s} | {mic_s} | {app_s} | '
                f'{sam_s} | {hyn_s} | {sam_up} | {hyn_up} |\n'
            )


# ────────────────────────────────────────────────────────────
# 리포트 생성
# ────────────────────────────────────────────────────────────

def generate_report(samsung_price, hynix_price):
    """마크다운 리포트를 생성하고 파일 경로를 반환합니다."""
    now        = datetime.now()
    ts         = now.strftime('%Y%m%d_%H%M%S')
    actual_per = MICRON_STOCK_PRICE / MICRON_EPS

    os.makedirs(WEEKLY_RESEARCH_DIR, exist_ok=True)
    filename = os.path.join(WEEKLY_RESEARCH_DIR, f'마이크론기반_반도체목표주가_{ts}.md')

    with open(filename, 'w', encoding='utf-8') as f:
        # 문서 상단 주석 (실제 PER 행 강조 안내)
        f.write('<!-- 🟢 표시 행: 마이크론 현재 주가 기준 실제 PER 적용 라인 -->\n')

        for dt in DISCOUNT_TABLES:
            rate      = dt['rate']
            mult      = 1 - rate
            disc_pct  = int(rate * 100)
            mult_pct  = int(mult * 100)
            section   = dt['section']

            # ── 섹션 헤더 ─────────────────────────────────────────
            f.write(f'## {section}\n\n')
            f.write(f'* 마이크론 EPS: {MICRON_EPS:,} (기준)\n')
            f.write(f'* 삼성전자 EPS: {SAMSUNG_EPS:,}원\n')
            f.write(f'* SK하이닉스 EPS: {HYNIX_EPS:,}원\n')
            f.write(f'* 마이크론 실제 주가({MICRON_PRICE_DATE}): {MICRON_STOCK_PRICE:,.2f}$\n')
            if disc_pct == 20:
                f.write(f'* 마이크론 대비 PER 할인율: {disc_pct}% (PER × {mult:.1f})\n\n')
            else:
                f.write(f'* 적정가 공식: EPS × 적용 PER\n\n')

            # ── 표 출력 ───────────────────────────────────────────
            rows, _ = build_per_rows(samsung_price, hynix_price, mult)
            write_table(f, rows, f'{mult_pct}%')

            # ── 실제 PER 각주 ─────────────────────────────────────
            f.write('\n')
            f.write(f'* 실제 PER = {MICRON_STOCK_PRICE:.2f} / {MICRON_EPS} = {actual_per:.2f}\n')
            f.write(
                f'* 삼성전자 실제 PER 적용가 = {SAMSUNG_EPS:,} × {actual_per:.2f}'
                f' = {int(SAMSUNG_EPS * actual_per):,}원\n'
            )
            f.write(
                f'* 하이닉스 실제 PER 적용가 = {HYNIX_EPS:,} × {actual_per:.2f}'
                f' = {int(HYNIX_EPS * actual_per):,}원\n\n'
            )
            f.write('---\n\n')

    return filename


# ────────────────────────────────────────────────────────────
# 메인
# ────────────────────────────────────────────────────────────

def main():
    print('=' * 60)
    print('  마이크론 EPS 기반 반도체 목표주가 산출 리포트')
    print('=' * 60)
    print()
    print(f'[설정] 마이크론 EPS: {MICRON_EPS:,}  /  주가: ${MICRON_STOCK_PRICE:,.2f}')
    print(f'[설정] 삼성전자 EPS: {SAMSUNG_EPS:,}원')
    print(f'[설정] SK하이닉스 EPS: {HYNIX_EPS:,}원')
    print()

    # ── 삼성전자 현재가 ────────────────────────────────────────
    samsung_price = SAMSUNG_PRICE_OVERRIDE
    if samsung_price is None:
        print('[1/2] 삼성전자 현재가 조회 중... (005930)')
        samsung_price = fetch_naver_price('005930')
        if samsung_price:
            print(f'  → {samsung_price:,}원')
        else:
            print(
                '  [ERROR] 자동 조회 실패.\n'
                '          micron_target_report.py 의 SAMSUNG_PRICE_OVERRIDE 에\n'
                '          현재 주가를 직접 입력하고 다시 실행하세요.'
            )
            return None

    # ── SK하이닉스 현재가 ──────────────────────────────────────
    hynix_price = HYNIX_PRICE_OVERRIDE
    if hynix_price is None:
        print('[2/2] SK하이닉스 현재가 조회 중... (000660)')
        hynix_price = fetch_naver_price('000660')
        if hynix_price:
            print(f'  → {hynix_price:,}원')
        else:
            print(
                '  [ERROR] 자동 조회 실패.\n'
                '          micron_target_report.py 의 HYNIX_PRICE_OVERRIDE 에\n'
                '          현재 주가를 직접 입력하고 다시 실행하세요.'
            )
            return None

    print()
    filename = generate_report(samsung_price, hynix_price)
    print(f'✅ 리포트 생성 완료: {filename}')
    return filename


if __name__ == '__main__':
    main()
