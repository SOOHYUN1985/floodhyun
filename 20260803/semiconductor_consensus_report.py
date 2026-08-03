"""
삼성전자 · SK하이닉스 증권사 목표주가 컨센서스 리포트 생성기

데이터 수집 방식 (우선순위):
  1. Playwright (설치된 경우): 네이버 금융 coinfo 페이지를 실제 브라우저로 렌더링
     → 투자의견 컨센서스 "+" 버튼 클릭 → 증권사별 목표가 상세 테이블 추출
  2. Requests (항상 동작): 네이버 금융 정적 HTML
     → 현재가, 집계 컨센서스, 52주H/L, PER/PBR, 리포트 목록

매수 원칙:
  * 목표가의 60% 미만  → ⚠️ 이상신호 (원인 파악 우선)
  * 목표가의 60~70%   → 강력매수
  * 목표가의 70~80%   → 매수
  * 목표가쀙 80~90%   → 적정
  * 목표가의 90~100%  → 보류
  * 목표가의 100% 초과 → 매도
"""

import os
import sys
import re
import json
import time
import requests
import numpy as np
from bs4 import BeautifulSoup
from datetime import datetime
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
from config import WEEKLY_RESEARCH_DIR

# ── 설정 ──────────────────────────────────────────────────────────────
STOCKS = [
    {'code': '005930', 'name': '삼성전자'},
    {'code': '000660', 'name': 'SK하이닉스'},
]

# ── 투자 판단 기준 (현재가 / 목표주가 비율) ──────────────────────────────
ANOMALY_MAX    = 0.60   # 60% 미만  → ⚠️ 이상신호 (원인 파악 우선)
STRONG_BUY_MAX = 0.70   # 60~70%   → 강력매수
BUY_MAX        = 0.80   # 70~80%   → 매수
FAIR_MAX       = 0.90   # 80~90%   → 적정
HOLD_MAX       = 1.00   # 90~100%  → 보류
                        # 100% 초과 → 매도

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/125.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'ko-KR,ko;q=0.9',
    'Referer': 'https://finance.naver.com/',
}


# ══════════════════════════════════════════════════════════════════════
# 1. Playwright 기반 수집 (JS 렌더링 → 증권사별 상세 목표가)
# ══════════════════════════════════════════════════════════════════════

def _playwright_available() -> bool:
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        return False


def fetch_broker_targets_playwright(code: str) -> list:
    """
    Playwright 로 네이버 금융 coinfo 페이지를 렌더링하고
    투자의견 컨센서스 '+' 버튼 클릭 후 증권사별 목표가 테이블 파싱.

    Returns:
        list of dict:
          {provider, date, target, prev_target, change_pct, opinion, prev_opinion}
    """
    from playwright.sync_api import sync_playwright

    url = f'https://finance.naver.com/item/coinfo.naver?code={code}'
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=HEADERS['User-Agent'],
            locale='ko-KR',
        )
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=30000)
            page.wait_for_timeout(2000)

            # "+" 버튼 클릭 (투자의견 컨센서스 확장)
            # 클래스 또는 텍스트로 "+" 버튼 탐색
            expand_selectors = [
                'button.btn_plus',
                'a.btn_plus',
                'button[class*="plus"]',
                'a[class*="plus"]',
                'span[class*="plus"]',
                '//button[contains(text(),"+")]',
                '//a[contains(text(),"+")]',
            ]
            for sel in expand_selectors:
                try:
                    if sel.startswith('//'):
                        elem = page.locator(f'xpath={sel}').first
                    else:
                        elem = page.locator(sel).first
                    if elem.is_visible(timeout=1000):
                        elem.click()
                        page.wait_for_timeout(1500)
                        break
                except Exception:
                    continue

            # 테이블 파싱 - "제공처", "최종일자", "목표가" 헤더를 찾음
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')

            for table in soup.find_all('table'):
                header_texts = [
                    th.get_text(strip=True)
                    for th in table.find_all(['th', 'td'])[:10]
                ]
                header_joined = ' '.join(header_texts)

                # 컨센서스 테이블 식별: "제공처" 또는 "목표가" 헤더 포함
                if not any(k in header_joined for k in ['제공처', '목표가', '적정주가']):
                    continue

                for row in table.find_all('tr')[1:]:
                    cells = [td.get_text(strip=True) for td in row.find_all('td')]
                    if len(cells) < 3:
                        continue

                    # 숫자 파싱 헬퍼
                    def _int(s):
                        s = re.sub(r'[^\d]', '', s)
                        return int(s) if s else None

                    def _float(s):
                        s = re.sub(r'[^\d.\-]', '', s)
                        try:
                            return float(s)
                        except Exception:
                            return None

                    target = _int(cells[2]) if len(cells) > 2 else None
                    if not target or target < 10000:
                        continue

                    results.append({
                        'provider':      cells[0] if cells else '',
                        'date':          cells[1] if len(cells) > 1 else '',
                        'target':        target,
                        'prev_target':   _int(cells[3]) if len(cells) > 3 else None,
                        'change_pct':    _float(cells[4]) if len(cells) > 4 else None,
                        'opinion':       cells[5] if len(cells) > 5 else '',
                        'prev_opinion':  cells[6] if len(cells) > 6 else '',
                    })

                if results:
                    break  # 첫 번째 유효 테이블에서 중지

        finally:
            browser.close()

    return results


