"""
외국인 매매동향 기반 현재 구간 진단 & 대응 전략 리포트
- 오늘 기준 최근 외국인 순매수/순매도 이벤트 파악
- 각 이벤트의 D+N 구간 확인 (N = 오늘까지 경과 거래일)
- 통계적 기대 수익률로 현 시점 위치 진단
- 최적 대응 전략 (매수/보유/관망/매도) 도출
"""

import warnings
warnings.filterwarnings('ignore')

import pandas as pd
import numpy as np
import sqlite3
import os
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "market_data.db")
INVESTOR_DB_PATH = os.path.join(BASE_DIR, "data", "investor_data.db")
from config import WEEKLY_RESEARCH_DIR as RESULTS_DIR

TODAY = datetime.now().date()
TODAY_STR = TODAY.strftime("%Y년 %m월 %d일")

# ──────────────────────────────────────────────────────
# 1. 데이터 로드
# ──────────────────────────────────────────────────────

def load_investor_data(market_code):
    """투자자 매매동향 로드 (KOSPI='01', KOSDAQ='02', 선물='03')"""
    if os.path.exists(INVESTOR_DB_PATH):
        try:
            conn = sqlite3.connect(INVESTOR_DB_PATH)
            df = pd.read_sql_query(
                "SELECT date as '날짜', individual as '개인', foreign_ as '외국인', "
                "institution as '기관계' "
                "FROM investor_daily WHERE market = ? ORDER BY date",
                conn, params=(market_code,), parse_dates=["날짜"],
            )
            conn.close()
            if len(df) > 50:
                df["외국인"] = pd.to_numeric(df["외국인"], errors="coerce")
                df["개인"] = pd.to_numeric(df["개인"], errors="coerce")
                df["기관계"] = pd.to_numeric(df["기관계"], errors="coerce")
                return df
        except Exception:
            pass
    raise FileNotFoundError(f"investor_data.db에서 market={market_code} 데이터 없음.")


def load_index_data():
    """DB에서 코스피/코스닥 지수 로드"""
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


# ──────────────────────────────────────────────────────
# 2. 거래일 계산
# ──────────────────────────────────────────────────────

def count_trading_days(index_df, event_date, target_date):
    """event_date 이후 target_date 까지의 거래일 수 계산"""
    dates = pd.to_datetime(index_df["date"]).dt.date.values
    event = pd.Timestamp(event_date).date()
    target = pd.Timestamp(target_date).date()
    after_event = [d for d in dates if d > event]
    before_target = [d for d in after_event if d <= target]
    return len(before_target)


def get_index_at_date(index_df, ref_date):
    """특정 날짜의 지수값 반환"""
    df = index_df.copy()
    df["date_only"] = pd.to_datetime(df["date"]).dt.date
    row = df[df["date_only"] == pd.Timestamp(ref_date).date()]
    if len(row) == 0:
        # 가장 가까운 이전 날짜
        earlier = df[df["date_only"] <= pd.Timestamp(ref_date).date()]
        if len(earlier) == 0:
            return None
        return earlier.iloc[-1]["close"]
    return row.iloc[-1]["close"]


def get_index_after_n_days(index_df, event_date, n):
    """event_date 이후 n번째 거래일의 지수값 반환"""
    df = index_df.copy()
    df["date_only"] = pd.to_datetime(df["date"]).dt.date
    event = pd.Timestamp(event_date).date()
    after_dates = df[df["date_only"] > event].reset_index(drop=True)
    if len(after_dates) <= n - 1:
        return None
    return after_dates.iloc[n - 1]["close"]


# ──────────────────────────────────────────────────────
# 3. 이벤트 감지 (최근 N일 내 유의미한 외국인 이벤트)
# ──────────────────────────────────────────────────────

