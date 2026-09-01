"""
외국인 순매도 Top 20 분석기
- 코스피, 코스닥, 선물 시장별 외국인 순매도 상위 20일 추출
- 해당일 이후 1~30 거래일간 코스피/코스닥 지수 변화 분석
- 최근 20년 / 최근 10년 비교 분석
- data/investor_data.db에 투자자 매매동향 저장 (증분 업데이트)
"""

import warnings
warnings.filterwarnings('ignore')

import requests
import pandas as pd
import numpy as np
import sqlite3
import time
import os
import sys
from datetime import datetime, timedelta
from io import StringIO

# ─────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "market_data.db")
INVESTOR_DB_PATH = os.path.join(BASE_DIR, "data", "investor_data.db")
CACHE_DIR = os.path.join(BASE_DIR, "data", "cache")
from config import WEEKLY_RESEARCH_DIR as RESULTS_DIR

MARKETS = {
    "KOSPI": "01",
    "KOSDAQ": "02",
    "선물": "03",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://finance.naver.com/sise/sise_deal.naver",
}

TOP_N = 20
FOLLOW_DAYS = 30  # 이후 추적할 거래일 수

# DB 컬럼 매핑 (한글 → 영문, DB 저장용)
_COL_MAP = {
    "날짜": "date", "개인": "individual", "외국인": "foreign",
    "기관계": "institution", "금융투자": "finance", "보험": "insurance",
    "투신 (사모)": "trust", "은행": "bank", "기타금융기관": "other_finance",
    "연기금등": "pension", "기타법인": "other_corp",
}
_COL_MAP_REV = {v: k for k, v in _COL_MAP.items()}


def _ensure_investor_db():
    """investor_data.db 테이블 생성"""
    conn = sqlite3.connect(INVESTOR_DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS investor_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE NOT NULL,
            market VARCHAR(2) NOT NULL,
            individual FLOAT,
            foreign_ FLOAT,
            institution FLOAT,
            finance FLOAT,
            insurance FLOAT,
            trust FLOAT,
            bank FLOAT,
            other_finance FLOAT,
            pension FLOAT,
            other_corp FLOAT,
            UNIQUE(date, market)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_inv_date ON investor_daily(date)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_inv_market ON investor_daily(market)")
    conn.commit()
    return conn, cur


def _db_latest_date(cur, sosok):
    """DB에서 해당 시장의 가장 최근 날짜 조회"""
    cur.execute(
        "SELECT MAX(date) FROM investor_daily WHERE market = ?", (sosok,)
    )
    row = cur.fetchone()
    return row[0] if row and row[0] else None


def _db_count(cur, sosok):
    cur.execute("SELECT COUNT(*) FROM investor_daily WHERE market = ?", (sosok,))
    return cur.fetchone()[0]


def _save_to_db(conn, cur, df, sosok):
    """DataFrame → investor_data.db 저장"""
    inserted = 0
    for _, row in df.iterrows():
        try:
            date_str = pd.to_datetime(row["날짜"]).strftime("%Y-%m-%d")
            cur.execute(
                "INSERT INTO investor_daily "
                "(date, market, individual, foreign_, institution, finance, insurance, "
                "trust, bank, other_finance, pension, other_corp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (date_str, sosok,
                 _to_float(row.get("개인")), _to_float(row.get("외국인")),
                 _to_float(row.get("기관계")), _to_float(row.get("금융투자")),
                 _to_float(row.get("보험")), _to_float(row.get("투신 (사모)")),
                 _to_float(row.get("은행")), _to_float(row.get("기타금융기관")),
                 _to_float(row.get("연기금등")), _to_float(row.get("기타법인")),
                 ),
            )
            inserted += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    return inserted


def _to_float(v):
    try:
        return float(v) if pd.notna(v) else None
    except (ValueError, TypeError):
        return None


def _load_from_db(sosok):
    """investor_data.db에서 DataFrame으로 로드 (한글 컬럼명으로 반환)"""
    conn = sqlite3.connect(INVESTOR_DB_PATH)
    df = pd.read_sql_query(
        "SELECT date, individual, foreign_ as '외국인', institution, "
        "finance, insurance, trust, bank, other_finance, pension, other_corp "
        "FROM investor_daily WHERE market = ? ORDER BY date",
        conn, params=(sosok,), parse_dates=["date"],
    )
    conn.close()
    # 컬럼명을 한글로 복원
    df = df.rename(columns={
        "date": "날짜", "individual": "개인", "institution": "기관계",
        "finance": "금융투자", "insurance": "보험", "trust": "투신 (사모)",
        "bank": "은행", "other_finance": "기타금융기관",
        "pension": "연기금등", "other_corp": "기타법인",
    })
    return df


