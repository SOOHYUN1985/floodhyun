using System;
using System.Collections.Generic;
using System.Linq;

namespace AutoTradingTest.Core
{
    /// <summary>
    /// 매도 유형
    /// </summary>
    public enum SellType
    {
        없음,
        로스컷,
        nR절반익절,
        장대음봉,
        급락매도,
        최대보유일,
        이평이탈
    }

    /// <summary>
    /// 매도 신호 정보
    /// </summary>
    public class SellSignal
    {
        public string 종목코드 { get; set; }
        public string 종목명 { get; set; }
        public SellType 매도유형 { get; set; }
        public int 매도수량 { get; set; }
        public string 매도이유 { get; set; }
        public bool 전량매도 { get; set; }
    }

    /// <summary>
    /// 종목별 실시간 시세 정보 (매도 판단용)
    /// </summary>
    public class RealTimePrice
    {
        public string 종목코드 { get; set; }
        public int 현재가 { get; set; }
        public int 시가 { get; set; }
        public int 고가 { get; set; }
        public int 저가 { get; set; }
        public int 전일종가 { get; set; }
        public long 거래량 { get; set; }
    }

    /// <summary>
    /// 매도 전략 엔진
    /// Python One_Day_Minervini_Mark_V1.py의 매도 규칙을 C#으로 이식
    /// </summary>
    public class SellStrategyManager
    {
        private readonly StrategyConfig _config;

        public SellStrategyManager(StrategyConfig config)
        {
            _config = config;
        }

        /// <summary>
        /// 보유종목 1건에 대해 매도 조건 체크 (우선순위 순)
        /// </summary>
        /// <returns>매도 신호 (없으면 null)</returns>
        public SellSignal CheckSellConditions(DBInfo holding, RealTimePrice price, long 최근50일최대거래량, Dictionary<int, int> emaValues = null)
        {
            if (price == null || holding == null) return null;

            // 매도 불가 상황 스킵
            if (IsSellBlocked(price)) return null;

            // 1. nR 절반 익절
            var signal = CheckNR절반익절(holding, price);
            if (signal != null) return signal;

            // 2. 트레일링 로스컷
            signal = CheckTrailingStop(holding, price);
            if (signal != null) return signal;

            // 3. 장대음봉 + 거래량
            signal = Check장대음봉(holding, price, 최근50일최대거래량);
            if (signal != null) return signal;

            // 4. 전일대비 급락
            signal = Check급락매도(holding, price);
            if (signal != null) return signal;

            // 5. 최대보유일 초과
            signal = Check최대보유일(holding, price);
            if (signal != null) return signal;

            // 6. EMA 이탈 분할매도
            signal = CheckEMA이탈(holding, price, emaValues);
            if (signal != null) return signal;

            return null;
        }

        /// <summary>
        /// 트레일링 스탑 로스컷가격 갱신 (실시간 호출)
        /// 수익이 R×j에 도달할 때마다 로스컷가격을 R×(j-1)로 상향
        /// </summary>
        public void UpdateTrailingStop(DBInfo holding, int currentPrice)
        {
            if (holding.매수가격 <= 0) return;
            double R = _config.R값;

            for (int j = holding.로스컷단계 + 1; j <= 100; j++)
            {
                double targetPrice = holding.매수가격 * (1.0 + R * j / 100.0);
                if (currentPrice >= targetPrice)
                {
                    if (j == 1)
                        holding.로스컷가격 = holding.매수가격; // 본전
                    else
                        holding.로스컷가격 = (int)(holding.매수가격 * (1.0 + R * (j - 1) / 100.0));

                    holding.로스컷단계 = j;
                }
                else
                {
                    break;
                }
            }
        }

        /// <summary>
        /// 매도 불가 상황 판별
        /// </summary>
        private bool IsSellBlocked(RealTimePrice price)
        {
            // 거래정지 (거래량 == 0)
            if (price.거래량 == 0) return true;

            // 하한가 (시가=고가=종가=저가 AND 하락)
            if (price.시가 == price.고가 && price.고가 == price.현재가 && price.현재가 == price.저가
                && price.현재가 < price.전일종가)
                return true;

            // 가하한가 (종가=저가 AND 전일대비 -19% 이상)
            if (price.전일종가 > 0 && price.현재가 == price.저가
                && (double)price.현재가 / price.전일종가 * 100 <= 81.0)
                return true;

            return false;
        }

