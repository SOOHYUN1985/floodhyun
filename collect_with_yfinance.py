"""
[스크립트 1] 전체 역사 데이터 수집 (처음 세팅 / DB 초기화용)
- yfinance period='max' → Yahoo Finance 보유 전체 기간 다운로드
- 코스피: ~1997년부터, 코스닥: ~2000년부터
- 한글 사용자명 경로의 SSL 인증서 문제 자동 우회
- 이미 DB에 있는 날짜는 자동 스킵(중복 방지)

사용법:
    python collect_with_yfinance.py
"""

import os
import sys
import shutil
import sqlite3
import pandas as pd
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

MARKETS = [
    ('^KS11', 'KS11', '코스피'),
    ('^KQ11', 'KQ11', '코스닥'),
]


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


def _insert_rows(cursor, df):
    """INSERT OR IGNORE. 신규 건수 반환"""
    inserted = 0
    for _, r in df.iterrows():
        try:
            cursor.execute(
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
    return inserted


def _db_stats(cursor, db_code):
    cursor.execute(
        "SELECT MIN(date), MAX(date), COUNT(*) "
        "FROM index_data WHERE index_name = ?", (db_code,),
    )
    return cursor.fetchone()


def collect_full_history():
    print("=" * 60)
    print("  전체 역사 데이터 수집  (yfinance period='max')")
    print("=" * 60)
    print(f"DB : {DB_PATH}\n")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS index_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE NOT NULL, index_name VARCHAR(10) NOT NULL,
            open FLOAT, high FLOAT, low FLOAT,
            close FLOAT, volume FLOAT, change FLOAT,
            UNIQUE(date, index_name))
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_date ON index_data(date)")
    conn.commit()

    total = 0
    for ticker, db_code, name in MARKETS:
        print(f"📊 {name} ({ticker}) 전체 기간 다운로드 중...")
        try:
            df = yf.download(ticker, period='max', progress=False)
            if df.empty:
                print(f"   ⚠️  데이터 없음\n"); continue
            print(f"   수집: {len(df):,}행")
            df = _prepare_df(df, ticker, db_code)
            ins = _insert_rows(cur, df); conn.commit(); total += ins
            mn, mx, cnt = _db_stats(cur, db_code)
            print(f"   ✅ 신규 {ins:,}건 저장")
            print(f"   📅 DB 기간: {mn} ~ {mx}  (총 {cnt:,}건)\n")
        except Exception as e:
            print(f"   ❌ 실패: {e}\n")

    # 최종 요약
    print("=" * 60)
    print("📊 최종 DB 통계")
    print("=" * 60)
    for _, db_code, name in MARKETS:
        mn, mx, cnt = _db_stats(cur, db_code)
        if mn:
            print(f"  {name}: {cnt:,}건  |  {mn} ~ {mx}  ({int(mx[:4])-int(mn[:4])+1}년)")
        else:
            print(f"  {name}: 데이터 없음")
    print("=" * 60)
    conn.close()
    print(f"\n✅ 완료! 총 {total:,}건 신규 저장")


if __name__ == '__main__':
    collect_full_history()
