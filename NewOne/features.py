"""
Feature Engineering (Look-ahead 안전)

모든 지표는 rolling/backward 연산만 사용한다.
어떤 전역(fit-on-full) 스케일링도 하지 않으므로, 각 날짜 t의 Feature 값은
t시점까지의 데이터만으로 결정된다 → 미래참조(Look-ahead) 없음.

수급(외국인/기관)은 시장규모 변화 영향을 줄이기 위해 절대금액이 아닌
rolling z-score(상대적 수급 강도)를 핵심 Feature로 사용한다.
"""

import numpy as np
import pandas as pd


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)


def _rolling_mdd(close: pd.Series, window: int) -> pd.Series:
    roll_max = close.rolling(window, min_periods=max(10, window // 5)).max()
    return (close / roll_max - 1.0) * 100.0  # 음수(%)


def _rolling_rally(close: pd.Series, window: int) -> pd.Series:
    """직전 window 저점 대비 반등률(%). 20% 룰의 강세 판정에 사용."""
    roll_min = close.rolling(window, min_periods=max(10, window // 5)).min()
    return (close / roll_min - 1.0) * 100.0  # 양수(%)


def _wilder(s: pd.Series, period: int) -> pd.Series:
    """Wilder 평활(RMA) = ewm(alpha=1/period)."""
    return s.ewm(alpha=1.0 / period, adjust=False).mean()


def _adx(high: pd.Series, low: pd.Series, close: pd.Series,
         period: int = 14) -> pd.DataFrame:
    """Wilder(1978) ADX/DMI — 추세의 '방향'이 아니라 '강도'를 측정.
    ADX<20 무추세(횡보), 20~25 추세 형성, >=25 추세, >=40 강한 추세."""
    up = high.diff()
    down = -low.diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low),
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = _wilder(tr, period).replace(0, np.nan)
    plus_di = 100.0 * _wilder(pd.Series(plus_dm, index=high.index), period) / atr
    minus_di = 100.0 * _wilder(pd.Series(minus_dm, index=high.index), period) / atr
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = _wilder(dx.fillna(0), period)
    return pd.DataFrame({'plus_di14': plus_di, 'minus_di14': minus_di, 'adx14': adx})


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    입력: open/high/low/close/volume/foreign_net/inst_net/indiv_net (날짜 인덱스)
    출력: 원본 + 모든 Feature 컬럼
    """
    out = df.copy()
    close = out['close']

    # ── 이동평균 & 이격도 & 기울기 ──
    for p in (5, 10, 20, 60, 120, 200):
        out[f'ma{p}'] = close.rolling(p).mean()
    for p in (20, 60, 120):
        out[f'disp{p}'] = close / out[f'ma{p}'] * 100.0
    out['ma20_slope'] = out['ma20'].pct_change(5) * 100.0
    out['ma200_slope'] = out['ma200'].pct_change(20) * 100.0   # 장기추세 방향(Faber)
    # 정배열 점수 (MA5>20>60>120)
    out['ma_align'] = (
        (out['ma5'] > out['ma20']).astype(int)
        + (out['ma20'] > out['ma60']).astype(int)
        + (out['ma60'] > out['ma120']).astype(int)
    )

    # ── 수익률 ──
    for p in (1, 3, 5, 10, 20, 60, 120, 252):
        out[f'ret{p}'] = close.pct_change(p) * 100.0

    # ── RSI / MACD ──
    out['rsi14'] = _rsi(close, 14)
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    out['macd'] = ema12 - ema26
    out['macd_signal'] = out['macd'].ewm(span=9, adjust=False).mean()
    out['macd_hist'] = out['macd'] - out['macd_signal']
    out['macd_hist_n'] = out['macd_hist'] / close * 100.0   # 가격정규화
    out['macd_up'] = (out['macd'] > out['macd_signal']).astype(int)

    # ── ADX / DMI (Wilder 1978) : 추세 강도 → 횡보 vs 추세 판별 ──
    out = out.join(_adx(out['high'], out['low'], close, 14))

    # ── 변동성 ──
    ret1 = close.pct_change()
    for p in (5, 20, 60, 120):
        out[f'realvol{p}'] = ret1.rolling(p).std() * np.sqrt(252) * 100.0
    out['vol20'] = out['realvol20']
    out['vol_pctile'] = out['vol20'].rolling(252, min_periods=60).rank(pct=True) * 100.0

    # ── MDD & 반등률 (20% 강세/약세 룰용) ──
    for w in (20, 60, 120, 252):
        out[f'mdd{w}'] = _rolling_mdd(close, w)
    out['rally252'] = _rolling_rally(close, 252)

    # ── 거래량 ──
    out['vol_ma20'] = out['volume'].rolling(20).mean()
    out['vol_ratio'] = out['volume'] / out['vol_ma20'].replace(0, np.nan)
    out['vol_z'] = (
        (out['volume'] - out['vol_ma20'])
        / out['volume'].rolling(60).std().replace(0, np.nan)
    )

    # ── 수급 (외국인/기관) : 누적 + rolling z-score ──
    for tag, col in (('foreign', 'foreign_net'), ('inst', 'inst_net')):
        if col not in out.columns:
            continue
        s = out[col]
        for p in (5, 20, 60, 120):
            csum = s.rolling(p).sum()
            out[f'{tag}_sum{p}'] = csum
            mu = csum.rolling(252, min_periods=60).mean()
            sd = csum.rolling(252, min_periods=60).std().replace(0, np.nan)
            out[f'{tag}_z{p}'] = (csum - mu) / sd
        # 연속 순매수/순매도 일수
        sign = np.sign(s.fillna(0))
        streak = sign.groupby((sign != sign.shift()).cumsum()).cumcount() + 1
        out[f'{tag}_streak'] = streak * sign

    return out


def add_relative_strength(feats: dict[str, pd.DataFrame]) -> None:
    """KOSPI/KOSDAQ 상대강도(20일 수익률 차)를 두 프레임에 추가한다."""
    if 'KOSPI' not in feats or 'KOSDAQ' not in feats:
        return
    a, b = feats['KOSPI'], feats['KOSDAQ']
    rs = (a['ret20'] - b['ret20'])
    a['rs_20'] = rs           # 코스피 기준 (양수=코스피 강세)
    b['rs_20'] = -rs          # 코스닥 기준