# ══════════════════════════════════════════════════════════════════════
# 2. Requests 기반 수집 (정적 HTML: 현재가·집계 컨센서스·PER 등)
# ══════════════════════════════════════════════════════════════════════

def fetch_naver_stock_info(code: str) -> dict:
    """
    네이버 금융 coinfo.naver 에서 정적으로 파싱 가능한 지표 수집.
    Returns dict: price, consensus_target, opinion, opinion_score,
                  w52_high, w52_low, per, est_per, pbr
    """
    url = f'https://finance.naver.com/item/coinfo.naver?code={code}'
    data = {}
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.encoding = 'euc-kr'
        soup = BeautifulSoup(r.text, 'html.parser')

        # ── 현재가 ────────────────────────────────────────────────────
        # 네이버 금융 price 영역: class="no_up" | "no_dn" | "no_stay"
        # 텍스트가 '667,000667,000' 처럼 두 번 붙어서 반복되므로 첫 번째 콤마 형식 숫자만 추출
        for klass in ('no_up', 'no_dn', 'no_stay'):
            tag = soup.find(class_=klass)
            if tag:
                raw = tag.get_text()
                m = re.search(r'\d{1,3}(?:,\d{3})+', raw)
                if not m:
                    m = re.search(r'\d+', raw)
                if m:
                    val = int(m.group(0).replace(',', ''))
                    if val > 0:
                        data['price'] = val
                        break

        # ── 투자정보 테이블 (th=레이블, td=값 구조) ────────────────────
        for tbl in soup.find_all('table'):
            for tr in tbl.find_all('tr'):
                ths = tr.find_all('th')
                tds = tr.find_all('td')
                if not ths or not tds:
                    continue
                label = ths[0].get_text(strip=True)
                value = tds[0].get_text(strip=True)

                # 투자의견l목표주가 → '4.04매수l427,917'
                if '투자의견' in label:
                    m = re.match(r'^([\d.]+)([^l]+)l([\d,]+)', value)
                    if m:
                        data['opinion_score']    = float(m.group(1))
                        data['opinion']          = m.group(2)
                        data['consensus_target'] = int(m.group(3).replace(',', ''))

                # 52주최고l최저 → '370,000l56,900'
                elif '52주최고' in label:
                    m = re.match(r'^([\d,]+)l([\d,]+)', value)
                    if m:
                        data['w52_high'] = int(m.group(1).replace(',', ''))
                        data['w52_low']  = int(m.group(2).replace(',', ''))

                # PERlEPS(2026.03)... → '25.66배l12,372원'
                elif label.startswith('PERl') and '추정' not in label:
                    m = re.match(r'^([\d.]+)배', value)
                    if m:
                        data['per'] = float(m.group(1))

                # 추정PERlEPS... → '7.00배l43,584원'
                elif '추정PER' in label:
                    m = re.match(r'^([\d.]+)배', value)
                    if m:
                        data['est_per'] = float(m.group(1))

                # PBRlBPS(2026.03)... → 'N/Al71,907원'
                elif label.startswith('PBRl'):
                    if not value.startswith('N/A'):
                        m = re.match(r'^([\d.]+)', value)
                        if m:
                            try:
                                data['pbr'] = float(m.group(1))
                            except Exception:
                                pass

    except Exception as e:
        print(f'[WARNING] Naver coinfo 파싱 실패 ({code}): {e}')

    return data


# ══════════════════════════════════════════════════════════════════════
# 2b. WiseReport 기반 수집 (FnGuide iframe: 증권사별 상세 목표가)
# ══════════════════════════════════════════════════════════════════════

