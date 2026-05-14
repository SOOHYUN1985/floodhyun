using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.Windows.Forms;

namespace AutoTradingTest
{
    /// <summary>
    /// 거래 이력 조회 창
    /// </summary>
    public class TradeHistoryForm : Form
    {
        // ── 데이터 ──────────────────────────────────────────
        private readonly List<DBInfo> _history;

        // ── 필터 컨트롤 ─────────────────────────────────────
        private ComboBox _periodCombo;
        private DateTimePicker _dtFrom;
        private DateTimePicker _dtTo;
        private TextBox _searchBox;
        private ComboBox _strategyCombo;
        private ComboBox _resultCombo;

        // ── 요약 카드 ────────────────────────────────────────
        private Label _cardTotal, _cardWinRate, _cardProfit, _cardAvgHold, _cardAvgRate;

        // ── 그리드 ───────────────────────────────────────────
        private DataGridView _grid;

        // ── 하단 상태 ────────────────────────────────────────
        private Label _statusLabel;

        // ── 색상 팔레트 ──────────────────────────────────────
        private static readonly Color BgDark      = Color.FromArgb(28, 36, 50);
        private static readonly Color BgPanel     = Color.FromArgb(38, 48, 65);
        private static readonly Color BgCard      = Color.FromArgb(48, 60, 80);
        private static readonly Color BgBody      = Color.FromArgb(245, 248, 252);
        private static readonly Color AccentBlue  = Color.FromArgb(50, 130, 240);
        private static readonly Color AccentGreen = Color.FromArgb(0, 185, 110);
        private static readonly Color AccentRed   = Color.FromArgb(220, 60, 60);
        private static readonly Color TextLight   = Color.FromArgb(230, 235, 245);
        private static readonly Color TextMuted   = Color.FromArgb(150, 165, 190);
        private static readonly Color GridHeader  = Color.FromArgb(45, 55, 72);
        private static readonly Color GridAlt     = Color.FromArgb(248, 251, 255);
        private static readonly Color BorderColor = Color.FromArgb(200, 210, 225);
        private static readonly Color ProfitColor = Color.FromArgb(210, 40, 40);
        private static readonly Color LossColor   = Color.FromArgb(50, 80, 210);

        public TradeHistoryForm(List<DBInfo> history)
        {
            _history = history ?? new List<DBInfo>();
            BuildUI();
            ApplyFilter();
        }

