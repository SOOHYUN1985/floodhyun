"""
MarketTop v2 - 설정 파일
코스피/코스닥 고점 판독 시스템
"""

import os

# 기본 경로
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
RESULTS_DIR = os.path.join(BASE_DIR, 'results')
REPORTS_DIR = os.path.join(RESULTS_DIR, 'reports', 'backtest')  # legacy alias

# BAT별 출력 폴더
DAILY_BACKTEST_DIR = os.path.join(RESULTS_DIR, 'daily_backtest')
WEEKLY_RESEARCH_DIR = os.path.join(RESULTS_DIR, 'weekly_research')
DAILY_POSITION_DIR = os.path.join(RESULTS_DIR, 'daily_position')
ARCHIVE_DIR = os.path.join(RESULTS_DIR, 'archive')

# 데이터베이스 경로
DB_PATH = os.path.join(DATA_DIR, 'market_data.db')

# 시장 설정
MARKETS = {
    'kospi': {
        'code': 'KS11',
        'name': '코스피',
        'table': 'kospi'
    },
    'kosdaq': {
        'code': 'KQ11',
        'name': '코스닥',
        'table': 'kosdaq'
    }
}

# 백테스트 파라미터
# 30년치 데이터 기준 약 3~5만회 조합으로 최적화
# 핵심 구간을 빠뜨리지 않되, 간격을 넓혀 실행 시간 단축
BACKTEST_PARAMS = {
    # 이격도 범위 (%) - 핵심 구간 위주 (step 2)
    'disparity_min': 102,
    'disparity_max': 128,
    'disparity_step': 2,

    # 이동평균 기간 (일) - 대표 기간 위주 (step 5)
    'ma_min': 5,
    'ma_max': 120,
    'ma_step': 5,

    # 기술적 지표 임계값 - 핵심값 위주 (각 10~12개)
    'rsi_thresholds': [60, 65, 68, 70, 73, 75, 78, 80, 83, 85, 88, 90],
    'stoch_thresholds': [65, 70, 73, 75, 78, 80, 83, 85, 88, 90, 93, 95],
    'mfi_thresholds': [65, 70, 73, 75, 78, 80, 83, 85, 88, 90],
    'cci_thresholds': [80, 100, 120, 140, 160, 180, 200, 220, 250],
    'bb_ratios': [1.01, 1.02, 1.03, 1.04, 1.05, 1.06, 1.08, 1.10, 1.12, 1.15],
    
    # 새로 추가된 지표 임계값
    'obv_ma_cross': True,
    'dmi_thresholds': [15, 20, 25, 30, 35, 40, 45, 50],
    'volume_ratio_thresholds': [1.3, 1.5, 1.8, 2.0, 2.5, 3.0, 3.5, 4.0],
    'vwap_ratios': [1.01, 1.02, 1.03, 1.04, 1.05, 1.06, 1.08, 1.10],
    
    # 하락반전 전략용 파라미터
    'reversal_rsi_thresholds': [60, 65, 68, 70, 73, 75, 78, 80, 85, 90],
    'reversal_stoch_thresholds': [65, 70, 75, 78, 80, 83, 85, 88, 90, 95],
    'reversal_mfi_thresholds': [65, 70, 75, 78, 80, 83, 85, 88, 90],
    'reversal_cci_thresholds': [50, 70, 90, 110, 130, 150, 170, 200, 230, 260, 300],
    'reversal_bb_ratios': [0.95, 0.97, 0.99, 1.01, 1.03, 1.05, 1.07, 1.10, 1.13, 1.17],
    'reversal_disparity_thresholds': [102, 105, 108, 110, 113, 115, 118, 120, 123, 125, 128],
    'reversal_adx_thresholds': [15, 20, 25, 30, 35, 40, 45, 50],
    'reversal_macd_periods': [8, 12, 16, 20],
    
    # 하락반전용 새로운 지표
    'reversal_dmi_thresholds': [15, 20, 25, 30, 35],

    # 최소 확인 신호 수 (통계적 신뢰도 확보 위해 최소 5개, 권장 8개 이상)
    'min_signals': 5,
    'min_signals_regime': 3,   # 현재 레짐(시장 국면)별 최소 신호 수

    # 필터 기준
    'min_win_rate': 70,
    'min_profit_factor': 1.3,  # 총이익/총손실 최소 비율

    # 다중검정 보정 (FDR)
    'fdr_alpha': 0.25,  # Benjamini-Hochberg FDR 기준 (25% — 소표본 대응)
    'fdr_enabled': True,
    'fdr_fallback_pvalue': 0.10,  # FDR 전멸 시 개별 p-value 기준

    # Walk-Forward 검증 (Rolling 다중 윈도우 방식)
    'walk_forward_enabled': True,
    'walk_forward_train_ratio': 0.7,  # 학습 데이터 비율 (70%)
    'walk_forward_min_oos_winrate': 50,  # OOS 최소 승률 (%)
    'walk_forward_max_degradation': 25,  # IS→OOS 승률 하락 허용폭 (%p)
    'walk_forward_rolling': True,        # Rolling 다중 윈도우 사용
    'walk_forward_n_windows': 3,         # Rolling 윈도우 수 (3개 시기로 분할 검증)

    # 신호 클러스터링: 독립 신호 간 최소 간격 (거래일)
    'signal_min_gap_days': 10,

    # Forward returns 기간 (30d·40d 추가로 최적 청산 타이밍 파악)
    'forward_days': [5, 10, 15, 20, 30, 40]
}

