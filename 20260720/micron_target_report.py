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

  주가 자동 조회 (기본값 None → 자동):
    마이크론(MU)      : Yahoo Finance 자동 조회
    삼성전자/하이닉스 : 네이버 금융 실시간 조회, 실패 시 최근 거래일 종가 폴백

  자동 조회 실패 시 직접 입력:
    MICRON_STOCK_PRICE     = 1032        (USD)
    SAMSUNG_PRICE_OVERRIDE = 307_000     (원)
    HYNIX_PRICE_OVERRIDE   = 2_244_000   (원)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import sys
import re
import requests
from datetime import datetime, timezone
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
from config import WEEKLY_RESEARCH_DIR

# ========================================================================
# ■ EPS 입력 구역  ← 여기만 수정하세요
# ========================================================================

MICRON_EPS         = 116         # 마이크론 연간 EPS (USD)
MICRON_STOCK_PRICE = None        # None → Yahoo Finance 자동 조회 / 직접: 예 1032
MICRON_PRICE_DATE  = None        # None → 자동 설정            / 직접: 예 '2026-07-02'

SAMSUNG_EPS        = 54_000      # 삼성전자 연간 EPS (원)
HYNIX_EPS          = 410_000      # SK하이닉스 연간 EPS (원)

# 현재 주가 수동 지정 (None → 자동 조회, 실패 시 최근 거래일 종가 폴백)
# 자동 조회 실패 시 아래 값을 직접 입력하세요.
SAMSUNG_PRICE_OVERRIDE = None        # None → 자동 / 직접: 예 294_500
HYNIX_PRICE_OVERRIDE   = None        # None → 자동 / 직접: 예 2_389_000

# ========================================================================
# ■ 분석 파라미터  (변경 필요 시에만 수정)
# ========================================================================

PER_MIN  = 7.00    # PER 분석 시작값
PER_MAX  = 15.00   # PER 분석 종료값
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
# 야후 파이낸스 마이크론(MU) 주가 조회
# ────────────────────────────────────────────────────────────

def fetch_micron_price():
    """Yahoo Finance에서 마이크론(MU) 최신 종가와 날짜(UTC) 조회."""
    url = 'https://query1.finance.yahoo.com/v8/finance/chart/MU?interval=1d&range=5d'
    try:
        r = requests.get(url, headers={'User-Agent': HEADERS['User-Agent']}, timeout=10)
        data = r.json()
        result     = data['chart']['result'][0]
        timestamps = result['timestamp']
        closes     = result['indicators']['quote'][0]['close']
        for ts, close in zip(reversed(timestamps), reversed(closes)):
            if close is not None:
                d = datetime.fromtimestamp(ts, tz=timezone.utc).strftime('%Y-%m-%d')
                return round(close, 2), d
    except Exception as e:
        print(f'  [WARN] 마이크론(MU) 주가 조회 실패: {e}')
    return None, None


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


def fetch_naver_price_with_fallback(code):
    """
    네이버 금융에서 현재 주가 조회. 실패 시 최근 거래일 종가 폴백.
    Returns: (price, date_str, source_label) or (None, None, None)
    """
    # 1. 실시간 조회 시도
    price = fetch_naver_price(code)
    if price:
        return price, datetime.now().strftime('%Y-%m-%d'), '실시간'

    # 2. 최근 거래일 종가 폴백 (일별 시세 페이지)
    url = f'https://finance.naver.com/item/sise_day.naver?code={code}'
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.encoding = 'euc-kr'
        soup = BeautifulSoup(r.text, 'html.parser')
        for tr in soup.select('table.type2 tr'):
            tds = tr.select('td')
            if len(tds) >= 2:
                date_raw  = tds[0].get_text(strip=True)
                price_raw = tds[1].get_text(strip=True).replace(',', '')
                if date_raw and price_raw.isdigit():
                    val = int(price_raw)
                    if val > 0:
                        return val, date_raw, '최근 거래일 종가'
    except Exception as e:
        print(f'  [WARN] 최근 거래일 주가 조회 실패 ({code}): {e}')
    return None, None, None


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