        // ════════════════════════════════════════════════════
        //  UI 구성
        // ════════════════════════════════════════════════════
        private void BuildUI()
        {
            this.Text = "거래 이력";
            this.Size = new Size(1300, 820);
            this.MinimumSize = new Size(900, 600);
            this.StartPosition = FormStartPosition.CenterParent;
            this.BackColor = BgBody;
            this.Font = new Font("맑은 고딕", 9f);
            this.DoubleBuffered = true;

            // ── 상단 헤더 패널 (요약 카드) ──────────────────
            var header = new Panel
            {
                Dock = DockStyle.Top,
                Height = 110,
                BackColor = BgDark,
                Padding = new Padding(16, 10, 16, 10)
            };

            var titleLabel = new Label
            {
                Text = "거래 이력",
                Font = new Font("맑은 고딕", 14f, FontStyle.Bold),
                ForeColor = TextLight,
                AutoSize = true,
                Location = new Point(16, 12)
            };
            header.Controls.Add(titleLabel);

            // 요약 카드 5개
            var cardDefs = new[] {
                ("총 거래",   "0 건"),
                ("승  률",    "0.0 %"),
                ("총수익금",  "+0 원"),
                ("평균보유일","0 일"),
                ("평균수익률","0.00 %"),
            };

            int cx = 200;
            foreach (var (title, init) in cardDefs)
            {
                var card = CreateSummaryCard(title, init, new Point(cx, 10));
                header.Controls.Add(card);
                cx += 200;
            }

            _cardTotal    = FindCardValue(header, "총 거래");
            _cardWinRate  = FindCardValue(header, "승  률");
            _cardProfit   = FindCardValue(header, "총수익금");
            _cardAvgHold  = FindCardValue(header, "평균보유일");
            _cardAvgRate  = FindCardValue(header, "평균수익률");

            this.Controls.Add(header);

            // ── 필터 바 ──────────────────────────────────────
            var filterPanel = new Panel
            {
                Dock = DockStyle.Top,
                Height = 48,
                BackColor = BgPanel,
                Padding = new Padding(12, 0, 12, 0)
            };

            int fx = 12;

            // 기간 콤보
            filterPanel.Controls.Add(MakeFilterLabel("기간", ref fx));
            _periodCombo = new ComboBox
            {
                DropDownStyle = ComboBoxStyle.DropDownList,
                Width = 90, Height = 26,
                Location = new Point(fx, 11),
                BackColor = Color.White, FlatStyle = FlatStyle.Flat
            };
            _periodCombo.Items.AddRange(new object[] { "전체", "오늘", "이번 주", "이번 달", "최근 3개월", "직접 입력" });
            _periodCombo.SelectedIndex = 0;
            _periodCombo.SelectedIndexChanged += (s, e) =>
            {
                bool custom = _periodCombo.SelectedItem?.ToString() == "직접 입력";
                _dtFrom.Enabled = _dtTo.Enabled = custom;
                ApplyFilter();
            };
            filterPanel.Controls.Add(_periodCombo);
            fx += _periodCombo.Width + 6;

            _dtFrom = new DateTimePicker { Width = 105, Location = new Point(fx, 11), Enabled = false, Format = DateTimePickerFormat.Short };
            _dtFrom.Value = DateTime.Today.AddMonths(-3);
            _dtFrom.ValueChanged += (s, e) => ApplyFilter();
            filterPanel.Controls.Add(_dtFrom);
            fx += _dtFrom.Width + 4;

            var dashLbl = new Label { Text = "~", ForeColor = TextLight, AutoSize = true, Location = new Point(fx, 14) };
            filterPanel.Controls.Add(dashLbl);
            fx += 14;

            _dtTo = new DateTimePicker { Width = 105, Location = new Point(fx, 11), Enabled = false, Format = DateTimePickerFormat.Short };
            _dtTo.Value = DateTime.Today;
            _dtTo.ValueChanged += (s, e) => ApplyFilter();
            filterPanel.Controls.Add(_dtTo);
            fx += _dtTo.Width + 14;

            // 종목명 검색
            filterPanel.Controls.Add(MakeFilterLabel("종목명", ref fx));
            _searchBox = new TextBox { Width = 110, Location = new Point(fx, 11), BackColor = Color.White };
            _searchBox.TextChanged += (s, e) => ApplyFilter();
            filterPanel.Controls.Add(_searchBox);
            fx += _searchBox.Width + 14;

            // 매수전략
            filterPanel.Controls.Add(MakeFilterLabel("전략", ref fx));
            _strategyCombo = new ComboBox
            {
                DropDownStyle = ComboBoxStyle.DropDownList,
                Width = 130, Location = new Point(fx, 11),
                BackColor = Color.White, FlatStyle = FlatStyle.Flat
            };
            _strategyCombo.Items.Add("전체");
            foreach (var s in _history.Select(h => h.매수전략 ?? "").Distinct().OrderBy(x => x))
                if (!string.IsNullOrEmpty(s)) _strategyCombo.Items.Add(s);
            _strategyCombo.SelectedIndex = 0;
            _strategyCombo.SelectedIndexChanged += (s, e) => ApplyFilter();
            filterPanel.Controls.Add(_strategyCombo);
            fx += _strategyCombo.Width + 14;

            // 결과 필터
            filterPanel.Controls.Add(MakeFilterLabel("결과", ref fx));
            _resultCombo = new ComboBox
            {
                DropDownStyle = ComboBoxStyle.DropDownList,
                Width = 80, Location = new Point(fx, 11),
                BackColor = Color.White, FlatStyle = FlatStyle.Flat
            };
            _resultCombo.Items.AddRange(new object[] { "전체", "수익", "손실" });
            _resultCombo.SelectedIndex = 0;
            _resultCombo.SelectedIndexChanged += (s, e) => ApplyFilter();
            filterPanel.Controls.Add(_resultCombo);
            fx += _resultCombo.Width + 14;

            // 초기화 버튼
            var resetBtn = new Button
            {
                Text = "초기화", Width = 60, Height = 26, Location = new Point(fx, 11),
                FlatStyle = FlatStyle.Flat,
                BackColor = Color.FromArgb(80, 100, 130), ForeColor = Color.White,
                Cursor = Cursors.Hand
            };
            resetBtn.FlatAppearance.BorderColor = Color.FromArgb(60, 80, 110);
            resetBtn.Click += (s, e) => ResetFilters();
            filterPanel.Controls.Add(resetBtn);

            // Excel 내보내기 버튼 (우측 정렬)
            var exportBtn = new Button
            {
                Text = "CSV 저장", Width = 80, Height = 26,
                Anchor = AnchorStyles.Top | AnchorStyles.Right,
                FlatStyle = FlatStyle.Flat,
                BackColor = Color.FromArgb(0, 130, 80), ForeColor = Color.White,
                Cursor = Cursors.Hand
            };
            exportBtn.FlatAppearance.BorderColor = Color.FromArgb(0, 100, 60);
            exportBtn.Click += ExportCsv;
            filterPanel.Controls.Add(exportBtn);
            filterPanel.Resize += (s, e) => exportBtn.Location = new Point(filterPanel.Width - exportBtn.Width - 12, 11);

            this.Controls.Add(filterPanel);

            // ── 메인 그리드 ──────────────────────────────────
            var gridPanel = new Panel { Dock = DockStyle.Fill, Padding = new Padding(12, 8, 12, 8) };

            _grid = new DataGridView
            {
                Dock = DockStyle.Fill,
                ReadOnly = true,
                AllowUserToAddRows = false,
                AllowUserToDeleteRows = false,
                SelectionMode = DataGridViewSelectionMode.FullRowSelect,
                MultiSelect = false,
                AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.None,
                ColumnHeadersHeightSizeMode = DataGridViewColumnHeadersHeightSizeMode.DisableResizing,
                BorderStyle = BorderStyle.None,
                CellBorderStyle = DataGridViewCellBorderStyle.SingleHorizontal,
                GridColor = Color.FromArgb(220, 228, 240),
                BackgroundColor = Color.White,
                RowHeadersVisible = false,
                EnableHeadersVisualStyles = false,
                AutoSizeRowsMode = DataGridViewAutoSizeRowsMode.None,
            };
            _grid.RowTemplate.Height = 26;
            _grid.DefaultCellStyle.WrapMode = DataGridViewTriState.False;

            // 헤더 스타일
            _grid.ColumnHeadersDefaultCellStyle.BackColor = GridHeader;
            _grid.ColumnHeadersDefaultCellStyle.ForeColor = Color.White;
            _grid.ColumnHeadersDefaultCellStyle.Font = new Font("맑은 고딕", 9f, FontStyle.Bold);
            _grid.ColumnHeadersDefaultCellStyle.Alignment = DataGridViewContentAlignment.MiddleCenter;
            _grid.ColumnHeadersDefaultCellStyle.SelectionBackColor = GridHeader;
            _grid.ColumnHeadersHeight = 32;

            // 셀 스타일
            _grid.DefaultCellStyle.BackColor = Color.White;
            _grid.DefaultCellStyle.ForeColor = Color.FromArgb(40, 50, 70);
            _grid.DefaultCellStyle.Font = new Font("맑은 고딕", 9f);
            _grid.DefaultCellStyle.SelectionBackColor = Color.FromArgb(210, 228, 252);
            _grid.DefaultCellStyle.SelectionForeColor = Color.FromArgb(20, 40, 80);
            _grid.DefaultCellStyle.Padding = new Padding(3, 0, 3, 0);
            _grid.AlternatingRowsDefaultCellStyle.BackColor = GridAlt;

            // 컬럼 정의
            AddColumn("매수일",   "매수일",     90,  DataGridViewContentAlignment.MiddleCenter);
            AddColumn("전량매도일", "매도일",   90,  DataGridViewContentAlignment.MiddleCenter);
            AddColumn("종목명",   "종목명",    110,  DataGridViewContentAlignment.MiddleLeft);
            AddColumn("종목코드", "코드",       68,  DataGridViewContentAlignment.MiddleCenter);
            AddColumn("매수전략", "전략(조건)", 130, DataGridViewContentAlignment.MiddleLeft);
            AddColumn("매수가격", "매수가",     88,  DataGridViewContentAlignment.MiddleRight);
            AddColumn("매도가격", "매도가",     88,  DataGridViewContentAlignment.MiddleRight);
            AddColumn("매수수량", "매수수량",   68,  DataGridViewContentAlignment.MiddleRight);
            AddColumn("매수금액", "매수금액",   98,  DataGridViewContentAlignment.MiddleRight);
            AddColumn("매도금액", "매도금액",   98,  DataGridViewContentAlignment.MiddleRight);
            AddColumn("보유일",   "보유일",     55,  DataGridViewContentAlignment.MiddleCenter);
            AddColumn("최종수익률", "수익률(%)", 75, DataGridViewContentAlignment.MiddleRight);
            AddColumn("최종수익금", "수익금",   90,  DataGridViewContentAlignment.MiddleRight);
            AddColumn("매도이유", "매도이유",   110, DataGridViewContentAlignment.MiddleLeft);
            AddColumn("nR익절",   "nR익절",     55,  DataGridViewContentAlignment.MiddleCenter);
            AddColumn("이평매도", "이평매도",   65,  DataGridViewContentAlignment.MiddleCenter);

            _grid.CellFormatting += Grid_CellFormatting;
            gridPanel.Controls.Add(_grid);
            this.Controls.Add(gridPanel);

            // ── 하단 상태 바 ─────────────────────────────────
            _statusLabel = new Label
            {
                Dock = DockStyle.Bottom,
                Height = 28,
                BackColor = BgDark,
                ForeColor = TextMuted,
                Font = new Font("맑은 고딕", 8.5f),
                TextAlign = ContentAlignment.MiddleLeft,
                Padding = new Padding(14, 0, 0, 0)
            };
            this.Controls.Add(_statusLabel);

            // Controls 추가 순서상 상단부터: header → filterPanel → gridPanel → statusLabel
            // DockStyle 처리를 위해 순서 조정
            this.Controls.SetChildIndex(_statusLabel, 0);
            this.Controls.SetChildIndex(gridPanel, 1);
            this.Controls.SetChildIndex(filterPanel, 2);
            this.Controls.SetChildIndex(header, 3);
        }

