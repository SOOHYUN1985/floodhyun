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
    
    def __init__(self, strategies: List[Dict]):
        """
        Args:
            strategies: 백테스트 결과 전략 리스트
        """
        self.strategies = strategies
        self.selected = []
    
    def select_diverse_strategies(self) -> List[Dict]:
        """
        유사도가 낮은 다양한 전략 선정
        
        Returns:
            선정된 전략 리스트
        """
        if len(self.strategies) == 0:
            return []
        
        print(f"\n{'─'*60}")
        print(f"🎯 전략 선정 (유사도 < {SIMILARITY_THRESHOLD*100:.0f}%)")
        print(f"{'─'*60}")
        
        # 승률 기준 정렬
        sorted_strategies = sorted(
            self.strategies,
            key=lambda x: (x['win_rate'], x['signal_count']),
            reverse=True
        )
        
        self.selected = []
        
        for strategy in sorted_strategies:
            if len(self.selected) >= MAX_SELECTED_STRATEGIES:
                break
            
            # 기존 선정 전략과의 유사도 확인
            if self._is_diverse(strategy):
                self.selected.append(strategy)
                print(f"   ✅ 선정: {strategy['name']}")
                print(f"      승률: {strategy['win_rate']:.1f}% | 신호: {strategy['signal_count']}개")
        
        print(f"\n   📊 총 {len(self.selected)}개 전략 선정")
        
        return self.selected
    
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
