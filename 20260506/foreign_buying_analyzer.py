"""
외국인 순매수 Top 20 분석기
- 코스피, 코스닥, 선물 시장별 외국인 순매수 상위 20일 추출
- 해당일 이후 1~30 거래일간 코스피/코스닥 지수 변화 분석
- 최근 20년 / 최근 10년 비교 분석
- data/investor_data.db에서 투자자 매매동향 로드 (foreign_selling_analyzer에서 수집)
"""

import warnings
warnings.filterwarnings('ignore')

import pandas as pd
import numpy as np
import sqlite3
import os
from datetime import datetime

# ─────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "market_data.db")
INVESTOR_DB_PATH = os.path.join(BASE_DIR, "data", "investor_data.db")
CACHE_DIR = os.path.join(BASE_DIR, "data", "cache")
from config import WEEKLY_RESEARCH_DIR as RESULTS_DIR

TOP_N = 20
FOLLOW_DAYS = 30  # 이후 추적할 거래일 수


def load_investor_data(sosok):
    """투자자 매매동향 로드 — DB 우선, CSV fallback"""
    if os.path.exists(INVESTOR_DB_PATH):
        try:
            conn = sqlite3.connect(INVESTOR_DB_PATH)
            df = pd.read_sql_query(
                "SELECT date as '날짜', individual as '개인', foreign_ as '외국인', "
                "institution as '기관계', finance as '금융투자', insurance as '보험', "
                "trust as '투신 (사모)', bank as '은행', other_finance as '기타금융기관', "
                "pension as '연기금등', other_corp as '기타법인' "
                "FROM investor_daily WHERE market = ? ORDER BY date",
                conn, params=(sosok,), parse_dates=["날짜"],
            )
            conn.close()
            if len(df) > 100:
                df["외국인"] = pd.to_numeric(df["외국인"], errors="coerce")
                print(f"  [DB] investor_data.db에서 {len(df)}일 로드")
                return df
        except Exception:
            pass

    cache_file = os.path.join(CACHE_DIR, f"investor_{sosok}.csv")
    if os.path.exists(cache_file):
        df = pd.read_csv(cache_file, parse_dates=["날짜"])
        df["외국인"] = pd.to_numeric(df["외국인"], errors="coerce")
        print(f"  [CSV] {cache_file}에서 {len(df)}일 로드")
        return df

    raise FileNotFoundError(
        f"투자자 데이터 없음: DB({INVESTOR_DB_PATH}) 또는 캐시({cache_file}) 필요. "
        f"먼저 foreign_selling_analyzer.py를 실행하세요."
    )


def load_index_data():
    """DB에서 코스피/코스닥 지수 데이터 로드"""
    conn = sqlite3.connect(DB_PATH)
    kospi = pd.read_sql(
        "SELECT date, close FROM index_data WHERE index_name='KS11' ORDER BY date",
        conn, parse_dates=["date"]
    )
    kosdaq = pd.read_sql(
        "SELECT date, close FROM index_data WHERE index_name='KQ11' ORDER BY date",
        conn, parse_dates=["date"]
    )
    conn.close()
    return kospi, kosdaq


def get_after_returns(index_df, event_dates, follow_days=30):
    """이벤트 날짜 이후 N거래일간 수익률 계산"""
    index_df = index_df.sort_values("date").reset_index(drop=True)
    dates = index_df["date"].values
    closes = index_df["close"].values

    results = []
    for event_date in event_dates:
        idx = np.searchsorted(dates, np.datetime64(event_date))
        if idx >= len(dates):
            continue

        base_close = closes[idx]
        row = {"event_date": event_date, "base_close": base_close}

        for d in range(1, follow_days + 1):
            future_idx = idx + d
            if future_idx < len(dates):
                future_close = closes[future_idx]
                ret = (future_close / base_close - 1) * 100
                row[f"D+{d}"] = ret
            else:
                row[f"D+{d}"] = np.nan

        results.append(row)

    return pd.DataFrame(results)


