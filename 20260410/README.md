# MarketTop v2 — 코스피/코스닥 종합 시장 분석 시스템

## 개요

코스피/코스닥 지수의 **고점 판독**, **밸류에이션 분석**, **계절성 효과**, **위기 대응 전략**까지 아우르는 종합 시장 분석 플랫폼입니다.

- Yahoo Finance + 네이버 금융 기반 **최대 31년치** 일봉 데이터 자동 수집
- **15,000+** 전략 조합 백테스트로 현재 시점 최적 매도/매수 전략 생성
- 보통주/우선주 괴리율 **27쌍 54종목** — Z-score 기반 매매 시그널
- 외국인 수급, 명절/연말 효과 등 **다각도 시장 분석**
- SQLite DB 2개 (`market_data.db`, `investor_data.db`) — 증분 업데이트, 수초 내 실행
- `daily_backtest.bat` / `weekly_research.bat` 더블클릭으로 자동화

---

## 핵심 기능

| 기능 | 설명 |
|------|------|
| **과열 대시보드** | RSI, Stoch, MFI, CCI, BB, ADX, MACD 7개 지표 실시간 과열 게이지 |
| **시장 추세 판단** | MA배열·기울기·모멘텀·BB·ADX 기반 상승/횡보/하락 자동 분류 (신뢰도 0-100) |
| **고점 판독 백테스트** | 상향돌파 매도(~11,000회) + 하락반전 매도(~4,000회) 이중 전략 |
| **다각화 전략 선정** | 신호 겹침률 15% 이하 독립 전략만 선정 → 분할매도 단계 배치 |
| **보통주/우선주 괴리율** | 27쌍 54종목 일일 괴리율 추적, Z-score 기반 매매 시그널 |
| **PER 밸류에이션 밴드** | Forward PER/PBR 기준 적정 지수대 산출 + 장기 밴드 차트 |
| **MDD 급락 매수 전략** | 31년 데이터 기반 다단계 하락 진입 + 6가지 청산 모드 백테스트 |
| **외국인 극단 매도 분석** | Top20 매도일 + 분위수별(1%~10%) D+1~D+30 수익률 추적 |
| **명절/연말 효과** | 설날·추석 D-30~D+30, 연말연초 D-30~D+30 패턴 분석 |
| **담보비율 시뮬레이터** | 6가지 프로파일별 MDD 시나리오 담보비율 계산 |

---

## 프로젝트 구조

```
MarketTop_v2/
│
├─ 핵심 파이프라인 (Core Pipeline)
│   ├── main.py                     # 메인 — 분석→백테스트→전략선정→리포트 파이프라인
│   ├── config.py                   # 설정 — 백테스트 파라미터, 매도/손절 단계, 임계값
│   ├── data_loader.py              # 데이터 — SQLite→DataFrame + 25개 기술적 지표 계산
│   ├── trend_analyzer.py           # 추세 — 상승/횡보/하락 분류 + 100점 방향성 점수
│   ├── peak_detector.py            # 고점 — 15,000+조합 백테스트 (돌파+반전 전략)
│   ├── strategy_selector.py        # 선정 — 겹침률 15%이하 독립 전략 Greedy 선정
│   ├── report_generator.py         # 리포트 — 과열대시보드, 분할매도표, 손절표 마크다운
│   ├── summary_generator.py        # 일일종합 — A4 한 장 요약 리포트
│   └── visualize_charts.py         # 차트 — 추세 캔들, MDD 차트, 연도별 추세 구성
│
├─ 데이터 수집/관리
│   └── update_market_data.py       # 일일 업데이트 — 지수+54종목 증분 수집 (네이버 fallback)
│
├─ 시장 연구/분석 도구
│   ├── premium_analyzer.py         # 보통주/우선주 괴리율 (27쌍 54종목, Z-score)
│   ├── kospi_valuation_chart.py    # 코스피 Forward PER/PBR 밸류에이션 밴드 차트
│   ├── foreign_selling_analyzer.py # 외국인 순매도 Top20 (investor_data.db 증분)
│   ├── foreign_selling_deep_analysis.py # 외국인 극단 매도 분위수별 심층 분석
│   ├── holiday_effect_analyzer.py  # 설날/추석 명절 효과 (음력 기반, 20년+)
│   ├── yearend_effect_analyzer.py  # 연말연초 효과 (12월-1월 패턴)
│   ├── margin_calculator.py        # 담보비율 시뮬레이터 (6 프로파일, 위기 시나리오)
│   └── stock_valuation_report.py   # 반도체(삼성전자/SK하이닉스) 밸류에이션
│
├─ 자동화
│   ├── daily_backtest.bat          # 매일 — DB업데이트→백테스트→밸류에이션→괴리율→정리
│   └── weekly_research.bat         # 주1회 — 계절성→외국인→담보→밸류에이션 리서치
│
├─ data/
│   ├── market_data.db              # 지수(코스피/코스닥 31년) + 종목(54종목 297K건)
│   └── investor_data.db            # 투자자별 매매동향 (외국인/기관/개인 21년)
│
├─ results/                        # ★ BAT별 전용 폴더
│   ├── daily_backtest/             # daily_backtest.bat 출력 (고점판독+밸류에이션+괴리율)
│   │   └── premium/                # 괴리율 리포트 + 27종목 개별 차트
│   ├── weekly_research/            # weekly_research.bat 출력 (명절/연말/외국인/담보/반도체)
│   ├── daily_position/             # daily_position.bat 출력 (시장국면+투자전략)
│   └── archive/                    # 이전 실행 결과 자동 백업 (48h 후 자동 정리)
│
└── requirements.txt
```

