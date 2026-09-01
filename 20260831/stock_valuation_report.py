"""
삼성전자 · SK하이닉스 밸류에이션 분석 리포트 생성기
- Forward PER 중심 분석 (싸이클 산업 특성 반영)
- PER/PBR Band 분석 (시각화)
- 적정주가 산출 (Forward EPS/BPS 기반)
- 저평가/고평가 판단
- 컨센서스 대비 분석
- 네이버금융 + wisereport 자동 크롤링으로 실시간 데이터 반영
"""

import os
import re
import time
import requests
from datetime import datetime
from bs4 import BeautifulSoup

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

# ── 한글 폰트 설정 ──
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://finance.naver.com/",
}


def _parse_number(text):
    """숫자 문자열 파싱 (콤마, 공백, 한국어 단위 제거)"""
    if not text:
        return None
    text = text.strip().replace(",", "").replace(" ", "")
    # 한국어 단위 제거
    for suffix in ["원", "억원", "억", "배", "%", "주"]:
        text = text.replace(suffix, "")
    # 음수 처리
    if text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1]
    try:
        return float(text)
    except (ValueError, TypeError):
        return None


def _fetch_naver_basic(code):
    """네이버금융에서 현재주가, 52주고저, PER/PBR/EPS/BPS 등 기본 데이터 수집"""
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    try:
        r = requests.get(url, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print(f"    [WARN] 네이버금융 접속 실패 ({code}): {e}")
        return {}

    result = {}

    # 현재가
    price_tag = soup.select_one(".no_today .blind")
    if price_tag:
        result["price"] = _parse_number(price_tag.text)

    # 52주 고저
    for em_tag in soup.select(".tab_con1 td em"):
        pass  # complex structure, use aside instead

    # aside 투자정보 테이블에서 PER/PBR/EPS/BPS/52주/시총/외국인/배당
    for table in soup.select("table"):
        for tr in table.select("tr"):
            tds = tr.select("td")
            ths = tr.select("th")
            text = tr.get_text(" ", strip=True)

            if "52주최고" in text and "최저" in text:
                nums = re.findall(r"[\d,]+", text)
                # "52주최고 l 최저 223,000 l 52,900" → skip "52" prefix
                prices = [_parse_number(n) for n in nums if _parse_number(n) and _parse_number(n) > 100]
                if len(prices) >= 2:
                    result["52w_high"] = max(prices[:2])
                    result["52w_low"] = min(prices[:2])

            # PER (trailing)
            if "PER" in text and "EPS" in text and "추정" not in text and "동일" not in text:
                nums = re.findall(r"[\d,.]+", text)
                # PER = first decimal that is NOT a year (20xx.xx)
                for i, n in enumerate(nums):
                    v = _parse_number(n)
                    if "." in n and v and not (2000 <= v <= 2099):
                        result["per_current"] = v
                        break
                # EPS: last big integer
                for n in reversed(nums):
                    v = _parse_number(n)
                    if v and v > 100:
                        result["trailing_eps"] = v
                        break

            # 추정 PER (12M Forward)
            if "추정PER" in text or "추정 PER" in text:
                nums = re.findall(r"[\d,.]+", text)
                for n in nums:
                    if "." in n:
                        result["per_12m"] = _parse_number(n)
                        break
                for n in reversed(nums):
                    v = _parse_number(n)
                    if v and v > 100:
                        result["consensus_eps_naver"] = v
                        break

            if "PBR" in text and "BPS" in text:
                nums = re.findall(r"[\d,.]+", text)
                for n in nums:
                    v = _parse_number(n)
                    if "." in n and v and not (2000 <= v <= 2099):
                        result["pbr_current"] = v
                        break
                for n in reversed(nums):
                    v = _parse_number(n)
                    if v and v > 100:
                        result["trailing_bps"] = v
                        break

            if "시가총액" in text:
                nums = re.findall(r"[\d,]+", text)
                for n in nums:
                    v = _parse_number(n)
                    if v and v > 10000:
                        result["market_cap_억"] = v
                        break

            if "외국인" in text and "지분" in text:
                nums = re.findall(r"[\d.]+", text)
                for n in nums:
                    v = _parse_number(n)
                    if v and 0 < v < 100:
                        result["foreign_ratio"] = v
                        break

            if "배당수익률" in text:
                nums = re.findall(r"[\d.]+", text)
                for n in nums:
                    v = _parse_number(n)
                    if v and 0 < v < 20:
                        result["dividend_yield"] = v
                        break

            # 목표주가 (네이버 투자의견)
            if "목표주가" in text:
                nums = re.findall(r"[\d,]+", text)
                # 가장 큰 숫자가 목표주가
                prices = [_parse_number(n) for n in nums if _parse_number(n) and _parse_number(n) > 1000]
                if prices:
                    result["target_price"] = max(prices)

    return result


def _fetch_wisereport(code):
    """네이버 wisereport에서 컨센서스 + Forward 지표 수집 (종목별 정확)"""
    url = (f"https://navercomp.wisereport.co.kr/v2/company/"
           f"c1010001.aspx?cmp_cd={code}")
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print(f"    [WARN] wisereport 접속 실패 ({code}): {e}")
        return {}

    result = {}

    # 주요지표 테이블: PER, PBR, EPS, BPS 등 (trailing + 26E)
    # "주요지표"가 포함된 테이블을 찾아야 함 (table 0에는 EPS/PER가 있지만 th/td 구조가 아님)
    for table in soup.select("table"):
        txt = table.get_text(" ", strip=True)
        if "주요지표" not in txt:
            continue
        rows = table.select("tr")
        for row in rows:
            ths = row.select("th")
            tds = row.select("td")
            if not ths or not tds:
                continue
            label = ths[0].text.strip()
            vals = [_parse_number(td.text) for td in tds]

            if label == "PER" and len(vals) >= 2:
                result["per_trailing"] = vals[0]
                result["per_26e"] = vals[1]
            elif label == "PBR" and len(vals) >= 2:
                result["pbr_trailing"] = vals[0]
                result["pbr_26e"] = vals[1]
            elif label == "EPS" and len(vals) >= 2:
                result["eps_trailing"] = vals[0]
                result["eps_26e"] = vals[1]
            elif label == "BPS" and len(vals) >= 2:
                result["bps_trailing"] = vals[0]
                result["bps_26e"] = vals[1]
            elif label == "현금DPS" and len(vals) >= 2:
                result["dps_trailing"] = vals[0]
                result["dps_26e"] = vals[1]
            elif label == "현금배당수익률" and len(vals) >= 2:
                result["div_yield_trailing"] = vals[0]
                result["div_yield_26e"] = vals[1]
            elif label == "EBITDA" and len(vals) >= 2:
                result["ebitda_trailing"] = vals[0]
                result["ebitda_26e"] = vals[1]
        break  # found the right table

    # 투자의견 컨센서스 테이블 (목표주가, EPS, PER 등)
    for table in soup.select("table"):
        txt = table.get_text(" ", strip=True)
        if "투자의견" in txt and "목표주가" in txt and "추정기관수" in txt:
            rows = table.select("tr")
            if len(rows) >= 2:
                cells = rows[1].select("td") if rows[1].select("td") else rows[0].select("td")
                if not cells:
                    cells = rows[0].select("td")
                # Find all numbers in the row
                all_text = rows[-1].get_text(" ", strip=True)
                nums = re.findall(r"[\d,]+", all_text)
                prices = [_parse_number(n) for n in nums if _parse_number(n) and _parse_number(n) > 10000]
                if prices:
                    result["target_price_wr"] = max(prices)
            break

    return result


def fetch_stock_data(code, name):
    """종목 데이터 자동 수집 (네이버금융 + wisereport)"""
    print(f"  📡 {name} ({code}) 데이터 수집 중...")

    naver = _fetch_naver_basic(code)
    time.sleep(0.5)
    wisereport = _fetch_wisereport(code)

    return {
        "naver": naver,
        "wisereport": wisereport,
    }


def update_stock_dict(stock, fetched):
    """기존 STOCKS 딕셔너리를 크롤링 데이터로 업데이트 (가져온 값만 덮어씀)"""
    nv = fetched.get("naver", {})
    wr = fetched.get("wisereport", {})

    updated = []

    # 현재 주가 (네이버)
    new_price = nv.get("price")
    if new_price and new_price > 0:
        stock["price"] = int(new_price)
        updated.append("price")

    # 52주 고저
    if nv.get("52w_high"):
        stock["52w_high"] = int(nv["52w_high"])
        updated.append("52w_high")
    if nv.get("52w_low"):
        stock["52w_low"] = int(nv["52w_low"])
        updated.append("52w_low")

    # 시가총액
    if nv.get("market_cap_억"):
        stock["market_cap_억"] = int(nv["market_cap_억"])
        updated.append("market_cap")

    # 외국인 지분율
    if nv.get("foreign_ratio"):
        stock["foreign_ratio"] = nv["foreign_ratio"]
        updated.append("foreign_ratio")

    # PER/PBR (trailing) - wisereport 우선, 네이버 fallback
    per_t = wr.get("per_trailing") or nv.get("per_current")
    if per_t:
        stock["per_current"] = per_t
        updated.append("per_current")
    pbr_t = wr.get("pbr_trailing") or nv.get("pbr_current")
    if pbr_t:
        stock["pbr_current"] = pbr_t
        updated.append("pbr_current")
    if nv.get("per_12m"):
        stock["per_12m"] = nv["per_12m"]
        updated.append("per_12m")

    # 배당수익률
    div_y = wr.get("div_yield_trailing") or nv.get("dividend_yield")
    if div_y:
        stock["dividend_yield"] = div_y
        updated.append("dividend_yield")

    # 목표주가 (네이버)
    if nv.get("target_price"):
        stock["target_price"] = int(nv["target_price"])
        updated.append("target_price")

    # ── wisereport 컨센서스 (26E) ──
    if wr.get("eps_26e"):
        stock["consensus_26_eps"] = int(wr["eps_26e"])
        stock["consensus_eps"] = int(wr["eps_26e"])
        updated.append("consensus_26_eps")
    if wr.get("bps_26e"):
        stock["consensus_26_bps"] = int(wr["bps_26e"])
        updated.append("consensus_26_bps")
    if wr.get("per_26e"):
        stock["consensus_per"] = wr["per_26e"]
        updated.append("consensus_per")
    if wr.get("eps_trailing"):
        stock["trailing_eps"] = int(wr["eps_trailing"])
        updated.append("trailing_eps")
    if wr.get("bps_trailing"):
        stock["trailing_bps"] = int(wr["bps_trailing"])
        updated.append("trailing_bps")

    # ROE 추정 (BPS 기반)
    if wr.get("eps_26e") and wr.get("bps_26e") and wr["bps_26e"] > 0:
        stock["consensus_26_roe"] = round(wr["eps_26e"] / wr["bps_26e"] * 100, 1)
        updated.append("consensus_26_roe")
    if wr.get("eps_trailing") and wr.get("bps_trailing") and wr["bps_trailing"] > 0:
        stock["roe_current"] = round(wr["eps_trailing"] / wr["bps_trailing"] * 100, 1)
        updated.append("roe_current")

    return updated

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 종목 데이터 (CSV + FnGuide에서 추출)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STOCKS = {
    "삼성전자": {
        "code": "A005930",
        "price": 183500,
        "market_cap_억": 10862536,
        "52w_high": 218000,
        "52w_low": 53000,
        "foreign_ratio": 49.58,
        # 현재 지표 (FnGuide 기준)
        "per_current": 27.96,      # FnGuide Snapshot PER
        "per_12m": 7.43,            # 12M Forward PER
        "pbr_current": 2.87,        # FnGuide Snapshot PBR
        "roe_current": 10.85,
        "dividend_yield": 0.91,
        # 컨센서스
        "consensus": "Buy (4.0)",
        "target_price": 248240,
        "consensus_eps": 23794,     # 26년E EPS
        "consensus_per": 7.7,
        # 히스토리컬 PER (연간 CSV)
        "per_history": {
            "16년": 11.31, "17년": 7.96, "18년": 5.26, "19년": 15.49,
            "20년": 18.53, "21년": 11.91, "22년": 6.03, "23년": 32.38,
            "24년": 9.45, "25년4Q(E)": 24.54,
        },
        # 히스토리컬 PBR (연간 CSV)
        "pbr_history": {
            "16년": 1.36, "17년": 1.59, "18년": 0.96, "19년": 1.31,
            "20년": 1.81, "21년": 1.58, "22년": 0.96, "23년": 1.33,
            "24년": 0.81, "25년4Q(E)": 2.56,
        },
        # EPS 히스토리 (연간 CSV)
        "eps_history": {
            "16년": 3187, "17년": 6405, "18년": 7352, "19년": 3602,
            "20년": 4370, "21년": 6574, "22년": 9168, "23년": 2424,
            "24년": 5632, "25년4Q(E)": 7477,
        },
        # BPS 히스토리 (연간 CSV)
        "bps_history": {
            "16년": 26503, "17년": 32102, "18년": 40214, "19년": 42701,
            "20년": 44838, "21년": 49623, "22년": 57822, "23년": 59170,
            "24년": 65612, "25년4Q(E)": 71679,
        },
        # ROE 히스토리
        "roe_history": {
            "16년": 12.02, "17년": 19.95, "18년": 18.28, "19년": 8.44,
            "20년": 9.75, "21년": 13.25, "22년": 15.86, "23년": 4.10,
            "24년": 8.58, "25년4Q(E)": 10.43,
        },
        # 주가 히스토리 (연말)
        "price_history": {
            "16년": 36040, "17년": 50960, "18년": 38700, "19년": 55800,
            "20년": 81000, "21년": 78300, "22년": 55300, "23년": 78500,
            "24년": 53200, "25년현재": 183500,
        },
        # 고저 PER/PBR
        "per_high": 32.38, "per_low": 5.26,
        "pbr_high": 2.56, "pbr_low": 0.81,
        # 5년 평균
        "per_5y_avg": 12.70, "pbr_5y_avg": 1.28,
        "roe_5y_avg": 10.29, "opm_5y_avg": 11.80,
        # 실적 (25년4Q 연환산)
        "revenue": 3336059,
        "op_income": 436012,
        "net_income": 442610,
        "opm": 13.07,
        # FnGuide 26년 컨센서스
        "consensus_26_revenue": 5159507,
        "consensus_26_op": 1925789,
        "consensus_26_ni": 1602675,
        "consensus_26_eps": 23794,
        "consensus_26_bps": 85588,
        "consensus_26_roe": 32.24,
    },
    "SK하이닉스": {
        "code": "A000660",
        "price": 910000,
        "market_cap_억": 6485592,
        "52w_high": 1099000,
        "52w_low": 164800,
        "foreign_ratio": 53.51,
        # 현재 지표
        "per_current": 15.44,
        "per_12m": 4.86,
        "pbr_current": 5.43,
        "roe_current": 44.15,
        "dividend_yield": 0.33,
        # 컨센서스
        "consensus": "Buy (4.0)",
        "target_price": 1325600,
        "consensus_eps": 181883,
        "consensus_per": 5.0,
        # 히스토리컬 PER
        "per_history": {
            "16년": 11.02, "17년": 5.23, "18년": 2.83, "19년": 34.15,
            "20년": 18.14, "21년": 9.93, "22년": 24.49, "23년": -11.30,
            "24년": 6.40, "25년4Q(E)": 15.11,
        },
        # 히스토리컬 PBR
        "pbr_history": {
            "16년": 1.35, "17년": 1.65, "18년": 0.94, "19년": 1.43,
            "20년": 1.66, "21년": 1.53, "22년": 0.86, "23년": 1.93,
            "24년": 1.71, "25년4Q(E)": 5.38,
        },
        # EPS 히스토리
        "eps_history": {
            "16년": 4057, "17년": 14617, "18년": 21346, "19년": 2755,
            "20년": 6532, "21년": 13190, "22년": 3063, "23년": -12517,
            "24년": 27182, "25년4Q(E)": 60221,
        },
        # BPS 히스토리
        "bps_history": {
            "16년": 32990, "17년": 46449, "18년": 64348, "19년": 65825,
            "20년": 71275, "21년": 85380, "22년": 86904, "23년": 73495,
            "24년": 101515, "25년4Q(E)": 169098,
        },
        # ROE 히스토리
        "roe_history": {
            "16년": 12.30, "17년": 31.47, "18년": 33.17, "19년": 4.19,
            "20년": 9.16, "21년": 15.45, "22년": 3.52, "23년": -17.03,
            "24년": 26.78, "25년4Q(E)": 35.61,
        },
        # 주가 히스토리
        "price_history": {
            "16년": 44700, "17년": 76500, "18년": 60500, "19년": 94100,
            "20년": 118500, "21년": 131000, "22년": 75000, "23년": 141500,
            "24년": 173900, "25년현재": 910000,
        },
        # 고저 PER/PBR
        "per_high": 68.91, "per_low": 2.83,
        "pbr_high": 5.38, "pbr_low": 0.86,
        # 5년 평균
        "per_5y_avg": 14.40, "pbr_5y_avg": 2.04,
        "roe_5y_avg": 10.98, "opm_5y_avg": 17.85,
        # 실적 (25년4Q 연환산)
        "revenue": 971467,
        "op_income": 472064,
        "net_income": 429193,
        "opm": 48.59,
        # FnGuide 26년 컨센서스
        "consensus_26_revenue": 2299806,
        "consensus_26_op": 1606938,
        "consensus_26_ni": 1299259,
        "consensus_26_eps": 181883,
        "consensus_26_bps": 341495,
        "consensus_26_roe": 71.70,
    }
}


def calc_per_band(stock):
    """PER Band 계산 — Forward EPS 기준 중심 (싸이클 산업)"""
    eps_now = stock["eps_history"]["25년4Q(E)"]
    eps_26e = stock["consensus_26_eps"]
    price = stock["price"]

    # Forward PER 산출
    fwd_per = price / eps_26e if eps_26e > 0 else 0

    # PER 밴드용 대표 레벨 (양수만)
    per_vals = [v for k, v in stock["per_history"].items() if v > 0]

    per_low = stock["per_low"]
    per_5y = stock["per_5y_avg"]
    per_median = sorted(per_vals)[len(per_vals)//2]
    per_high = stock["per_high"]

    # Forward EPS 기준 밴드 가격 (핵심)
    fwd_band = {}
    for mult in [3, 5, 7, 10, 13, 15, 20, 25]:
        fwd_band[mult] = eps_26e * mult

    return {
        "eps_now": eps_now, "eps_26e": eps_26e,
        "fwd_per": fwd_per,
        "per_low": per_low, "per_5y": per_5y, "per_median": per_median, "per_high": per_high,
        "now_low": eps_now * per_low, "now_5y": eps_now * per_5y,
        "now_median": eps_now * per_median, "now_high": eps_now * per_high,
        "e26_low": eps_26e * per_low, "e26_5y": eps_26e * per_5y,
        "e26_median": eps_26e * per_median, "e26_high": eps_26e * per_high,
        "fwd_band": fwd_band,
    }


def calc_pbr_band(stock):
    """PBR Band 계산"""
    bps_now = stock["bps_history"]["25년4Q(E)"]
    bps_26e = stock["consensus_26_bps"]
    price = stock["price"]

    # Forward PBR 산출
    fwd_pbr = price / bps_26e if bps_26e > 0 else 0

    pbr_low = stock["pbr_low"]
    pbr_5y = stock["pbr_5y_avg"]
    pbr_vals = [v for k, v in stock["pbr_history"].items() if v > 0]
    pbr_median = sorted(pbr_vals)[len(pbr_vals)//2]
    pbr_high = stock["pbr_high"]

    # Forward BPS 기준 밴드 가격
    fwd_band = {}
    for mult_10 in [5, 8, 10, 13, 15, 20, 25, 30, 40, 50]:
        mult = mult_10 / 10
        fwd_band[mult] = bps_26e * mult

    return {
        "bps_now": bps_now, "bps_26e": bps_26e,
        "fwd_pbr": fwd_pbr,
        "pbr_low": pbr_low, "pbr_5y": pbr_5y, "pbr_median": pbr_median, "pbr_high": pbr_high,
        "now_low": bps_now * pbr_low, "now_5y": bps_now * pbr_5y,
        "now_median": bps_now * pbr_median, "now_high": bps_now * pbr_high,
        "e26_low": bps_26e * pbr_low, "e26_5y": bps_26e * pbr_5y,
        "e26_median": bps_26e * pbr_median, "e26_high": bps_26e * pbr_high,
        "fwd_band": fwd_band,
    }


def assess_valuation(stock_name, stock):
    """종합 밸류에이션 평가 — Forward PER 중심"""
    price = stock["price"]
    per_band = calc_per_band(stock)
    pbr_band = calc_pbr_band(stock)

    # Forward PER/PBR
    fwd_per = per_band["fwd_per"]
    fwd_pbr = pbr_band["fwd_pbr"]

    # 적정주가 산출 (5년 평균 PER × 26년E EPS)
    fair_per = per_band["e26_5y"]
    fair_pbr = pbr_band["e26_5y"]
    fair_avg = (fair_per + fair_pbr) / 2

    # 괴리율
    gap_per = (price / fair_per - 1) * 100
    gap_pbr = (price / fair_pbr - 1) * 100
    gap_avg = (price / fair_avg - 1) * 100

    # Forward PER 기반 판단 (싸이클 산업 특성)
    if fwd_per < 5:
        fwd_verdict = "✅ Forward PER 매우 낮음 — 강한 저평가"
    elif fwd_per < 8:
        fwd_verdict = "✅ Forward PER 낮음 — 저평가"
    elif fwd_per < 12:
        fwd_verdict = "🟡 Forward PER 적정 수준"
    elif fwd_per < 18:
        fwd_verdict = "⚠️ Forward PER 높음 — 고평가 구간"
    else:
        fwd_verdict = "⚠️ Forward PER 매우 높음 — 사이클 고점 주의"

    # 종합 판단
    if gap_avg > 30:
        verdict = "⚠️ 상당히 고평가"
    elif gap_avg > 10:
        verdict = "⚠️ 고평가"
    elif gap_avg > -10:
        verdict = "🟡 적정 수준"
    elif gap_avg > -30:
        verdict = "✅ 저평가"
    else:
        verdict = "✅ 상당히 저평가"

    return {
        "fwd_per": fwd_per,
        "fwd_pbr": fwd_pbr,
        "fwd_verdict": fwd_verdict,
        "fair_per": fair_per,
        "fair_pbr": fair_pbr,
        "fair_avg": fair_avg,
        "gap_per": gap_per,
        "gap_pbr": gap_pbr,
        "gap_avg": gap_avg,
        "verdict": verdict,
        "per_band": per_band,
        "pbr_band": pbr_band,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 밸류에이션 밴드 차트 생성 (matplotlib)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _make_gauge(ax, title, current_val, min_val, max_val, avg_val, bands, unit='배'):
    """게이지 스타일 가로 바 — 현재 위치를 직관적으로 표시"""
    ax.set_xlim(min_val - (max_val - min_val) * 0.05,
                max_val + (max_val - min_val) * 0.15)
    ax.set_ylim(-0.5, 1.5)

    gradient_colors = ['#27ae60', '#2ecc71', '#f1c40f', '#e67e22', '#e74c3c']
    n = len(gradient_colors)
    seg_w = (max_val - min_val) / n
    for i, c in enumerate(gradient_colors):
        ax.barh(0.5, seg_w, left=min_val + i * seg_w, height=0.6,
                color=c, alpha=0.3, edgecolor='none')

    for label, val in bands.items():
        ax.axvline(val, color='gray', linestyle='--', alpha=0.5, linewidth=0.8)
        ax.text(val, 1.15, f'{val}{unit}', ha='center', fontsize=7, color='gray')

    ax.axvline(avg_val, color='#2c3e50', linestyle='-', alpha=0.8, linewidth=2)
    ax.text(avg_val, 1.35, f'평균 {avg_val}{unit}', ha='center', fontsize=8,
            fontweight='bold', color='#2c3e50')

    ax.annotate('', xy=(current_val, 0.5), xytext=(current_val, -0.3),
                arrowprops=dict(arrowstyle='->', color='red', lw=3))
    ax.scatter([current_val], [0.5], color='red', s=150, zorder=10,
               edgecolors='darkred', linewidth=2, marker='D')
    ax.text(current_val, -0.4, f'현재\n{current_val:.1f}{unit}',
            ha='center', fontsize=10, fontweight='bold', color='red')

    ax.set_title(title, fontsize=12, fontweight='bold', pad=10)
    ax.set_yticks([])
    ax.spines['top'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['right'].set_visible(False)


def _make_per_band(ax, stock_name, stock, per_b):
    """Forward PER 밸류에이션 밴드 차트 (히스토리컬)"""
    # 연도 & EPS 히스토리 추출
    yr_keys = sorted([k for k in stock["eps_history"].keys() if "E)" not in k],
                     key=lambda x: int(x.replace("년","")))
    years = [int(k.replace("년","")) + 2000 for k in yr_keys]
    eps_vals = [stock["eps_history"][k] for k in yr_keys]

    # 26E 추가
    years.append(2026)
    eps_vals.append(stock["consensus_26_eps"])

    # 음수 EPS → 직전 양수 EPS로 보간 (차트용)
    eps_plot = list(eps_vals)
    for i in range(len(eps_plot)):
        if eps_plot[i] <= 0:
            # 직전 양수값 또는 직후 양수값으로 대체
            prev = next((eps_plot[j] for j in range(i-1, -1, -1) if eps_plot[j] > 0), None)
            nxt = next((eps_plot[j] for j in range(i+1, len(eps_plot)) if eps_plot[j] > 0), None)
            eps_plot[i] = prev or nxt or 1

    # PER 고점이 극단적이면 (5Y평균의 3배 초과) 캡 적용
    per_high_capped = min(per_b["per_high"], per_b["per_5y"] * 3)

    # PER 밴드 레벨
    per_levels = [
        (per_b["per_low"], f'저점 ({per_b["per_low"]:.1f})', '#1a5276'),
        (per_b["per_5y"], f'5Y평균 ({per_b["per_5y"]:.1f})', '#27ae60'),
        (per_b["per_median"], f'중간값 ({per_b["per_median"]:.1f})', '#f39c12'),
        (per_high_capped, f'고점 ({per_high_capped:.1f})', '#e74c3c'),
    ]

    for per, label, color in per_levels:
        implied = [e * per for e in eps_plot]
        ax.plot(years, implied, color=color, linewidth=1.5,
                label=f'PER {label}', alpha=0.85)
        ax.annotate(f'{per:.1f}배\n({implied[-1]:,.0f})',
                    xy=(years[-1], implied[-1]),
                    xytext=(8, 0), textcoords='offset points',
                    fontsize=7.5, color=color, fontweight='bold', va='center')

    # 밴드 사이 fill
    for i in range(len(per_levels) - 1):
        lower = [e * per_levels[i][0] for e in eps_plot]
        upper = [e * per_levels[i+1][0] for e in eps_plot]
        ax.fill_between(years, lower, upper, color=per_levels[i][2], alpha=0.08)

    # 실제 주가
    price_keys = sorted([k for k in stock["price_history"].keys() if "현재" not in k],
                        key=lambda x: int(x.replace("년","")))
    price_years = [int(k.replace("년","")) + 2000 for k in price_keys]
    price_vals = [stock["price_history"][k] for k in price_keys]
    price_years.append(2026)
    price_vals.append(stock["price"])

    ax.plot(price_years, price_vals, color='black', linewidth=2.5,
            marker='o', markersize=4, label=f'실제 주가', zorder=5)

    # 현재 위치 강조
    ax.scatter([2026], [stock["price"]], color='red', s=200,
               zorder=10, edgecolors='darkred', linewidth=2, marker='*')
    fwd_per = per_b["fwd_per"]
    ax.annotate(f'현재 {stock["price"]:,.0f}\nFwd PER {fwd_per:.1f}배',
                xy=(2026, stock["price"]),
                xytext=(-130, 30), textcoords='offset points',
                fontsize=9, fontweight='bold', color='red',
                arrowprops=dict(arrowstyle='->', color='red', lw=1.5),
                bbox=dict(boxstyle='round,pad=0.4', facecolor='#fff3f3',
                          edgecolor='red', alpha=0.9))

    ax.set_title(f'{stock_name} Forward PER 밸류에이션 밴드 (2016~현재)',
                 fontsize=14, fontweight='bold', pad=12)
    ax.set_ylabel('주가 (원)', fontsize=11)
    ax.legend(loc='upper left', fontsize=8, framealpha=0.9)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))
    ax.grid(True, alpha=0.3)
    ax.set_xlim(min(years) - 0.5, 2027.5)


def _make_pbr_band(ax, stock_name, stock, pbr_b):
    """PBR 밸류에이션 밴드 차트 (히스토리컬)"""
    yr_keys = sorted([k for k in stock["bps_history"].keys() if "E)" not in k],
                     key=lambda x: int(x.replace("년","")))
    years = [int(k.replace("년","")) + 2000 for k in yr_keys]
    bps_vals = [stock["bps_history"][k] for k in yr_keys]

    years.append(2026)
    bps_vals.append(stock["consensus_26_bps"])

    pbr_levels = [
        (pbr_b["pbr_low"], f'저점 ({pbr_b["pbr_low"]:.2f})', '#1a5276'),
        (pbr_b["pbr_5y"], f'5Y평균 ({pbr_b["pbr_5y"]:.2f})', '#27ae60'),
        (pbr_b["pbr_median"], f'중간값 ({pbr_b["pbr_median"]:.2f})', '#f39c12'),
        (pbr_b["pbr_high"], f'고점 ({pbr_b["pbr_high"]:.2f})', '#e74c3c'),
    ]

    for pbr, label, color in pbr_levels:
        implied = [b * pbr for b in bps_vals]
        ax.plot(years, implied, color=color, linewidth=1.5,
                label=f'PBR {label}', alpha=0.85)
        ax.annotate(f'{pbr:.2f}배\n({implied[-1]:,.0f})',
                    xy=(years[-1], implied[-1]),
                    xytext=(8, 0), textcoords='offset points',
                    fontsize=7.5, color=color, fontweight='bold', va='center')

    for i in range(len(pbr_levels) - 1):
        lower = [b * pbr_levels[i][0] for b in bps_vals]
        upper = [b * pbr_levels[i+1][0] for b in bps_vals]
        ax.fill_between(years, lower, upper, color=pbr_levels[i][2], alpha=0.08)

    price_keys = sorted([k for k in stock["price_history"].keys() if "현재" not in k],
                        key=lambda x: int(x.replace("년","")))
    price_years = [int(k.replace("년","")) + 2000 for k in price_keys]
    price_vals = [stock["price_history"][k] for k in price_keys]
    price_years.append(2026)
    price_vals.append(stock["price"])

    ax.plot(price_years, price_vals, color='black', linewidth=2.5,
            marker='o', markersize=4, label=f'실제 주가', zorder=5)

    ax.scatter([2026], [stock["price"]], color='red', s=200,
               zorder=10, edgecolors='darkred', linewidth=2, marker='*')
    fwd_pbr = pbr_b["fwd_pbr"]
    ax.annotate(f'현재 {stock["price"]:,.0f}\nFwd PBR {fwd_pbr:.2f}배',
                xy=(2026, stock["price"]),
                xytext=(-130, 30), textcoords='offset points',
                fontsize=9, fontweight='bold', color='red',
                arrowprops=dict(arrowstyle='->', color='red', lw=1.5),
                bbox=dict(boxstyle='round,pad=0.4', facecolor='#fff3f3',
                          edgecolor='red', alpha=0.9))

    ax.set_title(f'{stock_name} PBR 밸류에이션 밴드 (2016~현재)',
                 fontsize=14, fontweight='bold', pad=12)
    ax.set_ylabel('주가 (원)', fontsize=11)
    ax.legend(loc='upper left', fontsize=8, framealpha=0.9)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))
    ax.grid(True, alpha=0.3)
    ax.set_xlim(min(years) - 0.5, 2027.5)


def generate_valuation_chart(stock_name, stock, per_b, pbr_b, out_dir):
    """종목별 밸류에이션 밴드 차트 PNG 생성 (게이지 + PER밴드 + PBR밴드)"""
    fig = plt.figure(figsize=(18, 20))
    today_str = datetime.now().strftime('%Y-%m-%d')
    fig.suptitle(f'{stock_name} 밸류에이션 현황 ({today_str}, {stock["price"]:,.0f}원)',
                 fontsize=18, fontweight='bold', y=0.98)

    fwd_per = per_b["fwd_per"]
    fwd_pbr = pbr_b["fwd_pbr"]

    # ── 1행: Forward PER 게이지 ──
    ax1 = fig.add_axes([0.06, 0.82, 0.88, 0.10])
    per_vals_pos = [v for v in stock["per_history"].values() if isinstance(v, (int, float)) and v > 0]
    per_min = min(per_vals_pos)
    # 게이지 범위: 극단치 캡 (5Y평균의 3배까지만)
    per_gauge_max = min(max(per_vals_pos), per_b["per_5y"] * 3)
    _make_gauge(ax1,
                f'Forward PER 위치 — 현재 {fwd_per:.1f}배 (범위: {per_min:.1f}~{per_gauge_max:.1f})',
                fwd_per,
                max(0, per_min - 2), per_gauge_max + 3,
                per_b["per_5y"],
                {'저점': round(per_b["per_low"], 1),
                 '5Y평균': round(per_b["per_5y"], 1),
                 '중간값': round(per_b["per_median"], 1),
                 '고점': round(min(per_b["per_high"], per_b["per_5y"] * 3), 1)})

    # ── 2행: PBR 게이지 ──
    ax2 = fig.add_axes([0.06, 0.70, 0.88, 0.10])
    pbr_vals_pos = [v for v in stock["pbr_history"].values() if isinstance(v, (int, float)) and v > 0]
    pbr_min = min(pbr_vals_pos)
    pbr_max = max(pbr_vals_pos)
    _make_gauge(ax2,
                f'Forward PBR 위치 — 현재 {fwd_pbr:.2f}배 (범위: {pbr_min:.2f}~{pbr_max:.2f})',
                fwd_pbr,
                max(0, pbr_min - 0.3), pbr_max + 0.5,
                pbr_b["pbr_5y"],
                {'저점': round(pbr_b["pbr_low"], 2),
                 '5Y평균': round(pbr_b["pbr_5y"], 2),
                 '중간값': round(pbr_b["pbr_median"], 2),
                 '고점': round(pbr_b["pbr_high"], 2)})

    # ── 3행: Forward PER 밴드 차트 ──
    ax3 = fig.add_axes([0.06, 0.37, 0.83, 0.28])
    _make_per_band(ax3, stock_name, stock, per_b)

    # ── 4행: PBR 밴드 차트 ──
    ax4 = fig.add_axes([0.06, 0.04, 0.83, 0.28])
    _make_pbr_band(ax4, stock_name, stock, pbr_b)

    # 저장
    code_clean = stock["code"].replace("A", "")
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = os.path.join(out_dir, f'{stock_name}_밸류에이션차트_{ts}.png')
    os.makedirs(out_dir, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()

    return out_path


def generate_report():
    """종합 리포트 생성 — Forward PER 중심"""
    report_date = datetime.now().strftime('%Y%m%d_%H%M%S')
    from config import WEEKLY_RESEARCH_DIR
    os.makedirs(WEEKLY_RESEARCH_DIR, exist_ok=True)
    filename = os.path.join(WEEKLY_RESEARCH_DIR, f"반도체_밸류에이션_분석_{report_date}.md")

    with open(filename, 'w', encoding='utf-8') as f:
        f.write("# 📊 삼성전자 · SK하이닉스 밸류에이션 분석 리포트\n\n")
        f.write(f"**분석일시**: {datetime.now().strftime('%Y년 %m월 %d일 %H:%M')}  \n")
        f.write(f"**데이터 출처**: 네이버금융, wisereport 컨센서스  \n")
        f.write(f"**분석 방법론**: Forward PER 중심 (싸이클 산업 특성 반영)  \n\n")
        f.write("---\n\n")

        # ── 싸이클 산업 주의사항 ──
        f.write("## ⚙️ 싸이클 산업과 Forward PER\n\n")
        f.write("> **반도체는 대표적인 싸이클 산업**입니다. Trailing PER(과거 실적 기준)은 오해를 유발합니다:  \n")
        f.write("> - **사이클 저점**: 실적 악화 → Trailing PER 급등 → 수치만 보면 \"비싸 보이지만\" 실제로는 매수 적기  \n")
        f.write("> - **사이클 고점**: 실적 폭증 → Trailing PER 급락 → 수치만 보면 \"싸 보이지만\" 실제로는 고점 부근  \n")
        f.write("> \n")
        f.write("> 따라서 **Forward PER (향후 12개월 예상 실적 기준)**을 핵심 지표로 사용합니다.  \n")
        f.write("> Forward PER = 현재 주가 ÷ 26년(E) EPS\n\n")
        f.write("---\n\n")

        # ── 종합 요약 ──
        f.write("## 🎯 종합 밸류에이션 요약\n\n")

        headers = "| 항목 |"
        divider = "|:---:|"
        for name in STOCKS:
            headers += f" {name} |"
            divider += ":---:|"
        f.write(headers + "\n" + divider + "\n")

        assessments = {}
        for name, stock in STOCKS.items():
            assessments[name] = assess_valuation(name, stock)

        rows = [
            ("현재 주가", lambda n: f"{STOCKS[n]['price']:,.0f}원"),
            ("시가총액", lambda n: f"{STOCKS[n]['market_cap_억']:,.0f}억"),
            ("52주 고/저", lambda n: f"{STOCKS[n]['52w_high']:,.0f} / {STOCKS[n]['52w_low']:,.0f}"),
            ("", lambda n: ""),
            ("**━━ Forward 지표 (핵심) ━━**", lambda n: ""),
            ("**Forward PER (26E)**", lambda n: f"**{assessments[n]['fwd_per']:.1f}배**"),
            ("**Forward PBR (26E)**", lambda n: f"**{assessments[n]['fwd_pbr']:.2f}배**"),
            ("26년(E) EPS", lambda n: f"{STOCKS[n]['consensus_26_eps']:,.0f}원"),
            ("26년(E) BPS", lambda n: f"{STOCKS[n]['consensus_26_bps']:,.0f}원"),
            ("26년(E) ROE", lambda n: f"{STOCKS[n]['consensus_26_roe']:.1f}%"),
            ("**Forward PER 판단**", lambda n: f"**{assessments[n]['fwd_verdict']}**"),
            ("", lambda n: ""),
            ("━━ Trailing 지표 (참고) ━━", lambda n: ""),
            ("Trailing PER", lambda n: f"{STOCKS[n]['per_current']:.1f}배"),
            ("12M Forward PER", lambda n: f"{STOCKS[n]['per_12m']:.1f}배"),
            ("현재 PBR", lambda n: f"{STOCKS[n]['pbr_current']:.2f}배"),
            ("현재 ROE", lambda n: f"{STOCKS[n]['roe_current']:.1f}%"),
            ("배당수익률", lambda n: f"{STOCKS[n]['dividend_yield']:.2f}%"),
            ("", lambda n: ""),
            ("━━ 적정주가 ━━", lambda n: ""),
            ("컨센서스 목표주가", lambda n: f"{STOCKS[n]['target_price']:,.0f}원"),
            ("**적정주가 (Fwd PER)**", lambda n: f"**{assessments[n]['fair_per']:,.0f}원**"),
            ("**적정주가 (Fwd PBR)**", lambda n: f"**{assessments[n]['fair_pbr']:,.0f}원**"),
            ("**적정주가 (평균)**", lambda n: f"**{assessments[n]['fair_avg']:,.0f}원**"),
            ("**현재 대비 괴리율**", lambda n: f"**{assessments[n]['gap_avg']:+.1f}%**"),
            ("**종합 판단**", lambda n: f"**{assessments[n]['verdict']}**"),
        ]

        for label, fn in rows:
            row = f"| {label} |"
            for name in STOCKS:
                row += f" {fn(name)} |"
            f.write(row + "\n")
        f.write("\n")

        # ── 각 종목 상세 분석 ──
        chart_paths = {}
        for name, stock in STOCKS.items():
            a = assessments[name]
            per_b = a["per_band"]
            pbr_b = a["pbr_band"]
            price = stock["price"]

            # 밸류에이션 밴드 차트 PNG 생성
            chart_path = generate_valuation_chart(name, stock, per_b, pbr_b,
                                                  WEEKLY_RESEARCH_DIR)
            chart_paths[name] = chart_path
            chart_basename = os.path.basename(chart_path)

            f.write(f"---\n\n")
            f.write(f"## 📈 {name} ({stock['code']}) 상세 분석\n\n")

            # 밸류에이션 밴드 차트 삽입
            f.write(f"### 📊 밸류에이션 밴드 차트\n\n")
            f.write(f"![{name} 밸류에이션 밴드]({chart_basename})\n\n")

            # 현재 위치
            f.write(f"### 현재 위치\n\n")
            f.write(f"- **주가**: {price:,.0f}원\n")
            f.write(f"- **52주 고점 대비**: {(price/stock['52w_high']-1)*100:+.1f}%\n")
            f.write(f"- **52주 저점 대비**: {(price/stock['52w_low']-1)*100:+.1f}%\n")
            f.write(f"- **외국인 지분율**: {stock['foreign_ratio']:.1f}%\n")
            gap_target = (price/stock['target_price']-1)*100
            f.write(f"- **컨센서스 목표주가**: {stock['target_price']:,.0f}원 ")
            f.write(f"(현재 대비 {'↑' if gap_target < 0 else '↓'}{abs(gap_target):.1f}%)\n\n")

            # ━━ Forward PER 분석 (핵심) ━━
            f.write(f"### ⭐ Forward PER 분석 (핵심)\n\n")
            f.write(f"| 항목 | 값 |\n")
            f.write(f"|:----:|:---:|\n")
            f.write(f"| 26년(E) EPS | {per_b['eps_26e']:,.0f}원 |\n")
            f.write(f"| **Forward PER** | **{a['fwd_per']:.1f}배** |\n")
            f.write(f"| 5년 평균 PER | {per_b['per_5y']:.1f}배 |\n")
            f.write(f"| Forward vs 5년평균 | {(a['fwd_per']/per_b['per_5y']-1)*100:+.1f}% |\n")
            f.write(f"| **판단** | **{a['fwd_verdict']}** |\n\n")

            # Forward PER Band 테이블
            f.write(f"**Forward PER Band (26년E EPS = {per_b['eps_26e']:,.0f}원 기준)**\n\n")
            f.write("| PER 배수 | 주가 수준 | 현재 주가 대비 |\n")
            f.write("|:--------:|:--------:|:------------:|\n")

            fwd_band = per_b["fwd_band"]
            for mult in sorted(fwd_band.keys()):
                band_price = fwd_band[mult]
                gap = (price / band_price - 1) * 100
                marker = " ◀◀" if abs(gap) < 15 else ""
                f.write(f"| {mult}배 | {band_price:,.0f}원 | {gap:+.1f}%{marker} |\n")
            f.write("\n")

            # Forward PER Band 시각화
            f.write(f"**Forward PER Band 시각화**\n\n")
            f.write("```\n")
            # 밴드 포인트 선정 (핵심 PER 레벨 + 현재 주가)
            band_vis = []
            for mult in sorted(fwd_band.keys()):
                band_vis.append((fwd_band[mult], f"PER {mult}x"))
            band_vis.append((price, "★ 현재 주가"))
            band_vis.sort()

            max_val = max(v for v, _ in band_vis)
            for val, label in band_vis:
                bar_len = int(val / max_val * 50)
                if "현재" in label:
                    marker = "★"
                    bar_char = "▓"
                else:
                    marker = "│"
                    bar_char = "█"
                f.write(f"  {val:>12,.0f}원 {marker} {bar_char * bar_len} {label}\n")
            f.write("```\n\n")

            # ━━ PER Band (히스토리컬 레벨) ━━
            f.write(f"### PER Band (히스토리컬 레벨)\n\n")
            f.write(f"**현재 EPS**: {per_b['eps_now']:,.0f}원 / **26년(E) EPS**: {per_b['eps_26e']:,.0f}원\n\n")

            f.write("| PER 수준 | PER 배수 | 현재EPS 기준 | 26년E 기준 | 현재 주가 위치 |\n")
            f.write("|:--------:|:-------:|:----------:|:---------:|:------------:|\n")

            per_levels = [
                ("저점", per_b["per_low"], per_b["now_low"], per_b["e26_low"]),
                ("5년평균", per_b["per_5y"], per_b["now_5y"], per_b["e26_5y"]),
                ("중간값", per_b["per_median"], per_b["now_median"], per_b["e26_median"]),
                ("고점", per_b["per_high"], per_b["now_high"], per_b["e26_high"]),
            ]
            for label, per, now_val, e26_val in per_levels:
                marker_e26 = " ◀" if abs(price/e26_val - 1) < 0.15 else ""
                f.write(f"| {label} | {per:.1f}배 | {now_val:,.0f}원 | {e26_val:,.0f}원{marker_e26} | ")
                if price > e26_val:
                    f.write(f"위 ({(price/e26_val-1)*100:+.0f}%) |\n")
                else:
                    f.write(f"아래 ({(price/e26_val-1)*100:+.0f}%) |\n")
            f.write("\n")

            # 히스토리컬 PER Band 시각화
            f.write("**PER 밴드 시각화 (26년E EPS 기준)**\n\n")
            f.write("```\n")
            band_points = sorted([
                (per_b["e26_low"], f"저점 PER {per_b['per_low']:.1f}x"),
                (per_b["e26_5y"], f"5년평균 PER {per_b['per_5y']:.1f}x"),
                (per_b["e26_median"], f"중간값 PER {per_b['per_median']:.1f}x"),
                (per_b["e26_high"], f"고점 PER {per_b['per_high']:.1f}x"),
                (price, "★ 현재 주가"),
            ])
            max_val = max(v for v, _ in band_points)
            for val, label in band_points:
                bar_len = int(val / max_val * 45)
                if "현재" in label:
                    f.write(f"  {val:>12,.0f}원 ★ {'▓' * bar_len} {label}\n")
                else:
                    f.write(f"  {val:>12,.0f}원 │ {'█' * bar_len} {label}\n")
            f.write("```\n\n")

            # ━━ PBR Band 분석 ━━
            f.write(f"### PBR Band 분석\n\n")
            f.write(f"**현재 BPS**: {pbr_b['bps_now']:,.0f}원 / **26년(E) BPS**: {pbr_b['bps_26e']:,.0f}원  \n")
            f.write(f"**Forward PBR**: {a['fwd_pbr']:.2f}배 (5년 평균 {pbr_b['pbr_5y']:.2f}배)\n\n")

            # Forward PBR Band 테이블
            f.write(f"**Forward PBR Band (26년E BPS = {pbr_b['bps_26e']:,.0f}원 기준)**\n\n")
            f.write("| PBR 배수 | 주가 수준 | 현재 주가 대비 |\n")
            f.write("|:--------:|:--------:|:------------:|\n")

            fwd_pbr_band = pbr_b["fwd_band"]
            # 적절한 범위만 표시 (현재 주가의 0.2~3배 범위)
            for mult in sorted(fwd_pbr_band.keys()):
                band_price = fwd_pbr_band[mult]
                if band_price < price * 0.1 or band_price > price * 5:
                    continue
                gap = (price / band_price - 1) * 100
                marker = " ◀◀" if abs(gap) < 15 else ""
                f.write(f"| {mult:.1f}배 | {band_price:,.0f}원 | {gap:+.1f}%{marker} |\n")
            f.write("\n")

            # PBR Band 히스토리컬 레벨
            f.write("| PBR 수준 | PBR 배수 | 현재BPS 기준 | 26년E 기준 | 현재 주가 위치 |\n")
            f.write("|:--------:|:-------:|:----------:|:---------:|:------------:|\n")

            pbr_levels = [
                ("저점", pbr_b["pbr_low"], pbr_b["now_low"], pbr_b["e26_low"]),
                ("5년평균", pbr_b["pbr_5y"], pbr_b["now_5y"], pbr_b["e26_5y"]),
                ("중간값", pbr_b["pbr_median"], pbr_b["now_median"], pbr_b["e26_median"]),
                ("고점", pbr_b["pbr_high"], pbr_b["now_high"], pbr_b["e26_high"]),
            ]
            for label, pbr, now_val, e26_val in pbr_levels:
                f.write(f"| {label} | {pbr:.2f}배 | {now_val:,.0f}원 | {e26_val:,.0f}원 | ")
                if price > e26_val:
                    f.write(f"위 ({(price/e26_val-1)*100:+.0f}%) |\n")
                else:
                    f.write(f"아래 ({(price/e26_val-1)*100:+.0f}%) |\n")
            f.write("\n")

            # PBR Band 시각화
            f.write("**PBR 밴드 시각화 (26년E BPS 기준)**\n\n")
            f.write("```\n")
            band_points = sorted([
                (pbr_b["e26_low"], f"저점 PBR {pbr_b['pbr_low']:.2f}x"),
                (pbr_b["e26_5y"], f"5년평균 PBR {pbr_b['pbr_5y']:.2f}x"),
                (pbr_b["e26_median"], f"중간값 PBR {pbr_b['pbr_median']:.2f}x"),
                (pbr_b["e26_high"], f"고점 PBR {pbr_b['pbr_high']:.2f}x"),
                (price, "★ 현재 주가"),
            ])
            max_val = max(v for v, _ in band_points)
            for val, label in band_points:
                bar_len = int(val / max_val * 45)
                if "현재" in label:
                    f.write(f"  {val:>12,.0f}원 ★ {'▓' * bar_len} {label}\n")
                else:
                    f.write(f"  {val:>12,.0f}원 │ {'█' * bar_len} {label}\n")
            f.write("```\n\n")

            # ━━ 히스토리컬 PER/PBR 추이 ━━
            f.write(f"### 히스토리컬 PER·PBR 추이\n\n")
            f.write("| 연도 | 주가 | EPS | PER | BPS | PBR | ROE |\n")
            f.write("|:----:|:----:|:---:|:---:|:---:|:---:|:---:|\n")
            years = ["16년", "17년", "18년", "19년", "20년", "21년", "22년", "23년", "24년", "25년4Q(E)"]
            for yr in years:
                price_key = yr if yr != "25년4Q(E)" else "25년현재"
                p = stock["price_history"].get(price_key, 0)
                eps = stock["eps_history"].get(yr, 0)
                per = stock["per_history"].get(yr, 0)
                bps = stock["bps_history"].get(yr, 0)
                pbr_v = stock["pbr_history"].get(yr, 0)
                roe = stock["roe_history"].get(yr, 0)
                per_str = f"{per:.1f}" if per > 0 else ("적자" if per < 0 else "N/A")
                f.write(f"| {yr} | {p:,.0f} | {eps:,.0f} | {per_str} | {bps:,.0f} | {pbr_v:.2f} | {roe:.1f}% |\n")
            f.write("\n")

            # ━━ 실적 요약 ━━
            f.write(f"### 실적 현황\n\n")
            f.write("| 항목 | 25년4Q 연환산 | 26년(E) 컨센서스 | YoY |\n")
            f.write("|:----:|:----------:|:-------------:|:---:|\n")
            f.write(f"| 매출액 | {stock['revenue']:,.0f}억 | {stock['consensus_26_revenue']:,.0f}억 | ")
            f.write(f"+{(stock['consensus_26_revenue']/stock['revenue']-1)*100:.0f}% |\n")
            f.write(f"| 영업이익 | {stock['op_income']:,.0f}억 | {stock['consensus_26_op']:,.0f}억 | ")
            f.write(f"+{(stock['consensus_26_op']/stock['op_income']-1)*100:.0f}% |\n")
            f.write(f"| 지배순이익 | {stock['net_income']:,.0f}억 | {stock['consensus_26_ni']:,.0f}억 | ")
            f.write(f"+{(stock['consensus_26_ni']/stock['net_income']-1)*100:.0f}% |\n")
            f.write(f"| OPM | {stock['opm']:.1f}% | ")
            opm_26 = stock['consensus_26_op']/stock['consensus_26_revenue']*100
            f.write(f"{opm_26:.1f}% | |\n")
            f.write(f"| EPS | {per_b['eps_now']:,.0f}원 | {per_b['eps_26e']:,.0f}원 | ")
            f.write(f"+{(per_b['eps_26e']/per_b['eps_now']-1)*100:.0f}% |\n")
            f.write(f"| BPS | {pbr_b['bps_now']:,.0f}원 | {pbr_b['bps_26e']:,.0f}원 | ")
            f.write(f"+{(pbr_b['bps_26e']/pbr_b['bps_now']-1)*100:.0f}% |\n")
            f.write(f"| ROE | {stock['roe_current']:.1f}% | {stock['consensus_26_roe']:.1f}% | |\n")
            f.write("\n")

            # ━━ 적정주가 산출 ━━
            f.write(f"### 적정주가 산출\n\n")
            f.write(f"**방법 1: Forward PER 기반** (5년 평균 PER × 26년E EPS)\n")
            f.write(f"- {per_b['per_5y']:.1f}배 × {per_b['eps_26e']:,.0f}원 = **{a['fair_per']:,.0f}원** (현재 대비 {a['gap_per']:+.1f}%)\n\n")
            f.write(f"**방법 2: Forward PBR 기반** (5년 평균 PBR × 26년E BPS)\n")
            f.write(f"- {pbr_b['pbr_5y']:.2f}배 × {pbr_b['bps_26e']:,.0f}원 = **{a['fair_pbr']:,.0f}원** (현재 대비 {a['gap_pbr']:+.1f}%)\n\n")
            f.write(f"**방법 3: 컨센서스 기반** (애널리스트 목표주가)\n")
            f.write(f"- **{stock['target_price']:,.0f}원** (현재 대비 {gap_target:+.1f}%)\n\n")
            f.write(f"**종합 적정주가**: **{a['fair_avg']:,.0f}원** → 현재 대비 **{a['gap_avg']:+.1f}%**\n\n")
            f.write(f"> **판단: {a['verdict']}**  \n")
            f.write(f"> **Forward PER 관점: {a['fwd_verdict']}**\n\n")

        # ── 비교 분석 ──
        f.write("---\n\n")
        f.write("## 🔍 삼성전자 vs SK하이닉스 비교\n\n")
        f.write("| 구분 | 삼성전자 | SK하이닉스 | 비고 |\n")
        f.write("|:----:|:-------:|:--------:|:----:|\n")

        se = STOCKS["삼성전자"]
        sk = STOCKS["SK하이닉스"]
        ae = assessments["삼성전자"]
        ak = assessments["SK하이닉스"]

        f.write(f"| **Forward PER** | **{ae['fwd_per']:.1f}배** | **{ak['fwd_per']:.1f}배** | 핵심 지표 |\n")
        f.write(f"| **Forward PBR** | **{ae['fwd_pbr']:.2f}배** | **{ak['fwd_pbr']:.2f}배** | |\n")
        f.write(f"| Trailing PER | {se['per_current']:.1f}배 | {sk['per_current']:.1f}배 | ")
        f.write(f"참고 (싸이클 왜곡) |\n")
        f.write(f"| 12M Fwd PER | {se['per_12m']:.1f}배 | {sk['per_12m']:.1f}배 | |\n")
        f.write(f"| 현재 PBR | {se['pbr_current']:.2f}배 | {sk['pbr_current']:.2f}배 | |\n")
        f.write(f"| 현재 ROE | {se['roe_current']:.1f}% | {sk['roe_current']:.1f}% | |\n")
        f.write(f"| 26년E ROE | {se['consensus_26_roe']:.1f}% | {sk['consensus_26_roe']:.1f}% | |\n")
        f.write(f"| OPM | {se['opm']:.1f}% | {sk['opm']:.1f}% | |\n")
        f.write(f"| 26년E EPS 성장률 | +{(se['consensus_26_eps']/se['eps_history']['25년4Q(E)']-1)*100:.0f}% | ")
        f.write(f"+{(sk['consensus_26_eps']/sk['eps_history']['25년4Q(E)']-1)*100:.0f}% | |\n")
        f.write(f"| 적정주가 괴리율 | {ae['gap_avg']:+.1f}% | {ak['gap_avg']:+.1f}% | |\n")
        f.write(f"| **Forward PER 판단** | **{ae['fwd_verdict']}** | **{ak['fwd_verdict']}** | |\n")
        f.write(f"| **밸류 판단** | **{ae['verdict']}** | **{ak['verdict']}** | |\n")
        f.write("\n")

        # ── 투자 시사점 ──
        f.write("---\n\n")
        f.write("## 💡 투자 시사점\n\n")

        for name in STOCKS:
            stock = STOCKS[name]
            a = assessments[name]
            f.write(f"### {name}\n\n")

            # Forward PER 핵심 포인트
            f.write(f"- **Forward PER {a['fwd_per']:.1f}배** → {a['fwd_verdict']}\n")
            f.write(f"- Trailing PER({stock['per_current']:.1f}배)과의 괴리가 큼 → 26년 실적 대폭 개선 전망 반영\n")

            if a["gap_avg"] > 10:
                f.write(f"- 현재 주가({stock['price']:,.0f}원)는 적정주가({a['fair_avg']:,.0f}원) 대비 **{a['gap_avg']:+.1f}% 고평가** 상태\n")
                f.write(f"- 26년 컨센서스 실적이 실현되더라도 현재 주가에는 상당한 프리미엄이 반영됨\n")
            elif a["gap_avg"] > -10:
                f.write(f"- 현재 주가({stock['price']:,.0f}원)는 적정주가({a['fair_avg']:,.0f}원) 부근으로 **적정 밸류에이션**\n")
            else:
                f.write(f"- 현재 주가({stock['price']:,.0f}원)는 적정주가({a['fair_avg']:,.0f}원) 대비 **{abs(a['gap_avg']):.1f}% 저평가** 상태\n")
                f.write(f"- 26년 실적 성장이 예상대로 실현되면 상당한 업사이드 잠재력\n")

            f.write(f"- 52주 고점({stock['52w_high']:,.0f}원) 대비 {(stock['price']/stock['52w_high']-1)*100:+.1f}%\n")
            f.write(f"- 애널리스트 목표주가 {stock['target_price']:,.0f}원 (현재 대비 {(stock['target_price']/stock['price']-1)*100:+.1f}%)\n")
            f.write("\n")

        # ── 리스크 요인 ──
        f.write("---\n\n")
        f.write("## ⚠️ 리스크 요인\n\n")
        f.write("- **반도체 사이클**: 메모리 업황 사이클에 따른 실적 변동성 존재. Forward PER가 낮아도 사이클 피크 리스크 점검 필요\n")
        f.write("- **컨센서스 리스크**: 26년 실적이 컨센서스에 못 미칠 경우 Forward PER 재산출 시 밸류에이션 급등\n")
        f.write("- **AI 기대감 과반영**: 현재 주가에 AI 수혜 기대가 상당히 반영된 상태\n")
        f.write("- **환율·지정학**: 원/달러 환율, 미중 갈등, 수출 규제 리스크\n")
        f.write("- **PBR 고점 리스크**: 역사적 PBR 고점 부근에 위치 → 순자산 대비 프리미엄 과도 여부 점검\n")
        f.write("- **싸이클 고점 시나리오**: Trailing PER이 낮을 때가 오히려 사이클 고점일 수 있음 (역설적 위험)\n\n")

        f.write("---\n\n")
        f.write("> **면책 조항**: 본 리포트는 공개된 데이터를 기반으로 한 기계적 분석이며, 투자 권유가 아닙니다. ")
        f.write("투자 판단은 본인의 책임하에 이루어져야 합니다.\n\n")
        f.write(f"**분석 도구**: Python  \n")
        f.write(f"**데이터 출처**: 네이버금융, wisereport (navercomp.wisereport.co.kr)\n")

    return filename


def main():
    print("=" * 60)
    print("  삼성전자 · SK하이닉스 밸류에이션 분석 (Forward PER 중심)")
    print("=" * 60)
    print()

    # ── 자동 크롤링으로 최신 데이터 갱신 ──
    print("[1/3] 📡 네이버금융 + wisereport에서 최신 데이터 수집 중...")
    print()
    for name, stock in STOCKS.items():
        code = stock["code"].replace("A", "")  # "A005930" → "005930"
        try:
            fetched = fetch_stock_data(code, name)
            updated = update_stock_dict(stock, fetched)
            if updated:
                print(f"    ✅ {name}: {len(updated)}개 항목 업데이트 ({', '.join(updated[:5])}{'...' if len(updated) > 5 else ''})")
            else:
                print(f"    ⚠ {name}: 크롤링 데이터 없음 — 기존값 사용")
        except Exception as e:
            print(f"    ⚠ {name}: 크롤링 실패 ({e}) — 기존값 사용")
    print()

    print("[2/3] 📊 밸류에이션 분석...")
    print()

    for name, stock in STOCKS.items():
        a = assess_valuation(name, stock)
        print(f"📊 {name} ({stock['code']})")
        print(f"   현재 주가: {stock['price']:,.0f}원")
        print(f"   Forward PER (26E): {a['fwd_per']:.1f}배 ← 핵심")
        print(f"   Forward PBR (26E): {a['fwd_pbr']:.2f}배")
        print(f"   Trailing PER: {stock['per_current']:.1f}배 (참고)")
        print(f"   {a['fwd_verdict']}")
        print(f"   적정주가(PER): {a['fair_per']:,.0f}원 ({a['gap_per']:+.1f}%)")
        print(f"   적정주가(PBR): {a['fair_pbr']:,.0f}원 ({a['gap_pbr']:+.1f}%)")
        print(f"   적정주가(평균): {a['fair_avg']:,.0f}원 ({a['gap_avg']:+.1f}%)")
        print(f"   종합 판단: {a['verdict']}")
        print()

    print("[3/3] 📝 리포트 + 차트 생성...")
    filename = generate_report()
    print(f"✅ 리포트 생성 완료: {filename}")
    print()


if __name__ == "__main__":
    main()
