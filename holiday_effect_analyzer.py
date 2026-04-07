"""
한국 명절 (설날·추석) 전후 30일 코스피/코스닥 등락 분석
- 명절 전 30거래일 ~ 명절 후 30거래일 평균 수익률 패턴
- 최적 매수/매도 타이밍 분석
- 확률 기반 전략 제시
"""

import sqlite3
import os
import sys
from datetime import datetime, timedelta
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 시작 연도 필터 (커맨드라인 인자로 받을 수 있음)
START_YEAR = int(sys.argv[1]) if len(sys.argv) > 1 else 2000

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 한국 명절 날짜 (음력 → 양력 변환 결과)
# 설날: 음력 1월 1일, 추석: 음력 8월 15일
# 연휴 기준일 (본날) 사용
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

HOLIDAYS = {
    "설날": {
        2000: "2000-02-05",
        2001: "2001-01-24",
        2002: "2002-02-12",
        2003: "2003-02-01",
        2004: "2004-01-22",
        2005: "2005-02-09",
        2006: "2006-01-29",
        2007: "2007-02-18",
        2008: "2008-02-07",
        2009: "2009-01-26",
        2010: "2010-02-14",
        2011: "2011-02-03",
        2012: "2012-01-23",
        2013: "2013-02-10",
        2014: "2014-01-31",
        2015: "2015-02-19",
        2016: "2016-02-08",
        2017: "2017-01-28",
        2018: "2018-02-16",
        2019: "2019-02-05",
        2020: "2020-01-25",
        2021: "2021-02-12",
        2022: "2022-02-01",
        2023: "2023-01-22",
        2024: "2024-02-10",
        2025: "2025-01-29",
        2026: "2026-02-17",
    },
    "추석": {
        2000: "2000-09-12",
        2001: "2001-10-01",
        2002: "2002-09-21",
        2003: "2003-09-11",
        2004: "2004-09-28",
        2005: "2005-09-18",
        2006: "2006-10-06",
        2007: "2007-09-25",
        2008: "2008-09-14",
        2009: "2009-10-03",
        2010: "2010-09-22",
        2011: "2011-09-12",
        2012: "2012-09-30",
        2013: "2013-09-19",
        2014: "2014-09-08",
        2015: "2015-09-27",
        2016: "2016-09-15",
        2017: "2017-10-04",
        2018: "2018-09-24",
        2019: "2019-09-13",
        2020: "2020-10-01",
        2021: "2021-09-21",
        2022: "2022-09-10",
        2023: "2023-09-29",
        2024: "2024-09-17",
        2025: "2025-10-06",
    },
}


def load_data():
    """DB에서 코스피/코스닥 데이터 로드"""
    conn = sqlite3.connect(os.path.join(BASE_DIR, 'data', 'market_data.db'))
    c = conn.cursor()

    data = {}
    for idx_name, label in [("KS11", "코스피"), ("KQ11", "코스닥")]:
        c.execute(
            "SELECT date, close FROM index_data WHERE index_name=? ORDER BY date",
            (idx_name,)
        )
        rows = c.fetchall()
        # date → (close, index_in_list)
        dates = []
        closes = []
        for date_str, close_val in rows:
            dates.append(date_str)
            closes.append(close_val)
        data[label] = {"dates": dates, "closes": closes}

    conn.close()
    return data


def find_trading_day_index(dates, target_date_str):
    """주어진 날짜에 가장 가까운 거래일의 인덱스 반환 (이전 거래일)"""
    # target_date_str 이하 중 가장 가까운 날짜
    for i in range(len(dates) - 1, -1, -1):
        if dates[i] <= target_date_str:
            return i
    return None