def fetch_wisereport_brokers(code: str) -> list:
    """
    FnGuide/WiseReport 페이지에서 정적 HTML로 증권사별 목표가 수집.
    네이버 금융 coinfo 페이지에 삽입된 iframe 소스를 직접 요청.

    Returns list of dict:
      {provider, date, target, prev_target, change_pct, opinion, prev_opinion}
    """
    url = f'https://navercomp.wisereport.co.kr/v2/company/c1010001.aspx?cmp_cd={code}'
    results = []

    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.content.decode('utf-8'), 'html.parser')

        def _int(s):
            s = re.sub(r'[^\d]', '', s)
            return int(s) if s else None

        def _float(s):
            s = re.sub(r'[^\d.\-]', '', s)
            try:
                return float(s)
            except Exception:
                return None

        for tbl in soup.find_all('table'):
            tbl_text = tbl.get_text()[:150]
            if '제공처' not in tbl_text and '목표가' not in tbl_text:
                continue

            for row in tbl.find_all('tr')[1:]:  # 헤더 행 건너뜀
                cells = [c.get_text(strip=True) for c in row.find_all(['th', 'td'])]
                if len(cells) < 3:
                    continue

                target = _int(cells[2]) if len(cells) > 2 else None
                if not target or target < 10000:
                    continue

                # 날짜 변환: '26/06/08' → '2026/06/08'
                date_raw = cells[1] if len(cells) > 1 else ''
                dm = re.match(r'^(\d{2})/(\d{2})/(\d{2})$', date_raw)
                date_str = f'20{dm.group(1)}/{dm.group(2)}/{dm.group(3)}' if dm else date_raw

                results.append({
                    'provider':     cells[0],
                    'date':         date_str,
                    'target':       target,
                    'prev_target':  _int(cells[3]) if len(cells) > 3 else None,
                    'change_pct':   _float(cells[4]) if len(cells) > 4 else None,
                    'opinion':      cells[5] if len(cells) > 5 else '',
                    'prev_opinion': cells[6] if len(cells) > 6 else '',
                })

            if results:
                break  # 첫 번째 유효 테이블에서 중지

    except Exception as e:
        print(f'[WARNING] WiseReport 수집 실패 ({code}): {e}')

    return results


def fetch_research_reports(code: str, pages: int = 3) -> list:
    """
    네이버 리서치 페이지에서 최근 증권사 리포트 목록 수집.
    Returns list of dict: {firm, title, date, year, month}
    """
    base_url = 'https://finance.naver.com/research/company_list.naver'
    reports = []

    for page in range(1, pages + 1):
        try:
            params = {'searchType': 'itemCode', 'itemCode': code, 'page': page}
            r = requests.get(base_url, params=params, headers=HEADERS, timeout=15)
            r.encoding = 'euc-kr'
            soup = BeautifulSoup(r.text, 'html.parser')

            # 테이블 찾기
            tbl = None
            for t in soup.find_all('table'):
                if '증권사' in t.get_text()[:300] or '종목명' in t.get_text()[:300]:
                    tbl = t
                    break

            if not tbl:
                break

            found = False
            for row in tbl.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) < 4:
                    continue
                texts = [c.get_text(strip=True) for c in cells]

                # 작성일 형식: "26.06.09"
                date_text = texts[4] if len(texts) > 4 else (texts[3] if len(texts) > 3 else '')
                dm = re.match(r'(\d{2})\.(\d{2})\.(\d{2})', date_text)
                if not dm:
                    continue

                yr  = 2000 + int(dm.group(1))
                mo  = int(dm.group(2))
                dy  = int(dm.group(3))
                firm  = texts[2]
                title = texts[1]

                if not firm:
                    continue

                reports.append({
                    'firm':  firm,
                    'title': title,
                    'date':  f'{yr}-{mo:02d}-{dy:02d}',
                    'year':  yr,
                    'month': mo,
                })
                found = True

            if not found:
                break

        except Exception as e:
            print(f'[WARNING] 리서치 페이지 파싱 실패 ({code} p{page}): {e}')
            break

    return reports


# ══════════════════════════════════════════════════════════════════════
# 3. 통계 계산
# ══════════════════════════════════════════════════════════════════════

def monthly_stats(broker_list: list, year: int, month: int) -> dict:
    """broker_list 중 해당 년/월의 목표가 통계 계산"""
    targets = []
    for item in broker_list:
        d = item.get('date', '')
        dm = re.search(r'(\d{2,4})[.\-/](\d{2})', d)
        if dm:
            y = int(dm.group(1))
            m = int(dm.group(2))
            if y < 100:
                y += 2000
            if y == year and m == month and item.get('target'):
                targets.append(item['target'])

    if not targets:
        return {}

    targets_sorted = sorted(targets)
    n = len(targets_sorted)
    result = {
        'count':  n,
        'mean':   int(np.mean(targets_sorted)),
        'median': int(np.median(targets_sorted)),
        'min':    targets_sorted[0],
        'max':    targets_sorted[-1],
        'targets': targets_sorted,
    }
    if n >= 5:
        trim = max(1, int(n * 0.1))
        trimmed = targets_sorted[trim:-trim]
        result['trimmed_mean'] = int(np.mean(trimmed)) if trimmed else result['mean']
    else:
        result['trimmed_mean'] = result['mean']

    return result