        /// <summary>
        /// 1. nR 절반 익절: 수익률 >= R × N배 도달 시 50% 매도
        /// </summary>
        private SellSignal CheckNR절반익절(DBInfo holding, RealTimePrice price)
        {
            if (holding.nR절반매도) return null; // 이미 실행됨
            if (holding.매수가격 <= 0) return null;

            double targetPrice = holding.매수가격 * (1.0 + _config.R값 * _config.N배수 / 100.0);
            if (price.현재가 >= targetPrice)
            {
                int sellQty = holding.보유수량 / 2;
                if (sellQty <= 0) sellQty = 1;

                return new SellSignal
                {
                    종목코드 = holding.종목코드,
                    종목명 = holding.종목명,
                    매도유형 = SellType.nR절반익절,
                    매도수량 = sellQty,
                    매도이유 = $"수익률 {_config.R값 * _config.N배수}% 도달 절반익절",
                    전량매도 = false
                };
            }
            return null;
        }

        /// <summary>
        /// 2. 트레일링 로스컷: 현재가 < 로스컷가격 → 전량매도
        /// </summary>
        private SellSignal CheckTrailingStop(DBInfo holding, RealTimePrice price)
        {
            if (holding.로스컷가격 <= 0) return null;

            if (price.현재가 < holding.로스컷가격)
            {
                return new SellSignal
                {
                    종목코드 = holding.종목코드,
                    종목명 = holding.종목명,
                    매도유형 = SellType.로스컷,
                    매도수량 = holding.보유수량,
                    매도이유 = $"로스컷 {holding.로스컷단계}단계 (기준가 {holding.로스컷가격:N0})",
                    전량매도 = true
                };
            }
            return null;
        }

        /// <summary>
        /// 3. 장대음봉 + 거래량: 50일 최대거래량 61.8% 이상 + 고가-종가 15% 이상
        /// </summary>
        private SellSignal Check장대음봉(DBInfo holding, RealTimePrice price, long 최근50일최대거래량)
        {
            if (최근50일최대거래량 <= 0 || price.전일종가 <= 0) return null;

            bool volumeCondition = price.거래량 >= (long)(최근50일최대거래량 * _config.장대음봉거래량비율);
            double highLowSpread = ((double)price.고가 / price.전일종가 - (double)price.현재가 / price.전일종가) * 100;
            bool candleCondition = highLowSpread >= _config.장대음봉스프레드기준;

            if (volumeCondition && candleCondition)
            {
                return new SellSignal
                {
                    종목코드 = holding.종목코드,
                    종목명 = holding.종목명,
                    매도유형 = SellType.장대음봉,
                    매도수량 = holding.보유수량,
                    매도이유 = $"장대음봉 (거래량 {price.거래량:N0}, 고가-종가 {highLowSpread:F1}%)",
                    전량매도 = true
                };
            }
            return null;
        }

        /// <summary>
        /// 4. 전일대비 급락: 종가/전일종가 × 100 <= 86.5
        /// </summary>
        private SellSignal Check급락매도(DBInfo holding, RealTimePrice price)
        {
            if (price.전일종가 <= 0) return null;

            double ratio = (double)price.현재가 / price.전일종가 * 100;
            if (ratio <= _config.급락매도기준)
            {
                return new SellSignal
                {
                    종목코드 = holding.종목코드,
                    종목명 = holding.종목명,
                    매도유형 = SellType.급락매도,
                    매도수량 = holding.보유수량,
                    매도이유 = $"전일대비 {(100 - ratio):F1}% 급락",
                    전량매도 = true
                };
            }
            return null;
        }

        /// <summary>
        /// 5. 최대보유일 초과: 보유일 > 최대보유일 AND 손실 중
        /// </summary>
        private SellSignal Check최대보유일(DBInfo holding, RealTimePrice price)
        {
            if (holding.보유일 <= _config.최대보유일) return null;
            if (holding.매수가격 <= 0) return null;

            if (price.현재가 < holding.매수가격) // 손실 상태
            {
                return new SellSignal
                {
                    종목코드 = holding.종목코드,
                    종목명 = holding.종목명,
                    매도유형 = SellType.최대보유일,
                    매도수량 = holding.보유수량,
                    매도이유 = $"보유 {holding.보유일}일 초과 + 손실 상태",
                    전량매도 = true
                };
            }
            return null;
        }

