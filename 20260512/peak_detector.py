"""
고점 판독 백테스터
- 상향돌파 매도 전략: 특정 조건 상향돌파 시 매도
- 하락조건 매도 전략: 상승 후 특정 하락 조건 충족 시 매도
- 5/10/15/20일 후 결과 분석
- FDR 다중검정 보정 (Benjamini-Hochberg)
- Walk-Forward 검증 (OOS 승률)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from scipy import stats
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
        """추세에 맞는 파라미터 설정 (적응형)"""
        params = BACKTEST_PARAMS
        
        if self.trend_type == 'bull':
            # 상승장: 높은 이격도, 높은 지표 임계값
            self.disparity_range = range(
                params['disparity_min'] + 5,  # 110%
                params['disparity_max'],
                params['disparity_step']
            )
            # 적응형: 상승장에서는 과열 기준 상향
            self.rsi_thresholds = [t for t in params['rsi_thresholds'] if t >= 65]
            self.stoch_thresholds = [t for t in params['stoch_thresholds'] if t >= 70]
            self.mfi_thresholds = [t for t in params['mfi_thresholds'] if t >= 70]
        elif self.trend_type == 'bear':
            # 하락장: 낮은 이격도, 낮은 지표 임계값
            self.disparity_range = range(
                params['disparity_min'],
                params['disparity_max'] - 10,  # 140%
                params['disparity_step']
            )
            # 적응형: 하락장에서는 과열 기준 하향
            self.rsi_thresholds = [t for t in params['rsi_thresholds'] if t <= 80]
            self.stoch_thresholds = [t for t in params['stoch_thresholds'] if t <= 85]
            self.mfi_thresholds = [t for t in params['mfi_thresholds'] if t <= 85]
        else:
            # 횡보장: 중간 범위
            self.disparity_range = range(
                params['disparity_min'],
                params['disparity_max'] - 5,
                params['disparity_step']
            )
            self.rsi_thresholds = params['rsi_thresholds']
            self.stoch_thresholds = params['stoch_thresholds']
            self.mfi_thresholds = params['mfi_thresholds']
        
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
        
        pre_fdr_count = len(self.strategies)
        print(f"\n   📊 FDR 보정 전 전략: {pre_fdr_count}개")
        
        # 3. FDR 다중검정 보정
        if BACKTEST_PARAMS.get('fdr_enabled', True) and self.strategies:
            print("\n3️⃣ FDR 다중검정 보정 적용 중...")
            self._apply_fdr_correction()
            print(f"   ✅ FDR 보정 후 전략: {len(self.strategies)}개 (제거: {pre_fdr_count - len(self.strategies)}개)")
        
        # 4. Walk-Forward 검증
        if BACKTEST_PARAMS.get('walk_forward_enabled', True) and self.strategies:
            pre_wf_count = len(self.strategies)
            print("\n4️⃣ Walk-Forward OOS 검증 중...")
            self._apply_walk_forward_validation()
            print(f"   ✅ Walk-Forward 후 전략: {len(self.strategies)}개 (제거: {pre_wf_count - len(self.strategies)}개)")
        
        # 5. 앙상블 투표 백테스트
        if len(self.strategies) >= 2:
            print("\n5️⃣ 앙상블 투표 백테스트 중...")
            self.ensemble_results = self._run_ensemble_backtest()
            if self.ensemble_results:
                print(f"   ✅ 앙상블 최적 N={self.ensemble_results['best_n']}, "
                      f"승률 {self.ensemble_results['best_win_rate']:.1f}%")
        else:
            self.ensemble_results = None
        
        print(f"\n✅ 총 {len(self.strategies)}개 전략 발견")
        
        return self.strategies
    
    def _apply_fdr_correction(self):
        """Benjamini-Hochberg FDR 보정으로 통계적으로 유의하지 않은 전략 제거"""
        alpha = BACKTEST_PARAMS.get('fdr_alpha', 0.25)
        fallback_p = BACKTEST_PARAMS.get('fdr_fallback_pvalue', 0.10)
        
        # 각 전략의 p-value 계산 (이항분포: 매도 후 하락 확률 = 50% 귀무가설)
        for s in self.strategies:
            n = s['valid_signal_count']
            k = int(s['win_rate'] * n / 100)
            # 귀무가설: 성공 확률 = 0.5 (동전 던지기와 같음)
            p_value = stats.binomtest(k, n, 0.5, alternative='greater').pvalue
            s['p_value'] = p_value
        
        # Benjamini-Hochberg 절차
        m = len(self.strategies)
        sorted_strategies = sorted(self.strategies, key=lambda x: x['p_value'])
        
        # BH: 가장 큰 k를 찾아서 p(k) <= k/m * alpha인 모든 전략을 유의하다고 판단
        max_significant_rank = 0
        for rank, s in enumerate(sorted_strategies, 1):
            bh_threshold = (rank / m) * alpha
            s['bh_threshold'] = bh_threshold
            s['fdr_rank'] = rank
            if s['p_value'] <= bh_threshold:
                max_significant_rank = rank
        
        # max_significant_rank까지의 모든 전략을 유의하다고 표시
        for rank, s in enumerate(sorted_strategies, 1):
            s['fdr_significant'] = (rank <= max_significant_rank)
        
        fdr_passed = [s for s in self.strategies if s.get('fdr_significant', False)]
        
        if fdr_passed:
            self.strategies = fdr_passed
        else:
            # FDR로 모두 탈락 시 fallback: 개별 p-value 기준으로 필터
            fallback_passed = [s for s in self.strategies if s['p_value'] <= fallback_p]
            if fallback_passed:
                for s in fallback_passed:
                    s['fdr_significant'] = False  # FDR은 실패, 개별 p-value만 통과
                    s['fdr_fallback'] = True
                self.strategies = fallback_passed
                print(f"   ⚠️ FDR 전멸 → fallback (p<{fallback_p}): {len(fallback_passed)}개 유지")
            else:
                # 모든 필터 실패 → 상위 20개를 p-value 기준으로 유지 (통계적 마진 표시)
                top_by_p = sorted(self.strategies, key=lambda x: x['p_value'])[:20]
                for s in top_by_p:
                    s['fdr_significant'] = False
                    s['fdr_fallback'] = True
                    s['stat_marginal'] = True
                self.strategies = top_by_p
                print(f"   ⚠️ 통계적 유의성 부족 → 상위 {len(top_by_p)}개 유지 (마진 표시)")
    
    def _apply_walk_forward_validation(self):
        """Walk-Forward: 학습기간에서 발견된 전략을 검증기간에서 평가"""
        train_ratio = BACKTEST_PARAMS.get('walk_forward_train_ratio', 0.7)
        min_oos_wr = BACKTEST_PARAMS.get('walk_forward_min_oos_winrate', 55)
        max_degrad = BACKTEST_PARAMS.get('walk_forward_max_degradation', 20)
        
        n_total = len(self.df)
        split_idx = int(n_total * train_ratio)
        split_date = self.df.index[split_idx]
        
        validated = []
        for s in self.strategies:
            # 학습기간(IS) 성과와 검증기간(OOS) 성과 분리
            is_returns = []
            oos_returns = []
            
            for fr in s['forward_returns']:
                ret20 = fr.get('return_20d')
                if ret20 is None:
                    continue
                if fr['signal_date'] < split_date:
                    is_returns.append(ret20)
                else:
                    oos_returns.append(ret20)
            
            # OOS 데이터가 충분한 경우만 검증
            if len(oos_returns) >= 3:
                oos_wins = sum(1 for r in oos_returns if r < 0)
                oos_win_rate = (oos_wins / len(oos_returns)) * 100
                
                is_wins = sum(1 for r in is_returns if r < 0) if is_returns else 0
                is_win_rate = (is_wins / len(is_returns)) * 100 if is_returns else s['win_rate']
                
                degradation = is_win_rate - oos_win_rate
                
                s['oos_win_rate'] = oos_win_rate
                s['oos_count'] = len(oos_returns)
                s['is_win_rate'] = is_win_rate
                s['is_count'] = len(is_returns)
                s['wf_degradation'] = degradation
                
                # OOS 최소 승률 및 하락폭 제한 검증
                if oos_win_rate >= min_oos_wr and degradation <= max_degrad:
                    s['wf_validated'] = True
                    validated.append(s)
                else:
                    s['wf_validated'] = False
            elif len(oos_returns) == 0 and len(is_returns) >= BACKTEST_PARAMS['min_signals']:
                # OOS 데이터 없음 (모든 신호가 학습기간에 있음) - 주의 표시 후 유지
                s['oos_win_rate'] = None
                s['oos_count'] = 0
                s['is_win_rate'] = s['win_rate']
                s['is_count'] = len(is_returns)
                s['wf_degradation'] = None
                s['wf_validated'] = None  # 검증 불가
                validated.append(s)
            else:
                # OOS 데이터 부족 - 유지하되 표시
                s['oos_win_rate'] = None
                s['oos_count'] = len(oos_returns)
                s['wf_degradation'] = None
                s['wf_validated'] = None
                validated.append(s)
        
        self.strategies = validated
    
    def _run_ensemble_backtest(self) -> Dict:
        """
        앙상블 투표 백테스트: N개 이상 동시 발동 시의 승률 검증
        """
        if len(self.strategies) < 2:
            return None
        
        # 모든 신호 날짜 수집
        all_dates = set()
        for s in self.strategies:
            for fr in s['forward_returns']:
                all_dates.add(fr['signal_date'])
        all_dates = sorted(all_dates)
        
        if not all_dates:
            return None
        
        # 각 날짜별 동시 발동 전략 수 계산
        date_signals = {}
        for d in all_dates:
            date_signals[d] = {'count': 0, 'strategies': [], 'returns_20d': []}
        
        for s in self.strategies:
            signal_dates_map = {}
            for fr in s['forward_returns']:
                signal_dates_map[fr['signal_date']] = fr
            
            for d in all_dates:
                if d in signal_dates_map:
                    date_signals[d]['count'] += 1
                    date_signals[d]['strategies'].append(s['name'])
                    ret20 = signal_dates_map[d].get('return_20d')
                    if ret20 is not None:
                        date_signals[d]['returns_20d'].append(ret20)
        
        # N=2,3,4,...별 앙상블 성과
        max_n = min(len(self.strategies), 6)
        ensemble_stats = {}
        best_n = 2
        best_wr = 0
        
        for n in range(2, max_n + 1):
            signals_n = [d for d, info in date_signals.items() 
                        if info['count'] >= n and info['returns_20d']]
            
            if len(signals_n) < 3:
                continue
            
            # 각 날짜의 평균 20d 수익률 사용
            wins = 0
            total = 0
            total_gain = 0.0
            total_loss = 0.0
            
            for d in signals_n:
                avg_ret = np.mean(date_signals[d]['returns_20d'])
                total += 1
                if avg_ret < 0:
                    wins += 1
                    total_gain += abs(avg_ret)
                else:
                    total_loss += avg_ret
            
            win_rate = (wins / total) * 100 if total > 0 else 0
            pf = (total_gain / total_loss) if total_loss > 0 else float('inf')
            
            ensemble_stats[n] = {
                'signal_count': len(signals_n),
                'win_rate': win_rate,
                'profit_factor': pf,
            }
            
            if win_rate > best_wr and len(signals_n) >= 3:
                best_wr = win_rate
                best_n = n
        
        if not ensemble_stats:
            return None
        
        return {
            'stats': ensemble_stats,
            'best_n': best_n,
            'best_win_rate': best_wr,
        }
    
    def _test_breakout_strategies(self):
        """상향돌파 매도 전략 테스트"""
        params = BACKTEST_PARAMS
        test_count = 0
        
        # 적응형 임계값 사용
        rsi_ths = self.rsi_thresholds
        stoch_ths = self.stoch_thresholds
        mfi_ths = self.mfi_thresholds
        
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
                for rsi_th in rsi_ths:
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
                for stoch_th in stoch_ths:
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
                for mfi_th in mfi_ths:
                    signals = (
                        (self.df['disparity'] >= disp) &
                        (self.df['MFI'] >= mfi_th)
                    )
                    self._evaluate_strategy(
                        f"이격도{disp}(MA{ma_period}) + MFI{mfi_th}+",
                        signals, 'breakout', disp, ma_period
                    )
                    test_count += 1
                
                # 이격도 + Volume Ratio
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
                
                # ─── 3중 조합 (상향돌파) ───
                # 이격도 + RSI + Stochastic
                for rsi_th in rsi_ths[::2]:  # 간격 넓혀 속도 확보
                    for stoch_th in stoch_ths[::2]:
                        signals = (
                            (self.df['disparity'] >= disp) &
                            (self.df['RSI'] >= rsi_th) &
                            (self.df['Stoch_K'] >= stoch_th)
                        )
                        self._evaluate_strategy(
                            f"이격도{disp}(MA{ma_period}) + RSI{rsi_th}+ + Stoch{stoch_th}+",
                            signals, 'breakout', disp, ma_period
                        )
                        test_count += 1
                
                # 이격도 + RSI + MFI
                for rsi_th in rsi_ths[::2]:
                    for mfi_th in mfi_ths[::2]:
                        signals = (
                            (self.df['disparity'] >= disp) &
                            (self.df['RSI'] >= rsi_th) &
                            (self.df['MFI'] >= mfi_th)
                        )
                        self._evaluate_strategy(
                            f"이격도{disp}(MA{ma_period}) + RSI{rsi_th}+ + MFI{mfi_th}+",
                            signals, 'breakout', disp, ma_period
                        )
                        test_count += 1
                
                # 이격도 + RSI + Volume Ratio
                if 'Volume_Ratio' in self.df.columns:
                    for rsi_th in rsi_ths[::2]:
                        for vol_th in params.get('volume_ratio_thresholds', [1.5, 2.0, 2.5])[::2]:
                            signals = (
                                (self.df['disparity'] >= disp) &
                                (self.df['RSI'] >= rsi_th) &
                                (self.df['Volume_Ratio'] >= vol_th)
                            )
                            self._evaluate_strategy(
                                f"이격도{disp}(MA{ma_period}) + RSI{rsi_th}+ + 거래량{vol_th:.1f}배+",
                                signals, 'breakout', disp, ma_period
                            )
                            test_count += 1
                
                # 이격도 + CCI + ADX (3중)
                if 'CCI' in self.df.columns and 'ADX' in self.df.columns:
                    for cci_th in params['cci_thresholds'][::2]:
                        for adx_th in params.get('dmi_thresholds', [25, 30, 35])[::2]:
                            signals = (
                                (self.df['disparity'] >= disp) &
                                (self.df['CCI'] >= cci_th) &
                                (self.df['ADX'] >= adx_th)
                            )
                            self._evaluate_strategy(
                                f"이격도{disp}(MA{ma_period}) + CCI{cci_th}+ + ADX{adx_th}+",
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
        
        # 이격도 컬럼 사전 계산 (reversal에서 사용)
        for ma in self.ma_range:
            disp_col = f'Disparity_{ma}'
            ma_col = f'MA{ma}'
            if disp_col not in self.df.columns:
                if ma_col not in self.df.columns:
                    self.df[ma_col] = self.df['close'].rolling(window=ma).mean()
                self.df[disp_col] = (self.df['close'] / self.df[ma_col]) * 100
        
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
        전략 평가 — 신호 클러스터링 제거, 리스크 지표 산출, 레짐 태깅
        
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
        
        # ── 신호 클러스터링 제거: 최소 N거래일 간격 유지 ──
        min_gap = BACKTEST_PARAMS.get('signal_min_gap_days', 10)
        deduped_indices = []
        last_loc = -min_gap  # 첫 신호는 항상 포함
        for sig_date in signal_indices:
            sig_loc = self.df.index.get_loc(sig_date)
            if sig_loc - last_loc >= min_gap:
                deduped_indices.append(sig_date)
                last_loc = sig_loc
        
        if len(deduped_indices) < BACKTEST_PARAMS['min_signals']:
            return
        
        # Forward returns 계산
        forward_returns = []
        wins = 0
        total_gain = 0.0  # 양수 수익 합산
        total_loss = 0.0  # 음수 수익 절대값 합산
        returns_20d = []
        
        close_array = self.df['close'].values
        index_array = self.df.index.values
        
        for signal_date in deduped_indices:
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
                    future_price = close_array[future_loc]
                    return_pct = (future_price - signal_price) / signal_price * 100
                    
                    result[f'date_{days}d'] = index_array[future_loc]
                    result[f'price_{days}d'] = future_price
                    result[f'return_{days}d'] = return_pct
                else:
                    result[f'date_{days}d'] = None
                    result[f'price_{days}d'] = None
                    result[f'return_{days}d'] = None
            
            forward_returns.append(result)
            
            # 20일 후 하락했으면 성공 (매도 전략이므로 하락 = 성공)
            ret20 = result.get('return_20d')
            if ret20 is not None:
                returns_20d.append(ret20)
                if ret20 < 0:
                    wins += 1
                    total_gain += abs(ret20)
                else:
                    total_loss += ret20
        
        # 유효 신호 수 확인
        valid_count = len(returns_20d)
        if valid_count < BACKTEST_PARAMS['min_signals']:
            return
        
        # ── 리스크 지표 산출 ──
        win_rate = (wins / valid_count) * 100
        
        # 최소 승률 필터
        if win_rate < BACKTEST_PARAMS['min_win_rate']:
            return
        
        # Profit Factor (총 이익 / 총 손실) — 매도 전략이므로 하락폭이 이익
        profit_factor = (total_gain / total_loss) if total_loss > 0 else float('inf')
        min_pf = BACKTEST_PARAMS.get('min_profit_factor', 1.3)
        if profit_factor < min_pf:
            return
        
        # 평균 수익률 (매도 후 20일 기준, 음수일수록 좋음)
        avg_return = np.mean(returns_20d)
        
        # 최대 역행 (Max Adverse Excursion) — 매도 후 최대 상승폭
        max_adverse = max(returns_20d) if returns_20d else 0
        
        # ── 추세별 승률 계산 (레짐 태깅) ──
        trend_win_rates = {}
        if self._trend_label_map is not None:
            trend_counts = {}  # {trend: [total, wins]}
            for r in forward_returns:
                if r.get('return_20d') is None:
                    continue
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
            'signal_count': len(deduped_indices),
            'valid_signal_count': valid_count,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'avg_return': avg_return,
            'max_adverse': max_adverse,
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
