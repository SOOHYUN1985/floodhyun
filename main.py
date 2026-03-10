"""
MarketTop v2 - 메인 실행 파일
코스피/코스닥 고점 판독 시스템

사용법:
  python main.py              # 코스피 분석
  python main.py --kosdaq     # 코스닥 분석
  python main.py --all        # 코스피 + 코스닥 모두 분석
"""

import os
import sys
import argparse
import time
from datetime import datetime

# 현재 디렉토리를 Python 경로에 추가
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from config import DB_PATH, MARKETS
from data_loader import DataLoader
from trend_analyzer import TrendAnalyzer
from peak_detector import PeakDetector
from strategy_selector import StrategySelector
from report_generator import ReportGenerator


class MarketTopSystem:
    """고점 판독 통합 시스템"""
    
    def __init__(self, market: str = 'kospi'):
        """
        Args:
            market: 'kospi' 또는 'kosdaq'
        """
        self.market = market.lower()
        self.market_info = MARKETS[self.market]
        self.market_name = self.market_info['name']
        
        # 결과 저장
        self.df = None
        self.trend_type = None
        self.trend_confidence = 0
        self.strategies = []
        self.selected_strategies = []
    
    def run(self) -> str:
        """
        전체 분석 실행
        
        Returns:
            리포트 파일 경로
        """
        start_time = time.time()
        
        print(f"\n{'='*70}")
        print(f"🎯 {self.market_name} 고점 판독 시스템")
        print(f"{'='*70}")
        
        # 1. 데이터 로드
        self._load_data()
        
        # 2. 시장 추세 분석
        self._analyze_trend()
        
        # 3. 고점 판독 백테스트
        self._run_backtest()
        
        # 4. 전략 선정
        self._select_strategies()
        
        # 5. 리포트 생성
        report_path = self._generate_report()
        
        elapsed = time.time() - start_time
        
        print(f"\n{'='*70}")
        print(f"✅ {self.market_name} 분석 완료!")
        print(f"⏱️  소요 시간: {elapsed:.1f}초")
        print(f"📄 리포트: {report_path}")
        print(f"{'='*70}\n")
        
        return report_path
    
    def _load_data(self):
        """데이터 로드"""
        print(f"\n📂 {self.market_name} 데이터 로드 중...")
        
        loader = DataLoader(DB_PATH)
        self.df = loader.load_market_data(self.market)
        self.df = loader.calculate_indicators(self.df)
        
        current_price = self.df['close'].iloc[-1]
        current_date = self.df.index[-1].strftime('%Y-%m-%d')
        
        print(f"   ✅ 데이터 기간: {self.df.index[0].strftime('%Y-%m-%d')} ~ {current_date}")
        print(f"   ✅ 현재 지수: {current_price:,.2f}")
        print(f"   ✅ 총 {len(self.df):,}일 데이터")
    
    def _analyze_trend(self):
        """시장 추세 분석"""
        print(f"\n📊 시장 추세 분석 중...")
        
        analyzer = TrendAnalyzer(self.df)
        details = analyzer.analyze()
        
        self.trend_type = details['trend_type']
        self.trend_confidence = details['confidence']
        
        analyzer.print_analysis()
    
    def _run_backtest(self):
        """고점 판독 백테스트"""
        print(f"\n🔍 고점 판독 백테스트 실행...")
        
        detector = PeakDetector(self.df, self.trend_type)
        self.strategies = detector.run_backtest()
        
        print(f"\n   📊 발견된 전략: {len(self.strategies)}개")
        if self.strategies:
            avg_win_rate = sum(s['win_rate'] for s in self.strategies) / len(self.strategies)
            print(f"   📈 평균 승률: {avg_win_rate:.1f}%")
    
    def _select_strategies(self):
        """전략 선정"""
        print(f"\n🎯 다각화된 전략 선정...")
        
        selector = StrategySelector(self.strategies)
        self.selected_strategies = selector.select_diverse_strategies()
    
    def _generate_report(self) -> str:
        """리포트 생성"""
        print(f"\n📝 리포트 생성 중...")
        
        current_price = self.df['close'].iloc[-1]
        
        generator = ReportGenerator(
            market_name=self.market_name,
            current_price=current_price,
            trend_type=self.trend_type,
            trend_confidence=self.trend_confidence,
            selected_strategies=self.selected_strategies,
            df=self.df
        )
        
        return generator.generate()


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='MarketTop v2 - 고점 판독 시스템')
    parser.add_argument('--kosdaq', action='store_true', help='코스닥 분석')
    parser.add_argument('--all', action='store_true', help='코스피 + 코스닥 모두 분석')
    
    args = parser.parse_args()
    
    print(f"\n{'#'*70}")
    print(f"#  MarketTop v2 - 고점 판독 시스템")
    print(f"#  {datetime.now().strftime('%Y년 %m월 %d일 %H시 %M분')}")
    print(f"{'#'*70}")
    
    reports = []
    
    if args.all:
        # 코스피 + 코스닥
        for market in ['kospi', 'kosdaq']:
            system = MarketTopSystem(market)
            report = system.run()
            reports.append(report)
    elif args.kosdaq:
        # 코스닥만
        system = MarketTopSystem('kosdaq')
        report = system.run()
        reports.append(report)
    else:
        # 코스피만 (기본)
        system = MarketTopSystem('kospi')
        report = system.run()
        reports.append(report)
    
    # 완료 메시지
    print(f"\n{'='*70}")
    print(f"🎉 모든 분석 완료!")
    print(f"{'='*70}")
    print(f"\n📄 생성된 리포트:")
    for report in reports:
        print(f"   • {report}")
    print()


if __name__ == '__main__':
    main()
