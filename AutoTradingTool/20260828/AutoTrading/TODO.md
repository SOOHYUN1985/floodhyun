# AutoTradingTest - TODO List

> 최종 업데이트: 2026-04-09 (Phase 1~5/6/7/8/10/12/13/14 구현 완료 — 모의투자 준비 완료)  
> 상태: ⬜ 미착수 | 🔧 진행중 | ✅ 완료

---

## Phase 1: 보유종목 실시간 시세 감시 (매도의 전제조건)

### 1.1 보유종목 실시간 시세 등록 ✅
- [x] 로그인 후 DB에서 로드한 보유종목 전부 `SetRealReg` 등록 (`RegisterHoldingsRealTime()`)
- [x] 장 개시 시에도 재등록  
- [x] 등록 FID: `10`(현재가), `11`(전일대비), `12`(등락률), `15`(거래량), `16`(시가), `17`(고가), `18`(저가)
- [x] 화면번호 `5007` (보유종목실시간) 추가

### 1.2 보유종목 현재가 실시간 업데이트 ✅
- [x] `onReceiveRealData` "주식체결" 이벤트에서 보유종목 여부 확인
- [x] `DBInfo.현재가`, `현재수익률`, `현재수익금` 실시간 갱신
- [x] 트레일링 스탑 로스컷가격 자동 갱신 (`UpdateTrailingStop`)

### 1.3 보유종목 당일 시세 데이터 저장 ✅
- [x] 종목별 당일 시가/고가/저가/현재가/거래량을 `m_RealTimePrices` Dictionary에 보관
- [x] 전일 종가 별도 보관 (현재가 - 전일대비로 계산)
- [x] 50일 최대거래량 캐싱 (`m_Max50DayVolume` Dictionary, 로그인/장개시 시 일봉 조회)

### 1.4 매도 완료 시 실시간 해제 ✅
- [x] 전량매도 완료 후 `SetRealRemove(스크린.보유종목실시간, 종목코드)` 호출
- [x] `m_RealTimePrices` Dictionary에서도 제거

### 1.5 DB 로드 후 즉시 보유종목 그리드 표시 ✅
- [x] `LoadDbAsync()` 완료 후 즉시 `RefreshHoldGrid()` 호출
- [x] `RefreshHoldGrid()` 메서드로 DataSource 재바인딩 + 포맷 + 색상 통합
- [x] 중간 패널 빈 화면 문제 해결

---

## Phase 2: 매도 전략 엔진 구현 (Python → C#)

### 2.1 SellStrategyManager 클래스 생성 ✅
- [x] `Core/SellStrategyManager.cs` 신규 파일 생성
- [x] `CheckSellConditions(DBInfo holding, 실시간시세)` → `SellSignal` 반환
- [x] `SellSignal` 모델 정의: `{ 종목코드, 매도유형(enum), 매도수량, 매도이유(string) }`
- [x] 매도유형 enum: `로스컷`, `nR절반익절`, `장대음봉`, `급락매도`, `최대보유일`, `이평이탈`, `없음`
- [x] `.csproj`에 파일 Include 추가
- [x] `RealTimePrice` 모델 정의 (종목별 실시간 시세 정보)

### 2.2 트레일링 로스컷 로직 ✅
- [x] R값 (기본 손절률%) 파라미터화
- [x] 수익이 R×j에 도달할 때마다 `로스컷가격`을 R×(j-1)배로 상향
  ```
  j=1일 때: 로스컷가격 = 매수가격 (본전)
  j=2일 때: 로스컷가격 = 매수가격 × (1 + R×1/100)
  j=3일 때: 로스컷가격 = 매수가격 × (1 + R×2/100)
  ```
- [x] `DBInfo.로스컷단계`, `DBInfo.로스컷가격` 갱신 → DB 저장
- [x] 매도 조건: 현재가 < 로스컷가격 → 전량매도 신호

### 2.3 nR 절반 익절 로직 ✅
- [x] 조건: 현재가 >= 매수가격 × (1 + R × N / 100)
- [x] `DBInfo.nR절반매도` == false 일 때만 1회 실행
- [x] 매도수량: `보유수량 × 50%` (반올림)
- [x] 매도 후 갱신: `nR절반매도=true`, `nR절반매도가격`, `nR절반매도수량`, `nR절반매도일자`

