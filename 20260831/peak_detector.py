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

from config import BACKTEST_PARAMS, TRADING_COSTS, MONTE_CARLO, INVERSE_TEST
from risk_metrics import enrich_strategy_metrics, apply_trading_costs

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
        # direction: 'short' (고점 후 하락 기대) / 'long' (저점 후 상승 기대)
        self.direction = 'short'
        
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
        
        self.ma_range = params.get(
            'ma_periods',
            range(params['ma_min'], params['ma_max'] + 1, params['ma_step'])
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

        # 3. 외국인 매매 + MDD 매도 전략
        print("\n3️⃣ 외국인 매매 + MDD 복합 매도 전략...")
        self._test_foreign_flow_sell_strategies()

        # 동일 사건을 다른 임계값 이름으로 반복한 후보를 통계 검증 전에 정리
        self.dedup_stats = self._deduplicate_candidate_strategies()

        pre_fdr_count = len(self.strategies)
        print(f"\n   📊 FDR 보정 전 전략: {pre_fdr_count}개")

        # 4. FDR 다중검정 보정
        if BACKTEST_PARAMS.get('fdr_enabled', True) and self.strategies:
            print("\n4️⃣ FDR 다중검정 보정 적용 중...")
            self._apply_fdr_correction()
            print(f"   ✅ FDR 보정 후 전략: {len(self.strategies)}개 (제거: {pre_fdr_count - len(self.strategies)}개)")

        # 5. Walk-Forward 검증
        if BACKTEST_PARAMS.get('walk_forward_enabled', True) and self.strategies:
            pre_wf_count = len(self.strategies)
            print("\n5️⃣ Walk-Forward OOS 검증 중...")
            self._apply_walk_forward_validation()
            print(f"   ✅ Walk-Forward 후 전략: {len(self.strategies)}개 (제거: {pre_wf_count - len(self.strategies)}개)")

        # Monte Carlo/리스크 지표는 중복·통계 검증을 통과한 후보에만 계산
        self._enrich_validated_strategies()

        # 6. 앙상블 투표 백테스트
        if len(self.strategies) >= 2:
            print("\n6️⃣ 앙상블 투표 백테스트 중...")
            self.ensemble_results = self._run_ensemble_backtest()
            if self.ensemble_results:
                print(f"   ✅ 앙상블 최적 N={self.ensemble_results['best_n']}, "
                      f"승률 {self.ensemble_results['best_win_rate']:.1f}%")
        else:
            self.ensemble_results = None

        # 6. 레짐 가중 재정렬 — 현재 레짐 승률 기준으로 전략 우선순위 조정
        if self.strategies:
            self._apply_regime_weighting()

        print(f"\n✅ 총 {len(self.strategies)}개 전략 발견")
        
        return self.strategies

    @staticmethod
    def _candidate_quality(strategy: Dict) -> float:
        """소표본 과대평가를 줄인 후보 정렬 점수."""
        count = max(1, strategy.get('valid_signal_count', 1))
        probability = strategy.get('win_rate', 0) / 100
        standard_error = np.sqrt(probability * (1 - probability) / count)
        conservative_win_rate = (probability - 1.96 * standard_error) * 100
        profit_factor = min(strategy.get('profit_factor', 0), 5.0)
        return conservative_win_rate + profit_factor * 2 + np.log1p(count)

    def _deduplicate_candidate_strategies(self) -> Dict:
        """신호일이 거의 같은 후보 중 통계 품질이 가장 높은 하나만 유지한다."""
        before = len(self.strategies)
        threshold = BACKTEST_PARAMS.get('candidate_signal_similarity', 0.85)
        ranked = sorted(self.strategies, key=self._candidate_quality, reverse=True)
        kept = []
        kept_signal_sets = []
        exact_removed = 0
        similar_removed = 0

        for strategy in ranked:
            signal_set = {item['signal_date'] for item in strategy.get('forward_returns', [])}
            duplicate_kind = None
            for existing, existing_signals in zip(kept, kept_signal_sets):
                if strategy.get('type') != existing.get('type'):
                    continue
                if not signal_set or not existing_signals:
                    continue
                if signal_set == existing_signals:
                    duplicate_kind = 'exact'
                    break
                overlap = len(signal_set & existing_signals) / max(len(signal_set), len(existing_signals))
                if overlap >= threshold:
                    duplicate_kind = 'similar'
                    break

            if duplicate_kind == 'exact':
                exact_removed += 1
            elif duplicate_kind == 'similar':
                similar_removed += 1
            else:
                kept.append(strategy)
                kept_signal_sets.append(signal_set)

        self.strategies = kept
        stats = {
            'before': before,
            'after': len(kept),
            'exact_removed': exact_removed,
            'similar_removed': similar_removed,
            'threshold': threshold,
        }
        if before:
            print(
                f"\n   🧹 후보 중복 정리: {before} → {len(kept)}개 "
                f"(완전중복 {exact_removed}, 유사신호 {similar_removed}, 기준 {threshold:.0%})"
            )
        return stats

    def _enrich_validated_strategies(self):
        """최종 후보에만 Monte Carlo와 위험조정 지표를 계산한다."""
        for strategy in self.strategies:
            try:
                enrich_strategy_metrics(
                    strategy,
                    total_days=len(self.df),
                    apply_costs=TRADING_COSTS.get('enabled', True),
                    cost_pct=(
                        TRADING_COSTS.get('commission_pct', 0.015)
                        + TRADING_COSTS.get('tax_pct', 0.20)
                        + TRADING_COSTS.get('slippage_pct', 0.10)
                    ),
                    run_monte_carlo=MONTE_CARLO.get('enabled', True),
                    n_mc_iter=MONTE_CARLO.get('n_iterations', 1000),
                )
            except Exception as error:
                logger.debug(f"리스크 메트릭 산출 실패 ({strategy['name']}): {error}")
    
    def _apply_regime_weighting(self):
        """현재 시장 레짐에서의 승률로 전략 재정렬 + 레짐 승률 낮은 전략 제거"""
        # 먼저 신호 품질 등급 계산
        for s in self.strategies:
            s['grade'] = self._compute_signal_grade(s)

        min_regime_wr = 55.0  # 현재 레짐 최소 승률 (전략이 충분히 있을 때만 적용)

        # 현재 레짐 승률이 있는 전략과 없는 전략 분리
        with_regime = [s for s in self.strategies if s.get('regime_win_rate') is not None]
        without_regime = [s for s in self.strategies if s.get('regime_win_rate') is None]

        # 현재 레짐 데이터가 충분한 경우만 필터 적용
        if len(with_regime) >= 3:
            # 현재 레짐 승률 기준: min_regime_wr 이상이거나 전체 상위 절반
            passing = [s for s in with_regime if s['regime_win_rate'] >= min_regime_wr]
            if not passing:
                # 아무도 통과 못하면 레짐 승률 상위 절반 유지
                passing = sorted(with_regime, key=lambda x: x['regime_win_rate'], reverse=True)
                passing = passing[:max(1, len(passing) // 2)]
            # 레짐 승률 우선, 전체 승률 보조로 정렬
            passing.sort(key=lambda s: (s['regime_win_rate'], s['win_rate']), reverse=True)
            self.strategies = passing + without_regime
        else:
            # 레짐 데이터 부족 → 전체 승률 기준 유지
            self.strategies.sort(key=lambda s: s['win_rate'], reverse=True)

    @staticmethod
    def _compute_signal_grade(s: dict) -> str:
        """전략 품질 등급: A+/A/B/C/D (5개 축 종합 평가)"""
        score = 0

        # 1. 전체 승률 (max 3점)
        wr = s.get('win_rate', 0)
        score += 3 if wr >= 85 else (2 if wr >= 75 else (1 if wr >= 70 else 0))

        # 2. Walk-Forward 롤링 통과율 (max 3점)
        wf_p = s.get('wf_pass_count')
        wf_t = s.get('wf_windows', 1)
        if wf_p is not None and wf_t > 0:
            ratio = wf_p / wf_t
            score += 3 if ratio >= 1.0 else (2 if ratio >= 0.67 else 1)
        elif s.get('oos_win_rate') is not None:
            oos = s['oos_win_rate']
            score += 2 if oos >= 60 else (1 if oos >= 50 else 0)

        # 3. 현재 레짐 승률 (max 2점)
        rwr = s.get('regime_win_rate')
        if rwr is not None:
            score += 2 if rwr >= 80 else (1 if rwr >= 65 else 0)

        # 4. MFE/MAE 비율 — 이익 잠재력 vs 손실 위험 (max 2점)
        mfe = s.get('avg_mfe', 0)
        mae = abs(s.get('max_adverse', 0.01)) or 0.01
        ratio = mfe / mae
        score += 2 if ratio >= 2.0 else (1 if ratio >= 1.0 else 0)

        # 5. 신호 수 (통계적 신뢰도) (max 1점)
        n = s.get('valid_signal_count', 0)
        score += 1 if n >= 12 else 0

        total = 11
        pct = score / total
        if pct >= 0.82: return 'A+'
        if pct >= 0.64: return 'A'
        if pct >= 0.45: return 'B'
        if pct >= 0.27: return 'C'
        return 'D'

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
        """Walk-Forward: 롤링 다중 윈도우로 과적합 방지 강화"""
        min_oos_wr  = BACKTEST_PARAMS.get('walk_forward_min_oos_winrate', 50)
        max_degrad  = BACKTEST_PARAMS.get('walk_forward_max_degradation', 25)
        use_rolling = BACKTEST_PARAMS.get('walk_forward_rolling', True)
        n_windows   = BACKTEST_PARAMS.get('walk_forward_n_windows', 3)

        n_total = len(self.df)

        # ── 롤링 윈도우 정의 ──
        # 각 윈도우: (IS 끝 비율, OOS 시작 비율, OOS 끝 비율)
        if use_rolling and n_windows >= 2:
            step = 1.0 / (n_windows + 1)
            windows = []
            for i in range(1, n_windows + 1):
                oos_start = step * i
                oos_end   = min(1.0, oos_start + step)
                windows.append((0.0, oos_start, oos_end))
        else:
            train_ratio = BACKTEST_PARAMS.get('walk_forward_train_ratio', 0.7)
            windows = [(0.0, train_ratio, 1.0)]

        def _get_split_date(ratio):
            idx = min(int(n_total * ratio), n_total - 1)
            return self.df.index[idx]

        validated = []
        for s in self.strategies:
            window_results = []   # 각 윈도우의 (oos_wr, degradation, oos_count)

            for (_, oos_start_r, oos_end_r) in windows:
                oos_start_date = _get_split_date(oos_start_r)
                oos_end_date   = _get_split_date(oos_end_r)
                is_end_date    = oos_start_date

                is_rets, oos_rets = [], []
                for fr in s['forward_returns']:
                    ret20 = fr.get('return_20d')
                    if ret20 is None:
                        continue
                    sd = fr['signal_date']
                    if sd < is_end_date:
                        is_rets.append(ret20)
                    elif oos_start_date <= sd < oos_end_date:
                        oos_rets.append(ret20)

                if len(oos_rets) < 2:
                    continue   # 이 윈도우는 데이터 부족 — 건너뜀

                if self.direction == 'long':
                    oos_wins = sum(1 for r in oos_rets if r > 0)
                    is_wins  = sum(1 for r in is_rets  if r > 0) if is_rets else 0
                else:
                    oos_wins = sum(1 for r in oos_rets if r < 0)
                    is_wins  = sum(1 for r in is_rets  if r < 0) if is_rets else 0

                oos_wr  = (oos_wins / len(oos_rets)) * 100
                is_wr   = (is_wins / len(is_rets)) * 100 if is_rets else s['win_rate']
                degrad  = is_wr - oos_wr

                window_results.append((oos_wr, degrad, len(oos_rets)))

            if not window_results:
                # OOS 데이터 없음 — 주의 표시 후 유지
                s['oos_win_rate']  = None
                s['oos_count']     = 0
                s['is_win_rate']   = s['win_rate']
                s['wf_degradation'] = None
                s['wf_validated']  = None
                s['wf_windows']    = 0
                validated.append(s)
                continue

            # ── 다중 윈도우 집계 ──
            avg_oos_wr  = float(np.mean([w[0] for w in window_results]))
            avg_degrad  = float(np.mean([w[1] for w in window_results]))
            # 통과 기준: 과반 이상의 윈도우에서 OOS 승률 충족
            pass_count  = sum(1 for w in window_results
                              if w[0] >= min_oos_wr and w[1] <= max_degrad)
            n_valid_windows = len(window_results)
            passed = pass_count >= max(1, n_valid_windows // 2 + 1)  # 과반수 통과

            # 전략 메타에 WF 결과 저장
            s['oos_win_rate']     = avg_oos_wr
            s['oos_count']        = sum(w[2] for w in window_results)
            s['is_win_rate']      = s['win_rate']
            s['wf_degradation']   = avg_degrad
            s['wf_validated']     = passed
            s['wf_windows']       = n_valid_windows   # 검증에 사용된 윈도우 수
            s['wf_pass_count']    = pass_count

            if passed:
                validated.append(s)
            else:
                s['wf_validated'] = False

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
                if self.direction == 'long':
                    if avg_ret > 0:
                        wins += 1
                        total_gain += avg_ret
                    else:
                        total_loss += abs(avg_ret)
                else:
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
    
    def _test_foreign_flow_sell_strategies(self):
        """
        외국인 매매동향 + MDD 기반 매도/하락 전략
        - 외국인 대량 매도 + 기술적 과열
        - MDD 내 단기 반등 실패 (Dead Cat Bounce) 포착
        """
        has_foreign = 'foreign_sell5_sig' in self.df.columns
        has_mdd     = 'rolling_mdd' in self.df.columns

        test_count = 0
        found_before = len(self.strategies)

        if has_foreign:
            sell5  = self.df['foreign_sell5_sig']  == 1
            sell10 = self.df['foreign_sell10_sig'] == 1
            turn_s = self.df.get('foreign_turn_sell', pd.Series(0, index=self.df.index)) == 1

            # 1. 외국인 강한 매도(하위 5%) + 기술적 과열
            for rsi_th in [60, 65, 68, 70]:
                sig = sell5 & (self.df['RSI'] >= rsi_th)
                self._evaluate_strategy(f"외국인하위5%매도 + RSI{rsi_th}+", sig, 'reversal', None, None)
                test_count += 1

            for mfi_th in [60, 65, 70, 75]:
                sig = sell5 & (self.df['MFI'] >= mfi_th)
                self._evaluate_strategy(f"외국인하위5%매도 + MFI{mfi_th}+", sig, 'reversal', None, None)
                test_count += 1

            # 외국인 하위 5% + ADX 강세
            for adx_th in [25, 30, 35]:
                sig = sell5 & (self.df['ADX'] >= adx_th)
                self._evaluate_strategy(f"외국인하위5%매도 + ADX{adx_th}+", sig, 'reversal', None, None)
                test_count += 1

            # 2. 외국인 매도 전환 + 과열 조합
            for adx_th in [25, 30]:
                for rsi_th in [60, 65]:
                    sig = turn_s & (self.df['ADX'] >= adx_th) & (self.df['RSI'] >= rsi_th)
                    self._evaluate_strategy(
                        f"외국인매도전환 + ADX{adx_th}+ + RSI{rsi_th}+",
                        sig, 'reversal', None, None
                    )
                    test_count += 1

            # 외국인 매도 전환 + MACD Dead
            macd_dead = (
                (self.df['MACD'] < self.df['MACD_Signal']) &
                (self.df['MACD'].shift(1) >= self.df['MACD_Signal'].shift(1))
            )
            for rsi_th in [60, 65]:
                sig = turn_s & macd_dead & (self.df['RSI'] >= rsi_th)
                self._evaluate_strategy(
                    f"외국인매도전환 + MACD데드 + RSI{rsi_th}+",
                    sig, 'reversal', None, None
                )
                test_count += 1

            # 3. 외국인 5일 누적 강한 매도 + 이격도 과열
            if 'foreign_5d_cum' in self.df.columns:
                pct10 = self.df['foreign_5d_cum'].dropna().quantile(0.10)
                if not pd.isna(pct10) and pct10 < 0:
                    strong_sell5d = self.df['foreign_5d_cum'] <= pct10
                    for ma in [10, 20, 60]:
                        disp_col = f'Disparity_{ma}'
                        if disp_col not in self.df.columns:
                            continue
                        for disp_th in [105, 108, 112, 116]:
                            sig = strong_sell5d & (self.df[disp_col] >= disp_th)
                            self._evaluate_strategy(
                                f"외국인5일강매도10% + 이격도{disp_th}(MA{ma})+",
                                sig, 'reversal', disp_th, ma
                            )
                            test_count += 1

        # 4. MDD 내 단기 반등 실패 (Dead Cat Bounce) — MDD < -20% 상태에서 반등 후 다시 하락
        if has_mdd:
            severe = self.df['mdd_severe']   # -20% 이하

            # MDD -20% 구간에서 단기 이격도 상승 = 반등이나 지속 불가 신호
            for ma in [5, 10, 20]:
                disp_col = f'Disparity_{ma}' if f'Disparity_{ma}' in self.df.columns else None
                if disp_col is None:
                    # 임시 이격도 계산
                    ma_col = f'MA{ma}'
                    if ma_col not in self.df.columns:
                        continue
                    disp_vals = (self.df['close'] / self.df[ma_col]) * 100
                else:
                    disp_vals = self.df[disp_col]

                for disp_th in [102, 104, 106]:
                    sig = severe & (disp_vals >= disp_th) & (self.df['ADX'] >= 30)
                    self._evaluate_strategy(
                        f"MDD-20%중반등실패 + 이격도{disp_th}(MA{ma})+ + ADX30+",
                        sig, 'reversal', disp_th, ma
                    )
                    test_count += 1

        # ── 외국인 + MDD 복합 매도 ──────────────────────────
        if has_foreign and has_mdd:
            sell5  = self.df['foreign_sell5_sig']  == 1
            sell10 = self.df['foreign_sell10_sig'] == 1
            severe = self.df['mdd_severe']

            # 5. MDD 구간 + 외국인 강한 매도 (추세 하락 지속 신호)
            for rsi_th in [55, 60, 65]:
                sig = severe & sell5 & (self.df['RSI'] >= rsi_th)
                self._evaluate_strategy(
                    f"MDD-20%이하 + 외국인하위5% + RSI{rsi_th}+",
                    sig, 'reversal', None, None
                )
                test_count += 1

            sig = severe & sell10
            self._evaluate_strategy("MDD-20%이하 + 외국인하위10%매도", sig, 'reversal', None, None)
            test_count += 1

        new_found = len(self.strategies) - found_before
        print(f"   ✅ 외국인+MDD 매도 전략 테스트 완료: {test_count}회, 발견: {new_found}개")

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

        # ============================================
        # 추가: BB Squeeze + 과열 반전 전략
        # ============================================
        if 'BB_width' in self.df.columns:
            # BB폭 하위 25% = squeeze 상태 (변동성 수축 후 돌파)
            bb_width_q25 = self.df['BB_width'].rolling(250).quantile(0.25)
            bb_squeezed = self.df['BB_width'] <= bb_width_q25

            for rsi_th in rev_rsi[::2]:
                signals = bb_squeezed & (self.df['RSI'] >= rsi_th)
                self._evaluate_strategy(
                    f"BB수축(하위25%) + RSI{rsi_th}+",
                    signals, 'reversal', None, None
                )
                test_count += 1

            for mfi_th in rev_mfi[::2]:
                signals = bb_squeezed & (self.df['MFI'] >= mfi_th)
                self._evaluate_strategy(
                    f"BB수축(하위25%) + MFI{mfi_th}+",
                    signals, 'reversal', None, None
                )
                test_count += 1

            # BB 상단 근접 + squeeze 해제 (폭 급확대) = 강한 매도 신호
            bb_expanding = (
                self.df['BB_width'] > bb_width_q25 * 1.5
            ) & (
                self.df['BB_width'].shift(3) <= bb_width_q25
            )
            for rsi_th in rev_rsi[::2]:
                signals = bb_expanding & (self.df['RSI'] >= rsi_th)
                self._evaluate_strategy(
                    f"BB확대반전 + RSI{rsi_th}+",
                    signals, 'reversal', None, None
                )
                test_count += 1

        # ============================================
        # 추가: 연속 N일 과열 지속 후 반전 (더 강한 신호)
        # ============================================
        for n_days in [2, 3]:
            # N일 연속 RSI 과열 후 하락 시작
            for rsi_th in rev_rsi[::3]:
                rsi_hot_ndays = True
                for k in range(n_days):
                    rsi_hot_ndays = rsi_hot_ndays & (self.df['RSI'].shift(k) >= rsi_th)
                rsi_reversal_after = rsi_hot_ndays & (self.df['RSI'] < self.df['RSI'].shift(1))
                self._evaluate_strategy(
                    f"RSI{rsi_th}+{n_days}일연속후반전",
                    rsi_reversal_after, 'reversal', None, None
                )
                test_count += 1

            # N일 연속 MACD 음전 + 이격도 과열
            macd_neg_ndays = True
            for k in range(n_days):
                macd_neg_ndays = macd_neg_ndays & (self.df['MACD_Hist'].shift(k) < 0)
            for disp_th in [110, 115, 120]:
                for ma in [20, 40, 60]:
                    disp_col = f'Disparity_{ma}'
                    if disp_col not in self.df.columns:
                        continue
                    signals = macd_neg_ndays & (self.df[disp_col] >= disp_th)
                    self._evaluate_strategy(
                        f"MACD음전{n_days}일+이격도{disp_th}(MA{ma})",
                        signals, 'reversal', disp_th, ma
                    )
                    test_count += 1

        # ============================================
        # 추가: ADX 고강도 + 하락반전 조합 (강한 추세 중 전환 포착)
        # ============================================
        if 'ADX' in self.df.columns and '-DI' in self.df.columns:
            for adx_th in [35, 40, 45, 50]:
                for rsi_th in rev_rsi[::2]:
                    # ADX 강한 추세 + RSI 과열 + MACD 데드
                    signals = (
                        (self.df['ADX'] >= adx_th) &
                        (self.df['-DI'] > self.df['+DI']) &
                        (self.df['RSI'] >= rsi_th)
                    )
                    self._evaluate_strategy(
                        f"ADX{adx_th}+(-DI우세) + RSI{rsi_th}+",
                        signals, 'reversal', None, None
                    )
                    test_count += 1

                    # ADX + MACD Dead + 이격도
                    for disp_th in [110, 115, 120]:
                        for ma in [20, 60]:
                            disp_col = f'Disparity_{ma}'
                            if disp_col not in self.df.columns:
                                continue
                            signals = (
                                (self.df['ADX'] >= adx_th) &
                                macd_dead &
                                (self.df[disp_col] >= disp_th)
                            )
                            self._evaluate_strategy(
                                f"ADX{adx_th}+ + MACD데드 + 이격도{disp_th}(MA{ma})",
                                signals, 'reversal', disp_th, ma
                            )
                            test_count += 1

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
            
            # 20일 후 결과 평가 — direction에 따라 승패 정의
            ret20 = result.get('return_20d')
            if ret20 is not None:
                returns_20d.append(ret20)
                if self.direction == 'long':
                    # 매수 신호: 상승=성공
                    if ret20 > 0:
                        wins += 1
                        total_gain += ret20
                    else:
                        total_loss += abs(ret20)
                else:
                    # 매도 신호: 하락=성공
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
        
        # Profit Factor (총 이익 / 총 손실)
        profit_factor = (total_gain / total_loss) if total_loss > 0 else float('inf')
        min_pf = BACKTEST_PARAMS.get('min_profit_factor', 1.3)
        if profit_factor < min_pf:
            return
        
        # 평균 수익률 (20일 기준)
        avg_return = np.mean(returns_20d)
        
        # 최대 역행 (Max Adverse Excursion) — direction에 따라 반대방향 최대
        if self.direction == 'long':
            # 매수 신호: 최대 하락폭 (가장 음수)
            max_adverse = abs(min(returns_20d)) if returns_20d else 0
        else:
            # 매도 신호: 최대 상승폭 (가장 양수)
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
                # direction에 따른 승리 조건
                if self.direction == 'long':
                    if r['return_20d'] > 0:
                        trend_counts[t][1] += 1
                else:
                    if r['return_20d'] < 0:
                        trend_counts[t][1] += 1
            for t, (cnt, wins_t) in trend_counts.items():
                if cnt >= 2:
                    trend_win_rates[t] = {
                        'win_rate': (wins_t / cnt) * 100,
                        'count': cnt
                    }
        
        # ── Inverse Strategy Test (과적합 진단) ──
        inverse_win_rate = None
        inverse_passed = True
        if INVERSE_TEST.get('enabled', True) and returns_20d:
            if self.direction == 'long':
                inverse_wins = sum(1 for r in returns_20d if r < 0)
            else:
                inverse_wins = sum(1 for r in returns_20d if r > 0)
            inverse_win_rate = (inverse_wins / len(returns_20d)) * 100
            inverse_passed = inverse_win_rate <= INVERSE_TEST.get('max_inverse_winrate', 45)

        # ── MFE (Maximum Favorable Excursion): 보유 기간 내 최대 유리한 이동 ──
        mfe_list = []
        optimal_days_votes = {}
        for r in forward_returns:
            favorable_returns = {}
            for d in BACKTEST_PARAMS['forward_days']:
                ret = r.get(f'return_{d}d')
                if ret is None:
                    continue
                if self.direction == 'long':
                    if ret > 0:
                        favorable_returns[d] = ret
                else:
                    if ret < 0:
                        favorable_returns[d] = abs(ret)
            if favorable_returns:
                best_d = max(favorable_returns, key=favorable_returns.get)
                mfe_list.append(favorable_returns[best_d])
                optimal_days_votes[best_d] = optimal_days_votes.get(best_d, 0) + 1
            else:
                mfe_list.append(0.0)

        avg_mfe = float(np.mean(mfe_list)) if mfe_list else 0.0
        # 최적 보유일: 가장 많은 신호에서 최대 이익이 난 D+N
        optimal_hold_days = max(optimal_days_votes, key=optimal_days_votes.get) if optimal_days_votes else 20

        # ── 기간별 평균 수익률 (전 forward_days 기준) ──
        avg_returns_by_period = {}
        for d in BACKTEST_PARAMS['forward_days']:
            rets = [r.get(f'return_{d}d') for r in forward_returns if r.get(f'return_{d}d') is not None]
            if rets:
                avg_returns_by_period[d] = float(np.mean(rets))

        # ── 현재 레짐 승률 (현재 trend_type과 동일한 시점의 신호만) ──
        regime_win_rate = None
        regime_count = 0
        if self._trend_label_map is not None:
            regime_wins = 0
            for r in forward_returns:
                t = self._trend_label_map.get(r['signal_date'], self.trend_type)
                if t == self.trend_type and r.get('return_20d') is not None:
                    regime_count += 1
                    ret20 = r['return_20d']
                    if self.direction == 'long':
                        if ret20 > 0:
                            regime_wins += 1
                    else:
                        if ret20 < 0:
                            regime_wins += 1
            if regime_count >= 2:
                regime_win_rate = (regime_wins / regime_count) * 100
        
        # 전략 저장
        strategy_dict = {
            'name': name,
            'type': strategy_type,
            'direction': self.direction,
            'disparity': disparity,
            'ma_period': ma_period,
            'signal_count': len(deduped_indices),
            'valid_signal_count': valid_count,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'avg_return': avg_return,
            'max_adverse': max_adverse,
            'avg_mfe': avg_mfe,                      # 평균 최대 유리 이동 (MFE)
            'optimal_hold_days': optimal_hold_days,  # 최적 보유일
            'avg_returns_by_period': avg_returns_by_period,  # 기간별 평균 수익률
            'regime_win_rate': regime_win_rate,      # 현재 레짐 한정 승률
            'regime_count': regime_count,            # 현재 레짐 신호 수
            'forward_returns': forward_returns,
            'trend_type': self.trend_type,
            'trend_win_rates': trend_win_rates,
            'inverse_win_rate': inverse_win_rate,
            'inverse_passed': inverse_passed,
        }
        
        self.strategies.append(strategy_dict)
    
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
