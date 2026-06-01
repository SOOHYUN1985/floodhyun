using System;
using System.Collections.Generic;

namespace AutoTradingTest
{
    /// <summary>
    /// DB 보유종목/거래내역 정보
    /// </summary>
    public class DBInfo
    {
        // 1. History
        public string 종목명 { get; set; }
        public string 종목코드 { get; set; }
        public string 매수일 { get; set; }
        public string 매수전략 { get; set; }
        public string 전량매도일 { get; set; }
        public string 전량매도이유 { get; set; }
        public int 매도가격 { get; set; }
        public float 최종수익률 { get; set; }
        public int 최종수익금 { get; set; }

        // 2. Info
        public int 매수수량 { get; set; }
        public int 보유수량 { get; set; }
        public int 매수가격 { get; set; }
        public int 로스컷단계 { get; set; }
        public int 로스컷가격 { get; set; }
        public int 보유일 { get; set; }

        // UI 표시용 (DB 비저장)
        public int 현재가 { get; set; }
        public float 현재수익률 { get; set; }
        public int 현재수익금 { get; set; }
        public int 평가금 { get; set; } // 현재가 * 보유수량

        // 3. Strategy
        public bool 돌파매수 { get; set; }
        public string nR절반매도일자 { get; set; }
        public bool nR절반매도 { get; set; }
        public int nR절반매도가격 { get; set; }
        public int nR절반매도수량 { get; set; }
        public string 이평매도일자 { get; set; }
        public int 이평매도가격 { get; set; }
        public int 이평매도수량 { get; set; }
    }

    /// <summary>
    /// 조건식 정보
    /// </summary>
    public class ConditionInfo
    {
        public int 조건식번호 { get; set; }
        public string 조건식이름 { get; set; }
        public bool 실시간등록여부 { get; set; }
        public List<StockItemInfo> stockItemList { get; set; } = new List<StockItemInfo>();
    }

    /// <summary>
    /// 조건식 종목 정보
    /// </summary>
    public class StockItemInfo
    {
        public string 조건명 { get; set; }
        public string 종목명 { get; set; }
        public string 종목코드 { get; set; }
        public string 현재가 { get; set; }
        public string 전일대비 { get; set; }
        public string 등락률 { get; set; }
        public string 거래량 { get; set; }
        public string 시가 { get; set; }
        public string 고가 { get; set; }
        public string 저가 { get; set; }
    }

    /// <summary>
    /// 종목별 전략 검증 데이터 (이동평균, 최고/최저가 등)
    /// </summary>
    public class ConditionCheck
    {
        public int 최고가 { get; set; }
        public int 최저가 { get; set; }
        public List<PriceInfoEntityObject> priceInfoList { get; set; } = new List<PriceInfoEntityObject>();
        public Dictionary<string, List<int>> 이동평균 { get; set; } = new Dictionary<string, List<int>>();
    }

    /// <summary>
    /// 일봉/분봉 가격 정보
    /// </summary>
    public class PriceInfoEntityObject
    {
        public string 일자 { get; set; }
        public int 시가 { get; set; }
        public int 고가 { get; set; }
        public int 저가 { get; set; }
        public int 종가 { get; set; }
        public int 거래량 { get; set; }
    }

    /// <summary>
    /// 계좌 보유종목 정보
    /// </summary>
    public class HoldJongmok
    {
        public string 종목명 { get; set; }
        public string 종목코드 { get; set; }
        public string 잔고수량 { get; set; }
        public string 매입금액 { get; set; }
        public string 평가금액 { get; set; }
        public string 손익금액 { get; set; }
        public string 수익률 { get; set; }
        public string 현재가 { get; set; }
    }

    /// <summary>
    /// 종목 이력 정보
    /// </summary>
    public class StockItemHistoryInfo
    {
        public string 종목명 { get; set; }
        public string 종목코드 { get; set; }
        public string 현재가 { get; set; }
        public string 전일대비 { get; set; }
        public string 등락률 { get; set; }
        public string 거래량 { get; set; }
        public string 시가 { get; set; }
        public string 고가 { get; set; }
        public string 저가 { get; set; }
    }

    /// <summary>
    /// 일별 자산 추이 레코드 (DailyAssetTable)
    /// </summary>
    public class DailyAssetRecord
    {
        public string 날짜 { get; set; }
        public long 추정예탁자산 { get; set; }
        public long 총매입금액 { get; set; }
        public long 총평가금액 { get; set; }
        public long 보유평가손익 { get; set; }
        public long 당일실현손익 { get; set; }
        public int 보유종목수 { get; set; }
        public int 당일매수건수 { get; set; }
        public int 당일매도건수 { get; set; }
        public int 당일매도승수 { get; set; }
        public int 당일매도패수 { get; set; }
    }
}
