"""
데이터 로딩 & 검증 계층

- market_data.db 의 index_data(OHLCV) + investor_data.db 의 investor_daily(수급) 병합
- 날짜 중복/결측/이상치 검사 (자동 삭제하지 않고 로그로만 보고)
- Look-ahead 방지를 위해 원본은 시간순 정렬만 하고 어떤 스케일링도 하지 않는다.
"""

import os
import sqlite3
import pandas as pd
import numpy as np

import config as C


def _read_index(market: str) -> pd.DataFrame:
    m = C.MARKETS[market]
    with sqlite3.connect(C.MARKET_DB) as conn:
        df = pd.read_sql_query(
            "SELECT date, open, high, low, close, volume "
            "FROM index_data WHERE index_name = ? ORDER BY date",
            conn, params=(m['index_name'],), parse_dates=['date'],
        )
    return df


def _read_investor(market: str) -> pd.DataFrame:
    if not os.path.exists(C.INVESTOR_DB):
        return pd.DataFrame(columns=['date', 'foreign_net', 'inst_net', 'indiv_net'])
    m = C.MARKETS[market]
    with sqlite3.connect(C.INVESTOR_DB) as conn:
        df = pd.read_sql_query(
            f"SELECT date, {C.COL['foreign']} AS foreign_net, "
            f"{C.COL['institution']} AS inst_net, {C.COL['individual']} AS indiv_net "
            "FROM investor_daily WHERE market = ? ORDER BY date",
            conn, params=(m['investor_code'],), parse_dates=['date'],
        )
    return df


def validate(df: pd.DataFrame, market: str) -> list[str]:
    """데이터 품질 검사. 문제를 자동 수정하지 않고 경고 목록만 반환한다."""
    warns = []
    dup = df['date'].duplicated().sum()
    if dup:
        warns.append(f"[{market}] 중복 날짜 {dup}건")
    for col in ('open', 'high', 'low', 'close'):
        n0 = int((df[col] <= 0).sum())
        if n0:
            warns.append(f"[{market}] {col}<=0 {n0}건")
    nvol0 = int((df['volume'] <= 0).sum())
    if nvol0:
        warns.append(f"[{market}] 거래량 0 {nvol0}건")
    # 일간 변동 ±25% 초과 = 이상치 후보
    chg = df['close'].pct_change().abs()
    nout = int((chg > 0.25).sum())
    if nout:
        warns.append(f"[{market}] 일간변동±25%초과 {nout}건 (이상치 후보)")
    nnull = int(df[['open', 'high', 'low', 'close']].isna().sum().sum())
    if nnull:
        warns.append(f"[{market}] 가격 결측 {nnull}건")
    # 수급 결측
    if 'foreign_net' in df.columns:
        first_flow = df['foreign_net'].first_valid_index()
        if first_flow is not None:
            cover = df.loc[first_flow, 'date']
            warns.append(f"[{market}] 수급데이터 시작일 {cover.date()} (이전 구간은 수급 Feature 결측)")
    return warns


def load_market(market: str) -> pd.DataFrame:
    """
    시장별 원본 데이터(OHLCV + 수급)를 날짜 인덱스로 반환.
    반환 컬럼: open, high, low, close, volume, foreign_net, inst_net, indiv_net
    """
    price = _read_index(market)
    flow = _read_investor(market)

    df = price.merge(flow, on='date', how='left')
    df = df.drop_duplicates('date').sort_values('date').reset_index(drop=True)
    df = df.set_index('date')
    return df


def load_all() -> dict[str, pd.DataFrame]:
    """모든 시장 로드 + 검증 경고 반환."""
    data, warnings = {}, []
    for market in C.MARKETS:
        df = load_market(market)
        warnings += validate(df.reset_index(), market)
        data[market] = df
    return data, warnings
