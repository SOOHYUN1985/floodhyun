"""
외국인 순매도 심층 분석기
- 매도 강도별 구간 분석 (하위 1%, 3%, 5%, 10%)
- D+0 당일 등락률 + D+1~D+30 일별 등락률
- 장기 수익률 (2개월, 3개월, 6개월, 1년, 2년)
- 최적 매수·매도 타이밍 결론 도출
- data/investor_data.db에서 투자자 매매동향 로드
"""

import warnings
warnings.filterwarnings('ignore')

import pandas as pd
import numpy as np
import sqlite3
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "market_data.db")
INVESTOR_DB_PATH = os.path.join(BASE_DIR, "data", "investor_data.db")
CACHE_DIR = os.path.join(BASE_DIR, "data", "cache")
from config import WEEKLY_RESEARCH_DIR as RESULTS_DIR

# 추적 거래일 수
SHORT_DAYS = 30
# 장기 추적 (거래일 기준: ~20일/월)
LONG_PERIODS = {
    "2개월": 40,
    "3개월": 60,
    "6개월": 120,
    "1년": 250,
    "2년": 500,
}

# 분석 구간 (외국인 순매수 하위 백분위)
THRESHOLDS = [1, 3, 5, 10]


def load_index_data():
    conn = sqlite3.connect(DB_PATH)
    kospi = pd.read_sql(
        "SELECT date, open, high, low, close, change FROM index_data WHERE index_name='KS11' ORDER BY date",
        conn, parse_dates=["date"]
    )
    kosdaq = pd.read_sql(
        "SELECT date, open, high, low, close, change FROM index_data WHERE index_name='KQ11' ORDER BY date",
        conn, parse_dates=["date"]
    )
    conn.close()
    return kospi, kosdaq


def load_investor_data(sosok):
    """투자자 매매동향 로드 — DB 우선, CSV fallback"""
    # ① investor_data.db에서 로드
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

    # ② CSV 캐시 fallback
    cache_file = os.path.join(CACHE_DIR, f"investor_{sosok}.csv")
    if os.path.exists(cache_file):
        df = pd.read_csv(cache_file, parse_dates=["날짜"])
        df["외국인"] = pd.to_numeric(df["외국인"], errors="coerce")
        print(f"  [CSV] {cache_file}에서 {len(df)}일 로드")
        return df

    raise FileNotFoundError(f"투자자 데이터 없음: DB({INVESTOR_DB_PATH}) 또는 캐시({cache_file}) 필요. "
                            f"먼저 foreign_selling_analyzer.py를 실행하세요.")


def get_returns_after_event(index_df, event_dates, max_days):
    """이벤트 이후 수익률 계산 (D+0 포함)"""
    index_df = index_df.sort_values("date").reset_index(drop=True)
    dates = index_df["date"].values
    closes = index_df["close"].values
    changes = index_df["change"].values if "change" in index_df else None

    results = []
    for event_date in event_dates:
        idx = np.searchsorted(dates, np.datetime64(event_date))
        if idx >= len(dates):
            continue

        base_close = closes[idx]
        row = {"event_date": event_date, "base_close": base_close}

        # D+0: 당일 등락률 (DB의 change 컬럼 사용, 소수→%로 변환)
        if changes is not None:
            row["D+0"] = changes[idx] * 100
        
        # D+0 당일 변동성 (시가→종가)
        if "open" in index_df.columns:
            day_open = index_df.iloc[idx]["open"]
            if day_open > 0:
                row["D+0_시가대비"] = (base_close / day_open - 1) * 100

        for d in range(1, max_days + 1):
            future_idx = idx + d
            if future_idx < len(dates):
                row[f"D+{d}"] = (closes[future_idx] / base_close - 1) * 100
            else:
                row[f"D+{d}"] = np.nan

        results.append(row)

    return pd.DataFrame(results)


def analyze_threshold(investor_df, index_df, threshold_pct, start_year, max_days):
    """특정 백분위 이하 순매도일의 이후 수익률 분석"""
    mask = investor_df["날짜"] >= datetime(start_year, 1, 1)
    df = investor_df[mask].copy()
    
    cutoff = df["외국인"].quantile(threshold_pct / 100)
    extreme_days = df[df["외국인"] <= cutoff].copy()
    
    event_dates = extreme_days["날짜"].tolist()
    returns = get_returns_after_event(index_df, event_dates, max_days)
    
    return {
        "threshold_pct": threshold_pct,
        "cutoff_value": cutoff,
        "n_events": len(extreme_days),
        "event_data": extreme_days,
        "returns": returns,
    }