def combined_stats(broker_list: list, year1: int, month1: int,
                   year2: int, month2: int) -> dict:
    """두 달의 합산 통계"""
    all_targets = []
    for item in broker_list:
        d = item.get('date', '')
        dm = re.search(r'(\d{2,4})[.\-/](\d{2})', d)
        if dm:
            y = int(dm.group(1))
            m = int(dm.group(2))
            if y < 100:
                y += 2000
            if ((y == year1 and m == month1) or (y == year2 and m == month2)) \
                    and item.get('target'):
                all_targets.append(item['target'])

    if not all_targets:
        return {}

    s = sorted(all_targets)
    n = len(s)
    result = {
        'count':  n,
        'mean':   int(np.mean(s)),
        'median': int(np.median(s)),
        'min':    s[0],
        'max':    s[-1],
    }
    if n >= 5:
        trim = max(1, int(n * 0.1))
        trimmed = s[trim:-trim]
        result['trimmed_mean'] = int(np.mean(trimmed)) if trimmed else result['mean']
    else:
        result['trimmed_mean'] = result['mean']

    return result


# ══════════════════════════════════════════════════════════════════════
# 4. 판단 및 포맷 헬퍼
# ══════════════════════════════════════════════════════════════════════

def verdict(price: int, target: int) -> str:
    if not price or not target:
        return '—'
    r = price / target
    if r < ANOMALY_MAX:
        return '⚠️ 이상신호'
    elif r <= STRONG_BUY_MAX:
        return '강력매수'
    elif r <= BUY_MAX:
        return '매수'
    elif r <= FAIR_MAX:
        return '적정'
    elif r <= HOLD_MAX:
        return '보류'
    else:
        return '매도'


MONTH_KR = {1:'1월', 2:'2월', 3:'3월', 4:'4월', 5:'5월', 6:'6월',
            7:'7월', 8:'8월', 9:'9월', 10:'10월', 11:'11월', 12:'12월'}


# ══════════════════════════════════════════════════════════════════════
# 5. 리포트 생성
# ══════════════════════════════════════════════════════════════════════