# ──────────────────────────────────────────────────────────
# 거래 비용 (실전 백테스트 정확도)
# ──────────────────────────────────────────────────────────
TRADING_COSTS = {
    'enabled': False,               # 패턴 분석 목적 → 비용 차감 비활성화
    'commission_pct': 0.015,       # 매매 수수료 (0.015% 한쪽)
    'tax_pct': 0.20,                # 증권거래세 (0.20%, 매도 시만)
    'slippage_pct': 0.0,            # 슬리피지 (지수 패턴 분석엔 불필요)
    # 활성화 시 매도 단방향 가정: 0.015 + 0.20 + 0.0 = 0.215%
}

# ──────────────────────────────────────────────────────────
# 신호 빈도 균형 (과적합 방지 + 실용성)
# ──────────────────────────────────────────────────────────
SIGNAL_FREQUENCY = {
    'min_avg_interval_days': 20,    # 최소 평균 신호 간격 (너무 잦으면 노이즈)
    'max_avg_interval_days': 750,   # 최대 평균 신호 간격 (3년 = 너무 드물면 비실용)
    'optimal_range_days': (30, 250),  # 적정 간격 범위
}

# ──────────────────────────────────────────────────────────
# Monte Carlo 신뢰구간 (부트스트랩)
# ──────────────────────────────────────────────────────────
MONTE_CARLO = {
    'enabled': True,
    'n_iterations': 1000,
    'confidence_level': 0.95,
}

# ──────────────────────────────────────────────────────────
# Inverse Strategy Test (과적합 진단)
# ──────────────────────────────────────────────────────────
INVERSE_TEST = {
    'enabled': True,
    'max_inverse_winrate': 45,  # 반대방향 승률 45% 이상이면 진짜 신호 아님 (단순 추세)
}

# ──────────────────────────────────────────────────────────
# ATR 기반 동적 손절/익절
# ──────────────────────────────────────────────────────────
ATR_STOPS = {
    'enabled': True,
    'period': 20,
    'stop_multiplier': 2.0,    # 손절 = 2×ATR
    'target_multiplier': 3.0,  # 익절 = 3×ATR (R:R = 1.5)
}

# ──────────────────────────────────────────────────────────
# 매크로 변수 (외생 변수 필터)
# ──────────────────────────────────────────────────────────
MACRO_DATA = {
    'enabled': True,
    'tickers': {
        'sp500': '^GSPC',           # S&P 500
        'nasdaq': '^IXIC',          # NASDAQ
        'vix': '^VIX',              # CBOE VIX
        'usdkrw': 'KRW=X',          # USD/KRW
        'us10y': '^TNX',            # 미국 10년물 금리
    },
}

