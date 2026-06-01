# AutoTradingTest - 키움증권 자동매매 시스템

## 개요

키움증권 OpenAPI를 활용한 한국 주식 **완전 자동매매** 시스템.  
Minervini 트렌드 템플릿 기반의 조건식 매수 → 6대 매도 전략 자동 실행.

> **현재 상태**: 모의투자 테스트 단계 (2026-04-09)  
> 자동매수 + 자동매도 + 실시간 감시 + 일일 리포트까지 구현 완료

## 기술 스택

| 항목 | 기술 |
|------|------|
| 언어 | C# (.NET Framework 4.8) |
| UI | WinForms (다크 테마, 동적 레이아웃) |
| 증권 API | 키움증권 OpenAPI (AxKHOpenAPILib COM interop) |
| 데이터베이스 | SQLite (System.Data.SQLite) |
| 차트 | System.Windows.Forms.DataVisualization.Charting |
| 빌드 | MSBuild (Visual Studio 18 Community) |

## 프로젝트 구조

```
AutoTradingTest/
├── Form1.cs                  # 메인 윈폼 - UI 이벤트, OpenAPI 콜백, 전체 흐름 제어
├── Form1.Designer.cs         # WinForms 디자이너 레이아웃
├── Program.cs                # 엔트리포인트
├── App.config                # 앱 설정
├── app.ico                   # 앱 아이콘 (캔들스틱 차트 + 상승 화살표)
├── Core/
│   ├── AsyncHelper.cs        # 비동기 유틸 (RunSafeAsync, RunOnUIThread)
│   ├── ConditionManager.cs   # 조건식 파싱, 종목 편입/편출 관리
│   ├── DbManager.cs          # SQLite CRUD (보유종목/거래내역)
│   ├── LogManager.cs         # 파일 로깅
│   ├── Models.cs             # 데이터 모델 (DBInfo, ConditionInfo, StockItemInfo 등)
│   ├── OrderManager.cs       # 주문번호-조건명 매핑 관리
│   ├── SellStrategyManager.cs # 매도 전략 엔진 (6대 매도 규칙 + EMA 이탈 + 호가단위)
│   ├── StrategyConfig.cs     # 전략 파라미터 설정 (R값, N배수, 보유일 등)
│   ├── StrategyManager.cs    # SMA/EMA 계산, 종목별 전략 데이터 관리
│   └── 스크린.cs              # 키움 화면번호 상수 정의
├── bin/Release/
│   ├── StrategyConfig.json   # 전략 설정 파일 (자동 생성)
│   ├── BujaGazua.sqlite      # 보유종목/거래내역 DB
│   └── Log/                  # 실행 로그 (일자별 .txt)
├── One_Day_Minervini_Mark_V1.py  # 매수/매도 전략 백테스트 (Python 원본)
└── packages/                 # NuGet 패키지 (EntityFramework, SQLite)
```

## 작동 흐름

```
1. 로그인 → 키움 OpenAPI 인증 (모의투자/실전 자동 감지)
2. 조건식 Update → 사용자 HTS 조건식 목록 로드
3. 조건식 체크 + [자동 매매 시작]
   ├── 선택 조건식에 실시간 조건식 등록 (SendCondition)
   ├── 편입 이벤트 수신 → TryAutoBuy() 자동매수
   │   ├── 지수 필터 (KOSPI ≥ MA60, 전일대비 -4% 이내)
   │   ├── 실시간 지수 MA60 비교 (m_JisuBelowMA60)
   │   ├── 보유 중복/최대종목수/잔고 확인
   │   ├── 슬리피지 반영 지정가 매수
   │   └── 매수 완료 → DB 저장 + 실시간 시세 등록
   ├── 보유종목 실시간 시세 감시 (2초 간격 매도 모니터)
   │   ├── 트레일링 로스컷 (R단위 상향)
   │   ├── nR 절반 익절 (수익 ≥ R×N%)
   │   ├── 장대음봉 + 거래량 전량매도
   │   ├── 전일대비 급락 전량매도
   │   ├── 최대보유일 초과 손절
   │   └── EMA 이탈 분할매도 (5/10/20일)
   └── 장 마감 → DB 일괄 저장 + 일일 리포트 생성
4. [자동 매매 종료] → 실시간 조건식 해제, 모니터링 중지
5. 비상 정지 (F12) → 전체 중지 + 미체결 일괄 취소
```

