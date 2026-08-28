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

        /// <summary>JSON 파일로 설정 저장 — '_' 설명 키 포함 사람이 읽기 좋은 형식으로 저장</summary>
        public void Save()
        {
            try
            {
                var sb = new System.Text.StringBuilder();
                sb.AppendLine("{");
                sb.AppendLine("  \"_사용법\": \"이 파일을 수정하면 프로그램 재시작 없이도 다음 로드 시 반영됩니다. '_'로 시작하는 키는 설명용이며 동작에 영향 없습니다.\",");
                sb.AppendLine();
                sb.AppendLine("  \"_R값_설명\": \"초기 손절 기준(%). 매수가 × (1 - R/100) 이 손절가. 트레일링 스탑도 이 단위로 상승 조정됨. 예) 7 → -7% 손절, 15 → -15% 손절 (백테스트 1위: 15)\",");
                sb.AppendLine($"  \"R값\": {R값.ToString(System.Globalization.CultureInfo.InvariantCulture)},");
                sb.AppendLine();
                sb.AppendLine("  \"_N배수_설명\": \"부분익절 기준 배수. 매수가 × (1 + R × N / 100) 도달 시 보유수량 50% 매도. 부분익절활성화=false 이면 무시됨. 예) R=7, N=3 → +21%에서 절반매도\",");
                sb.AppendLine($"  \"N배수\": {N배수},");
                sb.AppendLine();
                sb.AppendLine("  \"_부분익절활성화_설명\": \"true: nR 절반익절 활성화 / false: 비활성화 (백테스트 상위전략은 false — EMA+트레일링스탑만 사용)\",");
                sb.AppendLine($"  \"부분익절활성화\": {부분익절활성화.ToString().ToLower()},");
                sb.AppendLine();
                sb.AppendLine("  \"_EMA매도기간_설명\": \"EMA 매도에 사용할 기간 목록(일). EMA전량매도=false 이면 기간 수만큼 분할매도, true 이면 첫 이탈 시 전량매도. 예) [10] + 전량매도 = 백테스트 1위 방식, [5,10,20] + 분할 = 현재 방식\",");
                sb.AppendLine($"  \"EMA매도기간\": [{string.Join(", ", EMA매도기간)}],");
                sb.AppendLine();
                sb.AppendLine("  \"_EMA전량매도_설명\": \"true: 첫 EMA 이탈 시 전량매도 (백테스트 상위전략 동일) / false: 기간 수만큼 분할매도\",");
                sb.AppendLine($"  \"EMA전량매도\": {EMA전량매도.ToString().ToLower()},");
                sb.AppendLine();
                sb.AppendLine("  \"_최대보유일_설명\": \"보유일이 이 값을 초과하고 평균손익이 손실이면 전량매도. 예) 20\",");
                sb.AppendLine($"  \"최대보유일\": {최대보유일},");
                sb.AppendLine();
                sb.AppendLine("  \"_급락매도기준_설명\": \"전일종가 대비 현재가 비율(%)이 이 값 이하이면 전량매도. 예) 86.5 → 전일 대비 -13.5% 이상 급락 시 매도\",");
                sb.AppendLine($"  \"급락매도기준\": {급락매도기준.ToString(System.Globalization.CultureInfo.InvariantCulture)},");
                sb.AppendLine();
                sb.AppendLine("  \"_장대음봉거래량비율_설명\": \"최근 50일 최대거래량 대비 당일 거래량 비율 임계값. 이 값 이상 + 스프레드 조건 충족 시 전량매도. 예) 0.618\",");
                sb.AppendLine($"  \"장대음봉거래량비율\": {장대음봉거래량비율.ToString(System.Globalization.CultureInfo.InvariantCulture)},");
                sb.AppendLine();
                sb.AppendLine("  \"_장대음봉스프레드기준_설명\": \"전일종가 대비 (고가-종가) 스프레드 기준(%). 이 값 이상이어야 장대음봉 조건 충족. 예) 15 → 고가-종가 스프레드 15% 이상\",");
                sb.AppendLine($"  \"장대음봉스프레드기준\": {장대음봉스프레드기준.ToString(System.Globalization.CultureInfo.InvariantCulture)},");
                sb.AppendLine();
                sb.AppendLine("  \"_슬리피지매수_설명\": \"매수 시 슬리피지(%). 실제 체결가 = 매수가 × (1 + 슬리피지/100). 백테스트는 0.5 사용\",");
                sb.AppendLine($"  \"슬리피지매수\": {슬리피지매수.ToString(System.Globalization.CultureInfo.InvariantCulture)},");
                sb.AppendLine();
                sb.AppendLine("  \"_슬리피지매도_설명\": \"매도 시 슬리피지(%). 실제 체결가 = 매도가 × (1 - 슬리피지/100). 백테스트는 0.5 사용\",");
                sb.AppendLine($"  \"슬리피지매도\": {슬리피지매도.ToString(System.Globalization.CultureInfo.InvariantCulture)},");
                sb.AppendLine();
                sb.AppendLine("  \"_시가총액하한_설명\": \"매수 허용 최소 시가총액(원). 예) 500000000000 = 5000억\",");
                sb.AppendLine($"  \"시가총액하한\": {시가총액하한},");
                sb.AppendLine();
                sb.AppendLine("  \"_재매수금지기간_설명\": \"전량매도 후 동일종목 재매수 금지 기간(일). 0이면 비활성화\",");
                sb.AppendLine($"  \"재매수금지기간\": {재매수금지기간},");
                sb.AppendLine();
                sb.AppendLine("  \"_종목당최대투자금_설명\": \"종목당 최대 투자금액(원). 예) 20000000 = 2000만원\",");
                sb.AppendLine($"  \"종목당최대투자금\": {종목당최대투자금},");
                sb.AppendLine();
                sb.AppendLine("  \"_최대보유종목수_설명\": \"동시에 보유 가능한 최대 종목 수\",");
                sb.AppendLine($"  \"최대보유종목수\": {최대보유종목수},");
                sb.AppendLine();
                sb.AppendLine("  \"_백테스트_1위_참고\": \"singo_299_medo_10 [15,200]: R값=15, N배수 무관(부분익절활성화=false), EMA매도기간=[10], EMA전량매도=true, 슬리피지매수/매도=0.5\",");
                sb.Append  ("  \"_백테스트_5위_참고\": \"singo_299_medo_10 [10,200]: R값=10, 부분익절활성화=false, EMA매도기간=[10], EMA전량매도=true, 슬리피지=0.5 (원칙에 가장 부합)\"");
                sb.AppendLine();
                sb.Append("}");

                File.WriteAllText(CONFIG_PATH, sb.ToString(), Encoding.UTF8);
            }
            catch (Exception ex)
            {
                LogManager.Log($"설정 저장 실패: {ex.Message}");
            }
        }
    }
}