def analyze_holiday_pattern(data, holiday_name, holiday_dates, window=10):
    """명절 전후 window 거래일 수익률 패턴 분석"""
    dates = data["dates"]
    closes = data["closes"]

    # 각 연도별 명절 전후 수익률 저장
    # day_returns[d] = [r1, r2, ...] where d is -30 to +30 (0 = 명절 직전 거래일)
    day_returns = defaultdict(list)
    # cumulative returns from day -30
    cum_returns_all = []

    years_used = []

    for year, date_str in sorted(holiday_dates.items()):
        # 명절 당일에 가장 가까운 이전 거래일 찾기
        holiday_idx = find_trading_day_index(dates, date_str)
        if holiday_idx is None:
            continue

        # 전후 window 거래일이 충분한지 확인
        start_idx = holiday_idx - window
        end_idx = holiday_idx + window

        if start_idx < 0 or end_idx >= len(dates):
            continue

        years_used.append(year)

        # 기준점: day -window의 종가
        base_close = closes[start_idx]

        cum_returns = []
        for d in range(-window, window + 1):
            idx = holiday_idx + d
            current_close = closes[idx]
            cum_ret = (current_close / base_close - 1) * 100
            cum_returns.append(cum_ret)

            # 일별 수익률 (전일 대비)
            if idx > 0:
                daily_ret = (closes[idx] / closes[idx - 1] - 1) * 100
                day_returns[d].append(daily_ret)

        cum_returns_all.append(cum_returns)

    return {
        "years_used": years_used,
        "day_returns": day_returns,
        "cum_returns_all": cum_returns_all,
        "window": window,
    }


def find_best_strategy(cum_returns_all, window):
    """최적 매수/매도 타이밍 찾기"""
    n_days = 2 * window + 1
    n_years = len(cum_returns_all)

    best_strategies = []

    # 모든 매수일/매도일 조합 검토
    for buy_day in range(-window, window + 1):
        for sell_day in range(buy_day + 1, window + 1):
            buy_idx = buy_day + window
            sell_idx = sell_day + window

            profits = []
            win_count = 0
            for year_data in cum_returns_all:
                # 수익률: (sell시점 cum - buy시점 cum)은 base 기준이므로
                # 실제 수익률 계산: (sell가 / buy가 - 1)
                # cum_ret = (price / base - 1) * 100
                # price = base * (1 + cum_ret/100)
                # profit = sell_price / buy_price - 1
                buy_cum = year_data[buy_idx]
                sell_cum = year_data[sell_idx]
                profit = ((1 + sell_cum / 100) / (1 + buy_cum / 100) - 1) * 100
                profits.append(profit)
                if profit > 0:
                    win_count += 1

            avg_profit = sum(profits) / len(profits)
            win_rate = win_count / len(profits) * 100
            max_profit = max(profits)
            min_profit = min(profits)

            best_strategies.append({
                "buy_day": buy_day,
                "sell_day": sell_day,
                "avg_profit": avg_profit,
                "win_rate": win_rate,
                "max_profit": max_profit,
                "min_profit": min_profit,
                "n_years": n_years,
            })

    # 승률 × 평균수익률 기준으로 정렬 (복합 점수)
    for s in best_strategies:
        s["score"] = s["win_rate"] * s["avg_profit"] / 100

    best_strategies.sort(key=lambda x: x["score"], reverse=True)

    return best_strategies