## 핵심 데이터 모델

### DBInfo (보유종목 / 거래내역)

| 필드 | 설명 |
|------|------|
| 종목명, 종목코드 | 종목 식별 |
| 매수일, 매수전략 | 매수 시점 및 진입 조건식명 |
| 매수수량, 보유수량, 매수가격 | 포지션 정보 |
| 로스컷단계, 로스컷가격 | 트레일링 스탑 상태 |
| 보유일 | 매수 후 경과일 |
| nR절반매도, nR절반매도가격/수량/일자 | nR 익절 상태 |
| 이평매도일자, 이평매도가격, 이평매도수량 | EMA 이탈 분할매도 상태 |
| 전량매도일, 전량매도이유, 매도가격 | 매도 결과 (History용) |
| 최종수익률, 최종수익금 | 성과 기록 |

### 키움 화면번호

| 상수 | 번호 | 용도 |
|------|------|------|
| 장운영정보 | 5000 | 장 시작/종료 실시간 |
| 계좌잔고 | 5001 | 계좌 평가 조회 |
| 조건종목정보 | 5002 | 조건식 종목 시세 조회 |
| 매수주문 | 5003 | 매수 주문 |
| 매도주문 | 5004 | 매도 주문 |
| 종목일봉정보 | 5005 | 일봉 차트 데이터 |
| 실시간조건식 | 5006 | 실시간 조건식 편입/편출 |
| 보유종목실시간 | 5007 | 보유종목 실시간 시세 |
| 지수실시간 | 5008 | 코스피 지수 실시간 |

## 매매 전략

### 매수 조건 (현재 구현)

- ✅ 키움 HTS 조건식 편입 시 자동매수
- ✅ 지수 ≥ 지수 MA60 (시장 상태 필터)
- ✅ 지수 전일대비 -4% 이내
- ✅ 실시간 지수 MA60 비교 (장중 급락 차단)
- ✅ 예수금(잔고) 확인 후 매수
- ✅ 최대 보유종목수 제한
- ✅ 동일 종목 중복매수/재매수 금지

### 매수 조건 (미구현 — Python 원본)

- ⬜ 종가 > MA50 > MA150 (Minervini 트렌드 확인)
- ⬜ 시가총액 ≥ 5000억
- ⬜ 신고가 이후 0~10일 이내
- ⬜ RS(상대강도): 지수 대비 아웃퍼폼
- ⬜ 거래량 폭발 (5일 평균의 2배 이상)

### 매도 규칙 (전부 구현 완료)

| 순서 | 규칙 | 수량 | 설명 |
|------|------|------|------|
| 1 | nR 절반 익절 | 50% | 수익률 ≥ R×N배 도달 시 (기본 21%) |
| 2 | 트레일링 로스컷 | 전량 | 현재가 < 로스컷가격 (R단위로 자동 상향) |
| 3 | 장대음봉 + 거래량 | 전량 | 50일 최대거래량 61.8% 이상 + 고가-종가 15% 이상 |
| 4 | 전일대비 급락 | 전량 | 전일 종가 대비 -13.5% 이하 |
| 5 | 최대보유일 초과 | 전량 | 20일 초과 + 손실 상태 |
| 6 | EMA 이탈 분할매도 | 1/N | EMA(5/10/20) 하향 이탈 + 수익 중일 때 단계별 매도 |

### 매도 스킵 조건
- 거래정지 (거래량 = 0)
- 하한가 (시가=고가=종가=저가, 하락)
- 가하한가 (종가=저가, -19% 이상, 거래량 부족)

## 설정 (StrategyConfig.json)

```json
{
  "R값": 7.0,
  "N배수": 3,
  "EMA매도기간": [5, 10, 20],
  "최대보유일": 20,
  "종목당최대투자금": 10000000,
  "최대보유종목수": 10,
  "슬리피지매수": 0.3,
  "슬리피지매도": 0.3,
  "시가총액하한": 500000000000,
  "재매수금지기간": 0
}
```

- 앱 시작 시 자동 로드, 종료 시 자동 저장
- 파일 미존재 시 기본값으로 자동 생성 (경고 로그 출력)
- 경로: `bin/Release/StrategyConfig.json` (앱 실행 디렉토리 기준)

