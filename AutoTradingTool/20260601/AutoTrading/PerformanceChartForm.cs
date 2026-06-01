using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using System.Windows.Forms;
using System.Windows.Forms.DataVisualization.Charting;

namespace AutoTradingTest
{
    /// <summary>
    /// 계좌 수익률 vs 주요 지수 비교 차트
    /// </summary>
    public class PerformanceChartForm : Form
    {
        // ── Static HTTP client ────────────────────────────────
        private static readonly HttpClient _http;
        static PerformanceChartForm()
        {
            ServicePointManager.SecurityProtocol =
                SecurityProtocolType.Tls12 | SecurityProtocolType.Tls11 | SecurityProtocolType.Tls;
            _http = new HttpClient { Timeout = TimeSpan.FromSeconds(20) };
            _http.DefaultRequestHeaders.Add("User-Agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36");
            _http.DefaultRequestHeaders.Add("Accept", "application/json,*/*");
        }

        // ── Data ──────────────────────────────────────────────
        private readonly List<DailyAssetRecord> _allAccountData;
        private List<DailyAssetRecord> _accountData = new List<DailyAssetRecord>();
        private readonly Dictionary<string, List<(DateTime date, double close)>> _indexData
            = new Dictionary<string, List<(DateTime, double)>>();

        private DateTime _fromDate = DateTime.Today.AddMonths(-3);
        private DateTime _toDate   = DateTime.Today;

        // ── Index config (name, yahoo symbol, color, line width) ─
        private static readonly (string name, string symbol, Color color, int lw)[] Indices =
        {
            ("내 계좌",   null,    Color.FromArgb(255, 215,   0), 3),
            ("코스피",    "^KS11", Color.FromArgb(255,  80,  80), 2),
            ("코스닥",    "^KQ11", Color.FromArgb(255, 160,  40), 2),
            ("나스닥",    "^IXIC", Color.FromArgb( 40, 210, 100), 2),
            ("S&P500",   "^GSPC", Color.FromArgb( 80, 160, 255), 2),
            ("다우존스",  "^DJI",  Color.FromArgb(180,  80, 255), 2),
            ("러셀2000", "^RUT",  Color.FromArgb(255, 100, 200), 2),
        };

        private readonly Dictionary<string, bool> _visible = new Dictionary<string, bool>();

        // ── UI controls ───────────────────────────────────────
        private Chart _chart;
        private Label _statusLabel;
        private Label _loadingLabel;
        private Panel _topPanel;
        private DateTimePicker _fromPicker, _toPicker;

        // ── Colors ────────────────────────────────────────────
        private static readonly Color BgDark   = Color.FromArgb(16, 22, 34);
        private static readonly Color BgPanel  = Color.FromArgb(23, 31, 46);
        private static readonly Color BgCard   = Color.FromArgb(33, 43, 62);
        private static readonly Color BgActive = Color.FromArgb(45, 120, 230);
        private static readonly Color TextLt   = Color.FromArgb(215, 225, 242);
        private static readonly Color TextMu   = Color.FromArgb(120, 140, 172);
        private static readonly Color Border   = Color.FromArgb(48,  62,  88);
        private static readonly Color GridLine = Color.FromArgb(34,  46,  66);

        // ── Constructor ───────────────────────────────────────
        public PerformanceChartForm(List<DailyAssetRecord> accountData)
        {
            _allAccountData = accountData ?? new List<DailyAssetRecord>();
            foreach (var idx in Indices) _visible[idx.name] = true;
            BuildUI();
            this.Shown += async (s, e) => await RefreshAsync(3);
        }

        // ════════════════════════════════════════════════════
        //  UI 구성
        // ════════════════════════════════════════════════════
        private void BuildUI()
        {
            Text            = "수익률 비교 — 계좌 vs 주요 지수";
            Size            = new Size(1320, 780);
            MinimumSize     = new Size(900, 560);
            StartPosition   = FormStartPosition.CenterParent;
            BackColor       = BgDark;
            Font            = new Font("맑은 고딕", 9f);
            DoubleBuffered  = true;

            BuildTopPanel();
            BuildChart();
            BuildStatusBar();

            Controls.SetChildIndex(_statusLabel, 0);
            Controls.SetChildIndex(_chart,       1);
            Controls.SetChildIndex(_topPanel,    2);
        }

