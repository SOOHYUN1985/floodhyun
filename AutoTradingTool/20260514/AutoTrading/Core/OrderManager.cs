using System.Collections.Generic;

namespace AutoTradingTest.Core
{
    public class OrderManager
    {
        public Dictionary<string, string> SellOrders { get; set; } = new Dictionary<string, string>();
        public Dictionary<string, string> BuyOrders { get; set; } = new Dictionary<string, string>();

        public void AddBuyOrder(string orderNumber, string conditionName)
        {
            BuyOrders[orderNumber] = conditionName;
        }

        public void AddSellOrder(string orderNumber, string conditionName)
        {
            SellOrders[orderNumber] = conditionName;
        }

        public string GetBuyCondition(string orderNumber)
        {
            string result;
            return BuyOrders.TryGetValue(orderNumber, out result) ? result : null;
        }

        public string GetSellCondition(string orderNumber)
        {
            string result;
            return SellOrders.TryGetValue(orderNumber, out result) ? result : null;
        }

        public void RemoveBuyOrder(string orderNumber)
        {
            BuyOrders.Remove(orderNumber);
        }

        public void RemoveSellOrder(string orderNumber)
        {
            SellOrders.Remove(orderNumber);
        }
    }
}
