"""
개별 종목 목표주가 컨센서스 리포트 생성기

사용법:
    python stock_consensus_report.py [종목명 또는 종목코드]
    예) python stock_consensus_report.py 현대차
        python stock_consensus_report.py 005380
        python stock_consensus_report.py "SK하이닉스"
        python stock_consensus_report.py 카카오

    인자 없이 실행하면 대화형 입력.

출력: results/weekly_research/{종목명}_목표주가분석_{YYYYMMDD_HHMMSS}.md

투자 판단 기준 (현재가 / 목표주가):
  < 60%         → ⚠️ 이상신호 (원인 파악 우선)
  60 ~ 70%      → 강력매수
  70 ~ 80%      → 매수
  80 ~ 90%      → 적정
  90 ~ 100%     → 보류
  100% 초과      → 매도
"""

import os
import sys
import re
import requests
import numpy as np
from bs4 import BeautifulSoup
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
from config import WEEKLY_RESEARCH_DIR

# ── 투자 판단 기준 (현재가 / 목표주가 비율) ──────────────────────────────
# 비율이 낮을수록 업사이드가 크다 (현재가가 목표가보다 훨씬 낮음)
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

MONTH_KR = {
    1:'1월', 2:'2월', 3:'3월', 4:'4월', 5:'5월', 6:'6월',
    7:'7월', 8:'8월', 9:'9월', 10:'10월', 11:'11월', 12:'12월',
}

# KRX 전체 종목 목록 (최초 1회 로드, 캐싱)
_KRX_CACHE: list = []


# ══════════════════════════════════════════════════════════════════════
# 1. 종목 검색
# ══════════════════════════════════════════════════════════════════════

def _load_krx_stocks() -> list:
    """
    KRX 상장 종목 전체 목록 로드 (코스피 + 코스닥).
    Returns list of (code, name, market).
    결과를 모듈 수준 캐시에 저장해 두 번 이상 호출되지 않도록 함.
    """
    global _KRX_CACHE
    if _KRX_CACHE:
        return _KRX_CACHE

    stocks = []
    markets = [
        ('코스피', 'https://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13&marketType=stockMkt'),
        ('코스닥', 'https://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13&marketType=kosdaqMkt'),
    ]
    for mkt, url in markets:
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(r.content.decode('euc-kr'), 'html.parser')
            for row in soup.find_all('tr')[1:]:  # 헤더 행 스킵
                cells = [c.get_text(strip=True) for c in row.find_all('td')]
                if len(cells) >= 3 and re.match(r'^\d{6}$', cells[2]):
                    stocks.append((cells[2], cells[0], mkt))  # (code, name, market)
        except Exception as e:
            print(f'[WARNING] KRX {mkt} 목록 로드 실패: {e}')

    _KRX_CACHE = stocks
    return stocks


def search_stock(query: str) -> list:
    """
    종목명 또는 6자리 코드로 검색.
    Returns list of (code, name, market).
    """
    query = query.strip()

    # ── 6자리 코드 직접 입력 ───────────────────────────────────────
    if re.match(r'^\d{6}$', query):
        name = _fetch_stock_name(query)
        return [(query, name or query, '')]

    # ── 자주 쓰는 별칭 매핑 ────────────────────────────────────────
    ALIAS = {
        '현대차': '현대자동차',
        '기아차': '기아',
        '삼전': '삼성전자',
        '하닉': 'SK하이닉스',
        '셀트리온헬스': '셀트리온헬스케어',
    }
    if query in ALIAS:
        query = ALIAS[query]

    # ── KRX 전체 목록에서 부분 일치 검색 ──────────────────────────
    print('  KRX 종목 목록 로드 중...')
    stocks = _load_krx_stocks()
    if not stocks:
        print('[WARNING] KRX 목록 로드 실패, 코드 직접 입력 필요')
        return []

    query_lower = query.lower()

    # 1순위: 정확히 일치
    exact = [(c, n, m) for c, n, m in stocks if n == query]
    if exact:
        return exact

    # 2순위: query로 시작 (이름 길이 오름차순 — 더 짧고 정확한 것 우선)
    starts = [(c, n, m) for c, n, m in stocks if n.startswith(query)]
    if starts:
        return sorted(starts, key=lambda x: len(x[1]))

    # 3순위: query 포함 (이름 길이 오름차순)
    contains = [(c, n, m) for c, n, m in stocks if query_lower in n.lower()]
    return sorted(contains, key=lambda x: len(x[1]))


