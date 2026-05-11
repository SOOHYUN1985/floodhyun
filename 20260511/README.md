# MarketTop v2.0 — 코스피/코스닥 종합 시장 분석 시스템

> **"데이터로 말하는 시장 판단."**
> 30년치 일봉 데이터 백테스트 기반 고점 판독, 밸류에이션 분석, 계절성 효과, 외국인 수급 추적까지 — 더블클릭 한 번으로 실행되는 개인 투자자용 종합 시장 분석 플랫폼.

---

## 핵심 기능

| 기능 | 설명 |
|------|------|
| **고점 판독 백테스트** | RSI·Stoch·MFI·CCI·BB·ADX·MACD 조합 15,000+ 전략 자동 백테스트 |
| **과열 대시보드** | 7개 기술적 지표 실시간 과열 게이지 (0~100점) |
| **시장 추세 자동 분류** | MA배열·기울기·모멘텀·BB·ADX 기반 상승/횡보/하락 + 신뢰도 점수 |
| **다각화 전략** | 신호 겹침률 15% 이하 독립 전략만 선정 → 5단계 분할매도 배치 |
| **PER/PBR 밸류에이션** | 22년 역사적 Forward PER·PBR 밴드 차트 + 현재 위치 표시 |
| **보통주/우선주 괴리율** | 27쌍 54종목 Z-score 기반 매매 시그널 |
| **외국인 수급 분석** | 순매수/순매도 Top20 + 분위수별 D+1~D+30 수익률 추적 |
| **명절/연말 효과** | 설날·추석 D-30~D+30, 연말연초 패턴 분석 |
| **담보비율 시뮬레이터** | 6가지 프로파일별 MDD 시나리오 계산 |
| **포지션 분석** | 순자산/평가금액 기반 시장국면 판단 + 투자전략 시나리오 |

---

## Quick Start

### 1. 설치

```bash
# 가상환경 생성 (권장)
python -m venv venv
venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 최초 1회: 전체 DB 구축 (지수 + 54종목)
python update_market_data.py --stock --full
```

### 2. 일일 분석 (매일 실행)

**`daily_backtest.bat` 더블클릭** — 가장 핵심적인 일일 분석

```
실행 순서:
  [1] DB 업데이트 (지수 + 54종목 증분)
  [2] 코스피 밸류에이션 차트
  [3] 코스피 + 코스닥 고점 판독 백테스트 + 일일 종합
  [4] 보통주/우선주 괴리율 분석 (27쌍)
  [5] 최신 리포트 자동 열기

→ 결과: results/daily_backtest/
```

### 3. 포지션 분석 (장마감 후)

**`daily_position.bat` 더블클릭** — 순자산·평가금액 입력 시 시장국면 판단

```
입력: 순자산(억), 평가금액(억)
출력:
  · 코스피_시장국면판단_베어vs불_{날짜}.md
  · 투자전략_시나리오분석_{날짜}.md

→ 결과: results/daily_position/
```

### 4. 주간 리서치 (주 1회)

**`weekly_research.bat` 더블클릭** — 심층 분석 모음

```
실행 순서:
  [1]    명절 효과 (전체 기간)
  [2]    명절 효과 (2010이후)
  [3]    연말연초 효과
  [4]    외국인 순매도 Top20
  [5]    외국인 순매도 심층 분석
  [6]    외국인 순매수 Top20
  [7]    외국인 순매수 심층 분석
  [8]    담보비율 시뮬레이션
  [9]    반도체 밸류에이션
  [10]   추세/MDD 차트
  [11]   최신 리포트 자동 열기

→ 결과: results/weekly_research/
```

---

## 수동 실행 (CLI)

```bash
# ── 고점 판독 백테스트 ──
python main.py              # 코스피만 (기본)
python main.py --kosdaq     # 코스닥만
python main.py --all        # 코스피 + 코스닥

# ── 밸류에이션 ──
python kospi_valuation_chart.py         # Forward PER/PBR 밴드 차트
python stock_valuation_report.py        # 반도체 (삼성전자/SK하이닉스) 밸류에이션

# ── 보통주/우선주 괴리율 ──
python premium_analyzer.py              # 27쌍 54종목 Z-score 분석

# ── 포지션 분석 ──
python position_report.py --net 23.0 --stock 27.85              # 오늘 기준
python position_report.py --net 23.0 --stock 27.85 --date 20260407  # 날짜 지정

# ── 계절성 효과 ──
python holiday_effect_analyzer.py       # 설날/추석 (전체 기간)
python holiday_effect_analyzer.py 2010  # 설날/추석 (2010년 이후)
python yearend_effect_analyzer.py       # 연말연초 패턴

# ── 외국인 수급 ──
python foreign_selling_analyzer.py      # 외국인 순매도 Top20
python foreign_selling_deep_analysis.py # 외국인 순매도 심층 분석
python foreign_buying_analyzer.py       # 외국인 순매수 Top20
python foreign_buying_deep_analysis.py  # 외국인 순매수 심층 분석

# ── 기타 ──
python margin_calculator.py             # 담보비율 시뮬레이션 (6프로파일)

# ── DB 관리 ──
python update_market_data.py            # 일일 업데이트 (최근 7일)
python update_market_data.py --index    # 지수만
python update_market_data.py --stock    # 종목만
python update_market_data.py --stock --full  # 종목 전체 이력 재수집
```

