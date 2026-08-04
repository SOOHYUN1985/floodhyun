"""
시장 추세 분석기 v2
- 상승장/횡보장/하락장 판단 (현재 시점)
- 과거 전체 시점별 추세 레이블링 (백테스트용)
- 시장 국면 전환 감지 (상승→하락, 하락→상승)
- 거래량, MACD 확인 신호 통합
- 100점 만점 스코어링 시스템
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class TrendAnalyzer:
    """시장 추세 분석기 v2"""
    
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
        self.transition = None  # 'bull_to_bear', 'bear_to_bull', None
        self.details = {}
    
    def analyze(self) -> Dict:
        """
        종합 추세 분석 (현재 시점)
        
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
        
        # 6. MACD 방향 분석 (+/- 40점) ← 신규
        scores['macd'] = self._analyze_macd()
        
        # 7. 거래량 추세 분석 (+/- 30점) ← 신규
        scores['volume_trend'] = self._analyze_volume_trend()
        
        # 총점 계산 (ADX 제외한 방향성 점수)
        directional_score = (
            scores['ma_arrangement'] +
            scores['ma_slope'] +
            scores['momentum'] +
            scores['bb_position'] +
            scores['macd'] +
            scores['volume_trend']
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
        
        # 국면 전환 감지
        self.transition = self._detect_transition()
        
        self.details = {
            'trend_type': self.trend_type,
            'trend_score': self.trend_score,
            'confidence': self.confidence,
            'transition': self.transition,
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
        ma120 = self.current.get('MA120', self.current_price)
        
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
    
    def _analyze_macd(self) -> int:
        """MACD 방향 분석 (신규)"""
        if 'MACD' not in self.df.columns or 'MACD_Signal' not in self.df.columns:
            return 0
        
        score = 0
        macd = self.current.get('MACD', 0)
        signal = self.current.get('MACD_Signal', 0)
        hist = self.current.get('MACD_Hist', 0)
        
        if pd.isna(macd) or pd.isna(signal):
            return 0
        
        # MACD > Signal (골든크로스 상태) = 상승 추세
        if macd > signal:
            score += 20
        else:
            score -= 20
        
        # MACD 히스토그램 방향 (추세 가속/감속)
        if len(self.df) > 2 and 'MACD_Hist' in self.df.columns:
            hist_now = self.df['MACD_Hist'].iloc[-1]
            hist_prev = self.df['MACD_Hist'].iloc[-2]
            if not pd.isna(hist_now) and not pd.isna(hist_prev):
                if hist_now > 0 and hist_now > hist_prev:
                    score += 20  # 상승 추세 가속
                elif hist_now < 0 and hist_now < hist_prev:
                    score -= 20  # 하락 추세 가속
        
        return score
    
    def _analyze_volume_trend(self) -> int:
        """거래량 추세 분석 (신규)"""
        if 'Volume_Ratio' not in self.df.columns:
            return 0
        
        score = 0
        
        vol_ratio = self.current.get('Volume_Ratio', 1.0)
        if pd.isna(vol_ratio):
            return 0
        
        # 가격 방향과 거래량 동조 여부 확인
        if len(self.df) > 5:
            price_change_5d = (self.df['close'].iloc[-1] / self.df['close'].iloc[-6] - 1)
            vol_avg_5d = self.df['Volume_Ratio'].iloc[-5:].mean()
            
            if pd.isna(vol_avg_5d):
                return 0
            
            if price_change_5d > 0 and vol_avg_5d > 1.2:
                # 상승 + 거래량 증가 = 추세 확인
                score += 15
            elif price_change_5d > 0 and vol_avg_5d < 0.8:
                # 상승 + 거래량 감소 = 추세 약화 경고
                score -= 10
            elif price_change_5d < 0 and vol_avg_5d > 1.5:
                # 하락 + 거래량 급증 = 패닉 셀링
                score -= 15
            elif price_change_5d < 0 and vol_avg_5d < 0.8:
                # 하락 + 거래량 감소 = 약한 조정
                score += 10
        
        # OBV 추세 확인
        if 'OBV' in self.df.columns and 'OBV_MA20' in self.df.columns:
            obv = self.current.get('OBV', 0)
            obv_ma = self.current.get('OBV_MA20', 0)
            if not pd.isna(obv) and not pd.isna(obv_ma) and obv_ma != 0:
                if obv > obv_ma:
                    score += 15  # OBV 상승 추세
                else:
                    score -= 15  # OBV 하락 추세
        
        return score
    
    def _detect_transition(self) -> str:
        """
        시장 국면 전환 감지
        최근 20일과 이전 20일의 추세 점수를 비교하여
        상승→하락 또는 하락→상승 전환 여부 판단
        """
        if len(self.df) < 60:
            return None
        
        # 최근 20일 vs 이전 20~40일 전 추세 비교
        recent_scores = []
        past_scores = []
        
        for offset in range(1, 21):
            idx = -offset
            if abs(idx) >= len(self.df):
                break
            s = self._score_at(idx)
            recent_scores.append(s)
        
        for offset in range(21, 41):
            idx = -offset
            if abs(idx) >= len(self.df):
                break
            s = self._score_at(idx)
            past_scores.append(s)
        
        if not recent_scores or not past_scores:
            return None
        
        recent_avg = np.mean(recent_scores)
        past_avg = np.mean(past_scores)
        
        # 전환 판단: 평균 점수가 크게 변했으면 전환 중
        diff = recent_avg - past_avg
        
        if past_avg > 50 and recent_avg < -20:
            return 'bull_to_bear'
        elif past_avg < -50 and recent_avg > 20:
            return 'bear_to_bull'
        elif diff < -80:
            return 'bull_to_bear'
        elif diff > 80:
            return 'bear_to_bull'
        
        return None
    
    def _score_at(self, iloc_idx: int) -> float:
        """특정 시점의 간이 추세 점수 계산 (MA배열 + 모멘텀)"""
        row = self.df.iloc[iloc_idx]
        price = row['close']
        score = 0
        
        ma20 = row.get('MA20', price)
        ma60 = row.get('MA60', price)
        ma120 = row.get('MA120', price)
        
        if pd.isna(ma20) or pd.isna(ma60) or pd.isna(ma120):
            return 0
        
        # MA 배열
        if price > ma20 > ma60 > ma120:
            score += 100
        elif price < ma20 < ma60 < ma120:
            score -= 100
        elif price > ma20 > ma60:
            score += 50
        elif price < ma20 < ma60:
            score -= 50
        
        return score
    
    def label_all_trends(self) -> pd.Series:
        """
        과거 전체 시점에 대해 추세 레이블링 (백테스트용)
        
        MA20, MA60, MA120 배열 + MACD 방향을 종합하여
        각 날짜에 'bull', 'sideways', 'bear' 레이블 부여
        
        Returns:
            추세 레이블 시리즈
        """
        df = self.df
        
        ma20 = df['MA20'] if 'MA20' in df.columns else df['close'].rolling(20).mean()
        ma60 = df['MA60'] if 'MA60' in df.columns else df['close'].rolling(60).mean()
        ma120 = df['MA120'] if 'MA120' in df.columns else df['close'].rolling(120).mean()
        
        trend = pd.Series('sideways', index=df.index)
        
        # 기본 MA 배열 판단
        bull = (df['close'] > ma20) & (ma20 > ma60) & (ma60 > ma120)
        bear = (df['close'] < ma20) & (ma20 < ma60) & (ma60 < ma120)
        
        trend[bull] = 'bull'
        trend[bear] = 'bear'
        
        # MACD 확인 신호로 보강
        if 'MACD' in df.columns and 'MACD_Signal' in df.columns:
            macd_bull = df['MACD'] > df['MACD_Signal']
            macd_bear = df['MACD'] < df['MACD_Signal']
            
            # MA 정배열이지만 MACD 데드크로스 → 전환 가능성, sideways로 격하
            trend[(trend == 'bull') & macd_bear] = 'sideways'
            # MA 역배열이지만 MACD 골든크로스 → 반등 가능성, sideways로 격상
            trend[(trend == 'bear') & macd_bull] = 'sideways'
        
        logger.info(f"추세 레이블링 완료: "
                    f"상승 {(trend=='bull').sum()}일 ({(trend=='bull').mean()*100:.1f}%), "
                    f"횡보 {(trend=='sideways').sum()}일 ({(trend=='sideways').mean()*100:.1f}%), "
                    f"하락 {(trend=='bear').sum()}일 ({(trend=='bear').mean()*100:.1f}%)")
        
        return trend
    
    def get_trend_name(self) -> str:
        """추세명 반환"""
        names = {
            'bull': '📈 상승장 (Bull Market)',
            'sideways': '↔️ 횡보장 (Sideways)',
            'bear': '📉 하락장 (Bear Market)'
        }
        return names.get(self.trend_type, '알 수 없음')
    
    def get_transition_name(self) -> str:
        """국면 전환명 반환"""
        if self.transition is None:
            return None
        names = {
            'bull_to_bear': '⚠️ 상승→하락 전환 감지',
            'bear_to_bull': '🔄 하락→상승 전환 감지'
        }
        return names.get(self.transition, None)
    
    def print_analysis(self):
        """분석 결과 출력"""
        if not self.details:
            self.analyze()
        
        print(f"\n{'='*60}")
        print(f"📊 시장 추세 분석 v2")
        print(f"{'='*60}")
        print(f"📅 분석일: {self.current_date.strftime('%Y-%m-%d')}")
        print(f"💰 현재가: {self.current_price:,.2f}")
        print(f"\n{'─'*60}")
        
        scores = self.details['scores']
        print(f"【점수 상세】")
        print(f"  이동평균 배열: {scores['ma_arrangement']:+d}점")
        print(f"  이동평균 기울기: {scores['ma_slope']:+d}점")
        print(f"  가격 모멘텀: {scores['momentum']:+d}점")
        print(f"  MACD 방향:  {scores['macd']:+d}점")
        print(f"  거래량 추세: {scores['volume_trend']:+d}점")
        print(f"  볼린저밴드: {scores['bb_position']:+d}점")
        print(f"  ADX 강도: {scores['adx']:+d}점 (방향 무관)")
        print(f"  ────────────────────")
        print(f"  방향성 총점: {self.trend_score:+d}점")
        
        print(f"\n{'─'*60}")
        print(f"【종합 판단】")
        print(f"  {self.get_trend_name()}")
        print(f"  신뢰도: {self.confidence}%")
        
        transition_name = self.get_transition_name()
        if transition_name:
            print(f"\n  {transition_name}")
        
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
    
    # 과거 추세 레이블링 테스트
    print(f"\n{'─'*60}")
    print(f"📋 과거 추세 레이블링 결과")
    trends = analyzer.label_all_trends()
    print(f"  최근 5일 추세: {trends.iloc[-5:].tolist()}")