        // ════════════════════════════════════════════════════
        //  필터 적용
        // ════════════════════════════════════════════════════
        private void ApplyFilter()
        {
            var filtered = _history.Where(h => !string.IsNullOrEmpty(h.전량매도일)).ToList();

            // 기간 필터
            string period = _periodCombo?.SelectedItem?.ToString() ?? "전체";
            DateTime today = DateTime.Today;
            DateTime from = DateTime.MinValue, to = DateTime.MaxValue;

            switch (period)
            {
                case "오늘":
                    from = today; to = today; break;
                case "이번 주":
                    from = today.AddDays(-(int)today.DayOfWeek + 1); to = today; break;
                case "이번 달":
                    from = new DateTime(today.Year, today.Month, 1); to = today; break;
                case "최근 3개월":
                    from = today.AddMonths(-3); to = today; break;
                case "직접 입력":
                    if (_dtFrom != null) from = _dtFrom.Value.Date;
                    if (_dtTo   != null) to   = _dtTo.Value.Date;
                    break;
            }

            if (from != DateTime.MinValue || to != DateTime.MaxValue)
            {
                filtered = filtered.Where(h =>
                {
                    if (DateTime.TryParseExact(h.전량매도일, "yyyyMMdd",
                        System.Globalization.CultureInfo.InvariantCulture,
                        System.Globalization.DateTimeStyles.None, out DateTime dt))
                        return dt.Date >= from && dt.Date <= to;
                    return true;
                }).ToList();
            }

            // 종목명 검색
            string keyword = _searchBox?.Text?.Trim() ?? "";
            if (!string.IsNullOrEmpty(keyword))
                filtered = filtered.Where(h =>
                    (h.종목명 ?? "").IndexOf(keyword, StringComparison.OrdinalIgnoreCase) >= 0 ||
                    (h.종목코드 ?? "").IndexOf(keyword, StringComparison.OrdinalIgnoreCase) >= 0
                ).ToList();

            // 전략 필터
            string strategy = _strategyCombo?.SelectedItem?.ToString() ?? "전체";
            if (strategy != "전체")
                filtered = filtered.Where(h => h.매수전략 == strategy).ToList();

            // 수익/손실 필터
            string result = _resultCombo?.SelectedItem?.ToString() ?? "전체";
            if (result == "수익") filtered = filtered.Where(h => h.최종수익금 > 0).ToList();
            else if (result == "손실") filtered = filtered.Where(h => h.최종수익금 <= 0).ToList();

            // 날짜 내림차순 정렬 (최신 먼저)
            filtered = filtered.OrderByDescending(h => h.전량매도일).ThenByDescending(h => h.매수일).ToList();

            RefreshGrid(filtered);
            RefreshSummary(filtered);
        }