def analyze_market(investor_df, market_name, index_kospi, index_kosdaq,
                   start_year, period_name):
    """특정 시장의 외국인 순매수 Top N 분석"""
    mask = investor_df["날짜"] >= datetime(start_year, 1, 1)
    df = investor_df[mask].copy()

    if df.empty:
        return None

    foreign_col = "외국인"
    df[foreign_col] = pd.to_numeric(df[foreign_col], errors="coerce")

    # 순매수 상위 (가장 큰 양수 = 가장 많이 산 날)
    top_buying = df.nlargest(TOP_N, foreign_col).reset_index(drop=True)

    event_dates = top_buying["날짜"].tolist()

    kospi_returns = get_after_returns(index_kospi, event_dates, FOLLOW_DAYS)
    kosdaq_returns = get_after_returns(index_kosdaq, event_dates, FOLLOW_DAYS)

    return {
        "market_name": market_name,
        "period_name": period_name,
        "top_buying": top_buying,
        "kospi_returns": kospi_returns,
        "kosdaq_returns": kosdaq_returns,
    }


def format_number(val):
    """숫자 포맷 (억원 단위)"""
    if pd.isna(val):
        return "N/A"
    return f"{val:,.0f}"


def generate_report(all_results):
    """분석 결과를 마크다운 리포트로 생성"""
    now_str = datetime.now().strftime("%Y년 %m월 %d일 %H:%M")

    lines = []
    lines.append("# 📊 외국인 순매수 Top 20 이후 지수 변화 분석")
    lines.append("")
    lines.append(f"**분석일시**: {now_str}")
    lines.append(f"**데이터 출처**: Naver Finance (투자자별 매매동향)")
    lines.append(f"**분석 대상**: 코스피, 코스닥, 선물 시장 외국인 순매수 상위 {TOP_N}일")
    lines.append(f"**추적 기간**: 이후 {FOLLOW_DAYS} 거래일")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── 결론부터: 매매 전략 요약 ──
    _kospi_20y = [r for r in all_results if "20년" in r["period_name"] and r["market_name"] == "KOSPI"]
    _d1_avg = 0
    _d5_avg = 0
    _d10_avg = 0
    _d20_avg = 0
    _d20_up = 0
    if _kospi_20y:
        _kr = _kospi_20y[0]["kospi_returns"]
        if not _kr.empty:
            _d1_avg = _kr["D+1"].mean() if "D+1" in _kr else 0
            _d5_avg = _kr["D+5"].mean() if "D+5" in _kr else 0
            _d10_avg = _kr["D+10"].mean() if "D+10" in _kr else 0
            _d20_avg = _kr["D+20"].mean() if "D+20" in _kr else 0
            _d20_up = (_kr["D+20"] > 0).mean() * 100 if "D+20" in _kr else 0

    lines.append("## 🚨 결론부터: 외국인 대량 순매수 이후 전략")
    lines.append("")

    if _d20_avg > 0 and _d20_up >= 55:
        lines.append("> **외국인이 대량으로 샀다 → 🟢 추세 추종! 따라 사도 된다**")
        lines.append("")
        lines.append("```")
        lines.append("╔══════════════════════════════════════════════════════════════╗")
        lines.append("║  📌 외국인 대량 순매수 = 상승 모멘텀 지속 신호               ║")
        lines.append("╠══════════════════════════════════════════════════════════════╣")
        lines.append("║                                                              ║")
        lines.append("║  🟢 기 보유 중 → 보유 유지! 추가 상승 기대                  ║")
        if _d1_avg > 0:
            lines.append("║  🟡 미 보유 시 → D+1~3 눌림목에서 분할 매수 진입          ║")
        else:
            lines.append("║  🟡 미 보유 시 → D+3~5 조정 후 분할 매수 진입             ║")
        lines.append("║                                                              ║")
        lines.append(f"║  📈 D+20 기준: 평균 수익률 {_d20_avg:+.2f}%, 상승확률 {_d20_up:.0f}%     ║")
        lines.append("║                                                              ║")
        lines.append("║  📍 차익실현(매도) 시점:                                     ║")
        if _d20_avg > _d10_avg:
            lines.append("║    → D+20~30에서 분할 매도 (상승 추세 충분히 활용)         ║")
        else:
            lines.append("║    → D+10~15에서 1차 매도, 잔량은 D+20~30                 ║")
        lines.append("║                                                              ║")
        lines.append("╚══════════════════════════════════════════════════════════════╝")
    else:
        lines.append("> **외국인이 대량으로 샀다 → 🔴 추격 매수 주의! 고점 신호일 수 있다**")
        lines.append("")
        lines.append("```")
        lines.append("╔══════════════════════════════════════════════════════════════╗")
        lines.append("║  📌 외국인 대량 순매수 = 고점 경고 가능성                     ║")
        lines.append("╠══════════════════════════════════════════════════════════════╣")
        lines.append("║                                                              ║")
        lines.append("║  🔴 기 보유 중 → 분할 매도 고려! 차익실현 타이밍             ║")
        lines.append("║  ❌ 미 보유 시 → 추격 매수 금지! 조정 후 진입 대기           ║")
        lines.append("║                                                              ║")
        lines.append(f"║  📉 D+20 기준: 평균 수익률 {_d20_avg:+.2f}%, 상승확률 {_d20_up:.0f}%     ║")
        lines.append("║                                                              ║")
        lines.append("║  📍 기 보유자 매도 전략:                                     ║")
        if _d5_avg > 0:
            lines.append("║    → D+3~5 단기 상승 시 1차 매도 (단기 반짝 상승 활용)     ║")
        else:
            lines.append("║    → 즉시 분할 매도 시작 (되돌림 전에 차익실현)             ║")
        lines.append("║                                                              ║")
        lines.append("╚══════════════════════════════════════════════════════════════╝")

    lines.append("```")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── 핵심 요약 ──
    lines.append("## 🎯 핵심 요약")
    lines.append("")

    for period_group in ["20년", "10년"]:
        results_in_group = [r for r in all_results if period_group in r["period_name"]]
        if not results_in_group:
            continue

        lines.append(f"### {period_group} 기준")
        lines.append("")
        lines.append("| 시장 | 외국인 순매수 후 | D+1 | D+5 | D+10 | D+20 | D+30 | 상승확률(D+20) |")
        lines.append("|:----:|:-------------:|:---:|:---:|:----:|:----:|:----:|:-------------:|")

        # D+20 기준 순위 산출 (순매수 후 추가 상승이 큰 시장)
        summary_rows = []
        for r in results_in_group:
            name = r["market_name"]
            kr = r["kospi_returns"]
            if kr.empty:
                continue

            for idx_name, ret_df in [("코스피", r["kospi_returns"]), ("코스닥", r["kosdaq_returns"])]:
                if ret_df.empty:
                    continue
                d1 = ret_df["D+1"].mean() if "D+1" in ret_df else np.nan
                d5 = ret_df["D+5"].mean() if "D+5" in ret_df else np.nan
                d10 = ret_df["D+10"].mean() if "D+10" in ret_df else np.nan
                d20 = ret_df["D+20"].mean() if "D+20" in ret_df else np.nan
                d30 = ret_df["D+30"].mean() if "D+30" in ret_df else np.nan

                up_prob = (ret_df["D+20"] > 0).mean() * 100 if "D+20" in ret_df else np.nan
                summary_rows.append((name, idx_name, d1, d5, d10, d20, d30, up_prob))

        # D+20 수익률 기준 Top 3에 별표 부여
        d20_vals = [(i, row[5]) for i, row in enumerate(summary_rows) if not np.isnan(row[5])]
        d20_vals.sort(key=lambda x: -x[1])
        star_map = {}
        for rank_i, (idx, _) in enumerate(d20_vals[:3]):
            star_map[idx] = ["🥇⭐⭐⭐", "🥈⭐⭐", "🥉⭐"][rank_i]

        for i, (name, idx_name, d1, d5, d10, d20, d30, up_prob) in enumerate(summary_rows):
            d1_s = f"{d1:+.2f}%" if not np.isnan(d1) else "N/A"
            d5_s = f"{d5:+.2f}%" if not np.isnan(d5) else "N/A"
            d10_s = f"{d10:+.2f}%" if not np.isnan(d10) else "N/A"
            d20_s = f"{d20:+.2f}%" if not np.isnan(d20) else "N/A"
            d30_s = f"{d30:+.2f}%" if not np.isnan(d30) else "N/A"
            up_s = f"{up_prob:.0f}%" if not np.isnan(up_prob) else "N/A"
            star = f" {star_map[i]}" if i in star_map else ""

            lines.append(f"| {name}→{idx_name}{star} | 평균 수익률 | {d1_s} | {d5_s} | {d10_s} | {d20_s} | {d30_s} | {up_s} |")

        lines.append("")

    lines.append("---")
    lines.append("")

    # ── 시장별 상세 분석 ──
    for r in all_results:
        lines.append(f"## 📌 {r['market_name']} 외국인 순매수 Top {TOP_N} ({r['period_name']})")
        lines.append("")

        ts = r["top_buying"]

        # 순매수 순위표
        lines.append("### 순매수 순위")
        lines.append("")
        lines.append("| 순위 | 날짜 | 외국인 순매수(억원) | 개인(억원) | 기관(억원) |")
        lines.append("|:----:|:----:|:------------------:|:--------:|:--------:|")

        for i, row in ts.iterrows():
            rank = i + 1
            date_str = row["날짜"].strftime("%Y-%m-%d")
            foreign = format_number(row["외국인"])
            individual = format_number(row.get("개인", np.nan))
            institution = format_number(row.get("기관계", np.nan))
            lines.append(f"| {rank} | {date_str} | {foreign} | {individual} | {institution} |")

        lines.append("")

        # 이후 지수 변화
        for idx_name, ret_df in [("코스피", r["kospi_returns"]), ("코스닥", r["kosdaq_returns"])]:
            if ret_df.empty:
                continue

            lines.append(f"### {idx_name} 지수 변화 (순매수 이후)")
            lines.append("")

            # D+20 기준 Top 3 이벤트에 별표 부여 (추세 지속 최우수)
            d20_star_map = {}
            if "D+20" in ret_df.columns:
                d20_ranked = ret_df["D+20"].dropna().sort_values(ascending=False)
                for rank_i, orig_idx in enumerate(d20_ranked.index[:3]):
                    d20_star_map[orig_idx] = ["🥇⭐⭐⭐", "🥈⭐⭐", "🥉⭐"][rank_i]

            lines.append(f"| 날짜 | D+1 | D+3 | D+5 | D+10 | D+15 | D+20 | D+30 | 평가 |")
            lines.append("|:----:|:---:|:---:|:---:|:----:|:----:|:----:|:----:|:----:|")

            for row_idx, row in ret_df.iterrows():
                date_str = row["event_date"].strftime("%Y-%m-%d")
                cols = ["D+1", "D+3", "D+5", "D+10", "D+15", "D+20", "D+30"]
                vals = []
                for c in cols:
                    v = row.get(c, np.nan)
                    if pd.notna(v):
                        vals.append(f"{v:+.2f}%")
                    else:
                        vals.append("N/A")
                star = d20_star_map.get(row_idx, "")
                lines.append(f"| {date_str} | {' | '.join(vals)} | {star} |")

            lines.append("")

            # 통계 요약
            lines.append(f"**{idx_name} 통계 요약:**")
            lines.append("")
            lines.append("| 구분 | D+1 | D+3 | D+5 | D+10 | D+15 | D+20 | D+30 |")
            lines.append("|:----:|:---:|:---:|:---:|:----:|:----:|:----:|:----:|")

            stats_cols = ["D+1", "D+3", "D+5", "D+10", "D+15", "D+20", "D+30"]

            for stat_name, stat_func in [("평균", "mean"), ("중간값", "median"),
                                          ("최대", "max"), ("최소", "min")]:
                vals = []
                for c in stats_cols:
                    if c in ret_df:
                        v = getattr(ret_df[c], stat_func)()
                        vals.append(f"{v:+.2f}%")
                    else:
                        vals.append("N/A")
                lines.append(f"| {stat_name} | {' | '.join(vals)} |")

            # 상승 확률
            vals = []
            for c in stats_cols:
                if c in ret_df:
                    up = (ret_df[c] > 0).sum()
                    total = ret_df[c].notna().sum()
                    if total > 0:
                        vals.append(f"{up}/{total} ({up/total*100:.0f}%)")
                    else:
                        vals.append("N/A")
                else:
                    vals.append("N/A")
            lines.append(f"| 상승확률 | {' | '.join(vals)} |")

            lines.append("")

            # D+1 ~ D+30 평균 수익률 추이 (ASCII)
            lines.append(f"**{idx_name} 평균 수익률 추이 (D+1 ~ D+30):**")
            lines.append("")
            lines.append("```")

            avg_returns = []
            for d in range(1, FOLLOW_DAYS + 1):
                col = f"D+{d}"
                if col in ret_df:
                    avg_returns.append(ret_df[col].mean())
                else:
                    avg_returns.append(np.nan)

            valid_returns = [r for r in avg_returns if not np.isnan(r)]
            if valid_returns:
                max_val = max(abs(min(valid_returns)), abs(max(valid_returns)))
                if max_val == 0:
                    max_val = 1
                chart_width = 40

                for d, ret in enumerate(avg_returns, 1):
                    if np.isnan(ret):
                        continue
                    bar_len = int(abs(ret) / max_val * chart_width)
                    if ret >= 0:
                        bar = " " * chart_width + "│" + "█" * bar_len
                        label = f"D+{d:2d} {ret:+6.2f}%"
                    else:
                        bar = " " * (chart_width - bar_len) + "█" * bar_len + "│"
                        label = f"D+{d:2d} {ret:+6.2f}%"
                    lines.append(f"{label} {bar}")

            lines.append("```")
            lines.append("")

        lines.append("---")
        lines.append("")

    # ── 결론 ──
    lines.append("## 💡 투자 시사점")
    lines.append("")

    for r in all_results:
        if "20년" in r["period_name"] and r["market_name"] == "KOSPI":
            kr = r["kospi_returns"]
            if not kr.empty and "D+20" in kr:
                avg_d1 = kr["D+1"].mean() if "D+1" in kr else 0
                avg_d5 = kr["D+5"].mean() if "D+5" in kr else 0
                avg_d20 = kr["D+20"].mean()
                up_prob = (kr["D+20"] > 0).mean() * 100

                if avg_d20 > 0:
                    lines.append("### 🟢 외국인 대량 순매수 → 추세 추종 유효")
                    lines.append("")
                    lines.append("| 구분 | 전략 | 설명 |")
                    lines.append("|:----:|:----:|:-----|")
                    lines.append(f"| 기보유자 | **보유 유지** | D+20 평균 {avg_d20:+.2f}%, 상승확률 {up_prob:.0f}% |")
                    if avg_d1 > 0 and avg_d5 > 0:
                        lines.append(f"| 미보유자 | **D+1~3 매수** | 모멘텀 지속, 눌림목에서 진입 |")
                    else:
                        lines.append(f"| 미보유자 | **D+3~5 매수** | 단기 조정 후 진입 유리 |")
                    lines.append(f"| 차익실현 | **D+20~30 매도** | 수익률 극대화 구간 |")
                else:
                    lines.append("### 🔴 외국인 대량 순매수 → 고점 경고 신호")
                    lines.append("")
                    lines.append("| 구분 | 전략 | 설명 |")
                    lines.append("|:----:|:----:|:-----|")
                    lines.append(f"| 기보유자 | **분할 매도** | D+20 평균 {avg_d20:+.2f}% → 되돌림 패턴 |")
                    lines.append(f"| 미보유자 | **관망** | 추격 매수 금지, 조정 후 진입 대기 |")
                    if avg_d5 > 0:
                        lines.append(f"| 단기 매매 | **D+3~5 매도** | 단기 반짝 상승만 활용 가능 |")

    lines.append("")
    lines.append("### ⚠ 주의사항")
    lines.append("")
    lines.append("1. **외국인 매수가 항상 추가 상승을 의미하지 않음** — 환율·글로벌 자금 흐름 영향")
    lines.append("2. **추격 매수보다 조정 시 진입** — 대량 매수일 당일은 이미 상승한 경우 많음")
    lines.append("3. 선물 매수 단독은 롤오버·헤지 가능성 고려")
    lines.append("4. 과거 통계이며 미래 수익을 보장하지 않음")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("**데이터 출처**: Naver Finance 투자자별 매매동향 → investor_data.db")
    lines.append("**분석 도구**: Python + pandas")

    return "\n".join(lines)


