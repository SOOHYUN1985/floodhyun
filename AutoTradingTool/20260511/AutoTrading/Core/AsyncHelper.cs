using System;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace AutoTradingTest.Core
{
    public static class AsyncHelper
    {
        public static async Task RunSafeAsync(Func<Task> func, Action<Exception> onError = null)
        {
            try
            {
                await func();
            }
            catch (Exception ex)
            {
                onError?.Invoke(ex);
            }
        }

        public static void RunOnUIThread(Control control, Action action)
        {
            if (control.InvokeRequired)
                control.Invoke(action);
            else
                action();
        }
    }
}