def detect_significant_events(investor_df, look_back_days=60):
    """
    최근 look_back_days 거래일 내 유의미한 외국인 매매 이벤트 감지
    - 순매도 하위 5% 이하
    - 순매수 상위 5% 이상
    """
    df = investor_df.dropna(subset=["외국인"]).copy()
    df = df.sort_values("날짜")
    
    # 하위 5% / 상위 5% 기준 (전체 데이터 기준)
    sell_threshold = df["외국인"].quantile(0.05)   # 순매도 하위 5%
    buy_threshold  = df["외국인"].quantile(0.95)   # 순매수 상위 5%
    sell_1pct = df["외국인"].quantile(0.01)
    sell_3pct = df["외국인"].quantile(0.03)
    buy_1pct  = df["외국인"].quantile(0.99)
    buy_3pct  = df["외국인"].quantile(0.97)
    
    # 최근 look_back_days 거래일
    recent = df.tail(look_back_days)
    
    events = []
    for _, row in recent.iterrows():
        val = row["외국인"]
        date = row["날짜"]
        if val <= sell_threshold:
            if val <= sell_1pct:
                pct_rank = "하위 1%"
                strength = "극강 매도"
                signal = "SELL_EXTREME"
            elif val <= sell_3pct:
                pct_rank = "하위 3%"
                strength = "강한 매도"
                signal = "SELL_STRONG"
            else:
                pct_rank = "하위 5%"
                strength = "대량 매도"
                signal = "SELL_LARGE"
            events.append({
                "날짜": date, "외국인": val, "개인": row["개인"], "기관계": row["기관계"],
                "구분": "순매도", "강도": strength, "백분위": pct_rank, "신호": signal
            })
        elif val >= buy_threshold:
            if val >= buy_1pct:
                pct_rank = "상위 1%"
                strength = "극강 매수"
                signal = "BUY_EXTREME"
            elif val >= buy_3pct:
                pct_rank = "상위 3%"
                strength = "강한 매수"
                signal = "BUY_STRONG"
            else:
                pct_rank = "상위 5%"
                strength = "대량 매수"
                signal = "BUY_LARGE"
            events.append({
                "날짜": date, "외국인": val, "개인": row["개인"], "기관계": row["기관계"],
                "구분": "순매수", "강도": strength, "백분위": pct_rank, "신호": signal
            })
    
    return events, sell_threshold, buy_threshold, sell_1pct, buy_threshold, buy_1pct


# ──────────────────────────────────────────────────────
# 4. 통계 기대값 참조 테이블
# ──────────────────────────────────────────────────────

# 외국인 순매도 하위 5% 이하 발생 후 코스피 기대수익률 (심층분석 기준, 20년)
SELL_KOSPI_STATS = {
    1: (-0.17, 55), 2: (0.05, 54), 3: (0.11, 57), 4: (0.06, 57),
    5: (0.17, 53), 6: (0.10, 55), 7: (0.11, 55), 8: (0.37, 53),
    9: (0.58, 56), 10: (0.90, 55), 11: (1.20, 59), 12: (1.47, 60),
    13: (1.56, 61), 14: (1.69, 59), 15: (1.74, 59), 16: (1.93, 59),
    17: (2.22, 61), 18: (2.29, 60), 19: (2.44, 59), 20: (2.63, 60),
    21: (2.94, 60), 22: (3.16, 60), 23: (3.33, 61), 24: (3.67, 62),
    25: (3.87, 62), 26: (4.11, 65), 27: (4.25, 63), 28: (4.71, 64),
    29: (4.99, 64), 30: (5.24, 64),
}

# 외국인 순매수 상위 5% 이상 발생 후 코스피 기대수익률 (심층분석 기준, 20년)
BUY_KOSPI_STATS = {
    1: (0.19, 56), 2: (0.28, 58), 3: (0.44, 61), 4: (0.71, 64),
    5: (0.91, 63), 6: (0.98, 61), 7: (1.12, 60), 8: (1.22, 60),
    9: (1.30, 57), 10: (1.19, 56), 11: (1.34, 58), 12: (1.45, 55),
    13: (1.55, 56), 14: (1.59, 56), 15: (1.69, 57), 16: (1.90, 58),
    17: (2.01, 58), 18: (2.23, 59), 19: (2.41, 61), 20: (2.44, 58),
    21: (2.48, 60), 22: (2.65, 58), 23: (2.91, 59), 24: (2.95, 60),
    25: (3.20, 59), 26: (3.39, 60), 27: (3.42, 62), 28: (3.46, 61),
    29: (3.57, 60), 30: (3.65, 60),
}