### 2.4 거래량 급등 + 장대음봉 매도 ✅
- [x] 조건 1: 당일거래량 >= 최근 50일 최대거래량 × 0.618
- [x] 조건 2: `(고가/전일종가 - 종가/전일종가) × 100 >= 15`
- [x] 두 조건 동시 충족 시 전량매도 신호
- [x] 50일 최대거래량은 장 시작 시 일봉데이터에서 캐싱 (`FetchHoldingsDailyData`)

### 2.5 전일대비 급락 매도 ✅
- [x] 조건: `종가/전일종가 × 100 <= 86.5` (전일대비 -13.5% 이상 하락)
- [x] 전량매도 신호

### 2.6 최대보유일 초과 손절 ✅
- [x] 조건: `보유일 > 최대보유일` AND `현재수익률 < 0`
- [x] 전량매도 신호

### 2.7 EMA 이탈 분할매도 로직 ✅
- [x] 설정 가능한 EMA 기간 리스트 (예: `[5, 10, 20]`)
- [x] 조건: `종가 < EMA값` AND 해당 이평 미매도 AND 수익 중
- [x] 매도수량: `남은수량 × 1/(남은 이평 단계 수)` (자연수 보정)
- [x] `DBInfo.이평매도일자`에 완료단계 콤마구분 저장 ("5,10")
- [x] 보유종목일봉조회 TR에서 EMA 계산 + `m_HoldingEMA` 캐시
- [x] 마지막 단계 매도 시 전량매도 처리

### 2.8 매도 불가 상황 스킵 ✅
- [x] 거래정지: 거래량 == 0 → 매도 판단 스킵
- [x] 하한가: 시가=고가=종가=저가 AND 하락 → 매도 판단 스킵
- [x] 가하한가: 종가=저가 AND 전일대비 -19% 이상 → 스킵

---

## Phase 3: 매도 주문 실행 파이프라인

### 3.1 매도 가격/수량 결정 ✅
- [x] 전량매도: `DBInfo.보유수량` 전부
- [x] 부분매도: 계산된 수량 (소수점 절사)
- [x] 가격: 현재가 기준 (시장가 or 지정가 선택)
- [x] 슬리피지 반영 옵션 (`CalculateSellPrice`, `CalculateBuyPrice`)

### 3.2 호가단위 변환 함수 구현 ✅
- [x] 한국 주식 호가단위 변환 (`RoundToHogaUnit`, `GetHogaUnit`)
  ```
  ~1,000원: 1원 단위
  ~5,000원: 5원 단위
  ~10,000원: 10원 단위
  ~50,000원: 50원 단위
  ~100,000원: 100원 단위
  ~500,000원: 500원 단위
  500,000원~: 1,000원 단위
  ```

### 3.3 매도 주문 실행 ✅
- [x] `ExecuteSellOrder(SellSignal, DBInfo)` 메서드 구현
- [x] sRQName 형식: `"매도주문;{조건명};{매도유형}"` (식별용)
- [x] 슬리피지 반영 매도가격 (`CalculateSellPrice`)
- [x] 주문 로그 출력 (종목명, 매도유형, 수량, 가격, 사유)
- [x] Kiwoom 초당 5건 제한 준수 (매도 모니터 300ms 간격)

### 3.4 매도 체결 후 DB 처리 분기 ✅
- [x] **전량매도**: `deleteHoldingInsertHistory()` (HoldingTable → HistoryTable)
- [x] **부분매도**: `보유수량` 차감 + `updateHoldingDB()` (nR절반매도일자/가격/수량 기록)
- [x] `OnReceiveChejanData`에서 주문수량 vs 보유수량 비교로 부분/전량 분기
- [x] 부분매도 시 보유수량 <= 0 이면 전량매도로 전환
- [x] 전량매도 시 `SetRealRemove` + `m_RealTimePrices` 제거
- [x] `RefreshHoldGrid()` 호출로 즉시 UI 갱신

---

## Phase 4: 실시간 매도 체크 루프

### 4.1 realSellMonitor Task 구현 ✅
- [x] `CancellationToken` 기반 비동기 Task (`StartSellMonitor` / `StopSellMonitor`)
- [x] 주기: 2초마다 전체 보유종목 순회 (스냅샷 `.ToList()`)
- [x] 각 종목에 대해 `SellStrategyManager.CheckSellConditions()` 호출
- [x] 매도신호 발생 시 → `ExecuteSellOrder()` 실행 + 300ms 딜레이
- [x] `BeginInvoke`로 UI 스레드에서 SendOrder 호출
- [x] 장개시 시 자동 시작, 장마감알림/장마감 시 자동 중지
- [x] FormClosing에서 `StopSellMonitor()` 호출