# ──────────────────────────────────────────────────────────
# 밸류에이션 필터 (Buffett 스타일)
# ──────────────────────────────────────────────────────────
VALUATION_FILTER = {
    'enabled': True,
    'expensive_fwd_per': 13.5,  # 고평가 기준 (역사적 평균 +1.5sd)
    'cheap_fwd_per': 9.0,        # 저평가 기준
    'expensive_pbr': 1.20,
    'cheap_pbr': 0.90,
}

# 5단계 분할매도 설정 (상승 시)
SELL_STAGES = [
    {'stage': 1, 'ratio': 20, 'target_pct': 2.0, 'desc': '초기 익절'},
    {'stage': 2, 'ratio': 20, 'target_pct': 4.5, 'desc': '추가 익절'},
    {'stage': 3, 'ratio': 20, 'target_pct': 7.0, 'desc': '주요 익절'},
    {'stage': 4, 'ratio': 20, 'target_pct': 9.5, 'desc': '대부분 익절'},
    {'stage': 5, 'ratio': 20, 'target_pct': 12.0, 'desc': '완전 청산'}
]

# 하락 시 손절 전략 (하락 시)
STOP_LOSS_STAGES = [
    {'stage': 1, 'ratio': 30, 'target_pct': -3.0, 'desc': '1차 손절'},
    {'stage': 2, 'ratio': 30, 'target_pct': -5.0, 'desc': '2차 손절'},
    {'stage': 3, 'ratio': 40, 'target_pct': -8.0, 'desc': '전량 손절'}
]

# 추세 판단 기준
TREND_THRESHOLDS = {
    'bull_score': 100,    # 이 점수 이상이면 상승장
    'bear_score': -100,   # 이 점수 이하면 하락장
    # 그 사이는 보합장
}

# 유사성 임계값(이 값 이하의 유사도를 가진 쌍만 유지하며 조정)
SIMILARITY_THRESHOLD = 0.15  # 15%로 낮춤 (더 엄격한 다각화)

# 최종 유지 쌍 수
MAX_SELECTED_STRATEGIES = 12  # 8개에서 12개로 증가

# ──────────────────────────────────────────────────────────
# 밸류에이션 설정 (KOSPI Forward EPS / BPS)
# ** 백테스트 실행 전 아래 값을 최신으로 수정하세요 **
# ──────────────────────────────────────────────────────────
CURRENT_FWD_EPS = 1000     # ← 오늘자 12M Forward EPS (수시 업데이트)
CURRENT_FWD_BPS = 4912  # ← 오늘자 12M Forward BPS (분기별 업데이트)

# 22년 역사적 Forward PER 데이터 (연말 기준)
# {연도: (KOSPI종가, Fwd PER, Trailing PER, PBR)}
HIST_VALUATION = {
    2003: (810.71, 9.8, 14.2, 1.19),
    2004: (895.92, 8.5, 10.2, 1.13),
    2005: (1379.37, 10.2, 11.1, 1.59),
    2006: (1434.46, 9.8, 11.5, 1.49),
    2007: (1897.13, 10.5, 14.4, 1.81),
    2008: (1124.47, 9.5, 22.7, 0.93),
    2009: (1682.77, 10.8, 20.9, 1.52),
    2010: (2051.00, 9.5, 14.2, 1.50),
    2011: (1825.74, 8.8, 10.3, 1.10),
    2012: (1997.05, 9.2, 13.0, 1.10),
    2013: (2011.34, 9.0, 13.0, 1.04),
    2014: (1915.59, 9.6, 13.6, 0.97),
    2015: (1961.31, 10.1, 14.4, 0.99),
    2016: (2026.46, 9.5, 13.4, 0.97),
    2017: (2467.49, 9.2, 12.3, 1.08),
    2018: (2041.04, 8.4, 9.2, 0.85),
    2019: (2197.67, 11.5, 18.4, 0.86),
    2020: (2873.47, 14.2, 29.2, 1.18),
    2021: (2977.65, 10.0, 11.4, 1.08),
    2022: (2236.40, 10.5, 10.3, 0.83),
    2023: (2655.28, 11.0, 23.3, 0.92),
    2024: (2399.49, 9.0, 11.0, 0.86),
}