        // ── 상단 패널 ─────────────────────────────────────────
        private void BuildTopPanel()
        {
            _topPanel = new Panel { Dock = DockStyle.Top, Height = 95, BackColor = BgPanel };

            // Title
            _topPanel.Controls.Add(new Label
            {
                Text = "수익률 비교",
                Font = new Font("맑은 고딕", 14f, FontStyle.Bold),
                ForeColor = TextLt, AutoSize = true,
                Location = new Point(16, 12)
            });
            _topPanel.Controls.Add(new Label
            {
                Text = "기준일 = 100  |  내 계좌 vs 코스피/코스닥/나스닥/S&P500/다우/러셀2000",
                Font = new Font("맑은 고딕", 8.5f),
                ForeColor = TextMu, AutoSize = true,
                Location = new Point(18, 36), BackColor = Color.Transparent
            });

            // ── 기간 버튼 ──────────────────────────────────────
            var periods = new[] { ("1M", 1), ("3M", 3), ("6M", 6), ("1Y", 12), ("전체", 0) };
            int bx = 210; Button defBtn = null;
            foreach (var (label, months) in periods)
            {
                int m = months;
                var btn = MakePeriodBtn(label, bx, m);
                _topPanel.Controls.Add(btn);
                if (m == 3) { btn.BackColor = BgActive; btn.ForeColor = Color.White; defBtn = btn; }
                bx += btn.Width + 5;
            }

            // ── 지수 토글 체크박스 ─────────────────────────────
            bx += 12;
            foreach (var idx in Indices)
            {
                string name = idx.name; Color col = idx.color;
                var chk = new CheckBox
                {
                    Text = name, Checked = true,
                    ForeColor = col,
                    Font = new Font("맑은 고딕", 8.5f, FontStyle.Bold),
                    AutoSize = true,
                    Location = new Point(bx, 16),
                    BackColor = Color.Transparent,
                    Cursor = Cursors.Hand,
                };
                chk.CheckedChanged += (s, e) => { _visible[name] = chk.Checked; RedrawChart(); };
                _topPanel.Controls.Add(chk);
                bx += chk.PreferredSize.Width + 14;
            }

            // ── 직접 입력 ──────────────────────────────────────
            bx += 12;
            _fromPicker = new DateTimePicker { Width = 96, Location = new Point(bx, 14), Format = DateTimePickerFormat.Short };
            _fromPicker.Value = DateTime.Today.AddMonths(-3);
            _topPanel.Controls.Add(_fromPicker); bx += _fromPicker.Width + 3;
            _topPanel.Controls.Add(new Label { Text = "~", ForeColor = TextLt, AutoSize = true, Location = new Point(bx, 17), BackColor = Color.Transparent });
            bx += 13;
            _toPicker = new DateTimePicker { Width = 96, Location = new Point(bx, 14), Format = DateTimePickerFormat.Short };
            _toPicker.Value = DateTime.Today;
            _topPanel.Controls.Add(_toPicker); bx += _toPicker.Width + 4;

            var applyBtn = new Button
            {
                Text = "조회", Width = 46, Height = 26,
                Location = new Point(bx, 14),
                FlatStyle = FlatStyle.Flat,
                BackColor = Color.FromArgb(0, 140, 90), ForeColor = Color.White,
                Font = new Font("맑은 고딕", 9f), Cursor = Cursors.Hand
            };
            applyBtn.FlatAppearance.BorderColor = Color.FromArgb(0, 110, 70);
            applyBtn.Click += async (s, e) =>
            {
                ResetPeriodBtns();
                _fromDate = _fromPicker.Value.Date;
                _toDate   = _toPicker.Value.Date;
                await LoadAndDraw();
            };
            _topPanel.Controls.Add(applyBtn);

            // ── 로딩 라벨 ─────────────────────────────────────
            _loadingLabel = new Label
            {
                Text = "", AutoSize = true,
                Font = new Font("맑은 고딕", 8.5f),
                ForeColor = Color.FromArgb(90, 160, 245),
                Location = new Point(18, 60),
                BackColor = Color.Transparent
            };
            _topPanel.Controls.Add(_loadingLabel);

            Controls.Add(_topPanel);
        }

        private Button MakePeriodBtn(string label, int x, int months)
        {
            var btn = new Button
            {
                Text = label, Width = 52, Height = 28,
                Location = new Point(x, 14),
                FlatStyle = FlatStyle.Flat,
                BackColor = BgCard, ForeColor = TextLt,
                Font = new Font("맑은 고딕", 9f, FontStyle.Bold),
                Cursor = Cursors.Hand, Tag = months
            };
            btn.FlatAppearance.BorderColor = Border;
            btn.Click += async (s, e) =>
            {
                ResetPeriodBtns();
                btn.BackColor = BgActive; btn.ForeColor = Color.White;
                await RefreshAsync(months);
            };
            return btn;
        }