def _scrape_naver_pages(sosok, max_pages, delay, stop_before=None):
    """네이버 금융에서 투자자별 매매동향 스크래핑
    stop_before: 이 날짜 이전 데이터가 나오면 중단 (증분 수집 시)
    """
    url = "https://finance.naver.com/sise/investorDealTrendDay.naver"
    all_rows = []

    for page in range(1, max_pages + 1):
        try:
            params = {"bizdate": datetime.now().strftime("%Y%m%d"), "sosok": sosok, "page": page}
            resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
            resp.raise_for_status()

            dfs = pd.read_html(StringIO(resp.text), encoding="euc-kr")
            df = dfs[0].dropna(how="all")

            if df.empty:
                print(f"  Page {page}: 데이터 없음, 중단")
                break

            # 컬럼 정리 (MultiIndex 처리)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0] if c[0] == c[1] else c[1] for c in df.columns]

            df = df.copy()
            df["날짜"] = pd.to_datetime(df["날짜"], format="%y.%m.%d", errors="coerce")
            df = df.dropna(subset=["날짜"])

            if df.empty:
                break

            all_rows.append(df)

            # 증분 모드: DB에 이미 있는 날짜까지 도달하면 중단
            if stop_before and df["날짜"].min() <= pd.Timestamp(stop_before):
                print(f"  DB 기존 데이터({stop_before}) 도달, 중단 (Page {page})")
                break

            # 전체 모드: 2005년 이전 도달 시 중단
            if not stop_before and df["날짜"].min() < datetime(2005, 1, 1):
                print(f"  2005년 이전 도달, 중단 (Page {page})")
                break

            if page % 50 == 0:
                earliest = df["날짜"].min()
                print(f"  Page {page}: ~{earliest.strftime('%Y-%m-%d')}")

            time.sleep(delay)

        except Exception as e:
            print(f"  Page {page} 오류: {e}")
            time.sleep(1)
            continue

    if not all_rows:
        return pd.DataFrame()

    result = pd.concat(all_rows, ignore_index=True)
    result = result.sort_values("날짜").drop_duplicates(subset=["날짜"]).reset_index(drop=True)
    return result