MARKETS = {
    "KOSPI": "01",
    "KOSDAQ": "02",
    "선물": "03",
}


def main():
    print("=" * 60)
    print("외국인 순매수 Top 20 분석기")
    print("=" * 60)

    # 1. 지수 데이터 로드
    print("\n[1/3] 코스피/코스닥 지수 데이터 로드...")
    kospi, kosdaq = load_index_data()
    print(f"  코스피: {len(kospi)}일 ({kospi['date'].min().strftime('%Y-%m-%d')} ~ {kospi['date'].max().strftime('%Y-%m-%d')})")
    print(f"  코스닥: {len(kosdaq)}일 ({kosdaq['date'].min().strftime('%Y-%m-%d')} ~ {kosdaq['date'].max().strftime('%Y-%m-%d')})")

    # 2. 투자자별 매매동향 로드 (DB에서)
    print("\n[2/3] 투자자별 매매동향 로드...")
    investor_data = {}
    for market_name, sosok in MARKETS.items():
        print(f"\n  === {market_name} (sosok={sosok}) ===")
        try:
            df = load_investor_data(sosok)
            if not df.empty:
                investor_data[market_name] = df
                print(f"  기간: {df['날짜'].min().strftime('%Y-%m-%d')} ~ {df['날짜'].max().strftime('%Y-%m-%d')}")
        except FileNotFoundError as e:
            print(f"  [SKIP] {e}")

    if not investor_data:
        print("\n❌ 투자자 데이터가 없습니다. 먼저 foreign_selling_analyzer.py를 실행하세요.")
        return

    # 3. 분석
    print("\n[3/3] 분석 실행...")
    all_results = []

    current_year = datetime.now().year

    for market_name, df in investor_data.items():
        # 20년 분석
        start_20 = current_year - 20
        result_20 = analyze_market(df, market_name, kospi, kosdaq, start_20, f"최근 20년 ({start_20}~)")
        if result_20:
            all_results.append(result_20)
            print(f"  {market_name} 20년 분석 완료")

        # 10년 분석
        start_10 = current_year - 10
        result_10 = analyze_market(df, market_name, kospi, kosdaq, start_10, f"최근 10년 ({start_10}~)")
        if result_10:
            all_results.append(result_10)
            print(f"  {market_name} 10년 분석 완료")

    # 4. 리포트 생성
    print("\n리포트 생성 중...")
    report = generate_report(all_results)

    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"외국인_순매수_Top20_분석_{timestamp}.md"
    filepath = os.path.join(RESULTS_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n✅ 리포트 저장 완료: {filepath}")
    print(f"   총 {len(all_results)}개 분석 결과")


if __name__ == "__main__":
    main()
