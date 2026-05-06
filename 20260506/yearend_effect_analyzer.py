"""
연말연초 효과 분석기
- 12월 마지막 30거래일 + 1월 첫 30거래일
- Day 0 = 12월 마지막 거래일
- 코스피(KS11), 코스닥(KQ11)
- 전체 기간 + 2010년 이후
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime
import os
import warnings
warnings.filterwarnings('ignore')

DB_PATH = os.path.join("data", "market_data.db")
from config import WEEKLY_RESEARCH_DIR as OUTPUT_DIR

WINDOW = 30  # 전후 30거래일


def load_index_data(index_name):
    """DB에서 지수 데이터 로드"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT date, close, change FROM index_data WHERE index_name=? ORDER BY date",
        conn, params=(index_name,)
    )
    conn.close()
    df["date"] = pd.to_datetime(df["date"])
    df["change_pct"] = df["change"] * 100  # decimal → %
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    return df


def find_yearend_days(df):
    """각 연도의 12월 마지막 거래일(Day 0) 인덱스 찾기"""
    yearend_indices = []
    years = sorted(df["year"].unique())
    
    for y in years:
        dec_mask = (df["year"] == y) & (df["month"] == 12)
        dec_days = df[dec_mask]
        if len(dec_days) == 0:
            continue
        
        # 다음 해 1월 데이터도 있는지 확인
        jan_mask = (df["year"] == y + 1) & (df["month"] == 1)
        jan_days = df[jan_mask]
        if len(jan_days) < 5:  # 1월 데이터 부족시 스킵
            continue
        
        last_dec_idx = dec_days.index[-1]
        yearend_indices.append((y, last_dec_idx))
    
    return yearend_indices


def analyze_yearend_effect(df, start_year=None):
    """연말연초 효과 분석"""
    yearend_list = find_yearend_days(df)
    
    if start_year:
        yearend_list = [(y, idx) for y, idx in yearend_list if y >= start_year]
    
    all_returns = []
    daily_returns_by_day = {}
    
    for y, day0_idx in yearend_list:
        pos0 = df.index.get_loc(day0_idx)
        
        # D-30 ~ D+30 범위 체크
        start_pos = pos0 - WINDOW
        end_pos = pos0 + WINDOW
        
        if start_pos < 0 or end_pos >= len(df):
            continue
        
        base_close = df.iloc[start_pos]["close"]  # D-30 종가 기준
        
        year_data = {}
        for d in range(-WINDOW, WINDOW + 1):
            p = pos0 + d
            close = df.iloc[p]["close"]
            cum_ret = (close / base_close - 1) * 100
            daily_chg = df.iloc[p]["change_pct"]
            year_data[d] = {
                "cum_return": cum_ret,
                "daily_change": daily_chg,
                "date": df.iloc[p]["date"],
            }
            
            if d not in daily_returns_by_day:
                daily_returns_by_day[d] = []
            daily_returns_by_day[d].append({
                "year": y,
                "cum_return": cum_ret,
                "daily_change": daily_chg,
            })
        
        all_returns.append({"year": y, "data": year_data})
    
    return all_returns, daily_returns_by_day


def compute_stats(daily_returns_by_day):
    """일별 통계 계산"""
    stats = {}
    for d in sorted(daily_returns_by_day.keys()):
        entries = daily_returns_by_day[d]
        cum_rets = [e["cum_return"] for e in entries]
        daily_chgs = [e["daily_change"] for e in entries]
        n = len(entries)
        up = sum(1 for c in daily_chgs if c > 0)
        
        stats[d] = {
            "avg_cum": np.mean(cum_rets),
            "med_cum": np.median(cum_rets),
            "min_cum": np.min(cum_rets),
            "max_cum": np.max(cum_rets),
            "avg_daily": np.mean(daily_chgs),
            "med_daily": np.median(daily_chgs),
            "up_count": up,
            "total": n,
            "up_pct": up / n * 100 if n > 0 else 0,
        }
    return stats


def _calc_strategies(all_returns, buy_range, sell_range_fn, top_n=10):
    """전략 탐색 공통 함수"""
    strategies = []
    
    for buy_d in buy_range:
        for sell_d in sell_range_fn(buy_d):
            profits = []
            for yr in all_returns:
                data = yr["data"]
                if buy_d in data and sell_d in data:
                    profit = data[sell_d]["cum_return"] - data[buy_d]["cum_return"]
                    profits.append(profit)
            
            if len(profits) < 5:
                continue
            
            avg_ret = np.mean(profits)
            win_count = sum(1 for p in profits if p > 0)
            win_rate = win_count / len(profits) * 100
            score = avg_ret * win_rate / 100
            max_up = max(profits)
            max_dn = min(profits)
            
            strategies.append({
                "buy_day": buy_d,
                "sell_day": sell_d,
                "hold_days": sell_d - buy_d,
                "avg_return": avg_ret,
                "win_rate": win_rate,
                "win_count": win_count,
                "total": len(profits),
                "max_up": max_up,
                "max_dn": max_dn,
                "score": score,
            })
    
    strategies.sort(key=lambda x: x["score"], reverse=True)
    return strategies[:top_n]


