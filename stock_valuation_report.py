"""
삼성전자 · SK하이닉스 밸류에이션 분석 리포트 생성기
- Forward PER 중심 분석 (싸이클 산업 특성 반영)
- PER/PBR Band 분석 (시각화)
- 적정주가 산출 (Forward EPS/BPS 기반)
- 저평가/고평가 판단
- 컨센서스 대비 분석
"""

import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

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


def generate_report():
    """종합 리포트 생성 — Forward PER 중심"""
    report_date = datetime.now().strftime('%Y%m%d_%H%M%S')
    os.makedirs('results/analysis', exist_ok=True)
    filename = f"results/analysis/반도체_밸류에이션_분석_{report_date}.md"

    with open(filename, 'w', encoding='utf-8') as f:
        f.write("# 📊 삼성전자 · SK하이닉스 밸류에이션 분석 리포트\n\n")
        f.write(f"**분석일시**: {datetime.now().strftime('%Y년 %m월 %d일 %H:%M')}  \n")
        f.write(f"**데이터 출처**: FnGuide, 종목현황 CSV  \n")
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
        for name, stock in STOCKS.items():
            a = assessments[name]
            per_b = a["per_band"]
            pbr_b = a["pbr_band"]
            price = stock["price"]

            f.write(f"---\n\n")
            f.write(f"## 📈 {name} ({stock['code']}) 상세 분석\n\n")

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
        f.write(f"**데이터 출처**: FnGuide (comp.fnguide.com), 종목현황 CSV\n")

    return filename


def main():
    print("=" * 60)
    print("  삼성전자 · SK하이닉스 밸류에이션 분석 (Forward PER 중심)")
    print("=" * 60)
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

    filename = generate_report()
    print(f"✅ 리포트 생성 완료: {filename}")
    print()


if __name__ == "__main__":
    main()
