"""
데이터 로더 모듈
- market_data.db에서 코스피/코스닥 데이터 로드
- 기술적 지표 계산
"""

import os
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataLoader:
    """시장 데이터 로더"""

    def __init__(self, db_path: str):
        """
        Args:
            db_path: market_data.db 파일 경로
        """
        self.db_path = db_path

        if not os.path.exists(db_path):
            raise FileNotFoundError(f"데이터베이스 파일을 찾을 수 없습니다: {db_path}")

    def load_market_data(self, market: str = 'kospi', days: int = None) -> pd.DataFrame:
        """
        시장 데이터 로드

        Args:
            market: 'kospi' 또는 'kosdaq'
            days: 로드할 일수 (None이면 전체)

        Returns:
            DataFrame with columns: date, open, high, low, close, volume
        """
        # index_name 매핑
        index_name = 'KS11' if market.lower() == 'kospi' else 'KQ11'

        try:
            conn = sqlite3.connect(self.db_path)

            query = f"SELECT * FROM index_data WHERE index_name = '{index_name}' ORDER BY date"
            df = pd.read_sql_query(query, conn)
            conn.close()

            # 날짜 인덱스 설정
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)

            # 컬럼명 정리
            df.columns = [col.lower() for col in df.columns]

            if days:
                df = df.tail(days)

            logger.info(f"{market.upper()} 데이터 로드: {len(df):,}건")
            return df

        except Exception as e:
            logger.error(f"데이터 로드 실패: {e}")
            raise

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        기술적 지표 계산

        Args:
            df: OHLCV 데이터프레임

        Returns:
            지표가 추가된 데이터프레임
        """
        df = df.copy()

        # 이동평균선(다양한 기간)
        for period in [5, 10, 20, 40, 60, 80, 100, 120]:
            df[f'MA{period}'] = df['close'].rolling(window=period).mean()

        # RSI (14일)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        # Stochastic
        low_14 = df['low'].rolling(window=14).min()
        high_14 = df['high'].rolling(window=14).max()
        df['Stoch_K'] = 100 * (df['close'] - low_14) / (high_14 - low_14)
        df['Stoch_D'] = df['Stoch_K'].rolling(window=3).mean()

        # MACD
        exp12 = df['close'].ewm(span=12, adjust=False).mean()
        exp26 = df['close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp12 - exp26
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

        # Bollinger Bands
        df['BB_middle'] = df['close'].rolling(window=20).mean()
        std = df['close'].rolling(window=20).std()
        df['BB_upper'] = df['BB_middle'] + (std * 2)
        df['BB_lower'] = df['BB_middle'] - (std * 2)
        df['BB_width'] = (df['BB_upper'] - df['BB_lower']) / df['BB_middle'] * 100

        # MFI (Money Flow Index)
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        money_flow = typical_price * df['volume']

        positive_flow = money_flow.where(typical_price > typical_price.shift(1), 0)
        negative_flow = money_flow.where(typical_price < typical_price.shift(1), 0)

        positive_mf = positive_flow.rolling(window=14).sum()
        negative_mf = negative_flow.rolling(window=14).sum()

        mfi_ratio = positive_mf / negative_mf
        df['MFI'] = 100 - (100 / (1 + mfi_ratio))
        
        # CCI (Commodity Channel Index)
        tp = (df['high'] + df['low'] + df['close']) / 3
        sma_tp = tp.rolling(window=20).mean()
        mean_dev = tp.rolling(window=20).apply(lambda x: np.abs(x - x.mean()).mean())
        df['CCI'] = (tp - sma_tp) / (0.015 * mean_dev)

        # ATR (Average True Range)
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['ATR'] = true_range.rolling(window=14).mean()
        df['ATR_pct'] = df['ATR'] / df['close'] * 100

        # ADX
        df['ADX'] = self._calculate_adx(df)

        # OBV (On-Balance Volume)
        df['OBV'] = (np.sign(df['close'].diff()) * df['volume']).fillna(0).cumsum()
        df['OBV_MA20'] = df['OBV'].rolling(window=20).mean()

        # DMI (+DI, -DI)
        df['+DI'], df['-DI'] = self._calculate_dmi(df)

        # Volume Ratio (거래량 비율)
        df['Volume_MA20'] = df['volume'].rolling(window=20).mean()
        df['Volume_Ratio'] = df['volume'] / df['Volume_MA20']

        # VWAP (Volume Weighted Average Price) - 20일 기준
        df['VWAP'] = (df['close'] * df['volume']).rolling(window=20).sum() / df['volume'].rolling(window=20).sum()
        df['VWAP_ratio'] = df['close'] / df['VWAP']

        return df

    def _calculate_adx(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """ADX 계산"""
        high = df['high']
        low = df['low']
        close = df['close']

        plus_dm = high.diff()
        minus_dm = low.diff().abs() * -1

        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm > 0] = 0
        minus_dm = minus_dm.abs()

        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs()
        ], axis=1).max(axis=1)

        atr = tr.rolling(window=period).mean()
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)

        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()

        return adx

    def _calculate_dmi(self, df: pd.DataFrame, period: int = 14):
        """DMI (+DI, -DI) 계산"""
        high = df['high']
        low = df['low']
        close = df['close']

        plus_dm = high.diff()
        minus_dm = -low.diff()

        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0

        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs()
        ], axis=1).max(axis=1)

        atr = tr.rolling(window=period).mean()
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)

        return plus_di, minus_di

    def calculate_disparity(self, df: pd.DataFrame, ma_period: int) -> pd.Series:
        """
        이격도 계산

        Args:
            df: 데이터프레임
            ma_period: 이동평균 기간

        Returns:
            이격도 시리즈(%)
        """
        ma_col = f'MA{ma_period}'

        if ma_col not in df.columns:
            df[ma_col] = df['close'].rolling(window=ma_period).mean()

        return (df['close'] / df[ma_col]) * 100


def load_data(market: str = 'kospi', days: int = None, db_path: str = None) -> pd.DataFrame:
    """
    간편 데이터 로드 함수

    Args:
        market: 'kospi' 또는 'kosdaq'
        days: 로드할 일수
        db_path: DB 경로 (None이면 기본 경로 사용)

    Returns:
        지표가 계산된 데이터프레임
    """
    if db_path is None:
        from config import DB_PATH
        db_path = DB_PATH
        
    if db_path is None:
        raise FileNotFoundError(
            "데이터베이스를 찾을 수 없습니다.\n"
            "다음 중 하나의 경로에 market_data.db가 있어야 합니다:\n"
            "1. ./data/market_data.db\n"
            "2. D:\\Back_Test\\MarketTop_20260109\\data\\market_data.db"
        )

    loader = DataLoader(db_path)
    df = loader.load_market_data(market, days)
    df = loader.calculate_indicators(df)

    return df


if __name__ == '__main__':
    # 테스트
    from config import DB_PATH

    loader = DataLoader(DB_PATH)

    # 코스피 데이터 로드
    df_kospi = loader.load_market_data('kospi')
    df_kospi = loader.calculate_indicators(df_kospi)

    print(f"\n코스피 데이터:")
    print(f"  기간: {df_kospi.index[0]} ~ {df_kospi.index[-1]}")
    print(f"  현재가: {df_kospi['close'].iloc[-1]:,.2f}")
    print(f"  RSI: {df_kospi['RSI'].iloc[-1]:.1f}")
    print(f"  Stochastic K: {df_kospi['Stoch_K'].iloc[-1]:.1f}")

    # 코스닥 데이터 로드
    df_kosdaq = loader.load_market_data('kosdaq')
    df_kosdaq = loader.calculate_indicators(df_kosdaq)

    print(f"\n코스닥 데이터:")
    print(f"  기간: {df_kosdaq.index[0]} ~ {df_kosdaq.index[-1]}")
    print(f"  현재가: {df_kosdaq['close'].iloc[-1]:,.2f}")
    print(f"  RSI: {df_kosdaq['RSI'].iloc[-1]:.1f}")