# 하위 1% (극강 매도) 기준
SELL_1PCT_STATS = {
    5: (-0.49, 50), 10: (2.51, 58), 20: (5.99, 60), 30: (12.01, 68),
}
# 상위 1% (극강 매수) 기준
BUY_1PCT_STATS = {
    5: (1.45, 60), 10: (1.81, 58), 20: (5.22, 62), 30: (8.86, 65),
}


def get_expected_return(n_days, event_type, strength):
    """n_days 경과 시점의 기대수익률 반환"""
    if event_type == "순매도":
        stats = SELL_KOSPI_STATS
    else:
        stats = BUY_KOSPI_STATS
    if n_days <= 0:
        return 0.0, 50
    if n_days in stats:
        return stats[n_days]
    # 선형 보간
    keys = sorted(stats.keys())
    if n_days > max(keys):
        return stats[max(keys)]
    for i, k in enumerate(keys[:-1]):
        if k <= n_days <= keys[i+1]:
            r1, p1 = stats[k]
            r2, p2 = stats[keys[i+1]]
            t = (n_days - k) / (keys[i+1] - k)
            return r1 + t * (r2 - r1), int(p1 + t * (p2 - p1))
    return 0.0, 50


# ──────────────────────────────────────────────────────
# 5. 현재 구간 진단
# ──────────────────────────────────────────────────────

def diagnose_market_phase(events, kospi_df, look_back_days=60):
    """
    최근 이벤트들을 기반으로 현재 시장 국면 진단
    반환: 국면 문자열, 이벤트별 D+N 정보
    """
    if not events:
        return "이벤트 없음", []
    
    today = pd.Timestamp(TODAY)
    event_diagnostics = []
    
    recent_sell_count = 0
    recent_buy_count = 0
    last_event = None
    last_event_type = None
    
    for ev in sorted(events, key=lambda x: x["날짜"], reverse=True):
        ev_date = pd.Timestamp(ev["날짜"])
        n_days = count_trading_days(kospi_df, ev_date, today)
        base_close = get_index_at_date(kospi_df, ev_date)
        current_close = get_index_at_date(kospi_df, today)
        
        if base_close and current_close and base_close > 0:
            actual_return = (current_close / base_close - 1) * 100
        else:
            actual_return = None
        
        exp_ret, exp_prob = get_expected_return(n_days, ev["구분"], ev["강도"])
        
        if last_event is None:
            last_event = ev
            last_event_type = ev["구분"]
        
        if ev["구분"] == "순매도":
            recent_sell_count += 1
        else:
            recent_buy_count += 1
        
        # 남은 기대 수익 (n_days 이후 D+30까지)
        remaining_days = min(30 - n_days, 30)
        if remaining_days > 0 and n_days < 30:
            future_ret, _ = get_expected_return(30, ev["구분"], ev["강도"])
            remain_exp = future_ret - exp_ret
        else:
            remain_exp = 0.0
        
        event_diagnostics.append({
            "날짜": ev_date.strftime("%Y-%m-%d"),
            "외국인": ev["외국인"],
            "구분": ev["구분"],
            "강도": ev["강도"],
            "백분위": ev["백분위"],
            "경과_거래일": n_days,
            "현재실제수익": actual_return,
            "통계기대수익_D+N": exp_ret,
            "통계상승확률": exp_prob,
            "D+30까지_잔여기대": remain_exp,
        })
    
    # 국면 판단
    if last_event_type == "순매수":
        if last_event["강도"] in ["극강 매수", "강한 매수"]:
            phase = "🟢 강한 매수 전환 국면 (추세 추종 유효)"
        else:
            phase = "🟡 매수 전환 국면 (상승 모멘텀 진행 중)"
    elif last_event_type == "순매도":
        last_n = event_diagnostics[0]["경과_거래일"]
        if last_n <= 5:
            phase = "🔴 대량 매도 초기 국면 (추가 하락 주의)"
        elif last_n <= 10:
            phase = "🟠 대량 매도 후 바닥 확인 구간 (D+5~10, 분할 매수 검토)"
        elif last_n <= 20:
            phase = "🟡 매도 후 반등 구간 (D+10~20, 통계적 반등 기대)"
        else:
            phase = "🟢 매도 후 회복 국면 (D+20 이후, 상승 추세)"
    else:
        phase = "⚪ 중립 구간"
    
    # 최근 60일 순매도/매수 균형
    if recent_sell_count > recent_buy_count * 2:
        phase += f"\n> ⚠️ 최근 {look_back_days}거래일 매도 이벤트({recent_sell_count}회) >> 매수 이벤트({recent_buy_count}회) — 구조적 매도 압력 지속"
    elif recent_buy_count > recent_sell_count * 2:
        phase += f"\n> ✅ 최근 {look_back_days}거래일 매수 이벤트({recent_buy_count}회) >> 매도 이벤트({recent_sell_count}회) — 강한 매수 전환"
    
    return phase, event_diagnostics