        // ════════════════════════════════════════════════════
        //  그리드 갱신
        // ════════════════════════════════════════════════════
        private void RefreshGrid(List<DBInfo> data)
        {
            _grid.Rows.Clear();
            foreach (var h in data)
            {
                string buyDate  = FormatDate(h.매수일);
                string sellDate = FormatDate(h.전량매도일);
                string nrMark   = h.nR절반매도 ? "O" : "-";
                string emaMark  = !string.IsNullOrEmpty(h.이평매도일자) ? "O" : "-";
                long 매수금액 = (long)h.매수가격 * h.매수수량;
                long 매도금액 = (long)h.매도가격 * h.매수수량;

                int rowIdx = _grid.Rows.Add(
                    buyDate,
                    sellDate,
                    h.종목명,
                    h.종목코드,
                    h.매수전략,
                    h.매수가격 > 0 ? $"{h.매수가격:N0}" : "-",
                    h.매도가격 > 0 ? $"{h.매도가격:N0}" : "-",
                    h.매수수량 > 0 ? $"{h.매수수량:N0}" : "-",
                    매수금액 > 0 ? $"{매수금액:N0}" : "-",
                    매도금액 > 0 ? $"{매도금액:N0}" : "-",
                    h.보유일,
                    $"{h.최종수익률:F2}",
                    $"{h.최종수익금:N0}",
                    h.전량매도이유 ?? "",
                    nrMark,
                    emaMark
                );
                // 수익/손실에 따른 행 태그
                _grid.Rows[rowIdx].Tag = h.최종수익금;
            }
        }