def find_optimal_strategies(all_returns, top_n=10):
    """최적 매수/매도 전략 (12월 매수 → 1월 매도만)"""
    return _calc_strategies(
        all_returns,
        buy_range=range(-WINDOW, 1),  # D-30 ~ D+0 (12월)
        sell_range_fn=lambda b: range(max(b + 1, 1), WINDOW + 1),  # D+1 이후 (1월)
        top_n=top_n,
    )


def find_all_strategies(all_returns, top_n=10):
    """전체 조합 전략 (1월→1월 포함)"""
    return _calc_strategies(
        all_returns,
        buy_range=range(-WINDOW, WINDOW + 1),
        sell_range_fn=lambda b: range(b + 1, WINDOW + 1),
        top_n=top_n,
    )


def find_d10_strategies(all_returns, top_n=10):
    """D-10~D+10 범위 최적 전략 (12월 매수 → 1월 매도)"""
    return _calc_strategies(
        all_returns,
        buy_range=range(-10, 1),  # D-10 ~ D+0
        sell_range_fn=lambda b: range(max(b + 1, 1), 11),  # D+1 ~ D+10
        top_n=top_n,
    )


def find_short_strategies(all_returns, max_hold=5, top_n=5):
    """단기 전략 (5거래일 이내, 12월 매수 → 1월 매도)"""
    return _calc_strategies(
        all_returns,
        buy_range=range(-WINDOW, 1),  # 12월만
        sell_range_fn=lambda b: range(max(b + 1, 1), min(b + max_hold + 1, WINDOW + 1)),  # 1월, 5일 이내
        top_n=top_n,
    )


def find_jan_strategies(all_returns, top_n=5):
    """1월 매수 → 1월 매도 전략 (번외)"""
    return _calc_strategies(
        all_returns,
        buy_range=range(1, WINDOW + 1),  # 1월만
        sell_range_fn=lambda b: range(b + 1, WINDOW + 1),
        top_n=top_n,
    )


def day_label(d):
    """Day number → label"""
    if d < 0:
        return f"D{d}"
    elif d == 0:
        return "D+0"
    else:
        return f"D+{d}"


def day_description(d):
    """Day 설명"""
    if d == 0:
        return "12월 마지막 거래일"
    elif d == -WINDOW:
        return "분석 시작"
    elif d == WINDOW:
        return "분석 종료"
    elif d == -1:
        return "연말 전일"
    elif d == 1:
        return "1월 첫 거래일"
    else:
        return ""


