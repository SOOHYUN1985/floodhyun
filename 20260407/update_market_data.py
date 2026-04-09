"""
[스크립트 2] DB 일일 업데이트용
- 최근 7일 데이터를 삭제 후 재수집 (명절·연말 등 비정상 데이터 보정)
- 삭제된 날짜 ~ 오늘까지 yfinance로 다운로드하여 갱신
- 시장 지수(코스피/코스닥) + 개별 종목(보통주/우선주) 통합 관리
- 한글 사용자명 경로의 SSL 인증서 문제 자동 우회

사용법:
    python update_market_data.py          # 지수 + 종목 모두 업데이트
    python update_market_data.py --index  # 지수만 업데이트
    python update_market_data.py --stock  # 종목만 업데이트
"""

import os
import sys
import shutil
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import certifi

# ── SSL 인증서 한글 경로 우회 ──────────────────────────
_cert_src = certifi.where()
_cert_dst = r'C:\temp\cacert.pem'
if not os.path.exists(_cert_dst) or os.path.getmtime(_cert_src) > os.path.getmtime(_cert_dst):
    os.makedirs(os.path.dirname(_cert_dst), exist_ok=True)
    shutil.copy2(_cert_src, _cert_dst)
os.environ['CURL_CA_BUNDLE'] = _cert_dst
os.environ['SSL_CERT_FILE'] = _cert_dst
os.environ['REQUESTS_CA_BUNDLE'] = _cert_dst

# ── 경로 설정 ──────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
from config import DB_PATH

import yfinance as yf
import requests
import re

MARKETS = [
    ('^KS11', 'KS11', '코스피', 'KOSPI'),
    ('^KQ11', 'KQ11', '코스닥', 'KOSDAQ'),
]

# ── 보통주/우선주 종목 리스트 ──────────────────────────
# (보통주코드, 우선주코드, 종목명)
STOCK_PAIRS = [
    ("005930", "005935", "삼성전자"),
    ("009150", "009155", "삼성전기"),
    ("005380", "005385", "현대차"),
    ("006800", "006805", "미래에셋증권"),
    ("001040", "001045", "CJ"),
    ("001680", "001685", "대상"),
    ("034730", "03473K", "SK"),
    ("000880", "00088K", "한화"),
    ("003550", "003555", "LG"),
    ("078930", "078935", "GS"),
    ("000150", "000155", "두산"),
    ("090430", "090435", "아모레퍼시픽"),
    # ── 추가 대형주 (시총 5천억+) ──
    ("051910", "051915", "LG화학"),
    ("006400", "006405", "삼성SDI"),
    ("066570", "066575", "LG전자"),
    ("000810", "000815", "삼성화재"),
    ("010950", "010955", "S-Oil"),
    ("003490", "003495", "대한항공"),
    ("000100", "000105", "유한양행"),
    ("051900", "051905", "LG생활건강"),
    ("097950", "097955", "CJ제일제당"),
    # ── 추가 지주사/대형주 (시총 5천억+) ──
    ("000720", "000725", "현대건설"),
    ("011780", "011785", "금호석유"),
    ("120110", "120115", "코오롱인더"),
    ("002020", "002025", "코오롱"),
    ("008770", "008775", "호텔신라"),
    ("000210", "000215", "DL"),
]

CLEANUP_DAYS = 7  # 최근 N일 삭제 후 재수집


def _prepare_df(df, ticker, db_code):
    """yfinance DataFrame → DB 삽입용 정리"""
    df = df.reset_index()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] if c[1] == '' or c[1] == ticker else c[0] for c in df.columns]
    df['change'] = df['Close'].pct_change().fillna(0)
    df = df[['Date', 'Open', 'High', 'Low', 'Close', 'Volume', 'change']]
    df.columns = ['date', 'open', 'high', 'low', 'close', 'volume', 'change']
    df['index_name'] = db_code
    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
    return df


def _fetch_naver_index(naver_symbol, count=15):
    """네이버 금융에서 지수 일봉 데이터 가져오기 (yfinance fallback용)
    Returns: DataFrame with columns [date, open, high, low, close, volume]
    """
    url = 'https://fchart.stock.naver.com/sise.nhn'
    params = {'symbol': naver_symbol, 'timeframe': 'day', 'count': count, 'requestType': 0}
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        # XML 파싱: <item data="20260401|5330.04|5512.33|5272.45|5478.7|958953" />
        items = re.findall(r'data="([^"]+)"', resp.text)
        rows = []
        for item in items:
            parts = item.split('|')
            if len(parts) >= 6:
                rows.append({
                    'date': f"{parts[0][:4]}-{parts[0][4:6]}-{parts[0][6:8]}",
                    'open': float(parts[1]),
                    'high': float(parts[2]),
                    'low': float(parts[3]),
                    'close': float(parts[4]),
                    'volume': float(parts[5]),
                })
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        # 등락률 계산
        df['change'] = df['close'].pct_change().fillna(0)
        return df
    except Exception as e:
        print(f"  ⚠️ 네이버 금융 조회 실패: {e}")
        return pd.DataFrame()