def generate_report(stocks_data: list, use_playwright: bool = False) -> str:
    now        = datetime.now()
    ts         = now.strftime('%Y%m%d_%H%M%S')
    cur_year   = now.year
    cur_month  = now.month
    prev_month = cur_month - 1 if cur_month > 1 else 12
    prev_year  = cur_year if cur_month > 1 else cur_year - 1

    cur_m  = MONTH_KR[cur_month]
    prev_m = MONTH_KR[prev_month]

    os.makedirs(WEEKLY_RESEARCH_DIR, exist_ok=True)
    filename = os.path.join(WEEKLY_RESEARCH_DIR, f'삼전하닉목표주가_by_Analist_{ts}.md')

    with open(filename, 'w', encoding='utf-8') as f:

        # ── 헤더 ──────────────────────────────────────────────────────
        f.write('# 삼성전자 · SK하이닉스 목표주가 기반 매수 기준\n\n')
        f.write(f'> **기준일**: {now.strftime("%Y년 %m월 %d일 %H:%M")}  \n')
        src = "네이버 금융 + FnGuide(WiseReport) 증권사별 상세 데이터" if use_playwright else "네이버 금융 (집계 컨센서스)"
        f.write(f'> **데이터 출처**: {src}\n\n')
        f.write('## 투자 판단 기준\n\n')
        f.write('| 현재가 / 목표주가 | 판단 |\n')
        f.write('|:----------------:|:----:|\n')
        f.write('| **60% 미만** | ⚠️ **이상신호** (원인 파악 우선) |\n')
        f.write('| **60 ~ 70%** | 🔴 **강력매수** |\n')
        f.write('| **70 ~ 80%** | 🟠 **매수** |\n')
        f.write('| **80 ~ 90%** | 🟡 **적정** |\n')
        f.write('| **90 ~ 100%** | ⚪ **보류** |\n')
        f.write('| **100% 초과** | 🔵 **매도** |\n')
        f.write('\n---\n\n')

        for sd in stocks_data:
            name         = sd['name']
            nv           = sd['naver']
            brokers      = sd.get('brokers', [])   # playwright로 가져온 증권사별 데이터
            research     = sd.get('research', [])  # 리서치 리포트 목록
            price        = nv.get('price', 0)
            consensus_tg = nv.get('consensus_target', 0)

            # 이번달/전달 리포트 (리서치 페이지 기반)
            cur_research  = [r for r in research if r['year'] == cur_year  and r['month'] == cur_month]
            prev_research = [r for r in research if r['year'] == prev_year and r['month'] == prev_month]

            # 이번달/전달 통계 (broker 데이터 있을 때)
            cur_stats  = monthly_stats(brokers, cur_year, cur_month)
            prev_stats = monthly_stats(brokers, prev_year, prev_month)
            comb_stats = combined_stats(brokers, prev_year, prev_month, cur_year, cur_month)

            # ── 종목 헤더 ──────────────────────────────────────────────
            f.write(f'# {name}\n\n')
            f.write(f'현재주가: **{price:,}원**\n\n')

            # ── 증권사 컨센서스 목표가 (개별 데이터 있을 때) ────────────
            if brokers:
                f.write('## 증권사 컨센서스 목표가\n\n')
                rows = []
                if prev_stats:
                    rows.append((f'{prev_m} 평균',       prev_stats.get('mean', 0),     prev_stats.get('count', 0)))
                    rows.append((f'{prev_m} 중앙값',      prev_stats.get('median', 0),   None))
                if cur_stats:
                    rows.append((f'{cur_m} 평균',        cur_stats.get('mean', 0),      cur_stats.get('count', 0)))
                    rows.append((f'{cur_m} 중앙값',       cur_stats.get('median', 0),    None))
                    if cur_stats.get('trimmed_mean') and cur_stats['count'] >= 5:
                        rows.append((f'{cur_m} 절사평균',  cur_stats['trimmed_mean'],      None))
                if comb_stats:
                    rows.append((f'{prev_m}~{cur_m} 통합 평균',    comb_stats.get('mean', 0),   comb_stats.get('count', 0)))
                    rows.append((f'{prev_m}~{cur_m} 통합 중앙값',  comb_stats.get('median', 0), None))
                    if comb_stats.get('trimmed_mean'):
                        rows.append((f'{prev_m}~{cur_m} 통합 절사평균', comb_stats['trimmed_mean'], None))

                f.write('| 구분 | 목표가 |\n|:-----|------:|\n')
                for label, tp, cnt in rows:
                    cnt_str = f' ({cnt}건)' if cnt is not None else ''
                    f.write(f'| {label}{cnt_str} | {tp:,} |\n')
                f.write('\n')

            elif consensus_tg:
                # 집계 컨센서스만 있는 경우
                f.write('## 증권사 컨센서스 목표가\n\n')
                f.write('| 구분 | 목표가 |\n|:-----|------:|\n')
                f.write(f'| 네이버 집계 평균 | {consensus_tg:,} |\n\n')
                f.write('> ℹ️ 개별 증권사 상세 데이터는 Playwright 설치 후 이용 가능\n\n')

            # ── 매수 기준 적용 ─────────────────────────────────────────
            f.write('## 매수 기준 적용\n\n')
            f.write('| 기준 | 목표가 | 🔴강력매수 (70%) | 🟠매수 (80%) | 🟡적정 (90%) | ⚪보류 (100%) | 현재가/목표가 | 판단 |\n')
            f.write('|:-----|------:|----------:|-------:|-------:|-------:|------:|:----|\n')

            criteria_rows = []
            if prev_stats and prev_stats.get('mean'):
                criteria_rows.append((f'{prev_m} 평균',         prev_stats['mean']))
                criteria_rows.append((f'{prev_m} 중앙값',        prev_stats['median']))
            if comb_stats and comb_stats.get('mean'):
                criteria_rows.append((f'{prev_m}~{cur_m} 통합 평균', comb_stats['mean']))
                criteria_rows.append((f'{prev_m}~{cur_m} 통합 중앙값', comb_stats['median']))
                if comb_stats.get('trimmed_mean'):
                    criteria_rows.append((f'{prev_m}~{cur_m} 통합 절사평균', comb_stats['trimmed_mean']))
            if cur_stats and cur_stats.get('mean'):
                criteria_rows.append((f'{cur_m} 평균',         cur_stats['mean']))
                criteria_rows.append((f'{cur_m} 중앙값',        cur_stats['median']))
                if cur_stats.get('trimmed_mean') and cur_stats['count'] >= 5:
                    criteria_rows.append((f'{cur_m} 절사평균',  cur_stats['trimmed_mean']))
            if consensus_tg and not brokers:
                criteria_rows.append(('네이버 집계 평균', consensus_tg))
            elif consensus_tg and brokers:
                criteria_rows.append(('네이버 집계 참고', consensus_tg))

            for label, tp in criteria_rows:
                if tp and price:
                    ratio = price / tp
                    v     = verdict(price, tp)
                    f.write(f'| {label} | {tp:,} | {int(tp*0.70):,} | {int(tp*0.80):,} | {int(tp*0.90):,} | {int(tp*1.00):,} | {ratio:.1%} | {v} |\n')

            f.write('\n')

            # ── 컨센서스 변화 ──────────────────────────────────────────
            if prev_stats and cur_stats and prev_stats.get('mean') and cur_stats.get('mean'):
                pm = prev_stats['mean']
                cm = cur_stats['mean']
                chg = (cm - pm) / pm * 100
                f.write('### 컨센서스 변화\n\n')
                f.write('| 구분 | 목표가 |\n|:-----|------:|\n')
                f.write(f'| {prev_m} 평균 | {pm/10000:.1f}만 원 |\n')
                f.write(f'| {cur_m} 평균 | {cm/10000:.1f}만 원 |\n')
                f.write(f'| 상승폭 | {chg:+.1f}% |\n\n')

            # ── 해석 ──────────────────────────────────────────────────
            f.write('### 해석\n\n')
            for label, tp in criteria_rows:
                v = verdict(price, tp)
                if v != '—':
                    f.write(f'* {label} → **{v}**\n')

            if price and consensus_tg:
                ratio  = price / consensus_tg
                upside = (consensus_tg - price) / price * 100
                f.write(f'* 현재 주가는 집계 컨센서스 대비 약 **{ratio:.1%}** 수준 (업사이드 **{upside:+.1f}%**)\n')

            f.write('\n')

            # ── 기본 투자 정보 ─────────────────────────────────────────
            f.write('## 기본 투자 정보\n\n')
            f.write('| 항목 | 값 |\n|:----|:---:|\n')
            if consensus_tg:
                f.write(f'| 컨센서스 목표주가 (집계) | **{consensus_tg:,}원** |\n')
            if nv.get('opinion'):
                f.write(f'| 투자의견 | {nv["opinion"]} ({nv.get("opinion_score", "—")}) |\n')
            if nv.get('w52_high'):
                f.write(f'| 52주 최고가 | {nv["w52_high"]:,}원 |\n')
            if nv.get('w52_low'):
                f.write(f'| 52주 최저가 | {nv["w52_low"]:,}원 |\n')
            if price and nv.get('w52_high') and nv.get('w52_low'):
                w52_range = nv['w52_high'] - nv['w52_low']
                w52_pos   = (price - nv['w52_low']) / w52_range * 100 if w52_range > 0 else 0
                f.write(f'| 52주 구간 내 위치 | {w52_pos:.0f}% |\n')
                f.write(f'| 고가 대비 현재 | {(price-nv["w52_high"])/nv["w52_high"]*100:+.1f}% |\n')
                f.write(f'| 저가 대비 현재 | {(price-nv["w52_low"])/nv["w52_low"]*100:+.1f}% |\n')
            if nv.get('per'):
                f.write(f'| PER (실적 기준) | {nv["per"]}배 |\n')
            if nv.get('est_per'):
                f.write(f'| 추정 PER | {nv["est_per"]}배 |\n')
            if nv.get('pbr'):
                f.write(f'| PBR | {nv["pbr"]}배 |\n')
            # ── 투자 판단 요약 행 (테이블 마지막) ──
            _rq = price / consensus_tg if (price and consensus_tg) else None
            _vq = verdict(price, consensus_tg) if (price and consensus_tg) else None
            if _rq is not None:
                f.write(f'| 목표가 대비 (집계) | **{_rq:.1%}** |\n')
                f.write(f'| **투자 판단** | {_vq} |\n')
            f.write('\n')

            # ── 투자 판단 게이지 ──
            if _rq is not None and _vq:
                _G_LABELS  = ['⚠️ 이상신호', '🔴 강력매수', '🟠 매수', '🟡 적정', '⚪ 보류', '🔵 매도']
                _G_RANGES  = ['~60%', '60~70%', '70~80%', '80~90%', '90~100%', '100%~']
                _active    = (0 if '이상신호' in _vq else
                              1 if '강력매수' in _vq else
                              2 if '매수' in _vq else
                              3 if '적정' in _vq else
                              4 if '보류' in _vq else 5)
                _markers   = [f'**▲ {_rq:.1%}**' if i == _active else '' for i in range(6)]
                f.write('### 투자 판단 현황\n\n')
                f.write('| ' + ' | '.join(_G_LABELS)  + ' |\n')
                f.write('|' + ' :---: |' * 6 + '\n')
                f.write('| ' + ' | '.join(_G_RANGES)  + ' |\n')
                f.write('| ' + ' | '.join(_markers)   + ' |\n\n')

            # ── 증권사별 목표가 상세 (Playwright로 가져온 경우) ──────────
            if brokers:
                cur_brokers  = [b for b in brokers if _is_month(b.get('date',''), cur_year, cur_month)]
                prev_brokers = [b for b in brokers if _is_month(b.get('date',''), prev_year, prev_month)]

                for mlabel, mbrokers in [(cur_m, cur_brokers), (prev_m, prev_brokers)]:
                    if not mbrokers:
                        continue
                    f.write(f'### {mlabel} 증권사 리포트 목록\n\n')
                    f.write('| 제공처 | 최종일자 | 목표가 | 직전목표가 | 변동률(%) | 투자의견 | 직전투자의견 |\n')
                    f.write('|:------:|:------:|------:|------:|:-------:|:------:|:-------:|\n')
                    for b in sorted(mbrokers, key=lambda x: x.get('date',''), reverse=True):
                        tgt       = f'{b["target"]:,}'       if b.get('target')      else '—'
                        prev_tgt  = f'{b["prev_target"]:,}'  if b.get('prev_target') else '—'
                        chg_pct   = f'{b["change_pct"]:+.1f}%' if b.get('change_pct') is not None else '—'
                        f.write(f'| {b.get("provider","—")} | {b.get("date","—")} | **{tgt}** | {prev_tgt} | {chg_pct} | {b.get("opinion","—")} | {b.get("prev_opinion","—")} |\n')
                    f.write('\n')

            # ── 리서치 리포트 활동 ─────────────────────────────────────
            if research:
                f.write(f'## 증권사 리포트 활동\n\n')
                f.write(f'| 기간 | 리포트 수 | 주요 증권사 |\n|:-----|:--------:|:----------|\n')
                cur_firms  = list(dict.fromkeys(r['firm'] for r in cur_research))
                prev_firms = list(dict.fromkeys(r['firm'] for r in prev_research))
                f.write(f'| {cur_m} | {len(cur_research)}건 | {", ".join(cur_firms[:6])} |\n')
                f.write(f'| {prev_m} | {len(prev_research)}건 | {", ".join(prev_firms[:6])} |\n')
                if prev_research:
                    chg = (len(cur_research) - len(prev_research)) / len(prev_research) * 100
                    trend = '↑ 증가' if chg > 0 else ('↓ 감소' if chg < 0 else '→ 동일')
                    f.write(f'| 전월 대비 | {chg:+.0f}% | {trend} |\n')
                f.write('\n')

                if cur_research:
                    f.write(f'### {cur_m} 최신 리포트 목록\n\n')
                    f.write('| 증권사 | 일자 | 리포트 제목 |\n|:------:|:----:|:----------|\n')
                    for r in sorted(cur_research, key=lambda x: x['date'], reverse=True):
                        f.write(f'| {r["firm"]} | {r["date"]} | {r["title"]} |\n')
                    f.write('\n')

                if prev_research:
                    f.write(f'### {prev_m} 리포트 목록\n\n')
                    f.write('| 증권사 | 일자 | 리포트 제목 |\n|:------:|:----:|:----------|\n')
                    for r in sorted(prev_research, key=lambda x: x['date'], reverse=True)[:12]:
                        f.write(f'| {r["firm"]} | {r["date"]} | {r["title"]} |\n')
                    if len(prev_research) > 12:
                        f.write(f'> *(외 {len(prev_research)-12}건)*\n')
                    f.write('\n')

            f.write('---\n\n')

        # ── 한눈에 보는 현재 위치 ─────────────────────────────────────
        f.write('# 한눈에 보는 현재 위치\n\n')
        f.write('| 종목 | 기준 | 현재가/목표가 | 판단 |\n|:-----|:-----|------:|:----|\n')
        for sd in stocks_data:
            name         = sd['name']
            nv           = sd['naver']
            brokers      = sd.get('brokers', [])
            price        = nv.get('price', 0)
            consensus_tg = nv.get('consensus_target', 0)

            prev_stats = monthly_stats(brokers, prev_year, prev_month)
            cur_stats  = monthly_stats(brokers, cur_year, cur_month)
            comb_stats = combined_stats(brokers, prev_year, prev_month, cur_year, cur_month)

            for label, tp in [
                (f'{prev_m} 평균', prev_stats.get('mean', 0)),
                (f'{prev_m}~{cur_m} 통합 평균', comb_stats.get('mean', 0)),
                (f'{cur_m} 평균', cur_stats.get('mean', 0)),
                ('네이버 집계 평균', consensus_tg),
            ]:
                if tp and price:
                    ratio = price / tp
                    v     = verdict(price, tp)
                    f.write(f'| {name} | {label} | {ratio:.1%} | {v} |\n')

        f.write('\n---\n\n')

        # ── 컨센서스 상향 추이 비교 ────────────────────────────────────
        any_broker = any(sd.get('brokers') for sd in stocks_data)
        if any_broker:
            f.write('# 컨센서스 상향 추이 비교\n\n')
            f.write(f'| 종목 | {prev_m} 평균 | {cur_m} 평균 | 상승폭 |\n')
            f.write('|:-----|-------:|-------:|------:|\n')
            for sd in stocks_data:
                name    = sd['name']
                brokers = sd.get('brokers', [])
                p_stats = monthly_stats(brokers, prev_year, prev_month)
                c_stats = monthly_stats(brokers, cur_year, cur_month)
                if p_stats.get('mean') and c_stats.get('mean'):
                    pm  = p_stats['mean']
                    cm  = c_stats['mean']
                    chg = (cm - pm) / pm * 100
                    f.write(f'| {name} | {pm/10000:.1f}만 원 | {cm/10000:.1f}만 원 | {chg:+.1f}% |\n')
            f.write('\n---\n\n')

        # ── 최종 요약 ─────────────────────────────────────────────────
        f.write('# 최종 요약\n\n')

        # 전략 테이블
        f.write(f'| 종목 | {prev_m} 기준 | 통합 기준 | {cur_m} 기준 |\n')
        f.write('|:-----|:-----|:-----|:-----|\n')
        for sd in stocks_data:
            name    = sd['name']
            brokers = sd.get('brokers', [])
            nv      = sd['naver']
            price   = nv.get('price', 0)
            ct      = nv.get('consensus_target', 0)
            p_stats = monthly_stats(brokers, prev_year, prev_month)
            c_stats = monthly_stats(brokers, cur_year, cur_month)
            co_stats= combined_stats(brokers, prev_year, prev_month, cur_year, cur_month)

            pv   = verdict(price, p_stats.get('mean', 0))   if p_stats  else verdict(price, ct)
            cv   = verdict(price, c_stats.get('mean', 0))   if c_stats  else verdict(price, ct)
            cov  = verdict(price, co_stats.get('mean', 0))  if co_stats else verdict(price, ct)
            f.write(f'| **{name}** | {pv} | {cov} | {cv} |\n')

        f.write('\n')
        f.write('## 한 줄 결론\n\n')
        for sd in stocks_data:
            name    = sd['name']
            brokers = sd.get('brokers', [])
            nv      = sd['naver']
            price   = nv.get('price', 0)
            ct      = nv.get('consensus_target', 0)
            c_stats = monthly_stats(brokers, cur_year, cur_month)

            best_tp = c_stats.get('mean') or ct
            if best_tp and price:
                ratio  = price / best_tp
                upside = (best_tp - price) / price * 100
                v      = verdict(price, best_tp)
                label  = f'{cur_m} 컨센서스' if c_stats.get('mean') else '집계 컨센서스'
                f.write(f'* **{name}**: {label} 기준 현재가는 목표가의 **{ratio:.1%}** 수준'
                        f' (업사이드 **{upside:+.1f}%**) → **{v}**\n')

        f.write('\n---\n\n')
        f.write(f'*생성: {now.strftime("%Y-%m-%d %H:%M:%S")} | '
                f'데이터: 네이버 금융 + FnGuide(WiseReport)*\n')

    return filename