def fmt(v, decimals=2):
    if pd.isna(v):
        return "N/A"
    return f"{v:+.{decimals}f}%"


def pct(series):
    """상승 확률"""
    valid = series.dropna()
    if len(valid) == 0:
        return "N/A"
    up = (valid > 0).sum()
    return f"{up}/{len(valid)} ({up/len(valid)*100:.0f}%)"


def generate_report(kospi_results, kosdaq_results, futures_results,
                    kospi, kosdaq, start_year, period_name):
    """하나의 기간에 대한 분석 결과 생성 (문자열 반환)"""
    lines = []
    
    lines.append(f"## 📊 {period_name} 분석")
    lines.append("")
    
    # ================================================================
    # 1. 총괄 요약: 매도 강도별 D+5/D+10/D+20/D+30/장기 평균 수익률
    # ================================================================
    lines.append("### 1️⃣ 외국인 매도 강도별 코스피 반등 패턴")
    lines.append("")
    lines.append("| 매도 강도 | 기준 (억원) | 발생횟수 | D+0 | D+5 | D+10 | D+20 | D+30 | 3개월 | 6개월 | 1년 | 평가 |")
    lines.append("|:--------:|:----------:|:------:|:---:|:---:|:----:|:----:|:----:|:----:|:----:|:---:|:----:|")
    
    # D+20 기준 최고 반등 구간에 별표 부여
    kospi_d20_vals = []
    for r in kospi_results:
        ret = r["returns"]
        if ret.empty or "D+20" not in ret:
            kospi_d20_vals.append(np.nan)
        else:
            kospi_d20_vals.append(ret["D+20"].mean())
    kospi_d20_ranked = sorted([(i, v) for i, v in enumerate(kospi_d20_vals) if not np.isnan(v)], key=lambda x: -x[1])
    kospi_star_map = {}
    for rank_i, (idx, _) in enumerate(kospi_d20_ranked[:3]):
        kospi_star_map[idx] = ["🥇⭐⭐⭐", "🥈⭐⭐", "🥉⭐"][rank_i]
    
    for ri, r in enumerate(kospi_results):
        ret = r["returns"]
        if ret.empty:
            continue
        cols_map = {
            "D+0": "D+0", "D+5": "D+5", "D+10": "D+10",
            "D+20": "D+20", "D+30": "D+30",
            "3개월": f"D+{LONG_PERIODS['3개월']}",
            "6개월": f"D+{LONG_PERIODS['6개월']}",
            "1년": f"D+{LONG_PERIODS['1년']}",
        }
        vals = {}
        for label, col in cols_map.items():
            if col in ret:
                vals[label] = fmt(ret[col].mean())
            else:
                vals[label] = "N/A"
        
        star = kospi_star_map.get(ri, "")
        lines.append(
            f"| 하위 {r['threshold_pct']}% | ≤ {r['cutoff_value']:,.0f} | "
            f"{r['n_events']}회 | {vals['D+0']} | {vals['D+5']} | {vals['D+10']} | "
            f"{vals['D+20']} | {vals['D+30']} | {vals['3개월']} | {vals['6개월']} | {vals['1년']} | {star} |"
        )
    
    lines.append("")
    
    # 코스닥 버전
    lines.append("| 매도 강도 | 기준 (억원) | 발생횟수 | D+0 | D+5 | D+10 | D+20 | D+30 | 3개월 | 6개월 | 1년 | 평가 |")
    lines.append("|:--------:|:----------:|:------:|:---:|:---:|:----:|:----:|:----:|:----:|:----:|:---:|:----:|")
    
    # 코스닥 D+20 기준 별표
    kosdaq_d20_vals = []
    for r in kosdaq_results:
        ret = r["returns"]
        if ret.empty or "D+20" not in ret:
            kosdaq_d20_vals.append(np.nan)
        else:
            kosdaq_d20_vals.append(ret["D+20"].mean())
    kosdaq_d20_ranked = sorted([(i, v) for i, v in enumerate(kosdaq_d20_vals) if not np.isnan(v)], key=lambda x: -x[1])
    kosdaq_star_map = {}
    for rank_i, (idx, _) in enumerate(kosdaq_d20_ranked[:3]):
        kosdaq_star_map[idx] = ["🥇⭐⭐⭐", "🥈⭐⭐", "🥉⭐"][rank_i]
    
    for ri, r in enumerate(kosdaq_results):
        ret = r["returns"]
        if ret.empty:
            continue
        cols_map = {
            "D+0": "D+0", "D+5": "D+5", "D+10": "D+10",
            "D+20": "D+20", "D+30": "D+30",
            "3개월": f"D+{LONG_PERIODS['3개월']}",
            "6개월": f"D+{LONG_PERIODS['6개월']}",
            "1년": f"D+{LONG_PERIODS['1년']}",
        }
        vals = {}
        for label, col in cols_map.items():
            if col in ret:
                vals[label] = fmt(ret[col].mean())
            else:
                vals[label] = "N/A"
        
        star = kosdaq_star_map.get(ri, "")
        lines.append(
            f"| 하위 {r['threshold_pct']}% (코스닥) | ≤ {r['cutoff_value']:,.0f} | "
            f"{r['n_events']}회 | {vals['D+0']} | {vals['D+5']} | {vals['D+10']} | "
            f"{vals['D+20']} | {vals['D+30']} | {vals['3개월']} | {vals['6개월']} | {vals['1년']} | {star} |"
        )
    
    lines.append("")
    
    # ================================================================
    # 2. 코스피 하위 5% 상세 분석 (가장 실용적 구간)
    # ================================================================
    # 하위 5% 결과 찾기
    main_result = None
    for r in kospi_results:
        if r["threshold_pct"] == 5:
            main_result = r
            break
    if main_result is None:
        main_result = kospi_results[0]
    
    ret = main_result["returns"]
    
    lines.append(f"### 2️⃣ 코스피 외국인 순매도 하위 {main_result['threshold_pct']}% "
                 f"(≤{main_result['cutoff_value']:,.0f}억원) 상세 분석")
    lines.append("")
    
    # D+0 당일 분석
    lines.append("#### 📍 당일 (D+0) 상황")
    lines.append("")
    if "D+0" in ret:
        d0 = ret["D+0"]
        lines.append(f"- 당일 등락률: 평균 **{d0.mean():+.2f}%**, 중간값 {d0.median():+.2f}%")
        lines.append(f"- 하락 확률: **{(d0 < 0).mean()*100:.0f}%** ({(d0 < 0).sum()}/{len(d0)})")
        lines.append(f"- 최대 하락: {d0.min():+.2f}%, 최대 상승: {d0.max():+.2f}%")
    if "D+0_시가대비" in ret:
        d0s = ret["D+0_시가대비"]
        lines.append(f"- 시가 대비 종가: 평균 {d0s.mean():+.2f}% (장중 추가 하락 여부)")
    lines.append("")
    
    # D+1 ~ D+30 일별 상세
    lines.append("#### 📍 D+1 ~ D+30 일별 누적수익률")
    lines.append("")
    lines.append("| 거래일 | 평균 | 중간값 | 최소 | 최대 | 상승확률 |")
    lines.append("|:------:|:----:|:-----:|:----:|:----:|:-------:|")
    
    for d in range(1, SHORT_DAYS + 1):
        col = f"D+{d}"
        if col in ret:
            s = ret[col].dropna()
            if len(s) > 0:
                lines.append(
                    f"| D+{d} | {fmt(s.mean())} | {fmt(s.median())} | "
                    f"{fmt(s.min())} | {fmt(s.max())} | {pct(s)} |"
                )
    
    lines.append("")
    
    # 장기 수익률
    lines.append("#### 📍 장기 수익률")
    lines.append("")
    lines.append("| 기간 | 거래일 | 평균 | 중간값 | 최소 | 최대 | 상승확률 |")
    lines.append("|:----:|:-----:|:----:|:-----:|:----:|:----:|:-------:|")
    
    for label, days in LONG_PERIODS.items():
        col = f"D+{days}"
        if col in ret:
            s = ret[col].dropna()
            if len(s) > 0:
                lines.append(
                    f"| {label} | D+{days} | {fmt(s.mean())} | {fmt(s.median())} | "
                    f"{fmt(s.min())} | {fmt(s.max())} | {pct(s)} |"
                )
    
    lines.append("")
    
    # 수익률 추이 차트 (D+1 ~ D+30)
    lines.append("#### 📍 코스피 평균 누적수익률 추이")
    lines.append("")
    lines.append("```")
    
    avg_rets = []
    for d in range(1, SHORT_DAYS + 1):
        col = f"D+{d}"
        if col in ret:
            avg_rets.append((d, ret[col].mean()))
    
    if avg_rets:
        all_vals = [v for _, v in avg_rets]
        max_abs = max(abs(min(all_vals)), abs(max(all_vals)))
        if max_abs == 0:
            max_abs = 1
        w = 40
        
        for d, v in avg_rets:
            bar_len = int(abs(v) / max_abs * w)
            if v >= 0:
                bar = " " * w + "│" + "█" * bar_len
            else:
                bar = " " * (w - bar_len) + "█" * bar_len + "│"
            lines.append(f"D+{d:2d} {v:+6.2f}% {bar}")
    
    lines.append("```")
    lines.append("")
    
    # 상승확률 추이 차트
    lines.append("#### 📍 상승확률 추이")
    lines.append("")
    lines.append("```")
    
    up_probs = []
    for d in list(range(1, SHORT_DAYS + 1)) + list(LONG_PERIODS.values()):
        col = f"D+{d}"
        if col in ret:
            s = ret[col].dropna()
            if len(s) > 0:
                prob = (s > 0).mean() * 100
                up_probs.append((d, prob, len(s)))
    
    for d, prob, n in up_probs:
        bar_len = int(prob / 100 * 50)
        marker = "◀ 50%" if abs(prob - 50) < 2 else ""
        if prob >= 70:
            marker = " ★"
        elif prob >= 60:
            marker = " ◎"
        
        if d <= 30:
            label = f"D+{d:3d}"
        else:
            # 장기
            for name, days in LONG_PERIODS.items():
                if days == d:
                    label = f"{name:>4s}"
                    break
            else:
                label = f"D+{d:3d}"
        
        lines.append(f"{label} ({n:3d}건) {'█' * bar_len}{'░' * (50 - bar_len)} {prob:.0f}%{marker}")
    
    lines.append("```")
    lines.append("")
    
    # ================================================================
    # 3. 코스닥 외국인 매도 → 코스닥 지수 반응 (하위 5%)
    # ================================================================
    kq_main = None
    for r in kosdaq_results:
        if r["threshold_pct"] == 5:
            kq_main = r
            break
    
    if kq_main:
        kq_ret = kq_main["returns"]
        lines.append(f"### 3️⃣ 코스닥 외국인 순매도 하위 {kq_main['threshold_pct']}% "
                     f"(≤{kq_main['cutoff_value']:,.0f}억원) → 코스닥 지수")
        lines.append("")
        
        if "D+0" in kq_ret:
            d0 = kq_ret["D+0"]
            lines.append(f"- 당일 등락률: 평균 **{d0.mean():+.2f}%**, 하락 확률 **{(d0 < 0).mean()*100:.0f}%**")
        
        lines.append("")
        lines.append("| 구간 | 평균 | 중간값 | 상승확률 |")
        lines.append("|:----:|:----:|:-----:|:-------:|")
        
        for label, col in [("D+1", "D+1"), ("D+3", "D+3"), ("D+5", "D+5"),
                           ("D+10", "D+10"), ("D+20", "D+20"), ("D+30", "D+30"),
                           ("2개월", f"D+{LONG_PERIODS['2개월']}"),
                           ("3개월", f"D+{LONG_PERIODS['3개월']}"),
                           ("6개월", f"D+{LONG_PERIODS['6개월']}"),
                           ("1년", f"D+{LONG_PERIODS['1년']}")]:
            if col in kq_ret:
                s = kq_ret[col].dropna()
                if len(s) > 0:
                    lines.append(f"| {label} | {fmt(s.mean())} | {fmt(s.median())} | {pct(s)} |")
        
        lines.append("")
    
    # ================================================================
    # 4. 선물 외국인 매도 → 코스피 지수 반응 (하위 5%)
    # ================================================================
    if futures_results:
        fut_main = None
        for r in futures_results:
            if r["threshold_pct"] == 5:
                fut_main = r
                break
        
        if fut_main:
            fut_ret = fut_main["returns"]
            lines.append(f"### 4️⃣ 선물 외국인 순매도 하위 {fut_main['threshold_pct']}% "
                         f"(≤{fut_main['cutoff_value']:,.0f}억원) → 코스피 지수")
            lines.append("")
            
            lines.append("| 구간 | 평균 | 중간값 | 상승확률 |")
            lines.append("|:----:|:----:|:-----:|:-------:|")
            
            for label, col in [("D+0", "D+0"), ("D+1", "D+1"), ("D+5", "D+5"),
                               ("D+10", "D+10"), ("D+20", "D+20"), ("D+30", "D+30"),
                               ("3개월", f"D+{LONG_PERIODS['3개월']}"),
                               ("6개월", f"D+{LONG_PERIODS['6개월']}"),
                               ("1년", f"D+{LONG_PERIODS['1년']}")]:
                if col in fut_ret:
                    s = fut_ret[col].dropna()
                    if len(s) > 0:
                        lines.append(f"| {label} | {fmt(s.mean())} | {fmt(s.median())} | {pct(s)} |")
            
            lines.append("")
    
    return "\n".join(lines)