---

## 프로젝트 구조

```
MarketTop_v1.0/
│
├── 핵심 파이프라인 ─────────────────────────────────────────
│   ├── main.py                 분석→백테스트→전략선정→리포트 메인 파이프라인
│   ├── config.py               중앙 설정 (파라미터, 임계값, EPS/BPS, 밸류에이션)
│   ├── data_loader.py          SQLite→DataFrame + 25개 기술적 지표 계산
│   ├── trend_analyzer.py       상승/횡보/하락 분류 + 방향성 점수
│   ├── peak_detector.py        15,000+ 조합 백테스트 (돌파+반전 전략)
│   ├── strategy_selector.py    겹침률 15% 이하 독립 전략 Greedy 선정
│   ├── report_generator.py     과열 대시보드, 분할매도표, 손절표 마크다운
│   ├── summary_generator.py    일일 종합 A4 한 장 요약 리포트
│   └── visualize_charts.py     추세 캔들, MDD 차트, 연도별 추세 구성
│
├── 분석 도구 ───────────────────────────────────────────────
│   ├── premium_analyzer.py             보통주/우선주 괴리율 (27쌍, Z-score)
│   ├── kospi_valuation_chart.py        Forward PER/PBR 밸류에이션 밴드 차트
│   ├── position_report.py              시장국면 판단 + 투자전략 시나리오
│   ├── foreign_selling_analyzer.py     외국인 순매도 Top20
│   ├── foreign_selling_deep_analysis.py 외국인 순매도 심층 분석
│   ├── foreign_buying_analyzer.py      외국인 순매수 Top20
│   ├── foreign_buying_deep_analysis.py 외국인 순매수 심층 분석
│   ├── holiday_effect_analyzer.py      설날/추석 명절 효과
│   ├── yearend_effect_analyzer.py      연말연초 효과
│   ├── margin_calculator.py            담보비율 시뮬레이터
│   └── stock_valuation_report.py       반도체 밸류에이션
│
├── 데이터 수집 ─────────────────────────────────────────────
│   └── update_market_data.py   일일 업데이트 (지수+54종목, 네이버 fallback)
│
├── 자동화 배치 ─────────────────────────────────────────────
│   ├── daily_backtest.bat      매일: DB→백테스트→밸류에이션→괴리율
│   ├── daily_position.bat      매일 (장마감 후): 포지션 분석
│   ├── weekly_research.bat     주 1회: 계절성→외국인→담보→밸류에이션
│   └── archive_cleanup.bat     아카이브 정리 (5회/7일/30일 선택)
│
├── data/
│   ├── market_data.db          지수(코스피/코스닥 30년) + 종목(54종목)
│   └── investor_data.db        투자자별 매매동향 (외국인/기관/개인 21년)
│   ※ xlsx 원본 데이터는 별도 보관 (daily_backtest 파이프라인 미포함)
│
├── results/
│   ├── daily_backtest/         daily_backtest.bat 출력
│   │   └── premium/            괴리율 리포트 + 종목별 차트
│   ├── daily_position/         daily_position.bat 출력
│   ├── weekly_research/        weekly_research.bat 출력
│   └── archive/                이전 결과 자동 백업
│
└── requirements.txt
```

---

## 설정 변경

### 밸류에이션 상수 업데이트 (`config.py`)

Forward EPS/BPS가 변경되면 `config.py`의 아래 값만 수정하면 됩니다:

```python
CURRENT_FWD_EPS = 680     # ← 12M Forward EPS (수시 업데이트)
CURRENT_FWD_BPS = 3749.0  # ← 12M Forward BPS (분기별 업데이트)
```

> `kospi_valuation_chart.py`, `summary_generator.py`, `visualize_charts.py`가 이 값을 자동으로 참조합니다.