### 4.2 장 시작/종료 연동 ✅
- [x] `onReceiveRealData` "장시작시간" 이벤트 활용:
  - `구분=3` (장개시): 보유종목 실시간 등록, 보유일 계산 갱신, UI 갱신
  - `구분=2` (장마감알림): 로그 출력
  - `구분=4` (장마감): DB 일괄 저장

### 4.3 장 시작 시 일봉 데이터 갱신 ✅
- [x] 보유종목 전체 일봉 조회 (`FetchHoldingsDailyData` + `보유종목일봉조회` TR)
- [x] 최근 50일 최대거래량 캐싱 (`m_Max50DayVolume` Dictionary)
- [x] Kiwoom TR 요청 속도 제한 준수 (3.6초 간격)
- [x] EMA/SMA 재계산 (일봉 데이터 활용 — `m_HoldingEMA` 캐시)
- [ ] `ConditionCheck` 업데이트

---

## Phase 5: 매수 주문 자동화

### 5.1 매수 수량 계산 로직 ✅
- [x] 종목당 최대 투자금 설정 (`_strategyConfig.종목당최대투자금`)
- [x] 매수가격 = 현재가 × (1 + 슬리피지%) (`CalculateBuyPrice`)
- [x] 매수수량 = 종목당투자금 / 매수가격 (절사)
- [x] 현재가 조회: `GetMasterLastPrice`

### 5.2 매수 필터 조건 ✅ (기본 필터 완료)
- [x] 이미 보유 중인 종목 재매수 금지
- [x] 동시 보유 종목수 상한 설정 (`최대보유종목수`)
- [x] 매도 후 재매수금지기간 체크 (기본값 0=비활성, Python 원본도 주석처리됨)
- [ ] 종가 > MA50 > MA150 (Minervini 트렌드 확인)
- [ ] 시가총액 >= 5000억
- [x] 지수 >= 지수 MA60
- [x] 지수 전일대비 -4% 이내
- [x] 예수금(잔고) 확인 후 매수
- [ ] 신고가 이후 0~10일 이내
- [ ] RS(상대강도) 조건

### 5.3 조건식 편입 시 자동매수 실행 ✅
- [x] `onReceiveRealCondition` "편입" 이벤트에서 `TryAutoBuy()` 호출
- [x] 필터 통과 시 `SendOrder` 매수주문 (지정가 "00")
- [x] sRQName: `"매수주문;{조건식이름}"`
- [x] 중복 주문 방지 (동일 종목 보유 체크)
- [x] 매수 완료 후 실시간 시세 등록 (`SetRealReg` 추가 등록)
- [x] 매수 완료 후 초기 로스컷가격 설정 (매수가 × (1 - R%))
- [x] 매수 완료 후 `RefreshHoldGrid()` + `updateAccountInfo()` 호출

---

## Phase 6: 설정/파라미터 관리

### 6.1 전략 파라미터 설정 파일 ✅
- [x] 설정 항목 정의: `Core/StrategyConfig.cs`
  - `R값` (로스컷 기준 수익률%) — 기본: 7
  - `N배수` (절반익절 기준) — 기본: 3
  - `이평선 매도 기간 리스트` — 기본: [5, 10, 20]
  - `최대보유일` — 기본: 20
  - `종목당 최대 투자금` — 기본: 10,000,000
  - `최대 동시보유 종목수` — 기본: 10
  - `슬리피지 매수/매도` — 기본: 0.3% / 0.3%
  - `시가총액 하한` — 기본: 500,000,000,000 (5000억)
- [x] 저장 형식: `StrategyConfig.json` (DataContractJsonSerializer)
- [x] 앱 시작 시 로드 (`StrategyConfig.Load()`), 종료 시 저장 (`Save()`)

### 6.2 UI 설정 패널 ⬜
- [ ] 전략 파라미터 표시/수정 가능한 UI 패널
- [ ] 저장/불러오기 버튼
- [ ] 실시간 변경 시 매도 엔진에 즉시 반영

---

## Phase 7: UI 보강

### 7.1 보유종목 그리드 컬럼 확장 ✅
- [x] 표시 항목: 종목명, 종목코드, 매수가, 현재가, 수익률(%), 수익금, 보유수량, 보유일
- [x] 추가 항목: 로스컷가격, 로스컷단계, nR절반매도 여부
- [x] 수익률 색상: 양수 빨강, 음수 파랑 (실시간)
- [x] 숫자 포맷: 천 단위 콤마, 불필요 컬럼 숨김
- [x] `FormatHoldGrid()` 메서드로 컬럼 순서/표시/포맷 통일 관리