def _fetch_stock_name(code: str) -> str:
    """코드 → 종목명 (네이버 금융 페이지 title 태그)"""
    try:
        url = f'https://finance.naver.com/item/coinfo.naver?code={code}'
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.encoding = 'euc-kr'
        soup = BeautifulSoup(r.text, 'html.parser')
        tag = soup.find('title')
        if tag:
            # "삼성전자 : 종목분석 : 네이버 금융"
            return tag.get_text(strip=True).split(':')[0].strip()
    except Exception:
        pass
    return code


# ══════════════════════════════════════════════════════════════════════
# 2. 데이터 수집
# ══════════════════════════════════════════════════════════════════════

def fetch_naver_stock_info(code: str) -> dict:
    """
    네이버 금융 coinfo.naver 정적 HTML 파싱.
    Returns dict: price, consensus_target, opinion, opinion_score,
                  w52_high, w52_low, per, est_per, pbr
    """
    url = f'https://finance.naver.com/item/coinfo.naver?code={code}'
    data = {}
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.encoding = 'euc-kr'
        soup = BeautifulSoup(r.text, 'html.parser')

        # 현재가 — no_up/no_dn/no_stay 태그 안에 같은 텍스트가 두 번 붙어서
        # '667,000667,000' 형태로 반복되므로, 첫 번째 콤마 포맷 숫자만 추출
        for klass in ('no_up', 'no_dn', 'no_stay'):
            tag = soup.find(class_=klass)
            if tag:
                raw = tag.get_text()
                # \d{1,3}(,\d{3})+ → 첫 번째 유효한 원화 형식 숫자
                m = re.search(r'\d{1,3}(?:,\d{3})+', raw)
                if not m:
                    m = re.search(r'\d+', raw)
                if m:
                    val = int(m.group(0).replace(',', ''))
                    if val > 0:
                        data['price'] = val
                        break

        # th/td 구조로 투자정보 파싱
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

                # PERlEPS(실적) → '25.66배l12,372원'
                elif label.startswith('PERl') and '추정' not in label:
                    m = re.match(r'^([\d.]+)배', value)
                    if m:
                        data['per'] = float(m.group(1))

                # 추정PERlEPS → '7.00배l43,584원'
                elif '추정PER' in label:
                    m = re.match(r'^([\d.]+)배', value)
                    if m:
                        data['est_per'] = float(m.group(1))

                # PBRlBPS → 'N/Al71,907원' 또는 '1.87배l...'
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

    # ── 현재가 fallback: coinfo.naver에서 못 가져왔으면 polling API 시도 ──
    if not data.get('price'):
        try:
            api_url = f'https://polling.finance.naver.com/api/realtime?query=SERVICE_ITEM:{code}'
            r2 = requests.get(api_url, headers=HEADERS, timeout=15)
            item = r2.json()['result']['areas'][0]['datas'][0]
            val = int(item.get('nv', 0))
            if val > 0:
                data['price'] = val
        except Exception as e:
            print(f'[WARNING] Naver polling API 현재가 fallback 실패 ({code}): {e}')

    return data


