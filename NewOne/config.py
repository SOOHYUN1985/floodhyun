"""
설정 파일 — 시장국면·유사구간 기반 적정 주식비중 산출 시스템

기존 C:\\FREE\\gitTest\\Test\\data 의 DB를 그대로 재사용한다.
컬럼/시장코드 매핑을 이 파일에서만 관리하여 데이터 구조가 바뀌어도
코드 본문을 수정하지 않도록 한다.
"""

import os

# ── 경로 ────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 이 프로젝트는 자체 완결형이다. DB는 프로젝트 내부 data 폴더를 사용한다.
DATA_DIR = os.path.join(BASE_DIR, 'data')

MARKET_DB = os.path.join(DATA_DIR, 'market_data.db')       # index_data (OHLCV)
INVESTOR_DB = os.path.join(DATA_DIR, 'investor_data.db')   # investor_daily (수급)

# 결과 출력 폴더
RESULTS_DIR = os.path.join(BASE_DIR, 'results')

# DB 업데이트 스크립트 (프로젝트 내부)
UPDATE_SCRIPT = os.path.join(BASE_DIR, 'update_data.py')

# ── 시장 매핑 ───────────────────────────────────────────
# index_data.index_name  /  investor_daily.market 매핑
MARKETS = {
    'KOSPI':  {'index_name': 'KS11', 'investor_code': '01', 'name': '코스피'},
    'KOSDAQ': {'index_name': 'KQ11', 'investor_code': '02', 'name': '코스닥'},
}

# ── 컬럼 매핑 (DB 구조 변경 시 이곳만 수정) ─────────────
COL = {
    'date': 'date',
    'open': 'open',
    'high': 'high',
    'low': 'low',
    'close': 'close',
    'volume': 'volume',
    # investor_daily
    'foreign': 'foreign_',
    'institution': 'institution',
    'individual': 'individual',
}

# ── 분석 파라미터 ───────────────────────────────────────
# Forward Return 평가 구간 (거래일 기준)
FORWARD_HORIZONS = [1, 3, 5, 10, 20, 60, 120]

# 유사구간(analog) 검색
ANALOG = {
    'k': 60,                 # 최종 사용할 유사 사례 수
    'min_gap_days': 20,      # 유사 사례 간 최소 이격(거래일) — 중복 이벤트 방지
    'asof_buffer_days': 20,  # as-of 시점과 유사 사례 사이 최소 이격
}

# 유사도 계산에 사용할 Feature (표준화 후 유클리드 거리)
ANALOG_FEATURES = [
    'ret5', 'ret20', 'ret60',
    'disp20', 'disp60', 'disp120',
    'rsi14', 'macd_hist_n',
    'vol20', 'mdd120',
    'vol_ratio',
    'foreign_z20', 'inst_z20',
]

# 주식비중 모델
ALLOC = {
    'primary_horizon': 20,   # 비중 산출의 기준 구간
    'min_samples': 15,       # 통계적 신뢰 최소 표본 수
    'risk_aversion': 2.0,    # 위험회피 계수 (클수록 보수적)
    'change_threshold': 0.10,  # 이 값 미만의 비중 변화는 무시(잦은 매매 방지)
    'weight_floor': 0.0,
    'weight_cap': 1.0,
}

# Walk-forward 포트폴리오 백테스트
BACKTEST = {
    'start': '2012-01-01',   # 표본(투자자 수급 2005~) 워밍업 이후 시작
    'rebalance_days': 5,     # 주 1회 리밸런싱
    'trading_days_per_year': 252,
}