def main():
    print("=" * 60)
    print("외국인 순매도 심층 분석기")
    print("=" * 60)
    
    # 데이터 로드
    print("\n[1/4] 지수 데이터 로드...")
    kospi, kosdaq = load_index_data()
    print(f"  코스피: {len(kospi)}일, 코스닥: {len(kosdaq)}일")
    
    print("\n[2/4] 투자자 데이터 로드...")
    inv_kospi = load_investor_data("01")
    inv_kosdaq = load_investor_data("02")
    inv_futures = load_investor_data("03")
    print(f"  코스피: {len(inv_kospi)}일, 코스닥: {len(inv_kosdaq)}일, 선물: {len(inv_futures)}일")
    
    max_days = max(SHORT_DAYS, max(LONG_PERIODS.values()))
    
    # 분석 실행
    all_lines = []
    
    all_lines.append("# 📊 외국인 순매도 심층 분석: 최적 매수·매도 전략")
    all_lines.append("")
    now_str = datetime.now().strftime("%Y년 %m월 %d일 %H:%M")
    all_lines.append(f"**분석일시**: {now_str}")
    all_lines.append("**데이터 출처**: Naver Finance (투자자별 매매동향) + Yahoo Finance (지수)")
    all_lines.append(f"**분석 구간**: 외국인 순매도 하위 {', '.join(str(t)+'%' for t in THRESHOLDS)}")
    all_lines.append(f"**추적 기간**: D+0 ~ D+{SHORT_DAYS}, 2개월~2년")
    all_lines.append("")
    all_lines.append("---")
    all_lines.append("")
    
    for start_year, period_name in [(2006, "최근 20년 (2006~)"), (2010, "2010년 이후 (금융시장 안정화)"), (2016, "최근 10년 (2016~)")]:
        print(f"\n[3/4] {period_name} 분석 중...")
        
        # 코스피 외국인 매도 → 코스피 지수
        kospi_results = []
        for t in THRESHOLDS:
            r = analyze_threshold(inv_kospi, kospi, t, start_year, max_days)
            kospi_results.append(r)
            print(f"  코스피 하위 {t}%: {r['n_events']}건, 기준={r['cutoff_value']:,.0f}억")
        
        # 코스닥 외국인 매도 → 코스닥 지수
        kosdaq_results = []
        for t in THRESHOLDS:
            r = analyze_threshold(inv_kosdaq, kosdaq, t, start_year, max_days)
            kosdaq_results.append(r)
            print(f"  코스닥 하위 {t}%: {r['n_events']}건, 기준={r['cutoff_value']:,.0f}억")
        
        # 선물 외국인 매도 → 코스피 지수
        futures_results = []
        for t in THRESHOLDS:
            r = analyze_threshold(inv_futures, kospi, t, start_year, max_days)
            futures_results.append(r)
            print(f"  선물 하위 {t}%: {r['n_events']}건, 기준={r['cutoff_value']:,.0f}억")
        
        section = generate_report(kospi_results, kosdaq_results, futures_results,
                                  kospi, kosdaq, start_year, period_name)
        all_lines.append(section)
        all_lines.append("---")
        all_lines.append("")
    
    # ================================================================
    # 최종 결론
    # ================================================================
    print("\n[4/4] 결론 생성 중...")
    
    # 결론 도출을 위한 데이터 수집 (각 기간별 하위 5%)
    main_r = analyze_threshold(inv_kospi, kospi, 5, 2006, max_days)
    main_r_2010 = analyze_threshold(inv_kospi, kospi, 5, 2010, max_days)
    main_r_10y = analyze_threshold(inv_kospi, kospi, 5, 2016, max_days)
    ret = main_r_2010["returns"]  # 2010년 기준을 메인으로 사용
    
    # 최적 매도 타이밍 찾기: 평균수익률 × 상승확률이 최대인 지점
    best_scores = []
    for d in list(range(1, SHORT_DAYS + 1)) + list(LONG_PERIODS.values()):
        col = f"D+{d}"
        if col in ret:
            s = ret[col].dropna()
            if len(s) >= 5:
                avg_ret = s.mean()
                up_prob = (s > 0).mean()
                score = avg_ret * up_prob
                best_scores.append((d, avg_ret, up_prob * 100, score, len(s)))
    
    best_scores.sort(key=lambda x: -x[3])
    
    # 단기 최적 (D+1~30)
    short_best = [x for x in best_scores if x[0] <= 30]
    # 장기 최적
    long_best = [x for x in best_scores if x[0] > 30]
    
    all_lines.append("## 🎯 최종 결론: 최적 매수·매도 전략")
    all_lines.append("")
    
    # 당일 분석
    if "D+0" in ret:
        d0 = ret["D+0"]
        all_lines.append("### 📍 외국인 대량 매도일 당일 (D+0)")
        all_lines.append("")
        all_lines.append(f"- 외국인이 코스피에서 **{main_r_2010['cutoff_value']:,.0f}억원 이상** 순매도한 날 (2010년~ 하위 5%)")
        all_lines.append(f"- 당일 코스피 등락: 평균 **{d0.mean():+.2f}%**, 중간값 {d0.median():+.2f}%")
        all_lines.append(f"- 당일 하락 확률: **{(d0 < 0).mean()*100:.0f}%** → 대부분 하락 마감")
        if (d0 < -2).sum() > 0:
            all_lines.append(f"- 2% 이상 급락 확률: {(d0 < -2).mean()*100:.0f}%")
        all_lines.append("")
    
    # 매수 타이밍
    all_lines.append("### 📍 언제 매수하면 좋은가?")
    all_lines.append("")
    all_lines.append("```")
    all_lines.append("┌───────────────────────────────────────────────────────┐")
    all_lines.append("│              외국인 대량 매도 발생!                    │")
    all_lines.append("│                                                       │")
    
    # D+1~3 분석
    d1_avg = ret["D+1"].mean() if "D+1" in ret else 0
    d3_avg = ret["D+3"].mean() if "D+3" in ret else 0
    
    if d1_avg < 0 and d3_avg < 0:
        all_lines.append("│  D+0~3: 추가 하락 가능성 높음 → ❌ 즉시 매수 금지    │")
        all_lines.append("│  D+3~5: 바닥 확인 후 → ✅ 1차 분할 매수              │")
    elif d1_avg < 0:
        all_lines.append("│  D+0~1: 추가 하락 가능 → ❌ 즉시 매수 위험           │")
        all_lines.append("│  D+2~3: 반등 시작 → ✅ 1차 분할 매수                 │")
    else:
        all_lines.append("│  D+1: 이미 반등 시작 → ✅ 빠른 매수 유리             │")
    
    # 추가 매수 시점
    # D+5~10에서 평균이 여전히 낮으면 추가 매수 유리
    d5_avg = ret["D+5"].mean() if "D+5" in ret else 0
    d10_avg = ret["D+10"].mean() if "D+10" in ret else 0
    
    if d5_avg < d10_avg:
        all_lines.append("│  D+5~7: 가격 여전히 낮음 → ✅ 2차 추가 매수          │")
    
    all_lines.append("│                                                       │")
    all_lines.append("└───────────────────────────────────────────────────────┘")
    all_lines.append("```")
    all_lines.append("")
    
    # 매도 타이밍
    all_lines.append("### 📍 언제 매도하면 좋은가?")
    all_lines.append("")
    
    all_lines.append("**단기 매매 (스윙 트레이딩):**")
    all_lines.append("")
    if short_best:
        all_lines.append("| 순위 | 매도 시점 | 평균 수익률 | 상승확률 | 효율점수 | 평가 |")
        all_lines.append("|:----:|:--------:|:----------:|:-------:|:-------:|:----:|")
        for i, (d, avg, prob, score, n) in enumerate(short_best[:5]):
            star = ["🥇⭐⭐⭐", "🥈⭐⭐", "🥉⭐"][i] if i < 3 else ""
            all_lines.append(f"| {i+1} | D+{d} | {avg:+.2f}% | {prob:.0f}% | {score:.2f} | {star} |")
        all_lines.append("")
    
    all_lines.append("**장기 투자:**")
    all_lines.append("")
    if long_best:
        all_lines.append("| 순위 | 매도 시점 | 평균 수익률 | 상승확률 | 효율점수 | 평가 |")
        all_lines.append("|:----:|:--------:|:----------:|:-------:|:-------:|:----:|")
        for li, (d, avg, prob, score, n) in enumerate(long_best[:5]):
            for name, days in LONG_PERIODS.items():
                if days == d:
                    label = name
                    break
            else:
                label = f"D+{d}"
            star = ["🥇⭐⭐⭐", "🥈⭐⭐", "🥉⭐"][li] if li < 3 else ""
            all_lines.append(f"| - | {label} (D+{d}) | {avg:+.2f}% | {prob:.0f}% | {score:.2f} | {star} |")
        all_lines.append("")
    
    # 코스닥 결론
    kq_r = analyze_threshold(inv_kosdaq, kosdaq, 5, 2006, max_days)
    kq_ret = kq_r["returns"]
    
    all_lines.append("### 📍 코스닥 외국인 대량 매도 시 전략")
    all_lines.append("")
    
    kq_scores = []
    for d in list(range(1, SHORT_DAYS + 1)) + list(LONG_PERIODS.values()):
        col = f"D+{d}"
        if col in kq_ret:
            s = kq_ret[col].dropna()
            if len(s) >= 5:
                avg_ret = s.mean()
                up_prob = (s > 0).mean()
                kq_scores.append((d, avg_ret, up_prob * 100, avg_ret * up_prob, len(s)))
    
    kq_scores.sort(key=lambda x: -x[3])
    kq_short = [x for x in kq_scores if x[0] <= 30]
    
    if kq_short:
        all_lines.append("| 순위 | 매도 시점 | 평균 수익률 | 상승확률 |")
        all_lines.append("|:----:|:--------:|:----------:|:-------:|")
        for i, (d, avg, prob, score, n) in enumerate(kq_short[:3]):
            all_lines.append(f"| {i+1} | D+{d} | {avg:+.2f}% | {prob:.0f}% |")
        all_lines.append("")
    
    # 종합 전략 박스
    # 3개 기간 비교 테이블
    all_lines.append("### 📍 기간별 비교 (20년 vs 2010년~ vs 10년)")
    all_lines.append("")
    all_lines.append("코스피 외국인 순매도 하위 5% 기준:")
    all_lines.append("")
    all_lines.append("| 항목 | 20년 (2006~) | 2010년~ (안정화 후) | 10년 (2016~) |")
    all_lines.append("|:----:|:-----------:|:------------------:|:-----------:|")
    
    # Gather values for each period
    for label, r_obj in [("20년", main_r), ("2010", main_r_2010), ("10년", main_r_10y)]:
        pass  # we'll build rows below
    
    row_items = [
        ("하위 5% 기준", lambda r: f"≤ {r['cutoff_value']:,.0f}억"),
        ("발생 횟수", lambda r: f"{r['n_events']}회"),
    ]
    
    ret_items = [
        ("D+0 (당일)", "D+0"),
        ("D+5", "D+5"),
        ("D+10", "D+10"),
        ("D+20", "D+20"),
        ("D+30", "D+30"),
        ("3개월", f"D+{LONG_PERIODS['3개월']}"),
        ("6개월", f"D+{LONG_PERIODS['6개월']}"),
        ("1년", f"D+{LONG_PERIODS['1년']}"),
    ]
    
    for row_name, fn in row_items:
        v20 = fn(main_r)
        v2010 = fn(main_r_2010)
        v10 = fn(main_r_10y)
        all_lines.append(f"| {row_name} | {v20} | {v2010} | {v10} |")
    
    for row_name, col in ret_items:
        vals = []
        for r_obj in [main_r, main_r_2010, main_r_10y]:
            r_ret = r_obj["returns"]
            if col in r_ret:
                s = r_ret[col].dropna()
                if len(s) > 0:
                    avg = s.mean()
                    prob = (s > 0).mean() * 100
                    vals.append(f"{avg:+.2f}% ({prob:.0f}%)")
                else:
                    vals.append("N/A")
            else:
                vals.append("N/A")
        all_lines.append(f"| {row_name} | {vals[0]} | {vals[1]} | {vals[2]} |")
    
    all_lines.append("")
    
    # 코스닥 비교
    kq_2010 = analyze_threshold(inv_kosdaq, kosdaq, 5, 2010, max_days)
    kq_10y = analyze_threshold(inv_kosdaq, kosdaq, 5, 2016, max_days)
    
    all_lines.append("코스닥 외국인 순매도 하위 5% 기준:")
    all_lines.append("")
    all_lines.append("| 항목 | 20년 (2006~) | 2010년~ (안정화 후) | 10년 (2016~) |")
    all_lines.append("|:----:|:-----------:|:------------------:|:-----------:|")
    
    for row_name, fn in row_items:
        v20 = fn(kq_r)
        v2010 = fn(kq_2010)
        v10 = fn(kq_10y)
        all_lines.append(f"| {row_name} | {v20} | {v2010} | {v10} |")
    
    for row_name, col in ret_items:
        vals = []
        for r_obj in [kq_r, kq_2010, kq_10y]:
            r_ret = r_obj["returns"]
            if col in r_ret:
                s = r_ret[col].dropna()
                if len(s) > 0:
                    avg = s.mean()
                    prob = (s > 0).mean() * 100
                    vals.append(f"{avg:+.2f}% ({prob:.0f}%)")
                else:
                    vals.append("N/A")
            else:
                vals.append("N/A")
        all_lines.append(f"| {row_name} | {vals[0]} | {vals[1]} | {vals[2]} |")
    
    all_lines.append("")
    
    all_lines.append("### 📍 종합 실전 전략")
    all_lines.append("")
    all_lines.append("```")
    all_lines.append("╔══════════════════════════════════════════════════════════════╗")
    all_lines.append("║              외국인 대량 순매도 발생 시 실전 전략             ║")
    all_lines.append("╠══════════════════════════════════════════════════════════════╣")
    all_lines.append("║                                                              ║")
    all_lines.append("║  📌 매수 조건                                                ║")
    all_lines.append(f"║    • 코스피: 외국인 순매도 {abs(main_r_2010['cutoff_value']):,.0f}억원 이상 (2010~ 하위5%)   ║")
    all_lines.append(f"║    • 코스닥: 외국인 순매도 {abs(kq_2010['cutoff_value']):,.0f}억원 이상 (2010~ 하위5%)    ║")
    all_lines.append("║                                                              ║")
    all_lines.append("║  📌 매수 타이밍                                              ║")
    
    if d1_avg < 0:
        all_lines.append("║    • 1차 매수: D+3 ~ D+5 (추가 하락 후 바닥 확인)         ║")
        all_lines.append("║    • 2차 매수: D+7 ~ D+10 (반등 확인 후 추가)             ║")
    else:
        all_lines.append("║    • 1차 매수: D+1 ~ D+2 (빠른 반등 패턴)                ║")
        all_lines.append("║    • 2차 매수: D+5 (눌림 시 추가)                          ║")
    
    all_lines.append("║                                                              ║")
    all_lines.append("║  📌 매도 타이밍                                              ║")
    
    if short_best:
        best_d = short_best[0][0]
        best_ret = short_best[0][1]
        best_prob = short_best[0][2]
        all_lines.append(f"║    • 단기: D+{best_d} 목표 (평균 {best_ret:+.1f}%, 확률 {best_prob:.0f}%)       ║")
    
    if long_best:
        best_long = long_best[0]
        for name, days in LONG_PERIODS.items():
            if days == best_long[0]:
                long_label = name
                break
        else:
            long_label = f"D+{best_long[0]}"
        all_lines.append(f"║    • 장기: {long_label} 보유 (평균 {best_long[1]:+.1f}%, 확률 {best_long[2]:.0f}%)       ║")
    
    all_lines.append("║                                                              ║")
    all_lines.append("║  ⚠ 주의사항                                                 ║")
    all_lines.append("║    • 당일(D+0) 매수는 추가 하락 위험                         ║")
    all_lines.append("║    • 분할 매수로 리스크 분산 필수                              ║")
    all_lines.append("║    • 선물 매도 단독은 신호 강도 약함                           ║")
    all_lines.append("║    • 과거 통계이며 미래 수익을 보장하지 않음                    ║")
    all_lines.append("║                                                              ║")
    all_lines.append("╚══════════════════════════════════════════════════════════════╝")
    all_lines.append("```")
    all_lines.append("")
    all_lines.append("---")
    all_lines.append("")
    all_lines.append("**데이터 출처**: Naver Finance 투자자별 매매동향 + Yahoo Finance 지수 데이터")
    all_lines.append("**분석 도구**: Python + pandas")
    
    report = "\n".join(all_lines)
    
    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(RESULTS_DIR, f"외국인_순매도_심층분석_{timestamp}.md")
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"\n✅ 리포트 저장: {filepath}")


if __name__ == "__main__":
    main()
