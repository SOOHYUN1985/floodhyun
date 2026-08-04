# MarketTop v2.0 — 사용자 가이드

> 개인 투자자를 위한 코스피/코스닥 종합 시장 분석 플랫폼 실전 사용 매뉴얼

---

## 목차

1. [최초 설치 (한 번만)](#1-최초-설치-한-번만)
2. [매일 하는 일 — daily_backtest.bat](#2-매일-하는-일)
3. [장마감 후 — daily_position.bat](#3-장마감-후-포지션-분석)
4. [주 1회 — weekly_research.bat](#4-주-1회-심층-리서치)
5. [수시 — stock_analysis.bat](#5-수시-개별-종목-목표주가)
6. [config.py 값 업데이트 방법](#6-configpy-값-업데이트)
7. [결과 파일 읽는 법](#7-결과-파일-읽는-법)
8. [아카이브 정리](#8-아카이브-정리)
9. [자주 묻는 문제 (FAQ)](#9-faq)
10. [CLI 고급 사용법](#10-cli-고급-사용법)

---

## 1. 최초 설치 (한 번만)

### 1-1. Python 가상환경 생성 및 패키지 설치

```cmd
cd C:\FREE\gitTest\Test

python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt
```

### 1-2. DB 최초 구축 (30년치 데이터 수집 — 최초 1회, 수십 분 소요)

```cmd
python update_market_data.py --stock --full
```

> 이 명령은 코스피·코스닥 지수(1996년~) + 54종목(2000년~) 전체 이력을 수집합니다.  
> 이후 매일 `daily_backtest.bat` 실행 시 자동으로 증분 업데이트됩니다.

---

## 2. 매일 하는 일

### `daily_backtest.bat` 더블클릭 (오전 9시 이후)

| 단계 | 내용 | 소요 시간 |
|------|------|-----------|
| [1/5] DB 업데이트 | 지수 + 54종목 최근 7일 증분 수집 | 1~2분 |
| [2/5] 밸류에이션 차트 | 코스피 Forward PER/PBR 밴드 차트 생성 | 30초 |
| [3/5] 백테스트 | 코스피 + 코스닥 고점 판독 (15,000+ 전략) | 10~20분 |
| [4/5] 괴리율 분석 | 27쌍 54종목 보통주/우선주 Z-score | 2~3분 |
| [5/5] 리포트 열기 | 최신 고점판독 + 일일종합 자동 오픈 | — |

**출력 폴더:** `results/daily_backtest/`

**핵심 출력 파일:**

| 파일명 패턴 | 내용 |
|------------|------|
| `코스피_고점판독리포트_{날짜}.md` | 코스피 과열 대시보드 + 전략 상세 |
| `코스닥_고점판독리포트_{날짜}.md` | 코스닥 과열 대시보드 + 전략 상세 |
| `일일종합_{날짜}.md` | A4 한 장 요약 (가장 먼저 읽기) |
| `premium/` 폴더 | 27쌍 괴리율 차트 PNG + 리포트 |

---

### 통합 실행: `integrated_market_report.bat` 더블클릭

일일 백테스트와 주간 리서치를 순서대로 실행한 뒤, 코스피·코스닥의 매수·매도 실행 기준을 한 문서로 자동 생성합니다. 전체 실행에는 주간 리서치 시간(약 30~60분)이 포함됩니다.

**최종 출력:** `results/daily_backtest/통합_매매실행가이드_{날짜}.md`

문서에는 시장별 현재 행동, 매수 확인 조건, 3단계 분할 매수 가격·비중, 3단계 익절 및 방어선이 포함됩니다.

---

## 3. 장마감 후 포지션 분석

### `daily_position.bat` 더블클릭 (오후 4시 이후)

실행하면 두 가지를 입력받습니다:

```
순자산 (억, 예: 23.0):   → 현재 보유 순자산 총액 (현금 + 주식 평가금)
평가금액 (억, 예: 27.85): → 주식 평가금액만
기준일 (엔터=오늘):       → 오늘이면 그냥 엔터
```

**출력 폴더:** `results/daily_position/`

| 파일명 패턴 | 내용 |
|------------|------|
| `코스피_시장국면판단_베어vs불_{날짜}.md` | 현재 코스피 기술적 지표 기반 불/베어 판단 |
| `투자전략_시나리오분석_{날짜}.md` | 상승/횡보/하락 시나리오별 대응 전략 |

> **투자비중 = 평가금액 / 순자산 × 100** 으로 자동 계산되어 과다/과소 노출 여부를 판단합니다.

---

## 4. 주 1회 심층 리서치

### `weekly_research.bat` 더블클릭 (주말 또는 한가할 때)

총 14단계, 전체 30~60분 소요.

| 단계 | 분석 | 출력 파일 |
|------|------|----------|
| [1] | 명절 효과 (전체) | `명절효과_분석_{날짜}.md` |
| [2] | 명절 효과 (2010+) | `명절효과_분석_2010이후_{날짜}.md` |
| [3] | 연말연초 효과 | `연말연초_효과_분석_{날짜}.md` |
| [4] | 외국인 순매도 Top20 | `외국인_순매도_Top20_분석_{날짜}.md` |
| [5] | 외국인 순매도 심층 | `외국인_순매도_심층분석_{날짜}.md` |
| [6] | 외국인 순매수 Top20 | `외국인_순매수_Top20_분석_{날짜}.md` |
| [7] | 외국인 순매수 심층 | `외국인_순매수_심층분석_{날짜}.md` |
| [8] | 담보비율 시뮬레이션 | `담보대출_전략_{날짜}.md` |
| [9] | 반도체 밸류에이션 | `반도체_밸류에이션_분석_{날짜}.md` |
| [10] | 추세/MDD 차트 | PNG 파일 4개 |
| [11] | 시장 전략 리포트 | `시장전략_매매타이밍_{날짜}.md` |
| [12] | MDD 심층 분석 | `코스피_MDD_심층분석_리포트_{날짜}.md` |
| [13] | 반도체 컨센서스 | `삼전하닉목표주가_by_Analist_{날짜}.md` |
| [14] | 주요 리포트 자동 오픈 | — |

**출력 폴더:** `results/weekly_research/`

---

## 5. 수시 — 개별 종목 목표주가

### `stock_analysis.bat` 더블클릭 또는 드래그

```cmd
stock_analysis.bat 현대차
stock_analysis.bat 005380
stock_analysis.bat "SK하이닉스"
```

- 네이버 금융에서 증권사 목표주가 컨센서스 실시간 수집
- **강력매수 기준:** 현재가 ≤ 컨센서스 목표가 × 70%
- **매수 기준:** 현재가 ≤ 컨센서스 목표가 × 80%

**출력:** `results/weekly_research/{종목명}_목표주가분석_{날짜}.md`

#### 마이크론 EPS 기반 반도체 목표주가

마이크론 실적 발표 후 삼성전자/SK하이닉스 목표주가 역산:

1. `micron_target_report.py` 상단 **EPS 입력 구역** 수정
2. `python micron_target_report.py` 실행

```python
# micron_target_report.py 상단에서 수정
MICRON_EPS         = 116        # ← 마이크론 발표 EPS (USD)
SAMSUNG_EPS        = 54_000     # ← 삼성전자 연간 EPS (원)
HYNIX_EPS          = 410_000    # ← SK하이닉스 연간 EPS (원)
```

---

## 6. config.py 값 업데이트

### 6-1. 밸류에이션 상수 (수시 업데이트)

`config.py` 파일을 열어 아래 두 줄만 수정합니다:

```python
CURRENT_FWD_EPS = 1000     # ← 오늘자 12M Forward EPS (수시 업데이트)
CURRENT_FWD_BPS = 5000     # ← 오늘자 12M Forward BPS (분기별 업데이트)
```

> 이 값은 `kospi_valuation_chart.py`, `summary_generator.py`, `visualize_charts.py`에서 자동 참조됩니다.

**EPS/BPS 출처:** 에프엔가이드, 블룸버그, 증권사 리서치 리포트 등

### 6-2. 백테스트 파라미터 조정 (고급)

```python
BACKTEST_PARAMS = {
    'min_win_rate': 70,          # 전략 필터: 최소 승률 (%)
    'min_profit_factor': 1.3,    # 전략 필터: 최소 이익/손실 비율
    'disparity_min': 102,        # 이격도 탐색 하한 (%)
    'disparity_max': 128,        # 이격도 탐색 상한 (%)
    'ma_min': 5,                 # 이동평균 최소 기간 (일)
    'ma_max': 120,               # 이동평균 최대 기간 (일)
}
```

### 6-3. 분할매도/손절 전략 조정

```python
# 5단계 분할매도 (상승 시)
SELL_STAGES = [
    {'stage': 1, 'ratio': 20, 'target_pct': 2.0,  'desc': '초기 익절'},
    ...
    {'stage': 5, 'ratio': 20, 'target_pct': 12.0, 'desc': '완전 청산'},
]

# 3단계 손절 (하락 시)
STOP_LOSS_STAGES = [
    {'stage': 1, 'ratio': 30, 'target_pct': -3.0, 'desc': '1차 손절'},
    ...
    {'stage': 3, 'ratio': 40, 'target_pct': -8.0, 'desc': '전량 손절'},
]
```

---

## 7. 결과 파일 읽는 법

### 7-1. 일일종합 (가장 중요)

```
results/daily_backtest/일일종합_{날짜}.md
```

| 섹션 | 설명 |
|------|------|
| 시장 현황 요약 | 코스피/코스닥 현재가, 당일 등락률 |
| 추세 판단 | 상승장/횡보/하락장 + 신뢰도 점수 |
| 과열 게이지 | RSI·Stoch·MFI·CCI·BB·ADX·이격도 0~100점 |
| 밸류에이션 위치 | 현재 Forward PER이 역사적 위치에서 어디인지 |
| 핵심 전략 요약 | 오늘 유효한 고점/저점 신호 전략 Top 3 |

### 7-2. 고점판독리포트 상세

```
results/daily_backtest/코스피_고점판독리포트_{날짜}.md
```

| 섹션 | 설명 |
|------|------|
| 과열 게이지 대시보드 | ████░░ 형태 시각적 게이지 |
| 시장 추세 판단 | 상승/횡보/하락 + 점수 |
| 매도 전략 (5단계) | 익절 구간별 매도 비율과 목표가 |
| 손절 전략 (3단계) | 손절 구간별 비율과 손절가 |
| 백테스트 결과 | 선정 전략 수, 평균 승률, 전략 유형 분포 |
| 각 전략 상세 | 전략별 승률·수익률·샤프비율·켈리비중 |

### 7-3. 괴리율 리포트 (premium/)

- **Z-score > 2.0** → 우선주 고평가, 보통주 상대 저평가 신호
- **Z-score < -2.0** → 우선주 저평가, 매수 고려 가능

---

## 8. 아카이브 정리

`results/archive/` 폴더가 커지면 `archive_cleanup.bat` 실행:

| 옵션 | 동작 | 권장 |
|------|------|------|
| [1] 최근 5회분 보관 | 가장 최근 5일치만 남기고 삭제 | ✅ 권장 |
| [2] 7일 이전 삭제 | 일주일 된 파일 삭제 | |
| [3] 30일 이전 삭제 | 한 달 된 파일 삭제 | |

> 각 BAT 실행 시 이전 결과가 자동으로 archive로 이동됩니다.  
> archive_cleanup을 하지 않으면 archive 폴더가 계속 누적됩니다.

---

## 9. FAQ

### Q. `[ERROR] DB 업데이트 실패` 오류가 나옵니다

Yahoo Finance 네트워크 문제이거나 장 시작 직전일 수 있습니다.

```cmd
# venv 활성화 후 직접 실행해서 오류 메시지 확인
venv\Scripts\activate
python update_market_data.py
```

### Q. 백테스트가 너무 오래 걸립니다

`config.py`의 `BACKTEST_PARAMS` 범위를 좁히면 빨라집니다:

```python
'disparity_step': 4,    # 기본 2 → 4 (절반 속도)
'ma_step': 10,          # 기본 5 → 10 (절반 속도)
```

### Q. 외국인 순매도/매수 분석이 실패합니다

네이버 금융 스크래핑 실패입니다. 오류는 WARNING으로 처리되어 다음 단계로 넘어갑니다. 잠시 후 재실행하거나 네트워크를 확인하세요.

### Q. venv가 없다는 경고가 뜹니다

```cmd
cd C:\FREE\gitTest\Test
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### Q. `stock_consensus_report.py`가 종목을 못 찾습니다

종목명(한글) 또는 6자리 코드로 입력하세요. 종목코드는 KRX에서 확인합니다.

```cmd
python stock_consensus_report.py 삼성전자
python stock_consensus_report.py 005930
```

### Q. Forward EPS/BPS는 어디서 구하나요?

- **에프엔가이드** (fnguide.com) → 코스피 컨센서스 → 12M Forward EPS
- **증권사 리서치** → 코스피 밸류에이션 섹션
- 분기별로 크게 바뀌므로 실적 시즌(1/4/7/10월) 이후 업데이트 권장

---

## 10. CLI 고급 사용법

```bash
# ── 고점 판독 백테스트 ──
python main.py              # 코스피만
python main.py --kosdaq     # 코스닥만
python main.py --all        # 코스피 + 코스닥

# ── 밸류에이션 ──
python kospi_valuation_chart.py         # Forward PER/PBR 밴드 차트
python stock_valuation_report.py        # 삼성전자/SK하이닉스 밸류에이션

# ── 보통주/우선주 괴리율 ──
python premium_analyzer.py              # 27쌍 54종목 Z-score

# ── 포지션 분석 ──
python position_report.py --net 23.0 --stock 27.85
python position_report.py --net 23.0 --stock 27.85 --date 20260407

# ── 계절성 효과 ──
python holiday_effect_analyzer.py       # 설날/추석 전체 기간
python holiday_effect_analyzer.py 2010  # 2010년 이후
python yearend_effect_analyzer.py       # 연말연초 패턴

# ── 외국인 수급 ──
python foreign_selling_analyzer.py
python foreign_selling_deep_analysis.py
python foreign_buying_analyzer.py
python foreign_buying_deep_analysis.py

# ── 시장 전략 ──
python market_strategy_report.py        # 피보나치 + 매매 타이밍
python mdd_analysis_report.py           # MDD 심층 분석

# ── 반도체 목표주가 ──
python semiconductor_consensus_report.py    # 삼성전자·SK하이닉스 컨센서스
python stock_consensus_report.py [종목명]  # 개별 종목
python micron_target_report.py             # 마이크론 EPS 기반 역산

# ── DB 관리 ──
python update_market_data.py               # 일일 업데이트 (최근 7일)
python update_market_data.py --index       # 지수만
python update_market_data.py --stock       # 종목만
python update_market_data.py --stock --full  # 전체 이력 재수집
```

---

## 결과 폴더 구조

```
results/
├── daily_backtest/     → daily_backtest.bat 출력
│   └── premium/        → 괴리율 차트 + 리포트
├── daily_position/     → daily_position.bat 출력
├── weekly_research/    → weekly_research.bat 출력
└── archive/            → 이전 결과 자동 백업
    ├── daily_backtest/
    ├── daily_position/
    └── weekly_research/
```

---

*MarketTop v2.0 — Private Use Only*