        private void ResetPeriodBtns()
        {
            foreach (Control c in _topPanel.Controls)
                if (c is Button b && b.Tag is int) { b.BackColor = BgCard; b.ForeColor = TextLt; }
        }

        // ── 차트 영역 ─────────────────────────────────────────
        private void BuildChart()
        {
            _chart = new Chart
            {
                Dock = DockStyle.Fill,
                BackColor = BgDark,
                BorderlineColor = Color.Transparent
            };

            var area = new ChartArea("main")
            {
                BackColor = BgDark, BackSecondaryColor = BgDark,
                BackGradientStyle = GradientStyle.None,
                BorderColor = Border, BorderWidth = 1,
            };

            // X축
            area.AxisX.LabelStyle.ForeColor = TextMu;
            area.AxisX.LabelStyle.Font = new Font("맑은 고딕", 7.5f);
            area.AxisX.LineColor = Border;
            area.AxisX.MajorGrid.LineColor = GridLine;
            area.AxisX.MajorGrid.LineDashStyle = ChartDashStyle.Dot;
            area.AxisX.MajorTickMark.LineColor = Border;
            area.AxisX.LabelStyle.Format = "yy/MM/dd";

            // Y축
            area.AxisY.LabelStyle.ForeColor = TextMu;
            area.AxisY.LabelStyle.Font = new Font("맑은 고딕", 7.5f);
            area.AxisY.LineColor = Border;
            area.AxisY.MajorGrid.LineColor = GridLine;
            area.AxisY.MajorGrid.LineDashStyle = ChartDashStyle.Dot;
            area.AxisY.MajorTickMark.LineColor = Border;
            area.AxisY.LabelStyle.Format = "0.0";
            area.AxisY.Title = "  수익률 지수 (기준=100)  ";
            area.AxisY.TitleForeColor = TextMu;
            area.AxisY.TitleFont = new Font("맑은 고딕", 8f);

            area.InnerPlotPosition = new ElementPosition(7, 3, 86, 90);
            _chart.ChartAreas.Add(area);

            // Legend
            var legend = new Legend("main")
            {
                BackColor = Color.FromArgb(230, 23, 31, 46),
                ForeColor = TextLt,
                Font = new Font("맑은 고딕", 9f, FontStyle.Bold),
                Docking = Docking.Bottom,
                LegendStyle = LegendStyle.Row,
                MaximumAutoSize = 14f,
                BorderColor = Border, BorderWidth = 1,
            };
            _chart.Legends.Add(legend);

            Controls.Add(_chart);
        }

        // ── 하단 상태바 ───────────────────────────────────────
        private void BuildStatusBar()
        {
            _statusLabel = new Label
            {
                Dock = DockStyle.Bottom, Height = 26,
                BackColor = BgPanel, ForeColor = TextMu,
                Font = new Font("맑은 고딕", 8.5f),
                TextAlign = ContentAlignment.MiddleLeft,
                Padding = new Padding(14, 0, 0, 0),
                Text = ""
            };
            Controls.Add(_statusLabel);
        }

        // ════════════════════════════════════════════════════
        //  데이터 로드 & 갱신
        // ════════════════════════════════════════════════════
        private async Task RefreshAsync(int months)
        {
            if (months == 0)
            {
                _fromDate = _allAccountData.Count > 0
                    ? ParseDate(_allAccountData[0].날짜) ?? DateTime.Today.AddYears(-3)
                    : DateTime.Today.AddYears(-3);
            }
            else
            {
                _fromDate = DateTime.Today.AddMonths(-months);
            }
            _toDate = DateTime.Today;
            await LoadAndDraw();
        }

        private async Task LoadAndDraw()
        {
            SetLoading(true);

            // 계좌 데이터 필터링
            _accountData = _allAccountData
                .Where(r =>
                {
                    var dt = ParseDate(r.날짜);
                    return dt.HasValue && dt.Value >= _fromDate && dt.Value <= _toDate;
                })
                .OrderBy(r => r.날짜)
                .ToList();

            // 지수 데이터 병렬 로드
            var tasks = Indices
                .Where(idx => idx.symbol != null)
                .Select(async idx =>
                {
                    var data = await FetchIndexAsync(idx.symbol, _fromDate, _toDate);
                    return (idx.name, data);
                });
            var results = await Task.WhenAll(tasks);
            foreach (var (name, data) in results)
                _indexData[name] = data;

            RedrawChart();
            SetLoading(false);
        }