        // ════════════════════════════════════════════════════
        //  요약 카드 갱신
        // ════════════════════════════════════════════════════
        private void RefreshSummary(List<DBInfo> data)
        {
            int total  = data.Count;
            int wins   = data.Count(h => h.최종수익금 > 0);
            long totalProfit = data.Sum(h => (long)h.최종수익금);
            double avgHold = total > 0 ? data.Average(h => (double)h.보유일) : 0;
            double avgRate = total > 0 ? data.Average(h => (double)h.최종수익률) : 0;
            double winRate = total > 0 ? wins * 100.0 / total : 0;

            if (_cardTotal    != null) _cardTotal.Text    = $"{total:N0} 건";
            if (_cardWinRate  != null)
            {
                _cardWinRate.Text      = $"{winRate:F1} %";
                _cardWinRate.ForeColor = winRate >= 50 ? AccentGreen : AccentRed;
            }
            if (_cardProfit   != null)
            {
                _cardProfit.Text      = $"{(totalProfit >= 0 ? "+" : "")}{totalProfit:N0} 원";
                _cardProfit.ForeColor = totalProfit >= 0 ? AccentGreen : AccentRed;
            }
            if (_cardAvgHold  != null) _cardAvgHold.Text  = $"{avgHold:F1} 일";
            if (_cardAvgRate  != null)
            {
                _cardAvgRate.Text      = $"{(avgRate >= 0 ? "+" : "")}{avgRate:F2} %";
                _cardAvgRate.ForeColor = avgRate >= 0 ? AccentGreen : AccentRed;
            }

            int losses = total - wins;
            if (_statusLabel != null)
                _statusLabel.Text = $"  총 {total}건 표시 중  |  수익 {wins}건  |  손실 {losses}건  |  승률 {winRate:F1}%  |  총 수익금 {(totalProfit >= 0 ? "+" : "")}{totalProfit:N0}원  |  평균 보유일 {avgHold:F1}일";
        }

        // ════════════════════════════════════════════════════
        //  셀 포맷팅 (수익/손실 색상)
        // ════════════════════════════════════════════════════
        private void Grid_CellFormatting(object sender, DataGridViewCellFormattingEventArgs e)
        {
            if (e.RowIndex < 0 || e.RowIndex >= _grid.Rows.Count) return;
            var row = _grid.Rows[e.RowIndex];
            if (row.Tag is int profit)
            {
                string colName = _grid.Columns[e.ColumnIndex].Name;
                if (colName == "최종수익률" || colName == "최종수익금")
                {
                    e.CellStyle.ForeColor = profit > 0 ? ProfitColor : (profit < 0 ? LossColor : Color.Gray);
                    e.CellStyle.Font = new Font("맑은 고딕", 9f, FontStyle.Bold);
                }
            }
        }

