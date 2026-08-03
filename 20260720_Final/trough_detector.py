"""
저점 판독 백테스터 (TroughDetector)
- PeakDetector의 거울 — 매수 신호 검출 (저점 후 상승 패턴)
- 하향이격도 + 과매도 지표 조합
- 저점반전: RSI/Stoch/MFI/CCI 반전 상승 + BB하단 접촉 + MACD 골든크로스
- 20일 후 상승 = 매수 성공
- direction='long'으로 모든 메트릭 자동 계산
"""

import pandas as pd
import numpy as np
from tqdm import tqdm
import logging

from peak_detector import PeakDetector
from config import BACKTEST_PARAMS

logger = logging.getLogger(__name__)


class TroughDetector(PeakDetector):
    """저점 판독 백테스터 — PeakDetector의 거울 (long direction)"""

    def __init__(self, df, trend_type='bull', trend_labels=None):
        super().__init__(df, trend_type, trend_labels)
        self.direction = 'long'  # 매수 신호 모드

    def _setup_params(self):
        """저점 판독용 과매도 임계값"""
        super()._setup_params()
        # 매수 신호용 과매도 임계값 (저값)
        # 추세에 따라 적응
        if self.trend_type == 'bull':
            # 상승장에서의 단기 조정 매수 — 약한 과매도
            self.rsi_thresholds = [30, 35, 40, 45]
            self.stoch_thresholds = [10, 15, 20, 25, 30]
            self.mfi_thresholds = [20, 25, 30, 35]
            self.cci_thresholds = [-100, -130, -160, -200]
            self.disparity_lo_range = [88, 90, 92, 94, 96]  # 하향이격도
        elif self.trend_type == 'bear':
            # 하락장에서의 깊은 저점 매수 — 강한 과매도
            self.rsi_thresholds = [15, 20, 25, 30]
            self.stoch_thresholds = [5, 10, 15, 20]
            self.mfi_thresholds = [10, 15, 20, 25]
            self.cci_thresholds = [-150, -200, -250, -300]
            self.disparity_lo_range = [80, 83, 86, 89, 92]
        else:  # sideways
            self.rsi_thresholds = [25, 30, 35, 40]
            self.stoch_thresholds = [10, 15, 20, 25]
            self.mfi_thresholds = [15, 20, 25, 30]
            self.cci_thresholds = [-100, -150, -200, -250]
            self.disparity_lo_range = [85, 88, 91, 94]

    def run_backtest(self):
        """저점 판독 백테스트 실행"""
        self.strategies = []
        print(f"\n{'─'*60}")
        print(f"📉 저점 판독 백테스트 시작 ({self.trend_type.upper()} 시장)")
        print(f"{'─'*60}")

        print("\n1️⃣ 하향이격도 매수 전략 테스트...")
        self._test_breakdown_strategies()

        print("\n2️⃣ 저점반전 매수 전략 테스트...")
        self._test_reversal_up_strategies()

        pre_fdr = len(self.strategies)
        print(f"\n   📊 FDR 보정 전 전략: {pre_fdr}개")

        if BACKTEST_PARAMS.get('fdr_enabled', True) and self.strategies:
            print("\n3️⃣ FDR 다중검정 보정...")
            self._apply_fdr_correction()
            print(f"   ✅ 보정 후: {len(self.strategies)}개")

        if BACKTEST_PARAMS.get('walk_forward_enabled', True) and self.strategies:
            pre_wf = len(self.strategies)
            print("\n4️⃣ Walk-Forward OOS 검증...")
            self._apply_walk_forward_validation()
            print(f"   ✅ 검증 후: {len(self.strategies)}개 (제거: {pre_wf - len(self.strategies)}개)")

        if len(self.strategies) >= 2:
            print("\n5️⃣ 앙상블 투표 백테스트...")
            self.ensemble_results = self._run_ensemble_backtest()
            if self.ensemble_results:
                print(f"   ✅ 최적 N={self.ensemble_results['best_n']}, "
                      f"승률 {self.ensemble_results['best_win_rate']:.1f}%")
        else:
            self.ensemble_results = None

        print(f"\n✅ 총 {len(self.strategies)}개 매수 전략 발견")
        return self.strategies

    def _test_breakdown_strategies(self):
        """하향이격도(저점) + 과매도 매수 전략"""
        params = BACKTEST_PARAMS
        test_count = 0

        pbar = tqdm(list(self.disparity_lo_range), desc="   하향이격도+지표", unit="disp")
        for disp_lo in pbar:
            for ma_period in self.ma_range:
                ma_col = f'MA{ma_period}'
                if ma_col not in self.df.columns:
                    self.df[ma_col] = self.df['close'].rolling(window=ma_period).mean()
                self.df['disparity'] = (self.df['close'] / self.df[ma_col]) * 100

                # 하향이격도 + RSI 과매도
                for rsi_th in self.rsi_thresholds:
                    signals = (
                        (self.df['disparity'] <= disp_lo) &
                        (self.df['RSI'] <= rsi_th)
                    )
                    self._evaluate_strategy(
                        f"하향이격도{disp_lo}(MA{ma_period}) + RSI{rsi_th}-",
                        signals, 'breakdown', disp_lo, ma_period
                    )
                    test_count += 1

                # 하향이격도 + Stochastic 과매도
                for stoch_th in self.stoch_thresholds:
                    signals = (
                        (self.df['disparity'] <= disp_lo) &
                        (self.df['Stoch_K'] <= stoch_th)
                    )
                    self._evaluate_strategy(
                        f"하향이격도{disp_lo}(MA{ma_period}) + Stoch{stoch_th}-",
                        signals, 'breakdown', disp_lo, ma_period
                    )
                    test_count += 1

                # 하향이격도 + MFI 과매도
                for mfi_th in self.mfi_thresholds:
                    signals = (
                        (self.df['disparity'] <= disp_lo) &
                        (self.df['MFI'] <= mfi_th)
                    )
                    self._evaluate_strategy(
                        f"하향이격도{disp_lo}(MA{ma_period}) + MFI{mfi_th}-",
                        signals, 'breakdown', disp_lo, ma_period
                    )
                    test_count += 1

                # 하향이격도 + RSI + Stoch (3중)
                for rsi_th in self.rsi_thresholds[::2]:
                    for stoch_th in self.stoch_thresholds[::2]:
                        signals = (
                            (self.df['disparity'] <= disp_lo) &
                            (self.df['RSI'] <= rsi_th) &
                            (self.df['Stoch_K'] <= stoch_th)
                        )
                        self._evaluate_strategy(
                            f"하향이격도{disp_lo}(MA{ma_period}) + RSI{rsi_th}- + Stoch{stoch_th}-",
                            signals, 'breakdown', disp_lo, ma_period
                        )
                        test_count += 1

                # 하향이격도 + CCI + ADX (3중)
                if 'CCI' in self.df.columns and 'ADX' in self.df.columns:
                    for cci_th in self.cci_thresholds[::2]:
                        for adx_th in params.get('dmi_thresholds', [25, 30, 35])[::2]:
                            signals = (
                                (self.df['disparity'] <= disp_lo) &
                                (self.df['CCI'] <= cci_th) &
                                (self.df['ADX'] >= adx_th)
                            )
                            self._evaluate_strategy(
                                f"하향이격도{disp_lo}(MA{ma_period}) + CCI{cci_th}- + ADX{adx_th}+",
                                signals, 'breakdown', disp_lo, ma_period
                            )
                            test_count += 1
            pbar.set_postfix({'tests': test_count, 'found': len(self.strategies)})
        pbar.close()
        print(f"   ✅ 하향이격도 전략 테스트 완료: {test_count:,}회")

    def _test_reversal_up_strategies(self):
        """저점반전 매수 전략 (반대 방향 — peak의 _test_reversal_strategies 미러)"""
        params = BACKTEST_PARAMS
        test_count = 0
        found = len(self.strategies)

        # 이격도 컬럼 사전 계산
        for ma in self.ma_range:
            disp_col = f'Disparity_{ma}'
            ma_col = f'MA{ma}'
            if disp_col not in self.df.columns:
                if ma_col not in self.df.columns:
                    self.df[ma_col] = self.df['close'].rolling(window=ma).mean()
                self.df[disp_col] = (self.df['close'] / self.df[ma_col]) * 100

        rev_rsi = self.rsi_thresholds
        rev_stoch = self.stoch_thresholds
        rev_mfi = self.mfi_thresholds
        rev_cci = self.cci_thresholds
        rev_disp_lo = self.disparity_lo_range
        rev_bb = [0.99, 0.97, 0.95]  # BB 하단 접촉 비율 (BB_lower * ratio 이하)

        total_estimate = (
            len(rev_rsi) * len(rev_stoch) * 2 +  # MACD골드 조합
            len(rev_rsi) * len(rev_disp_lo) * len(self.ma_range) +  # RSI반전 + 이격도
            len(rev_cci) * len(rev_rsi) +
            len(rev_bb) * len(rev_rsi) * len(rev_stoch) +
            len(rev_mfi) * len(rev_rsi) +
            300  # 여유
        )
        pbar = tqdm(total=total_estimate, desc="   저점반전", unit="tests")

        # 1. MACD 골든크로스 (음수→양수 또는 하방→상방)
        macd_gold = (
            (self.df['MACD'] > self.df['MACD_Signal']) &
            (self.df['MACD'].shift(1) <= self.df['MACD_Signal'].shift(1))
        )

        for rsi_th in rev_rsi:
            for stoch_th in rev_stoch:
                signals = macd_gold & (self.df['RSI'] <= rsi_th) & (self.df['Stoch_K'] <= stoch_th)
                self._evaluate_strategy(
                    f"MACD골드 + RSI{rsi_th}- + Stoch{stoch_th}-",
                    signals, 'reversal_up', None, None
                )
                test_count += 1
                pbar.update(1)

        for rsi_th in rev_rsi:
            for mfi_th in rev_mfi:
                signals = macd_gold & (self.df['RSI'] <= rsi_th) & (self.df['MFI'] <= mfi_th)
                self._evaluate_strategy(
                    f"MACD골드 + RSI{rsi_th}- + MFI{mfi_th}-",
                    signals, 'reversal_up', None, None
                )
                test_count += 1
                pbar.update(1)

        # 2. Stochastic 골든크로스
        stoch_gold = (
            (self.df['Stoch_K'] > self.df['Stoch_D']) &
            (self.df['Stoch_K'].shift(1) <= self.df['Stoch_D'].shift(1))
        )
        for stoch_th in rev_stoch:
            for mfi_th in rev_mfi:
                signals = stoch_gold & (self.df['Stoch_K'].shift(1) <= stoch_th) & (self.df['MFI'] <= mfi_th)
                self._evaluate_strategy(
                    f"Stoch골드(K<{stoch_th}) + MFI{mfi_th}-",
                    signals, 'reversal_up', None, None
                )
                test_count += 1
                pbar.update(1)

        # 3. RSI 저점 반전 (상승 전환)
        for rsi_th in rev_rsi:
            rsi_rev_up = (
                (self.df['RSI'].shift(1) <= rsi_th) &
                (self.df['RSI'] > self.df['RSI'].shift(1))
            )
            for disp_th in rev_disp_lo:
                for ma in self.ma_range:
                    disp_col = f'Disparity_{ma}'
                    if disp_col not in self.df.columns:
                        continue
                    signals = rsi_rev_up & (self.df[disp_col] <= disp_th)
                    self._evaluate_strategy(
                        f"RSI{rsi_th}저점반전 + 하향이격도{disp_th}(MA{ma})",
                        signals, 'reversal_up', disp_th, ma
                    )
                    test_count += 1
                    pbar.update(1)

        # 4. CCI 저점 반전
        for cci_th in rev_cci:
            cci_rev_up = (
                (self.df['CCI'].shift(1) <= cci_th) &
                (self.df['CCI'] > self.df['CCI'].shift(1))
            )
            for rsi_th in rev_rsi:
                signals = cci_rev_up & (self.df['RSI'] <= rsi_th)
                self._evaluate_strategy(
                    f"CCI{cci_th}저점반전 + RSI{rsi_th}-",
                    signals, 'reversal_up', None, None
                )
                test_count += 1
                pbar.update(1)

        # 5. 볼린저밴드 하단 접촉 후 반등
        for bb_ratio in rev_bb:
            bb_touch_up = (
                (self.df['close'].shift(1) <= self.df['BB_lower'].shift(1) * bb_ratio) &
                (self.df['close'] > self.df['BB_lower'])
            )
            for rsi_th in rev_rsi:
                for stoch_th in rev_stoch:
                    signals = bb_touch_up & (self.df['RSI'] <= rsi_th) & (self.df['Stoch_K'] <= stoch_th)
                    self._evaluate_strategy(
                        f"BB하단{int(bb_ratio*100)}%반전 + RSI{rsi_th}- + Stoch{stoch_th}-",
                        signals, 'reversal_up', None, None
                    )
                    test_count += 1
                    pbar.update(1)
            for cci_th in rev_cci:
                signals = bb_touch_up & (self.df['CCI'] <= cci_th)
                self._evaluate_strategy(
                    f"BB하단{int(bb_ratio*100)}%반전 + CCI{cci_th}-",
                    signals, 'reversal_up', None, None
                )
                test_count += 1
                pbar.update(1)

        # 6. MFI 저점 반전
        for mfi_th in rev_mfi:
            mfi_rev_up = (
                (self.df['MFI'].shift(1) <= mfi_th) &
                (self.df['MFI'] > self.df['MFI'].shift(1))
            )
            for rsi_th in rev_rsi:
                signals = mfi_rev_up & (self.df['RSI'] <= rsi_th)
                self._evaluate_strategy(
                    f"MFI{mfi_th}저점반전 + RSI{rsi_th}-",
                    signals, 'reversal_up', None, None
                )
                test_count += 1
                pbar.update(1)

        # 7. DMI 상승 전환 (-DI < +DI cross)
        if '+DI' in self.df.columns and '-DI' in self.df.columns:
            dmi_bullish_cross = (
                (self.df['+DI'] > self.df['-DI']) &
                (self.df['+DI'].shift(1) <= self.df['-DI'].shift(1))
            )
            for dmi_th in params.get('reversal_dmi_thresholds', [20, 25, 30]):
                for rsi_th in rev_rsi[:6]:
                    signals = dmi_bullish_cross & (self.df['+DI'] >= dmi_th) & (self.df['RSI'] <= rsi_th)
                    self._evaluate_strategy(
                        f"DMI상승전환(+DI{dmi_th}+) + RSI{rsi_th}-",
                        signals, 'reversal_up', None, None
                    )
                    test_count += 1
                    pbar.update(1)

        # 8. OBV 상향 돌파
        if 'OBV' in self.df.columns and 'OBV_MA20' in self.df.columns:
            obv_bullish = (
                (self.df['OBV'] > self.df['OBV_MA20']) &
                (self.df['OBV'].shift(1) <= self.df['OBV_MA20'].shift(1))
            )
            for rsi_th in rev_rsi[:6]:
                signals = obv_bullish & (self.df['RSI'] <= rsi_th)
                self._evaluate_strategy(
                    f"OBV상향돌파 + RSI{rsi_th}-",
                    signals, 'reversal_up', None, None
                )
                test_count += 1
                pbar.update(1)

        pbar.close()

        # ============================================
        # 추가: BB Squeeze 저점 + 과매도 매수 전략
        # ============================================
        if 'BB_width' in self.df.columns:
            bb_width_q25 = self.df['BB_width'].rolling(250).quantile(0.25)
            bb_squeezed = self.df['BB_width'] <= bb_width_q25  # 변동성 수축 = 폭발 임박

            for rsi_th in rev_rsi[::2]:
                signals = bb_squeezed & (self.df['RSI'] <= rsi_th)
                self._evaluate_strategy(
                    f"BB수축(하위25%) + RSI{rsi_th}-",
                    signals, 'reversal_up', None, None
                )
                test_count += 1

            for mfi_th in rev_mfi[::2]:
                signals = bb_squeezed & (self.df['MFI'] <= mfi_th)
                self._evaluate_strategy(
                    f"BB수축(하위25%) + MFI{mfi_th}-",
                    signals, 'reversal_up', None, None
                )
                test_count += 1

            # BB 하단 접촉 + 수축 상태 (최강 저점 신호)
            bb_lower_squeeze = (
                (self.df['close'] <= self.df['BB_lower'] * 1.01) &
                bb_squeezed
            )
            for rsi_th in rev_rsi[::2]:
                signals = bb_lower_squeeze & (self.df['RSI'] <= rsi_th)
                self._evaluate_strategy(
                    f"BB하단+수축 + RSI{rsi_th}-",
                    signals, 'reversal_up', None, None
                )
                test_count += 1

        # ============================================
        # 추가: VWAP 하단 이탈 후 회귀 매수 전략
        # ============================================
        if 'VWAP_ratio' in self.df.columns:
            for vwap_r in [0.92, 0.94, 0.96, 0.98]:
                vwap_below = self.df['VWAP_ratio'] <= vwap_r
                # VWAP 하단 이탈 + RSI 과매도
                for rsi_th in rev_rsi[::2]:
                    signals = vwap_below & (self.df['RSI'] <= rsi_th)
                    self._evaluate_strategy(
                        f"VWAP{int(vwap_r*100)}%- + RSI{rsi_th}-",
                        signals, 'reversal_up', None, None
                    )
                    test_count += 1
                # VWAP 하단 이탈 + MFI 과매도
                for mfi_th in rev_mfi[::2]:
                    signals = vwap_below & (self.df['MFI'] <= mfi_th)
                    self._evaluate_strategy(
                        f"VWAP{int(vwap_r*100)}%- + MFI{mfi_th}-",
                        signals, 'reversal_up', None, None
                    )
                    test_count += 1

        # ============================================
        # 추가: 연속 N일 과매도 지속 후 반전 (강한 저점 신호)
        # ============================================
        for n_days in [2, 3]:
            for rsi_th in rev_rsi[::3]:
                rsi_oversold_ndays = True
                for k in range(n_days):
                    rsi_oversold_ndays = rsi_oversold_ndays & (self.df['RSI'].shift(k) <= rsi_th)
                rsi_reversal_up = rsi_oversold_ndays & (self.df['RSI'] > self.df['RSI'].shift(1))
                self._evaluate_strategy(
                    f"RSI{rsi_th}-{n_days}일연속후반등",
                    rsi_reversal_up, 'reversal_up', None, None
                )
                test_count += 1

        # ============================================
        # 추가: ADX 강한 하락 추세 + 극단적 과매도 (역추세 저점 매수)
        # ============================================
        if 'ADX' in self.df.columns and '-DI' in self.df.columns:
            for adx_th in [35, 40, 45]:
                adx_bear_strong = (
                    (self.df['ADX'] >= adx_th) &
                    (self.df['-DI'] > self.df['+DI'])
                )
                for rsi_th in rev_rsi[:4]:   # 극단적 과매도만 (15~25)
                    signals = adx_bear_strong & (self.df['RSI'] <= rsi_th)
                    self._evaluate_strategy(
                        f"ADX{adx_th}+하락추세 + RSI{rsi_th}극단-",
                        signals, 'reversal_up', None, None
                    )
                    test_count += 1

        new_found = len(self.strategies) - found
        print(f"   ✅ 저점반전 전략 테스트 완료: {test_count:,}회, 발견: {new_found}개")