### 7.2 주문 내역 / 체결 내역 표시 ⬜
- [ ] 금일 주문 목록 (미체결/체결/취소 상태)
- [ ] 체결 알림 (StatusStrip 또는 Toast)

### 7.3 전략 상태 대시보드 ✅
- [x] 보유종목 수, 총 수익금, 총 수익률 표시
- [x] 매도 모니터 상태 (가동중/중지)
- [x] 50일거래량 캐시 건수
- [x] 대시보드 라벨 위치: 보유종목 그리드 상단 스트립
- [x] 수익 양/음에 따른 색상 변경 (Red/Blue)
- [x] 금일 매수/매도 건수
- [x] 지수 상태 표시 (MA60 위/아래 ▲/▼)

---

## Phase 8: 안정성 / 운영

### 8.1 Kiwoom API 요청 속도 제한기 ⬜
- [ ] TR 요청 큐 + 시간 기반 스로틀링
- [ ] 초당 5건 / 시간당 1000건 제한 관리
- [ ] 제한 초과 시 큐에 대기 → 자동 재시도

### 8.2 연결 상태 모니터링 ⬜
- [ ] API 연결 끊김 감지 (heartbeat or 이벤트)
- [ ] 연결 끊김 시 UI 경고 + 자동 재로그인 시도

### 8.3 비상 정지 기능 ✅
- [x] 단축키 F12로 전체 자동매매 즉시 중지
- [x] UI 빨간 비상정지 버튼 (상단 바)
- [x] 매도 모니터 + 조건식 모니터 + 종목 모니터링 일괄 중지
- [x] 미체결 주문 일괄 취소 기능

### 8.4 일일 리포트 자동 생성 ✅
- [x] 장 마감 후 금일 거래 요약 로그 (매수/매도 건수, 수익률)
- [x] 보유종목 현황 스냅샷 로그 기록
- [ ] 일별 총 자산 추이 DB 기록

---

## Phase 9: Python 원본 전략 완전 이식 (고급 매수 필터)

> Python `One_Day_Minervini_Mark_V1.py`에 있지만 아직 C#에 미구현된 조건들

### 9.1 Minervini 트렌드 필터 ⬜
- [ ] `종가 > MA50 > MA150` 확인 (일봉 데이터 필요)
- [ ] `MA50`이 10일 전보다 상승세 (`ma50 > ma50[i-10]`)
- [ ] 신저가 대비 30% 이상 (`close >= 240일신저가 × 1.3`)
- [ ] MA10과 MA20이 10% 이내 수렴 (`max(values) <= min(values) × 1.1`)

### 9.2 거래량/모멘텀 필터 ⬜
- [ ] 당일 거래량 >= 5일 평균 × 2 (`volume >= volume_5 × 2`)
- [ ] 60일 거래량 이평 상승추세 (`volume_60[i] > volume_60[i-5]`)
- [ ] 5일 거래량 이평 20일 전 대비 증가
- [ ] 전일까지 3일 중 하루라도 50일 평균 거래량 이하 (과열 아닌 상태)
- [ ] 299일 최고가 돌파 (`close >= max(high[i-298:i])`)

### 9.3 RS(상대강도) 필터 ⬜
- [ ] 5/10/20/30/50일 기간별 지수 대비 2배 이상 아웃퍼폼
- [ ] 100/200/299일 장기 지수 대비 아웃퍼폼
- [ ] 지수 하락 시: 종목 수익률 > 지수 수익률 / RS_Rate
- [ ] 지수 상승 시: 종목 수익률 > 지수 수익률 × RS_Rate

### 9.4 지수 필터 ✅
- [x] KOSPI 지수 >= MA60 (`close_jisu >= ma60_jisu`)
- [x] 지수 전일대비 -4% 이내 (`close_jisu > close_jisu[i-1] × 0.96`)
- [x] 지수 데이터 장개시시 갱신 + MA60 재계산
- [x] 지수 TR 응답 덮어쓰기 지원 (재요청 시 데이터 갱신)

### 9.5 신고가 타이밍 필터 ⬜
- [ ] 신고가 달성 후 0~10일 이내만 매수
- [ ] 신고가 갱신 시 singo_after_day 초기화
- [ ] `SINGO` / `SINGOHIGH` 데이터 계산

---

## Phase 10: 모의투자 운영 안정성 긴급 수정 ✅

