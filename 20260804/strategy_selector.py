"""
전략 선정기
- 유사도 기반 다각화된 전략 선정
- 중복 제거 및 최적 전략 조합
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple
import logging

from config import SIMILARITY_THRESHOLD, MAX_SELECTED_STRATEGIES

logger = logging.getLogger(__name__)


class StrategySelector:
    """전략 선정기"""
    
    def __init__(self, strategies: List[Dict], current_trend: str = None):
        """
        Args:
            strategies: 백테스트 결과 전략 리스트
            current_trend: 현재 시장 추세 ('bull'/'sideways'/'bear')
        """
        self.strategies = strategies
        self.current_trend = current_trend
        self.selected = []
    
    def select_diverse_strategies(self) -> List[Dict]:
        """
        복합 점수(승률 + Profit Factor + 레짐 가중) 기반 다각화 선정
        
        Returns:
            선정된 전략 리스트
        """
        if len(self.strategies) == 0:
            return []
        
        print(f"\n{'─'*60}")
        print(f"🎯 전략 선정 (유사도 < {SIMILARITY_THRESHOLD*100:.0f}%, 복합 스코어)")
        print(f"{'─'*60}")
        
        # 복합 점수 산출 후 정렬
        scored = []
        for s in self.strategies:
            score = self._composite_score(s)
            scored.append((score, s))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        
        self.selected = []
        
        for score, strategy in scored:
            if len(self.selected) >= MAX_SELECTED_STRATEGIES:
                break
            
            # 기존 선정 전략과의 유사도 확인
            if self._is_diverse(strategy):
                self.selected.append(strategy)
                pf = strategy.get('profit_factor', 0)
                pf_str = f"{pf:.1f}" if pf != float('inf') else "∞"
                regime_wr = self._get_regime_win_rate(strategy)
                print(f"   ✅ 선정: {strategy['name']}")
                print(f"      승률: {strategy['win_rate']:.1f}% | PF: {pf_str} | 레짐승률: {regime_wr:.0f}% | 신호: {strategy['signal_count']}개 | 점수: {score:.1f}")
        
        print(f"\n   📊 총 {len(self.selected)}개 전략 선정")
        
        return self.selected
    
    def _composite_score(self, strategy: Dict) -> float:
        """
        복합 전략 점수 산출 (v2 — 리스크 조정 지표 통합)
        
        구성:
          - 승률 (25% 가중) — 거래비용 차감 시 net 승률 우선
          - Profit Factor (15% 가중, capped at 5)
          - 현재 레짐 승률 (10% 가중)
          - 신호 수 보너스 (5% 가중)
          - MAE 패널티 (10% 가중)
          - OOS 승률 보너스 (10% 가중)
          - Sharpe Ratio (10% 가중) — 위험 대비 수익
          - Sortino Ratio (5% 가중) — 하방 위험 대비 수익
          - 신호 빈도 적정성 (5% 가중) — 너무 잦거나 드물면 감점
          - Inverse 통과 (5% 가중) — 진짜 신호 검증
        """
        # 거래비용 차감 net 값 우선 사용
        win_rate = strategy.get('win_rate_net', strategy['win_rate'])
        pf_raw = strategy.get('profit_factor_net', strategy.get('profit_factor', 1.0))
        
        # Profit Factor (cap at 5 to prevent inf distortion)
        pf = min(pf_raw, 5.0)
        pf_score = (pf / 5.0) * 100
        
        # 현재 레짐 승률
        regime_wr = self._get_regime_win_rate(strategy)
        
        # 신호 수 보너스
        sig_count = strategy.get('valid_signal_count', strategy['signal_count'])
        sig_score = min(100, max(0, (np.log(sig_count / 5) / np.log(10)) * 100))
        
        # MAE 패널티
        max_adverse = strategy.get('max_adverse', 10)
        mae_score = max(0, 100 - (max_adverse * 5))
        
        # OOS 승률 보너스
        oos_wr = strategy.get('oos_win_rate')
        if oos_wr is not None:
            oos_score = oos_wr
        else:
            oos_score = win_rate * 0.7
        
        # Sharpe Ratio (0~3 정상 범위 → 0~100 스케일)
        sharpe = strategy.get('sharpe_ratio', 0)
        sharpe_score = max(0, min(100, sharpe * 33.3))
        
        # Sortino Ratio
        sortino = strategy.get('sortino_ratio', 0)
        if sortino == float('inf'):
            sortino_score = 100
        else:
            sortino_score = max(0, min(100, sortino * 25.0))
        
        # 신호 빈도 적정성
        freq_score = strategy.get('signal_interval', {}).get('frequency_score', 50)
        
        # Inverse Test 통과 보너스
        inv_score = 100 if strategy.get('inverse_passed', True) else 0
        
        composite = (
            win_rate * 0.25 +
            pf_score * 0.15 +
            regime_wr * 0.10 +
            sig_score * 0.05 +
            mae_score * 0.10 +
            oos_score * 0.10 +
            sharpe_score * 0.10 +
            sortino_score * 0.05 +
            freq_score * 0.05 +
            inv_score * 0.05
        )
        return composite
    
    def _get_regime_win_rate(self, strategy: Dict) -> float:
        """현재 레짐에서의 승률 (없으면 전체 승률 반환)"""
        if self.current_trend is None:
            return strategy['win_rate']
        
        trend_wr = strategy.get('trend_win_rates', {})
        regime_data = trend_wr.get(self.current_trend)
        if regime_data and regime_data.get('count', 0) >= 2:
            return regime_data['win_rate']
        return strategy['win_rate']
    
    def _is_diverse(self, new_strategy: Dict) -> bool:
        """
        새 전략이 기존 전략들과 충분히 다른지 확인
        
        Args:
            new_strategy: 검사할 전략
        
        Returns:
            충분히 다르면 True
        """
        if len(self.selected) == 0:
            return True
        
        new_signals = set(new_strategy['forward_returns'][i]['signal_date'] 
                        for i in range(len(new_strategy['forward_returns'])))
        
        for existing in self.selected:
            existing_signals = set(existing['forward_returns'][i]['signal_date'] 
                                  for i in range(len(existing['forward_returns'])))
            
            # 신호 중복률 계산
            if len(new_signals) == 0 or len(existing_signals) == 0:
                continue
            
            overlap = len(new_signals & existing_signals)
            similarity = overlap / max(len(new_signals), len(existing_signals))
            
            if similarity > SIMILARITY_THRESHOLD:
                return False
        
        return True
    
    def _calculate_signal_vector(self, strategy: Dict) -> np.ndarray:
        """전략의 신호를 벡터로 변환"""
        # 모든 날짜 수집
        all_dates = set()
        for s in self.strategies:
            for fr in s['forward_returns']:
                all_dates.add(fr['signal_date'])
        
        all_dates = sorted(all_dates)
        date_to_idx = {d: i for i, d in enumerate(all_dates)}
        
        # 벡터 생성
        vector = np.zeros(len(all_dates))
        for fr in strategy['forward_returns']:
            idx = date_to_idx[fr['signal_date']]
            vector[idx] = 1
        
        return vector
    
    def get_strategy_summary(self) -> Dict:
        """선정된 전략 요약"""
        if not self.selected:
            return {}
        
        avg_win_rate = np.mean([s['win_rate'] for s in self.selected])
        total_signals = sum(s['signal_count'] for s in self.selected)
        
        # 타입별 분류
        breakout_count = sum(1 for s in self.selected if s['type'] == 'breakout')
        reversal_count = sum(1 for s in self.selected if s['type'] == 'reversal')
        
        return {
            'total_strategies': len(self.selected),
            'avg_win_rate': avg_win_rate,
            'total_signals': total_signals,
            'breakout_strategies': breakout_count,
            'reversal_strategies': reversal_count,
            'strategies': self.selected
        }


def select_strategies(strategies: List[Dict]) -> List[Dict]:
    """
    간편 전략 선정 함수
    
    Args:
        strategies: 백테스트 결과 전략 리스트
    
    Returns:
        선정된 전략 리스트
    """
    selector = StrategySelector(strategies)
    return selector.select_diverse_strategies()


if __name__ == '__main__':
    # 테스트용 더미 데이터
    from data_loader import load_data
    from peak_detector import PeakDetector
    from trend_analyzer import analyze_market_trend
    
    df = load_data('kospi')
    trend_type, _, _ = analyze_market_trend(df)
    
    detector = PeakDetector(df, trend_type)
    strategies = detector.run_backtest()
    
    selector = StrategySelector(strategies)
    selected = selector.select_diverse_strategies()
    
    print(f"\n선정된 전략: {len(selected)}개")