        // ════════════════════════════════════════════════════
        //  CSV 저장
        // ════════════════════════════════════════════════════
        private void ExportCsv(object sender, EventArgs e)
        {
            using (var dlg = new SaveFileDialog
            {
                Filter = "CSV 파일 (*.csv)|*.csv",
                FileName = $"거래이력_{DateTime.Now:yyyyMMdd_HHmmss}.csv",
                Title = "CSV 저장"
            })
            {
                if (dlg.ShowDialog(this) != DialogResult.OK) return;
                try
                {
                    var lines = new List<string>();
                    // 헤더
                    var headers = _grid.Columns.Cast<DataGridViewColumn>().Select(c => $"\"{c.HeaderText}\"");
                    lines.Add(string.Join(",", headers));
                    // 데이터
                    foreach (DataGridViewRow row in _grid.Rows)
                    {
                        var cells = row.Cells.Cast<DataGridViewCell>().Select(c => $"\"{c.Value}\"");
                        lines.Add(string.Join(",", cells));
                    }
                    System.IO.File.WriteAllLines(dlg.FileName, lines, System.Text.Encoding.UTF8);
                    MessageBox.Show($"저장 완료: {dlg.FileName}", "CSV 저장", MessageBoxButtons.OK, MessageBoxIcon.Information);
                }
                catch (Exception ex)
                {
                    MessageBox.Show($"저장 실패: {ex.Message}", "오류", MessageBoxButtons.OK, MessageBoxIcon.Error);
                }
            }
        }

        // ════════════════════════════════════════════════════
        //  필터 초기화
        // ════════════════════════════════════════════════════
        private void ResetFilters()
        {
            _periodCombo.SelectedIndex = 0;
            _searchBox.Text = "";
            _strategyCombo.SelectedIndex = 0;
            _resultCombo.SelectedIndex = 0;
        }

        // ════════════════════════════════════════════════════
        //  헬퍼 메서드
        // ════════════════════════════════════════════════════
        private Panel CreateSummaryCard(string title, string value, Point location)
        {
            var card = new Panel
            {
                Location = location,
                Size = new Size(180, 85),
                BackColor = BgCard,
                Tag = title
            };
            card.Paint += (s, e) =>
            {
                using (var pen = new Pen(Color.FromArgb(70, 90, 115), 1f))
                    e.Graphics.DrawRectangle(pen, 0, 0, card.Width - 1, card.Height - 1);
            };

            var titleLbl = new Label
            {
                Text = title,
                Font = new Font("맑은 고딕", 8.5f),
                ForeColor = TextMuted,
                TextAlign = ContentAlignment.MiddleCenter,
                Dock = DockStyle.Top,
                Height = 28
            };
            var valueLbl = new Label
            {
                Text = value,
                Font = new Font("맑은 고딕", 15f, FontStyle.Bold),
                ForeColor = TextLight,
                TextAlign = ContentAlignment.MiddleCenter,
                Dock = DockStyle.Fill,
                Tag = "value"
            };
            card.Controls.Add(valueLbl);
            card.Controls.Add(titleLbl);
            return card;
        }

        private Label FindCardValue(Control parent, string cardTitle)
        {
            foreach (Control ctrl in parent.Controls)
            {
                if (ctrl is Panel cp && cp.Tag?.ToString() == cardTitle)
                    foreach (Control c in cp.Controls)
                        if (c is Label lbl && lbl.Tag?.ToString() == "value")
                            return lbl;
            }
            return null;
        }

        private Label MakeFilterLabel(string text, ref int x)
        {
            var lbl = new Label
            {
                Text = text,
                ForeColor = TextLight,
                AutoSize = true,
                Location = new Point(x, 15)
            };
            x += lbl.PreferredWidth + 4;
            return lbl;
        }

        private void AddColumn(string name, string header, int width, DataGridViewContentAlignment align)
        {
            var col = new DataGridViewTextBoxColumn
            {
                Name = name,
                HeaderText = header,
                Width = width,
                AutoSizeMode = DataGridViewAutoSizeColumnMode.None,
                SortMode = DataGridViewColumnSortMode.Automatic
            };
            col.DefaultCellStyle.Alignment = align;
            col.HeaderCell.Style.Alignment = DataGridViewContentAlignment.MiddleCenter;
            _grid.Columns.Add(col);
        }

        private static string FormatDate(string raw)
        {
            if (string.IsNullOrEmpty(raw) || raw.Length < 8) return raw ?? "";
            if (DateTime.TryParseExact(raw, "yyyyMMdd",
                System.Globalization.CultureInfo.InvariantCulture,
                System.Globalization.DateTimeStyles.None, out DateTime dt))
                return dt.ToString("yy/MM/dd");
            return raw;
        }
    }
}
