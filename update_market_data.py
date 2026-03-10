"""
[스크립트 2] DB 일일 업데이트용
- 최근 7일 데이터를 삭제 후 재수집 (명절·연말 등 비정상 데이터 보정)
- 삭제된 날짜 ~ 오늘까지 yfinance로 다운로드하여 갱신
- 한글 사용자명 경로의 SSL 인증서 문제 자동 우회

사용법:
    python update_market_data.py
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

MARKETS = [
    ('^KS11', 'KS11', '코스피'),
    ('^KQ11', 'KQ11', '코스닥'),
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


def _db_stats(cursor, db_code):
    cursor.execute(
        "SELECT MIN(date), MAX(date), COUNT(*) "
        "FROM index_data WHERE index_name = ?", (db_code,),
    )
    return cursor.fetchone()


def update_market_data():
    """최근 7일 삭제 → 삭제 시작일~오늘 재수집"""
    today = datetime.now()
    today_str = today.strftime('%Y-%m-%d')
    cutoff = (today - timedelta(days=CLEANUP_DAYS)).strftime('%Y-%m-%d')

    print("=" * 60)
    print("  DB 업데이트  (최근 7일 재수집)")
    print("=" * 60)
    print(f"DB : {DB_PATH}")
    print(f"오늘: {today_str}  |  삭제 기준일: {cutoff}")
    print()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    total_inserted = 0

    for ticker, db_code, name in MARKETS:
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

        # ② 삭제 기준일 ~ 오늘 데이터 다운로드
        # 등락률 계산을 위해 며칠 여유를 두고 다운로드
        fetch_start = (today - timedelta(days=CLEANUP_DAYS + 10)).strftime('%Y-%m-%d')
        # yfinance end는 exclusive이므로 내일 날짜를 지정해야 오늘 데이터도 포함
        fetch_end = (today + timedelta(days=1)).strftime('%Y-%m-%d')

        print(f"   📥 {cutoff} ~ {fetch_end} 다운로드 중...", end=' ', flush=True)

        try:
            df = yf.download(ticker, start=fetch_start, end=fetch_end, progress=False)
            if df.empty:
                print("⚠️  데이터 없음")
                continue

            df = _prepare_df(df, ticker, db_code)

            # cutoff 이전 데이터는 등락률 계산용이었으므로 제외
            df = df[df['date'] >= cutoff]

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
    print(f"\n✅ 업데이트 완료! {total_inserted:,}건 갱신")


if __name__ == '__main__':
    update_market_data()