> 모의투자 테스트 전 반드시 필요했던 크리티컬 버그 수정 (2026-04-09)

### 10.1 예수금 확인 후 매수 ✅
- [x] `m_estimatedBalance` 필드 추가 (추정예탁자산 캐싱)
- [x] `계좌잔고평가내역` TR 응답에서 `m_estimatedBalance` 갱신
- [x] `TryAutoBuy()` 주문 전 잔고 검증 (주문금액 vs 예탁자산)
- [x] 잔고 부족 시 매수 스킵 + 로그

### 10.2 로스컷가격 DB 저장 순서 수정 ✅
- [x] 매수 체결 시 `insertDB()` **전에** 로스컷가격 설정
- [x] 프로그램 재시작 시 로스컷가격=0 버그 해결

### 10.3 m_RealTimePrices thread-safety ✅
- [x] `Dictionary<string, RealTimePrice>` → `ConcurrentDictionary` 변경
- [x] 매도 모니터(백그라운드) + 실시간 데이터(UI 스레드) 동시접근 안전

### 10.4 SendCondition 무한루프 수정 ✅
- [x] `for(;;)` → `while(retryCount < 5)` 최대 5회 재시도로 변경
- [x] 실패 시 경고 로그 후 다음 조건식으로 진행

### 10.5 주문 거부 처리 ✅
- [x] `OnReceiveChejanData`에서 `접수거부`/`확인거부` 상태 감지
- [x] 거부된 주문번호 `m_dicBuyOrder`/`m_dicSellOrder`에서 정리

### 10.6 코스피 지수 데이터 장개시 갱신 ✅
- [x] 장개시(`구분=3`) 시 `requestJisuInfo()` 재호출
- [x] 지수일봉조회 TR 핸들러: 기존 데이터 덮어쓰기 (Add→대입)
- [x] MA60 재계산 + 갱신 로그

---

## Phase 12: 코드 안정성 / 버그 수정 (2026-04-09 코드 리뷰)

> 코드 전체 리뷰에서 발견된 thread-safety / 로직 버그 긴급 수정

### 12.1 m_dicBuyOrder / m_dicSellOrder thread-safety ✅
- [x] `Dictionary<string,string>` → `ConcurrentDictionary<string,string>` 변경
- [x] 매도 모니터(백그라운드) + UI 스레드 + 체잔 이벤트 동시접근 안전
- [x] `.Remove()` → `.TryRemove()` 변경

### 12.2 m_Max50DayVolume thread-safety ✅
- [x] `Dictionary<string,long>` → `ConcurrentDictionary<string,long>` 변경
- [x] 일봉 조회 백그라운드 + 매도 모니터 동시접근 안전

### 12.3 매도 중복 주문 방지 ✅
- [x] `m_PendingSellOrders` ConcurrentDictionary 추가 (매도 진행 중 종목 추적)
- [x] 매도 모니터에서 주문 전 이미 매도 진행 중이면 스킵
- [x] 매도 체결/거부 시 pending 제거

### 12.4 매수 중복 주문 방지 로직 개선 ✅
- [x] `m_PendingBuyOrders` ConcurrentDictionary 추가 (매수 진행 중 종목코드 추적)
- [x] TryAutoBuy에서 동일 종목코드 매수 주문 진행 중이면 스킵
- [x] 매수 체결/거부 시 pending 제거

### 12.5 최종수익금 / 최종수익률 계산 버그 수정 ✅
- [x] 부분매도(nR절반익절) 후 전량매도 시 `매수수량` 대신 `보유수량` 사용 버그 수정
- [x] 전량매도 시 부분매도 실현 수익 + 잔여수량 수익 합산하여 `최종수익금` 계산
- [x] `최종수익률` = 전체 수익금 / (매수가격 × 매수수량) × 100으로 통일

### 12.6 updateHoldingDays 날짜 파싱 수정 ✅
- [x] `DateTime.Parse(holding.매수일)` → `DateTime.ParseExact(holding.매수일, "yyyyMMdd", null)` 변경
- [x] 파싱 실패 시 안전 fallback (보유일++)

### 12.7 비상정지 미체결 주문 일괄 취소 ✅
- [x] `EmergencyStop()`에서 `m_PendingBuyOrders` / `m_PendingSellOrders` 기반 미체결 취소
- [x] 매수취소(3) / 매도취소(4) SendOrder 호출