### 백테스트 파라미터 조정 (`config.py`)

```python
BACKTEST_PARAMS = {
    'disparity_min': 102,    # 이격도 하한 (%)
    'disparity_max': 128,    # 이격도 상한 (%)
    'ma_min': 5,             # 이동평균 최소 기간 (일)
    'ma_max': 120,           # 이동평균 최대 기간 (일)
    'min_win_rate': 70,      # 최소 승률 필터 (%)
    # ... (상세 파라미터는 config.py 참조)
}
```

### 분할매도/손절 전략 (`config.py`)

```python
# 5단계 분할매도 (상승 시)
SELL_STAGES = [
    {'stage': 1, 'ratio': 20, 'target_pct': 2.0,  'desc': '초기 익절'},
    {'stage': 2, 'ratio': 20, 'target_pct': 4.5,  'desc': '추가 익절'},
    {'stage': 3, 'ratio': 20, 'target_pct': 7.0,  'desc': '주요 익절'},
    {'stage': 4, 'ratio': 20, 'target_pct': 9.5,  'desc': '대부분 익절'},
    {'stage': 5, 'ratio': 20, 'target_pct': 12.0, 'desc': '완전 청산'}
]

# 3단계 손절 전략 (하락 시)
STOP_LOSS_STAGES = [
    {'stage': 1, 'ratio': 30, 'target_pct': -3.0, 'desc': '1차 손절'},
    {'stage': 2, 'ratio': 30, 'target_pct': -5.0, 'desc': '2차 손절'},
    {'stage': 3, 'ratio': 40, 'target_pct': -8.0, 'desc': '전량 손절'}
]
```

---

## 데이터

### market_data.db (SQLite)

| 테이블 | 내용 | 소스 |
|--------|------|------|
| `index_data` | 코스피/코스닥 지수 (OHLCV + 등락률) | Yahoo Finance + 네이버 fallback |
| `stock_data` | 54종목 종가/거래량 | Yahoo Finance |

| 항목 | 기간 | 비고 |
|------|------|------|
| 코스피 (^KS11) | 1996년~ | ~7,200건 |
| 코스닥 (^KQ11) | 2000년~ | ~6,300건 |
| 개별 종목 (54) | 2000년~ | ~297,000건 |

### investor_data.db (SQLite)

| 테이블 | 내용 | 소스 |
|--------|------|------|
| `investor_daily` | 일별 투자주체별 순매수 (외국인/기관/개인 등 10개) | 네이버 금융 |

### 기술적 지표 (data_loader.py에서 실시간 산출)

MA(5~120), RSI(14), Stochastic(K/D), MACD, MFI, CCI, BB(상/중/하/폭), ATR, ADX, OBV, DMI(+DI/-DI), Volume Ratio, VWAP — 총 25개+

---

## 괴리율 분석 대상 (27쌍 54종목)

| 구분 | 종목 |
|------|------|
| **대표 대형주** | 삼성전자, 현대차, 삼성전기, 미래에셋증권, 아모레퍼시픽, 두산 |
| **지주사** | SK, 한화, LG, GS, CJ, 코오롱, DL |
| **산업 대형주** | LG화학, 삼성SDI, LG전자, 삼성화재, S-Oil, 대한항공, 유한양행, LG생활건강, CJ제일제당, 대상 |
| **추가 (2026.04)** | 현대건설, 금호석유, 코오롱인더, 호텔신라 |

---

## 의존성

| 패키지 | 버전 | 용도 |
|--------|------|------|
| `pandas` | ≥ 1.5 | 데이터 처리 |
| `numpy` | ≥ 1.21 | 수치 연산 |
| `matplotlib` | ≥ 3.5 | 차트 생성 |
| `yfinance` | ≥ 0.2 | Yahoo Finance API |
| `tqdm` | ≥ 4.64 | 프로그레스 바 |
| `certifi` | ≥ 2022 | SSL 인증서 |
| `requests` | ≥ 2.28 | HTTP 요청 (네이버 스크래핑) |
| `beautifulsoup4` | ≥ 4.11 | HTML 파싱 (반도체 밸류에이션) |

---

## 아카이브 관리

각 BAT 실행 시 이전 결과가 `results/archive/`로 자동 이동됩니다.

아카이브 누적이 많아지면 `archive_cleanup.bat`를 실행하여 정리:
- **최근 5회분 보관** — 날짜 기준 최근 5일치 결과만 보관 (권장)
- **7일 이전 삭제** — 1주일 이전 파일 삭제
- **30일 이전 삭제** — 1개월 이전 파일 삭제

---

## 라이선스

Private Use Only