        private void SetLoading(bool loading)
        {
            if (InvokeRequired) { Invoke((Action<bool>)SetLoading, loading); return; }
            _loadingLabel.Text = loading
                ? "  지수 데이터 로딩 중... (Yahoo Finance)"
                : "  ✓ 로딩 완료";
            _loadingLabel.ForeColor = loading
                ? Color.FromArgb(90, 160, 245)
                : Color.FromArgb(0, 195, 110);
        }

        // ── Yahoo Finance 지수 로드 ────────────────────────────
        private static async Task<List<(DateTime date, double close)>> FetchIndexAsync(
            string symbol, DateTime from, DateTime to)
        {
            var list = new List<(DateTime, double)>();
            try
            {
                long p1 = new DateTimeOffset(from.Date).ToUnixTimeSeconds();
                long p2 = new DateTimeOffset(to.Date.AddDays(1)).ToUnixTimeSeconds();
                string url = "https://query1.finance.yahoo.com/v8/finance/chart/"
                           + Uri.EscapeDataString(symbol)
                           + $"?interval=1d&period1={p1}&period2={p2}";

                string json = await _http.GetStringAsync(url);

                // timestamp 배열 파싱
                var tsMatch = Regex.Match(json, @"""timestamp""\s*:\s*\[([^\]]+)\]");
                if (!tsMatch.Success) return list;
                var tsList = tsMatch.Groups[1].Value.Split(',')
                    .Select(s => { long.TryParse(s.Trim(), out long v); return v; })
                    .ToList();

                // close 배열 파싱 (quote 블록 내)
                var quoteMatch = Regex.Match(json, @"""quote""\s*:\s*\[\{([\s\S]*?)\}\]");
                if (!quoteMatch.Success) return list;
                var closeMatch = Regex.Match(quoteMatch.Groups[1].Value, @"""close""\s*:\s*\[([^\]]+)\]");
                if (!closeMatch.Success) return list;
                var closes = closeMatch.Groups[1].Value.Split(',')
                    .Select(s =>
                    {
                        s = s.Trim();
                        if (s == "null") return double.NaN;
                        double.TryParse(s, System.Globalization.NumberStyles.Any,
                            System.Globalization.CultureInfo.InvariantCulture, out double v);
                        return v;
                    }).ToList();

                int cnt = Math.Min(tsList.Count, closes.Count);
                for (int i = 0; i < cnt; i++)
                {
                    if (tsList[i] == 0 || double.IsNaN(closes[i])) continue;
                    var dt = DateTimeOffset.FromUnixTimeSeconds(tsList[i]).LocalDateTime.Date;
                    list.Add((dt, closes[i]));
                }
            }
            catch { /* 네트워크 오류 시 빈 리스트 반환 */ }
            return list;
        }

        // ════════════════════════════════════════════════════
        //  차트 렌더링
        // ════════════════════════════════════════════════════
        private void RedrawChart()
        {
            if (InvokeRequired) { Invoke((Action)RedrawChart); return; }

            _chart.Series.Clear();

            var returnSummary = new System.Text.StringBuilder("  ");
            bool firstSeries = true;

            // ── 내 계좌 ──────────────────────────────────────
            if (_visible["내 계좌"])
            {
                if (_accountData.Count >= 2)
                {
                    double baseAsset = _accountData[0].추정예탁자산;
                    if (baseAsset > 0)
                    {
                        var s = AddSeries("내 계좌", Indices[0].color, 3);
                        foreach (var r in _accountData)
                            s.Points.AddXY(ParseDate(r.날짜) ?? DateTime.Today,
                                           r.추정예탁자산 / baseAsset * 100.0);

                        double ret = (_accountData.Last().추정예탁자산 / baseAsset - 1.0) * 100.0;
                        string retStr = $"{S(ret)}{ret:F2}%";
                        s.LegendText = $"내 계좌  {retStr}";
                        var lastPt0 = s.Points[s.Points.Count - 1];
                        lastPt0.Label = retStr;
                        lastPt0.LabelForeColor = Indices[0].color;
                        lastPt0.LabelBackColor = Color.FromArgb(180, 16, 22, 34);
                        lastPt0.Font = new Font("맑은 고딕", 8f, FontStyle.Bold);
                        Append(returnSummary, $"내 계좌 {retStr}", Indices[0].color, ref firstSeries);
                    }
                }
                else
                {
                    Append(returnSummary, "내 계좌: 데이터 없음 (장 마감 후 자동 기록됨)", TextMu, ref firstSeries);
                }
            }

            // ── 지수 ─────────────────────────────────────────
            foreach (var idx in Indices.Skip(1))
            {
                if (!_visible[idx.name]) continue;
                if (!_indexData.TryGetValue(idx.name, out var data) || data.Count < 2)
                {
                    Append(returnSummary, $"{idx.name}: 로드 실패", TextMu, ref firstSeries);
                    continue;
                }

                // 계좌 시작일에 맞춰 기준 정렬
                DateTime effectiveFrom = _accountData.Count > 0
                    ? (ParseDate(_accountData[0].날짜) ?? _fromDate)
                    : _fromDate;
                var aligned = data.Where(d => d.date >= effectiveFrom).ToList();
                if (aligned.Count < 2) aligned = data;

                double baseClose = aligned[0].close;
                if (baseClose <= 0) continue;

                var s = AddSeries(idx.name, idx.color, idx.lw);
                foreach (var (dt, close) in aligned)
                    s.Points.AddXY(dt, close / baseClose * 100.0);

                double ret = (aligned.Last().close / baseClose - 1.0) * 100.0;
                string retStr = $"{S(ret)}{ret:F2}%";
                s.LegendText = $"{idx.name}  {retStr}";
                var lastPt = s.Points[s.Points.Count - 1];
                lastPt.Label = retStr;
                lastPt.LabelForeColor = idx.color;
                lastPt.LabelBackColor = Color.FromArgb(180, 16, 22, 34);
                lastPt.Font = new Font("맑은 고딕", 8f, FontStyle.Bold);
                Append(returnSummary, $"{idx.name} {retStr}", idx.color, ref firstSeries);
            }

            // ── 기준선 100 ────────────────────────────────────
            AddBaseline100();

            // ── X축 포맷 자동 조정 ────────────────────────────
            int days = (int)(_toDate - _fromDate).TotalDays;
            var area = _chart.ChartAreas["main"];
            area.AxisX.LabelStyle.Format = days <= 35 ? "MM/dd" : (days <= 180 ? "yy/MM/dd" : "yy/MM");
            area.AxisX.Interval     = days <= 35 ? 5 : (days <= 90 ? 14 : (days <= 180 ? 21 : 30));
            area.AxisX.IntervalType = DateTimeIntervalType.Days;

            _statusLabel.Text = returnSummary.ToString();
        }

        private void AddBaseline100()
        {
            double minX = double.MaxValue, maxX = double.MinValue;
            foreach (Series s in _chart.Series)
            {
                if (s.Points.Count == 0) continue;
                minX = Math.Min(minX, s.Points[0].XValue);
                maxX = Math.Max(maxX, s.Points[s.Points.Count - 1].XValue);
            }
            if (minX == double.MaxValue) return;

            var baseLine = new Series("기준(100)")
            {
                ChartType = SeriesChartType.Line,
                Color = Color.FromArgb(75, 95, 120),
                BorderWidth = 1,
                BorderDashStyle = ChartDashStyle.Dash,
                IsVisibleInLegend = false,
                XValueType = ChartValueType.DateTime,
                ChartArea = "main"
            };
            baseLine.Points.AddXY(DateTime.FromOADate(minX), 100.0);
            baseLine.Points.AddXY(DateTime.FromOADate(maxX), 100.0);
            _chart.Series.Add(baseLine);
        }

        private Series AddSeries(string name, Color color, int width)
        {
            var s = new Series(name)
            {
                ChartType = SeriesChartType.Line,
                Color = color, BorderWidth = width,
                XValueType = ChartValueType.DateTime,
                IsVisibleInLegend = true,
                LegendText = name,
                ChartArea = "main", Legend = "main",
                MarkerStyle = MarkerStyle.None,
            };
            _chart.Series.Add(s);
            return s;
        }

        // ════════════════════════════════════════════════════
        //  헬퍼
        // ════════════════════════════════════════════════════
        private static DateTime? ParseDate(string s)
        {
            if (DateTime.TryParseExact(s, "yyyyMMdd",
                System.Globalization.CultureInfo.InvariantCulture,
                System.Globalization.DateTimeStyles.None, out DateTime dt))
                return dt;
            return null;
        }

        private static string S(double v) => v >= 0 ? "+" : "";

        private static void Append(System.Text.StringBuilder sb, string text, Color color, ref bool first)
        {
            if (!first) sb.Append("   |   ");
            sb.Append(text);
            first = false;
        }
    }
}