def generate_report(data):
    """리포트 생성"""
    report_date = datetime.now().strftime('%Y%m%d_%H%M%S')
    os.makedirs('results/analysis', exist_ok=True)

    # 필터링된 명절 데이터
    holidays_filtered = {}
    for h_name, h_dates in HOLIDAYS.items():
        holidays_filtered[h_name] = {y: d for y, d in h_dates.items() if y >= START_YEAR}

    suffix = f"_{START_YEAR}이후" if START_YEAR > 2000 else ""
    filename = f"results/analysis/명절효과_분석{suffix}_{report_date}.md"

    period_label = f"{START_YEAR}년 이후" if START_YEAR > 2000 else "전체"

    with open(filename, 'w', encoding='utf-8') as f:
        f.write("# 🎑 한국 명절 (설날·추석) 전후 주식시장 분석\n\n")
        f.write(f"**분석일시**: {datetime.now().strftime('%Y년 %m월 %d일 %H:%M')}  \n")
        f.write(f"**분석 기간**: {period_label}  \n")
        f.write(f"**분석 범위**: 설날 {len(holidays_filtered['설날'])}년 / 추석 {len(holidays_filtered['추석'])}년  \n")
        f.write(f"**분석 구간**: 명절 전 10거래일 ~ 명절 후 10거래일  \n")
        f.write(f"**대상 지수**: 코스피(KS11), 코스닥(KQ11)  \n\n")
        f.write("---\n\n")

        # 방법론 설명
        f.write("## 📋 분석 방법론\n\n")
        f.write("1. 설날/추석 당일 기준 **직전 거래일**을 Day 0으로 설정\n")
        f.write("2. Day -10 (명절 10거래일 전) ~ Day +10 (명절 10거래일 후) 구간 분석\n")
        f.write("3. 각 연도별 **누적 수익률** 패턴을 평균하여 전형적인 움직임 도출\n")
        f.write("4. 모든 매수일/매도일 조합의 **평균 수익률 × 승률** 기반 최적 전략 탐색\n\n")
        f.write("---\n\n")

        for market_name in ["코스피", "코스닥"]:
            market = data[market_name]

            f.write(f"## 📊 {market_name} 명절 효과 분석\n\n")

            for holiday_name in ["설날", "추석"]:
                result = analyze_holiday_pattern(
                    market, holiday_name, holidays_filtered[holiday_name], window=10
                )

                if not result["years_used"]:
                    continue

                years = result["years_used"]
                cum_all = result["cum_returns_all"]
                day_rets = result["day_returns"]
                window = result["window"]

                f.write(f"### 🎊 {market_name} × {holiday_name} (분석 연도: {min(years)}~{max(years)}, {len(years)}년)\n\n")

                # ── 평균 누적 수익률 그래프 ──
                f.write(f"#### 평균 누적 수익률 패턴 (Day -30 ~ Day +30)\n\n")
                f.write(f"Day 0 = {holiday_name} 직전 거래일, 기준점 = Day -{window} 종가\n\n")

                # 평균 누적 수익률 계산
                avg_cum = []
                for d_idx in range(2 * window + 1):
                    vals = [yr[d_idx] for yr in cum_all]
                    avg_cum.append(sum(vals) / len(vals))

                # 핵심 포인트 테이블
                f.write("| Day | 평균 누적수익률 | 일 설명 |\n")
                f.write("|:---:|:-------------:|:------:|\n")
                for d in range(-window, window + 1):
                    idx = d + window
                    desc = ""
                    if d == -window:
                        desc = "분석 시작"
                    elif d == -1:
                        desc = f"{holiday_name} 전일"
                    elif d == 0:
                        desc = f"{holiday_name} 직전 거래일"
                    elif d == 1:
                        desc = f"{holiday_name} 직후 거래일"
                    elif d == window:
                        desc = "분석 종료"
                    f.write(f"| D{d:+d} | {avg_cum[idx]:+.2f}% | {desc} |\n")
                f.write("\n")

                # ASCII 그래프
                f.write("**누적 수익률 그래프**\n\n")
                f.write("```\n")

                # 그래프 높이
                graph_height = 14
                min_val = min(avg_cum)
                max_val = max(avg_cum)
                val_range = max_val - min_val
                if val_range == 0:
                    val_range = 1

                n_days = 2 * window + 1
                # y축 레이블 폭
                for y in range(graph_height, -1, -1):
                    val = min_val + (max_val - min_val) * y / graph_height
                    line = f"  {val:>+6.2f}% │"
                    for d in range(-window, window + 1):
                        idx = d + window
                        bar_y = (avg_cum[idx] - min_val) / val_range * graph_height
                        if abs(bar_y - y) < 0.5:
                            if d == 0:
                                line += "◆"
                            else:
                                line += "●"
                        elif d == 0:
                            line += "│"
                        elif d % 5 == 0:
                            line += "·"
                        else:
                            line += " "
                    f.write(line + "\n")

                # x축
                f.write("         └" + "─" * n_days + "\n")
                f.write("          -10       -5        D0        +5       +10\n")
                f.write(f"                        ◆ = {holiday_name} 직전 거래일\n")
                f.write("```\n\n")

                # ── 일별 평균 수익률 (상승 확률 포함) ──
                f.write("#### 일별 수익률 분석\n\n")
                f.write("| Day | 평균 일수익률 | 상승 확률 | 상승일/전체 | 비고 |\n")
                f.write("|:---:|:-----------:|:--------:|:----------:|:----:|\n")

                notable_days = []
                for d in range(-10, 11):
                    if d not in day_rets or not day_rets[d]:
                        continue
                    rets = day_rets[d]
                    avg_r = sum(rets) / len(rets)
                    up_count = sum(1 for r in rets if r > 0)
                    up_rate = up_count / len(rets) * 100

                    note = ""
                    if up_rate >= 70:
                        note = "✅ 강한 상승 경향"
                        notable_days.append((d, avg_r, up_rate, "상승"))
                    elif up_rate >= 60:
                        note = "📈 상승 우세"
                    elif up_rate <= 30:
                        note = "⚠️ 강한 하락 경향"
                        notable_days.append((d, avg_r, up_rate, "하락"))
                    elif up_rate <= 40:
                        note = "📉 하락 우세"

                    f.write(f"| D{d:+d} | {avg_r:+.3f}% | {up_rate:.0f}% | {up_count}/{len(rets)} | {note} |\n")
                f.write("\n")

                # ── 최적 전략 찾기 ──
                best = find_best_strategy(cum_all, window)

                f.write("#### 🏆 최적 매수/매도 전략 (Top 10)\n\n")
                f.write("| 순위 | 매수일 | 매도일 | 보유기간 | 평균수익률 | 승률 | 최대↑ | 최대↓ | 점수 |\n")
                f.write("|:----:|:-----:|:-----:|:-------:|:---------:|:----:|:----:|:----:|:----:|\n")

                for rank, s in enumerate(best[:10], 1):
                    hold = s["sell_day"] - s["buy_day"]
                    marker = " ⭐" if rank == 1 else ""
                    f.write(f"| {rank} | D{s['buy_day']:+d} | D{s['sell_day']:+d} | {hold}일 | ")
                    f.write(f"{s['avg_profit']:+.2f}% | {s['win_rate']:.0f}% | ")
                    f.write(f"{s['max_profit']:+.1f}% | {s['min_profit']:+.1f}% | ")
                    f.write(f"{s['score']:.2f}{marker} |\n")
                f.write("\n")

                # 최적 전략 설명
                top = best[0]
                f.write(f"> **최적 전략**: **D{top['buy_day']:+d}에 매수 → D{top['sell_day']:+d}에 매도**  \n")
                f.write(f"> 보유 기간 {top['sell_day']-top['buy_day']}거래일, ")
                f.write(f"평균 수익률 **{top['avg_profit']:+.2f}%**, 승률 **{top['win_rate']:.0f}%**  \n")
                f.write(f"> ({len(years)}년 중 {int(top['win_rate']*len(years)/100)}회 수익)\n\n")

                # ── 단기 전략 (5일 이내) ──
                short_term = [s for s in best if s["sell_day"] - s["buy_day"] <= 5]
                short_term.sort(key=lambda x: x["score"], reverse=True)

                if short_term:
                    f.write("#### ⚡ 단기 전략 (보유 5거래일 이내, Top 5)\n\n")
                    f.write("| 순위 | 매수일 | 매도일 | 보유기간 | 평균수익률 | 승률 |\n")
                    f.write("|:----:|:-----:|:-----:|:-------:|:---------:|:----:|\n")
                    for rank, s in enumerate(short_term[:5], 1):
                        hold = s["sell_day"] - s["buy_day"]
                        f.write(f"| {rank} | D{s['buy_day']:+d} | D{s['sell_day']:+d} | {hold}일 | ")
                        f.write(f"{s['avg_profit']:+.2f}% | {s['win_rate']:.0f}% |\n")
                    f.write("\n")

                f.write("---\n\n")

        # ━━ 종합 결론 ━━
        f.write("## 🎯 종합 결론 및 투자 전략\n\n")

        # 모든 조합의 Top 전략 모아서 비교
        f.write("### 전체 Best 전략 비교\n\n")
        f.write("| 시장 | 명절 | 매수일 | 매도일 | 보유기간 | 평균수익률 | 승률 |\n")
        f.write("|:----:|:----:|:-----:|:-----:|:-------:|:---------:|:----:|\n")

        for market_name in ["코스피", "코스닥"]:
            market = data[market_name]
            for holiday_name in ["설날", "추석"]:
                result = analyze_holiday_pattern(
                    market, holiday_name, holidays_filtered[holiday_name], window=10
                )
                if not result["years_used"]:
                    continue
                best = find_best_strategy(result["cum_returns_all"], result["window"])
                top = best[0]
                hold = top["sell_day"] - top["buy_day"]
                f.write(f"| {market_name} | {holiday_name} | D{top['buy_day']:+d} | D{top['sell_day']:+d} | ")
                f.write(f"{hold}일 | {top['avg_profit']:+.2f}% | {top['win_rate']:.0f}% |\n")
        f.write("\n")

        # 실전 팁
        f.write("### 💡 실전 투자 팁\n\n")
        f.write("1. **명절 전 매수가 유리한 이유**\n")
        f.write("   - 명절 연휴 전 불확실성 회피 매도 → 주가 눌림\n")
        f.write("   - 연휴 후 기관·외국인 복귀 → 매수세 유입\n")
        f.write("   - 배당·실적 시즌과 겹칠 경우 시너지\n\n")
        f.write("2. **주의사항**\n")
        f.write("   - 과거 패턴이 미래를 보장하지 않음\n")
        f.write("   - 매크로 환경(금리, 환율, 지정학)이 패턴을 압도할 수 있음\n")
        f.write("   - 개별 종목은 지수와 다른 움직임을 보일 수 있음\n")
        f.write("   - 거래 비용(수수료, 세금) 고려 필요\n\n")
        f.write("3. **활용 방법**\n")
        f.write("   - 기존 보유 포지션의 **비중 조절** 참고로 활용\n")
        f.write("   - 명절 전 조정 시 **추가 매수 타이밍** 판단\n")
        f.write("   - ETF(KODEX 200, KODEX 코스닥150) 등 지수 추종 상품 활용\n\n")

        f.write("---\n\n")
        f.write("> **면책 조항**: 본 분석은 과거 데이터에 기반한 통계적 분석이며, ")
        f.write("미래 수익을 보장하지 않습니다. 투자 판단은 본인의 책임하에 이루어져야 합니다.\n\n")
        f.write(f"**분석 도구**: Python  \n")
        f.write(f"**데이터 출처**: Yahoo Finance (KS11, KQ11)\n")

    return filename