def _is_month(date_str: str, year: int, month: int) -> bool:
    m = re.search(r'(\d{2,4})[.\-/](\d{2})', date_str)
    if m:
        y  = int(m.group(1))
        mo = int(m.group(2))
        if y < 100:
            y += 2000
        return y == year and mo == month
    return False


# ══════════════════════════════════════════════════════════════════════
# 6. 메인
# ══════════════════════════════════════════════════════════════════════

def main():
    print('=' * 60)
    print('  삼성전자·SK하이닉스 목표주가 컨센서스 리포트')
    print('=' * 60)
    print()

    print('[INFO] FnGuide(WiseReport) → 증권사별 상세 목표가 수집 모드')
    print()

    stocks_data = []

    for stock in STOCKS:
        code = stock['code']
        name = stock['name']
        print(f'[{name}] 데이터 수집 중...')

        nv = fetch_naver_stock_info(code)
        if nv.get('price'):
            print(f'  현재가: {nv["price"]:,}원')
        if nv.get('consensus_target'):
            print(f'  컨센서스(집계): {nv["consensus_target"]:,}원  |  의견: {nv.get("opinion","—")}')

        # FnGuide/WiseReport에서 증권사별 목표가 수집 (정적 HTML)
        brokers = fetch_wisereport_brokers(code)
        print(f'  증권사별 데이터: {len(brokers)}건')

        research = fetch_research_reports(code, pages=3)
        print(f'  리서치 리포트: {len(research)}건')

        stocks_data.append({
            'name':     name,
            'naver':    nv,
            'brokers':  brokers,
            'research': research,
        })
        print()

    filename = generate_report(stocks_data, use_playwright=any(sd['brokers'] for sd in stocks_data))
    print(f'✅ 리포트 생성 완료: {filename}')
    return filename


if __name__ == '__main__':
    main()