## 데이터베이스

SQLite 파일: `BujaGazua.sqlite` (앱 실행 디렉토리 기준)

| 테이블 | 용도 |
|--------|------|
| HoldingTable | 현재 보유종목 |
| HistoryTable | 매도 완료 종목 (거래 이력) |

전량매도 시 HoldingTable → HistoryTable로 트랜잭션 이동.

## Thread-Safety

| 리소스 | 타입 | 보호 |
|--------|------|------|
| m_dicBuyOrder / m_dicSellOrder | ConcurrentDictionary | 자체 동기화 |
| m_PendingBuyOrders / m_PendingSellOrders | ConcurrentDictionary | 자체 동기화 |
| m_RealTimePrices | ConcurrentDictionary | 자체 동기화 |
| m_Max50DayVolume | ConcurrentDictionary | 자체 동기화 |
| m_HoldingDbInfoList | List + lock | m_HoldingLock 객체 |
| m_IsMarketOpen | volatile bool | 원자적 읽기/쓰기 |
| m_RealtimeJisuPrice | volatile int | 원자적 읽기/쓰기 |
| m_JisuBelowMA60 | volatile bool | 원자적 읽기/쓰기 |

## UI 기능

- **동적 레이아웃**: 창 크기 조절 시 모든 패널/버튼 자동 재배치
- **대시보드**: 보유종목수, 총수익금/률, 매도모니터 상태, 금일 매수/매도건수, 지수상태(▲/▼)
- **비상 정지**: F12 단축키 또는 빨간 버튼 — 전체 자동매매 즉시 중지 + 미체결 취소
- **테스트 매수/매도**: 상단 바에서 종목코드/가격/수량 입력 후 수동 주문 (확인 대화상자)
- **일일 리포트**: 장 마감 시 자동 생성 (매수/매도 건수, 승/패, 실현손익, 보유현황)
- **계좌 잔고 자동 갱신**: 10분 간격 (장중에만)

## 빌드 및 실행

```powershell
# MSBuild 빌드
& "C:\Program Files\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\MSBuild.exe" `
  AutoTradingTest.sln /p:Configuration=Release

# 실행 (32bit 필수 - 키움 OpenAPI 요구사항)
.\bin\Release\AutoTradingTest.exe
```

**주의사항**:
- 키움 OpenAPI는 32bit COM 컨트롤이므로 반드시 x86으로 빌드/실행
- 키움증권 OpenAPI 모듈이 설치되어 있어야 함
- 모의투자는 키움증권 홈페이지에서 별도 신청 필요

## 로그

- **파일 로그**: `bin/Release/Log/YYYY-MM-DD.txt` (일자별 자동 생성)
- **UI 로그**: 하단 로그 패널 (다크 테마, 타임스탬프 포함)
- **설정 로그**: 앱 시작 시 로드된 전략 파라미터 출력
- **일일 리포트**: 장 마감 시 매수/매도 요약 + 보유현황 스냅샷

## 구현 현황

| Phase | 설명 | 상태 |
|-------|------|------|
| Phase 1 | 보유종목 실시간 시세 감시 | ✅ 완료 |
| Phase 2 | 매도 전략 엔진 (6대 규칙 + EMA) | ✅ 완료 |
| Phase 3 | 매도 주문 실행 파이프라인 | ✅ 완료 |
| Phase 4 | 실시간 매도 체크 루프 | ✅ 완료 |
| Phase 5 | 매수 주문 자동화 | ✅ 완료 |
| Phase 6 | 설정/파라미터 관리 | ✅ 완료 (UI 패널 미구현) |
| Phase 7 | UI 보강 (대시보드) | ✅ 완료 |
| Phase 8 | 안정성/운영 (비상정지, 리포트) | ✅ 완료 |
| Phase 9 | Python 고급 필터 이식 | ⬜ 미착수 |
| Phase 10 | 모의투자 긴급 수정 | ✅ 완료 |
| Phase 11 | 실전 운영 고도화 | 🔧 부분 완료 |
| Phase 12 | 코드 안정성/버그 수정 | ✅ 완료 |
| Phase 13 | UX 개선/2차 안정성 | ✅ 완료 |