def main():
    period_label = f"{START_YEAR}년 이후" if START_YEAR > 2000 else "전체"
    print("=" * 60)
    print(f"  🎑 한국 명절 전후 주식시장 분석 ({period_label})")
    print("=" * 60)
    print()

    # 필터링
    holidays_filtered = {}
    for h_name, h_dates in HOLIDAYS.items():
        holidays_filtered[h_name] = {y: d for y, d in h_dates.items() if y >= START_YEAR}

    print("📥 데이터 로딩...")
    data = load_data()
    print(f"   코스피: {len(data['코스피']['dates'])}거래일")
    print(f"   코스닥: {len(data['코스닥']['dates'])}거래일")
    print()

    print("📊 분석 중...")
    for market_name in ["코스피", "코스닥"]:
        for holiday_name in ["설날", "추석"]:
            result = analyze_holiday_pattern(
                data[market_name], holiday_name, holidays_filtered[holiday_name], window=10
            )
            if result["years_used"]:
                best = find_best_strategy(result["cum_returns_all"], result["window"])
                top = best[0]
                print(f"  {market_name} × {holiday_name} ({len(result['years_used'])}년)")
                print(f"    최적: D{top['buy_day']:+d} 매수 → D{top['sell_day']:+d} 매도")
                print(f"    평균 {top['avg_profit']:+.2f}%, 승률 {top['win_rate']:.0f}%")
    print()

    filename = generate_report(data)
    print(f"✅ 리포트 생성 완료: {filename}")


if __name__ == "__main__":
    main()
