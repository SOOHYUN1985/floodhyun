"""
고점 판독 백테스터
- 상향돌파 매도 전략: 특정 조건 상향돌파 시 매도
- 하락조건 매도 전략: 상승 후 특정 하락 조건 충족 시 매도
- 5/10/15/20일 후 결과 분석
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from tqdm import tqdm
import logging

from config import BACKTEST_PARAMS

logger = logging.getLogger(__name__)


class PeakDetector:
    """고점 판독 백테스터"""
    
    def __init__(self, df: pd.DataFrame, trend_type: str = 'bull',
                 trend_labels: pd.Series = None):
        """
        Args:
            df: 지표가 계산된 데이터프레임
            trend_type: 'bull', 'sideways', 'bear' (현재 시점 추세)
            trend_labels: 날짜별 추세 레이블 시리즈 (백테스트에서 시점별 추세 반영)
        """
        self.df = df.copy()
        self.trend_type = trend_type
        self.trend_labels = trend_labels  # 날짜별 추세 ('bull'/'sideways'/'bear')
        self._trend_label_map = None
        if trend_labels is not None:
            self._trend_label_map = trend_labels.to_dict()
        self.strategies = []
        
        # 파라미터 설정
        self._setup_params()
    
    def _setup_params(self):
        """추세에 맞는 파라미터 설정"""
        params = BACKTEST_PARAMS
        
        if self.trend_type == 'bull':
            # 상승장: 높은 이격도, 높은 지표 임계값
            self.disparity_range = range(
                params['disparity_min'] + 5,  # 110%
                params['disparity_max'],
                params['disparity_step']
            )
        elif self.trend_type == 'bear':
            # 하락장: 낮은 이격도, 낮은 지표 임계값
            self.disparity_range = range(
                params['disparity_min'],
                params['disparity_max'] - 10,  # 140%
                params['disparity_step']
            )
        else:
            # 횡보장: 중간 범위
            self.disparity_range = range(
                params['disparity_min'],
                params['disparity_max'] - 5,
                params['disparity_step']
            )
        
        self.ma_range = range(
            params['ma_min'],
            params['ma_max'] + 1,
            params['ma_step']
        )
    
    def run_backtest(self) -> List[Dict]:
        """
        전체 백테스트 실행
        
        Returns:
            전략 리스트
        """
        self.strategies = []
        
        print(f"\n{'─'*60}")
        print(f"📈 고점 판독 백테스트 시작 ({self.trend_type.upper()} 시장)")
        print(f"{'─'*60}")
        
        # 1. 상향돌파 매도 전략
        print("\n1️⃣ 상향돌파 매도 전략 테스트...")
        self._test_breakout_strategies()
        
        # 2. 하락조건 매도 전략
        print("\n2️⃣ 하락조건 매도 전략 테스트...")
        self._test_reversal_strategies()
        
        print(f"\n✅ 총 {len(self.strategies)}개 전략 발견")
        
        return self.strategies
    
    def _test_breakout_strategies(self):
        """상향돌파 매도 전략 테스트"""
        params = BACKTEST_PARAMS
        test_count = 0
        
        # 이격도 + RSI 조합
        pbar = tqdm(list(self.disparity_range), desc="   이격도+지표", unit="disp")
        
        for disp in pbar:
            for ma_period in self.ma_range:
                # 이격도 계산
                ma_col = f'MA{ma_period}'
                if ma_col not in self.df.columns:
                    self.df[ma_col] = self.df['close'].rolling(window=ma_period).mean()
                
                self.df['disparity'] = (self.df['close'] / self.df[ma_col]) * 100
                
                # 이격도 + RSI
                for rsi_th in params['rsi_thresholds']:
                    signals = (
                        (self.df['disparity'] >= disp) &
                        (self.df['RSI'] >= rsi_th)
                    )
                    self._evaluate_strategy(
                        f"이격도{disp}(MA{ma_period}) + RSI{rsi_th}+",
                        signals, 'breakout', disp, ma_period
                    )
                    test_count += 1
                
                # 이격도 + Stochastic
                for stoch_th in params['stoch_thresholds']:
                    signals = (
                        (self.df['disparity'] >= disp) &
                        (self.df['Stoch_K'] >= stoch_th)
                    )
                    self._evaluate_strategy(
                        f"이격도{disp}(MA{ma_period}) + Stoch{stoch_th}+",
                        signals, 'breakout', disp, ma_period
                    )
                    test_count += 1
                
                # 이격도 + MFI
                for mfi_th in params['mfi_thresholds']:
                    signals = (
                        (self.df['disparity'] >= disp) &
                        (self.df['MFI'] >= mfi_th)
                    )
                    self._evaluate_strategy(
                        f"이격도{disp}(MA{ma_period}) + MFI{mfi_th}+",
                        signals, 'breakout', disp, ma_period
                    )
                    test_count += 1
                
                # 이격도 + Volume Ratio (새로운 지표)
                for vol_th in params.get('volume_ratio_thresholds', [1.5, 2.0, 2.5]):
                    if 'Volume_Ratio' in self.df.columns:
                        signals = (
                            (self.df['disparity'] >= disp) &
                            (self.df['Volume_Ratio'] >= vol_th)
                        )
                        self._evaluate_strategy(
                            f"이격도{disp}(MA{ma_period}) + 거래량{vol_th:.1f}배+",
                            signals, 'breakout', disp, ma_period
                        )
                        test_count += 1
            
            pbar.set_postfix({'tests': test_count, 'found': len(self.strategies)})
        
        # ============================================
        # 2. DMI 기반 상향돌파 전략 (새로운 전략)
        # ============================================
        if '+DI' in self.df.columns and '-DI' in self.df.columns:
            for dmi_th in params.get('dmi_thresholds', [25, 30, 35]):
                # +DI > -DI (상승 추세)
                dmi_bullish = self.df['+DI'] > self.df['-DI']
                
                for rsi_th in params['rsi_thresholds']:
                    signals = dmi_bullish & (self.df['+DI'] >= dmi_th) & (self.df['RSI'] >= rsi_th)
                    self._evaluate_strategy(
                        f"+DI{dmi_th}+ + RSI{rsi_th}+",
                        signals, 'breakout', None, None
                    )
                    test_count += 1
        
        # ============================================
        # 3. VWAP 기반 상향돌파 전략 (새로운 전략)
        # ============================================
        if 'VWAP_ratio' in self.df.columns:
            for vwap_r in params.get('vwap_ratios', [1.04, 1.06, 1.08]):
                vwap_breakout = self.df['VWAP_ratio'] >= vwap_r
                
                for rsi_th in params['rsi_thresholds']:
                    signals = vwap_breakout & (self.df['RSI'] >= rsi_th)
                    self._evaluate_strategy(
                        f"VWAP{int(vwap_r*100)}%+ + RSI{rsi_th}+",
                        signals, 'breakout', None, None
                    )
                    test_count += 1
        
        pbar.close()
        print(f"   ✅ 상향돌파 전략 테스트 완료: {test_count:,}회")
    
    def _test_reversal_strategies(self):
        """하락조건 매도 전략 테스트 - 만 번 이상 테스트를 위한 대폭 확장"""
        params = BACKTEST_PARAMS
        test_count = 0
        found_count = len(self.strategies)
        
        # 하락반전용 세밀 파라미터 (config에서 로드, 없으면 기본값)
        rev_rsi = params.get('reversal_rsi_thresholds', params['rsi_thresholds'])
        rev_stoch = params.get('reversal_stoch_thresholds', params['stoch_thresholds'])
        rev_mfi = params.get('reversal_mfi_thresholds', params['mfi_thresholds'])
        rev_cci = params.get('reversal_cci_thresholds', params['cci_thresholds'])
        rev_bb = params.get('reversal_bb_ratios', params['bb_ratios'])
        rev_disp = params.get('reversal_disparity_thresholds', [105, 107, 110, 112, 115, 118, 120, 122, 125])
        rev_adx = params.get('reversal_adx_thresholds', [20, 25, 30, 35, 40, 45, 50])
        
        from tqdm import tqdm
        
        # 전체 테스트 수 추정 (프로그레스바용) - Williams, Aroon, ROC, SAR 제거
        total_estimate = (
            len(rev_rsi) * len(rev_stoch) +  # RSI + Stoch
            len(rev_rsi) * len(rev_mfi) +    # RSI + MFI
            len(rev_rsi) * len(rev_cci) +    # RSI + CCI
            len(rev_stoch) * len(rev_mfi) +  # Stoch + MFI
            len(rev_rsi) * len(rev_disp) * len(self.ma_range) +  # RSI반전 + 이격도
            len(rev_cci) * len(rev_rsi) * 2 +  # CCI반전 조합
            len(rev_bb) * len(rev_rsi) * len(rev_stoch) +  # BB 조합
            len(rev_mfi) * len(rev_rsi) * len(rev_stoch)  # MFI 조합
        )
        
        pbar = tqdm(total=total_estimate, desc="   하락반전", unit="tests")
        
        # ============================================
        # 1. MACD 데드크로스 기반 조합
        # ============================================
        macd_dead = (
            (self.df['MACD'] < self.df['MACD_Signal']) &
            (self.df['MACD'].shift(1) >= self.df['MACD_Signal'].shift(1))
        )
        
        # MACD + RSI + Stochastic 3중 조합
        for rsi_th in rev_rsi:
            for stoch_th in rev_stoch:
                signals = macd_dead & (self.df['RSI'] >= rsi_th) & (self.df['Stoch_K'] >= stoch_th)
                self._evaluate_strategy(
                    f"MACD데드 + RSI{rsi_th}+ + Stoch{stoch_th}+",
                    signals, 'reversal', None, None
                )
                test_count += 1
                pbar.update(1)
        
        # MACD + RSI + MFI 조합
        for rsi_th in rev_rsi:
            for mfi_th in rev_mfi:
                signals = macd_dead & (self.df['RSI'] >= rsi_th) & (self.df['MFI'] >= mfi_th)
                self._evaluate_strategy(
                    f"MACD데드 + RSI{rsi_th}+ + MFI{mfi_th}+",
                    signals, 'reversal', None, None
                )
                test_count += 1
                pbar.update(1)
        
        # MACD + RSI + CCI 조합
        for rsi_th in rev_rsi:
            for cci_th in rev_cci:
                signals = macd_dead & (self.df['RSI'] >= rsi_th) & (self.df['CCI'] >= cci_th)
                self._evaluate_strategy(
                    f"MACD데드 + RSI{rsi_th}+ + CCI{cci_th}+",
                    signals, 'reversal', None, None
                )
                test_count += 1
                pbar.update(1)
        
        # ============================================
        # 2. Stochastic 데드크로스 기반 조합
        # ============================================
        stoch_dead = (
            (self.df['Stoch_K'] < self.df['Stoch_D']) &
            (self.df['Stoch_K'].shift(1) >= self.df['Stoch_D'].shift(1))
        )
        
        # Stoch데드 + MFI + RSI 조합
        for stoch_th in rev_stoch:
            for mfi_th in rev_mfi:
                signals = stoch_dead & (self.df['Stoch_K'].shift(1) >= stoch_th) & (self.df['MFI'] >= mfi_th)
                self._evaluate_strategy(
                    f"Stoch데드(K>{stoch_th}) + MFI{mfi_th}+",
                    signals, 'reversal', None, None
                )
                test_count += 1
                pbar.update(1)
        
        # ============================================
        # 3. RSI 고점 반전 기반 대규모 조합
        # ============================================
        for rsi_th in rev_rsi:
            rsi_reversal = (
                (self.df['RSI'].shift(1) >= rsi_th) &
                (self.df['RSI'] < self.df['RSI'].shift(1))
            )
            
            # RSI반전 + 이격도 + MA 조합 (대규모)
            for disp_th in rev_disp:
                for ma in self.ma_range:
                    disp_col = f'Disparity_{ma}'
                    if disp_col not in self.df.columns:
                        continue
                    signals = rsi_reversal & (self.df[disp_col] >= disp_th)
                    self._evaluate_strategy(
                        f"RSI{rsi_th}반전 + 이격도{disp_th}(MA{ma})",
                        signals, 'reversal', disp_th, ma
                    )
                    test_count += 1
                    pbar.update(1)
            
            # RSI반전 + Stochastic + MFI 조합
            for stoch_th in rev_stoch:
                for mfi_th in rev_mfi[:5]:  # 일부만
                    signals = rsi_reversal & (self.df['Stoch_K'] >= stoch_th) & (self.df['MFI'] >= mfi_th)
                    self._evaluate_strategy(
                        f"RSI{rsi_th}반전 + Stoch{stoch_th}+ + MFI{mfi_th}+",
                        signals, 'reversal', None, None
                    )
                    test_count += 1
                    pbar.update(1)
        
        # ============================================
        # 4. CCI 고점 반전 기반 조합
        # ============================================
        for cci_th in rev_cci:
            cci_reversal = (
                (self.df['CCI'].shift(1) >= cci_th) &
                (self.df['CCI'] < self.df['CCI'].shift(1))
            )
            
            # CCI반전 + RSI 조합
            for rsi_th in rev_rsi:
                signals = cci_reversal & (self.df['RSI'] >= rsi_th)
                self._evaluate_strategy(
                    f"CCI{cci_th}반전 + RSI{rsi_th}+",
                    signals, 'reversal', None, None
                )
                test_count += 1
                pbar.update(1)
            
            # CCI반전 + RSI + Stochastic 조합
            for rsi_th in rev_rsi:
                for stoch_th in rev_stoch[:5]:  # 일부만
                    signals = cci_reversal & (self.df['RSI'] >= rsi_th) & (self.df['Stoch_K'] >= stoch_th)
                    self._evaluate_strategy(
                        f"CCI{cci_th}반전 + RSI{rsi_th}+ + Stoch{stoch_th}+",
                        signals, 'reversal', None, None
                    )
                    test_count += 1
                    pbar.update(1)
            
            # CCI반전 + 이격도 조합
            for disp_th in rev_disp:
                for ma in self.ma_range:
                    disp_col = f'Disparity_{ma}'
                    if disp_col not in self.df.columns:
                        continue
                    signals = cci_reversal & (self.df[disp_col] >= disp_th)
                    self._evaluate_strategy(
                        f"CCI{cci_th}반전 + 이격도{disp_th}(MA{ma})",
                        signals, 'reversal', disp_th, ma
                    )
                    test_count += 1
                    pbar.update(1)
        
        # ============================================
        # 5. 볼린저밴드 반전 기반 조합
        # ============================================
        for bb_ratio in rev_bb:
            bb_touch_down = (
                (self.df['close'].shift(1) >= self.df['BB_upper'].shift(1) * bb_ratio) &
                (self.df['close'] < self.df['BB_upper'])
            )
            
            # BB반전 + RSI + Stochastic 조합
            for rsi_th in rev_rsi:
                for stoch_th in rev_stoch:
                    signals = bb_touch_down & (self.df['RSI'] >= rsi_th) & (self.df['Stoch_K'] >= stoch_th)
                    self._evaluate_strategy(
                        f"BB{int(bb_ratio*100)}%반전 + RSI{rsi_th}+ + Stoch{stoch_th}+",
                        signals, 'reversal', None, None
                    )
                    test_count += 1
                    pbar.update(1)
            
            # BB반전 + CCI 조합
            for cci_th in rev_cci:
                signals = bb_touch_down & (self.df['CCI'] >= cci_th)
                self._evaluate_strategy(
                    f"BB{int(bb_ratio*100)}%반전 + CCI{cci_th}+",
                    signals, 'reversal', None, None
                )
                test_count += 1
                pbar.update(1)
            
            # BB반전 + 이격도 조합
            for disp_th in rev_disp:
                for ma in self.ma_range:
                    disp_col = f'Disparity_{ma}'
                    if disp_col not in self.df.columns:
                        continue
                    signals = bb_touch_down & (self.df[disp_col] >= disp_th)
                    self._evaluate_strategy(
                        f"BB{int(bb_ratio*100)}%반전 + 이격도{disp_th}(MA{ma})",
                        signals, 'reversal', disp_th, ma
                    )
                    test_count += 1
                    pbar.update(1)
        
        # ============================================
        # 7. MFI 반전 기반 조합
        # ============================================
        for mfi_th in rev_mfi:
            mfi_reversal = (
                (self.df['MFI'].shift(1) >= mfi_th) &
                (self.df['MFI'] < self.df['MFI'].shift(1))
            )
            
            # MFI반전 + RSI + Stochastic 조합
            for rsi_th in rev_rsi:
                for stoch_th in rev_stoch:
                    signals = mfi_reversal & (self.df['RSI'] >= rsi_th) & (self.df['Stoch_K'] >= stoch_th)
                    self._evaluate_strategy(
                        f"MFI{mfi_th}반전 + RSI{rsi_th}+ + Stoch{stoch_th}+",
                        signals, 'reversal', None, None
                    )
                    test_count += 1
                    pbar.update(1)
            
            # MFI반전 + CCI 조합
            for cci_th in rev_cci:
                signals = mfi_reversal & (self.df['CCI'] >= cci_th)
                self._evaluate_strategy(
                    f"MFI{mfi_th}반전 + CCI{cci_th}+",
                    signals, 'reversal', None, None
                )
                test_count += 1
                pbar.update(1)
            
            # MFI반전 + 이격도 조합
            for disp_th in rev_disp:
                for ma in self.ma_range:
                    disp_col = f'Disparity_{ma}'
                    if disp_col not in self.df.columns:
                        continue
                    signals = mfi_reversal & (self.df[disp_col] >= disp_th)
                    self._evaluate_strategy(
                        f"MFI{mfi_th}반전 + 이격도{disp_th}(MA{ma})",
                        signals, 'reversal', disp_th, ma
                    )
                    test_count += 1
                    pbar.update(1)
        
        # ============================================
        # 8. 복합 데드크로스 (MACD + Stoch 동시)
        # ============================================
        dual_dead = macd_dead & stoch_dead
        
        # 복합데드 + RSI + MFI 조합
        for rsi_th in rev_rsi:
            for mfi_th in rev_mfi:
                signals = dual_dead & (self.df['RSI'] >= rsi_th) & (self.df['MFI'] >= mfi_th)
                self._evaluate_strategy(
                    f"MACD+Stoch동시데드 + RSI{rsi_th}+ + MFI{mfi_th}+",
                    signals, 'reversal', None, None
                )
                test_count += 1
                pbar.update(1)
        
        # 복합데드 + 이격도 조합
        for disp_th in rev_disp:
            for ma in self.ma_range:
                disp_col = f'Disparity_{ma}'
                if disp_col not in self.df.columns:
                    continue
                for rsi_th in rev_rsi[:5]:  # 일부만
                    signals = dual_dead & (self.df[disp_col] >= disp_th) & (self.df['RSI'] >= rsi_th)
                    self._evaluate_strategy(
                        f"MACD+Stoch동시데드 + 이격도{disp_th}(MA{ma}) + RSI{rsi_th}+",
                        signals, 'reversal', disp_th, ma
                    )
                    test_count += 1
                    pbar.update(1)
        
        # ============================================
        # 9. ADX 기반 추세 강도 + 반전 조합
        # ============================================
        if 'ADX' in self.df.columns:
            for adx_th in rev_adx:
                adx_strong = self.df['ADX'] >= adx_th
                
                # 강한 추세 + RSI반전
                for rsi_th in rev_rsi:
                    rsi_reversal = (
                        (self.df['RSI'].shift(1) >= rsi_th) &
                        (self.df['RSI'] < self.df['RSI'].shift(1))
                    )
                    signals = adx_strong & rsi_reversal
                    self._evaluate_strategy(
                        f"ADX{adx_th}+ + RSI{rsi_th}반전",
                        signals, 'reversal', None, None
                    )
                    test_count += 1
                    pbar.update(1)
                
                # 강한 추세 + MACD 데드
                for rsi_th in rev_rsi[:5]:
                    signals = adx_strong & macd_dead & (self.df['RSI'] >= rsi_th)
                    self._evaluate_strategy(
                        f"ADX{adx_th}+ + MACD데드 + RSI{rsi_th}+",
                        signals, 'reversal', None, None
                    )
                    test_count += 1
                    pbar.update(1)
        
        # ============================================
        # 10. DMI 기반 하락반전 전략 (새로운 지표)
        # ============================================
        if '+DI' in self.df.columns and '-DI' in self.df.columns:
            # +DI < -DI 전환 (상승 → 하락 추세 전환)
            dmi_bearish_cross = (
                (self.df['+DI'] < self.df['-DI']) &
                (self.df['+DI'].shift(1) >= self.df['-DI'].shift(1))
            )
            
            for dmi_th in params.get('reversal_dmi_thresholds', [20, 25, 30]):
                # DMI 크로스 + RSI 과열
                for rsi_th in rev_rsi[:6]:
                    signals = dmi_bearish_cross & (self.df['-DI'] >= dmi_th) & (self.df['RSI'] >= rsi_th)
                    self._evaluate_strategy(
                        f"DMI하락전환(-DI{dmi_th}+) + RSI{rsi_th}+",
                        signals, 'reversal', None, None
                    )
                    test_count += 1
                    pbar.update(1)
        
        # ============================================
        # 11. OBV 기반 하락반전 전략 (새로운 지표)
        # ============================================
        if 'OBV' in self.df.columns and 'OBV_MA20' in self.df.columns:
            # OBV가 OBV_MA20 아래로 하향 돌파 (약세 전환)
            obv_bearish = (
                (self.df['OBV'] < self.df['OBV_MA20']) &
                (self.df['OBV'].shift(1) >= self.df['OBV_MA20'].shift(1))
            )
            
            for rsi_th in rev_rsi[:6]:
                signals = obv_bearish & (self.df['RSI'] >= rsi_th)
                self._evaluate_strategy(
                    f"OBV하향돌파 + RSI{rsi_th}+",
                    signals, 'reversal', None, None
                )
                test_count += 1
                pbar.update(1)
        

        pbar.close()
        
        new_found = len(self.strategies) - found_count
        print(f"   ✅ 하락반전 전략 테스트 완료: {test_count:,}회, 발견: {new_found}개")
    
    def _evaluate_strategy(self, name: str, signals: pd.Series, 
                          strategy_type: str, disparity: float, ma_period: int):
        """
        전략 평가 및 forward returns 계산 (최적화된 버전)
        
        Args:
            name: 전략명
            signals: 신호 시리즈
            strategy_type: 'breakout' 또는 'reversal'
            disparity: 이격도 (breakout 전략용)
            ma_period: MA 기간 (breakout 전략용)
        """
        signal_indices = self.df.index[signals].tolist()
        
        if len(signal_indices) < BACKTEST_PARAMS['min_signals']:
            return
        
        # Forward returns 계산 (벡터화)
        forward_returns = []
        wins = 0
        
        # 닫힌 가격 numpy 배열로 변환 (속도 최적화)
        close_array = self.df['close'].values
        index_array = self.df.index.values
        
        for signal_date in signal_indices:
            signal_loc = self.df.index.get_loc(signal_date)
            signal_price = close_array[signal_loc]
            
            result = {
                'signal_date': signal_date,
                'signal_price': signal_price,
            }
            
            # 5, 10, 15, 20일 후 가격 및 수익률
            for days in BACKTEST_PARAMS['forward_days']:
                future_loc = signal_loc + days
                
                if future_loc < len(close_array):
                    future_date = index_array[future_loc]
                    future_price = close_array[future_loc]
                    return_pct = (future_price - signal_price) / signal_price * 100
                    
                    result[f'date_{days}d'] = future_date
                    result[f'price_{days}d'] = future_price
                    result[f'return_{days}d'] = return_pct
                else:
                    result[f'date_{days}d'] = None
                    result[f'price_{days}d'] = None
                    result[f'return_{days}d'] = None
            
            forward_returns.append(result)
            
            # 20일 후 하락했으면 성공
            if result.get('return_20d') is not None and result['return_20d'] < 0:
                wins += 1
        
        # 승률 계산
        valid_signals = [r for r in forward_returns if r.get('return_20d') is not None]
        if len(valid_signals) == 0:
            return
        
        win_rate = (wins / len(valid_signals)) * 100
        
        # 최소 승률 필터
        if win_rate < BACKTEST_PARAMS['min_win_rate']:
            return
        
        # 추세별 승률 계산 (날짜별 추세 레이블이 있는 경우)
        trend_win_rates = {}
        if self._trend_label_map is not None:
            # 통과한 전략에 대해서만 추세 태깅 수행
            trend_counts = {}  # {trend: [total, wins]}
            for r in valid_signals:
                t = self._trend_label_map.get(r['signal_date'], self.trend_type)
                r['trend_at_signal'] = t
                if t not in trend_counts:
                    trend_counts[t] = [0, 0]
                trend_counts[t][0] += 1
                if r['return_20d'] < 0:
                    trend_counts[t][1] += 1
            for t, (cnt, wins_t) in trend_counts.items():
                if cnt >= 2:
                    trend_win_rates[t] = {
                        'win_rate': (wins_t / cnt) * 100,
                        'count': cnt
                    }
        
        # 전략 저장
        self.strategies.append({
            'name': name,
            'type': strategy_type,
            'disparity': disparity,
            'ma_period': ma_period,
            'signal_count': len(signal_indices),
            'valid_signal_count': len(valid_signals),
            'win_rate': win_rate,
            'forward_returns': forward_returns,
            'trend_type': self.trend_type,
            'trend_win_rates': trend_win_rates
        })
    
    def get_top_strategies(self, n: int = 20) -> List[Dict]:
        """상위 N개 전략 반환"""
        sorted_strategies = sorted(
            self.strategies, 
            key=lambda x: (x['win_rate'], x['signal_count']), 
            reverse=True
        )
        return sorted_strategies[:n]


def run_peak_detection(df: pd.DataFrame, trend_type: str = 'bull') -> List[Dict]:
    """
    간편 고점 판독 함수
    
    Args:
        df: 지표가 계산된 데이터프레임
        trend_type: 추세 타입
    
    Returns:
        전략 리스트
    """
    detector = PeakDetector(df, trend_type)
    return detector.run_backtest()


if __name__ == '__main__':
    from data_loader import load_data
    from trend_analyzer import analyze_market_trend
    
    # 데이터 로드
    df = load_data('kospi')
    
    # 추세 분석
    trend_type, confidence, details = analyze_market_trend(df)
    print(f"\n시장 추세: {trend_type} (신뢰도: {confidence}%)")
    
    # 백테스트
    detector = PeakDetector(df, trend_type)
    strategies = detector.run_backtest()
    
    # 상위 전략 출력
    print(f"\n{'─'*60}")
    print(f"📊 상위 전략")
    print(f"{'─'*60}")
    
    for i, s in enumerate(detector.get_top_strategies(5), 1):
        print(f"{i}. {s['name']}")
        print(f"   승률: {s['win_rate']:.1f}% | 신호수: {s['signal_count']}")
