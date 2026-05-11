using System.Collections.Generic;
using System.Linq;

namespace AutoTradingTest.Core
{
    public class ConditionManager
    {
        public List<ConditionInfo> ConditionList { get; set; } = new List<ConditionInfo>();

        /// <summary>
        /// 조건식 문자열을 파싱하여 ConditionList에 저장
        /// </summary>
        public void ParseConditions(string conditionNameList)
        {
            ConditionList.Clear();
            string[] conditionNameArray = conditionNameList.Split(';');

            for (int i = 0; i < conditionNameArray.Length; i++)
            {
                string[] conditionInfo = conditionNameArray[i].Split('^');
                if (conditionInfo.Length == 2)
                {
                    int condNum;
                    if (int.TryParse(conditionInfo[0].Trim(), out condNum))
                    {
                        ConditionList.Add(new ConditionInfo()
                        {
                            조건식번호 = condNum,
                            조건식이름 = conditionInfo[1].Trim()
                        });
                    }
                }
            }

            ConditionList = ConditionList.OrderBy(p => p.조건식번호).ToList();
        }

        /// <summary>
        /// 특정 조건식에 종목 편입
        /// </summary>
        public bool AddStock(int conditionIndex, StockItemInfo stockItem)
        {
            if (conditionIndex < 0 || conditionIndex >= ConditionList.Count) return false;

            var condition = ConditionList[conditionIndex];
            if (condition.stockItemList.Any(s => s.종목코드 == stockItem.종목코드))
                return false;

            condition.stockItemList.Add(stockItem);
            return true;
        }

        /// <summary>
        /// 특정 조건식에서 종목 이탈
        /// </summary>
        public bool RemoveStock(int conditionIndex, string 종목코드)
        {
            if (conditionIndex < 0 || conditionIndex >= ConditionList.Count) return false;

            return ConditionList[conditionIndex].stockItemList.RemoveAll(p => p.종목코드 == 종목코드) > 0;
        }
    }
}