# ──────────────────────────────────────────────────────
# 6. 종합 전략 도출
# ──────────────────────────────────────────────────────

def derive_strategy(events, event_diagnostics, kospi_df):
    """현재 이벤트 분포를 기반으로 종합 전략 도출"""
    if not event_diagnostics:
        return "데이터 부족 — 전략 도출 불가", {}, {}
    
    # 가장 최근 이벤트
    most_recent = sorted(event_diagnostics, key=lambda x: x["날짜"], reverse=True)[0]
    n = most_recent["경과_거래일"]
    ev_type = most_recent["구분"]
    ev_str = most_recent["강도"]
    
    # 순매도 클러스터 분석 (최근 20거래일 내 매도 이벤트 연속성)
    today = pd.Timestamp(TODAY)
    recent_20_sells = [e for e in event_diagnostics if e["구분"] == "순매도" and e["경과_거래일"] <= 20]
    recent_20_buys  = [e for e in event_diagnostics if e["구분"] == "순매수" and e["경과_거래일"] <= 20]
    
    # 누적 순매도 최근 20거래일
    investor_vals_recent = [e["외국인"] for e in event_diagnostics if e["경과_거래일"] <= 20]
    net_flow_20 = sum(investor_vals_recent)
    
    # 매수 시점 권고 (분할 매수 구간 계산)
    if ev_type == "순매도":
        if n <= 3:
            buy_timing = "🔴 아직 매수 금지 — D+3 이전, 추가 하락 진행 중"
            action = "관망 (현금 보유)"
            risk = "고위험"
        elif n <= 7:
            buy_timing = "🟡 1차 분할 매수 시작 가능 — D+3~7, 바닥 탐색 구간"
            action = "1차 매수 (25~30%)"
            risk = "중고위험"
        elif n <= 15:
            buy_timing = "🟢 2차 추가 매수 — D+8~15, 통계적 반등 구간"
            action = "2차 매수 (추가 25~30%)"
            risk = "중위험"
        elif n <= 25:
            buy_timing = "🟢 3차 매수 완성 또는 보유 유지 — D+15~25 반등 가속"
            action = "3차 매수 완성 또는 보유"
            risk = "중위험"
        else:
            buy_timing = "📤 차익실현 검토 — D+25 이후 분할 매도 시작"
            action = "분할 매도 (차익실현)"
            risk = "낮음"
    else:  # 순매수
        if n <= 3:
            buy_timing = "🟢 추세 추종 진입 가능 — 눌림목 이용 매수"
            action = "추세 추종 매수 또는 보유 유지"
            risk = "중위험"
        elif n <= 10:
            buy_timing = "🟢 상승 모멘텀 유지 — 보유 또는 추가 매수"
            action = "보유 유지 (또는 소량 추가)"
            risk = "중위험"
        elif n <= 20:
            buy_timing = "🟡 상승 지속 — 분할 매도 준비"
            action = "부분 익절 시작 검토 (30~50%)"
            risk = "낮음~중위험"
        else:
            buy_timing = "📤 차익실현 구간 — D+20 이후 분할 매도"
            action = "분할 매도 완료 (차익실현)"
            risk = "낮음"
    
    # 코스닥 전략 (코스피 순매도 후 코스닥은 더 부진)
    if ev_type == "순매도":
        kosdaq_strategy = "⚠️ 코스닥은 코스피 대비 더 큰 하락 압력. 코스닥 비중 최소화 권장."
    else:
        kosdaq_strategy = "📊 코스닥은 코스피 순매수 후 신호 혼조. 코스피 중심 대응 권장."
    
    return buy_timing, {
        "action": action,
        "risk": risk,
        "kosdaq": kosdaq_strategy,
        "net_flow_20": net_flow_20,
        "sell_count_20": len(recent_20_sells),
        "buy_count_20": len(recent_20_buys),
    }, most_recent