### 12.8 장 마감 후 자동매수 차단 ✅
- [x] `m_IsMarketOpen` 플래그 추가 (장개시=true, 장마감알림/장마감=false)
- [x] `TryAutoBuy()` 진입 시 장 운영시간 체크 — 장외 시간 매수 원천 차단
- [x] 2026-04-09 로그에서 발견: 15:30 장마감 후 조건식 편입으로 매수시도 5건 (전부 거부됨)

---

## Phase 13: UX 개선 / 운영 안정성 (2026-04-09 2차 코드 리뷰) ✅

> 전체 코드 리뷰 + UX 개선 + 안정성 강화

### 13.1 예수금 0원 표시 버그 수정 ✅
- [x] `추정예탁자산` API 반환값이 0인 경우 `m_estimatedBalance` 덮어쓰기 방지
- [x] 장외시간/API 미응답 시 기존 잔고값 유지
- [x] 예수금 라벨은 항상 `m_estimatedBalance` 기준으로 표시

### 13.2 계좌 잔고 주기적 자동 갱신 ✅
- [x] `_balanceRefreshTimer` 10분 간격 자동 조회 (장중에만)
- [x] 로그인 성공 시 타이머 시작
- [x] FormClosing에서 타이머 정리

### 13.3 상단 바 전체 동적 레이아웃 ✅
- [x] `GetConditionButton`, `ATStartButton`, `ATStopButton` 동적 위치 재배치
- [x] `LoginButton`, `tableLayoutPanel1` 동적 위치 재배치
- [x] 버튼 표시/숨김 전환 시 `BringToFront()` 호출
- [x] 모든 상단 컨트롤 Z-Order 최상위 보장 (패널에 가려지지 않음)

### 13.4 DB/Config 경로 안정성 ✅
- [x] DB경로: 상대경로 → `AppDomain.CurrentDomain.BaseDirectory` 기준 절대경로
- [x] StrategyConfig 경로도 동일하게 앱 디렉토리 기준으로 변경
- [x] 다른 경로에서 프로그램 실행 시 DB/Config 유실 방지

### 13.5 StrategyConfig 로드 상태 로그 ✅
- [x] 설정 파일 로드 성공 시 주요 파라미터 로그 출력
- [x] 설정 파일 미존재 시 경고 로그 + 기본값으로 자동 생성/저장
- [x] 사용자가 어떤 설정으로 동작 중인지 명확히 확인 가능

### 13.6 m_HoldingDbInfoList thread-safety ✅
- [x] `m_HoldingLock` 객체 추가 (보유종목 리스트 동기화)
- [x] 매수 체결 시 `.Add()` 락 보호
- [x] 전량매도 시 `.RemoveAt()` 락 보호
- [x] 매도 모니터 `.ToList()` 스냅샷 락 보호

### 13.7 exe 아이콘 임베드 ✅
- [x] `CreateAppIcon()` 동일 디자인의 `app.ico` 파일 생성 (16/32/48/256px 멀티사이즈)
- [x] `.csproj`에 `<ApplicationIcon>app.ico</ApplicationIcon>` 추가
- [x] 바로가기/작업표시줄에서 캔들스틱 아이콘 표시

---

## Phase 14: 최종 안정화 (2026-04-09 3차 리뷰) ✅

> 모의투자 전 마지막 안정화 — 레이스컨디션/로깅/UX 마무리

### 14.1 장개시 DB 로드 레이스컨디션 수정 ✅
- [x] `m_DbLoaded` 플래그 추가 (DB 로드 완료 추적)
- [x] 장개시(구분=3) 이벤트에서 DB 미로드 시 최대 5초 대기
- [x] 타임아웃 시 경고 로그 후 계속 진행

### 14.2 대시보드 Z-Order 보장 ✅
- [x] `AdjustLayout()`에서 `_dashboardLabel.BringToFront()` 호출
- [x] 창 리사이즈 시 대시보드가 패널에 가려지지 않음

### 14.3 LogManager 비동기 큐 방식 개선 ✅
- [x] 동기 `File.AppendAllText` → `ConcurrentQueue` + 500ms 일괄 flush
- [x] UI 스레드 블로킹 제거 (네트워크 드라이브/느린 디스크 대응)
- [x] 타임스탬프 밀리초 추가 (`HH:mm:ss` → `HH:mm:ss.fff`)
- [x] 에러 시 `Debug.WriteLine` 출력 (무음 실패 방지)

### 14.4 향후 개선 사항 (모의투자 후) ⬜
- [ ] 크래시 복구 메커니즘 (pending order 저널링)
- [ ] 매도 모니터 수동 일시정지 토글
- [ ] 미체결 주문 UI 표시 (m_PendingBuyOrders/SellOrders)
- [ ] nR 익절 다단계 확장 (1회 → 여러 단계)
- [ ] 주문 수수료/세금 반영 수익 계산