def make_ascii_graph(stats, keys=None):
    """누적 수익률 ASCII 그래프"""
    if keys is None:
        keys = sorted(stats.keys())
    
    values = [stats[d]["avg_cum"] for d in keys]
    vmin, vmax = min(values), max(values)
    span = vmax - vmin
    if span == 0:
        span = 1
    
    rows = 15
    lines = []
    
    # Header
    for r in range(rows, -1, -1):
        level = vmin + span * r / rows
        label = f"{level:+.2f}%"
        bar = ""
        for i, d in enumerate(keys):
            v = stats[d]["avg_cum"]
            v_row = round((v - vmin) / span * rows)
            if v_row == r:
                if d == 0:
                    bar += "◆"
                else:
                    bar += "●"
            elif d == 0:
                bar += "│"
            else:
                bar += " "
        
        lines.append(f"   {label:>8s} │{bar}")
    
    # Bottom
    lines.append(f"            └{'─' * len(keys)}")
    
    # X-axis labels
    x_label = "             "
    for i, d in enumerate(keys):
        if d == -WINDOW:
            x_label = f"          D-{WINDOW}" + " " * (len(keys) // 2 - 4) + "D0" + " " * (len(keys) // 2 - 4) + f"D+{WINDOW}"
            break
    lines.append(x_label)
    lines.append(f"                        ◆ = 12월 마지막 거래일")
    
    return "\n".join(lines)


def make_return_chart(stats):
    """누적수익률 바 차트"""
    lines = []
    # 주요 일자만
    key_days = list(range(-WINDOW, WINDOW + 1, 1))
    
    vals = [stats[d]["avg_cum"] for d in key_days if d in stats]
    if not vals:
        return ""
    
    max_abs = max(abs(v) for v in vals) if vals else 1
    if max_abs == 0:
        max_abs = 1
    bar_width = 40
    
    # 선택적으로 5일 간격 + 주요 포인트
    display_days = list(range(-WINDOW, WINDOW + 1, 5))
    if 0 not in display_days:
        display_days.append(0)
    if 1 not in display_days:
        display_days.append(1)
    if -1 not in display_days:
        display_days.append(-1)
    display_days = sorted(set(display_days))
    
    for d in display_days:
        if d not in stats:
            continue
        v = stats[d]["avg_cum"]
        label = day_label(d)
        
        if v >= 0:
            left = " " * bar_width + "│"
            right_len = int(v / max_abs * bar_width)
            right = "█" * right_len
            lines.append(f"{label:>5s} {v:+.2f}% {left}{right}")
        else:
            right = "│"
            left_len = int(abs(v) / max_abs * bar_width)
            left = " " * (bar_width - left_len) + "█" * left_len
            lines.append(f"{label:>5s} {v:+.2f}% {left}{right}")
    
    return "\n".join(lines)


def generate_report(results, period_label, index_name, index_label, stats, all_returns):
    """각 분석 단위 리포트 섹션 생성"""
    lines = []
    n_years = len(all_returns)
    years_range = f"{all_returns[0]['year']}~{all_returns[-1]['year']}" if all_returns else "N/A"
    
    lines.append(f"### 🎄 {index_label} × 연말연초 효과 (분석: {years_range}, {n_years}년)")
    lines.append("")
    lines.append(f"#### 평균 누적 수익률 패턴 (D-{WINDOW} ~ D+{WINDOW})")
    lines.append("")
    lines.append(f"Day 0 = 12월 마지막 거래일, 기준점 = D-{WINDOW} 종가")
    lines.append("")
    
    # 누적 수익률 테이블 (5일 간격 + 핵심 포인트)
    lines.append("| Day | 평균 누적수익률 | 중간값 | 상승확률 (당일) | 일 설명 |")
    lines.append("|:---:|:-------------:|:-----:|:-------------:|:------:|")
    
    display_days = list(range(-WINDOW, WINDOW + 1, 5))
    for key_d in [0, 1, -1]:
        if key_d not in display_days:
            display_days.append(key_d)
    display_days = sorted(set(display_days))
    
    for d in display_days:
        if d not in stats:
            continue
        s = stats[d]
        desc = day_description(d)
        dl = day_label(d)
        up_str = f"{s['up_count']}/{s['total']} ({s['up_pct']:.0f}%)"
        lines.append(f"| {dl} | {s['avg_cum']:+.2f}% | {s['med_cum']:+.2f}% | {up_str} | {desc} |")
    
    lines.append("")
    
    # 누적 수익률 차트
    lines.append("#### 누적 수익률 추이 차트")
    lines.append("")
    lines.append("```")
    lines.append(make_return_chart(stats))
    lines.append("```")
    lines.append("")
    
    # 일별 수익률 분석 (전체)
    lines.append("#### 📍 일별 수익률 상세 (D-10 ~ D+10)")
    lines.append("")
    lines.append("| Day | 평균 일수익률 | 상승 확률 | 상승일/전체 | 비고 |")
    lines.append("|:---:|:-----------:|:--------:|:----------:|:----:|")
    
    for d in range(-10, 11):
        if d not in stats:
            continue
        s = stats[d]
        dl = day_label(d)
        note = ""
        if s["up_pct"] >= 70:
            note = "✅ 강한 상승"
        elif s["up_pct"] >= 62:
            note = "📈 상승 우세"
        elif s["up_pct"] <= 35:
            note = "❌ 강한 하락"
        elif s["up_pct"] <= 42:
            note = "📉 하락 우세"
        
        if d == 0:
            note += " 🔔 연말"
        elif d == 1:
            note += " 🔔 신년"
        
        lines.append(f"| {dl} | {s['avg_daily']:+.3f}% | {s['up_pct']:.0f}% | {s['up_count']}/{s['total']} | {note} |")
    
    lines.append("")
    
    # 상승확률 바 차트 (D-10~D+10)
    lines.append("#### 📍 상승확률 추이 (D-10 ~ D+10)")
    lines.append("")
    lines.append("```")
    for d in range(-10, 11):
        if d not in stats:
            continue
        s = stats[d]
        dl = day_label(d)
        pct = s["up_pct"]
        filled = int(pct / 100 * 48)
        empty = 48 - filled
        marker = ""
        if pct >= 62:
            marker = " ◎"
        elif pct <= 40:
            marker = " ◀"
        line = f"{dl:>5s} ({s['total']:>2d}건) {'█' * filled}{'░' * empty} {pct:.0f}%{marker}"
        lines.append(line)
    lines.append("```")
    lines.append("")
    
    # 최적 전략 (12월 매수 → 1월 매도)
    top_strats = find_optimal_strategies(all_returns, top_n=10)
    lines.append("#### 🏆 최적 매수/매도 전략 — 12월 매수 → 1월 매도 (Top 10)")
    lines.append("")
    lines.append("| 순위 | 매수일 | 매도일 | 보유기간 | 평균수익률 | 승률 | 최대↑ | 최대↓ | 점수 |")
    lines.append("|:----:|:-----:|:-----:|:-------:|:---------:|:----:|:----:|:----:|:----:|")
    
    for i, st in enumerate(top_strats):
        star = " ⭐" if i == 0 else ""
        lines.append(
            f"| {i+1} | {day_label(st['buy_day'])} | {day_label(st['sell_day'])} | "
            f"{st['hold_days']}일 | {st['avg_return']:+.2f}% | {st['win_rate']:.0f}% | "
            f"{st['max_up']:+.1f}% | {st['max_dn']:+.1f}% | {st['score']:.2f}{star} |"
        )
    
    lines.append("")
    
    if top_strats:
        best = top_strats[0]
        lines.append(
            f"> **최적 전략**: **{day_label(best['buy_day'])}에 매수 → {day_label(best['sell_day'])}에 매도**  "
        )
        lines.append(
            f"> 보유 기간 {best['hold_days']}거래일, 평균 수익률 **{best['avg_return']:+.2f}%**, "
            f"승률 **{best['win_rate']:.0f}%** ({best['win_count']}/{best['total']})"
        )
        lines.append("")
    
    # 단기 전략 (12월 매수 → 1월 매도, 5일 이내)
    short_strats = find_short_strategies(all_returns, max_hold=5, top_n=5)
    lines.append("#### ⚡ 단기 전략 — 12월 매수 → 1월 매도, 5거래일 이내 (Top 5)")
    lines.append("")
    lines.append("| 순위 | 매수일 | 매도일 | 보유기간 | 평균수익률 | 승률 |")
    lines.append("|:----:|:-----:|:-----:|:-------:|:---------:|:----:|")
    
    for i, st in enumerate(short_strats):
        lines.append(
            f"| {i+1} | {day_label(st['buy_day'])} | {day_label(st['sell_day'])} | "
            f"{st['hold_days']}일 | {st['avg_return']:+.2f}% | {st['win_rate']:.0f}% |"
        )
    
    lines.append("")
    
    # D-10 ~ D+10 단기 집중 분석
    d10_strats = find_d10_strategies(all_returns, top_n=10)
    lines.append("#### 🔍 D-10 ~ D+10 단기 집중 전략 — 12월 매수 → 1월 매도 (Top 10)")
    lines.append("")
    lines.append("| 순위 | 매수일 | 매도일 | 보유기간 | 평균수익률 | 승률 | 최대↑ | 최대↓ | 점수 |")
    lines.append("|:----:|:-----:|:-----:|:-------:|:---------:|:----:|:----:|:----:|:----:|")
    
    for i, st in enumerate(d10_strats):
        star = " ⭐" if i == 0 else ""
        lines.append(
            f"| {i+1} | {day_label(st['buy_day'])} | {day_label(st['sell_day'])} | "
            f"{st['hold_days']}일 | {st['avg_return']:+.2f}% | {st['win_rate']:.0f}% | "
            f"{st['max_up']:+.1f}% | {st['max_dn']:+.1f}% | {st['score']:.2f}{star} |"
        )
    
    lines.append("")
    
    if d10_strats:
        best = d10_strats[0]
        lines.append(
            f"> **D-10~D+10 최적**: **{day_label(best['buy_day'])}에 매수 → {day_label(best['sell_day'])}에 매도**  "
        )
        lines.append(
            f"> 보유 기간 {best['hold_days']}거래일, 평균 수익률 **{best['avg_return']:+.2f}%**, "
            f"승률 **{best['win_rate']:.0f}%** ({best['win_count']}/{best['total']})"
        )
        lines.append("")
    
    return "\n".join(lines), top_strats, short_strats, d10_strats


def generate_full_report():
    """전체 리포트 생성"""
    now = datetime.now()
    ts = now.strftime("%Y%m%d_%H%M%S")
    
    print("=" * 60)
    print("연말연초 효과 분석기")
    print("=" * 60)
    
    # 데이터 로드
    print("\n[1/3] 데이터 로드 중...")
    kospi = load_index_data("KS11")
    kosdaq = load_index_data("KQ11")
    print(f"  코스피: {len(kospi)}일 ({kospi['date'].min().date()} ~ {kospi['date'].max().date()})")
    print(f"  코스닥: {len(kosdaq)}일 ({kosdaq['date'].min().date()} ~ {kosdaq['date'].max().date()})")
    
    # 분석 실행
    report_lines = []
    report_lines.append("# 🎅 연말연초 효과 분석: 최적 매수·매도 전략")
    report_lines.append("")
    report_lines.append(f"**분석일시**: {now.strftime('%Y년 %m월 %d일 %H:%M')}")
    report_lines.append("**데이터 출처**: Yahoo Finance (지수)")
    report_lines.append(f"**분석 구간**: 12월 마지막 {WINDOW}거래일 ~ 1월 첫 {WINDOW}거래일")
    report_lines.append("**Day 0**: 12월 마지막 거래일 (연말 마감일)")
    report_lines.append("**대상 지수**: 코스피(KS11), 코스닥(KQ11)")
    report_lines.append("")
    report_lines.append("---")
    report_lines.append("")
    report_lines.append("## 📋 분석 방법론")
    report_lines.append("")
    report_lines.append("1. 매년 **12월 마지막 거래일**을 Day 0으로 설정")
    report_lines.append(f"2. Day -{WINDOW} (12월 초) ~ Day +{WINDOW} (1월 말) 구간 분석")
    report_lines.append(f"3. D-{WINDOW} 종가를 기준으로 **누적 수익률** 계산")
    report_lines.append("4. 모든 매수일/매도일 조합의 **평균 수익률 × 승률** 기반 최적 전략 탐색")
    report_lines.append("5. 전체 기간 + 2010년 이후(금융시장 안정화) 별도 분석")
    report_lines.append("")
    report_lines.append("---")
    report_lines.append("")
    
    all_best_strategies = {}  # 결론용
    
    # 기간별 분석
    periods = [
        (None, "전체 기간"),
        (2010, "2010년 이후 (금융시장 안정화)"),
    ]
    
    for start_year, period_label in periods:
        print(f"\n[2/3] {period_label} 분석 중...")
        report_lines.append(f"## 📊 {period_label} 분석")
        report_lines.append("")
        
        for idx_code, idx_label in [("KS11", "코스피"), ("KQ11", "코스닥")]:
            df = kospi if idx_code == "KS11" else kosdaq
            
            all_returns, daily_by_day = analyze_yearend_effect(df, start_year)
            
            if not all_returns:
                print(f"  {idx_label}: 데이터 부족으로 스킵")
                continue
            
            stats = compute_stats(daily_by_day)
            
            yr_start = all_returns[0]["year"]
            yr_end = all_returns[-1]["year"]
            print(f"  {idx_label}: {len(all_returns)}년 분석 ({yr_start}~{yr_end})")
            
            section, top_strats, short_strats, d10_strats = generate_report(
                all_returns, period_label, idx_code, idx_label, stats, all_returns
            )
            report_lines.append(section)
            
            # 1월→1월 전략도 저장 (번외용)
            jan_strats = find_jan_strategies(all_returns, top_n=5)
            
            key = f"{period_label}_{idx_label}"
            all_best_strategies[key] = {
                "top": top_strats,
                "short": short_strats,
                "d10": d10_strats,
                "jan": jan_strats,
                "n_years": len(all_returns),
                "stats": stats,
                "all_returns": all_returns,
                "years_range": f"{yr_start}~{yr_end}",
            }
        
        report_lines.append("---")
        report_lines.append("")
    
    # 결론 섹션
    print("\n[3/3] 결론 생성 중...")
    report_lines.append("## 🎯 최종 결론: 연말연초 최적 매매 전략")
    report_lines.append("")
    report_lines.append("> **모든 전략은 \"12월 매수 → 1월 매도\" 원칙** 기준입니다.")
    report_lines.append("")
    
    kb_full = all_best_strategies.get("전체 기간_코스피", {})
    kb_2010 = all_best_strategies.get("2010년 이후 (금융시장 안정화)_코스피", {})
    kq_full = all_best_strategies.get("전체 기간_코스닥", {})
    kq_2010 = all_best_strategies.get("2010년 이후 (금융시장 안정화)_코스닥", {})
    
    # ── 비교표 ──
    report_lines.append("### 📍 전체 기간 vs 2010년 이후 비교 (12월 매수 → 1월 매도)")
    report_lines.append("")
    report_lines.append("#### 코스피")
    report_lines.append("")
    report_lines.append("| 구분 | 기간 | 매수일 | 매도일 | 보유기간 | 평균수익률 | 승률 |")
    report_lines.append("|:----:|:----:|:-----:|:-----:|:-------:|:---------:|:----:|")
    
    for label, data in [("전체", kb_full), ("**2010~**", kb_2010)]:
        if data.get("top"):
            best = data["top"][0]
            report_lines.append(
                f"| {label} | {data['years_range']} ({data['n_years']}년) | "
                f"**{day_label(best['buy_day'])}** | **{day_label(best['sell_day'])}** | "
                f"{best['hold_days']}일 | {best['avg_return']:+.2f}% | {best['win_rate']:.0f}% |"
            )
        if data.get("short"):
            best = data["short"][0]
            sl = "전체(단기)" if label == "전체" else "2010~(단기)"
            report_lines.append(
                f"| {sl} | {data['years_range']} | "
                f"{day_label(best['buy_day'])} | {day_label(best['sell_day'])} | "
                f"{best['hold_days']}일 | {best['avg_return']:+.2f}% | {best['win_rate']:.0f}% |"
            )
    
    report_lines.append("")
    report_lines.append("#### 코스닥")
    report_lines.append("")
    report_lines.append("| 구분 | 기간 | 매수일 | 매도일 | 보유기간 | 평균수익률 | 승률 |")
    report_lines.append("|:----:|:----:|:-----:|:-----:|:-------:|:---------:|:----:|")
    
    for label, data in [("전체", kq_full), ("**2010~**", kq_2010)]:
        if data.get("top"):
            best = data["top"][0]
            report_lines.append(
                f"| {label} | {data['years_range']} ({data['n_years']}년) | "
                f"**{day_label(best['buy_day'])}** | **{day_label(best['sell_day'])}** | "
                f"{best['hold_days']}일 | {best['avg_return']:+.2f}% | {best['win_rate']:.0f}% |"
            )
        if data.get("short"):
            best = data["short"][0]
            sl = "전체(단기)" if label == "전체" else "2010~(단기)"
            report_lines.append(
                f"| {sl} | {data['years_range']} | "
                f"{day_label(best['buy_day'])} | {day_label(best['sell_day'])} | "
                f"{best['hold_days']}일 | {best['avg_return']:+.2f}% | {best['win_rate']:.0f}% |"
            )
    
    report_lines.append("")
    
    # ── D-10 ~ D+10 단기 집중 비교 ──
    report_lines.append("### 📍 D-10 ~ D+10 단기 집중 분석 (12월 마지막 10거래일 → 1월 첫 10거래일)")
    report_lines.append("")
    report_lines.append("연말연초 핵심 구간만 집중 분석한 결과:")
    report_lines.append("")
    
    report_lines.append("#### 코스피")
    report_lines.append("")
    report_lines.append("| 구분 | 매수일 | 매도일 | 보유기간 | 평균수익률 | 승률 | 최대↑ | 최대↓ | 점수 |")
    report_lines.append("|:----:|:-----:|:-----:|:-------:|:---------:|:----:|:----:|:----:|:----:|")
    
    for label, data in [("전체", kb_full), ("**2010~**", kb_2010)]:
        d10 = data.get("d10", [])
        for i, st in enumerate(d10[:5]):
            star = " ⭐" if i == 0 else ""
            report_lines.append(
                f"| {label if i == 0 else ''} | {day_label(st['buy_day'])} | {day_label(st['sell_day'])} | "
                f"{st['hold_days']}일 | {st['avg_return']:+.2f}% | {st['win_rate']:.0f}% | "
                f"{st['max_up']:+.1f}% | {st['max_dn']:+.1f}% | {st['score']:.2f}{star} |"
            )
    
    report_lines.append("")
    report_lines.append("#### 코스닥")
    report_lines.append("")
    report_lines.append("| 구분 | 매수일 | 매도일 | 보유기간 | 평균수익률 | 승률 | 최대↑ | 최대↓ | 점수 |")
    report_lines.append("|:----:|:-----:|:-----:|:-------:|:---------:|:----:|:----:|:----:|:----:|")
    
    for label, data in [("전체", kq_full), ("**2010~**", kq_2010)]:
        d10 = data.get("d10", [])
        for i, st in enumerate(d10[:5]):
            star = " ⭐" if i == 0 else ""
            report_lines.append(
                f"| {label if i == 0 else ''} | {day_label(st['buy_day'])} | {day_label(st['sell_day'])} | "
                f"{st['hold_days']}일 | {st['avg_return']:+.2f}% | {st['win_rate']:.0f}% | "
                f"{st['max_up']:+.1f}% | {st['max_dn']:+.1f}% | {st['score']:.2f}{star} |"
            )
    
    report_lines.append("")
    
    # ── 연말 마감일/신년 첫날 ──
    report_lines.append("### 📍 연말 마지막 거래일 (D+0) & 신년 첫 거래일 (D+1)")
    report_lines.append("")
    report_lines.append("| 지수 | Day | 전체 기간 상승확률 | 2010년 이후 상승확률 |")
    report_lines.append("|:----:|:---:|:----------------:|:------------------:|")
    
    for idx_label in ["코스피", "코스닥"]:
        for d in [0, 1]:
            full_key = f"전체 기간_{idx_label}"
            y2010_key = f"2010년 이후 (금융시장 안정화)_{idx_label}"
            dl = day_label(d)
            
            full_str = y2010_str = ""
            full_stats = all_best_strategies.get(full_key, {}).get("stats", {})
            y2010_stats = all_best_strategies.get(y2010_key, {}).get("stats", {})
            
            if d in full_stats:
                s = full_stats[d]
                full_str = f"**{s['up_pct']:.0f}%** ({s['up_count']}/{s['total']}), 평균 {s['avg_daily']:+.3f}%"
            if d in y2010_stats:
                s = y2010_stats[d]
                y2010_str = f"**{s['up_pct']:.0f}%** ({s['up_count']}/{s['total']}), 평균 {s['avg_daily']:+.3f}%"
            
            report_lines.append(f"| {idx_label} | {dl} | {full_str} | {y2010_str} |")
    
    report_lines.append("")
    
    # ── 구간별 수익률 비교 ──
    report_lines.append("### 📍 구간별 평균 수익률 비교")
    report_lines.append("")
    report_lines.append("D-30 종가 기준 누적 수익률:")
    report_lines.append("")
    report_lines.append("| 시점 | 코스피(전체) | 코스피(2010~) | 코스닥(전체) | 코스닥(2010~) |")
    report_lines.append("|:----:|:----------:|:------------:|:----------:|:------------:|")
    
    compare_days = [-20, -15, -10, -5, -1, 0, 1, 5, 10, 15, 20, 25, 30]
    for d in compare_days:
        dl = day_label(d)
        vals = []
        for key in ["전체 기간_코스피", "2010년 이후 (금융시장 안정화)_코스피",
                     "전체 기간_코스닥", "2010년 이후 (금융시장 안정화)_코스닥"]:
            st = all_best_strategies.get(key, {}).get("stats", {})
            if d in st:
                vals.append(f"{st[d]['avg_cum']:+.2f}%")
            else:
                vals.append("-")
        report_lines.append(f"| {dl} | {vals[0]} | {vals[1]} | {vals[2]} | {vals[3]} |")
    
    report_lines.append("")
    
    # ── 2010년 이후 핵심 발견 ──
    report_lines.append("### 📍 2010년 이후 데이터의 의미")
    report_lines.append("")
    report_lines.append("> 2008년 금융위기 전후의 극단적 시장 상황이 제외되어,")
    report_lines.append("> 현재 시장 구조에 더 부합하는 패턴을 보여줍니다.")
    report_lines.append("")
    
    for idx_label, full_data, y2010_data in [("코스피", kb_full, kb_2010), ("코스닥", kq_full, kq_2010)]:
        if y2010_data.get("top") and full_data.get("top"):
            bf = full_data["top"][0]
            b2 = y2010_data["top"][0]
            report_lines.append(f"**{idx_label} 핵심 발견:**")
            report_lines.append(f"- 전체 최적: {day_label(bf['buy_day'])} → {day_label(bf['sell_day'])} (수익률 {bf['avg_return']:+.2f}%, 승률 {bf['win_rate']:.0f}%)")
            report_lines.append(f"- 2010~ 최적: {day_label(b2['buy_day'])} → {day_label(b2['sell_day'])} (수익률 {b2['avg_return']:+.2f}%, 승률 {b2['win_rate']:.0f}%)")
            if y2010_data.get("d10"):
                bd = y2010_data["d10"][0]
                report_lines.append(f"- 2010~ D-10~D+10 최적: {day_label(bd['buy_day'])} → {day_label(bd['sell_day'])} (수익률 {bd['avg_return']:+.2f}%, 승률 {bd['win_rate']:.0f}%)")
            report_lines.append("")
    
    # ── 실전 전략 박스 ──
    report_lines.append("### 📍 종합 실전 전략")
    report_lines.append("")
    
    for idx_label, data in [("코스피", kb_2010), ("코스닥", kq_2010)]:
        if data.get("top"):
            best = data["top"][0]
            report_lines.append(f"#### {idx_label} 연말연초 매매")
            report_lines.append("")
            report_lines.append("```")
            report_lines.append("╔══════════════════════════════════════════════════════════════╗")
            report_lines.append(f"║         {idx_label} 연말연초 전략 (2010년 이후 기준)             ║")
            report_lines.append("╠══════════════════════════════════════════════════════════════╣")
            report_lines.append("║                                                              ║")
            report_lines.append(f"║  📌 최적 전략 (12월 매수 → 1월 매도)                         ║")
            report_lines.append(f"║    매수: {day_label(best['buy_day']):>5s} (12월)                                    ║")
            report_lines.append(f"║    매도: {day_label(best['sell_day']):>5s} (1월)                                     ║")
            report_lines.append(f"║    수익률: {best['avg_return']:+.2f}%, 승률: {best['win_rate']:.0f}%                         ║")
            report_lines.append("║                                                              ║")
            
            if data.get("d10"):
                d10b = data["d10"][0]
                report_lines.append(f"║  📌 단기 전략 (D-10~D+10 구간)                               ║")
                report_lines.append(f"║    매수: {day_label(d10b['buy_day']):>5s} → 매도: {day_label(d10b['sell_day']):>5s} ({d10b['hold_days']}일 보유)              ║")
                report_lines.append(f"║    수익률: {d10b['avg_return']:+.2f}%, 승률: {d10b['win_rate']:.0f}%                         ║")
                report_lines.append("║                                                              ║")
            
            report_lines.append("║  ⚠ 주의사항                                                 ║")
            report_lines.append("║    • 과거 통계이며 미래 수익을 보장하지 않음                    ║")
            if idx_label == "코스닥":
                report_lines.append("║    • 코스닥은 변동성이 높아 손절 기준 설정 필수                  ║")
            else:
                report_lines.append("║    • 대외 환경(금리, 환율, 지정학) 고려 필수                    ║")
            report_lines.append("║    • 분할 매수로 리스크 분산 권장                               ║")
            report_lines.append("║                                                              ║")
            report_lines.append("╚══════════════════════════════════════════════════════════════╝")
            report_lines.append("```")
            report_lines.append("")
    
    # ── 명절효과 비교 ──
    report_lines.append("### 📍 명절 효과 vs 연말연초 효과 비교")
    report_lines.append("")
    report_lines.append("> 설날 효과 (기존 분석): 코스피 D-3→D+6 매수매도, 평균 +2.14%, 승률 78%  ")
    report_lines.append("> 연말연초 효과: 이 분석 결과 참고  ")
    report_lines.append("> 두 효과가 겹치는 1~2월에는 설날 효과와 연초 효과가 복합적으로 작용할 수 있음")
    report_lines.append("")
    
    # ── 번외: 1월 매수 → 1월 매도 ──
    report_lines.append("---")
    report_lines.append("")
    report_lines.append("## 📎 번외: 1월 매수 → 1월 매도 전략")
    report_lines.append("")
    report_lines.append("> 본 분석의 핵심은 \"12월 매수 → 1월 매도\"이지만,")
    report_lines.append("> 참고용으로 1월 중 매수·매도 전략도 기록합니다.")
    report_lines.append("")
    
    for idx_label, full_data, y2010_data in [("코스피", kb_full, kb_2010), ("코스닥", kq_full, kq_2010)]:
        jan_full = full_data.get("jan", [])
        jan_2010 = y2010_data.get("jan", [])
        
        if jan_full or jan_2010:
            report_lines.append(f"#### {idx_label}")
            report_lines.append("")
            report_lines.append("| 구분 | 매수일 | 매도일 | 보유기간 | 평균수익률 | 승률 |")
            report_lines.append("|:----:|:-----:|:-----:|:-------:|:---------:|:----:|")
            
            for i, st in enumerate(jan_full[:3]):
                report_lines.append(
                    f"| 전체 | {day_label(st['buy_day'])} | {day_label(st['sell_day'])} | "
                    f"{st['hold_days']}일 | {st['avg_return']:+.2f}% | {st['win_rate']:.0f}% |"
                )
            for i, st in enumerate(jan_2010[:3]):
                report_lines.append(
                    f"| 2010~ | {day_label(st['buy_day'])} | {day_label(st['sell_day'])} | "
                    f"{st['hold_days']}일 | {st['avg_return']:+.2f}% | {st['win_rate']:.0f}% |"
                )
            report_lines.append("")
    
    report_lines.append("---")
    report_lines.append("")
    report_lines.append("**데이터 출처**: Yahoo Finance 지수 데이터")
    report_lines.append("**분석 도구**: Python + pandas")
    
    # 파일 저장
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filename = f"연말연초_효과_분석_{ts}.md"
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    
    print(f"\n✅ 리포트 저장: {filepath}")
    return filepath


if __name__ == "__main__":
    generate_full_report()
