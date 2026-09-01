"""
DB 업데이트 (프로젝트 내부 자체 완결형)

대상 DB: NewOne/data/market_data.db (index_data) + investor_data.db (investor_daily)

- 지수(코스피/코스닥) 일봉: yfinance + 네이버금융 fallback 로 최근 구간 재수집
- 투자자 수급: pykrx 가 설치돼 있으면 최근 구간 갱신, 없으면 안내 후 건너뜀
  (수급 갱신을 원하면:  pip install pykrx)

사용법:
    python update_data.py           # 지수 + 수급(가능하면) 갱신
    python update_data.py --index   # 지수만
    python update_data.py --flow    # 수급만
"""

import os
import sys
import shutil
import sqlite3
import re
import pandas as pd
from datetime import datetime, timedelta

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

import config as C

# ── SSL 인증서 한글 경로 우회 ──────────────────────────
try:
    import certifi
    _cert_src = certifi.where()
    _cert_dst = r'C:\temp\cacert.pem'
    if not os.path.exists(_cert_dst) or os.path.getmtime(_cert_src) > os.path.getmtime(_cert_dst):
        os.makedirs(os.path.dirname(_cert_dst), exist_ok=True)
        shutil.copy2(_cert_src, _cert_dst)
    os.environ['CURL_CA_BUNDLE'] = _cert_dst
    os.environ['SSL_CERT_FILE'] = _cert_dst
    os.environ['REQUESTS_CA_BUNDLE'] = _cert_dst
except Exception:
    pass

CLEANUP_DAYS = 7

# (yfinance 티커, DB코드, 이름, 네이버심볼, investor_market)
INDEX_SPECS = [
    ('^KS11', 'KS11', '코스피', 'KOSPI', '01'),
    ('^KQ11', 'KQ11', '코스닥', 'KOSDAQ', '02'),
]


# ──────────────────────────── 지수 ────────────────────────────
def _prepare_df(df, ticker, db_code):
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
    import requests
    url = 'https://fchart.stock.naver.com/sise.nhn'
    params = {'symbol': naver_symbol, 'timeframe': 'day', 'count': count, 'requestType': 0}
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        rows = []
        for item in re.findall(r'data="([^"]+)"', resp.text):
            p = item.split('|')
            if len(p) >= 6:
                rows.append({
                    'date': f"{p[0][:4]}-{p[0][4:6]}-{p[0][6:8]}",
                    'open': float(p[1]), 'high': float(p[2]),
                    'low': float(p[3]), 'close': float(p[4]), 'volume': float(p[5]),
                })
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df['change'] = df['close'].pct_change().fillna(0)
        return df
    except Exception as e:
        print(f"   (네이버 조회 실패: {e})")
        return pd.DataFrame()