---

## Phase 11: 실전 운영 고도화 (향후)

> 모의투자 테스트 결과를 바탕으로 추가할 항목

### 11.1 주문 체결 모니터링 ⬜
- [ ] 미체결 주문 자동 취소 (N분 경과 시)
- [ ] 부분체결 처리 개선 (체결분 DB 기록)
- [ ] 비상정지 시 미체결 일괄 취소

### 11.2 실시간 지수 감시 ✅
- [x] 코스피 실시간 체결가 수신 (SetRealReg "업종지수" "001")
- [x] 장중 지수 MA60 대비 모니터링 (`m_JisuBelowMA60` 플래그)
- [x] 지수 급락 시 신규 매수 즉시 차단 (`TryAutoBuy` 진입부 체크)

### 11.3 수익률 분석 리포트 ⬜
- [ ] 일별/주별/월별 수익률 집계
- [ ] 전략별 승률/평균수익 분석
- [ ] 매도유형별 통계 (로스컷/익절/장대음봉 등)

### 11.4 멀티 전략 지원 ⬜
- [ ] 조건식별 독립 StrategyConfig 할당
- [ ] 조건식별 독립 투자금/최대종목수 설정
- [ ] 전략간 격리 (동일 종목 다른 전략으로 보유 가능)

---

## 기 완료 항목

### 코드 리팩토링 ✅
- [x] `Thread.Abort()` → `CancellationTokenSource` 패턴 교체
- [x] `delay()` busy-wait → `Task.Delay()` async 교체
- [x] `OnReceiveChejanData` index out-of-range 버그 수정
- [x] DB 코드 중복 제거 → `Core/DbManager.cs` 중앙화
- [x] 로그 일원화 → `Core/LogManager.cs`
- [x] 매니저 클래스 분리 (ConditionManager, OrderManager, StrategyManager)
- [x] 데이터 모델 분리 → `Core/Models.cs`
- [x] 화면번호 상수화 → `Core/스크린.cs`
- [x] `.csproj` AllowUnsafeBlocks 제거

### 버그 수정 ✅
- [x] `_조건名인덱스` → `_조건명인덱스` (한자→한글 오타 수정)
- [x] 수익률 계산 공식 오류: `매도가/매수가*100` → `(매도가-매수가)/매수가*100`
- [x] `m_dicBuyOrder`/`m_dicSellOrder` `KeyNotFoundException` → `TryGetValue` 변경
- [x] 체잔/계좌데이터 `int.Parse` 크래시 → `TryParse` 변경
- [x] `LogMessage()` 크로스 스레드 접근 → `InvokeRequired` 체크 추가
- [x] `conditionFilteredGridView` 편출 삭제 → `Invoke` 처리
- [x] `showChart` CurrentRow null 체크 추가
- [x] `onReceiveRealCondition` 조건식 인덱스 범위 체크 추가
- [x] `chart1_AxisViewChanged` m_PriceInfoList null 체크 추가
- [x] 일봉 조회 하드코딩 300 → nCnt 사용 + try-catch
- [x] `매수/매도주문` Split 배열 길이 체크 추가
- [x] `m_Today` 고정 날짜 → 삭제 (실시간 DateTime 사용)
- [x] `requestJongmokDaily` 비활성 API 호출 명시

### UI 개선 ✅
- [x] DoubleBuffered + OptimizedDoubleBuffer 깜빡임 방지
- [x] DataGridView 숫자 인식 정렬 기능
- [x] 동적 아이콘 생성 (캔들스틱 차트 디자인)
- [x] UI 스타일링 (다크 테마 로그, 색상 코딩 버튼, 교차 행 색상)
- [x] 코드 기반 동적 레이아웃 (`AdjustLayout`) — 리사이즈/최대화 지원
- [x] 상단 바 버튼 동적 배치 (매수/매도/비상정지 — 창 축소 시 겨침 방지)
- [x] `axKHOpenAPI1` OCX 숨김 처리 (0,0, 1x1, Visible=false)
- [x] MinimumSize 1200x700, CenterScreen

### 안정성 ✅
- [x] `FormClosing` 핸들러 (CancellationToken 취소, 조건식 중지, DB 저장)
- [x] 테스트 매수/매도 버튼 확인 대화상자 추가
- [x] 계좌잔고평가내역 try-catch 감싸기