# ──────────────────────────────────────────────────────
# 7. 최근 20거래일 매매동향 로드
# ──────────────────────────────────────────────────────

def get_recent_flow_table(investor_df, kospi_df, n=20):
    """최근 n거래일 매매동향 + 코스피 지수 변화 테이블"""
    df = investor_df.dropna(subset=["외국인"]).copy()
    df = df.sort_values("날짜").tail(n).reset_index(drop=True)
    
    kospi_copy = kospi_df.copy()
    kospi_copy["date_only"] = pd.to_datetime(kospi_copy["date"]).dt.date
    
    rows = []
    for _, r in df.iterrows():
        d = pd.Timestamp(r["날짜"]).date()
        krow = kospi_copy[kospi_copy["date_only"] == d]
        close = krow.iloc[-1]["close"] if len(krow) > 0 else None
        rows.append({
            "날짜": r["날짜"].strftime("%Y-%m-%d") if hasattr(r["날짜"], "strftime") else str(r["날짜"]),
            "외국인": r["외국인"],
            "개인": r["개인"],
            "기관": r["기관계"],
            "코스피": close,
        })
    
    result = pd.DataFrame(rows)
    # 코스피 일간 등락률
    result["코스피_등락"] = result["코스피"].pct_change() * 100
    return result


# ──────────────────────────────────────────────────────
# 8. 리포트 생성
# ──────────────────────────────────────────────────────