---

## 사용법

### 원클릭 실행

**매일** — `daily_backtest.bat` 더블클릭
```
→ 결과: results/daily_backtest/  (이전 결과는 archive/로 자동 이동)
[1] DB업데이트 (지수+54종목)
[2] 코스피+코스닥 백테스트 + 일일종합
[3] FwdPER/PBR 밸류에이션 차트
[4] 보통주/우선주 괴리율 (27쌍)
[5] archive 48시간 이전 정리 → 최신 리포트 자동오픈
```

**매일 (장마감 후)** — `daily_position.bat` 더블클릭
```
→ 결과: results/daily_position/  (이전 결과는 archive/로 자동 이동)
순자산(억), 평가금액(억) 입력 → 2개 리포트 자동 생성
  · 코스피_시장국면판단_베어vs불_{날짜}.md
  · 투자전략_시나리오분석_{날짜}.md
```

**주 1회** — `weekly_research.bat` 더블클릭
```
→ 결과: results/weekly_research/  (이전 결과는 archive/로 자동 이동)
[1-2] 명절효과 (전체+2010이후)
[3]   연말연초효과
[4]   외국인매도 Top20 (DB 증분)
[5]   외국인 심층분석
[6]   담보비율 시뮬레이션
[7]   반도체 밸류에이션 → 최신 5개 리포트 자동오픈
```

### 수동 실행

```bash
# 코스피만 / 코스닥만 / 동시 분석
python main.py
python main.py --kosdaq
python main.py --all

# 보통주/우선주 괴리율 (27쌍)
python premium_analyzer.py

# 밸류에이션 차트
python kospi_valuation_chart.py

# 포지션 분석 리포트
python position_report.py --net 23.0 --stock 27.85              # 오늘 기준
python position_report.py --net 23.0 --stock 27.85 --date 20260407  # 날짜 지정
```

### 개별 분석 도구

```bash
# 계절성 효과
python holiday_effect_analyzer.py           # 설날/추석 (전체 기간)
python holiday_effect_analyzer.py 2010      # 설날/추석 (2010년 이후)
python yearend_effect_analyzer.py           # 연말연초 패턴

# 외국인 수급
python foreign_selling_analyzer.py          # 외국인 매도 Top20 + DB 업데이트
python foreign_selling_deep_analysis.py     # 외국인 극단 매도 심층 분석

# 밸류에이션/전략
python margin_calculator.py                 # 담보비율 6프로파일
python stock_valuation_report.py            # 반도체 밸류에이션
```

### DB 관리

```bash
# 일일 업데이트 — 지수 + 54종목 (최근 7일 재수집, 네이버 fallback)
python update_market_data.py

# 지수만 / 종목만
python update_market_data.py --index
python update_market_data.py --stock

# 종목 전체 이력 재수집 (초기 세팅/종목 추가 시)
python update_market_data.py --stock --full
```

---

## 괴리율 분석 대상 (27쌍 54종목)

| 구분 | 종목 |
|------|------|
| **대표 대형주** | 삼성전자, 현대차, 삼성전기, 미래에셋증권, 아모레퍼시픽, 두산 |
| **지주사** | SK, 한화, LG, GS, CJ, 코오롱, DL |
| **산업 대형주** | LG화학, 삼성SDI, LG전자, 삼성화재, S-Oil, 대한항공, 유한양행, LG생활건강, CJ제일제당, 대상 |
| **추가 (2026.04)** | 현대건설, 금호석유, 코오롱인더, 호텔신라 |

---

## 데이터

### market_data.db

| 테이블 | 내용 | 소스 |
|--------|------|------|
| `index_data` | 코스피/코스닥 지수 (OHLCV + 등락률) | Yahoo Finance + 네이버 fallback |
| `stock_data` | 54종목 종가/거래량 | Yahoo Finance |

| 항목 | 기간 | 건수 |
|------|------|------|
| 코스피 (^KS11) | 1996년~ | ~7,200건 |
| 코스닥 (^KQ11) | 2000년~ | ~6,300건 |
| 개별 종목 (54종목) | 2000년~ | ~297,000건 |

### investor_data.db

| 테이블 | 내용 | 소스 |
|--------|------|------|
| `investor_daily` | 일별 투자주체별 순매수 (개인/외국인/기관 등 10개 주체) | 네이버 금융 스크래핑 |

| 시장 | 기간 | 건수 |
|------|------|------|
| 코스피 (01) | 2005년~ | ~5,200건 |
| 코스닥 (02) | 2005년~ | ~5,200건 |
| 선물 (03) | 2010년~ | ~3,800건 |

**기술적 지표**: MA(5~120), RSI, Stochastic, MACD, MFI, CCI, BB, ADX, OBV, VWAP, DMI 등 25개+ (`data_loader.py`에서 실시간 산출)

---

## 설치

```bash
pip install -r requirements.txt
python update_market_data.py --stock --full   # 최초 1회: 전체 DB 구축
```

### 의존성

- `pandas` ≥ 1.5 · `numpy` ≥ 1.21 — 데이터 처리
- `yfinance` ≥ 0.2 — Yahoo Finance API
- `matplotlib` ≥ 3.5 — 차트 생성
- `tqdm` ≥ 4.64 — 프로그레스 바
- `certifi` — SSL 인증서 관리

---

## 라이선스

Private Use Only
