# 시장 국면·유사구간 기반 적정 주식비중 시스템

KOSPI·KOSDAQ 20년 일봉 + 투자자 수급 데이터로 **현재 시장 국면을 판단**하고,
**과거 20년 중 현재와 가장 유사했던 시장 상황**을 찾아 그 이후 실제 결과를
통계적으로 분석하여 **향후 상승확률·기대수익·위험**을 추정하고,
최종적으로 **현재 적정 주식비중(%)** 을 산출한다.

> **자체 완결형 프로젝트**: 데이터·업데이트·분석·리포트가 모두 이 폴더 안에서 동작한다.
> DB는 `NewOne/data`(market_data.db + investor_data.db)를 사용하고,
> DB 업데이트도 프로젝트 내부 `update_data.py`가 담당한다.

---

## 한 번에 실행 (권장)

```
run_report.bat   더블클릭
```

1. 최신 DB로 업데이트 (프로젝트 내부 `update_data.py`)
2. 시장 분석 + 유사구간 검색 + Walk-forward 백테스트
3. HTML 리포트 자동 오픈

전체 소요 시간: DB 업데이트(1~2분) + 분석·백테스트(약 30초)

> 지수 가격은 yfinance + 네이버금융으로 자동 갱신된다.
> 투자자 수급(외국인/기관)까지 자동 갱신하려면 `pip install pykrx` 후 실행한다.
> (pykrx가 없으면 수급 DB는 기존 값을 유지하고 가격만 갱신된다.)

---

## 명령행 사용

```bash
python main.py                 # 최신일 기준 전체 분석 + 백테스트 + 리포트
python main.py --open          # 완료 후 HTML 자동 열기
python main.py --no-backtest   # 유사구간·비중 분석만 (빠름)
python main.py --asof 20200320 # 특정 시점 재현(그날까지의 데이터만 사용)
```

---

## 아키텍처 (모듈)

| 파일 | 역할 |
|------|------|
| `config.py` | 경로·시장코드·컬럼 매핑·파라미터 (DB 구조 변경 시 이곳만 수정) |
| `update_data.py` | 프로젝트 내부 DB 갱신 (지수: yfinance+네이버 / 수급: pykrx 선택) |
| `data_layer.py` | DB 로딩(OHLCV+수급 병합) + 품질 검증(자동삭제 안 함, 로그만) |
| `features.py` | Feature Engineering (전부 backward rolling → Look-ahead 없음) |
| `regime.py` | 시장 국면 분류 (추세+모멘텀+위험 종합 rule-based) |
| `analog.py` | **핵심**: 과거 유사구간 검색 + Forward Return 통계 + MFE/MAE + 상승/하락 판별 |
| `allocation.py` | Direction/ExpectedReturn/Risk/Confidence 분리 → 위험조정 비중 산출 |
| `backtest.py` | Walk-forward 포트폴리오 백테스트 + 벤치마크 비교 |
| `report.py` | Markdown + HTML(차트) + Excel 리포트 생성 |
| `main.py` | 전체 파이프라인 오케스트레이션 |
| `run_report.bat` | DB 업데이트 → 분석 → 리포트 오픈 (원클릭) |

---

## Look-ahead Bias 차단 (가장 중요한 원칙)

- 모든 Feature는 rolling/backward 연산만 사용 → 날짜 t의 값은 t까지 데이터로만 결정
- 유사구간 표준화(median/IQR)는 **t 이전 데이터(candidate pool)로만 fit**
- 유사 사례는 **t-20거래일 이전**에서만 탐색
- Forward Return은 유사 사례 d에 대해 **d+h ≤ t (이미 실현된 과거)** 일 때만 통계 포함
- 백테스트는 각 리밸런싱 시점 이전 데이터만으로 비중 산출 (Walk-forward)

→ 실시간 예측에서도 합성된 미래값이 절대 사용되지 않는다.

---

## 주요 Feature

- 수익률: 1/3/5/10/20/60/120/252일
- 이동평균/이격도/기울기/정배열, MA5·10·20·60·120·200
- RSI(14), MACD/Signal/Histogram(가격정규화)
- 변동성 5/20/60/120일(연율화) + rolling percentile
- Rolling MDD 20/60/120/252일
- 거래량 비율/Z-score
- **수급(외국인·기관)**: 5/20/60/120일 누적 + rolling z-score(시장규모 변화에 강건) + 연속일수
- KOSPI/KOSDAQ 상대강도

유사도 계산 Feature는 `config.ANALOG_FEATURES`에서 관리(표준화 후 유클리드 거리).

---

## 유사구간 → 비중 산출 로직

1. **유사구간 검색**: 현재 Feature Vector와 과거 모든 날짜의 표준화 거리 → 상위 K개
   (최소 20거래일 이격으로 같은 이벤트 중복 방지)
2. **Forward 통계**: 각 구간별 평균/중앙값/표준편차/상승확률/분위수/N
3. **경로 위험**: MFE(최대상승)·MAE(최대하락) — 최종수익 뒤에 숨은 중간 위험
4. **상승/하락 판별**: 유사 사례를 이후 상승/하락으로 나눠 무엇이 갈랐는지 분석
5. **비중 산출**: Direction·ExpectedReturn·Risk·Confidence 4요소 분리 →
   위험조정 노출로 0~100% 산출. 표본 부족 시 신뢰도로 중립(50%)에 수축.

리포트의 유사 사례 표에는 **각 유사 날짜의 당시 국면과 그 이후 실제 20/60일 수익률**이
함께 표시되어, "어떤 날짜의 어떤 상황이었고 이후 실제로 어떻게 됐는지"를 바로 확인할 수 있다.

> 지수 가격과 투자자 수급의 최신일이 다를 수 있어, 분석 기준일(as-of)은
> **두 시장 모두 Feature가 완비된 마지막 날짜**로 자동 정렬된다.

---

## 백테스트 & 벤치마크

Walk-forward(5거래일 리밸런싱)로 모델 비중을 과거에 적용하고 다음과 비교:
- 코스피 B&H / 코스닥 B&H / 50:50 / 현금 100% / MA200 추세추종
- 지표: 총수익·CAGR·변동성·Sharpe·Sortino·MDD·Calmar·승률

---

## 출력물 (`results/YYYYMMDD/`)

- `시장비중리포트_YYYYMMDD.md` — 사람이 읽는 종합 리포트
- `시장비중리포트_YYYYMMDD.html` — 차트 포함, bat 실행 시 자동 오픈
- `시장비중리포트_YYYYMMDD.xlsx` — Summary/Forward/Similar/Backtest 시트
- `path_*.png`, `equity_curve.png` — 유사구간 경로 / 자산곡선

---

## 정직성 원칙

- 모든 통계에 표본 수 N을 함께 표시하고, 부족하면 "신뢰도 낮음"으로 명시
- "무조건 오른다" 식 단정 대신 확률·분위수·하방위험을 함께 제시
- 백테스트는 look-ahead 없이 산출되므로 buy&hold 대비 초과수익을 과장하지 않는다
  (본 모델은 수익 극대화보다 **MDD 축소·위험조정 노출**에 초점)

*과거 데이터 기반 통계이며 미래 수익을 보장하지 않는다.*