def generate_report(samsung_price, hynix_price, price_meta=None):
    """마크다운 리포트를 생성하고 파일 경로를 반환합니다."""
    now        = datetime.now()
    ts         = now.strftime('%Y%m%d_%H%M%S')
    actual_per = MICRON_STOCK_PRICE / MICRON_EPS

    os.makedirs(WEEKLY_RESEARCH_DIR, exist_ok=True)
    filename = os.path.join(WEEKLY_RESEARCH_DIR, f'마이크론기반_반도체목표주가_{ts}.md')

    with open(filename, 'w', encoding='utf-8') as f:
        # 문서 상단 주석 (실제 PER 행 강조 안내)
        f.write('<!-- 🟢 표시 행: 마이크론 현재 주가 기준 실제 PER 적용 라인 -->\n')

        # 주가 데이터 출처 명시
        if price_meta:
            m = price_meta.get('micron',  {})
            s = price_meta.get('samsung', {})
            h = price_meta.get('hynix',   {})
            f.write('\n> **📌 주가 데이터 기준**\n')
            f.write('>\n')
            f.write('> | 종목 | 적용 주가 | 기준일 | 출처 |\n')
            f.write('> |:---|---:|:---:|:---|\n')
            f.write(f'> | 마이크론(MU) | ${m.get("price", MICRON_STOCK_PRICE):,.2f}'
                    f' | {m.get("date", MICRON_PRICE_DATE)} | {m.get("source", "—")} |\n')
            f.write(f'> | 삼성전자 | {s.get("price", samsung_price):,}원'
                    f' | {s.get("date", "—")} | {s.get("source", "—")} |\n')
            f.write(f'> | SK하이닉스 | {h.get("price", hynix_price):,}원'
                    f' | {h.get("date", "—")} | {h.get("source", "—")} |\n')
            f.write('\n---\n\n')

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
    global MICRON_STOCK_PRICE, MICRON_PRICE_DATE

    print('=' * 60)
    print('  마이크론 EPS 기반 반도체 목표주가 산출 리포트')
    print('=' * 60)
    print()

    price_meta = {}

    # ── 마이크론 주가 조회 ─────────────────────────────────────
    if MICRON_STOCK_PRICE is None:
        print('[0/3] 마이크론(MU) 주가 조회 중... (Yahoo Finance)')
        mic_price, mic_date = fetch_micron_price()
        if mic_price:
            MICRON_STOCK_PRICE = mic_price
            MICRON_PRICE_DATE  = mic_date
            print(f'  → ${mic_price:,.2f}  ({mic_date})')
            price_meta['micron'] = {'price': mic_price, 'date': mic_date, 'source': '야후파이낸스 자동 조회'}
        else:
            print(
                '  [ERROR] 마이크론 주가 자동 조회 실패.\n'
                '          micron_target_report.py 의 MICRON_STOCK_PRICE 에\n'
                '          현재 주가를 직접 입력하고 다시 실행하세요.'
            )
            return None
    else:
        price_meta['micron'] = {
            'price':  MICRON_STOCK_PRICE,
            'date':   MICRON_PRICE_DATE or datetime.now().strftime('%Y-%m-%d'),
            'source': '수동 입력',
        }

    print(f'[설정] 마이크론 EPS: {MICRON_EPS:,}  /  주가: ${MICRON_STOCK_PRICE:,.2f}')
    print(f'[설정] 삼성전자 EPS: {SAMSUNG_EPS:,}원')
    print(f'[설정] SK하이닉스 EPS: {HYNIX_EPS:,}원')
    print()

    # ── 삼성전자 현재가 ────────────────────────────────────────
    samsung_price = SAMSUNG_PRICE_OVERRIDE
    if samsung_price is None:
        print('[1/3] 삼성전자 현재가 조회 중... (005930)')
        samsung_price, s_date, s_src = fetch_naver_price_with_fallback('005930')
        if samsung_price:
            print(f'  → {samsung_price:,}원  ({s_date}, {s_src})')
            price_meta['samsung'] = {'price': samsung_price, 'date': s_date, 'source': f'네이버 금융 {s_src}'}
        else:
            print(
                '  [ERROR] 주가 조회 실패.\n'
                '          micron_target_report.py 의 SAMSUNG_PRICE_OVERRIDE 에\n'
                '          현재 주가를 직접 입력하고 다시 실행하세요.'
            )
            return None
    else:
        price_meta['samsung'] = {
            'price':  samsung_price,
            'date':   datetime.now().strftime('%Y-%m-%d'),
            'source': '수동 입력',
        }

    # ── SK하이닉스 현재가 ──────────────────────────────────────
    hynix_price = HYNIX_PRICE_OVERRIDE
    if hynix_price is None:
        print('[2/3] SK하이닉스 현재가 조회 중... (000660)')
        hynix_price, h_date, h_src = fetch_naver_price_with_fallback('000660')
        if hynix_price:
            print(f'  → {hynix_price:,}원  ({h_date}, {h_src})')
            price_meta['hynix'] = {'price': hynix_price, 'date': h_date, 'source': f'네이버 금융 {h_src}'}
        else:
            print(
                '  [ERROR] 주가 조회 실패.\n'
                '          micron_target_report.py 의 HYNIX_PRICE_OVERRIDE 에\n'
                '          현재 주가를 직접 입력하고 다시 실행하세요.'
            )
            return None
    else:
        price_meta['hynix'] = {
            'price':  hynix_price,
            'date':   datetime.now().strftime('%Y-%m-%d'),
            'source': '수동 입력',
        }

    print()
    filename = generate_report(samsung_price, hynix_price, price_meta)
    print(f'✅ 리포트 생성 완료: {filename}')
    return filename


if __name__ == '__main__':
    main()
