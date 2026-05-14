using System;
using System.IO;
using System.Collections.Concurrent;
using System.Threading;

namespace AutoTradingTest.Core
{
    public static class LogManager
    {
        private static readonly string LogDir = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "Log");
        private static readonly ConcurrentQueue<string> _logQueue = new ConcurrentQueue<string>();
        private static readonly Timer _flushTimer;
        private static bool _dirCreated = false;

        static LogManager()
        {
            // 500ms 간격으로 큐의 로그를 파일에 일괄 기록 (UI 스레드 블로킹 방지)
            _flushTimer = new Timer(_ => FlushQueue(), null, 500, 500);
        }

        public static void Log(string message)
        {
            _logQueue.Enqueue($"[{DateTime.Now:HH:mm:ss.fff}] {message}");
        }

        private static void FlushQueue()
        {
            if (_logQueue.IsEmpty) return;

            try
            {
                if (!_dirCreated)
                {
                    Directory.CreateDirectory(LogDir);
                    _dirCreated = true;
                }

                string logFile = Path.Combine(LogDir, DateTime.Now.ToString("yyyy-MM-dd") + ".txt");
                var sb = new System.Text.StringBuilder();
                while (_logQueue.TryDequeue(out string entry))
                    sb.AppendLine(entry);

                if (sb.Length > 0)
                {
                    // UTF-8 BOM 포함으로 저장 → PowerShell/메모장에서 한글 깨짐 방지
                    var utf8Bom = new System.Text.UTF8Encoding(encoderShouldEmitUTF8Identifier: true);
                    File.AppendAllText(logFile, sb.ToString(), utf8Bom);
                }
            }
            catch (Exception ex)
            {
                // 파일 쓰기 실패 시 콘솔에 출력 (완전 무음 방지)
                System.Diagnostics.Debug.WriteLine($"LogManager 오류: {ex.Message}");
            }
        }
    }
}