def _ensure_index_table(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS index_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE NOT NULL,
            index_name VARCHAR(10) NOT NULL,
            open FLOAT, high FLOAT, low FLOAT, close FLOAT,
            volume FLOAT, change FLOAT,
            UNIQUE(date, index_name)
        )""")


def update_index():
    import yfinance as yf
    today = datetime.now()
    cutoff = (today - timedelta(days=CLEANUP_DAYS)).strftime('%Y-%m-%d')
    conn = sqlite3.connect(C.MARKET_DB)
    cur = conn.cursor()
    _ensure_index_table(cur)

    for ticker, db_code, name, naver_sym, _mk in INDEX_SPECS:
        print(f"[지수] {name} 갱신")
        cur.execute("DELETE FROM index_data WHERE index_name=? AND date>=?", (db_code, cutoff))
        conn.commit()

        start = (today - timedelta(days=CLEANUP_DAYS + 10)).strftime('%Y-%m-%d')
        end = (today + timedelta(days=1)).strftime('%Y-%m-%d')
        try:
            df = yf.download(ticker, start=start, end=end, progress=False)
            df = _prepare_df(df, ticker, db_code) if not df.empty else pd.DataFrame()
            if len(df):
                df = df[df['date'] >= cutoff]
            yf_max = df['date'].max() if len(df) else cutoff

            naver = _fetch_naver_index(naver_sym, count=15)
            if len(naver):
                naver = naver[naver['date'] >= cutoff]
                new = naver[naver['date'] > yf_max].copy()
                if len(new):
                    new['index_name'] = db_code
                    df = pd.concat([df, new], ignore_index=True)
                if (not len(df)) and len(naver):
                    naver['index_name'] = db_code
                    df = naver

            inserted = 0
            for _, r in df.iterrows():
                try:
                    cur.execute(
                        "INSERT INTO index_data (date, index_name, open, high, low, close, volume, change) "
                        "VALUES (?,?,?,?,?,?,?,?)",
                        (r['date'], r['index_name'], float(r['open']), float(r['high']),
                         float(r['low']), float(r['close']), float(r['volume']), float(r['change'])))
                    inserted += 1
                except sqlite3.IntegrityError:
                    pass
            conn.commit()
            mn, mx, cnt = cur.execute(
                "SELECT MIN(date), MAX(date), COUNT(*) FROM index_data WHERE index_name=?",
                (db_code,)).fetchone()
            print(f"   +{inserted}건 저장 | DB {mn}~{mx} (총 {cnt:,}건)")
        except Exception as e:
            print(f"   [실패] {e}")
    conn.close()


# ──────────────────────────── 수급 ────────────────────────────
def _ensure_investor_table(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS investor_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE NOT NULL,
            market VARCHAR(2) NOT NULL,
            individual FLOAT, foreign_ FLOAT, institution FLOAT,
            finance FLOAT, insurance FLOAT, trust FLOAT, bank FLOAT,
            other_finance FLOAT, pension FLOAT, other_corp FLOAT,
            UNIQUE(date, market)
        )""")


def update_investor():
    try:
        from pykrx import stock
    except Exception:
        print("[수급] pykrx 미설치 — 수급 데이터는 갱신하지 않고 기존 값을 유지합니다.")
        print("       (수급 자동 갱신을 원하면:  pip install pykrx)")
        return

    today = datetime.now()
    frm = (today - timedelta(days=CLEANUP_DAYS + 5)).strftime('%Y%m%d')
    to = today.strftime('%Y%m%d')
    conn = sqlite3.connect(C.INVESTOR_DB)
    cur = conn.cursor()
    _ensure_investor_table(cur)

    for name, mk, ticker in (('코스피', '01', 'KOSPI'), ('코스닥', '02', 'KOSDAQ')):
        print(f"[수급] {name} 갱신")
        try:
            # 시장 전체 투자자별 순매수(거래대금) 일별
            df = stock.get_market_trading_value_by_date(frm, to, ticker)
            if df is None or df.empty:
                print("   데이터 없음")
                continue
            colmap = {'개인': 'individual', '외국인': 'foreign_', '기관합계': 'institution'}
            inserted = 0
            for idx, row in df.iterrows():
                d = pd.Timestamp(idx).strftime('%Y-%m-%d')
                def _v(k):
                    return float(row[k]) / 1e8 if k in row and pd.notna(row[k]) else 0.0
                cur.execute("DELETE FROM investor_daily WHERE date=? AND market=?", (d, mk))
                cur.execute(
                    "INSERT INTO investor_daily (date, market, individual, foreign_, institution) "
                    "VALUES (?,?,?,?,?)",
                    (d, mk, _v('개인'), _v('외국인'), _v('기관합계')))
                inserted += 1
            conn.commit()
            print(f"   +{inserted}일 갱신")
        except Exception as e:
            print(f"   [건너뜀] pykrx 응답 처리 실패: {e}")
    conn.close()


def main():
    os.makedirs(C.DATA_DIR, exist_ok=True)
    do_index = '--flow' not in sys.argv
    do_flow = '--index' not in sys.argv
    print("=" * 56)
    print(f"  DB 업데이트  →  {C.DATA_DIR}")
    print("=" * 56)
    if do_index:
        update_index()
    if do_flow:
        update_investor()
    print("=" * 56)
    print("  업데이트 완료")


if __name__ == '__main__':
    main()