def _db_stats(cursor, db_code):
    cursor.execute(
        "SELECT MIN(date), MAX(date), COUNT(*) "
        "FROM index_data WHERE index_name = ?", (db_code,),
    )
    return cursor.fetchone()


def _ensure_stock_table(cursor):
    """stock_data 테이블이 없으면 생성"""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE NOT NULL,
            stock_code VARCHAR(10) NOT NULL,
            close FLOAT NOT NULL,
            volume FLOAT,
            UNIQUE(date, stock_code)
        )
    """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_stock_date ON stock_data(date)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_stock_code ON stock_data(stock_code)"
    )


def _stock_db_stats(cursor, stock_code):
    cursor.execute(
        "SELECT MIN(date), MAX(date), COUNT(*) "
        "FROM stock_data WHERE stock_code = ?", (stock_code,),
    )
    return cursor.fetchone()


def _get_all_stock_codes():
    """STOCK_PAIRS에서 모든 종목코드 추출 → yfinance ticker 매핑"""
    codes = []
    for pair in STOCK_PAIRS:
        common, preferred = pair[0], pair[1]
        codes.append((common, f"{common}.KS"))
        codes.append((preferred, f"{preferred}.KS"))
    return codes


def update_stock_data(conn, cur, full=False):
    """종목 데이터 업데이트 (보통주/우선주)"""
    today = datetime.now()
    today_str = today.strftime('%Y-%m-%d')
    cutoff = (today - timedelta(days=CLEANUP_DAYS)).strftime('%Y-%m-%d')

    _ensure_stock_table(cur)

    # 최초 실행 여부 확인 (데이터가 있는지)
    cur.execute("SELECT COUNT(*) FROM stock_data")
    existing_count = cur.fetchone()[0]

    if existing_count == 0 or full:
        print("  📦 최초 실행 — 전체 데이터 다운로드 (period=max)")
        fetch_mode = "full"
    else:
        fetch_mode = "incremental"

    all_codes = _get_all_stock_codes()
    total_inserted = 0
    success_count = 0

    for stock_code, yf_ticker in all_codes:
        try:
            if fetch_mode == "incremental":
                # 최근 7일 삭제 후 재수집
                cur.execute(
                    "DELETE FROM stock_data WHERE stock_code = ? AND date >= ?",
                    (stock_code, cutoff),
                )
                conn.commit()

                fetch_start = (today - timedelta(days=CLEANUP_DAYS + 10)).strftime('%Y-%m-%d')
                fetch_end = (today + timedelta(days=1)).strftime('%Y-%m-%d')
                df = yf.download(yf_ticker, start=fetch_start, end=fetch_end, progress=False)
            else:
                df = yf.download(yf_ticker, period="max", progress=False)

            if df.empty:
                continue

            df = df.reset_index()
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0] if c[1] == '' or c[1] == yf_ticker else c[0] for c in df.columns]

            df = df[['Date', 'Close', 'Volume']].copy()
            df.columns = ['date', 'close', 'volume']
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
            df['stock_code'] = stock_code

            if fetch_mode == "incremental":
                df = df[df['date'] >= cutoff]

            inserted = 0
            for _, r in df.iterrows():
                try:
                    cur.execute(
                        "INSERT INTO stock_data (date, stock_code, close, volume) "
                        "VALUES (?, ?, ?, ?)",
                        (r['date'], r['stock_code'], float(r['close']),
                         float(r['volume']) if pd.notna(r['volume']) else 0),
                    )
                    inserted += 1
                except sqlite3.IntegrityError:
                    pass

            conn.commit()
            total_inserted += inserted
            success_count += 1

        except Exception as e:
            print(f"  ⚠️ {stock_code} 실패: {e}")
            continue

    return total_inserted, success_count


def update_market_data():
    """최근 7일 삭제 → 삭제 시작일~오늘 재수집"""
    today = datetime.now()
    today_str = today.strftime('%Y-%m-%d')
    cutoff = (today - timedelta(days=CLEANUP_DAYS)).strftime('%Y-%m-%d')

    # CLI 플래그 처리
    do_index = True
    do_stock = True
    full_stock = False
    if '--index' in sys.argv:
        do_stock = False
    elif '--stock' in sys.argv:
        do_index = False
    if '--full' in sys.argv:
        full_stock = True

    print("=" * 60)
    print("  DB 업데이트  (최근 7일 재수집)")
    print("=" * 60)
    print(f"DB : {DB_PATH}")
    print(f"오늘: {today_str}  |  삭제 기준일: {cutoff}")
    if do_index and do_stock:
        print(f"대상: 시장 지수 + 종목 데이터 ({len(STOCK_PAIRS)}쌍, {len(STOCK_PAIRS)*2}종목)")
    elif do_index:
        print("대상: 시장 지수만")
    else:
        print(f"대상: 종목 데이터만 ({len(STOCK_PAIRS)}쌍, {len(STOCK_PAIRS)*2}종목)")
    print()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    total_inserted = 0

    # ── Part 1: 시장 지수 업데이트 ──
    if do_index:
        for ticker, db_code, name, naver_sym in MARKETS:
            print(f"📊 {name} 업데이트")

            # ① 최근 7일 데이터 삭제
            cur.execute(
                "SELECT COUNT(*) FROM index_data "
                "WHERE index_name = ? AND date >= ?",
                (db_code, cutoff),
            )
            del_count = cur.fetchone()[0]

            cur.execute(
                "DELETE FROM index_data "
                "WHERE index_name = ? AND date >= ?",
                (db_code, cutoff),
            )
            conn.commit()
            print(f"   🗑️  {cutoff} 이후 {del_count}건 삭제")

            # ② yfinance에서 다운로드
            fetch_start = (today - timedelta(days=CLEANUP_DAYS + 10)).strftime('%Y-%m-%d')
            fetch_end = (today + timedelta(days=1)).strftime('%Y-%m-%d')

            print(f"   📥 {cutoff} ~ {fetch_end} 다운로드 중...", end=' ', flush=True)

            try:
                df = yf.download(ticker, start=fetch_start, end=fetch_end, progress=False)
                if df.empty:
                    print("⚠️  yfinance 데이터 없음")
                    df = pd.DataFrame()
                else:
                    df = _prepare_df(df, ticker, db_code)
                    # cutoff 이전 데이터는 등락률 계산용이었으므로 제외
                    df = df[df['date'] >= cutoff]

                # ③ 네이버 금융 fallback — yfinance에 없는 최신 데이터 보충
                yf_max_date = df['date'].max() if len(df) > 0 else cutoff
                naver_df = _fetch_naver_index(naver_sym, count=15)
                if len(naver_df) > 0:
                    naver_df = naver_df[naver_df['date'] >= cutoff]
                    # yfinance에 없는 날짜만 추출
                    naver_new = naver_df[naver_df['date'] > yf_max_date].copy()
                    if len(naver_new) > 0:
                        naver_new['index_name'] = db_code
                        df = pd.concat([df, naver_new], ignore_index=True)
                        print(f"(+네이버 {len(naver_new)}일 보충) ", end='')

                    # yfinance 데이터가 비어있으면 네이버 데이터로 전체 대체
                    if yf_max_date == cutoff and len(naver_df) > 0:
                        naver_df['index_name'] = db_code
                        df = naver_df
                        print(f"(네이버 {len(df)}일 대체) ", end='')

                inserted = 0
                for _, r in df.iterrows():
                    try:
                        cur.execute(
                            "INSERT INTO index_data "
                            "(date, index_name, open, high, low, close, volume, change) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            (r['date'], r['index_name'],
                             float(r['open']), float(r['high']),
                             float(r['low']),  float(r['close']),
                             float(r['volume']), float(r['change'])),
                        )
                        inserted += 1
                    except sqlite3.IntegrityError:
                        pass

                conn.commit()
                total_inserted += inserted

                mn, mx, cnt = _db_stats(cur, db_code)
                print(f"✅ {inserted}건 저장")
                print(f"   📅 DB 기간: {mn} ~ {mx}  (총 {cnt:,}건)")

            except Exception as e:
                print(f"❌ 실패: {e}")

            print()

    # ── Part 2: 종목 데이터 업데이트 (보통주/우선주) ──
    if do_stock:
        print("📊 종목 데이터 업데이트 ({0}쌍, {1}종목)".format(len(STOCK_PAIRS), len(STOCK_PAIRS) * 2))
        stock_inserted, stock_success = update_stock_data(conn, cur, full=full_stock)
        total_inserted += stock_inserted
        print(f"   ✅ {stock_success}/{len(STOCK_PAIRS)*2}종목 성공, {stock_inserted:,}건 저장")

        # 종목 DB 통계
        for pair in STOCK_PAIRS:
            common, preferred, name = pair[0], pair[1], pair[2]
            cmn, cmx, ccnt = _stock_db_stats(cur, common)
            pmn, pmx, pcnt = _stock_db_stats(cur, preferred)
            if cmn:
                print(f"   {name}: 보통주 {ccnt:,}건({cmn}~{cmx}), 우선주 {pcnt:,}건")
        print()

    # 최종 요약
    print("=" * 60)
    print("📊 최종 DB 통계")
    print("=" * 60)
    if do_index:
        for _, db_code, name, _ in MARKETS:
            mn, mx, cnt = _db_stats(cur, db_code)
            if mn:
                print(f"  {name}: {cnt:,}건  |  {mn} ~ {mx}  ({int(mx[:4])-int(mn[:4])+1}년)")
            else:
                print(f"  {name}: 데이터 없음")
    if do_stock:
        cur.execute("SELECT COUNT(DISTINCT stock_code), COUNT(*) FROM stock_data")
        n_codes, n_rows = cur.fetchone()
        cur.execute("SELECT MIN(date), MAX(date) FROM stock_data")
        smin, smax = cur.fetchone()
        if smin:
            print(f"  종목: {n_codes}종목, {n_rows:,}건  |  {smin} ~ {smax}")
    print("=" * 60)
    conn.close()
    print(f"\n✅ 업데이트 완료! {total_inserted:,}건 갱신")


if __name__ == '__main__':
    update_market_data()
