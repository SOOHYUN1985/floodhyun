using System;
using System.Collections.Generic;

namespace AutoTradingTest.Core
{
    public class StrategyManager
    {
        // 종목별 전략 정보 <종목명, ConditionCheck>
        public Dictionary<string, ConditionCheck> ConditionChecks { get; set; } = new Dictionary<string, ConditionCheck>();

        /// <summary>
        /// 단순이동평균 (SMA) 계산
        /// </summary>
        public static List<int> CalculateSMA(List<PriceInfoEntityObject> priceInfo, int period)
        {
            List<int> sma = new List<int>();
            int sum = 0;

            for (int i = 0; i < priceInfo.Count; i++)
            {
                sum += priceInfo[i].종가;

                if (i >= period - 1)
                {
                    sma.Add(sum / period);
                    sum -= priceInfo[i - period + 1].종가;
                }
            }

            return sma;
        }

        /// <summary>
        /// 지수이동평균 (EMA) 계산
        /// </summary>
        public static List<int> CalculateEMA(List<PriceInfoEntityObject> priceInfo, int period)
        {
            List<int> ema = new List<int>();
            double alpha = 2.0 / (period + 1);
            double previousEma = -1;

            for (int i = priceInfo.Count - 1; i >= 0; i--)
            {
                if (previousEma == -1)
                    previousEma = priceInfo[i].종가;
                else
                    previousEma = (priceInfo[i].종가 * alpha) + (previousEma * (1 - alpha));

                ema.Add((int)Math.Round(previousEma));
            }

            ema.Reverse();
            return ema;
        }

        /// <summary>
        /// 종목의 ConditionCheck 등록
        /// </summary>
        public void RegisterConditionCheck(string 종목명, ConditionCheck check)
        {
            ConditionChecks[종목명] = check;
        }

        /// <summary>
        /// 종목의 ConditionCheck 조회
        /// </summary>
        public ConditionCheck GetConditionCheck(string 종목명)
        {
            ConditionCheck result;
            return ConditionChecks.TryGetValue(종목명, out result) ? result : null;
        }
    }
}
