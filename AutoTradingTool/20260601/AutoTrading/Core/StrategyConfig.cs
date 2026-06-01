using System;
using System.IO;
using System.Runtime.Serialization.Json;
using System.Text;

namespace AutoTradingTest.Core
{
    /// <summary>
    /// 자동매매 전략 파라미터 설정
    /// Python 백테스트의 profit_loss_ratio, 보유일, 이평선 등에 대응
    /// </summary>
    public class StrategyConfig
    {
        private static readonly string CONFIG_PATH = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "StrategyConfig.json");

        /// <summary>로스컷 기준 수익률 (%) - Python의 profit_loss_ratio[0]</summary>
        public double R값 { get; set; } = 7.0;

        /// <summary>절반익절 기준 배수 - Python의 profit_loss_ratio[1]</summary>
        public int N배수 { get; set; } = 3;

        /// <summary>이평선 매도 기간 리스트 - Python의 strategy[1]</summary>
        public int[] EMA매도기간 { get; set; } = new int[] { 5, 10, 20 };

        /// <summary>최대 보유일 - 초과 + 손실 시 전량매도</summary>
        public int 최대보유일 { get; set; } = 20;

        /// <summary>종목당 최대 투자금 (원)</summary>
        public int 종목당최대투자금 { get; set; } = 20_000_000;

        /// <summary>최대 동시 보유 종목수</summary>
        public int 최대보유종목수 { get; set; } = 10;

        /// <summary>매수 슬리피지 (%)</summary>
        public double 슬리피지매수 { get; set; } = 0.3;

        /// <summary>매도 슬리피지 (%)</summary>
        public double 슬리피지매도 { get; set; } = 0.3;

        /// <summary>시가총액 하한 (원)</summary>
        public long 시가총액하한 { get; set; } = 500_000_000_000;

        /// <summary>장대음봉 거래량 비율 (50일 최대 대비)</summary>
        public double 장대음봉거래량비율 { get; set; } = 0.618;

        /// <summary>장대음봉 고가-종가 스프레드 기준 (%)</summary>
        public double 장대음봉스프레드기준 { get; set; } = 15.0;

        /// <summary>전일대비 급락 기준 (%)</summary>
        public double 급락매도기준 { get; set; } = 86.5;

        /// <summary>부분익절(nR) 활성화 여부 — false면 nR 절반익절 비발동 (백테스트 상위전략 기본값: false)</summary>
        public bool 부분익절활성화 { get; set; } = true;

        /// <summary>EMA 이탈 시 전량매도 여부 — true면 첫 EMA 이탈 시 전량매도, false면 분할매도 (백테스트 상위전략 기본값: true)</summary>
        public bool EMA전량매도 { get; set; } = false;

        /// <summary>매도 후 재매수 금지 기간 (일) — 0이면 비활성화 (Python 원본: 주석처리됨)</summary>
        public int 재매수금지기간 { get; set; } = 0;

        /// <summary>JSON 파일에서 설정 로드 (없으면 기본값)</summary>
        public static StrategyConfig Load()
        {
            try
            {
                if (File.Exists(CONFIG_PATH))
                {
                    string json = File.ReadAllText(CONFIG_PATH, Encoding.UTF8);
                    var serializer = new DataContractJsonSerializer(typeof(StrategyConfig));
                    using (var ms = new MemoryStream(Encoding.UTF8.GetBytes(json)))
                    {
                        var config = (StrategyConfig)serializer.ReadObject(ms);
                        LogManager.Log($"설정 로드 완료: R값={config.R값}, N배수={config.N배수}, 최대보유일={config.최대보유일}, 종목당투자금={config.종목당최대투자금:N0}, 부분익절={config.부분익절활성화}, EMA전량매도={config.EMA전량매도}");
                        return config;
                    }
                }
                else
                {
                    LogManager.Log($"[주의] {CONFIG_PATH} 파일 없음 — 기본값으로 생성합니다.");
                    var config = new StrategyConfig();
                    config.Save();
                    return config;
                }
            }
            catch (Exception ex)
            {
                LogManager.Log($"설정 로드 실패 (기본값 사용): {ex.Message}");
            }
            return new StrategyConfig();
        }

        /// <summary>JSON 파일로 설정 저장</summary>
        public void Save()
        {
            try
            {
                var serializer = new DataContractJsonSerializer(typeof(StrategyConfig));
                using (var ms = new MemoryStream())
                {
                    serializer.WriteObject(ms, this);
                    string json = Encoding.UTF8.GetString(ms.ToArray());
                    File.WriteAllText(CONFIG_PATH, json, Encoding.UTF8);
                }
            }
            catch (Exception ex)
            {
                LogManager.Log($"설정 저장 실패: {ex.Message}");
            }
        }
    }
}