def fetch_wisereport_brokers(code: str) -> list:
    """
    FnGuide/WiseReport 정적 HTML → 증권사별 목표가 목록.
    Returns list of dict: {provider, date, target, prev_target, change_pct, opinion, prev_opinion}
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
            hdr = tbl.get_text()[:150]
            if '제공처' not in hdr and '목표가' not in hdr:
                continue

            for row in tbl.find_all('tr')[1:]:  # 헤더 행 스킵
                cells = [c.get_text(strip=True) for c in row.find_all(['th', 'td'])]
                if len(cells) < 3:
                    continue

                target = _int(cells[2])
                if not target or target < 100:
                    continue

                # '26/06/08' → '2026/06/08'
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
                break

    except Exception as e:
        print(f'[WARNING] WiseReport 수집 실패 ({code}): {e}')
    return results


def fetch_research_reports(code: str, pages: int = 3) -> list:
    """네이버 리서치 페이지 → 최근 리포트 목록"""
    base_url = 'https://finance.naver.com/research/company_list.naver'
    reports = []

    for page in range(1, pages + 1):
        try:
            params = {'searchType': 'itemCode', 'itemCode': code, 'page': page}
            r = requests.get(base_url, params=params, headers=HEADERS, timeout=15)
            r.encoding = 'euc-kr'
            soup = BeautifulSoup(r.text, 'html.parser')

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
                date_text = texts[4] if len(texts) > 4 else (texts[3] if len(texts) > 3 else '')
                dm = re.match(r'(\d{2})\.(\d{2})\.(\d{2})', date_text)
                if not dm:
                    continue

                yr    = 2000 + int(dm.group(1))
                mo    = int(dm.group(2))
                dy    = int(dm.group(3))
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
            print(f'[WARNING] 리서치 페이지 오류 (p{page}): {e}')
            break

    return reports


# ══════════════════════════════════════════════════════════════════════
# 3. 통계 헬퍼
# ══════════════════════════════════════════════════════════════════════

def _monthly_stats(broker_list: list, year: int, month: int) -> dict:
    targets = []
    for item in broker_list:
        dm = re.search(r'(\d{4})[/\-.](\d{2})', item.get('date', ''))
        if dm and int(dm.group(1)) == year and int(dm.group(2)) == month:
            if item.get('target'):
                targets.append(item['target'])

    if not targets:
        return {}
    s = sorted(targets)
    n = len(s)
    res = {
        'count':  n,
        'mean':   int(np.mean(s)),
        'median': int(np.median(s)),
        'min':    s[0],
        'max':    s[-1],
    }
    if n >= 5:
        trim = max(1, int(n * 0.1))
        trimmed = s[trim:-trim]
        res['trimmed_mean'] = int(np.mean(trimmed)) if trimmed else res['mean']
    else:
        res['trimmed_mean'] = res['mean']
    return res


def _combined_stats(broker_list, y1, m1, y2, m2) -> dict:
    targets = []
    for item in broker_list:
        dm = re.search(r'(\d{4})[/\-.](\d{2})', item.get('date', ''))
        if dm:
            y, m = int(dm.group(1)), int(dm.group(2))
            if ((y == y1 and m == m1) or (y == y2 and m == m2)) and item.get('target'):
                targets.append(item['target'])
    if not targets:
        return {}
    s = sorted(targets)
    n = len(s)
    res = {
        'count':  n,
        'mean':   int(np.mean(s)),
        'median': int(np.median(s)),
        'min':    s[0],
        'max':    s[-1],
    }
    if n >= 5:
        trim = max(1, int(n * 0.1))
        trimmed = s[trim:-trim]
        res['trimmed_mean'] = int(np.mean(trimmed)) if trimmed else res['mean']
    else:
        res['trimmed_mean'] = res['mean']
    return res


def _verdict(price: int, target: int) -> str:
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


def _is_month(date_str, year, month) -> bool:
    dm = re.search(r'(\d{4})[/\-.](\d{2})', date_str)
    return bool(dm) and int(dm.group(1)) == year and int(dm.group(2)) == month


# ══════════════════════════════════════════════════════════════════════
# 4. 리포트 생성
# ══════════════════════════════════════════════════════════════════════

def generate_report(name: str, code: str,
                    nv: dict, brokers: list, research: list) -> str:
    now        = datetime.now()
    ts         = now.strftime('%Y%m%d_%H%M%S')
    cur_year   = now.year
    cur_month  = now.month
    prev_month = cur_month - 1 if cur_month > 1 else 12
    prev_year  = cur_year if cur_month > 1 else cur_year - 1

    cur_m  = MONTH_KR[cur_month]
    prev_m = MONTH_KR[prev_month]

    price        = nv.get('price', 0)
    consensus_tg = nv.get('consensus_target', 0)

    cur_research  = [r for r in research if r['year'] == cur_year  and r['month'] == cur_month]
    prev_research = [r for r in research if r['year'] == prev_year and r['month'] == prev_month]

    cur_stats  = _monthly_stats(brokers, cur_year, cur_month)
    prev_stats = _monthly_stats(brokers, prev_year, prev_month)
    comb_stats = _combined_stats(brokers, prev_year, prev_month, cur_year, cur_month)

    safe_name = re.sub(r'[\\/:*?"<>|]', '_', name)
    os.makedirs(WEEKLY_RESEARCH_DIR, exist_ok=True)
    filename = os.path.join(WEEKLY_RESEARCH_DIR, f'{safe_name}_목표주가분석_{ts}.md')

    with open(filename, 'w', encoding='utf-8') as f:

        # ── 헤더 ──────────────────────────────────────────────────────
        f.write(f'# {name} ({code}) 목표주가 컨센서스 분석\n\n')
        f.write(f'> **기준일**: {now.strftime("%Y년 %m월 %d일 %H:%M")}  \n')
        f.write(f'> **데이터 출처**: 네이버 금융 + FnGuide(WiseReport)\n\n')
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

        # ── 현재 시세 ─────────────────────────────────────────────────
        f.write('## 현재 시세\n\n')
        f.write('| 항목 | 값 |\n|:----|:---:|\n')
        if price:
            f.write(f'| 현재주가 | **{price:,}원** |\n')
        if consensus_tg:
            f.write(f'| 집계 컨센서스 목표주가 | **{consensus_tg:,}원** |\n')
        if nv.get('opinion'):
            f.write(f'| 투자의견 | {nv["opinion"]} ({nv.get("opinion_score", "—")}) |\n')
        if nv.get('w52_high'):
            f.write(f'| 52주 최고가 | {nv["w52_high"]:,}원 |\n')
        if nv.get('w52_low'):
            f.write(f'| 52주 최저가 | {nv["w52_low"]:,}원 |\n')
        if price and nv.get('w52_high') and nv.get('w52_low'):
            rng = nv['w52_high'] - nv['w52_low']
            if rng > 0:
                pos = (price - nv['w52_low']) / rng * 100
                f.write(f'| 52주 구간 내 위치 | {pos:.0f}% |\n')
                f.write(f'| 고가 대비 현재 | {(price - nv["w52_high"]) / nv["w52_high"] * 100:+.1f}% |\n')
                f.write(f'| 저가 대비 현재 | {(price - nv["w52_low"]) / nv["w52_low"] * 100:+.1f}% |\n')
        if nv.get('per'):
            f.write(f'| PER (실적 기준) | {nv["per"]}배 |\n')
        if nv.get('est_per'):
            f.write(f'| 추정 PER | {nv["est_per"]}배 |\n')
        if nv.get('pbr'):
            f.write(f'| PBR | {nv["pbr"]}배 |\n')
        # ── 투자 판단 요약 행 (테이블 마지막) ──
        _rq = price / consensus_tg if (price and consensus_tg) else None
        _vq = _verdict(price, consensus_tg) if (price and consensus_tg) else None
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

        # ── 컨센서스 목표가 통계 ──────────────────────────────────────
        if brokers:
            f.write('## 증권사 컨센서스 목표가\n\n')
            rows = []
            if prev_stats:
                rows += [
                    (f'{prev_m} 평균',  prev_stats['mean'],   prev_stats['count']),
                    (f'{prev_m} 중앙값', prev_stats['median'], None),
                ]
            if cur_stats:
                rows += [
                    (f'{cur_m} 평균',  cur_stats['mean'],   cur_stats['count']),
                    (f'{cur_m} 중앙값', cur_stats['median'], None),
                ]
                if cur_stats.get('count', 0) >= 5:
                    rows.append((f'{cur_m} 절사평균', cur_stats['trimmed_mean'], None))
            if comb_stats:
                rows += [
                    (f'{prev_m}~{cur_m} 통합 평균',  comb_stats['mean'],   comb_stats['count']),
                    (f'{prev_m}~{cur_m} 통합 중앙값', comb_stats['median'], None),
                ]
                if comb_stats.get('count', 0) >= 5:
                    rows.append((f'{prev_m}~{cur_m} 통합 절사평균', comb_stats['trimmed_mean'], None))
            if consensus_tg:
                rows.append(('네이버 집계 참고', consensus_tg, None))

            f.write('| 구분 | 목표가 |\n|:-----|------:|\n')
            for label, tp, cnt in rows:
                cnt_str = f' ({cnt}건)' if cnt is not None else ''
                f.write(f'| {label}{cnt_str} | {tp:,} |\n')
            f.write('\n')

        elif consensus_tg:
            f.write('## 증권사 컨센서스 목표가\n\n')
            f.write('| 구분 | 목표가 |\n|:-----|------:|\n')
            f.write(f'| 네이버 집계 평균 | {consensus_tg:,} |\n\n')
            f.write('> ℹ️ 증권사 개별 목표가 미수집 (커버리지 없음)\n\n')

        else:
            f.write('## 증권사 컨센서스 목표가\n\n')
            f.write('> ⚠️ 이 종목에 대한 애널리스트 커버리지 데이터가 없습니다.\n\n')

        # ── 매수 기준 적용 ─────────────────────────────────────────────
        f.write('## 매수 기준 적용\n\n')
        f.write('| 기준 | 목표가 | 🔴강력매수 (70%) | 🟠매수 (80%) | 🟡적정 (90%) | ⚪보류 (100%) | 현재가/목표가 | 판단 |\n')
        f.write('|:-----|------:|----------:|-------:|-------:|-------:|------:|:----| \n')

        criteria = []
        if prev_stats and prev_stats.get('mean'):
            criteria += [
                (f'{prev_m} 평균',  prev_stats['mean']),
                (f'{prev_m} 중앙값', prev_stats['median']),
            ]
        if comb_stats and comb_stats.get('mean'):
            criteria.append((f'{prev_m}~{cur_m} 통합 평균', comb_stats['mean']))
            if comb_stats.get('count', 0) >= 5:
                criteria.append((f'{prev_m}~{cur_m} 통합 절사평균', comb_stats['trimmed_mean']))
        if cur_stats and cur_stats.get('mean'):
            criteria += [
                (f'{cur_m} 평균',  cur_stats['mean']),
                (f'{cur_m} 중앙값', cur_stats['median']),
            ]
            if cur_stats.get('count', 0) >= 5:
                criteria.append((f'{cur_m} 절사평균', cur_stats['trimmed_mean']))
        if consensus_tg:
            label = '네이버 집계 참고' if brokers else '네이버 집계 평균'
            criteria.append((label, consensus_tg))

        for label, tp in criteria:
            if tp and price:
                ratio = price / tp
                v     = _verdict(price, tp)
                f.write(f'| {label} | {tp:,} | {int(tp * 0.70):,} | {int(tp * 0.80):,} | {int(tp * 0.90):,} | {int(tp * 1.00):,} | {ratio:.1%} | {v} |\n')

        f.write('\n')

        # ── 컨센서스 변화 ──────────────────────────────────────────────
        if prev_stats and cur_stats and prev_stats.get('mean') and cur_stats.get('mean'):
            pm  = prev_stats['mean']
            cm  = cur_stats['mean']
            chg = (cm - pm) / pm * 100
            arrow = '⬆' if chg > 5 else ('⬇' if chg < -5 else '→')
            f.write('### 컨센서스 변화\n\n')
            f.write('| 구분 | 목표가 |\n|:-----|------:|\n')
            f.write(f'| {prev_m} 평균 ({prev_stats["count"]}건) | {pm:,} |\n')
            f.write(f'| {cur_m} 평균 ({cur_stats["count"]}건) | {cm:,} |\n')
            f.write(f'| 변화폭 | {arrow} {chg:+.1f}% |\n\n')

        # ── 한 줄 결론 ─────────────────────────────────────────────────
        f.write('### 한 줄 결론\n\n')
        best_tp = (cur_stats.get('mean') or comb_stats.get('mean')
                   or prev_stats.get('mean') or consensus_tg)
        if best_tp and price:
            ratio  = price / best_tp
            upside = (best_tp - price) / price * 100
            v      = _verdict(price, best_tp)
            label_used = (f'{cur_m} 컨센서스' if cur_stats.get('mean')
                          else ('통합 컨센서스' if comb_stats.get('mean')
                          else (f'{prev_m} 컨센서스' if prev_stats.get('mean')
                          else '집계 컨센서스')))
            f.write(f'> {label_used} 기준 현재가는 목표가의 **{ratio:.1%}** 수준 '
                    f'(업사이드 **{upside:+.1f}%**) → **{v}**\n\n')
        f.write('---\n\n')

        # ── 증권사별 목표가 상세 ────────────────────────────────────────
        if brokers:
            for mlabel, yr_, mo_ in [
                (cur_m,  cur_year,  cur_month),
                (prev_m, prev_year, prev_month),
            ]:
                mb = [b for b in brokers if _is_month(b.get('date', ''), yr_, mo_)]
                if not mb:
                    continue
                f.write(f'## {mlabel} 증권사 목표가 상세\n\n')
                f.write('| 제공처 | 최종일자 | 목표가 | 직전목표가 | 변동률 | 투자의견 |\n')
                f.write('|:------:|:-------:|------:|------:|:------:|:------:|\n')
                for b in sorted(mb, key=lambda x: x.get('date', ''), reverse=True):
                    tgt      = f'{b["target"]:,}'      if b.get('target')      else '—'
                    prev_tgt = f'{b["prev_target"]:,}' if b.get('prev_target') else '—'
                    chg_pct  = f'{b["change_pct"]:+.1f}%' if b.get('change_pct') is not None else '—'
                    f.write(f'| {b.get("provider","—")} | {b.get("date","—")} | **{tgt}** | {prev_tgt} | {chg_pct} | {b.get("opinion","—")} |\n')
                f.write('\n')

        # ── 리서치 리포트 활동 ─────────────────────────────────────────
        if research:
            f.write('## 증권사 리포트 활동\n\n')
            cur_firms  = list(dict.fromkeys(r['firm'] for r in cur_research))
            prev_firms = list(dict.fromkeys(r['firm'] for r in prev_research))
            f.write('| 기간 | 건수 | 주요 증권사 |\n|:-----|:---:|:----------|\n')
            f.write(f'| {cur_m} | {len(cur_research)}건 | {", ".join(cur_firms[:6])} |\n')
            f.write(f'| {prev_m} | {len(prev_research)}건 | {", ".join(prev_firms[:6])} |\n')
            if prev_research:
                chg = (len(cur_research) - len(prev_research)) / len(prev_research) * 100
                trend = '↑ 증가' if chg > 0 else ('↓ 감소' if chg < 0 else '→ 동일')
                f.write(f'| 전월 대비 | {chg:+.0f}% | {trend} |\n')
            f.write('\n')

            if cur_research:
                f.write(f'### {cur_m} 최신 리포트\n\n')
                f.write('| 증권사 | 일자 | 제목 |\n|:------:|:----:|:----|\n')
                for r in sorted(cur_research, key=lambda x: x['date'], reverse=True):
                    f.write(f'| {r["firm"]} | {r["date"]} | {r["title"]} |\n')
                f.write('\n')

            if prev_research:
                f.write(f'### {prev_m} 리포트\n\n')
                f.write('| 증권사 | 일자 | 제목 |\n|:------:|:----:|:----|\n')
                for r in sorted(prev_research, key=lambda x: x['date'], reverse=True)[:15]:
                    f.write(f'| {r["firm"]} | {r["date"]} | {r["title"]} |\n')
                if len(prev_research) > 15:
                    f.write(f'> *(외 {len(prev_research) - 15}건)*\n')
                f.write('\n')

        elif not research and not brokers and not consensus_tg:
            f.write('> ⚠️ 이 종목에 대한 증권사 리포트가 없습니다.\n\n')

        f.write('---\n\n')
        f.write(f'*생성: {now.strftime("%Y-%m-%d %H:%M:%S")} | '
                f'종목코드: {code} | 데이터: 네이버 금융 + FnGuide(WiseReport)*\n')

    return filename


# ══════════════════════════════════════════════════════════════════════
# 5. 메인
# ══════════════════════════════════════════════════════════════════════

def main():
    print('=' * 60)
    print('  개별 종목 목표주가 컨센서스 리포트')
    print('=' * 60)
    print()

    # ── 입력 처리 ──────────────────────────────────────────────────
    if len(sys.argv) >= 2:
        query = ' '.join(sys.argv[1:]).strip()
    else:
        print('  종목명 또는 종목코드를 입력하세요.')
        print('  예) 현대차  /  005380  /  카카오  /  NAVER  /  SK하이닉스')
        print()
        query = input('▶ 입력: ').strip()

    if not query:
        print('[ERROR] 입력값이 없습니다.')
        sys.exit(1)

    print(f'[검색] {query!r} ...')
    candidates = search_stock(query)

    if not candidates:
        print(f'[ERROR] 종목을 찾을 수 없습니다: {query!r}')
        sys.exit(1)

    # ── 복수 후보 시 선택 ──────────────────────────────────────────
    if len(candidates) == 1:
        code, name, market = candidates[0]
    else:
        print(f'\n검색 결과 {len(candidates)}건:')
        for i, (c, n, mkt) in enumerate(candidates[:10], 1):
            print(f'  [{i}] {n}  ({c})  {mkt}')
        print()
        while True:
            sel = input(f'번호를 선택하세요 (1~{min(len(candidates), 10)}): ').strip()
            if re.match(r'^\d+$', sel):
                idx = int(sel) - 1
                if 0 <= idx < min(len(candidates), 10):
                    code, name, market = candidates[idx]
                    break
            print('올바른 번호를 입력하세요.')

    print(f'\n[분석 대상] {name}  ({code})\n')

    # ── 데이터 수집 ────────────────────────────────────────────────
    print('  투자정보 수집 중...')
    nv = fetch_naver_stock_info(code)
    if nv.get('price'):
        print(f'  현재가: {nv["price"]:,}원')
    if nv.get('consensus_target'):
        print(f'  집계 컨센서스: {nv["consensus_target"]:,}원  |  의견: {nv.get("opinion","—")}')

    print('  증권사별 목표가 수집 중...')
    brokers = fetch_wisereport_brokers(code)
    print(f'  증권사별 데이터: {len(brokers)}건')

    print('  리서치 리포트 수집 중...')
    research = fetch_research_reports(code, pages=3)
    print(f'  리서치 리포트: {len(research)}건')
    print()

    filename = generate_report(name, code, nv, brokers, research)
    print(f'[완료] 리포트 생성 완료: {filename}')

    try:
        os.startfile(filename)
    except Exception:
        pass

    return filename


if __name__ == '__main__':
    main()