        /// <summary>
        /// 6. EMA 이탈 분할매도: 수익 중 + 종가 < EMA → 남은수량의 1/(남은단계수) 매도
        /// 이평매도일자 필드에 완료 단계를 콤마구분으로 저장 (예: "5,10")
        /// </summary>
        private SellSignal CheckEMA이탈(DBInfo holding, RealTimePrice price, Dictionary<int, int> emaValues)
        {
            if (emaValues == null || emaValues.Count == 0) return null;
            if (holding.매수가격 <= 0) return null;
            // 수익 중일 때만 EMA 이탈 매도 (손실 중이면 로스컷에서 처리)
            if (price.현재가 <= holding.매수가격) return null;

            // 이미 완료된 EMA 단계 파싱
            var completedStages = new HashSet<int>();
            if (!string.IsNullOrEmpty(holding.이평매도일자))
            {
                foreach (var s in holding.이평매도일자.Split(','))
                {
                    if (int.TryParse(s.Trim(), out int stage))
                        completedStages.Add(stage);
                }
            }

            // 설정된 EMA 기간 중 미완료 + 이탈 조건 확인 (짧은 기간부터)
            var sortedPeriods = _config.EMA매도기간.OrderBy(p => p).ToArray();
            var remainingStages = sortedPeriods.Where(p => !completedStages.Contains(p)).ToArray();
            if (remainingStages.Length == 0) return null;

            foreach (int period in remainingStages)
            {
                if (!emaValues.TryGetValue(period, out int emaValue)) continue;
                if (emaValue <= 0) continue;

                // 현재가 < EMA값 → 이탈
                if (price.현재가 < emaValue)
                {
                    int 남은단계수 = remainingStages.Length;
                    int sellQty = holding.보유수량 / 남은단계수;
                    if (sellQty <= 0) sellQty = 1;

                    // 마지막 남은 단계이면 전량매도
                    bool isFullSell = (남은단계수 == 1) || (sellQty >= holding.보유수량);

                    return new SellSignal
                    {
                        종목코드 = holding.종목코드,
                        종목명 = holding.종목명,
                        매도유형 = SellType.이평이탈,
                        매도수량 = isFullSell ? holding.보유수량 : sellQty,
                        매도이유 = $"EMA{period} 이탈 (현재가 {price.현재가:N0} < EMA{period} {emaValue:N0})",
                        전량매도 = isFullSell
                    };
                }
            }
            return null;
        }

        /// <summary>
        /// EMA 이탈 매도 완료 시 단계 기록 (Form1에서 체결 후 호출)
        /// </summary>
        public static string RecordEmaStage(string 현재이평매도일자, int completedPeriod)
        {
            if (string.IsNullOrEmpty(현재이평매도일자))
                return completedPeriod.ToString();
            return 현재이평매도일자 + "," + completedPeriod;
        }

        /// <summary>
        /// EMA 이탈 매도 이유에서 EMA 기간 추출 (예: "EMA5 이탈 ..." → 5)
        /// </summary>
        public static int ParseEmaPeriodFromReason(string 매도이유)
        {
            if (string.IsNullOrEmpty(매도이유)) return 0;
            // "EMA5 이탈", "EMA10 이탈", "EMA20 이탈" 패턴
            var match = System.Text.RegularExpressions.Regex.Match(매도이유, @"EMA(\d+)");
            if (match.Success && int.TryParse(match.Groups[1].Value, out int period))
                return period;
            return 0;
        }

        // ── 유틸리티 ──

        /// <summary>
        /// 한국 주식 호가단위에 맞춰 가격 정리 (매도 시 내림, 매수 시 올림)
        /// </summary>
        public static int RoundToHogaUnit(int price, bool isBuy)
        {
            int unit = GetHogaUnit(price);
            if (isBuy)
                return (int)(Math.Ceiling((double)price / unit) * unit);
            else
                return (int)(Math.Floor((double)price / unit) * unit);
        }

        /// <summary>
        /// 가격대별 호가단위 반환
        /// </summary>
        public static int GetHogaUnit(int price)
        {
            int absPrice = Math.Abs(price);
            if (absPrice < 1000) return 1;
            if (absPrice < 5000) return 5;
            if (absPrice < 10000) return 10;
            if (absPrice < 50000) return 50;
            if (absPrice < 100000) return 100;
            if (absPrice < 500000) return 500;
            return 1000;
        }

        /// <summary>
        /// 슬리피지 반영 매도가격 계산
        /// </summary>
        public int CalculateSellPrice(int currentPrice)
        {
            return RoundToHogaUnit((int)(currentPrice * (1.0 - _config.슬리피지매도 / 100.0)), false);
        }

        /// <summary>
        /// 슬리피지 반영 매수가격 계산
        /// </summary>
        public int CalculateBuyPrice(int currentPrice)
        {
            return RoundToHogaUnit((int)(currentPrice * (1.0 + _config.슬리피지매수 / 100.0)), true);
        }
    }
}