def generate_report():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    print("  데이터 로드 중...")
    kospi_df, kosdaq_df = load_index_data()
    
    try:
        investor_kospi = load_investor_data("01")
    except FileNotFoundError as e:
        print(f"  [ERROR] {e}")
        return
    
    print("  이벤트 감지 중...")
    events_raw, sell_thr, buy_thr, sell_1p, buy_5p, buy_1p = detect_significant_events(
        investor_kospi, look_back_days=60
    )
    
    if not events_raw:
        print("  최근 60 거래일 내 유의미한 이벤트 없음.")
        return
    
    print(f"  {len(events_raw)}개 이벤트 감지")
    
    # 현재 구간 진단
    phase, event_diagnostics = diagnose_market_phase(events_raw, kospi_df, look_back_days=60)
    buy_timing, strategy_info, most_recent_ev = derive_strategy(events_raw, event_diagnostics, kospi_df)
    
    # 최근 20거래일 흐름
    recent_flow = get_recent_flow_table(investor_kospi, kospi_df, n=20)
    
    # 현재 코스피/코스닥 수준
    current_kospi = get_index_at_date(kospi_df, TODAY)
    current_kosdaq = get_index_at_date(kosdaq_df, TODAY)
    
    # 최근 1개월 누적 외국인 순매수
    recent_1m = investor_kospi.tail(20)
    net_1m = recent_1m["외국인"].sum()
    net_1m_str = f"+{net_1m:,.0f}" if net_1m >= 0 else f"{net_1m:,.0f}"
    
    # 최근 3개월
    recent_3m = investor_kospi.tail(60)
    net_3m = recent_3m["외국인"].sum()
    net_3m_str = f"+{net_3m:,.0f}" if net_3m >= 0 else f"{net_3m:,.0f}"
    
    # 날짜 기반 파일명
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"외국인_매매동향_현재구간_전략_{ts}.md"
    filepath = os.path.join(RESULTS_DIR, filename)
    
    # ──────────────────────
    # 리포트 작성
    # ──────────────────────
    lines = []
    
    lines += [
        f"# 📊 외국인 매매동향 기반 현재 구간 진단 & 대응 전략",
        "",
        f"**분석일시**: {TODAY_STR}",
        f"**데이터 출처**: Naver Finance (투자자별 매매동향) + Yahoo Finance (지수)",
        f"**분석 기준**: 최근 60 거래일 내 유의미한 외국인 이벤트 추적",
        "",
        "---",
        "",
    ]
    
    # ── 현재 시장 현황
    lines += [
        "## 📌 현재 시장 현황",
        "",
        f"| 항목 | 현재값 |",
        f"|:----:|:------:|",
        f"| 코스피 | {current_kospi:,.2f} pt |" if current_kospi else "| 코스피 | N/A |",
        f"| 코스닥 | {current_kosdaq:,.2f} pt |" if current_kosdaq else "| 코스닥 | N/A |",
        f"| 최근 1개월(20거래일) 외국인 누적 | **{net_1m_str}억원** |",
        f"| 최근 3개월(60거래일) 외국인 누적 | **{net_3m_str}억원** |",
        "",
        "---",
        "",
    ]
    
    # ── 현재 시장 국면
    lines += [
        "## 🎯 현재 시장 국면 진단",
        "",
        f"> ### {phase}",
        "",
    ]
    
    # 가장 최근 이벤트 기준 D+N 설명
    if most_recent_ev:
        n = most_recent_ev["경과_거래일"]
        ev_date = most_recent_ev["날짜"]
        ev_type = most_recent_ev["구분"]
        ev_str = most_recent_ev["강도"]
        exp_r = most_recent_ev["통계기대수익_D+N"]
        exp_p = most_recent_ev["통계상승확률"]
        actual = most_recent_ev["현재실제수익"]
        
        lines += [
            f"**가장 최근 주요 이벤트**: `{ev_date}` 코스피 {ev_type} ({ev_str})",
            f"- 오늘 기준 경과 거래일: **D+{n}**",
            f"- 통계적 기대수익률 (D+{n}): **{exp_r:+.2f}%** (상승확률 {exp_p}%)",
        ]
        if actual is not None:
            diff = actual - exp_r
            diff_str = f"{diff:+.2f}%"
            lines.append(f"- 실제 수익률 (이벤트 당일 대비 현재): **{actual:+.2f}%** (통계 대비 {diff_str})")
        lines.append("")
    
    # ── 전략 박스
    lines += [
        "---",
        "",
        "## 💡 현재 권장 대응 전략",
        "",
        "```",
        f"╔══════════════════════════════════════════════════════════════╗",
        f"║  📍 현재 구간: D+{most_recent_ev['경과_거래일'] if most_recent_ev else 'N/A'} ({most_recent_ev['구분'] if most_recent_ev else ''} 후 {most_recent_ev['경과_거래일'] if most_recent_ev else 'N/A'}거래일)  ",
        f"╠══════════════════════════════════════════════════════════════╣",
        f"║                                                              ║",
        f"║  {buy_timing[:60]:<60}  ║",
        f"║                                                              ║",
        f"║  ✅ 권장 액션: {strategy_info['action'][:46]:<46}  ║",
        f"║  ⚡ 리스크 수준: {strategy_info['risk']:<44}  ║",
        f"║                                                              ║",
        f"╚══════════════════════════════════════════════════════════════╝",
        "```",
        "",
        f"**코스닥 전략**: {strategy_info['kosdaq']}",
        "",
        "---",
        "",
    ]
    
    # ── 최근 이벤트별 D+N 현황 테이블
    lines += [
        "## 📋 최근 유의미한 외국인 이벤트 D+N 현황",
        "",
        f"*(최근 60 거래일 내 순매도 하위 5% 이하 / 순매수 상위 5% 이상 이벤트)*",
        "",
        "| 날짜 | 구분 | 강도 | 백분위 | 외국인(억) | 경과(D+N) | 통계기대수익 | 상승확률 | 실제수익 | 잔여기대 |",
        "|:----:|:----:|:----:|:------:|:---------:|:--------:|:-----------:|:-------:|:-------:|:-------:|",
    ]
    
    for ed in sorted(event_diagnostics, key=lambda x: x["날짜"], reverse=True):
        n = ed["경과_거래일"]
        exp_r = ed["통계기대수익_D+N"]
        exp_p = ed["통계상승확률"]
        actual = ed["현재실제수익"]
        remain = ed["D+30까지_잔여기대"]
        actual_str = f"{actual:+.2f}%" if actual is not None else "N/A"
        remain_str = f"{remain:+.2f}%" if n < 30 else "완료"
        구분_emoji = "🔴" if ed["구분"] == "순매도" else "🟢"
        lines.append(
            f"| {ed['날짜']} | {구분_emoji}{ed['구분']} | {ed['강도']} | {ed['백분위']} | "
            f"{ed['외국인']:,.0f} | **D+{n}** | {exp_r:+.2f}% | {exp_p}% | {actual_str} | {remain_str} |"
        )
    
    lines += [
        "",
        "> **참고**: 통계기대수익은 2006~현재 20년 데이터 기준 해당 이벤트 D+N 시점 누적 평균 수익률",
        "",
        "---",
        "",
    ]
    
    # ── 분할 매수 시나리오 (최근 가장 큰 매도 이벤트 기준)
    biggest_sell = None
    for ev in sorted(event_diagnostics, key=lambda x: x["외국인"]):
        if ev["구분"] == "순매도":
            biggest_sell = ev
            break
    
    if biggest_sell:
        bs_n = biggest_sell["경과_거래일"]
        bs_date = biggest_sell["날짜"]
        
        lines += [
            f"## 📈 분할 매수 시나리오 (기준 이벤트: {bs_date})",
            "",
            f"> 코스피 외국인 역대 최대급 순매도 이벤트 기준 D+{bs_n} 현재 위치",
            "",
            "| 매수 단계 | 시점 | 통계 기대수익 | 권장 비중 | 오늘 기준 |",
            "|:--------:|:----:|:------------:|:--------:|:--------:|",
        ]
        
        stages = [
            ("1차 매수", "D+3~5", 3, 5, "25%"),
            ("2차 매수", "D+5~10", 5, 10, "25%"),
            ("3차 매수", "D+10~20", 10, 20, "25%"),
            ("차익실현", "D+20~30", 20, 30, "분할 매도"),
        ]
        
        for stage_name, stage_range, d1, d2, weight in stages:
            r1 = SELL_KOSPI_STATS.get(d1, (0, 50))[0]
            r2 = SELL_KOSPI_STATS.get(d2, (0, 50))[0]
            
            if bs_n < d1:
                status = "⏳ 아직"
            elif d1 <= bs_n <= d2:
                status = "✅ **현재 구간**"
            else:
                status = "✔️ 경과"
            
            lines.append(
                f"| {stage_name} | {stage_range} | {r1:+.1f}%~{r2:+.1f}% | {weight} | {status} |"
            )
        
        lines += ["", "---", ""]
    
    # ── 매수 전환 이벤트 확인
    recent_buy_evs = [e for e in event_diagnostics if e["구분"] == "순매수"]
    if recent_buy_evs:
        latest_buy = sorted(recent_buy_evs, key=lambda x: x["날짜"], reverse=True)[0]
        lb_n = latest_buy["경과_거래일"]
        lb_date = latest_buy["날짜"]
        
        lines += [
            f"## 🔄 외국인 매수 전환 신호 분석",
            "",
            f"> 최근 매수 전환 이벤트: **{lb_date}** ({latest_buy['강도']}, D+{lb_n})",
            "",
            "| 평가 항목 | 내용 |",
            "|:--------:|:----:|",
            f"| 매수 강도 | {latest_buy['강도']} ({latest_buy['백분위']}) |",
            f"| 매수 규모 | {latest_buy['외국인']:+,.0f}억원 |",
            f"| 경과 거래일 | D+{lb_n} |",
            f"| 통계 기대수익 (D+{lb_n}) | {latest_buy['통계기대수익_D+N']:+.2f}% |",
            f"| 통계 상승확률 | {latest_buy['통계상승확률']}% |",
        ]
        
        if latest_buy["현재실제수익"] is not None:
            lines.append(f"| 실제 수익률 | {latest_buy['현재실제수익']:+.2f}% |")
        
        # 추가 경고: 매수 후 D+1 -6.37% 급락의 의미
        if latest_buy["현재실제수익"] is not None and latest_buy["현재실제수익"] < -3.0 and lb_n <= 5:
            lines += [
                "",
                "> ⚠️ **주의**: 대량 매수 이후 단기 급락 발생. 역사적으로 이런 경우 추가 변동성이 남아있을 수 있습니다.",
                "> 분할 매수 전략으로 리스크 분산 필요.",
            ]
        
        lines += ["", "---", ""]
    
    # ── 최근 20거래일 매매동향 테이블
    lines += [
        "## 📊 최근 20거래일 외국인 매매동향 (코스피)",
        "",
        "| 날짜 | 외국인(억원) | 개인(억원) | 기관(억원) | 코스피 | 일간등락 |",
        "|:----:|:-----------:|:---------:|:---------:|:------:|:-------:|",
    ]
    
    for _, r in recent_flow.iterrows():
        fval = r["외국인"]
        flag = ""
        if not pd.isna(fval):
            if fval <= sell_thr:
                flag = "🔴"
            elif fval >= buy_thr:
                flag = "🟢"
        
        f_str = f"{flag}{fval:+,.0f}" if not pd.isna(fval) else "N/A"
        p_str = f"{r['개인']:+,.0f}" if not pd.isna(r["개인"]) else "N/A"
        i_str = f"{r['기관']:+,.0f}" if not pd.isna(r["기관"]) else "N/A"
        k_str = f"{r['코스피']:,.2f}" if r["코스피"] is not None and not pd.isna(r["코스피"]) else "N/A"
        d_str = f"{r['코스피_등락']:+.2f}%" if not pd.isna(r["코스피_등락"]) else "-"
        
        lines.append(f"| {r['날짜']} | {f_str} | {p_str} | {i_str} | {k_str} | {d_str} |")
    
    lines += [
        "",
        "> 🔴 = 순매도 하위 5% 이하 (대량 매도 이벤트), 🟢 = 순매수 상위 5% 이상 (대량 매수 이벤트)",
        "",
        "---",
        "",
    ]
    
    # ── 종합 결론
    lines += [
        "## ✅ 종합 결론 및 투자 전략 요약",
        "",
        "```",
        "╔══════════════════════════════════════════════════════════════════╗",
        "║                   외국인 매매 기반 종합 전략                      ║",
        "╠══════════════════════════════════════════════════════════════════╣",
        "║                                                                  ║",
    ]
    
    # 결론 라인들
    conclusion_lines = [
        f"  📍 현재 국면: {phase.split(chr(10))[0][:55]}",
        f"  📅 기준 이벤트 D+{most_recent_ev['경과_거래일'] if most_recent_ev else 'N/A'} ({most_recent_ev['날짜'] if most_recent_ev else ''} {most_recent_ev['구분'] if most_recent_ev else ''})   ",
        f"  ",
        f"  💰 권장 액션: {strategy_info['action'][:53]}",
        f"  ⚡ 리스크: {strategy_info['risk'][:57]}",
        f"  ",
        f"  📊 코스닥: {strategy_info['kosdaq'][:55]}",
        f"  ",
        f"  🔑 핵심: 통계적으로 외국인 대량 매도 후               ",
        f"     D+10~30 구간에서 코스피 반등 확률 높음 (60~65%)     ",
        f"     분할 매수 + D+20~30 차익실현 전략 유효              ",
    ]
    
    for cl in conclusion_lines:
        lines.append(f"║  {cl:<65}  ║")
    
    lines += [
        "║                                                                  ║",
        "╚══════════════════════════════════════════════════════════════════╝",
        "```",
        "",
        "---",
        "",
        f"*본 리포트는 통계적 패턴 기반 참고 자료입니다. 실제 투자 결정은 추가적인 분석과 판단이 필요합니다.*",
        f"*생성일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
    ]
    
    content = "\n".join(lines)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    
    print(f"  [저장] {filepath}")
    return filepath


# ──────────────────────────────────────────────────────
# 실행
# ──────────────────────────────────────────────────────

if __name__ == "__main__":
    print("외국인 매매동향 기반 현재 구간 진단 & 전략 리포트 생성 중...")
    result = generate_report()
    if result:
        print(f"  완료: {os.path.basename(result)}")
    else:
        print("  리포트 생성 실패")
