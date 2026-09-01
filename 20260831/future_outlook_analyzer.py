# -*- coding: utf-8 -*-
"""현재와 유사한 과거 국면을 이용한 다중 시간축 시장 전망."""

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


HORIZONS = [
    (1, '1일'), (2, '2일'), (3, '3일'), (4, '4일'), (5, '5일/1주'),
    (10, '2주'), (15, '3주'), (20, '4주'), (25, '5주'),
    (30, '6주'), (35, '7주'), (40, '8주'), (60, '3개월'), (120, '6개월'),
]


class FutureOutlookAnalyzer:
    """MDD·기술지표·수급이 비슷한 과거 국면 이후의 흐름을 추정한다."""

    FEATURE_COLUMNS = [
        'ret_1d', 'ret_5d', 'ret_20d', 'ret_60d', 'mdd_250d',
        'ma20_gap', 'ma60_gap', 'rsi', 'stoch', 'mfi', 'cci_scaled',
        'bb_position', 'adx_scaled', 'macd_scaled', 'atr_scaled',
        'volume_scaled', 'foreign_percentile', 'foreign_5d_scaled',
        'foreign_20d_scaled',
    ]

    FEATURE_WEIGHTS = np.array([
        0.8, 1.1, 1.2, 1.0, 1.5,
        1.0, 1.2, 0.9, 0.7, 0.7, 0.6,
        0.8, 1.0, 0.8, 0.8,
        0.5, 1.2, 1.0, 1.1,
    ])

    def __init__(self, df: pd.DataFrame, max_analogs: int = 35,
                 min_spacing: int = 40):
        self.df = df.copy()
        self.max_analogs = max_analogs
        self.min_spacing = min_spacing
        self.features = self._build_features(self.df)

    def analyze(self) -> Dict:
        """현재 시점 전망과 과거 시점 워크포워드 검증 결과를 반환한다."""
        target_pos = len(self.df) - 1
        analogs = self._find_analogs(target_pos, require_known_horizon=120)
        if len(analogs) < 10:
            return {
                'available': False,
                'reason': f'독립 유사국면 표본 부족 ({len(analogs)}개)',
            }

        forecasts = self._summarize_outcomes(target_pos, analogs)
        validation = self._walk_forward_validate()
        return {
            'available': True,
            'as_of': self.df.index[target_pos],
            'current_price': float(self.df['close'].iloc[target_pos]),
            'analog_count': len(analogs),
            'analogs': [
                {
                    'date': self.df.index[pos],
                    'distance': distance,
                    'mdd': float(self.features['mdd_250d'].iloc[pos] * 100),
                    'ret_20d': float(self.features['ret_20d'].iloc[pos] * 100),
                }
                for pos, distance in analogs[:10]
            ],
            'forecasts': forecasts,
            'validation': validation,
            'method': '19개 상태변수 표준화 거리 + 독립 유사국면 가중 분포',
        }

    @staticmethod
    def _build_features(df: pd.DataFrame) -> pd.DataFrame:
        close = df['close'].astype(float)
        rolling_high = close.rolling(250, min_periods=60).max()
        bb_range = (df['BB_upper'] - df['BB_lower']).replace(0, np.nan)
        flow_scale = df.get('foreign_net', pd.Series(0.0, index=df.index)).abs().rolling(
            250, min_periods=30
        ).median().replace(0, np.nan)

        features = pd.DataFrame(index=df.index)
        features['ret_1d'] = close.pct_change(1)
        features['ret_5d'] = close.pct_change(5)
        features['ret_20d'] = close.pct_change(20)
        features['ret_60d'] = close.pct_change(60)
        features['mdd_250d'] = close / rolling_high - 1
        features['ma20_gap'] = close / df['MA20'] - 1
        features['ma60_gap'] = close / df['MA60'] - 1
        features['rsi'] = df['RSI'] / 100
        features['stoch'] = df['Stoch_K'] / 100
        features['mfi'] = df['MFI'] / 100
        features['cci_scaled'] = df['CCI'].clip(-300, 300) / 300
        features['bb_position'] = ((close - df['BB_lower']) / bb_range).clip(-0.5, 1.5)
        features['adx_scaled'] = df['ADX'].clip(0, 80) / 80
        features['macd_scaled'] = (df['MACD_Hist'] / close).clip(-0.1, 0.1) * 10
        features['atr_scaled'] = df['ATR_pct'].clip(0, 15) / 15
        features['volume_scaled'] = df['Volume_Ratio'].clip(0, 4) / 4
        features['foreign_percentile'] = df.get(
            'foreign_roll_pct', pd.Series(np.nan, index=df.index)
        ) / 100
        features['foreign_5d_scaled'] = (
            df.get('foreign_5d_cum', pd.Series(np.nan, index=df.index)) /
            (flow_scale * 5)
        ).clip(-3, 3) / 3
        features['foreign_20d_scaled'] = (
            df.get('foreign_20d_cum', pd.Series(np.nan, index=df.index)) /
            (flow_scale * 20)
        ).clip(-3, 3) / 3
        return features.replace([np.inf, -np.inf], np.nan)

    def _find_analogs(self, target_pos: int, require_known_horizon: int,
                      candidate_end: Optional[int] = None) -> List[Tuple[int, float]]:
        candidate_end = (target_pos - require_known_horizon if candidate_end is None
                         else min(candidate_end, target_pos - require_known_horizon))
        if candidate_end < 500:
            return []

        columns = self.FEATURE_COLUMNS
        target = self.features.iloc[target_pos][columns]
        candidates = self.features.iloc[:candidate_end + 1][columns]
        valid_columns = target.notna() & (candidates.notna().mean() >= 0.6)
        columns = list(target.index[valid_columns])
        if len(columns) < 12:
            return []

        candidates = candidates[columns].dropna()
        if len(candidates) < 300:
            return []
        target_values = target[columns].to_numpy(dtype=float)
        values = candidates.to_numpy(dtype=float)
        scale = np.nanpercentile(values, 75, axis=0) - np.nanpercentile(values, 25, axis=0)
        scale = np.where(scale < 1e-8, 1.0, scale)
        weight_indices = [self.FEATURE_COLUMNS.index(column) for column in columns]
        weights = self.FEATURE_WEIGHTS[weight_indices]
        distances = np.sqrt(np.average(((values - target_values) / scale) ** 2,
                                       axis=1, weights=weights))
        ranked = sorted(zip(candidates.index, distances), key=lambda item: item[1])

        positions = {date: pos for pos, date in enumerate(self.df.index)}
        selected = []
        for date, distance in ranked:
            pos = positions[date]
            if all(abs(pos - chosen_pos) >= self.min_spacing for chosen_pos, _ in selected):
                selected.append((pos, float(distance)))
            if len(selected) >= self.max_analogs:
                break
        return selected

    @staticmethod
    def _weighted_quantile(values: np.ndarray, weights: np.ndarray,
                           quantile: float) -> float:
        order = np.argsort(values)
        sorted_values = values[order]
        sorted_weights = weights[order]
        cumulative = np.cumsum(sorted_weights) - 0.5 * sorted_weights
        cumulative /= sorted_weights.sum()
        return float(np.interp(quantile, cumulative, sorted_values))

    def _summarize_outcomes(self, target_pos: int,
                            analogs: List[Tuple[int, float]]) -> List[Dict]:
        current_price = float(self.df['close'].iloc[target_pos])
        positions = np.array([pos for pos, _ in analogs], dtype=int)
        distances = np.array([distance for _, distance in analogs], dtype=float)
        weights = 1 / np.maximum(distances, 0.05) ** 2
        close = self.df['close'].to_numpy(dtype=float)
        forecasts = []

        for days, label in HORIZONS:
            outcomes = close[positions + days] / close[positions] - 1
            mean = float(np.average(outcomes, weights=weights))
            median = self._weighted_quantile(outcomes, weights, 0.50)
            lower = self._weighted_quantile(outcomes, weights, 0.25)
            upper = self._weighted_quantile(outcomes, weights, 0.75)
            up_probability = float(np.average(outcomes > 0, weights=weights) * 100)
            forecasts.append({
                'days': days,
                'label': label,
                'mean_return': mean * 100,
                'median_return': median * 100,
                'lower_return': lower * 100,
                'upper_return': upper * 100,
                'up_probability': up_probability,
                'target_price': current_price * (1 + median),
            })
        return forecasts

    def _walk_forward_validate(self) -> Dict:
        """각 검증 시점에서 그때 알 수 있었던 과거만 사용한다."""
        max_horizon = 120
        last_test_pos = len(self.df) - max_horizon - 1
        first_test_pos = max(800, last_test_pos - 21 * 30)
        test_positions = list(range(first_test_pos, last_test_pos + 1, 21))
        horizons = [5, 20, 60, 120]
        results = {days: {'predicted': [], 'actual': []} for days in horizons}
        close = self.df['close'].to_numpy(dtype=float)

        for target_pos in test_positions:
            analogs = self._find_analogs(target_pos, require_known_horizon=max_horizon)
            if len(analogs) < 10:
                continue
            forecast_map = {
                item['days']: item for item in self._summarize_outcomes(target_pos, analogs)
            }
            for days in horizons:
                results[days]['predicted'].append(forecast_map[days]['median_return'])
                actual = (close[target_pos + days] / close[target_pos] - 1) * 100
                results[days]['actual'].append(float(actual))

        metrics = {}
        for days in horizons:
            predicted = np.array(results[days]['predicted'])
            actual = np.array(results[days]['actual'])
            if len(actual) == 0:
                continue
            metrics[days] = {
                'samples': len(actual),
                'direction_accuracy': float(np.mean(np.sign(predicted) == np.sign(actual)) * 100),
                'mae': float(np.mean(np.abs(predicted - actual))),
            }
        return metrics