### 매도 전략 엔진 기초 ✅
- [x] `Core/SellStrategyManager.cs` — 매도 6대 규칙 스켈레톤 (로스컷, nR익절, 장대음봉, 급락, 최대보유일, EMA이탈)
- [x] `Core/StrategyConfig.cs` — 전략 파라미터 클래스 (R값, N배수, 최대보유일, 슬리피지 등)
- [x] `SellSignal`, `SellType` enum, `RealTimePrice` 모델 정의
- [x] `RoundToHogaUnit()`, `GetHogaUnit()` — 한국 주식 호가단위 변환
- [x] `CalculateSellPrice()`, `CalculateBuyPrice()` — 슬리피지 반영 가격 계산
- [x] `UpdateTrailingStop()` — 트레일링 스탑 로스컷가격 실시간 갱신
- [x] `IsSellBlocked()` — 거래정지/하한가 매도 불가 판별

### UI 보강 ✅
- [x] 패널 경계선 스타일링 (border + 미세 그림자)
- [x] `FormatHoldGrid()` — 보유종목 그리드 컬럼 순서/포맷/숨김 통일 관리
- [x] 전략 상태 대시보드 스트립 (보유종목수, 총수익금/률, 매도모니터 상태, 거래량캐시 건수)
- [x] 비상 정지 버튼 (빨간색, 상단 바) + F12 단축키

### 자동매도 파이프라인 ✅
- [x] `ExecuteSellOrder()` — SellSignal 기반 매도 주문 (슬리피지 반영)
- [x] `StartSellMonitor()` / `StopSellMonitor()` — 장중 2초 간격 매도 조건 체크
- [x] `OnReceiveChejanData` 부분매도/전량매도 분기 (nR절반익절 지원)
- [x] 전량매도 시 `SetRealRemove` + `m_RealTimePrices` 자동 정리
- [x] `FetchHoldingsDailyData()` — 보유종목 일봉 조회 + 50일 최대거래량 캐싱

### 설정 관리 ✅
- [x] `StrategyConfig.Load()` / `Save()` — JSON 파일 기반 설정 영속화
- [x] 앱 시작 시 자동 로드, 종료 시 자동 저장
- [x] 매도 전략 엔진에서 config 값 사용 (장대음봉 비율/스프레드, 급락기준 등)

### 자동매수 파이프라인 ✅
- [x] `TryAutoBuy()` — 조건식 편입 시 자동매수 (보유중복/최대종목수/수량계산/슬리피지)
- [x] 매수 완료 후 실시간 시세 등록 (`SetRealReg` 추가 등록 모드 "1")
- [x] 매수 완료 후 초기 로스컷가격 설정 (매수가 × (1 - R%))
- [x] 매수 완료 후 `RefreshHoldGrid()` 호출 (UI 즉시 반영)
- [x] 전량매도이유에 매도유형(로스컷/장대음봉 등) 기록 (sRQName 파싱)
- [x] 재매수금지기간 기본값 0 (Python 원본과 동일 — 비활성)

---

## 구현 우선순위

| 순서 | Phase | 설명 | 효과 |
|------|-------|------|------|
| **1** | Phase 1 | 보유종목 실시간 시세 | 매도의 전제조건 |
| **2** | Phase 2 | 매도 전략 엔진 | 핵심 매도 로직 (**EMA 이탈 포함 완료**) |
| **3** | Phase 3 | 매도 주문 실행 | 실제 매도 동작 |
| **4** | Phase 4 | 실시간 매도 루프 | **여기까지 = 자동 매도 완성** |
| **5** | Phase 5 | 매수 자동화 | **여기까지 = 완전 자동매매** |
| **6** | Phase 10+12 | 안정성 긴급수정 | **thread-safety/수익계산/중복방지** |
| **7** | Phase 6 | 설정 관리 | 파라미터 유연성 |
| **8** | Phase 7 | UI 보강 | **대시보드 완료 (지수/매수매도건수)** |
| **9** | Phase 8 | 안정성/운영 | **일일리포트/비상정지 완료** |
| **10** | Phase 11 | 실시간 지수감시 | **실시간 MA60 비교 완료** |
| **11** | Phase 13 | UX/안정성 2차 | **예수금버그/레이아웃/스레드안전/아이콘** |
| **12** | Phase 14 | 최종 안정화 | **DB레이스컨디션/로깅개선/대시보드** |
| **13** | Phase 9 | Python 고급 필터 이식 | 실전 수준 전략 품질 |