def fetch_investor_data(sosok, max_pages=550, delay=0.3):
    """투자자별 매매동향 수집 — DB 우선, 증분 업데이트"""
    conn, cur = _ensure_investor_db()
    db_count = _db_count(cur, sosok)
    latest = _db_latest_date(cur, sosok)

    if db_count == 0:
        # ① 최초 실행: 전체 스크래핑
        print(f"  [최초] 전체 데이터 스크래핑 (최대 {max_pages}페이지)...")
        df = _scrape_naver_pages(sosok, max_pages, delay)
        if not df.empty:
            inserted = _save_to_db(conn, cur, df, sosok)
            print(f"  → DB 저장: {inserted}건")
    else:
        # ② 증분 업데이트: DB 최신일 이후만 수집
        today_str = datetime.now().strftime("%Y-%m-%d")
        if latest == today_str or latest == (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"):
            # 오늘 또는 어제 데이터까지 있으면 업데이트 불필요
            pass
        else:
            print(f"  [증분] {latest} 이후 데이터 수집 중...")
            # 최근 데이터만 수집 (DB 기존일까지 닿으면 중단)
            df = _scrape_naver_pages(sosok, max_pages=100, delay=delay, stop_before=latest)
            if not df.empty:
                # DB 최신일 이후 데이터만 필터
                df_new = df[df["날짜"] > pd.Timestamp(latest)]
                if not df_new.empty:
                    inserted = _save_to_db(conn, cur, df_new, sosok)
                    print(f"  → DB 추가: {inserted}건 ({latest} → {df_new['날짜'].max().strftime('%Y-%m-%d')})")

    conn.close()

    # DB에서 전체 데이터 로드
    result = _load_from_db(sosok)
    new_latest = _db_latest_date(sqlite3.connect(INVESTOR_DB_PATH).cursor(), sosok)
    print(f"  [DB] {len(result)}일 로드 ({result['날짜'].min().strftime('%Y-%m-%d')} ~ {result['날짜'].max().strftime('%Y-%m-%d')})")
    return result


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
        # 이벤트 날짜에 해당하는 인덱스 찾기
        idx = np.searchsorted(dates, np.datetime64(event_date))
        
        if idx >= len(dates):
            continue
        
        # 이벤트 당일 종가
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
    """특정 시장의 외국인 순매도 Top N 분석"""
    # 기간 필터
    mask = investor_df["날짜"] >= datetime(start_year, 1, 1)
    df = investor_df[mask].copy()
    
    if df.empty:
        return None
    
    # 외국인 순매수 컬럼 (음수 = 순매도)
    foreign_col = "외국인"
    df[foreign_col] = pd.to_numeric(df[foreign_col], errors="coerce")
    
    # 순매도 상위 (가장 큰 음수 = 가장 많이 판 날)
    top_selling = df.nsmallest(TOP_N, foreign_col).reset_index(drop=True)
    
    # 이벤트 날짜 목록
    event_dates = top_selling["날짜"].tolist()
    
    # 코스피 이후 수익률
    kospi_returns = get_after_returns(index_kospi, event_dates, FOLLOW_DAYS)
    
    # 코스닥 이후 수익률
    kosdaq_returns = get_after_returns(index_kosdaq, event_dates, FOLLOW_DAYS)
    
    return {
        "market_name": market_name,
        "period_name": period_name,
        "top_selling": top_selling,
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
    lines.append("# 📊 외국인 순매도 Top 20 이후 지수 변화 분석")
    lines.append("")
    lines.append(f"**분석일시**: {now_str}")
    lines.append(f"**데이터 출처**: Naver Finance (투자자별 매매동향)")
    lines.append(f"**분석 대상**: 코스피, 코스닥, 선물 시장 외국인 순매도 상위 {TOP_N}일")
    lines.append(f"**추적 기간**: 이후 {FOLLOW_DAYS} 거래일")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # ── 결론부터: 매매 전략 요약 ──
    # 20년 기준 KOSPI 순매도 후 코스피 D+5, D+20 평균 수익률 계산
    _kospi_20y = [r for r in all_results if "20년" in r["period_name"] and r["market_name"] == "KOSPI"]
    _d5_avg = 0
    _d10_avg = 0
    _d20_avg = 0
    _d20_up = 0
    if _kospi_20y:
        _kr = _kospi_20y[0]["kospi_returns"]
        if not _kr.empty:
            _d5_avg = _kr["D+5"].mean() if "D+5" in _kr else 0
            _d10_avg = _kr["D+10"].mean() if "D+10" in _kr else 0
            _d20_avg = _kr["D+20"].mean() if "D+20" in _kr else 0
            _d20_up = (_kr["D+20"] > 0).mean() * 100 if "D+20" in _kr else 0
    
    lines.append("## 🚨 결론부터: 외국인 대량 순매도 = 매수 기회!")
    lines.append("")
    lines.append("> **외국인이 대량으로 팔았다 → 🟢 사라! (역발상 매수)**")
    lines.append("")
    lines.append("```")
    lines.append("╔══════════════════════════════════════════════════════════════╗")
    lines.append("║  📌 외국인 대량 순매도 발생 시 → 매수 전략                    ║")
    lines.append("╠══════════════════════════════════════════════════════════════╣")
    lines.append("║                                                              ║")
    if _d5_avg < 0:
        lines.append("║  ❌ D+0~3: 당일~3일은 추가 하락 가능 → 아직 사지 마라!    ║")
        lines.append("║  🟡 D+3~5: 바닥 확인 후 → 1차 분할 매수 시작              ║")
        lines.append("║  🟢 D+5~10: 반등 시작 → 2차 추가 매수                     ║")
    else:
        lines.append("║  🟡 D+0~1: 당일 추가 하락 가능 → 서두르지 마라!           ║")
        lines.append("║  🟢 D+2~3: 반등 시작 → 1차 분할 매수                      ║")
        lines.append("║  🟢 D+5~7: 눌림 시 → 2차 추가 매수                        ║")
    lines.append("║                                                              ║")
    lines.append(f"║  📈 D+20 기준: 평균 수익률 {_d20_avg:+.2f}%, 상승확률 {_d20_up:.0f}%     ║")
    lines.append("║                                                              ║")
    lines.append("║  📍 매도(차익실현) 시점:                                      ║")
    if _d20_avg > _d10_avg:
        lines.append("║    → D+20~30 근처에서 분할 매도 (수익률 극대화)            ║")
    else:
        lines.append("║    → D+10~15 근처에서 1차 매도, 잔량은 D+20~30            ║")
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
        lines.append("| 시장 | 외국인 순매도 후 | D+1 | D+5 | D+10 | D+20 | D+30 | 상승확률(D+20) |")
        lines.append("|:----:|:-------------:|:---:|:---:|:----:|:----:|:----:|:-------------:|")
        
        # D+20 기준 순위 산출 (순매도 후 반등이 큰 시장 = 매수 기회)
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
        lines.append(f"## 📌 {r['market_name']} 외국인 순매도 Top {TOP_N} ({r['period_name']})")
        lines.append("")
        
        ts = r["top_selling"]
        
        # 순매도 순위표
        lines.append("### 순매도 순위")
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
        
        # 이후 지수 변화 - 코스피
        for idx_name, ret_df in [("코스피", r["kospi_returns"]), ("코스닥", r["kosdaq_returns"])]:
            if ret_df.empty:
                continue
                
            lines.append(f"### {idx_name} 지수 변화 (순매도 이후)")
            lines.append("")
            
            # D+20 기준 Top 3 이벤트에 별표 부여 (반등 최우수)
            d20_star_map = {}
            if "D+20" in ret_df.columns:
                d20_ranked = ret_df["D+20"].dropna().sort_values(ascending=False)
                for rank_i, orig_idx in enumerate(d20_ranked.index[:3]):
                    d20_star_map[orig_idx] = ["🥇⭐⭐⭐", "🥈⭐⭐", "🥉⭐"][rank_i]
            
            # 개별 이벤트별 수익률
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
    lines.append("### 🟢 외국인 대량 순매도 = 역발상 매수 기회")
    lines.append("")
    lines.append("| 구분 | 전략 | 설명 |")
    lines.append("|:----:|:----:|:-----|")
    
    # 20년 결과에서 패턴 추출
    for r in all_results:
        if "20년" in r["period_name"] and r["market_name"] == "KOSPI":
            kr = r["kospi_returns"]
            if not kr.empty and "D+20" in kr:
                avg_d5 = kr["D+5"].mean() if "D+5" in kr else 0
                avg_d20 = kr["D+20"].mean()
                up_prob = (kr["D+20"] > 0).mean() * 100
                
                if avg_d5 < 0:
                    lines.append(f"| 매수 시점 | **D+3~5** | 순매도 후 3~5일 추가 하락 후 바닥 → 분할 매수 |")
                else:
                    lines.append(f"| 매수 시점 | **D+1~3** | 순매도 다음 날부터 반등 시작 → 빠른 매수 유리 |")
                lines.append(f"| 매도 시점 | **D+20~30** | 평균 {avg_d20:+.2f}% 수익, 상승확률 {up_prob:.0f}% |")
                lines.append(f"| 핵심 근거 | 역발상 | 외국인 공포 매도 = 시장 저점 가능성 높음 |")
    
    lines.append("")
    lines.append("### ⚠ 주의사항")
    lines.append("")
    lines.append("1. **당일(D+0) 매수는 금물** — 추가 하락 가능성 높음")
    lines.append("2. **분할 매수 필수** — 한 번에 올인하지 말 것")
    lines.append("3. 선물 매도는 헤지 목적일 수 있어 현물 매도와 동일시하지 말 것")
    lines.append("4. 과거 통계이며 미래 수익을 보장하지 않음")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("**데이터 출처**: Naver Finance 투자자별 매매동향 → investor_data.db")
    lines.append("**분석 도구**: Python + pandas")
    
    return "\n".join(lines)


def main():
    print("=" * 60)
    print("외국인 순매도 Top 20 분석기")
    print("=" * 60)
    
    # 1. 지수 데이터 로드
    print("\n[1/3] 코스피/코스닥 지수 데이터 로드...")
    kospi, kosdaq = load_index_data()
    print(f"  코스피: {len(kospi)}일 ({kospi['date'].min().strftime('%Y-%m-%d')} ~ {kospi['date'].max().strftime('%Y-%m-%d')})")
    print(f"  코스닥: {len(kosdaq)}일 ({kosdaq['date'].min().strftime('%Y-%m-%d')} ~ {kosdaq['date'].max().strftime('%Y-%m-%d')})")
    
    # 2. 투자자별 매매동향 수집
    print("\n[2/3] 투자자별 매매동향 수집 (Naver Finance)...")
    investor_data = {}
    for market_name, sosok in MARKETS.items():
        print(f"\n  === {market_name} (sosok={sosok}) ===")
        df = fetch_investor_data(sosok)
        if not df.empty:
            investor_data[market_name] = df
            print(f"  기간: {df['날짜'].min().strftime('%Y-%m-%d')} ~ {df['날짜'].max().strftime('%Y-%m-%d')}")
    
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
    filename = f"외국인_순매도_Top20_분석_{timestamp}.md"
    filepath = os.path.join(RESULTS_DIR, filename)
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"\n✅ 리포트 저장 완료: {filepath}")
    print(f"   총 {len(all_results)}개 분석 결과")


if __name__ == "__main__":
    main()
