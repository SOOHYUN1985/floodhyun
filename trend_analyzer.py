"""
시장 추세 분석기
- 상승장/횡보장/하락장 판단
- 100점 만점 스코어링 시스템
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class TrendAnalyzer:
    """시장 추세 분석기"""
    
    def __init__(self, df: pd.DataFrame):
        """
        Args:
            df: 지표가 계산된 데이터프레임
        """
        self.df = df
        self.current = df.iloc[-1]
        self.current_price = self.current['close']
        self.current_date = df.index[-1]
        
        # 분석 결과
        self.trend_type = None  # 'bull', 'sideways', 'bear'
        self.trend_score = 0
        self.confidence = 0
        self.details = {}
    
    def analyze(self) -> Dict:
        """
        종합 추세 분석
        
        Returns:
            분석 결과 딕셔너리
        """
        scores = {}
        
        # 1. 이동평균선 배열 분석 (+/- 100점)
        scores['ma_arrangement'] = self._analyze_ma_arrangement()
        
        # 2. 이동평균선 기울기 분석 (+/- 100점)
        scores['ma_slope'] = self._analyze_ma_slope()
        
        # 3. 가격 모멘텀 분석 (+/- 50점)
        scores['momentum'] = self._analyze_momentum()
        
        # 4. ADX 추세 강도 분석 (0-50점, 방향성 없음)
        scores['adx'] = self._analyze_adx()
        
        # 5. 볼린저밴드 위치 분석 (+/- 30점)
        scores['bb_position'] = self._analyze_bb_position()
        
        # 총점 계산 (ADX 제외한 방향성 점수)
        directional_score = (
            scores['ma_arrangement'] +
            scores['ma_slope'] +
            scores['momentum'] +
            scores['bb_position']
        )
        
        self.trend_score = directional_score
        
        # 추세 판단
        if directional_score >= 100:
            self.trend_type = 'bull'
            self.confidence = min(100, 50 + scores['adx'])
        elif directional_score <= -100:
            self.trend_type = 'bear'
            self.confidence = min(100, 50 + scores['adx'])
        else:
            self.trend_type = 'sideways'
            self.confidence = max(0, 100 - abs(directional_score))
        
        self.details = {
            'trend_type': self.trend_type,
            'trend_score': self.trend_score,
            'confidence': self.confidence,
            'scores': scores,
            'current_price': self.current_price,
            'current_date': self.current_date
        }
        
        return self.details
    
    def _analyze_ma_arrangement(self) -> int:
        """이동평균선 배열 분석"""
        score = 0
        
        # MA20, MA60, MA120 배열 확인
        ma20 = self.current.get('MA20', self.current_price)
        ma60 = self.current.get('MA60', self.current_price)
        ma120 = self.current.get('MA100', self.current_price)
        
        # 정배열 (상승): 가격 > MA20 > MA60 > MA120
        if self.current_price > ma20 > ma60:
            score += 50
        if ma20 > ma60 > ma120:
            score += 50
        
        # 역배열 (하락): 가격 < MA20 < MA60 < MA120
        if self.current_price < ma20 < ma60:
            score -= 50
        if ma20 < ma60 < ma120:
            score -= 50
        
        return score
    
    def _analyze_ma_slope(self) -> int:
        """이동평균선 기울기 분석"""
        score = 0
        
        # 20일 이평선 기울기
        if 'MA20' in self.df.columns:
            ma20_now = self.df['MA20'].iloc[-1]
            ma20_5d = self.df['MA20'].iloc[-6] if len(self.df) > 6 else ma20_now
            slope_20 = (ma20_now - ma20_5d) / ma20_5d * 100
            
            if slope_20 > 1:
                score += 50
            elif slope_20 > 0.5:
                score += 25
            elif slope_20 < -1:
                score -= 50
            elif slope_20 < -0.5:
                score -= 25
        
        # 60일 이평선 기울기
        if 'MA60' in self.df.columns:
            ma60_now = self.df['MA60'].iloc[-1]
            ma60_20d = self.df['MA60'].iloc[-21] if len(self.df) > 21 else ma60_now
            slope_60 = (ma60_now - ma60_20d) / ma60_20d * 100
            
            if slope_60 > 2:
                score += 50
            elif slope_60 > 1:
                score += 25
            elif slope_60 < -2:
                score -= 50
            elif slope_60 < -1:
                score -= 25
        
        return score
    
    def _analyze_momentum(self) -> int:
        """가격 모멘텀 분석"""
        score = 0
        
        # 5일 수익률
        ret_5d = (self.df['close'].iloc[-1] / self.df['close'].iloc[-6] - 1) * 100
        if ret_5d > 3:
            score += 15
        elif ret_5d > 1:
            score += 10
        elif ret_5d < -3:
            score -= 15
        elif ret_5d < -1:
            score -= 10
        
        # 20일 수익률
        if len(self.df) > 20:
            ret_20d = (self.df['close'].iloc[-1] / self.df['close'].iloc[-21] - 1) * 100
            if ret_20d > 10:
                score += 20
            elif ret_20d > 5:
                score += 10
            elif ret_20d < -10:
                score -= 20
            elif ret_20d < -5:
                score -= 10
        
        # 60일 수익률
        if len(self.df) > 60:
            ret_60d = (self.df['close'].iloc[-1] / self.df['close'].iloc[-61] - 1) * 100
            if ret_60d > 15:
                score += 15
            elif ret_60d > 8:
                score += 10
            elif ret_60d < -15:
                score -= 15
            elif ret_60d < -8:
                score -= 10
        
        return score
    
    def _analyze_adx(self) -> int:
        """ADX 추세 강도 분석 (0-50점, 추세가 강할수록 높은 점수)"""
        adx = self.current.get('ADX', 20)
        
        if pd.isna(adx):
            return 25  # 기본값
        
        if adx >= 40:
            return 50  # 매우 강한 추세
        elif adx >= 30:
            return 40
        elif adx >= 25:
            return 30
        elif adx >= 20:
            return 20
        else:
            return 10  # 약한 추세
    
    def _analyze_bb_position(self) -> int:
        """볼린저밴드 위치 분석"""
        if 'BB_upper' not in self.df.columns:
            return 0
        
        bb_upper = self.current['BB_upper']
        bb_lower = self.current['BB_lower']
        bb_middle = self.current['BB_middle']
        
        # 밴드 내 위치 계산 (0-100%)
        bb_range = bb_upper - bb_lower
        if bb_range == 0:
            return 0
        
        position = (self.current_price - bb_lower) / bb_range * 100
        
        if position > 90:
            return 30  # 상단 돌파 근접
        elif position > 70:
            return 15
        elif position < 10:
            return -30  # 하단 돌파 근접
        elif position < 30:
            return -15
        else:
            return 0
    
    def get_trend_name(self) -> str:
        """추세명 반환"""
        names = {
            'bull': '📈 상승장 (Bull Market)',
            'sideways': '↔️ 횡보장 (Sideways)',
            'bear': '📉 하락장 (Bear Market)'
        }
        return names.get(self.trend_type, '알 수 없음')
    
    def print_analysis(self):
        """분석 결과 출력"""
        if not self.details:
            self.analyze()
        
        print(f"\n{'='*60}")
        print(f"📊 시장 추세 분석")
        print(f"{'='*60}")
        print(f"📅 분석일: {self.current_date.strftime('%Y-%m-%d')}")
        print(f"💰 현재가: {self.current_price:,.2f}")
        print(f"\n{'─'*60}")
        
        scores = self.details['scores']
        print(f"【점수 상세】")
        print(f"  이동평균 배열: {scores['ma_arrangement']:+d}점")
        print(f"  이동평균 기울기: {scores['ma_slope']:+d}점")
        print(f"  가격 모멘텀: {scores['momentum']:+d}점")
        print(f"  볼린저밴드: {scores['bb_position']:+d}점")
        print(f"  ADX 강도: {scores['adx']:+d}점")
        print(f"  ────────────────────")
        print(f"  총점: {self.trend_score:+d}점")
        
        print(f"\n{'─'*60}")
        print(f"【종합 판단】")
        print(f"  {self.get_trend_name()}")
        print(f"  신뢰도: {self.confidence}%")
        print(f"{'='*60}")


def analyze_market_trend(df: pd.DataFrame) -> Tuple[str, int, Dict]:
    """
    간편 추세 분석 함수
    
    Args:
        df: 지표가 계산된 데이터프레임
    
    Returns:
        (trend_type, confidence, details)
    """
    analyzer = TrendAnalyzer(df)
    details = analyzer.analyze()
    return analyzer.trend_type, analyzer.confidence, details


if __name__ == '__main__':
    from data_loader import load_data
    
    # 코스피 분석
    df = load_data('kospi')
    analyzer = TrendAnalyzer(df)
    analyzer.analyze()
    analyzer.print_analysis()
