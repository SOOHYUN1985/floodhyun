// AutoTradingTest - Form1.cs
// 메인 윈도우 폼, 자동매매 UI 및 이벤트 처리

using AxKHOpenAPILib;
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;
using System.Windows.Forms.DataVisualization.Charting;
using System.Threading; // CancellationTokenSource
using System.Text.RegularExpressions;
using System.Collections.Concurrent; // ConcurrentQueue

/*
// TODO
- 전략에 사용 할 종목별 이평 정보 / 최고가 등
 = 보유종목, 조건 편입종목

// Apply
- 매수,매도 호가 -> 현재가 기준 +- 3퍼 해서 1천원 단위로.. IntRound
*/

namespace AutoTradingTest
{
    /// <summary>
    /// 자동매매 테스트 메인 폼
    /// - 실시간 데이터 수신, 주문, DB 연동, 전략 관리 등 UI 및 이벤트 처리 담당
    /// </summary>
    public partial class Form1 : Form
    {
        /// <summary>
        /// 실시간 조건식 관련 Thread
        /// </summary>
        private CancellationTokenSource m_ConditionCts = null;
        private object m_ConditionLock = new object();

        /// <summary>
        /// 실시간 종목 모니터링 관련 Thread
        /// </summary>
        private CancellationTokenSource m_MonitoringCts = null;
        private object m_MonitoringLock = new object();

        /// <summary>
        /// 매도 모니터 Task (장중 주기적 매도 조건 체크)
        /// </summary>
        private CancellationTokenSource m_SellMonitorCts = null;
        private bool m_SellMonitorRunning = false;

        private int _scrNum = 5050;

        // 매니저 클래스 분리
        private Core.DbManager _dbManager;
        private Core.ConditionManager _conditionManager;
        private Core.StrategyManager _strategyManager;
        private Core.OrderManager _orderManager;
        private Core.SellStrategyManager _sellStrategyManager;
        private Core.StrategyConfig _strategyConfig;

        // 보유종목 그리드 BindingSource (DataSource null/재할당 시 CurrencyManager -1 오류 방지)
        private BindingSource _holdGridBindingSource = new BindingSource();

        // 보유종목 실시간 시세 <종목코드, RealTimePrice> — ConcurrentDictionary for thread-safety
        private ConcurrentDictionary<string, Core.RealTimePrice> m_RealTimePrices = new ConcurrentDictionary<string, Core.RealTimePrice>();

        // 보유종목 50일 최대거래량 캐시 <종목코드, 최대거래량> (ConcurrentDictionary for thread-safety)
        private ConcurrentDictionary<string, long> m_Max50DayVolume = new ConcurrentDictionary<string, long>();

        // 보유종목 EMA 캐시 <종목코드, Dictionary<EMA기간, EMA값>> (일봉 조회 시 계산)
        private ConcurrentDictionary<string, Dictionary<int, int>> m_HoldingEMA = new ConcurrentDictionary<string, Dictionary<int, int>>();

        // 보유종목 일봉 데이터 요청 큐 (로그인 후 순차 조회)
        private ConcurrentQueue<string> m_holdingDailyQueue = new ConcurrentQueue<string>();

        // 비상 정지 버튼
        private Button _emergencyStopButton;

        // 패널간 크기 조절용 SplitContainer
        private SplitContainer _splitMain; // 상단(조건식+보유종목) vs 하단(차트+로그)
        private SplitContainer _splitTop;  // 조건식 vs 보유종목
        private bool _splitInitialized = false;

        // 차트
        List<PriceInfoEntityObject> m_PriceInfoList;
        private Series m_PriceSeries;
        private Series m_VolumeSeries;

        // 실시간 모니터링 종목 List <종목코드, 종목명>
        Dictionary<string, string> m_monitoring = new Dictionary<string, string>();
        ConcurrentQueue<string> m_monitoringQueue = new ConcurrentQueue<string>();

        // Orders mapping: 주문번호 -> 조건명 (ConcurrentDictionary for thread-safety)
        private ConcurrentDictionary<string, string> m_dicBuyOrder = new ConcurrentDictionary<string, string>();
        private ConcurrentDictionary<string, string> m_dicSellOrder = new ConcurrentDictionary<string, string>();

        // 매수/매도 중복 주문 방지: 종목코드 -> 조건명 (진행 중 추적)
        private ConcurrentDictionary<string, string> m_PendingBuyOrders = new ConcurrentDictionary<string, string>();
        private ConcurrentDictionary<string, string> m_PendingSellOrders = new ConcurrentDictionary<string, string>();

        // 미체결 매수 주문 자동취소용: 종목코드 -> 주문시각
        private ConcurrentDictionary<string, DateTime> m_BuyOrderTime = new ConcurrentDictionary<string, DateTime>();
        private const int BUY_TIMEOUT_SEC = 300; // 미체결 매수 안전장치 (5분) — 주로 잔고부족 시 자동취소로 처리

        // 매수 주문 화면번호/주문번호/주문금액 추적 (취소·잔고복원 시 사용)
        private ConcurrentDictionary<string, string> m_BuyOrderScreen  = new ConcurrentDictionary<string, string>();
        private ConcurrentDictionary<string, string> m_BuyOrderNo      = new ConcurrentDictionary<string, string>();
        private ConcurrentDictionary<string, long>   m_BuyOrderAmount  = new ConcurrentDictionary<string, long>();
        private int m_buyScreenIdx = 9; // 5010~5099 순환 (화면번호 충돌 방지)

        // DB lists
        private List<DBInfo> m_HoldingDbInfoList = new List<DBInfo>();
        private readonly object m_HoldingLock = new object(); // m_HoldingDbInfoList 스레드 동기화
        private List<DBInfo> m_HistoryDbInfoList = new List<DBInfo>();

        // DB settings (앱 실행 디렉토리 기준 — 다른 경로에서 실행해도 DB 유실 방지)
        private static readonly string DB_PATH = "Data Source=" + Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "BujaGazua.sqlite") + ";Pooling=true";
        private string m_HoldingTable = "HoldingTable";
        private string m_HistoryTable = "HistoryTable";

        // Condition and monitoring
        private List<ConditionInfo> m_ConditionList = new List<ConditionInfo>();
        private List<HoldJongmok> m_HoldJongmokList = new List<HoldJongmok>();
        private Dictionary<string, ConditionCheck> m_conditionCheck = new Dictionary<string, ConditionCheck>();

        // 전략 상태 대시보드 라벨
        private Label _dashboardLabel;

        // 거래이력 버튼
        private Button _historyButton;
        private Button _performanceButton;

        // 추정예탁자산 (예수금) — 매수 전 잔고 확인용
        private long m_estimatedBalance = 0;
        // 실제 주문가능금액 (추정예탁자산 - 전체평가금액)
        private long m_availableBalance = 0;

        // 장중 여부 (장개시~장마감)
        private volatile bool m_IsMarketOpen = false;

        // 실시간 코스피 지수 (장중 실시간 갱신)
        private volatile int m_RealtimeJisuPrice = 0;
        private volatile bool m_JisuBelowMA60 = false;

        // 금일 매수/매도 건수 카운터
        private int m_TodayBuyCount = 0;
        private int m_TodaySellCount = 0;

        // 계좌 잔고 주기적 갱신 타이머
        private System.Windows.Forms.Timer _balanceRefreshTimer;
        // 매도 후 빠른 확인 타이머
        private System.Windows.Forms.Timer _sellConfirmTimer;
        // 보유종목 UI 실시간 갱신 타이머 (그리드 + 우측상단 요약 동기화)
        private System.Windows.Forms.Timer _holdingUIRefreshTimer;

        // DB 로드 완료 플래그 (장개시 이벤트가 DB 로드 전에 올 수 있음)
        private volatile bool m_DbLoaded = false;

        // 최초 로그인 완료 여부 (재연결 시 중복 초기화 방지)
        private bool m_InitialLoginDone = false;

        // 연결 상태 모니터링 타이머
        private System.Windows.Forms.Timer _connectionCheckTimer;

        // 정렬 상태 추적
        private int m_conditionSortCol = -1;
        private SortOrder m_conditionSortOrder = SortOrder.None;
        private int m_holdSortCol = -1;
        private SortOrder m_holdSortOrder = SortOrder.None;

        public Form1()
        {
            // 매니저 클래스 초기화
            _dbManager = new Core.DbManager(DB_PATH);
            _conditionManager = new Core.ConditionManager();
            _strategyManager = new Core.StrategyManager();
            _orderManager = new Core.OrderManager();
            _strategyConfig = Core.StrategyConfig.Load();
            _sellStrategyManager = new Core.SellStrategyManager(_strategyConfig);
            InitializeComponent();

            // 폼 아이콘 및 타이틀 설정
            this.Icon = CreateAppIcon();
            this.Text = "AutoTrading";

            // 비상 정지 버튼 생성
            _emergencyStopButton = new Button();
            _emergencyStopButton.Text = "비상정지 (F12)";
            _emergencyStopButton.Location = new Point(945, 10);
            _emergencyStopButton.Size = new Size(110, 27);
            _emergencyStopButton.FlatStyle = FlatStyle.Flat;
            _emergencyStopButton.BackColor = Color.FromArgb(200, 40, 40);
            _emergencyStopButton.ForeColor = Color.White;
            _emergencyStopButton.Font = new Font("맑은 고딕", 9f, FontStyle.Bold);
            _emergencyStopButton.FlatAppearance.BorderColor = Color.FromArgb(160, 30, 30);
            _emergencyStopButton.Cursor = Cursors.Hand;
            _emergencyStopButton.Click += (s, ev) => EmergencyStop();
            this.Controls.Add(_emergencyStopButton);
            _emergencyStopButton.BringToFront();

            // 거래이력 버튼
            _historyButton = new Button();
            _historyButton.Text = "📋 거래이력";
            _historyButton.Size = new Size(90, 27);
            _historyButton.FlatStyle = FlatStyle.Flat;
            _historyButton.BackColor = Color.FromArgb(210, 120, 20);
            _historyButton.ForeColor = Color.White;
            _historyButton.Font = new Font("맑은 고딕", 9f, FontStyle.Bold);
            _historyButton.FlatAppearance.BorderColor = Color.FromArgb(170, 90, 10);
            _historyButton.Cursor = Cursors.Hand;
            _historyButton.Click += (s, ev) =>
            {
                var form = new TradeHistoryForm(m_HistoryDbInfoList);
                form.Show(this);
            };
            this.Controls.Add(_historyButton);
            _historyButton.BringToFront();

            _performanceButton = new Button();
            _performanceButton.Text = "📈 수익비교";
            _performanceButton.Size = new Size(90, 27);
            _performanceButton.FlatStyle = FlatStyle.Flat;
            _performanceButton.BackColor = Color.FromArgb(0, 160, 130);
            _performanceButton.ForeColor = Color.White;
            _performanceButton.Font = new Font("맑은 고딕", 9f, FontStyle.Bold);
            _performanceButton.FlatAppearance.BorderColor = Color.FromArgb(0, 120, 100);
            _performanceButton.Cursor = Cursors.Hand;
            _performanceButton.Click += (s, ev) =>
            {
                var assets = _dbManager?.LoadDailyAssets() ?? new System.Collections.Generic.List<DailyAssetRecord>();
                var form = new PerformanceChartForm(assets);
                form.Show(this);
            };
            this.Controls.Add(_performanceButton);
            _performanceButton.BringToFront();

            // F12 비상 정지 단축키
            this.KeyPreview = true;
            this.KeyDown += (s, ev) => { if (ev.KeyCode == Keys.F12) EmergencyStop(); };

            // 전략 상태 대시보드 라벨
            _dashboardLabel = new Label();
            _dashboardLabel.AutoSize = false;
            _dashboardLabel.TextAlign = ContentAlignment.MiddleLeft;
            _dashboardLabel.Font = new Font("맑은 고딕", 9f, FontStyle.Regular);
            _dashboardLabel.ForeColor = Color.FromArgb(200, 200, 200);
            _dashboardLabel.BackColor = Color.FromArgb(35, 40, 50);
            _dashboardLabel.Padding = new Padding(8, 0, 0, 0);
            _dashboardLabel.Text = "보유 0종목 | 총 수익금 0원";
            this.Controls.Add(_dashboardLabel);
            _dashboardLabel.BringToFront();

            // 패널간 크기 조절 SplitContainer 설정
            SetupSplitContainers();

            // UI 스타일 적용
            ApplyUIStyle();

            // 리사이즈 깜빡임 방지
            this.DoubleBuffered = true;
            this.SetStyle(ControlStyles.OptimizedDoubleBuffer | ControlStyles.AllPaintingInWmPaint, true);
            this.ResizeBegin += (s, ev) => this.SuspendLayout();
            this.ResizeEnd += (s, ev) =>
            {
                this.ResumeLayout(true);
                AdjustLayout();
            };
            this.Resize += (s, ev) =>
            {
                if (this.WindowState != FormWindowState.Minimized)
                    AdjustLayout();
            };

            // 주문 Test
            BuyTestButton.Click += buyTestButton;
            SellTestButton.Click += sellTestButton;


            // 로그인
            LoginButton.Click += loginButton;
            axKHOpenAPI1.OnEventConnect += onEventconect;

            axKHOpenAPI1.OnReceiveTrData += onReceiveTrData;

            axKHOpenAPI1.OnReceiveRealData += onReceiveRealData;



            // 조건식
            GetConditionButton.Click += getConditionButton;
            axKHOpenAPI1.OnReceiveConditionVer += onReceiveConditionVer;

            // 조건식 종목
            conditionCheckedListBox.SelectedIndexChanged += conditionSelectedChanged;
            axKHOpenAPI1.OnReceiveTrCondition += onReceiveTrCondition;

            // 실시간 조건식 편입 / 편출
            axKHOpenAPI1.OnReceiveRealCondition += onReceiveRealCondition;

            // 주문
            axKHOpenAPI1.OnReceiveChejanData += OnReceiveChejanData;
            axKHOpenAPI1.OnReceiveMsg += OnReceiveMsg;

            // 차트
            m_PriceSeries = chart1.Series["priceSeries"];
            m_PriceSeries["PriceUpColor"] = "Red";
            m_PriceSeries["PriceDownColor"] = "Blue";
            m_VolumeSeries = chart1.Series["volumeSeries"];
            chart1.AxisViewChanged += chart1_AxisViewChanged;
            chart1.MouseMove += chart1_MouseMove;
            chart1.ChartAreas[0].AxisY.LabelStyle.Format = "#,##0";
            chart1.ChartAreas[1].AxisY.LabelStyle.Format = "#,##0,K";

            conditionFilteredGridView.DoubleClick += showChart;

            // 로그 텍스트박스 우클릭 메뉴 (복사/전체선택)
            var logContextMenu = new ContextMenuStrip();
            var menuLogCopy = new ToolStripMenuItem("복사 (Ctrl+C)");
            var menuLogSelectAll = new ToolStripMenuItem("전체 선택 (Ctrl+A)");
            var menuLogCopyAll = new ToolStripMenuItem("전체 로그 복사");
            menuLogCopy.Click += (s, ev) => { if (logTextBox.SelectionLength > 0) Clipboard.SetText(logTextBox.SelectedText); };
            menuLogSelectAll.Click += (s, ev) => logTextBox.SelectAll();
            menuLogCopyAll.Click += (s, ev) => { if (!string.IsNullOrEmpty(logTextBox.Text)) Clipboard.SetText(logTextBox.Text); };
            logContextMenu.Items.AddRange(new ToolStripItem[] { menuLogCopy, menuLogSelectAll, new ToolStripSeparator(), menuLogCopyAll });
            logTextBox.ContextMenuStrip = logContextMenu;

            // 정렬 기능
            conditionFilteredGridView.ColumnHeaderMouseClick += conditionGridView_ColumnHeaderMouseClick;
            conditionFilteredGridView.SortCompare += conditionGridView_SortCompare;
            holdJongmokGridView.ColumnHeaderMouseClick += holdGridView_ColumnHeaderMouseClick;
            holdJongmokGridView.DataError += (s, ev) => { ev.ThrowException = false; };
            holdJongmokGridView.DataSource = _holdGridBindingSource;

            // 보유종목 그리드 우클릭 컨텍스트 메뉴
            var holdContextMenu = new ContextMenuStrip();
            var menuSellAll = new ToolStripMenuItem("전량 매도 (시장가)");
            var menuSellPartial = new ToolStripMenuItem("수량 지정 매도");
            var menuSellLimit = new ToolStripMenuItem("지정가 매도");
            var menuViewChart = new ToolStripMenuItem("차트 보기");
            var menuCopyCode = new ToolStripMenuItem("종목코드 복사");
            menuSellAll.Click += HoldGrid_SellAll_Click;
            menuSellPartial.Click += HoldGrid_SellPartial_Click;
            menuSellLimit.Click += HoldGrid_SellLimit_Click;
            menuViewChart.Click += HoldGrid_ViewChart_Click;
            menuCopyCode.Click += HoldGrid_CopyCode_Click;
            holdContextMenu.Items.AddRange(new ToolStripItem[] { menuSellAll, menuSellPartial, menuSellLimit, new ToolStripSeparator(), menuViewChart, menuCopyCode });
            holdJongmokGridView.ContextMenuStrip = holdContextMenu;
            // 우클릭 시 해당 행 선택
            holdJongmokGridView.CellMouseDown += (s, ev) =>
            {
                if (ev.Button == MouseButtons.Right && ev.RowIndex >= 0)
                {
                    holdJongmokGridView.ClearSelection();
                    holdJongmokGridView.Rows[ev.RowIndex].Selected = true;
                    holdJongmokGridView.CurrentCell = holdJongmokGridView.Rows[ev.RowIndex].Cells[0];
                }
            };
            // 더블클릭 시 차트
            holdJongmokGridView.CellDoubleClick += (s, ev) =>
            {
                if (ev.RowIndex >= 0 && ev.RowIndex < m_HoldingDbInfoList.Count)
                {
                    string code = m_HoldingDbInfoList[ev.RowIndex].종목코드;
                    if (!string.IsNullOrEmpty(code)) requestDailyChart(code);
                }
            };

            // 조건 편입 그리드 우클릭 컨텍스트 메뉴
            var condContextMenu = new ContextMenuStrip();
            var menuCondChart = new ToolStripMenuItem("차트 보기");
            var menuCondBuy = new ToolStripMenuItem("수동 매수");
            var menuCondCopy = new ToolStripMenuItem("종목코드 복사");
            menuCondChart.Click += CondGrid_ViewChart_Click;
            menuCondBuy.Click += CondGrid_ManualBuy_Click;
            menuCondCopy.Click += CondGrid_CopyCode_Click;
            condContextMenu.Items.AddRange(new ToolStripItem[] { menuCondBuy, new ToolStripSeparator(), menuCondChart, menuCondCopy });
            conditionFilteredGridView.ContextMenuStrip = condContextMenu;
            conditionFilteredGridView.CellMouseDown += (s, ev) =>
            {
                if (ev.Button == MouseButtons.Right && ev.RowIndex >= 0)
                {
                    conditionFilteredGridView.ClearSelection();
                    conditionFilteredGridView.Rows[ev.RowIndex].Selected = true;
                    conditionFilteredGridView.CurrentCell = conditionFilteredGridView.Rows[ev.RowIndex].Cells[0];
                }
            };

            // 자동 매매 시작
            ATStartButton.Click += atStartButton;
            ATStopButton.Click += atStopButton;

            // 종료 시 정리
            this.FormClosing += Form1_FormClosing;

            // 계좌 잔고 주기적 갱신 (30초 간격)
            _balanceRefreshTimer = new System.Windows.Forms.Timer();
            _balanceRefreshTimer.Interval = 30_000; // 30초
            _balanceRefreshTimer.Tick += (s, ev) =>
            {
                if (m_IsMarketOpen && !string.IsNullOrEmpty(AccountList.Text))
                    updateAccountInfo();
            };

            // 매도 후 빠른 갱신 타이머 (1회성)
            _sellConfirmTimer = new System.Windows.Forms.Timer();
            _sellConfirmTimer.Interval = 5000; // 5초
            _sellConfirmTimer.Tick += (s, ev) =>
            {
                _sellConfirmTimer.Stop();
                if (!string.IsNullOrEmpty(AccountList.Text))
                    updateAccountInfo();
            };

            // 보유종목 UI 실시간 갱신 타이머 (3초 간격 — 그리드 + 우측상단 요약 동기화)
            _holdingUIRefreshTimer = new System.Windows.Forms.Timer();
            _holdingUIRefreshTimer.Interval = 3000; // 3초
            _holdingUIRefreshTimer.Tick += (s, ev) =>
            {
                if (m_IsMarketOpen && m_HoldingDbInfoList.Count > 0)
                    RefreshHoldGrid();
            };

            // 초기 레이아웃 적용
            this.Load += (s, ev) => AdjustLayout();

            // DB 생성 & 로딩 (비동기)
            _ = LoadDbAsync();

            axKHOpenAPI1.SetRealReg(스크린.장운영정보, "", "215;20;214", "0");
        }

        private void sellTestButton(object sender, EventArgs e)
        {
            // 보유종목 그리드에서 선택된 항목이 있고, testCode가 비어있으면 그리드 기준 매도
            string code = testCode.Text.Trim();
            bool isPlaceholder = string.IsNullOrEmpty(code) || code == "종목코드";

            if (isPlaceholder)
            {
                // 보유종목 그리드에서 선택된 종목 시장가 전량 매도
                var holding = GetSelectedHolding();
                if (holding == null)
                {
                    MessageBox.Show("보유종목 그리드에서 매도할 종목을 선택하거나,\n상단에 종목코드/가격/수량을 입력해주세요.", "매도 대상 없음", MessageBoxButtons.OK, MessageBoxIcon.Information);
                    return;
                }
                HoldGrid_SellAll_Click(sender, e);
                return;
            }

            if (!int.TryParse(testAmount.Text, out int amount) || !int.TryParse(testPrice.Text, out int price))
            {
                MessageBox.Show("수량/가격을 올바르게 입력해주세요.", "입력 오류", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }
            if (MessageBox.Show($"[매도] {code} {amount}주 @ {price}원\n주문하시겠습니까?", "주문 확인", MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes)
                return;
            axKHOpenAPI1.SendOrder("매도주문;Test", 스크린.매도주문, AccountList.Text, 2, code, amount, price, "00", "");
        }

        private void buyTestButton(object sender, EventArgs e)
        {
            if (!int.TryParse(testAmount.Text, out int amount) || !int.TryParse(testPrice.Text, out int price))
            {
                MessageBox.Show("수량/가격을 올바르게 입력해주세요.", "입력 오류", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }
            if (MessageBox.Show($"[매수] {testCode.Text} {amount}주 @ {price}원\n주문하시겠습니까?", "주문 확인", MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes)
                return;
            axKHOpenAPI1.SendOrder("매수주문;Test", 스크린.매수주문, AccountList.Text, 1, testCode.Text, amount, price, "00", "");
        }

        private void OnReceiveMsg(object sender, _DKHOpenAPIEvents_OnReceiveMsgEvent e)
        {
            if (!string.IsNullOrWhiteSpace(e.sMsg))
                LogMessage($"[키움메시지] TR={e.sTrCode} RQ={e.sRQName} 메시지={e.sMsg.Trim()}");
        }

        private void OnReceiveChejanData(object sender, _DKHOpenAPIEvents_OnReceiveChejanDataEvent e)
        {
            LogMessage($"[체잔] sGubun={e.sGubun}");
            if (e.sGubun == "0") // 주문 체결
            {
                LogMessage("주문번호 " + axKHOpenAPI1.GetChejanData(9203) + " 종목코드 " +
                           axKHOpenAPI1.GetChejanData(9001) + " 주문상태 " +
                           axKHOpenAPI1.GetChejanData(913) + " 종목명 " +
                           axKHOpenAPI1.GetChejanData(302).Replace(" ", string.Empty) + " 주문수량 " +
                           axKHOpenAPI1.GetChejanData(900) + " 주문가격 " +
                           axKHOpenAPI1.GetChejanData(901) + " 미체결수량 " +
                           axKHOpenAPI1.GetChejanData(902) + " 원주문번호 " +
                           axKHOpenAPI1.GetChejanData(904) + " 매매구분 " +
                           axKHOpenAPI1.GetChejanData(906) + " 매도수구분 " +
                           axKHOpenAPI1.GetChejanData(907) + " 체결가 " +
                           axKHOpenAPI1.GetChejanData(910) + " 화면번호 " +
                           axKHOpenAPI1.GetChejanData(920));

                // 주문 거부 처리
                string 주문상태 = axKHOpenAPI1.GetChejanData(913).Trim();
                if (주문상태 == "접수거부" || 주문상태 == "확인거부")
                {
                    string 거부주문번호 = axKHOpenAPI1.GetChejanData(9203);
                    string 거부종목코드 = GetStockCode(axKHOpenAPI1.GetChejanData(9001));
                    LogMessage($"[주문거부] {주문상태} — 주문번호: {거부주문번호} 종목: {거부종목코드}");
                    m_dicBuyOrder.TryRemove(거부주문번호, out _);
                    // pending 제거 + 잔고 복원 (m_dicBuyOrder 유무 무관하게 항상 처리)
                    if (m_PendingBuyOrders.TryRemove(거부종목코드, out _))
                    {
                        m_BuyOrderTime.TryRemove(거부종목코드, out _);
                        // 주문금액 복원 (주문수량 × 주문가격, 시장가는 가격=0이므로 수량만)
                        int.TryParse(axKHOpenAPI1.GetChejanData(900), out int 거부수량);
                        int.TryParse(axKHOpenAPI1.GetChejanData(901), out int 거부가격);
                        if (거부수량 > 0 && 거부가격 > 0)
                            m_availableBalance += (long)거부수량 * 거부가격;
                    }
                    m_dicSellOrder.TryRemove(거부주문번호, out _);
                    if (m_PendingSellOrders.ContainsKey(거부종목코드))
                        m_PendingSellOrders.TryRemove(거부종목코드, out _);
                    return;
                }

                if (!int.TryParse(axKHOpenAPI1.GetChejanData(902), out int 미체결수량))
                    return;

                // 접수 이벤트 (미체결수량 > 0): 주문번호 → m_dicBuyOrder 등록
                // (onReceiveTrData에서 주문번호가 빈 문자열로 오는 경우 보완)
                if (미체결수량 != 0)
                {
                    if (!int.TryParse(axKHOpenAPI1.GetChejanData(907), out int _접수매도수구분))
                        return;
                    if (_접수매도수구분 == 2) // 매수 접수
                    {
                        string _접수주문번호 = axKHOpenAPI1.GetChejanData(9203);
                        string _접수종목코드 = GetStockCode(axKHOpenAPI1.GetChejanData(9001));
                        if (!string.IsNullOrEmpty(_접수주문번호) && !m_dicBuyOrder.ContainsKey(_접수주문번호))
                        {
                            if (m_PendingBuyOrders.TryGetValue(_접수종목코드, out string _접수조건명))
                            {
                                m_dicBuyOrder[_접수주문번호] = _접수조건명;
                                m_BuyOrderNo[_접수종목코드] = _접수주문번호; // 취소 시 원주문번호로 사용
                                LogMessage($"[접수확인] {_접수종목코드} 주문번호={_접수주문번호} 등록");
                            }
                        }
                    }
                    return;
                }

                if (!int.TryParse(axKHOpenAPI1.GetChejanData(907), out int 매도수구분))
                    return;

                string 주문번호 = axKHOpenAPI1.GetChejanData(9203);

                if (매도수구분 == 1) // 1 : 매도
                {
                    LogMessage("매도완 주문번호 " + 주문번호 + " " + axKHOpenAPI1.GetChejanData(302));

                    string _조건명 = "";
                    string _매도유형 = "";

                    if (m_dicSellOrder.TryGetValue(주문번호, out string _sellInfo))
                    {
                        // _sellInfo = "조건명;매도유형"
                        string[] sellParts = _sellInfo.Split(';');
                        _조건명 = sellParts[0];
                        _매도유형 = sellParts.Length >= 2 ? sellParts[1] : "";
                    }
                    else
                    {
                        // m_dicSellOrder에 없으면 수동매도/미등록 주문 — 종목코드 기반 fallback
                        LogMessage($"매도 주문번호 미등록 — 종목코드 기반 처리: {주문번호}");
                        _조건명 = "수동";
                        _매도유형 = "수동전량매도";
                    }

                    int.TryParse(axKHOpenAPI1.GetChejanData(910), out int 체결가);
                    int.TryParse(axKHOpenAPI1.GetChejanData(900), out int 주문수량);

                    // 보유종목 찾기: 1차 종목명+전략으로 검색, 2차 종목코드로 검색
                    string 체결종목명 = axKHOpenAPI1.GetChejanData(302).Replace(" ", string.Empty);
                    string 체결종목코드 = GetStockCode(axKHOpenAPI1.GetChejanData(9001));
                    DBInfo holding = null;
                    int index = -1;

                    // 1차: 종목명 + 매수전략 매칭
                    if (!string.IsNullOrEmpty(_조건명) && _조건명 != "수동")
                    {
                        for (int i = 0; i < m_HoldingDbInfoList.Count; i++)
                        {
                            if (m_HoldingDbInfoList[i].종목명 == 체결종목명
                                && m_HoldingDbInfoList[i].매수전략 == _조건명)
                            {
                                holding = m_HoldingDbInfoList[i];
                                index = i;
                                break;
                            }
                        }
                    }

                    // 2차: 종목코드로 검색 (수동매도 또는 1차 실패 시)
                    if (holding == null)
                    {
                        for (int i = 0; i < m_HoldingDbInfoList.Count; i++)
                        {
                            if (m_HoldingDbInfoList[i].종목코드 == 체결종목코드)
                            {
                                holding = m_HoldingDbInfoList[i];
                                index = i;
                                _조건명 = holding.매수전략; // 실제 전략명으로 덮어쓰기
                                break;
                            }
                        }
                    }

                    // 3차: 종목명으로 검색 (코드가 비어있을 수 있는 경우)
                    if (holding == null)
                    {
                        for (int i = 0; i < m_HoldingDbInfoList.Count; i++)
                        {
                            if (m_HoldingDbInfoList[i].종목명 == 체결종목명)
                            {
                                holding = m_HoldingDbInfoList[i];
                                index = i;
                                _조건명 = holding.매수전략;
                                break;
                            }
                        }
                    }

                    if (holding == null)
                    {
                        LogMessage("매도완료 종목을 보유목록에서 찾을 수 없음: " + 체결종목명 + "(" + 체결종목코드 + ")");
                        m_dicSellOrder.TryRemove(주문번호, out _);
                        m_PendingSellOrders.TryRemove(체결종목코드, out _);
                        return;
                    }

                    // m_dicSellOrder value 형식: "조건명" 또는 "매도유형" (sRQName에서 파싱된 값)
                    // sRQName: "매도주문;조건명;매도유형"
                    bool 부분매도 = (주문수량 < holding.보유수량);

                    if (부분매도)
                    {
                        // 부분매도: 보유수량 차감 + DB Update
                        holding.보유수량 -= 주문수량;
                        if (holding.보유수량 <= 0)
                        {
                            // 보유수량이 0 이하면 전량매도로 전환
                            부분매도 = false;
                        }
                        else
                        {
                            // 부분매도 유형별 기록
                            if (_매도유형 == "이평이탈")
                            {
                                // EMA 이탈 단계 기록
                                // _sellInfo에서 매도이유 파싱은 불가하므로, 매도유형으로 판별
                                // 이평매도수량 누적, 이평매도가격 최근가
                                holding.이평매도수량 += 주문수량;
                                holding.이평매도가격 = 체결가;
                                // 이평매도일자에 완료된 EMA 기간 기록 (SellSignal 매도이유에서 추출)
                                // 매도이유는 sRQName에 없으므로 현재 이탈된 EMA 단계를 추정
                                // → 짧은 기간부터 순서대로 매도하므로, 미완료 중 가장 짧은 기간이 이번 단계
                                var completedStages = new HashSet<int>();
                                if (!string.IsNullOrEmpty(holding.이평매도일자))
                                    foreach (var s in holding.이평매도일자.Split(','))
                                        if (int.TryParse(s.Trim(), out int st)) completedStages.Add(st);
                                foreach (int period in _strategyConfig.EMA매도기간.OrderBy(p => p))
                                {
                                    if (!completedStages.Contains(period))
                                    {
                                        holding.이평매도일자 = Core.SellStrategyManager.RecordEmaStage(holding.이평매도일자, period);
                                        break;
                                    }
                                }
                            }
                            else
                            {
                                // nR절반익절 기록
                                holding.nR절반매도 = true;
                                holding.nR절반매도일자 = DateTime.Now.ToString("yyyyMMdd");
                                holding.nR절반매도가격 = 체결가;
                                holding.nR절반매도수량 = 주문수량;
                            }

                            updateHoldingDB(holding);
                            LogMessage($"[부분매도] {holding.종목명} {_매도유형} {주문수량}주 @ {체결가:N0}원 (잔여 {holding.보유수량}주)");
                            m_TodaySellCount++;
                        }
                    }

                    if (!부분매도)
                    {
                        // 전량매도: History로 이동
                        holding.전량매도일 = DateTime.Now.ToString("yyyyMMdd");

                        // --- 매도이유 구체화 ---
                        string 매도이유표시 = null;
                        bool nr익절 = holding.nR절반매도;
                        int emaPeriod = 0;
                        if (!string.IsNullOrEmpty(holding.이평매도일자))
                        {
                            var arr = holding.이평매도일자.Split(',');
                            if (arr.Length > 0)
                            {
                                string last = arr[arr.Length - 1];
                                if (int.TryParse(last, out int p)) emaPeriod = p;
                            }
                        }
                        bool isEmaSell = _매도유형 == "이평이탈" || emaPeriod > 0;
                        bool isTrailing = _매도유형 == "로스컷" && holding.로스컷단계 > 0 && holding.로스컷가격 > 0 && 체결가 <= holding.로스컷가격;
                        bool isLossCut = _매도유형 == "로스컷" && holding.로스컷단계 > 0 && (!isTrailing);
                        bool isMaxHold = _매도유형 == "최대보유일";
                        bool isCrash = _매도유형 == "급락매도";
                        bool isBigVol = _매도유형 == "장대음봉";
                        bool isManual = _매도유형.StartsWith("수동");

                        // 손익 판단
                        bool isProfit = holding.매수가격 > 0 && 체결가 > holding.매수가격;
                        string profitStr = isProfit ? "(익절)" : "(손실)";

                        if (nr익절 && isEmaSell)
                        {
                            매도이유표시 = $"nR익절 후 EMA{emaPeriod} 이탈{profitStr}";
                        }
                        else if (nr익절 && isTrailing)
                        {
                            매도이유표시 = "nR익절 후 트레일링스탑";
                        }
                        else if (nr익절 && isLossCut)
                        {
                            매도이유표시 = "nR익절 후 로스컷";
                        }
                        else if (nr익절)
                        {
                            매도이유표시 = "nR익절 후 전량매도";
                        }
                        else if (isEmaSell)
                        {
                            매도이유표시 = $"EMA{emaPeriod} 이탈{profitStr}";
                        }
                        else if (isTrailing)
                        {
                            매도이유표시 = $"트레일링스탑{profitStr}";
                        }
                        else if (isLossCut)
                        {
                            매도이유표시 = "nR 미달 로스컷";
                        }
                        else if (isMaxHold)
                        {
                            매도이유표시 = "최대보유일 초과";
                        }
                        else if (isCrash)
                        {
                            매도이유표시 = "급락매도";
                        }
                        else if (isBigVol)
                        {
                            매도이유표시 = "장대음봉";
                        }
                        else if (isManual)
                        {
                            매도이유표시 = "수동매도";
                        }
                        else
                        {
                            매도이유표시 = string.IsNullOrEmpty(_매도유형) ? (!string.IsNullOrEmpty(_조건명) ? _조건명 : "기타") : _매도유형;
                        }

                        holding.전량매도이유 = 매도이유표시;
                        holding.매도가격 = 체결가;

                        // 최종수익금 계산: 부분매도 실현 수익 + 잔여수량 수익 합산
                        int 부분매도실현수익 = 0;
                        int 부분매도총수량 = 0;

                        // nR절반익절 부분매도 수익
                        if (holding.nR절반매도 && holding.nR절반매도수량 > 0 && holding.nR절반매도가격 > 0)
                        {
                            부분매도실현수익 += (holding.nR절반매도가격 - holding.매수가격) * holding.nR절반매도수량;
                            부분매도총수량 += holding.nR절반매도수량;
                        }

                        // EMA 이탈 부분매도 수익 (이평매도수량은 누적, 이평매도가격은 최근가 기준 근사)
                        if (holding.이평매도수량 > 0 && holding.이평매도가격 > 0)
                        {
                            부분매도실현수익 += (holding.이평매도가격 - holding.매수가격) * holding.이평매도수량;
                            부분매도총수량 += holding.이평매도수량;
                        }

                        if (부분매도총수량 > 0)
                        {
                            int 잔여수량 = holding.매수수량 - 부분매도총수량;
                            int 잔여매도수익 = (holding.매도가격 - holding.매수가격) * Math.Max(잔여수량, 0);
                            holding.최종수익금 = 부분매도실현수익 + 잔여매도수익;
                        }
                        else
                        {
                            holding.최종수익금 = (holding.매도가격 - holding.매수가격) * holding.매수수량;
                        }
                        int 총투자금 = holding.매수가격 * holding.매수수량;
                        holding.최종수익률 = 총투자금 != 0 ? (float)holding.최종수익금 / 총투자금 * 100f : 0f;

                        m_HistoryDbInfoList.Add(holding);
                        deleteHoldingInsertHistory(holding);

                        if (index >= 0)
                            lock (m_HoldingLock) { m_HoldingDbInfoList.RemoveAt(index); }

                        // 실시간 시세 해제
                        if (!string.IsNullOrEmpty(holding.종목코드))
                        {
                            axKHOpenAPI1.SetRealRemove(스크린.보유종목실시간, holding.종목코드);
                            m_RealTimePrices.TryRemove(holding.종목코드, out _);
                        }

                        LogMessage($"[전량매도] {holding.종목명} @ {체결가:N0}원 수익률 {holding.최종수익률:F2}% 수익금 {holding.최종수익금:N0}원");
                        m_TodaySellCount++;
                    }

                    RefreshHoldGrid();
                    updateAccountInfo();
                    m_dicSellOrder.TryRemove(주문번호, out _);
                    // pending 매도 제거
                    if (!string.IsNullOrEmpty(holding.종목코드))
                        m_PendingSellOrders.TryRemove(holding.종목코드, out _);
                }
                else // 2 : 매수
                {
                    // 매수 완료 시 DB m_HoldingDbInfoList 에 반영
                    LogMessage("매수완 주문번호 " + 주문번호 + " " + axKHOpenAPI1.GetChejanData(302));
                    if (!m_dicBuyOrder.TryGetValue(주문번호, out string _조건명))
                    {
                        LogMessage("매수 주문번호를 찾을 수 없음: " + 주문번호);
                        return;
                    }

                    int.TryParse(axKHOpenAPI1.GetChejanData(900), out int 주문수량);
                    int.TryParse(axKHOpenAPI1.GetChejanData(910), out int 체결가);

                    var newHolding = new DBInfo()
                    {
                        종목명 = axKHOpenAPI1.GetChejanData(302).Replace(" ", string.Empty),
                        종목코드 = GetStockCode(axKHOpenAPI1.GetChejanData(9001)),

                        매수일 = DateTime.Now.ToString("yyyyMMdd"),
                        매수전략 = _조건명,
                        전량매도일 = "",
                        전량매도이유 = "",
                        매도가격 = 0,
                        최종수익률 = 0,
                        최종수익금 = 0,

                        매수수량 = 주문수량,
                        보유수량 = 주문수량,
                        매수가격 = 체결가,
                        로스컷단계 = 0,
                        로스컷가격 = 0,
                        보유일 = 1,

                        돌파매수 = false,
                        nR절반매도일자 = "",
                        nR절반매도 = false,
                        nR절반매도가격 = 0,
                        nR절반매도수량 = 0,

                        이평매도일자 = "",
                        이평매도가격 = 0,
                        이평매도수량 = 0,
                    };

                    // 초기 로스컷가격 설정 (매수가 기준 -R%) — DB 저장 전에 설정
                    newHolding.로스컷가격 = (int)(newHolding.매수가격 * (1.0 - _strategyConfig.R값 / 100.0));

                    lock (m_HoldingLock) { m_HoldingDbInfoList.Add(newHolding); }
                    insertDB(m_HoldingTable, newHolding);

                    // 매수 완료 → 실시간 시세 등록 (매도 감시를 위해)
                    if (!string.IsNullOrEmpty(newHolding.종목코드))
                    {
                        axKHOpenAPI1.SetRealReg(스크린.보유종목실시간, newHolding.종목코드, "10;11;12;15;16;17;18", "1");
                        LogMessage($"[매수완료] {newHolding.종목명}({newHolding.종목코드}) {주문수량}주 @ {체결가:N0}원 LC={newHolding.로스컷가격:N0}원 → 실시간 등록");
                    }

                    m_TodayBuyCount++;
                    RefreshHoldGrid();
                    updateAccountInfo();
                    m_dicBuyOrder.TryRemove(주문번호, out _);
                    // pending 매수 제거
                    if (!string.IsNullOrEmpty(newHolding.종목코드))
                    {
                        m_PendingBuyOrders.TryRemove(newHolding.종목코드, out _);
                        m_BuyOrderTime.TryRemove(newHolding.종목코드, out _);
                        m_BuyOrderScreen.TryRemove(newHolding.종목코드, out _);
                        m_BuyOrderNo.TryRemove(newHolding.종목코드, out _);
                    }
                }
            }
        }

        private void onReceiveRealData(object sender, _DKHOpenAPIEvents_OnReceiveRealDataEvent e)
        {
            if (e.sRealType == "주식체결")
            {
                string 종목코드 = e.sRealKey;
                int.TryParse(axKHOpenAPI1.GetCommRealData(e.sRealType, 10).Replace("+", "").Replace("-", ""), out int 현재가);
                현재가 = Math.Abs(현재가);

                // 보유종목이면 현재가/수익률 갱신
                DBInfo holding = null;
                lock (m_HoldingLock) { holding = m_HoldingDbInfoList.FirstOrDefault(h => h.종목코드 == 종목코드); }
                if (holding != null && 현재가 > 0)
                {
                    holding.현재가 = 현재가;
                    holding.평가금 = 현재가 * holding.보유수량;
                    if (holding.매수가격 > 0)
                    {
                        holding.현재수익률 = (float)(현재가 - holding.매수가격) / holding.매수가격 * 100f;
                        holding.현재수익금 = (현재가 - holding.매수가격) * holding.보유수량;
                    }

                    // 트레일링 스탑 갱신
                    _sellStrategyManager.UpdateTrailingStop(holding, 현재가);

                    // RealTimePrice 갱신
                    int.TryParse(axKHOpenAPI1.GetCommRealData(e.sRealType, 16).Replace("+", "").Replace("-", ""), out int 시가);
                    int.TryParse(axKHOpenAPI1.GetCommRealData(e.sRealType, 17).Replace("+", "").Replace("-", ""), out int 고가);
                    int.TryParse(axKHOpenAPI1.GetCommRealData(e.sRealType, 18).Replace("+", "").Replace("-", ""), out int 저가);
                    long.TryParse(axKHOpenAPI1.GetCommRealData(e.sRealType, 15).Replace("+", "").Replace("-", ""), out long 거래량);
                    int.TryParse(axKHOpenAPI1.GetCommRealData(e.sRealType, 11), out int 전일대비raw);

                    m_RealTimePrices[종목코드] = new Core.RealTimePrice
                    {
                        종목코드 = 종목코드,
                        현재가 = 현재가,
                        시가 = Math.Abs(시가),
                        고가 = Math.Abs(고가),
                        저가 = Math.Abs(저가),
                        거래량 = Math.Abs(거래량),
                        전일종가 = 현재가 - 전일대비raw // 전일종가 = 현재가 - 전일대비(부호포함)
                    };
                }
            }
            else if (e.sRealType == "업종지수")
            {
                // 코스피 지수 실시간 갱신
                string 업종코드 = e.sRealKey;
                if (업종코드 == "001") // 코스피
                {
                    int.TryParse(axKHOpenAPI1.GetCommRealData(e.sRealType, 10).Replace("+", "").Replace("-", "").Replace(".", ""), out int 지수현재가);
                    if (지수현재가 > 0)
                    {
                        m_RealtimeJisuPrice = 지수현재가;

                        // MA60 비교 (장개시 시 계산된 값 활용)
                        lock (m_MonitoringLock)
                        {
                            if (m_conditionCheck.TryGetValue("지수", out var jisuCheck) &&
                                jisuCheck.이동평균.TryGetValue("ma60", out var ma60List) &&
                                ma60List.Count > 0)
                            {
                                bool wasBelowMA60 = m_JisuBelowMA60;
                                m_JisuBelowMA60 = 지수현재가 < ma60List[0];

                                // 상태 변경 시 로그
                                if (m_JisuBelowMA60 && !wasBelowMA60)
                                    LogMessage($"[지수경고] 코스피({지수현재가}) MA60({ma60List[0]}) 하회 → 신규 매수 차단");
                                else if (!m_JisuBelowMA60 && wasBelowMA60)
                                    LogMessage($"[지수회복] 코스피({지수현재가}) MA60({ma60List[0]}) 상회 → 매수 허용");
                            }
                        }
                    }
                }
            }
            else if (e.sRealType == "장시작시간")
            {
                string 장구분 = axKHOpenAPI1.GetCommRealData(e.sRealType, 215).Trim();
                LogMessage("장운영 구분 " + 장구분 +
                    " 현재시간 " + axKHOpenAPI1.GetCommRealData(e.sRealType, 20) +
                    " 남은시간 " + axKHOpenAPI1.GetCommRealData(e.sRealType, 214));

                if (장구분 == "3") // 장개시
                {
                    m_IsMarketOpen = true;
                    LogMessage("장 개시 - 보유종목 실시간 등록 및 보유일 갱신");

                    // DB 로드가 아직 안끝났으면 잠시 대기 (최대 5초)
                    if (!m_DbLoaded)
                    {
                        LogMessage("[대기] DB 로드 완료 대기 중...");
                        for (int wait = 0; wait < 50 && !m_DbLoaded; wait++)
                            System.Threading.Thread.Sleep(100);
                        if (!m_DbLoaded)
                            LogMessage("[경고] DB 로드 타임아웃 — 보유종목 없이 계속 진행");
                    }

                    // 코스피 지수 데이터 갱신 (당일분 반영)
                    requestJisuInfo();
                    // 보유일 +1 갱신
                    foreach (var h in m_HoldingDbInfoList)
                    {
                        if (!string.IsNullOrEmpty(h.매수일))
                        {
                            try
                            {
                                h.보유일 = (DateTime.Now.Date - DateTime.ParseExact(h.매수일, "yyyyMMdd", null)).Days + 1;
                            }
                            catch { h.보유일++; }
                        }
                        else
                        {
                            h.보유일++;
                        }
                    }
                    // 보유종목 실시간 시세 등록
                    RegisterHoldingsRealTime();
                    // 보유종목 일봉 데이터 갱신 (50일 거래량 캐싱)
                    if (m_MonitoringCts != null && !m_MonitoringCts.IsCancellationRequested)
                        _ = Task.Run(() => FetchHoldingsDailyData(m_MonitoringCts.Token));
                    // 매도 모니터 시작
                    StartSellMonitor();
                    // UI 갱신
                    RefreshHoldGrid();
                }
                else if (장구분 == "2") // 장마감알림
                {
                    LogMessage("장 마감 알림 - 매도 모니터 중지");
                    m_IsMarketOpen = false;
                    StopSellMonitor();
                }
                else if (장구분 == "4") // 장마감
                {
                    LogMessage("장 마감 - DB 일괄 저장");
                    m_IsMarketOpen = false;
                    StopSellMonitor();
                    _dbManager.UpdateAll(m_HoldingDbInfoList);

                    // 일일 리포트 생성
                    GenerateDailyReport();
                }

                /*
                장운영 구분
                0 장전알림
                2 장마감알림
                3 장개시
                4 장마감
                a 장후종가
                c 시간외 단일
                */

                /*
                매수가격.. 호가에서 긁어 오던지 해야 함...

                int orderCount = 0;
                if (axKHOpenAPI1.GetCommRealData(e.sRealType, 215) == "2" || 
                    axKHOpenAPI1.GetCommRealData(e.sRealType, 214) == "001000")
                {
                    foreach (ConditionInfo condition in m_ConditionList)
                    {
                        if (condition.실시간등록여부 == false)
                            continue;


  
                        foreach (StockItemInfo stockInfo in condition.stockItemList)
                        {
                            if (orderCount % 4 == 0)
                                delay(1000);

                            axKHOpenAPI1.SendOrder("매수주문;" + condition.조건식이름 , 스크린.매수주문, AccountList.Text, 1, stockInfo.종목코드,
                                                    int.Parse(testAmount.Text), int.Parse(testPrice.Text), "00", "");

                            orderCount++;
                        }
                        

                    }
                }
                */






                /*
                 * axKHOpenAPI1.SendOrder("매수주문", 스크린.매수주문, AccountList.Text, 1, "145020", 100, 220000, "00", "");
                 *           SendOrder(
          BSTR sRQName, // 사용자 구분명
          BSTR sScreenNo, // 화면번호
          BSTR sAccNo,  // 계좌번호 10자리
          LONG nOrderType,  // 주문유형 1:신규매수, 2:신규매도 3:매수취소, 4:매도취소, 5:매수정정, 6:매도정정, 7:프로그램매매 매수, 8:프로그램매매 매도
          BSTR sCode, // 종목코드 (6자리)
          LONG nQty,  // 주문수량
          LONG nPrice, // 주문가격
          BSTR sHogaGb,   // 거래구분(혹은 호가구분)은 아래 참고
          BSTR sOrgOrderNo  // 원주문번호. 신규주문에는 공백 입력, 정정/취소시 입력합니다.
          )
                SendOrder 로 주문 넣고
                OnReceiveTrData 에서 주문번호 받아 옴
                OnReceiveChejanData 로 결과 회신 GetChejanData FID 항목 값 확인
                axKHOpenAPI1.SendOrder("매수주문", 스크린.매수주문, AccountList.Text, 1, "145020", 100, 230000, "00", "");

                */
            }
        }

        private void requestJisuInfo()
        {
            LogMessage("requestJisuInfo");
            axKHOpenAPI1.SetInputValue("업종코드", "001");
            axKHOpenAPI1.SetInputValue("기준일자", DateTime.Now.ToString("yyyyMMdd"));

            int nRet = axKHOpenAPI1.CommRqData("지수일봉조회", "OPT20006", 0, GetScrNum());
        }

        public void requestJongmokDaily(string stockCode)
        {
            LogMessage("requestJongmokDaily");
            axKHOpenAPI1.SetInputValue("종목코드", stockCode);
            axKHOpenAPI1.SetInputValue("기준일자", DateTime.Now.ToString("yyyyMMdd"));
            axKHOpenAPI1.SetInputValue("수정주가구분", "1");

            string _종목명 = axKHOpenAPI1.GetMasterCodeName(stockCode);

            //int nRet = axKHOpenAPI1.CommRqData("종목일봉차트조회;" + _종목명, "OPT10081", 0, 스크린.종목일봉정보);
            int nRet = 0; // TODO: 위 주석 해제하여 실제 API 호출 활성화 필요
            if (nRet == 0 && false) // 비활성 상태 - 실제 API 호출 시 && false 제거
                LogMessage("종목 일봉 정보요청 성공 " + axKHOpenAPI1.GetMasterCodeName(stockCode));
            else
                LogMessage("종목 일봉 정보요청 실패 " + axKHOpenAPI1.GetMasterCodeName(stockCode));
        }


        /*
         DB 관련 함수 START
         */

        // 보유종목 매도 후 히스토리로 이동
        private void deleteHoldingInsertHistory(DBInfo dbInfo)
        {
            _dbManager.MoveToHistory(dbInfo);
        }

        private void updateHoldingDays()
        {
            foreach (DBInfo holding in m_HoldingDbInfoList)
            {
                try
                {
                    holding.보유일 = (DateTime.Now.Date - DateTime.ParseExact(holding.매수일, "yyyyMMdd", null)).Days + 1;
                }
                catch
                {
                    holding.보유일++;
                }
            }
            _dbManager.UpdateAll(m_HoldingDbInfoList);
        }

        // 매수 or 매도 후 DB INSERT
        private void insertDB(string tableName, DBInfo dbInfo)
        {
            if (dbInfo != null)
            {
                _dbManager.Insert(tableName, dbInfo);
            }
        }

        private void updateAllHoldingDB()
        {
            _dbManager.UpdateAll(m_HoldingDbInfoList);
        }

        // 기 보유종목 DB Update 함수
        private void updateHoldingDB(DBInfo holding)
        {
            _dbManager.Update(m_HoldingTable, holding);
        }

        // 프로그램 실행 시 DB Load
        private async Task LoadDbAsync()
        {
            await Core.AsyncHelper.RunSafeAsync(async () =>
            {
                await Task.Run(() =>
                {
                    _dbManager.EnsureTables();
                    m_HoldingDbInfoList = _dbManager.LoadAll(m_HoldingTable);
                    m_HistoryDbInfoList = _dbManager.LoadAll(m_HistoryTable);
                });

                // DB 로드 후 즉시 보유종목 그리드 표시
                RefreshHoldGrid();
                m_DbLoaded = true;
                LogMessage($"DB 로드 완료 - 보유 {m_HoldingDbInfoList.Count}건, 히스토리 {m_HistoryDbInfoList.Count}건");
            },
            ex => Core.AsyncHelper.RunOnUIThread(this, () => MessageBox.Show($"DB 로딩 오류: {ex.Message}", "오류", MessageBoxButtons.OK, MessageBoxIcon.Error)));
        }

        /// <summary>
        /// 보유종목 그리드 갱신 (DataSource 재바인딩 + 포맷 + 수익률 색상)
        /// </summary>
        private void RefreshHoldGrid()
        {
            List<DBInfo> snapshot;
            lock (m_HoldingLock) { snapshot = m_HoldingDbInfoList.ToList(); }
            _holdGridBindingSource.DataSource = snapshot;
            FormatHoldGrid();

            for (int i = 0; i < snapshot.Count; i++)
            {
                if (snapshot[i].현재수익률 < 0)
                    holdJongmokGridView["현재수익률", i].Style.ForeColor = Color.Blue;
                else if (snapshot[i].현재수익률 > 0)
                    holdJongmokGridView["현재수익률", i].Style.ForeColor = Color.Red;
            }

            // 우측 상단 평가수익/수익률 라벨도 보유종목 실시간 데이터 기준으로 동기화
            UpdateHoldingSummaryLabels(snapshot);

            UpdateDashboard();
        }

        /// <summary>
        /// 보유종목 실시간 데이터 기반으로 우측 상단 평가수익/수익률 라벨 갱신
        /// </summary>
        private void UpdateHoldingSummaryLabels(List<DBInfo> snapshot)
        {
            try
            {
                if (snapshot == null || snapshot.Count == 0) return;

                // 평가수익/수익률만 실시간 갱신 (보유종목 그리드와 동기화)
                // 평가금·예수금·매수금은 키움 API 공식 데이터(updateAccountInfo)로만 갱신
                long 전체매입금액 = snapshot.Sum(h => (long)h.매수가격 * h.보유수량);
                long 전체손익금액 = snapshot.Sum(h => (long)h.현재수익금);
                float 전체수익률 = 전체매입금액 > 0 ? (float)전체손익금액 / 전체매입금액 * 100f : 0f;

                평가수익label.Text = $"{(전체손익금액 >= 0 ? "+" : "")}{전체손익금액:N0}";
                수익률label.Text = $"{(전체수익률 >= 0 ? "+" : "")}{전체수익률:F2}%";
                평가수익label.ForeColor = 전체손익금액 >= 0 ? Color.FromArgb(220, 50, 50) : Color.FromArgb(50, 50, 220);
                수익률label.ForeColor = 전체수익률 >= 0 ? Color.FromArgb(220, 50, 50) : Color.FromArgb(50, 50, 220);
            }
            catch { }
        }

        /// <summary>
        /// 전략 상태 대시보드 갱신
        /// </summary>
        private void UpdateDashboard()
        {
            try
            {
                int count;
                long totalProfit;
                long totalBuyAmount;
                string holdingDetails;
                lock (m_HoldingLock)
                {
                    count = m_HoldingDbInfoList.Count;
                    totalProfit = m_HoldingDbInfoList.Sum(h => (long)h.현재수익금);
                    totalBuyAmount = m_HoldingDbInfoList.Sum(h => (long)h.매수가격 * h.보유수량);
                    // 개별 종목 수익률 요약 (종목명 수익률%)
                    holdingDetails = count > 0
                        ? string.Join(" | ", m_HoldingDbInfoList
                            .OrderByDescending(h => h.현재수익률)
                            .Select(h => $"{h.종목명} {(h.현재수익률 >= 0 ? "+" : "")}{h.현재수익률:F1}%"))
                        : "";
                }
                float totalProfitRate = totalBuyAmount > 0 ? (float)totalProfit / totalBuyAmount * 100f : 0f;
                string monitorStatus = m_SellMonitorRunning ? "가동중" : "중지";
                string profitColor = totalProfit >= 0 ? "+" : "";
                string jisuStatus = m_RealtimeJisuPrice > 0
                    ? (m_JisuBelowMA60 ? $"▼{m_RealtimeJisuPrice}" : $"▲{m_RealtimeJisuPrice}")
                    : "—";

                // 계좌 수익률 (초기자산 대비) — 제거됨

                string text = $"보유 {count}종목 | " +
                              $"보유수익 {profitColor}{totalProfit:N0}원 ({totalProfitRate:F2}%) | " +
                              $"매수 {m_TodayBuyCount} 매도 {m_TodaySellCount} | " +
                              $"코스피 {jisuStatus} | " +
                              $"매도모니터: {monitorStatus}" +
                              (count > 0 ? $"  ▸ {holdingDetails}" : "");

                if (_dashboardLabel.InvokeRequired)
                    _dashboardLabel.BeginInvoke(new Action(() =>
                    {
                        _dashboardLabel.Text = text;
                        _dashboardLabel.ForeColor = totalProfit >= 0 ? Color.FromArgb(255, 120, 120) : Color.FromArgb(100, 150, 255);
                    }));
                else
                {
                    _dashboardLabel.Text = text;
                    _dashboardLabel.ForeColor = totalProfit >= 0 ? Color.FromArgb(255, 120, 120) : Color.FromArgb(100, 150, 255);
                }
            }
            catch (Exception ex) { LogMessage($"[Dashboard] {ex.Message}"); }
        }

        /// <summary>
        /// 장 마감 시 금일 거래 요약 리포트 생성
        /// </summary>
        private void GenerateDailyReport()
        {
            try
            {
                string today = DateTime.Now.ToString("yyyyMMdd");
                var 금일매도 = m_HistoryDbInfoList.Where(h => h.전량매도일 == today).ToList();

                long 보유총평가 = m_HoldingDbInfoList.Sum(h => (long)h.현재가 * h.보유수량);
                long 보유총매입 = m_HoldingDbInfoList.Sum(h => (long)h.매수가격 * h.보유수량);
                long 보유총수익금 = m_HoldingDbInfoList.Sum(h => (long)h.현재수익금);
                float 보유총수익률 = 보유총매입 > 0 ? (float)보유총수익금 / 보유총매입 * 100f : 0f;

                long 금일매도수익금 = 금일매도.Sum(h => (long)h.최종수익금);
                int 금일매도승수 = 금일매도.Count(h => h.최종수익금 > 0);
                int 금일매도패수 = 금일매도.Count(h => h.최종수익금 <= 0);

                LogMessage("═══════════════════════════════════════");
                LogMessage($"  📊 일일 리포트 ({DateTime.Now:yyyy-MM-dd})");
                LogMessage("═══════════════════════════════════════");
                LogMessage($"  매수 {m_TodayBuyCount}건 | 매도 {m_TodaySellCount}건 (전량 {금일매도.Count}건)");
                if (금일매도.Count > 0)
                {
                    LogMessage($"  매도 승/패: {금일매도승수}승 {금일매도패수}패 (승률 {(금일매도.Count > 0 ? 금일매도승수 * 100.0 / 금일매도.Count : 0):F1}%)");
                    LogMessage($"  금일 실현손익: {금일매도수익금:N0}원");
                    foreach (var h in 금일매도)
                        LogMessage($"    {h.종목명} {h.전량매도이유} → {h.최종수익률:F2}% ({h.최종수익금:N0}원)");
                }
                LogMessage($"  보유 {m_HoldingDbInfoList.Count}종목 | 평가 {보유총평가:N0}원 | 수익금 {보유총수익금:N0}원 ({보유총수익률:F2}%)");
                foreach (var h in m_HoldingDbInfoList)
                    LogMessage($"    {h.종목명} {h.현재수익률:F2}% ({h.현재수익금:N0}원) D+{h.보유일} LC:{h.로스컷가격:N0}");
                LogMessage($"  예탁자산: {m_estimatedBalance:N0}원");
                LogMessage("═══════════════════════════════════════");

                // 일별 자산 추이 저장
                try
                {
                    _dbManager.UpsertDailyAsset(new DailyAssetRecord
                    {
                        날짜          = today,
                        추정예탁자산 = m_estimatedBalance,
                        총매입금액 = 보유총매입,
                        총평가금액 = 보유총평가,
                        보유평가손익 = 보유총수익금,
                        당일실현손익 = 금일매도수익금,
                        보유종목수   = m_HoldingDbInfoList.Count,
                        당일매수건수 = m_TodayBuyCount,
                        당일매도건수 = m_TodaySellCount,
                        당일매도승수 = 금일매도승수,
                        당일매도패수 = 금일매도패수,
                    });
                }
                catch (Exception exDA) { Core.LogManager.Log($"일별자산 저장 오류: {exDA.Message}"); }

                // 카운터 리셋 (익일 대비)
                m_TodayBuyCount = 0;
                m_TodaySellCount = 0;
            }
            catch (Exception ex) { Core.LogManager.Log($"일일 리포트 생성 오류: {ex.Message}"); }
        }

        /// <summary>
        /// 보유종목 전체를 실시간 시세 등록
        /// </summary>
        private void RegisterHoldingsRealTime()
        {
            if (m_HoldingDbInfoList.Count == 0) return;

            string codeList = string.Join(";", m_HoldingDbInfoList.Select(h => h.종목코드).Where(c => !string.IsNullOrEmpty(c)));
            if (string.IsNullOrEmpty(codeList)) return;

            // FID: 10(현재가), 11(전일대비), 12(등락률), 15(거래량), 16(시가), 17(고가), 18(저가)
            axKHOpenAPI1.SetRealReg(스크린.보유종목실시간, codeList, "10;11;12;15;16;17;18", "0");

            LogMessage($"보유종목 실시간 시세 등록: {m_HoldingDbInfoList.Count}건");
        }

        /// <summary>
        /// 매도 주문 실행 (SellSignal 기반)
        /// </summary>
        private void ExecuteSellOrder(Core.SellSignal signal, DBInfo holding)
        {
            if (signal == null || holding == null) return;
            if (signal.매도수량 <= 0 || string.IsNullOrEmpty(holding.종목코드)) return;

            // 매도가격: 현재가 - 슬리피지 (빠른 체결 위해 약간 낮게)
            int sellPrice = _sellStrategyManager.CalculateSellPrice(holding.현재가);
            if (sellPrice <= 0) sellPrice = holding.현재가;

            // sRQName: "매도주문;조건명;매도유형" (체결 시 분기용)
            string rqName = $"매도주문;{holding.매수전략};{signal.매도유형}";

            LogMessage($"[매도주문] {holding.종목명}({holding.종목코드}) {signal.매도유형} " +
                       $"{signal.매도수량}주 @ {sellPrice:N0}원 | {signal.매도이유}");

            int ret = axKHOpenAPI1.SendOrder(rqName, 스크린.매도주문, AccountList.Text, 2,
                                   holding.종목코드, signal.매도수량, sellPrice, "00", "");
            if (ret == 0)
                m_PendingSellOrders[holding.종목코드] = rqName;
        }

        /// <summary>
        /// 매도 모니터 시작 (장중 주기적으로 매도 조건 체크)
        /// </summary>
        private void StartSellMonitor()
        {
            if (m_SellMonitorRunning) return;

            // 로스컷가격=0인 보유종목 자동 계산 (DB에서 로드됐으나 로스컷 미설정 종목 복원)
            lock (m_HoldingLock)
            {
                foreach (var h in m_HoldingDbInfoList)
                {
                    if (h.로스컷가격 <= 0 && h.매수가격 > 0)
                    {
                        h.로스컷가격 = (int)(h.매수가격 * (1.0 - _strategyConfig.R값 / 100.0));
                        _dbManager.Update(m_HoldingTable, h);
                        LogMessage($"[LC복원] {h.종목명}({h.종목코드}) 로스컷가격={h.로스컷가격:N0}원 (매수가={h.매수가격:N0}원, R={_strategyConfig.R값}%)");
                    }
                }
            }

            m_SellMonitorCts = new CancellationTokenSource();
            m_SellMonitorRunning = true;
            var token = m_SellMonitorCts.Token;

            Task.Run(async () =>
            {
                LogMessage("매도 모니터 시작");
                while (!token.IsCancellationRequested)
                {
                    try
                    {
                        // 보유종목 스냅샷으로 순회 (컬렉션 변경 방지)
                        List<DBInfo> holdings;
                        lock (m_HoldingLock) { holdings = m_HoldingDbInfoList.ToList(); }
                        foreach (var holding in holdings)
                        {
                            if (token.IsCancellationRequested) break;
                            if (string.IsNullOrEmpty(holding.종목코드)) continue;

                            m_RealTimePrices.TryGetValue(holding.종목코드, out Core.RealTimePrice price);
                            if (price == null) continue;

                            // 50일 최대거래량 캐시 조회
                            m_Max50DayVolume.TryGetValue(holding.종목코드, out long 최근50일최대거래량);

                            // EMA 캐시 조회
                            m_HoldingEMA.TryGetValue(holding.종목코드, out Dictionary<int, int> emaValues);

                            var signal = _sellStrategyManager.CheckSellConditions(holding, price, 최근50일최대거래량, emaValues);
                            if (signal != null)
                            {
                                // 이미 매도 주문 진행 중이면 스킵 (중복 주문 방지)
                                if (m_PendingSellOrders.ContainsKey(holding.종목코드))
                                {
                                    continue;
                                }

                                // pending 매도 등록
                                m_PendingSellOrders[holding.종목코드] = signal.매도유형.ToString();
                                // UI 스레드에서 SendOrder 실행 (Kiwoom API는 UI 스레드 필수)
                                this.BeginInvoke(new Action(() =>
                                {
                                    ExecuteSellOrder(signal, holding);
                                }));

                                // 동일 종목 중복 주문 방지: 다음 체크까지 대기
                                await Task.Delay(300, token);
                            }
                        }
                    }
                    catch (OperationCanceledException) { break; }
                    catch (Exception ex) { Core.LogManager.Log($"매도 모니터 오류: {ex.Message}"); }

                    // 미체결 매수 주문 자동취소 체크
                    try
                    {
                        var now = DateTime.Now;
                        foreach (var kvp in m_BuyOrderTime.ToArray())
                        {
                            if ((now - kvp.Value).TotalSeconds >= BUY_TIMEOUT_SEC)
                            {
                                string code = kvp.Key;
                                if (m_PendingBuyOrders.TryRemove(code, out _))
                                {
                                    m_BuyOrderTime.TryRemove(code, out _);
                                    this.BeginInvoke(new Action(() =>
                                    {
                                        string cancelScr = m_BuyOrderScreen.TryGetValue(code, out string scr) ? scr : 스크린.매수주문;
                                        string cancelOrd = m_BuyOrderNo.TryGetValue(code, out string ord)     ? ord  : "";
                                        LogMessage($"[미체결취소] {code} — {BUY_TIMEOUT_SEC}초 초과 → 매수취소 시도 (스크린={cancelScr} 원주문={cancelOrd})");
                                        axKHOpenAPI1.SendOrder("매수취소;타임아웃", cancelScr, AccountList.Text, 3, code, 0, 0, "03", cancelOrd);
                                        m_BuyOrderScreen.TryRemove(code, out _);
                                        m_BuyOrderNo.TryRemove(code, out _);
                                        // 선차감된 주문가능금액 복원 (체잔 없이 타임아웃된 경우)
                                        if (m_BuyOrderAmount.TryRemove(code, out long _timeoutAmt))
                                            m_availableBalance += _timeoutAmt;
                                    }));
                                }
                            }
                        }
                    }
                    catch (Exception ex) { Core.LogManager.Log($"미체결 취소 오류: {ex.Message}"); }

                    // 2초 간격 체크
                    try { await Task.Delay(2000, token); }
                    catch (OperationCanceledException) { break; }
                }
                m_SellMonitorRunning = false;
                LogMessage("매도 모니터 종료");
            }, token);
        }

        /// <summary>
        /// 매도 모니터 중지
        /// </summary>
        private void StopSellMonitor()
        {
            if (m_SellMonitorCts != null && !m_SellMonitorCts.IsCancellationRequested)
            {
                m_SellMonitorCts.Cancel();
                m_SellMonitorCts.Dispose();
                m_SellMonitorCts = null;
            }
        }

        /// <summary>
        /// 비상 정지: 매도 모니터 즉시 중지 + 조건식 중지 + 미체결 취소 시도
        /// </summary>
        private void EmergencyStop()
        {
            LogMessage("!!! 비상 정지 발동 !!!");

            // 매도 모니터 중지
            StopSellMonitor();

            // 조건식 모니터 중지
            m_ConditionCts?.Cancel();

            // 모니터링 중지
            m_MonitoringCts?.Cancel();

            // 미체결 매수 주문 일괄 취소
            try
            {
                foreach (var kvp in m_PendingBuyOrders)
                {
                    string 종목코드 = kvp.Key;
                    string emergencyScr = m_BuyOrderScreen.TryGetValue(종목코드, out string eScr) ? eScr : 스크린.매수주문;
                    string emergencyOrd = m_BuyOrderNo.TryGetValue(종목코드, out string eOrd)     ? eOrd  : "";
                    LogMessage($"[비상정지] 매수취소 시도: {종목코드} (스크린={emergencyScr} 원주문={emergencyOrd})");
                    axKHOpenAPI1.SendOrder("매수취소;비상정지", emergencyScr, AccountList.Text, 3, 종목코드, 0, 0, "03", emergencyOrd);
                }
                m_PendingBuyOrders.Clear();
            }
            catch (Exception ex) { LogMessage($"매수취소 오류: {ex.Message}"); }

            // 미체결 매도 주문 일괄 취소
            try
            {
                foreach (var kvp in m_PendingSellOrders)
                {
                    string 종목코드 = kvp.Key;
                    LogMessage($"[비상정지] 매도취소 시도: {종목코드}");
                    axKHOpenAPI1.SendOrder("매도취소;비상정지", 스크린.매도주문, AccountList.Text, 4, 종목코드, 0, 0, "00", "");
                }
                m_PendingSellOrders.Clear();
            }
            catch (Exception ex) { LogMessage($"매도취소 오류: {ex.Message}"); }

            LogMessage("모든 자동매매 모니터 중지 + 미체결 취소 시도 완료");
            MessageBox.Show("비상 정지가 발동되었습니다.\n모든 자동매매가 중지되고 미체결 주문 취소를 시도했습니다.",
                "비상 정지", MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }

        // ── 보유종목 그리드 컨텍스트 메뉴 핸들러 ──

        private DBInfo GetSelectedHolding()
        {
            if (holdJongmokGridView.CurrentRow == null || holdJongmokGridView.CurrentRow.Index < 0
                || holdJongmokGridView.CurrentRow.Index >= m_HoldingDbInfoList.Count)
                return null;
            return m_HoldingDbInfoList[holdJongmokGridView.CurrentRow.Index];
        }

        private void HoldGrid_SellAll_Click(object sender, EventArgs e)
        {
            var holding = GetSelectedHolding();
            if (holding == null) return;

            if (holding.보유수량 <= 0)
            {
                MessageBox.Show("보유수량이 0입니다.", "매도 불가", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            // 계좌 실제 잔고 확인 (DB와 불일치 방지)
            int 실제수량 = holding.보유수량;
            var accountHolding = m_HoldJongmokList.FirstOrDefault(h => h.종목코드 == holding.종목코드);
            if (accountHolding != null && int.TryParse(accountHolding.잔고수량, out int 계좌잔고) && 계좌잔고 > 0)
            {
                if (계좌잔고 != holding.보유수량)
                    LogMessage($"[잔고차이] {holding.종목명} DB={holding.보유수량} 계좌={계좌잔고} → 계좌 기준 매도");
                실제수량 = 계좌잔고;
            }

            string priceStr = axKHOpenAPI1.GetMasterLastPrice(holding.종목코드).Replace("+", "").Replace("-", "").Trim();
            int.TryParse(priceStr, out int 현재가);
            if (현재가 <= 0) 현재가 = holding.현재가;

            if (MessageBox.Show(
                $"[전량 시장가 매도]\n종목: {holding.종목명} ({holding.종목코드})\n수량: {실제수량}주\n현재가: {현재가:N0}원 (시장가 주문)\n\n주문하시겠습니까?",
                "전량 매도 확인", MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes)
                return;

            // 기존 pending 매도 제거 (이전 미체결 주문과 충돌 방지)
            m_PendingSellOrders.TryRemove(holding.종목코드, out _);

            string rqName = $"매도주문;수동;수동전량매도";
            int ret = axKHOpenAPI1.SendOrder(rqName, 스크린.매도주문, AccountList.Text, 2, holding.종목코드, 실제수량, 0, "03", "");
            if (ret != 0)
            {
                LogMessage($"[수동매도 실패] {holding.종목명}({holding.종목코드}) SendOrder 반환={ret}");
                MessageBox.Show($"매도 주문 실패 (에러코드: {ret})\n\n이전 미체결 주문이 남아있으면\n키움HTS에서 먼저 취소해주세요.", "주문 실패", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }
            m_PendingSellOrders[holding.종목코드] = rqName;
            LogMessage($"[수동매도] {holding.종목명}({holding.종목코드}) 전량 {실제수량}주 (시장가)");
        }

        private void HoldGrid_SellPartial_Click(object sender, EventArgs e)
        {
            var holding = GetSelectedHolding();
            if (holding == null) return;

            // 계좌 실제 잔고 확인
            int 실제수량 = holding.보유수량;
            var accountHolding = m_HoldJongmokList.FirstOrDefault(h => h.종목코드 == holding.종목코드);
            if (accountHolding != null && int.TryParse(accountHolding.잔고수량, out int 계좌잔고) && 계좌잔고 > 0)
                실제수량 = 계좌잔고;

            if (실제수량 <= 0)
            {
                MessageBox.Show("보유수량이 0입니다.", "매도 불가", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            string input = Microsoft.VisualBasic.Interaction.InputBox(
                $"{holding.종목명} ({holding.종목코드})\n보유: {실제수량}주\n\n매도할 수량을 입력하세요:",
                "수량 지정 매도", 실제수량.ToString());
            if (string.IsNullOrEmpty(input)) return;
            if (!int.TryParse(input, out int 매도수량) || 매도수량 <= 0 || 매도수량 > 실제수량)
            {
                MessageBox.Show($"유효한 수량을 입력해주세요. (1~{실제수량})", "입력 오류", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            string priceStr = axKHOpenAPI1.GetMasterLastPrice(holding.종목코드).Replace("+", "").Replace("-", "").Trim();
            int.TryParse(priceStr, out int 현재가);
            if (현재가 <= 0) 현재가 = holding.현재가;

            if (MessageBox.Show(
                $"[부분 시장가 매도]\n종목: {holding.종목명} ({holding.종목코드})\n수량: {매도수량}주 / 보유 {holding.보유수량}주\n현재가: {현재가:N0}원 (시장가 주문)\n\n주문하시겠습니까?",
                "부분 매도 확인", MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes)
                return;

            m_PendingSellOrders.TryRemove(holding.종목코드, out _);

            string rqName = $"매도주문;수동;부분매도";
            int ret = axKHOpenAPI1.SendOrder(rqName, 스크린.매도주문, AccountList.Text, 2, holding.종목코드, 매도수량, 0, "03", "");
            if (ret != 0)
            {
                LogMessage($"[수동매도 실패] {holding.종목명}({holding.종목코드}) SendOrder 반환={ret}");
                MessageBox.Show($"매도 주문 실패 (에러코드: {ret})\n\n이전 미체결 주문이 남아있으면\n키움HTS에서 먼저 취소해주세요.", "주문 실패", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }
            m_PendingSellOrders[holding.종목코드] = rqName;
            LogMessage($"[수동매도] {holding.종목명}({holding.종목코드}) {매도수량}주 (시장가)");
        }

        private void HoldGrid_SellLimit_Click(object sender, EventArgs e)
        {
            var holding = GetSelectedHolding();
            if (holding == null) return;

            if (holding.보유수량 <= 0)
            {
                MessageBox.Show("보유수량이 0입니다.", "매도 불가", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            string priceStr = axKHOpenAPI1.GetMasterLastPrice(holding.종목코드).Replace("+", "").Replace("-", "").Trim();
            int.TryParse(priceStr, out int 현재가);
            if (현재가 <= 0) 현재가 = holding.현재가;

            string inputQty = Microsoft.VisualBasic.Interaction.InputBox(
                $"{holding.종목명} ({holding.종목코드})\n보유: {holding.보유수량}주 | 현재가: {현재가:N0}원\n\n매도 수량:",
                "지정가 매도 - 수량", holding.보유수량.ToString());
            if (string.IsNullOrEmpty(inputQty)) return;
            if (!int.TryParse(inputQty, out int 매도수량) || 매도수량 <= 0 || 매도수량 > holding.보유수량)
            {
                MessageBox.Show($"유효한 수량을 입력해주세요. (1~{holding.보유수량})", "입력 오류", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            string inputPrice = Microsoft.VisualBasic.Interaction.InputBox(
                $"{holding.종목명} ({holding.종목코드})\n현재가: {현재가:N0}원\n\n매도 가격:",
                "지정가 매도 - 가격", 현재가.ToString());
            if (string.IsNullOrEmpty(inputPrice)) return;
            if (!int.TryParse(inputPrice, out int 매도가) || 매도가 <= 0)
            {
                MessageBox.Show("유효한 가격을 입력해주세요.", "입력 오류", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            if (MessageBox.Show(
                $"[지정가 매도]\n종목: {holding.종목명} ({holding.종목코드})\n수량: {매도수량}주\n가격: {매도가:N0}원\n\n주문하시겠습니까?",
                "지정가 매도 확인", MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes)
                return;

            m_PendingSellOrders.TryRemove(holding.종목코드, out _);

            string rqName = $"매도주문;수동;지정가";
            int ret = axKHOpenAPI1.SendOrder(rqName, 스크린.매도주문, AccountList.Text, 2, holding.종목코드, 매도수량, 매도가, "00", "");
            if (ret != 0)
            {
                LogMessage($"[수동매도 실패] {holding.종목명}({holding.종목코드}) SendOrder 반환={ret}");
                MessageBox.Show($"매도 주문 실패 (에러코드: {ret})", "주문 실패", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }
            m_PendingSellOrders[holding.종목코드] = rqName;
            LogMessage($"[수동매도] {holding.종목명}({holding.종목코드}) {매도수량}주 @ {매도가:N0}원 (지정가)");
        }

        private void HoldGrid_ViewChart_Click(object sender, EventArgs e)
        {
            var holding = GetSelectedHolding();
            if (holding != null && !string.IsNullOrEmpty(holding.종목코드))
                requestDailyChart(holding.종목코드);
        }

        private void HoldGrid_CopyCode_Click(object sender, EventArgs e)
        {
            var holding = GetSelectedHolding();
            if (holding != null && !string.IsNullOrEmpty(holding.종목코드))
                Clipboard.SetText(holding.종목코드);
        }

        // ── 조건 편입 그리드 컨텍스트 메뉴 핸들러 ──

        private void CondGrid_ViewChart_Click(object sender, EventArgs e)
        {
            if (conditionFilteredGridView.CurrentRow == null) return;
            string code = conditionFilteredGridView.CurrentRow.Cells["종목코드"].Value?.ToString() ?? "";
            if (!string.IsNullOrEmpty(code)) requestDailyChart(code);
        }

        private void CondGrid_ManualBuy_Click(object sender, EventArgs e)
        {
            if (conditionFilteredGridView.CurrentRow == null) return;
            string code = conditionFilteredGridView.CurrentRow.Cells["종목코드"].Value?.ToString() ?? "";
            string name = conditionFilteredGridView.CurrentRow.Cells["종목명"].Value?.ToString() ?? "";
            if (string.IsNullOrEmpty(code)) return;

            string priceStr = axKHOpenAPI1.GetMasterLastPrice(code).Replace("+", "").Replace("-", "").Trim();
            int.TryParse(priceStr, out int 현재가);
            if (현재가 <= 0) return;

            int 매수가 = _sellStrategyManager.CalculateBuyPrice(현재가);
            int 매수수량 = _strategyConfig.종목당최대투자금 / 매수가;
            if (매수수량 <= 0)
            {
                MessageBox.Show($"투자금({_strategyConfig.종목당최대투자금:N0}) 대비 가격({매수가:N0}) 초과", "매수 불가", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            string inputQty = Microsoft.VisualBasic.Interaction.InputBox(
                $"{name} ({code})\n현재가: {현재가:N0}원 | 매수가: {매수가:N0}원\n\n매수 수량:",
                "수동 매수 - 수량", 매수수량.ToString());
            if (string.IsNullOrEmpty(inputQty)) return;
            if (!int.TryParse(inputQty, out int 최종수량) || 최종수량 <= 0)
            {
                MessageBox.Show("유효한 수량을 입력해주세요.", "입력 오류", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            if (MessageBox.Show(
                $"[수동 매수]\n종목: {name} ({code})\n수량: {최종수량}주\n매수가: {매수가:N0}원\n총액: {(long)매수가 * 최종수량:N0}원\n\n주문하시겠습니까?",
                "수동 매수 확인", MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes)
                return;

            m_PendingBuyOrders[code] = "수동매수";
            axKHOpenAPI1.SendOrder("매수주문;수동", 스크린.매수주문, AccountList.Text, 1, code, 최종수량, 매수가, "00", "");
            LogMessage($"[수동매수] {name}({code}) {최종수량}주 @ {매수가:N0}원");
        }

        private void CondGrid_CopyCode_Click(object sender, EventArgs e)
        {
            if (conditionFilteredGridView.CurrentRow == null) return;
            string code = conditionFilteredGridView.CurrentRow.Cells["종목코드"].Value?.ToString() ?? "";
            if (!string.IsNullOrEmpty(code)) Clipboard.SetText(code);
        }

        /// <summary>
        /// 조건식 편입 시 자동매수 실행
        /// </summary>
        private void TryAutoBuy(string 종목코드, string 종목명, string 조건명)
        {
            // 0. 장중이 아니면 매수 차단
            if (!m_IsMarketOpen)
            {
                LogMessage($"[매수스킵] {종목명}({종목코드}) — 장 운영시간 아님");
                return;
            }

            // 0-1. ETF 종목 매수 차단
            try
            {
                string stockState = axKHOpenAPI1.GetMasterStockState(종목코드);
                if (!string.IsNullOrEmpty(stockState) && stockState.Contains("ETF"))
                {
                    LogMessage($"[매수스킵] {종목명}({종목코드}) — ETF 종목 제외");
                    return;
                }
            }
            catch { }

            // 0-2. 금리/채권/레버리지/인버스 등 비주식 종목 필터
            {
                string[] 제외키워드 = { "금리", "채권", "국채", "회사채", "레버리지", "인버스", "선물", "옵션",
                                       "머니마켓", "단기자금", "CD금리", "KORIBOR", "통안채", "국고채",
                                       "하이일드", "크레딧", "BOND", "TREASURY", "금현물" };
                string nameUpper = 종목명.ToUpper();
                foreach (var kw in 제외키워드)
                {
                    if (nameUpper.Contains(kw.ToUpper()))
                    {
                        LogMessage($"[매수스킵] {종목명}({종목코드}) — 비주식 종목 제외 ({kw})");
                        return;
                    }
                }

                // ETF 브랜드명으로 시작하는 종목 제외 (GetMasterStockState는 ETF 식별 불가)
                string[] ETF브랜드 = { "KODEX", "TIGER", "RISE", "HANARO", "ACE ", "SOL ", "PLUS ",
                                       "1Q ", "KIWOOM", "ARIRANG", "TIMEFOLIO", "TIME Korea", "KB " };
                foreach (var brand in ETF브랜드)
                {
                    if (nameUpper.StartsWith(brand.ToUpper()))
                    {
                        LogMessage($"[매수스킵] {종목명}({종목코드}) — ETF 제외 ({brand.Trim()})");
                        return;
                    }
                }
            }

            // 1. 이미 보유 중인 종목 재매수 금지
            if (m_HoldingDbInfoList.Any(h => h.종목코드 == 종목코드))
            {
                LogMessage($"[매수스킵] {종목명}({종목코드}) — 이미 보유 중");
                return;
            }

            // 2. 재매수금지기간 체크 (최근 매도 후 N일 이내 재매수 차단)
            if (_strategyConfig.재매수금지기간 > 0)
            {
                string today = DateTime.Now.ToString("yyyyMMdd");
                var recentSold = m_HistoryDbInfoList.FirstOrDefault(h =>
                    h.종목코드 == 종목코드 && !string.IsNullOrEmpty(h.전량매도일));
                if (recentSold != null)
                {
                    try
                    {
                        var 매도일 = DateTime.ParseExact(recentSold.전량매도일, "yyyyMMdd", null);
                        int 경과일 = (DateTime.Now.Date - 매도일.Date).Days;
                        if (경과일 < _strategyConfig.재매수금지기간)
                        {
                            LogMessage($"[매수스킵] {종목명}({종목코드}) — 재매수금지 ({경과일}/{_strategyConfig.재매수금지기간}일)");
                            return;
                        }
                    }
                    catch { }
                }
            }

            // 3. 코스피 지수 필터 (지수≥MA60, 전일대비 -4% 이상)
            // 3a. 실시간 지수 감시 (장중 실시간 데이터 우선)
            if (m_JisuBelowMA60 && m_RealtimeJisuPrice > 0)
            {
                LogMessage($"[매수스킵] {종목명}({종목코드}) — 실시간 코스피({m_RealtimeJisuPrice}) MA60 하회 중");
                return;
            }

            // 3b. 일봉 기반 필터 (실시간 데이터 없을 때 fallback)
            lock (m_MonitoringLock)
            {
                if (m_conditionCheck.TryGetValue("지수", out var jisuCheck) &&
                    jisuCheck.priceInfoList.Count >= 2 &&
                    jisuCheck.이동평균.TryGetValue("ma60", out var ma60List) &&
                    ma60List.Count > 0)
                {
                    int jisuClose = jisuCheck.priceInfoList[0].종가;
                    int jisuMA60 = ma60List[0];
                    int jisuPrevClose = jisuCheck.priceInfoList[1].종가;

                    if (jisuClose < jisuMA60)
                    {
                        LogMessage($"[매수스킵] {종목명}({종목코드}) — 코스피({jisuClose}) < MA60({jisuMA60})");
                        return;
                    }
                    if (jisuClose < (int)(jisuPrevClose * 0.96))
                    {
                        LogMessage($"[매수스킵] {종목명}({종목코드}) — 코스피 전일대비 -4%↓ ({jisuClose} vs 전일{jisuPrevClose})");
                        return;
                    }
                }
                else
                {
                    LogMessage($"[매수스킵] {종목명}({종목코드}) — 코스피 지수 데이터 미수신");
                    return;
                }
            }

            // 4. 최대 동시보유 종목수 체크
            if (m_HoldingDbInfoList.Count >= _strategyConfig.최대보유종목수)
            {
                LogMessage($"[매수스킵] {종목명}({종목코드}) — 최대보유 {_strategyConfig.최대보유종목수}종목 도달");
                return;
            }

            // 5. 이미 매수 주문 진행 중인 종목 중복 방지
            if (m_PendingBuyOrders.ContainsKey(종목코드))
            {
                LogMessage($"[매수스킵] {종목명}({종목코드}) — 매수 주문 진행 중");
                return;
            }

            // 6. 매수 가격/수량 계산
            // 현재가 조회 (GetMasterLastPrice)
            string priceStr = axKHOpenAPI1.GetMasterLastPrice(종목코드).Replace("+", "").Replace("-", "").Trim();
            if (!int.TryParse(priceStr, out int 현재가) || 현재가 <= 0)
            {
                LogMessage($"[매수스킵] {종목명}({종목코드}) — 현재가 조회 실패");
                return;
            }

            int 매수가격 = _sellStrategyManager.CalculateBuyPrice(현재가);
            if (매수가격 <= 0) 매수가격 = 현재가;

            int 매수수량 = _strategyConfig.종목당최대투자금 / 매수가격;
            if (매수수량 <= 0)
            {
                LogMessage($"[매수스킵] {종목명}({종목코드}) — 투자금({_strategyConfig.종목당최대투자금:N0}) 대비 가격({매수가격:N0}) 초과");
                return;
            }

            // 예수금 확인 (실제 주문가능금액 대비 주문금액 체크)
            long 주문금액 = (long)매수가격 * 매수수량;
            if (주문금액 > m_availableBalance)
            {
                // 미체결 매수 주문 중 가장 오래된 것을 취소하여 자금 확보 시도
                if (m_BuyOrderTime.Count > 0)
                {
                    var oldest = m_BuyOrderTime.OrderBy(x => x.Value).First();
                    string cancelCode = oldest.Key;
                    m_PendingBuyOrders.TryRemove(cancelCode, out string cancelCondition);
                    m_BuyOrderTime.TryRemove(cancelCode, out _);
                    string cancelName = axKHOpenAPI1.GetMasterCodeName(cancelCode);
                    string cancelScr2 = m_BuyOrderScreen.TryGetValue(cancelCode, out string scr2) ? scr2 : 스크린.매수주문;
                    string cancelOrd2 = m_BuyOrderNo.TryGetValue(cancelCode, out string ord2)     ? ord2  : "";
                    LogMessage($"[미체결취소] {cancelName}({cancelCode}) — 신규 매수({종목명}) 위해 기존 미체결 취소 (스크린={cancelScr2})");
                    axKHOpenAPI1.SendOrder("매수취소;자금확보", cancelScr2, AccountList.Text, 3, cancelCode, 0, 0, "03", cancelOrd2);
                    m_BuyOrderScreen.TryRemove(cancelCode, out _);
                    m_BuyOrderNo.TryRemove(cancelCode, out _);
                    // 취소 후 즉시 재시도하지 않음 — 다음 편입 신호에서 매수 가능
                }
                LogMessage($"[매수스킵] {종목명}({종목코드}) — 잔고부족 (주문={주문금액:N0} vs 주문가능={m_availableBalance:N0})");
                return;
            }

            // 매수 주문 후 주문가능금액 선차감 (잔고 갱신 전 중복매수 방지)
            m_availableBalance -= 주문금액;
            if (m_availableBalance < 0) m_availableBalance = 0;

            // 7. 매수 주문 실행 (시장가 "03" — 즉시 체결)
            // 화면번호를 주문마다 동적 할당 → 동일 화면번호 재사용으로 인한 충돌 방지
            int scrIdx = (System.Threading.Interlocked.Increment(ref m_buyScreenIdx) % 90) + 10;
            string buyScreenNo = (5000 + scrIdx).ToString("D4");

            string rqName = $"매수주문;{조건명};{종목코드}";
            LogMessage($"[자동매수] {종목명}({종목코드}) {매수수량}주 시장가 | 조건식: {조건명} | 스크린={buyScreenNo} 계좌={AccountList.Text}");

            // pending 매수 등록 (중복 주문 방지) + 화면번호·주문금액 기록
            m_PendingBuyOrders[종목코드] = 조건명;
            m_BuyOrderTime[종목코드] = DateTime.Now;
            m_BuyOrderScreen[종목코드] = buyScreenNo;
            m_BuyOrderAmount[종목코드] = 주문금액;

            int sendRet = axKHOpenAPI1.SendOrder(rqName, buyScreenNo, AccountList.Text, 1,
                                                 종목코드, 매수수량, 0, "03", "");
            if (sendRet != 0)
            {
                LogMessage($"[매수실패] SendOrder 오류 ret={sendRet}: {종목명}({종목코드}) {매수수량}주 스크린={buyScreenNo}");
                // 선차감 잔고 복원 + pending 제거
                m_availableBalance += 주문금액;
                m_PendingBuyOrders.TryRemove(종목코드, out _);
                m_BuyOrderTime.TryRemove(종목코드, out _);
                m_BuyOrderScreen.TryRemove(종목코드, out _);
                m_BuyOrderAmount.TryRemove(종목코드, out _);
            }
        }

        /// <summary>
        /// 보유종목 일봉 데이터 순차 조회 (50일 최대거래량 캐싱 포함)
        /// </summary>
        private async Task FetchHoldingsDailyData(CancellationToken token)
        {
            // 보유종목 코드 큐에 적재
            foreach (var h in m_HoldingDbInfoList)
            {
                if (!string.IsNullOrEmpty(h.종목코드))
                    m_holdingDailyQueue.Enqueue(h.종목코드);
            }

            LogMessage($"보유종목 일봉 데이터 조회 시작: {m_holdingDailyQueue.Count}건");

            while (!token.IsCancellationRequested && m_holdingDailyQueue.TryDequeue(out string 종목코드))
            {
                try
                {
                    this.Invoke((Action)(() =>
                    {
                        string 종목명 = axKHOpenAPI1.GetMasterCodeName(종목코드);
                        axKHOpenAPI1.SetInputValue("종목코드", 종목코드);
                        axKHOpenAPI1.SetInputValue("기준일자", DateTime.Now.ToString("yyyyMMdd"));
                        axKHOpenAPI1.SetInputValue("수정주가구분", "1");
                        axKHOpenAPI1.CommRqData("보유종목일봉조회;" + 종목명 + ";" + 종목코드, "OPT10081", 0, 스크린.종목일봉정보);
                    }));
                }
                catch (Exception ex) { Core.LogManager.Log($"일봉 조회 오류: {ex.Message}"); }

                // TR 요청 속도 제한 (3.6초 간격)
                try { await Task.Delay(3600, token); }
                catch (OperationCanceledException) { break; }
            }

            LogMessage($"보유종목 일봉 데이터 조회 완료 (캐싱 {m_Max50DayVolume.Count}건)");
        }

        /*
         DB 관련 함수 END
         */

        private void showChart(object sender, EventArgs e)
        {
            String stockCode = "";
            if (sender.Equals(conditionFilteredGridView))
            {
                if (conditionFilteredGridView.CurrentRow == null) return;
                stockCode = conditionFilteredGridView.CurrentRow.Cells["종목코드"].Value?.ToString() ?? "";
            }

            if (!String.IsNullOrEmpty(stockCode))
            {
                requestDailyChart(stockCode);
            }
        }

        private void onReceiveRealCondition(object sender, _DKHOpenAPIEvents_OnReceiveRealConditionEvent e)
        {
            LogMessage("onReceiveRealCondition");
            String _종목코드 = GetStockCode(e.sTrCode);
            String _종목명 = axKHOpenAPI1.GetMasterCodeName(_종목코드);
            String _조건명 = e.strConditionName;
            String _조건명인덱스 = e.strConditionIndex;
            if (!int.TryParse(_조건명인덱스, out int index) || index < 0 || index >= m_ConditionList.Count)
            {
                LogMessage($"잘못된 조건식 인덱스: {_조건명인덱스}");
                return;
            }
            if (e.strType.Equals("I"))  //종목편입 
            {
                LogMessage("편입 " + _조건명 + " " + _종목코드 + " " + _종목명);

                bool already = false;

                lock (m_ConditionLock)
                {
                    foreach (StockItemInfo stockItem in m_ConditionList[index].stockItemList)
                    {
                        if (stockItem.종목코드 == _종목코드)
                        {
                            LogMessage("이미 있음 : " + _조건명 + " " + _종목코드 + " " + _종목명);
                            already = true;
                            break;
                        }
                    }

                    if (already == false)
                    {
                        m_ConditionList[index].stockItemList.Add(new StockItemInfo()
                        {
                            조건명 = _조건명,
                            종목명 = _종목명,
                            종목코드 = _종목코드,
                            현재가 = "",
                            전일대비 = "",
                            등락률 = "",
                            거래량 = "",
                            시가 = "",
                            고가 = "",
                            저가 = ""
                        });

                        LogMessage("편입 추가 완료");

                        // 자동매수 실행
                        TryAutoBuy(_종목코드, _종목명, _조건명);
                    }
                }
            }
            else if (e.strType.Equals("D")) //종목이탈 
            {
                LogMessage("편출 " + _조건명 + " " + _종목코드 + " " + _종목명);

                lock (m_ConditionLock)
                {
                    m_ConditionList[index].stockItemList.RemoveAll(p => p.종목코드 == _종목코드);

                    bool isDelete = false;

                    Action removeAction = () =>
                    {
                    for (int i = conditionFilteredGridView.Rows.Count - 1; i >= 0; i--)
                    {
                        DataGridViewRow row = conditionFilteredGridView.Rows[i];
                        if (row.IsNewRow) continue;

                        string _조건명2 = row.Cells["조건명"].Value?.ToString();
                        string _종목코드2 = row.Cells["종목코드"].Value?.ToString();

                        if (_조건명 == _조건명2 && _종목코드 == _종목코드2)
                        {
                            LogMessage("편출 종목 삭제 완료 " + _종목명);
                            conditionFilteredGridView.Rows.RemoveAt(i);
                            isDelete = true;
                            break;
                        }
                    }
                    };

                    if (conditionFilteredGridView.InvokeRequired)
                        conditionFilteredGridView.Invoke(removeAction);
                    else
                        removeAction();

                    if (isDelete == false)
                        LogMessage("편출 종목 이미 삭제됨");
                }
            }
        }

        private async void atStopButton(object sender, EventArgs e)
        {
            int checkCount = conditionCheckedListBox.CheckedItems.Count;

            if (checkCount > 0)
            {
                LogMessage("자동 매매 종료!!");

                m_ConditionCts?.Cancel();

                ATStopButton.Visible = false;

                CheckedListBox.CheckedIndexCollection checkedIndices = conditionCheckedListBox.CheckedIndices;

                foreach (int index in checkedIndices)
                {
                    axKHOpenAPI1.SendConditionStop(
                                                   스크린.실시간조건식,//GetScrNum(),
                                                   m_ConditionList[index].조건식이름,
                                                   m_ConditionList[index].조건식번호
                                                   );

                    m_ConditionList[index].실시간등록여부 = false;

                    m_ConditionList[index].stockItemList.Clear();

                    await Task.Delay(500);
                }

                conditionCheckedListBox.Enabled = true;

                ATStartButton.Visible = true;
                ATStartButton.BringToFront();
            }
        }

        private void Form1_FormClosing(object sender, FormClosingEventArgs e)
        {
            // 타이머 중지
            _balanceRefreshTimer?.Stop();
            _balanceRefreshTimer?.Dispose();
            _holdingUIRefreshTimer?.Stop();
            _holdingUIRefreshTimer?.Dispose();

            // CancellationToken 취소
            m_ConditionCts?.Cancel();
            m_ConditionCts?.Dispose();
            m_MonitoringCts?.Cancel();
            m_MonitoringCts?.Dispose();
            StopSellMonitor();

            // 실시간 조건식 중지
            try
            {
                for (int i = 0; i < m_ConditionList.Count; i++)
                {
                    if (m_ConditionList[i].실시간등록여부)
                    {
                        axKHOpenAPI1.SendConditionStop(스크린.실시간조건식, m_ConditionList[i].조건식이름, m_ConditionList[i].조건식번호);
                    }
                }
            }
            catch { }

            // DB 최종 저장
            try
            {
                _dbManager.UpdateAll(m_HoldingDbInfoList);
            }
            catch { }

            // 설정 저장
            try { _strategyConfig.Save(); } catch { }
        }

        private async void atStartButton(object sender, EventArgs e)
        {
            int checkCount = conditionCheckedListBox.CheckedItems.Count;

            if (checkCount > 0)
            {
                ATStartButton.Visible = false;

                conditionFilteredGridView.Rows.Clear();
                conditionFilteredGridView.Refresh();

                conditionCheckedListBox.Enabled = false;

                CheckedListBox.CheckedIndexCollection checkedIndices = conditionCheckedListBox.CheckedIndices;

                foreach (int index in checkedIndices)
                {
                    int retryCount = 0;
                    const int maxRetry = 5;
                    bool registered = false;

                    while (retryCount < maxRetry)
                    {
                        int result = axKHOpenAPI1.SendCondition(
                        스크린.실시간조건식,
                        m_ConditionList[index].조건식이름,
                        m_ConditionList[index].조건식번호,
                        1
                        );

                        if (result > 0)
                        {
                            LogMessage("자동 매매 시작!! " + m_ConditionList[index].조건식이름);
                            m_ConditionList[index].stockItemList = new List<StockItemInfo>();
                            m_ConditionList[index].실시간등록여부 = true;
                            registered = true;
                            break;
                        }
                        else
                        {
                            retryCount++;
                            LogMessage($"자동 매매 조건검색 대기!! ({retryCount}/{maxRetry})");
                            await Task.Delay(10000);
                        }
                    }

                    if (!registered)
                        LogMessage($"[경고] 조건식 등록 실패: {m_ConditionList[index].조건식이름} — {maxRetry}회 재시도 초과");

                    await Task.Delay(1000);
                }

                LogMessage("자동 매매 시작!!");

                // 장중 재시작 시 m_IsMarketOpen 복원 (장구분 "3"은 09:00에 한 번만 수신)
                var now = DateTime.Now.TimeOfDay;
                if (!m_IsMarketOpen && now >= new TimeSpan(9, 0, 0) && now < new TimeSpan(15, 30, 0))
                {
                    m_IsMarketOpen = true;
                    LogMessage("[장중 복원] 자동매매 재시작 — m_IsMarketOpen = true");
                    if (!m_SellMonitorRunning) StartSellMonitor();
                }

                ATStopButton.Visible = true;
                ATStopButton.BringToFront();

                // CancellationToken 기반 비동기 실시간 조건식 업데이트 시작
                m_ConditionCts = new CancellationTokenSource();
                _ = Task.Run(() => realConditionUpdater(m_ConditionCts.Token));

            }
            else
            {
                LogMessage("체크된 조건식이 없습니다.");
            }
        }

        // UI 스레드에서 안전하게 딜레이 (busy-wait 대체)
        private async Task DelayAsync(int ms, CancellationToken token = default)
        {
            await Task.Delay(ms, token);
        }


        // 실시간 조건검색 (CancellationToken 기반)
        public async Task realConditionUpdater(CancellationToken token)
        {
            while (!token.IsCancellationRequested)
            {
                foreach (ConditionInfo condition in m_ConditionList)
                {
                    if (token.IsCancellationRequested) break;

                    if (condition.실시간등록여부 == false)
                        continue;

                    //
                    List<string> codeListAll = new List<string>();
                    lock (m_ConditionLock)
                    {
                        foreach (StockItemInfo stockInfo in condition.stockItemList)
                        {
                            codeListAll.Add(stockInfo.종목코드);

                            if (!m_monitoring.ContainsKey(stockInfo.종목코드))
                            {
                                m_monitoring.Add(stockInfo.종목코드, stockInfo.종목명);
                                m_monitoringQueue.Enqueue(stockInfo.종목코드);
                            }
                        }
                    }

                    // CommKwRqData 최대 100종목 제한 → 배치 분할
                    const int batchSize = 100;
                    for (int batchStart = 0; batchStart < codeListAll.Count; batchStart += batchSize)
                    {
                        if (token.IsCancellationRequested) break;

                        var batch = codeListAll.Skip(batchStart).Take(batchSize).ToList();
                        string codeList = string.Join(";", batch) + ";";

                        this.Invoke((Action)(() =>
                        {
                            axKHOpenAPI1.CommKwRqData(codeList, 0, batch.Count, 0,
                            "조건식종목정보;" + condition.조건식이름 + ";" + condition.조건식번호.ToString(), 스크린.조건종목정보);
                        }));

                        await DelayAsync(7000, token);
                    }
                }
            }
        }

        private async Task realMonitoringUpdater(CancellationToken token)
        {
            string _종목코드;
            while (!token.IsCancellationRequested)
            {
                if (m_monitoringQueue.TryDequeue(out _종목코드))
                {
                    this.Invoke((Action)(() =>
                    {
                        axKHOpenAPI1.SetInputValue("종목코드", _종목코드);
                        axKHOpenAPI1.SetInputValue("기준일자", DateTime.Now.ToString("yyyyMMdd"));
                        axKHOpenAPI1.SetInputValue("수정주가구분", "1");

                        string _종목명 = axKHOpenAPI1.GetMasterCodeName(_종목코드);

                        axKHOpenAPI1.CommRqData("종목일봉차트조회;" + _종목명, "OPT10081", 0, 스크린.종목일봉정보);
                    }));
                }

                await DelayAsync(5000, token);
            }
        }

        private void requestDailyChart(string stockCode)
        {
            axKHOpenAPI1.SetInputValue("종목코드", stockCode);
            axKHOpenAPI1.SetInputValue("기준일자", DateTime.Now.ToString("yyyyMMdd"));
            axKHOpenAPI1.SetInputValue("수정주가구분", "1");

            int nRet = axKHOpenAPI1.CommRqData("주식일봉차트조회", "OPT10081", 0, 스크린.종목일봉정보);

            if (nRet == 0)
                Console.WriteLine("주식 일봉 정보요청 성공");
            else
                Console.WriteLine("주식 일봉 정보요청 실패");
        }

        private void requestStockInfo(string stockCode)
        {
            axKHOpenAPI1.SetInputValue("종목코드", stockCode);

            int nRet = axKHOpenAPI1.CommRqData("JM_주식기본정보요청", "OPT10001", 0, GetScrNum());

            if (nRet == 0)
                Console.WriteLine("주식기본정보요청 성공");
            else
                Console.WriteLine("주식기본정보요청 실패");
        }

        private void chart1_MouseMove(object sender, MouseEventArgs e)
        {
            ChartArea priceChartArea = chart1.ChartAreas[0];
            ChartArea volumeChartArea = chart1.ChartAreas[1];
            Point mousePoint = new Point(e.X, e.Y);


            if (chart1.Height * 0.05 < e.Y && e.Y < chart1.Height * 0.57)
            {
                chartYLabel.Visible = true;
                priceChartArea.CursorX.SetCursorPixelPosition(mousePoint, true);
                priceChartArea.CursorY.SetCursorPixelPosition(mousePoint, true);


                chartYLabel.Text = String.Format("{0:#,###}", priceChartArea.CursorY.Position);
                chartYLabel.Location = new Point((int)(chart1.Width * 0.9), e.Y - chartYLabel.Height / 2);
            }
            else if (chart1.Height * 0.605 < e.Y && e.Y < chart1.Height * 0.915)
            {
                chartYLabel.Visible = true;
                volumeChartArea.CursorX.SetCursorPixelPosition(mousePoint, true);
                volumeChartArea.CursorY.SetCursorPixelPosition(mousePoint, true);

                chartYLabel.Text = String.Format("{0:#,###}", volumeChartArea.CursorY.Position);
                chartYLabel.Location = new Point((int)(chart1.Width * 0.9), e.Y - chartYLabel.Height / 2);
            }
            else
            {
                chartYLabel.Visible = false;
            }
        }

        private void chart1_AxisViewChanged(object sender, ViewEventArgs e)
        {
            if (sender.Equals(chart1) && m_PriceInfoList != null)
            {
                try
                {
                    int startPosition = (int)e.Axis.ScaleView.ViewMinimum;
                    int endPosition = (int)e.Axis.ScaleView.ViewMaximum;

                    int max = 0;
                    int min = int.MaxValue;

                    int volumeMax = 0;
                    int volumeMin = int.MaxValue;

                    for (int i = startPosition - 1; i < endPosition; i++)
                    {
                        if (i >= m_PriceInfoList.Count)
                            break;
                        if (i < 0)
                            i = 0;

                        if (m_PriceInfoList[i].고가 > max)
                            max = m_PriceInfoList[i].고가;
                        if (m_PriceInfoList[i].저가 < min)
                            min = m_PriceInfoList[i].저가;

                        if (m_PriceInfoList[i].거래량 > volumeMax)
                            volumeMax = m_PriceInfoList[i].거래량;
                        if (m_PriceInfoList[i].거래량 < volumeMin)
                            volumeMin = m_PriceInfoList[i].거래량;
                    }

                    double offset = 0.2 * (max - min);
                    this.chart1.ChartAreas[0].AxisY.Maximum = max + offset;
                    this.chart1.ChartAreas[0].AxisY.Minimum = min - offset;

                    double volumeOffset = 0.2 * (volumeMax - volumeMin);
                    this.chart1.ChartAreas[1].AxisY.Maximum = volumeMax + volumeOffset;
                    if (volumeMin - volumeOffset > 0)
                        this.chart1.ChartAreas[1].AxisY.Minimum = volumeMin - volumeOffset;
                    else
                        this.chart1.ChartAreas[1].AxisY.Minimum = 0;
                }
                catch (Exception exception)
                {
                    Console.WriteLine(exception.Message.ToString());
                }
            }
        }

        private void onReceiveTrCondition(object sender, _DKHOpenAPIEvents_OnReceiveTrConditionEvent e)
        {
            LogMessage("onReceiveTrCondition");
            String codeList = e.strCodeList.Trim();
            String _조건명 = e.strConditionName;
            int _조건명인덱스 = e.nIndex;
            if (codeList.Length > 0)
                codeList = codeList.Remove(codeList.Length - 1);
            int nCodeCount = codeList.Trim().Split(';').Length;

            String[] codes = codeList.Split(';');

            if (e.nNext == 2)    //추가 종목 정보 
            {
                axKHOpenAPI1.SendCondition(
                       e.sScrNo,
                       e.strConditionName,
                       e.nIndex,
                       2
                       );
            }

            foreach (string code in codes)
            {
                if (code == "")
                    break;

                String _종목명 = axKHOpenAPI1.GetMasterCodeName(code);
                m_ConditionList[_조건명인덱스].stockItemList.Add(new StockItemInfo()
                {
                    조건명 = _조건명,
                    종목명 = _종목명,
                    종목코드 = code,
                    현재가 = "",
                    전일대비 = "",
                    등락률 = "",
                    거래량 = "",
                    시가 = "",
                    고가 = "",
                    저가 = ""
                });
            }

            //axKHOpenAPI1.CommKwRqData(codeList, 0, nCodeCount, 0, "조건식종목정보;" + 조건명 + ";" + 조건명인덱스.ToString(), GetScrNum());
        }

        private void conditionSelectedChanged(object sender, EventArgs e)
        {
            CheckedListBox checkedListBox = sender as CheckedListBox;
            if (checkedListBox.Equals(this.conditionCheckedListBox))
            {
                int index = checkedListBox.SelectedIndex;
                if (index < 0 || index >= m_ConditionList.Count)
                    return;

                if (checkedListBox.SelectedItem == null)
                    return;

                string item = checkedListBox.SelectedItem.ToString();

                // -> OnReceiveTrCondition
                int result = axKHOpenAPI1.SendCondition(
                GetScrNum(),
                m_ConditionList[index].조건식이름,
                m_ConditionList[index].조건식번호,
                0
                );

                if (result > 0)
                {
                    LogMessage("조건검색 성공");
                    m_ConditionList[index].stockItemList = new List<StockItemInfo>();

                    conditionFilteredGridView.Rows.Clear();
                    conditionFilteredGridView.Refresh();
                }
                else
                {
                    LogMessage("조건검색 실패 (1분 대기)");
                    conditionFilteredGridView.Rows.Clear();
                    List<StockItemInfo> stockItemInfo = m_ConditionList[index].stockItemList;
                    for (int i = 0; i < stockItemInfo.Count; i++)
                    {
                        conditionFilteredGridView.Rows.Add();
                        conditionFilteredGridView["조건명", conditionFilteredGridView.RowCount - 2].Value = stockItemInfo[i].조건명;
                        conditionFilteredGridView["종목명", conditionFilteredGridView.RowCount - 2].Value = stockItemInfo[i].종목명;
                        conditionFilteredGridView["종목코드", conditionFilteredGridView.RowCount - 2].Value = stockItemInfo[i].종목코드;
                        conditionFilteredGridView["현재가", conditionFilteredGridView.RowCount - 2].Value = stockItemInfo[i].현재가;
                        conditionFilteredGridView["전일대비", conditionFilteredGridView.RowCount - 2].Value = stockItemInfo[i].전일대비;
                        conditionFilteredGridView["등락률", conditionFilteredGridView.RowCount - 2].Value = stockItemInfo[i].등락률;
                        conditionFilteredGridView["거래량", conditionFilteredGridView.RowCount - 2].Value = stockItemInfo[i].거래량;
                        conditionFilteredGridView["시가", conditionFilteredGridView.RowCount - 2].Value = stockItemInfo[i].시가;
                        conditionFilteredGridView["고가", conditionFilteredGridView.RowCount - 2].Value = stockItemInfo[i].고가;
                        conditionFilteredGridView["저가", conditionFilteredGridView.RowCount - 2].Value = stockItemInfo[i].저가;
                    }
                }
            }
        }

        private void getConditionButton(object sender, EventArgs e)
        {
            axKHOpenAPI1.GetConditionLoad();
        }

        private void onReceiveConditionVer(object sender, _DKHOpenAPIEvents_OnReceiveConditionVerEvent e)
        {
            LogMessage("조건식 조회 완료");
            m_ConditionList = new List<ConditionInfo>();

            // 기존 항목 초기화 (재조회 시 중복 방지)
            conditionCheckedListBox.Items.Clear();

            String conditionNameList = axKHOpenAPI1.GetConditionNameList();
            String[] conditionNameArray = conditionNameList.Split(';');

            for (int i = 0; i < conditionNameArray.Length; i++)
            {
                String[] conditionInfo = conditionNameArray[i].Split('^');
                if (conditionInfo.Length == 2)
                {
                    m_ConditionList.Add(new ConditionInfo()
                    {
                        조건식번호 = int.Parse(conditionInfo[0].Trim()),
                        조건식이름 = conditionInfo[1].Trim()
                    });
                }
            }

            m_ConditionList = m_ConditionList.OrderBy(p => p.조건식번호).ToList();

            foreach (ConditionInfo condition in m_ConditionList)
            {
                conditionCheckedListBox.Items.Add(condition.조건식이름);
            }
        }

        private void HoldJongmokSyncWithDB()
        {
            foreach (HoldJongmok holdJongmok in m_HoldJongmokList)
            {
                if (!m_monitoring.ContainsKey(holdJongmok.종목코드))
                {
                    m_monitoring.Add(holdJongmok.종목코드, holdJongmok.종목명);
                    m_monitoringQueue.Enqueue(holdJongmok.종목코드);
                }


                int 계좌홀드잔고 = int.Parse(holdJongmok.잔고수량);
                int DB홀드잔고 = 0;
                int 매칭전략갯수 = 0;

                lock (m_HoldingLock)
                {
                    foreach (DBInfo holdingDB in m_HoldingDbInfoList)
                    {
                        if (holdingDB.종목명 == holdJongmok.종목명)
                        {
                            holdingDB.현재가 = int.Parse(holdJongmok.현재가);
                            holdingDB.평가금 = holdingDB.현재가 * holdingDB.보유수량;
                            holdingDB.현재수익금 = (holdingDB.현재가 - holdingDB.매수가격) * holdingDB.보유수량;
                            holdingDB.현재수익률 = holdingDB.매수가격 > 0
                                ? (float)Math.Round((float)(holdingDB.현재가 - holdingDB.매수가격) / holdingDB.매수가격 * 100, 2)
                                : 0f;

                            DB홀드잔고 += holdingDB.보유수량;
                            매칭전략갯수++;
                        }
                    }
                }

                if (계좌홀드잔고 == DB홀드잔고)
                {
                    if (매칭전략갯수 == 1)
                    {
                        //
                    }
                    else
                    {
                        //
                    }
                }
                else
                {
                    LogMessage("HoldJongmokSyncWithDB - 계좌/DB 잔고 불일치 " + holdJongmok.종목명 + "계좌 : " + 계좌홀드잔고 + " / DB : " + DB홀드잔고);

                    // 계좌 실제 잔고로 DB 보유수량 동기화
                    lock (m_HoldingLock)
                    {
                        if (매칭전략갯수 == 1)
                        {
                            var dbItem = m_HoldingDbInfoList.FirstOrDefault(h => h.종목명 == holdJongmok.종목명);
                            if (dbItem != null && 계좌홀드잔고 >= 0)
                            {
                                LogMessage($"[잔고동기화] {holdJongmok.종목명} DB 보유수량 {dbItem.보유수량} → {계좌홀드잔고}");
                                dbItem.보유수량 = 계좌홀드잔고;
                                if (계좌홀드잔고 <= 0)
                                {
                                    // 보유수량 0 → 히스토리로 이동 + 메모리 제거
                                    m_HoldingDbInfoList.Remove(dbItem);
                                    _dbManager.MoveToHistory(dbItem);
                                    LogMessage($"[잔고동기화] {dbItem.종목명}({dbItem.매수전략}) 보유수량 0 → 히스토리로 이동");
                                }
                                else
                                {
                                    updateHoldingDB(dbItem);
                                }
                            }
                        }
                        else if (매칭전략갯수 > 1)
                        {
                            // 다중 전략 보유: DB합계가 계좌잔고보다 많으면 초과분 항목 제거
                            // 계좌복원 항목을 우선 제거 대상으로 선정
                            int 초과수량 = DB홀드잔고 - 계좌홀드잔고;
                            var 매칭항목 = m_HoldingDbInfoList
                                .Where(h => h.종목명 == holdJongmok.종목명)
                                .OrderByDescending(h => h.매수전략 == "계좌복원") // 계좌복원 우선 제거
                                .ThenBy(h => h.보유수량) // 수량 적은 것 먼저
                                .ToList();

                            foreach (var item in 매칭항목)
                            {
                                if (초과수량 <= 0) break;

                                if (item.보유수량 <= 초과수량)
                                {
                                    // 이 항목 전체 제거
                                    초과수량 -= item.보유수량;
                                    LogMessage($"[잔고동기화] {item.종목명}({item.매수전략}) 보유수량 {item.보유수량} → 0 (중복 제거)");
                                    item.보유수량 = 0;
                                }
                                else
                                {
                                    // 부분 차감
                                    int 새수량 = item.보유수량 - 초과수량;
                                    LogMessage($"[잔고동기화] {item.종목명}({item.매수전략}) 보유수량 {item.보유수량} → {새수량} (다중전략)");
                                    item.보유수량 = 새수량;
                                    초과수량 = 0;
                                }
                            }

                            // 보유수량 0인 항목 DB에서 삭제 + 메모리에서 제거
                            var 제거대상 = m_HoldingDbInfoList
                                .Where(h => h.종목명 == holdJongmok.종목명 && h.보유수량 <= 0)
                                .ToList();
                            foreach (var item in 제거대상)
                            {
                                m_HoldingDbInfoList.Remove(item);
                                _dbManager.MoveToHistory(item);
                                LogMessage($"[중복제거] {item.종목명}({item.매수전략}) 보유수량 0 → 히스토리로 이동");
                            }

                            // 남은 항목 DB 업데이트
                            foreach (var item in m_HoldingDbInfoList.Where(h => h.종목명 == holdJongmok.종목명))
                            {
                                item.평가금 = item.현재가 * item.보유수량;
                                item.현재수익금 = (item.현재가 - item.매수가격) * item.보유수량;
                                updateHoldingDB(item);
                            }
                        }
                    }
                }
            }

            // ── 계좌에는 있지만 DB에 없는 종목 감지 → 자동 복원 ──
            foreach (HoldJongmok accountItem in m_HoldJongmokList)
            {
                if (string.IsNullOrEmpty(accountItem.종목코드)) continue;
                if (!int.TryParse(accountItem.잔고수량, out int 잔고) || 잔고 <= 0) continue;

                bool existsInDB;
                lock (m_HoldingLock)
                {
                    existsInDB = m_HoldingDbInfoList.Any(h =>
                        h.종목코드 == accountItem.종목코드 || h.종목명 == accountItem.종목명);
                }

                if (!existsInDB)
                {
                    // 매입단가 계산 (매입금액 / 수량)
                    int.TryParse(accountItem.현재가, out int 현재가);
                    double.TryParse(accountItem.매입금액, out double 매입금액raw);
                    int 매입단가 = 잔고 > 0 ? (int)(매입금액raw / 잔고) : 현재가;
                    if (매입단가 <= 0) 매입단가 = 현재가;

                    // 히스토리에서 최근 매수전략/매수일 조회 — 이전 매매 이력이 있으면 복원
                    string lastStrategy = _dbManager.FindLastStrategy(accountItem.종목코드);
                    string lastBuyDate  = _dbManager.FindLastBuyDate(accountItem.종목코드);
                    string 복원전략 = string.IsNullOrEmpty(lastStrategy) ? "계좌복원" : lastStrategy;

                    // 매수일: 히스토리에 있으면 해당 일자, 없으면 오늘
                    string 복원매수일 = !string.IsNullOrEmpty(lastBuyDate) ? lastBuyDate : DateTime.Now.ToString("yyyyMMdd");

                    // 보유일 계산
                    int 복원보유일 = 1;
                    if (DateTime.TryParseExact(복원매수일, "yyyyMMdd", null, System.Globalization.DateTimeStyles.None, out DateTime buyDt))
                        복원보유일 = Math.Max(1, (int)(DateTime.Now - buyDt).TotalDays + 1);

                    // 로스컷가격: 매입단가 기준 -R% (정상 매수완료와 동일 로직)
                    int 복원로스컷가격 = (int)(매입단가 * (1.0 - _strategyConfig.R값 / 100.0));

                    var recovered = new DBInfo()
                    {
                        종목명 = accountItem.종목명,
                        종목코드 = accountItem.종목코드,
                        매수일 = 복원매수일,
                        매수전략 = 복원전략,
                        매수수량 = 잔고,
                        보유수량 = 잔고,
                        매수가격 = 매입단가,
                        현재가 = 현재가,
                        평가금 = 현재가 * 잔고,
                        현재수익금 = (현재가 - 매입단가) * 잔고,
                        현재수익률 = 매입단가 > 0 ? (float)(현재가 - 매입단가) / 매입단가 * 100f : 0f,
                        보유일 = 복원보유일,
                        로스컷단계 = 0,
                        로스컷가격 = 복원로스컷가격,
                    };

                    lock (m_HoldingLock) { m_HoldingDbInfoList.Add(recovered); }
                    insertDB(m_HoldingTable, recovered);

                    LogMessage($"[계좌복원] {accountItem.종목명}({accountItem.종목코드}) " +
                               $"{잔고}주 매입단가 {매입단가:N0}원 LC={복원로스컷가격:N0}원 D+{복원보유일} — 전략:{복원전략} 매수일:{복원매수일}");
                }
            }

            // ── 매도 완료 감지: 매도 주문을 냈고, 계좌잔고에서 사라진 종목만 처리 ──
            if (m_HoldJongmokList.Count > 0 && m_PendingSellOrders.Count > 0)
            {
                List<DBInfo> soldHoldings = new List<DBInfo>();
                lock (m_HoldingLock)
                {
                    foreach (var dbItem in m_HoldingDbInfoList.ToList())
                    {
                        if (string.IsNullOrEmpty(dbItem.종목코드)) continue;

                        // 매도 주문이 있는 종목만 확인 (무분별한 삭제 방지)
                        if (!m_PendingSellOrders.ContainsKey(dbItem.종목코드)) continue;

                        // 계좌잔고에 해당 종목이 있는지 확인
                        var accountItem = m_HoldJongmokList.FirstOrDefault(h => h.종목코드 == dbItem.종목코드 || h.종목명 == dbItem.종목명);
                        if (accountItem != null) continue; // 아직 보유 중

                        // 매도 주문 존재 + 계좌에 없음 → 매도 완료
                        soldHoldings.Add(dbItem);
                    }
                }

                foreach (var holding in soldHoldings)
                {
                    LogMessage($"[매도감지] {holding.종목명}({holding.종목코드}) 계좌잔고에 없음 → 매도완료 처리");

                    // 매도가격: 현재가 또는 최근 시세 사용
                    int 매도가 = holding.현재가 > 0 ? holding.현재가 : holding.매수가격;
                    holding.전량매도일 = DateTime.Now.ToString("yyyyMMdd");
                    holding.전량매도이유 = m_PendingSellOrders.ContainsKey(holding.종목코드) ? "수동전량매도" : "HTS/외부매도";
                    holding.매도가격 = 매도가;
                    holding.최종수익금 = (매도가 - holding.매수가격) * holding.매수수량;
                    int 총투자금 = holding.매수가격 * holding.매수수량;
                    holding.최종수익률 = 총투자금 != 0 ? (float)holding.최종수익금 / 총투자금 * 100f : 0f;

                    m_HistoryDbInfoList.Add(holding);
                    deleteHoldingInsertHistory(holding);

                    lock (m_HoldingLock) { m_HoldingDbInfoList.Remove(holding); }

                    // 실시간 시세 해제
                    axKHOpenAPI1.SetRealRemove(스크린.보유종목실시간, holding.종목코드);
                    m_RealTimePrices.TryRemove(holding.종목코드, out _);
                    m_PendingSellOrders.TryRemove(holding.종목코드, out _);

                    LogMessage($"[매도완료] {holding.종목명} 수익률 {holding.최종수익률:F2}% 수익금 {holding.최종수익금:N0}원");
                    m_TodaySellCount++;
                }

                if (soldHoldings.Count > 0)
                    RefreshHoldGrid();
            }
        }


        private void onReceiveTrData(object sender, _DKHOpenAPIEvents_OnReceiveTrDataEvent e)
        {
            LogMessage("onReceiveTrData " + e.sRQName);
            if (e.sRQName == "계좌잔고평가내역")
            {
                try
                {
                int nCnt = axKHOpenAPI1.GetRepeatCnt(e.sTrCode, e.sRQName);
                m_HoldJongmokList = new List<HoldJongmok>();

                for (int nIdx = 0; nIdx < nCnt; nIdx++)
                {
                    int.TryParse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, nIdx, "현재가").Trim(), out int 현재가);
                    double.TryParse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, nIdx, "수익률(%)").Trim(), out double 수익률);
                    double.TryParse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, nIdx, "평가손익").Trim(), out double 평가손익);
                    double.TryParse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, nIdx, "매입금액").Trim(), out double 매입금액);
                    int.TryParse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, nIdx, "평가금액").Trim(), out int 평가금액);
                    Double 손익금액 = 평가손익 - (int)(매입금액 * 0.01);
                    수익률 /= 100.0; // Kiwoom API는 수익률을 100배로 반환

                    String 종목코드 = GetStockCode(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, nIdx, "종목번호").Trim());
                    int.TryParse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, nIdx, "보유수량").Trim(), out int 잔고수량);

                    m_HoldJongmokList.Add(new HoldJongmok()
                    {
                        종목명 = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, nIdx, "종목명").Trim(),
                        종목코드 = 종목코드,
                        잔고수량 = 잔고수량.ToString(),
                        매입금액 = 매입금액.ToString(),
                        평가금액 = 평가금액.ToString(),
                        손익금액 = 손익금액.ToString(),
                        수익률 = 수익률.ToString(),
                        현재가 = 현재가.ToString()
                    });
                }

                // DB sync 후 UI update
                HoldJongmokSyncWithDB();

                // DB List 로 교체
                RefreshHoldGrid();

                // 부호 제거하지 않고 파싱 (손익/수익률에 음수 가능)
                string raw매입 = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, 0, "총매입금액").Trim().Replace("+", "").Replace("--", "-");
                string raw예수금 = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, 0, "추정예탁자산").Trim().Replace("+", "").Replace("--", "-");
                string raw평가 = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, 0, "총평가금액").Trim().Replace("+", "").Replace("--", "-");
                string raw손익 = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, 0, "총평가손익금액").Trim().Replace("+", "").Replace("--", "-");
                string raw수익률 = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, 0, "총수익률(%)").Trim().Replace("+", "").Replace("--", "-");

                long.TryParse(raw매입, out long 전체매입금액);
                long.TryParse(raw예수금, out long 예수금);
                long.TryParse(raw평가, out long 전체평가금액);
                long.TryParse(raw손익, out long 전체손익금액);
                float.TryParse(raw수익률, out float 전체수익률);
                // 키움 opw00018 총수익률(%)는 이미 퍼센트 값으로 반환됨 (100배 아님)

                // 예수금이 0인 경우 장외시간 등 API 반환값 미달 — 기존값 유지
                if (예수금 > 0)
                    m_estimatedBalance = 예수금;
                long 주문가능금액 = m_estimatedBalance - 전체평가금액;
                if (주문가능금액 >= 0)
                    m_availableBalance = 주문가능금액;
                if (주문가능금액 < 0) 주문가능금액 = 0;

                매수금label.Text = string.Format("{0:N0}", 주문가능금액);
                예수금label.Text = string.Format("{0:N0}", m_estimatedBalance);
                평가금label.Text = string.Format("{0:N0}", 전체평가금액);
                평가수익label.Text = $"{(전체손익금액 >= 0 ? "+" : "")}{전체손익금액:N0}";
                수익률label.Text = $"{(전체수익률 >= 0 ? "+" : "")}{전체수익률:F2}%";
                평가수익label.ForeColor = 전체손익금액 >= 0 ? Color.FromArgb(220, 50, 50) : Color.FromArgb(50, 50, 220);
                수익률label.ForeColor = 전체수익률 >= 0 ? Color.FromArgb(220, 50, 50) : Color.FromArgb(50, 50, 220);

                // 보유종목 실시간요청
                //SetRealReg로 등록
                //axKHOpenAPI1.SetRealReg("1000", 종목코드[i], "10;20;12;15;195;182;197;1365;1366;305;306", "0");
                }
                catch (Exception ex)
                {
                    LogMessage("계좌잔고평가내역 처리 오류: " + ex.Message);
                }
            }
            else if (e.sRQName.Contains("조건식종목정보"))
            {
                // 조건식종목정보 받고 실시간 데이터는 끊어 줌
                axKHOpenAPI1.DisconnectRealData(스크린.조건종목정보);

                //LogMessage(e.sRQName);
                String[] str = e.sRQName.Split(';');
                String _조건명 = str[1];
                int index = int.Parse(str[2]);
                int nCnt = axKHOpenAPI1.GetRepeatCnt(e.sTrCode, e.sRQName);

                for (int i = 0; i < nCnt; i++)
                {
                    String _종목명 = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, i, "종목명").Trim();
                    String _종목코드 = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, i, "종목코드").Trim();
                    String _현재가 = ChangeStrToNumberStyle(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, i, "현재가").Trim());
                    String _전일대비 = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, i, "전일대비").Trim();
                    String _등락율 = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, i, "등락율").Trim();
                    String _거래량 = ChangeStrToNumberStyle(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, i, "거래량").Trim());
                    String _시가 = ChangeStrToNumberStyle(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, i, "시가").Trim());
                    String _고가 = ChangeStrToNumberStyle(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, i, "고가").Trim());
                    String _저가 = ChangeStrToNumberStyle(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, i, "저가").Trim());

                    lock (m_ConditionLock)
                    {
                        foreach (StockItemInfo stockItem in m_ConditionList[index].stockItemList)
                        {
                            if (_종목코드 == stockItem.종목코드)
                            {
                                stockItem.조건명 = _조건명;
                                stockItem.종목명 = _종목명;
                                stockItem.현재가 = _현재가;
                                stockItem.전일대비 = _전일대비;
                                stockItem.등락률 = _등락율;
                                stockItem.거래량 = _거래량;
                                stockItem.시가 = _시가;
                                stockItem.고가 = _고가;
                                stockItem.저가 = _저가;
                                break;
                            }
                        }

                        bool isUpdate = false;

                        for (int j = 0; j < conditionFilteredGridView.RowCount - 1; j++)
                        {
                            if (conditionFilteredGridView["조건명", j].Value.ToString() == _조건명 &&
                                conditionFilteredGridView["종목명", j].Value.ToString() == _종목명)
                            {
                                conditionFilteredGridView["종목코드", j].Value = _종목코드;
                                conditionFilteredGridView["현재가", j].Value = _현재가;
                                conditionFilteredGridView["전일대비", j].Value = _전일대비;
                                conditionFilteredGridView["등락률", j].Value = _등락율;
                                conditionFilteredGridView["거래량", j].Value = _거래량;
                                conditionFilteredGridView["시가", j].Value = _시가;
                                conditionFilteredGridView["고가", j].Value = _고가;
                                conditionFilteredGridView["저가", j].Value = _저가;
                                isUpdate = true;
                                break;
                            }
                        }

                        if (isUpdate == false)
                        {
                            conditionFilteredGridView.Rows.Add();
                            conditionFilteredGridView["조건명", conditionFilteredGridView.RowCount - 2].Value = _조건명;
                            conditionFilteredGridView["종목명", conditionFilteredGridView.RowCount - 2].Value = _종목명;
                            conditionFilteredGridView["종목코드", conditionFilteredGridView.RowCount - 2].Value = _종목코드;
                            conditionFilteredGridView["현재가", conditionFilteredGridView.RowCount - 2].Value = _현재가;
                            conditionFilteredGridView["전일대비", conditionFilteredGridView.RowCount - 2].Value = _전일대비;
                            conditionFilteredGridView["등락률", conditionFilteredGridView.RowCount - 2].Value = _등락율;
                            conditionFilteredGridView["거래량", conditionFilteredGridView.RowCount - 2].Value = _거래량;
                            conditionFilteredGridView["시가", conditionFilteredGridView.RowCount - 2].Value = _시가;
                            conditionFilteredGridView["고가", conditionFilteredGridView.RowCount - 2].Value = _고가;
                            conditionFilteredGridView["저가", conditionFilteredGridView.RowCount - 2].Value = _저가;
                        }
                    }
                }
            }
            // 안씀
            else if (e.sRQName.Contains("주식기본정보요청"))
            {
                LogMessage(e.sRQName);
                String[] str = e.sRQName.Split(';');
                String _조건명 = str[1];
                int index = int.Parse(str[2]);


                String _종목명 = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, 0, "종목명").Trim();
                String _종목코드 = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, 0, "종목코드").Trim();
                String _현재가 = ChangeStrToNumberStyle(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, 0, "현재가").Trim());
                String _전일대비 = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, 0, "전일대비").Trim();
                String _등락율 = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, 0, "등락율").Trim();
                String _거래량 = ChangeStrToNumberStyle(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, 0, "거래량").Trim());
                String _시가 = ChangeStrToNumberStyle(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, 0, "시가").Trim());
                String _고가 = ChangeStrToNumberStyle(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, 0, "고가").Trim());
                String _저가 = ChangeStrToNumberStyle(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, 0, "저가").Trim());

                bool already = false;

                lock (m_ConditionLock)
                {
                    foreach (StockItemInfo stockItem in m_ConditionList[index].stockItemList)
                    {
                        if (stockItem.종목명 == _종목명)
                        {
                            LogMessage("이미 있음 : " + _조건명 + " " + _종목명);
                            already = true;
                            break;
                        }
                    }

                    if (already == false)
                    {
                        LogMessage("신규 추가 : " + _조건명 + " " + _종목명);
                        m_ConditionList[index].stockItemList.Add(new StockItemInfo()
                        {
                            조건명 = _조건명,
                            종목명 = _종목명,
                            종목코드 = _종목코드,
                            현재가 = _현재가,
                            전일대비 = _전일대비,
                            등락률 = _등락율,
                            거래량 = _거래량,
                            시가 = _시가,
                            고가 = _고가,
                            저가 = _저가
                        }); ;

                        conditionFilteredGridView.Rows.Add();
                        conditionFilteredGridView["조건명", conditionFilteredGridView.RowCount - 2].Value = _조건명;
                        conditionFilteredGridView["종목명", conditionFilteredGridView.RowCount - 2].Value = _종목명;
                        conditionFilteredGridView["종목코드", conditionFilteredGridView.RowCount - 2].Value = _종목코드;
                        conditionFilteredGridView["현재가", conditionFilteredGridView.RowCount - 2].Value = _현재가;
                        conditionFilteredGridView["전일대비", conditionFilteredGridView.RowCount - 2].Value = _전일대비;
                        conditionFilteredGridView["등락률", conditionFilteredGridView.RowCount - 2].Value = _등락율;
                        conditionFilteredGridView["거래량", conditionFilteredGridView.RowCount - 2].Value = _거래량;
                        conditionFilteredGridView["시가", conditionFilteredGridView.RowCount - 2].Value = _시가;
                        conditionFilteredGridView["고가", conditionFilteredGridView.RowCount - 2].Value = _고가;
                        conditionFilteredGridView["저가", conditionFilteredGridView.RowCount - 2].Value = _저가;
                    }
                }
            }
            else if (e.sRQName == "주식일봉차트조회")
            {
                try
                {
                    axKHOpenAPI1.DisconnectRealData(스크린.종목일봉정보);

                    int nCnt = axKHOpenAPI1.GetRepeatCnt(e.sTrCode, e.sRQName);

                    m_PriceInfoList = new List<PriceInfoEntityObject>();
                    m_PriceSeries.Points.Clear();
                    m_VolumeSeries.Points.Clear();

                    chart1.ChartAreas[1].AxisY.LabelStyle.Format = "#,##0,K";
                    ChartArea priceChartArea = chart1.ChartAreas["PriceChartArea"];
                    do
                    {
                        priceChartArea.AxisX.ScaleView.ZoomReset();
                    }
                    while (priceChartArea.AxisX.ScaleView.IsZoomed);

                    int maxValue = 0;
                    int minValue = int.MaxValue;

                    for (int nIdx = 0; nIdx < nCnt; nIdx++)
                    {
                        if (e.sRQName == "JM_주식분봉차트조회" || e.sRQName == "JM_주식틱봉차트조회")
                            m_PriceInfoList.Add(new PriceInfoEntityObject()
                            {
                                일자 = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, nIdx, "체결시간").Trim(),
                                시가 = Math.Abs(Int32.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, nIdx, "시가").Trim())),
                                고가 = Math.Abs(Int32.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, nIdx, "고가").Trim())),
                                저가 = Math.Abs(Int32.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, nIdx, "저가").Trim())),
                                종가 = Math.Abs(Int32.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, nIdx, "현재가").Trim())),
                                거래량 = Int32.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, nIdx, "거래량").Trim()),
                            });
                        else
                            m_PriceInfoList.Add(new PriceInfoEntityObject()
                            {
                                일자 = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, nIdx, "일자").Trim(),
                                시가 = Int32.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, nIdx, "시가").Trim()),
                                고가 = Int32.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, nIdx, "고가").Trim()),
                                저가 = Int32.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, nIdx, "저가").Trim()),
                                종가 = Int32.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, nIdx, "현재가").Trim()),
                                거래량 = Int32.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, nIdx, "거래량").Trim()),
                            });
                        if (m_PriceInfoList[nIdx].고가 > maxValue)
                            maxValue = m_PriceInfoList[nIdx].고가;
                        if (m_PriceInfoList[nIdx].저가 < minValue)
                            minValue = m_PriceInfoList[nIdx].저가;

                        // adding date and high
                        m_PriceSeries.Points.AddXY(m_PriceInfoList[nIdx].일자, m_PriceInfoList[nIdx].고가);
                        // adding low
                        m_PriceSeries.Points[nIdx].YValues[1] = m_PriceInfoList[nIdx].저가;
                        //adding open
                        m_PriceSeries.Points[nIdx].YValues[2] = m_PriceInfoList[nIdx].시가;
                        // adding close
                        m_PriceSeries.Points[nIdx].YValues[3] = m_PriceInfoList[nIdx].종가;

                        m_PriceSeries.Points[nIdx].ToolTip = "일자 : " + m_PriceInfoList[nIdx].일자 + "\n"
                                                          + "시가 : " + String.Format("{0:#,###}", m_PriceInfoList[nIdx].시가) + "\n"
                                                          + "고가 : " + String.Format("{0:#,###}", m_PriceInfoList[nIdx].고가) + "\n"
                                                          + "저가 : " + String.Format("{0:#,###}", m_PriceInfoList[nIdx].저가) + "\n"
                                                          + "종가 : " + String.Format("{0:#,###}", m_PriceInfoList[nIdx].종가) + "\n"
                                                          + "거래량 : " + String.Format("{0:#,###}", m_PriceInfoList[nIdx].거래량);

                        m_VolumeSeries.Points.AddXY(m_PriceInfoList[nIdx].일자, m_PriceInfoList[nIdx].거래량);

                        m_VolumeSeries.Points[nIdx].ToolTip = "일자 : " + m_PriceInfoList[nIdx].일자 + "\n"
                                                           + "거래량 : " + String.Format("{0:#,###}", m_PriceInfoList[nIdx].거래량);

                    }

                    //requestStockInfo(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, 0, "종목코드").Trim());

                    if (nCnt > 0)
                    {
                        priceChartArea.AxisX.ScaleView.ZoomReset();

                        priceChartArea.AxisY.Maximum = maxValue;
                        priceChartArea.AxisY.Minimum = minValue;

                        if (!priceChartArea.AxisX.ScaleView.IsZoomed)
                            chart1_AxisViewChanged(chart1, new ViewEventArgs(priceChartArea.AxisX, 0));
                    }

                }
                catch (Exception exception)
                {
                    Console.WriteLine(exception.Message.ToString());
                }

            }
            else if (e.sRQName.Contains("보유종목일봉조회"))
            {
                axKHOpenAPI1.DisconnectRealData(스크린.종목일봉정보);

                String[] str = e.sRQName.Split(';');
                if (str.Length < 3) return;
                String _종목명 = str[1];
                String _종목코드 = str[2];

                int nCnt = axKHOpenAPI1.GetRepeatCnt(e.sTrCode, e.sRQName);
                if (nCnt <= 0) return;

                // 일봉 데이터 수집
                List<PriceInfoEntityObject> dailyData = new List<PriceInfoEntityObject>();
                long maxVolume = 0;
                int limit = Math.Min(nCnt, 300);
                for (int nIdx = 0; nIdx < limit; nIdx++)
                {
                    try
                    {
                        int close = Math.Abs(Int32.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, nIdx, "현재가").Trim()));
                        long vol = Math.Abs(long.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, nIdx, "거래량").Trim()));
                        dailyData.Add(new PriceInfoEntityObject()
                        {
                            일자 = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, nIdx, "일자").Trim(),
                            종가 = close,
                            거래량 = (int)vol
                        });
                        if (nIdx < 50 && vol > maxVolume) maxVolume = vol;
                    }
                    catch { break; }
                }

                // 50일 최대거래량 캐싱
                m_Max50DayVolume[_종목코드] = maxVolume;

                // EMA 계산 및 캐싱 (설정된 EMA 기간별)
                var emaValues = new Dictionary<int, int>();
                foreach (int period in _strategyConfig.EMA매도기간)
                {
                    if (dailyData.Count >= period)
                    {
                        List<int> emaList = Core.StrategyManager.CalculateEMA(dailyData, period);
                        if (emaList.Count > 0)
                            emaValues[period] = emaList[0]; // 최신값
                    }
                }
                m_HoldingEMA[_종목코드] = emaValues;

                string emaLog = string.Join(", ", emaValues.Select(kv => $"EMA{kv.Key}={kv.Value:N0}"));
                LogMessage($"일봉 캐싱: {_종목명}({_종목코드}) 50일최대거래량={maxVolume:N0} {emaLog}");
            }
            else if (e.sRQName.Contains("종목일봉차트조회"))
            {
                axKHOpenAPI1.DisconnectRealData(스크린.종목일봉정보);

                String[] str = e.sRQName.Split(';');
                String _종목명 = str[1];

                int nCnt = axKHOpenAPI1.GetRepeatCnt(e.sTrCode, e.sRQName);

                if (nCnt <= 0)
                {
                    LogMessage("nCnt <= 0");
                    return;
                }

                ConditionCheck localConditionCheck = new ConditionCheck();
                List<PriceInfoEntityObject> localPriceInfo = new List<PriceInfoEntityObject>();

                int maxValue = 0;
                int minValue = int.MaxValue;

                for (int nIdx = 0; nIdx < nCnt; nIdx++)
                {
                    try
                    {
                    localPriceInfo.Add(new PriceInfoEntityObject()
                    {
                        일자 = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, nIdx, "일자").Trim(),
                        시가 = Int32.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, nIdx, "시가").Trim()),
                        고가 = Int32.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, nIdx, "고가").Trim()),
                        저가 = Int32.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, nIdx, "저가").Trim()),
                        종가 = Int32.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, nIdx, "현재가").Trim()),
                        거래량 = Int32.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, nIdx, "거래량").Trim()),
                    });
                    }
                    catch { break; }

                    if (localPriceInfo[nIdx].고가 > maxValue)
                        maxValue = localPriceInfo[nIdx].고가;
                    if (localPriceInfo[nIdx].저가 < minValue)
                        minValue = localPriceInfo[nIdx].저가;
                }

                localConditionCheck.priceInfoList = localPriceInfo;
                localConditionCheck.최고가 = maxValue;
                localConditionCheck.최저가 = minValue;

                lock (m_MonitoringLock)
                {
                    if (!m_conditionCheck.ContainsKey(_종목명))
                        m_conditionCheck.Add(_종목명, localConditionCheck);

                    List<int> jong10EMA = Core.StrategyManager.CalculateSMA(localPriceInfo, 10);

                    m_conditionCheck[_종목명].이동평균.Add("ema10", jong10EMA);
                }
                /* Test code
                List<int> prices5MA = Core.StrategyManager.CalculateSMA(prices, 5);
                List<int> prices20MA = Core.StrategyManager.CalculateSMA(prices, 20);
                List<int> prices60MA = Core.StrategyManager.CalculateSMA(prices, 60);

                List<int> prices13EMA = Core.StrategyManager.CalculateEMA(prices, 13);
                List<int> prices16EMA = Core.StrategyManager.CalculateEMA(prices, 16);
                */


            }
            else if (e.sRQName == "지수일봉조회")
            {
                int nCnt = axKHOpenAPI1.GetRepeatCnt(e.sTrCode, e.sRQName);

                ConditionCheck localConditionCheck = new ConditionCheck();
                List<PriceInfoEntityObject> localPriceInfo = new List<PriceInfoEntityObject>();

                for (int nIdx = 0; nIdx < nCnt; nIdx++)
                {
                    try
                    {
                    localPriceInfo.Add(new PriceInfoEntityObject()
                    {
                        일자 = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, nIdx, "일자").Trim(),
                        시가 = Int32.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, nIdx, "시가").Trim()),
                        고가 = Int32.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, nIdx, "고가").Trim()),
                        저가 = Int32.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, nIdx, "저가").Trim()),
                        종가 = Int32.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, nIdx, "현재가").Trim()),
                    });
                    }
                    catch { break; }
                }

                localConditionCheck.priceInfoList = localPriceInfo;

                lock (m_MonitoringLock)
                {
                    // 기존 데이터 덮어쓰기 (장개시 시 갱신 지원)
                    m_conditionCheck["지수"] = localConditionCheck;

                    List<int> jisu60MA = Core.StrategyManager.CalculateSMA(localPriceInfo, 60);
                    m_conditionCheck["지수"].이동평균["ma60"] = jisu60MA;

                    if (localPriceInfo.Count > 0)
                        LogMessage($"코스피 지수 데이터 갱신: {localPriceInfo[0].일자} 종가={localPriceInfo[0].종가} MA60={jisu60MA[0]}");
                }

            }
            else if (e.sRQName.Contains("매수주문"))
            {
                LogMessage(e.sRQName);
                String[] str = e.sRQName.Split(';');
                if (str.Length < 3) { LogMessage("매수주문 RQName 파싱 실패"); return; }
                String _조건명  = str[1];
                String _종목코드 = str[2];
                String _주문번호 = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, 0, "주문번호").Trim();
                LogMessage($"매수TR sTrCode=[{e.sTrCode}] 주문번호=[{_주문번호}]");

                if (_주문번호 == "")
                {
                    // 키움 서버가 주문을 즉시 거부 (잔고부족, 한도초과 등) → pending 즉시 해제 + 선차감 잔고 복원
                    LogMessage($"[매수거부] {_종목코드} — 서버 즉시거부(주문번호 없음), pending 해제 및 잔고 복원");
                    m_PendingBuyOrders.TryRemove(_종목코드, out _);
                    m_BuyOrderTime.TryRemove(_종목코드, out _);
                    m_BuyOrderScreen.TryRemove(_종목코드, out _);
                    if (m_BuyOrderAmount.TryRemove(_종목코드, out long _거부금액))
                        m_availableBalance += _거부금액;
                }
                else
                {
                    m_dicBuyOrder[_주문번호] = _조건명;
                    m_BuyOrderNo[_종목코드] = _주문번호;
                }
            }
            else if (e.sRQName.Contains("매도주문"))
            {
                LogMessage(e.sRQName);
                String[] str = e.sRQName.Split(';');
                if (str.Length < 2) { LogMessage("매도주문 RQName 파싱 실패"); return; }
                String _조건명 = str[1];
                String _매도유형 = str.Length >= 3 ? str[2] : "";
                String _주문번호 = axKHOpenAPI1.GetCommData(e.sTrCode, "", 0, "주문번호").Trim();

                if (_주문번호 == "")
                    LogMessage("매도 주문번호 미수신 (체결 콜백에서 처리됨)");
                else
                    m_dicSellOrder[_주문번호] = _조건명 + ";" + _매도유형;

                // OnReceiveChejanData가 동작하지 않을 경우를 대비, 5초 후 계좌조회로 매도 감지
                _sellConfirmTimer?.Stop();
                _sellConfirmTimer?.Start();
            }
            /*
            else if (e.sRQName == "주식기본정보요청")
            {
                try
                {
                    int 현재가 = int.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, 0, "현재가"));
                    int 전일대비 = int.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, 0, "전일대비"));
                    double 등락율 = double.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, 0, "등락율").Trim());
                    double 거래량 = double.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, 0, "거래량"));
                    double 거래대비 = double.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, 0, "거래대비"));
                    int 시가 = int.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, 0, "시가"));
                    int 고가 = int.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, 0, "고가"));
                    int 저가 = int.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, 0, "저가"));

                    //SetStockInfo(현재가, 전일대비, 등락율, 거래량, 거래대비, 0, 0, 시가, 고가, 저가);
                }
                catch (Exception exception)
                {
                    Console.WriteLine(exception.Message.ToString());
                }
            }
            */
        }

        private void updateAccountInfo()
        {
            string 계좌번호 = AccountList.Text;
            axKHOpenAPI1.SetInputValue("계좌번호", 계좌번호);
            axKHOpenAPI1.SetInputValue("비밀번호", "");
            axKHOpenAPI1.SetInputValue("비밀번호입력매체구분", "00");
            axKHOpenAPI1.SetInputValue("조회구분", "2");

            axKHOpenAPI1.CommRqData("계좌잔고평가내역", "opw00018", 0, GetScrNum());
        }
        private void loginButton(object sender, EventArgs e)
        {
            if (axKHOpenAPI1.CommConnect() != 0)
            {
                LogMessage("로그인창 열기 실패");
            }
        }

        private void onEventconect(object sender, _DKHOpenAPIEvents_OnEventConnectEvent e)
        {
            if (e.nErrCode == 0)
            {
                if (!m_InitialLoginDone)
                {
                    // ═══ 최초 로그인 ═══
                    LogMessage("로그인 성공");

                    string 계좌목록 = axKHOpenAPI1.GetLoginInfo("ACCLIST").Trim();
                    string[] 사용자계좌 = 계좌목록.Split(';');

                    for (int i = 0; i < 사용자계좌.Length; i++)
                    {
                        AccountList.Items.Add(사용자계좌[i]);
                    }
                    AccountList.SelectedIndex = 0;
                    string 사용자id = axKHOpenAPI1.GetLoginInfo("USER_ID");
                    UserID.Text = 사용자id;

                    string 접속서버구분 = axKHOpenAPI1.GetLoginInfo("GetServerGubun");
                    if (접속서버구분 == "1")
                    {
                        ServerGubun.Text = "● 모의투자";
                        ServerGubun.ForeColor = Color.FromArgb(50, 130, 240);
                    }
                    else
                    {
                        ServerGubun.Text = "● 실전";
                        ServerGubun.ForeColor = Color.FromArgb(220, 60, 60);
                    }

                    this.Text = "AutoTrading - " + 사용자id + " [" + ServerGubun.Text.Replace("● ", "") + "]";

                    // 로그인 버튼 상태 변경
                    LoginButton.Text = "✔ 접속됨";
                    LoginButton.Enabled = false;
                    LoginButton.BackColor = Color.FromArgb(60, 60, 60);
                    LoginButton.ForeColor = Color.FromArgb(120, 200, 120);

                    // 모니터링 비동기 태스크 시작
                    m_MonitoringCts = new CancellationTokenSource();
                    _ = Task.Run(() => realMonitoringUpdater(m_MonitoringCts.Token));

                    // 보유종목 일봉 데이터 조회 (50일 최대거래량 캐싱)
                    _ = Task.Run(() => FetchHoldingsDailyData(m_MonitoringCts.Token));

                    // 연결 상태 모니터링 타이머 시작
                    _connectionCheckTimer = new System.Windows.Forms.Timer();
                    _connectionCheckTimer.Interval = 30_000; // 30초
                    _connectionCheckTimer.Tick += ConnectionCheck_Tick;
                    _connectionCheckTimer.Start();

                    m_InitialLoginDone = true;
                }
                else
                {
                    // ═══ 네트워크 재연결 ═══
                    LogMessage("★ [재연결] 서버 재접속 감지 — 실시간 등록 복원 중...");

                    // 조건식 재등록 (실시간 등록되었던 것들 복원)
                    _ = ReRegisterConditionsAsync();
                }

                // ─── 공통 (최초 + 재연결 모두) ───
                updateAccountInfo();
                requestJisuInfo();

                // 계좌 잔고 주기적 갱신 타이머 시작
                _balanceRefreshTimer?.Start();

                // 보유종목 UI 실시간 갱신 타이머 시작
                _holdingUIRefreshTimer?.Start();

                // 보유종목 실시간 시세 등록
                RegisterHoldingsRealTime();

                // 코스피 지수 실시간 등록 (업종코드 "001" = 코스피)
                axKHOpenAPI1.SetRealReg(스크린.지수실시간, "001", "20;10;11;12", "0");
                LogMessage("코스피 지수 실시간 등록");
            }
            else if (e.nErrCode == 100)
            {
                LogMessage("사용자 정보교환 실패");
            }
            else if (e.nErrCode == 101)
            {
                LogMessage("서버접속 실패");
            }
            else if (e.nErrCode == 102)
            {
                LogMessage("버전처리 실패");
            }
        }

        /// <summary>
        /// 네트워크 재연결 후 실시간 조건식 재등록
        /// </summary>
        private async Task ReRegisterConditionsAsync()
        {
            int registered = 0;
            foreach (var condition in m_ConditionList)
            {
                if (!condition.실시간등록여부) continue;

                await Task.Delay(1000);
                int retryCount = 0;
                bool success = false;
                while (retryCount < 3)
                {
                    int result = 0;
                    this.Invoke((Action)(() =>
                    {
                        result = axKHOpenAPI1.SendCondition(
                            스크린.실시간조건식, condition.조건식이름, condition.조건식번호, 1);
                    }));

                    if (result > 0)
                    {
                        LogMessage($"  [재연결] 조건식 복원: {condition.조건식이름}");
                        registered++;
                        success = true;
                        break;
                    }
                    retryCount++;
                    await Task.Delay(5000);
                }
                if (!success)
                    LogMessage($"  [재연결] 조건식 복원 실패: {condition.조건식이름}");
            }
            if (registered > 0)
                LogMessage($"★ [재연결] 조건식 {registered}개 복원 완료");
        }

        /// <summary>
        /// 연결 상태 주기적 확인 — 연결 끊어짐 감지 시 UI에 표시
        /// </summary>
        private void ConnectionCheck_Tick(object sender, EventArgs e)
        {
            try
            {
                int state = axKHOpenAPI1.GetConnectState();
                if (state == 0) // 연결 끊어짐
                {
                    LoginButton.Text = "⚠ 연결끊김";
                    LoginButton.ForeColor = Color.FromArgb(255, 200, 50);
                    LogMessage("[경고] 서버 연결 끊어짐 감지 — 자동 재연결 대기 중...");
                }
                else
                {
                    if (LoginButton.Text.Contains("연결끊김"))
                    {
                        LoginButton.Text = "✔ 접속됨";
                        LoginButton.ForeColor = Color.FromArgb(120, 200, 120);
                    }
                }
            }
            catch { }
        }

        private string ChangeStrToNumberStyle(string strNumber, bool bIsAbs = true)
        {
            int number = Int32.Parse(strNumber);

            if (bIsAbs)
                number = Math.Abs(number);

            return String.Format("{0:#,###}", number);
        }
        private string ChangeIntToNumberStyle(int nNumber)
        {
            return String.Format("{0:#,###}", nNumber);
        }

        public string GetStockCode(string code)
        {
            return Regex.Replace(code, @"\D", "");
        }

        /// <summary>
        /// TextBox Placeholder 효과 (ForeColor 전환)
        /// </summary>
        private void SetPlaceholder(TextBox tb, string placeholder)
        {
            tb.ForeColor = Color.Gray;
            tb.Text = placeholder;
            tb.GotFocus += (s, e) =>
            {
                if (tb.Text == placeholder)
                {
                    tb.Text = "";
                    tb.ForeColor = Color.Black;
                }
            };
            tb.LostFocus += (s, e) =>
            {
                if (string.IsNullOrWhiteSpace(tb.Text))
                {
                    tb.ForeColor = Color.Gray;
                    tb.Text = placeholder;
                }
            };
        }

        // IntRound(xxx, -3) 천에서 올림
        public int IntRound(int Value, int Digit)
        {
            double Temp = Math.Pow(10.0, Digit);
            return (int)(Math.Ceiling(Value * Temp) / Temp);
        }

        private string GetScrNum()
        {
            if (_scrNum < 5200)
                _scrNum++;
            else
                _scrNum = 5050;
            return _scrNum.ToString();
        }

        public bool LogMessage(string strMsg)
        {
            try
            {
                string strTotalLog = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.ff") + " : " + strMsg;

                if (logTextBox.InvokeRequired)
                    logTextBox.BeginInvoke(new Action(() => logTextBox.AppendText(strTotalLog + Environment.NewLine)));
                else
                    logTextBox.AppendText(strTotalLog + Environment.NewLine);

                Core.LogManager.Log(strMsg);

                return true;
            }
            catch (Exception ex)
            {
                try
                {
                    Core.LogManager.Log($"[LogError] {ex.Message}");
                }
                catch { }
                return false;
            }
        }

        // Helper to find DBInfo in lists
        private DBInfo FindDbInfo(List<DBInfo> list, string 종목명, string 매수일, string 매수전략)
        {
            if (list == null) return null;
            return list.Find(x => x.종목명 == 종목명 && x.매수일 == 매수일 && x.매수전략 == 매수전략);
        }

        /// <summary>
        /// 패널간 크기 조절이 가능한 SplitContainer 설정
        /// </summary>
        private void SetupSplitContainers()
        {
            // tableLayoutPanel3(상단), tableLayoutPanel5(중간), tableLayoutPanel4(하단)을 SplitContainer에 배치
            // 기존 패널들을 폼에서 분리
            this.Controls.Remove(tableLayoutPanel3);
            this.Controls.Remove(tableLayoutPanel5);
            this.Controls.Remove(tableLayoutPanel4);

            // 패널 제목 라벨 추가
            var lblCondition = CreateSectionLabel("📋 조건식 목록");
            var lblCondResult = CreateSectionLabel("📊 조건식 편입종목");
            var lblHolding = CreateSectionLabel("💰 보유종목 (우클릭: 매도)");
            var lblChart = CreateSectionLabel("📈 차트");
            var lblLog = CreateSectionLabel("📝 로그");

            // 조건식 체크리스트에 제목 추가
            var condPanel = new Panel();
            condPanel.Dock = DockStyle.Fill;
            lblCondition.Dock = DockStyle.Top;
            condPanel.Controls.Add(conditionCheckedListBox);
            condPanel.Controls.Add(lblCondition);
            conditionCheckedListBox.Dock = DockStyle.Fill;

            // 조건식 편입종목 그리드에 제목 추가
            var condResultPanel = new Panel();
            condResultPanel.Dock = DockStyle.Fill;
            lblCondResult.Dock = DockStyle.Top;
            condResultPanel.Controls.Add(conditionFilteredGridView);
            condResultPanel.Controls.Add(lblCondResult);
            conditionFilteredGridView.Dock = DockStyle.Fill;

            // tableLayoutPanel3 재구성 (조건식 패널들)
            tableLayoutPanel3.Controls.Clear();
            tableLayoutPanel3.Controls.Add(condPanel, 0, 0);
            tableLayoutPanel3.Controls.Add(condResultPanel, 1, 0);
            tableLayoutPanel3.Controls.Add(tableLayoutPanel2, 2, 0);

            // 보유종목에 제목 추가
            var holdPanel = new Panel();
            holdPanel.Dock = DockStyle.Fill;
            lblHolding.Dock = DockStyle.Top;
            holdPanel.Controls.Add(holdJongmokGridView);
            holdPanel.Controls.Add(lblHolding);
            holdJongmokGridView.Dock = DockStyle.Fill;
            tableLayoutPanel5.Controls.Clear();
            tableLayoutPanel5.Controls.Add(holdPanel, 0, 0);

            // 차트에 제목 추가
            lblChart.Dock = DockStyle.Top;
            panel1.Controls.Add(lblChart);
            chart1.Dock = DockStyle.Fill;

            // 로그에 제목 추가
            lblLog.Dock = DockStyle.Top;
            panel3.Controls.Add(lblLog);
            logTextBox.Dock = DockStyle.Fill;

            // 상단 SplitContainer: 조건식(Panel1) vs 보유종목(Panel2)
            _splitTop = new SplitContainer();
            _splitTop.Orientation = Orientation.Horizontal;
            _splitTop.Dock = DockStyle.Fill;
            _splitTop.SplitterWidth = 6;
            _splitTop.BackColor = Color.FromArgb(220, 225, 235);
            _splitTop.Panel1.Controls.Add(tableLayoutPanel3);
            _splitTop.Panel2.Controls.Add(tableLayoutPanel5);
            tableLayoutPanel3.Dock = DockStyle.Fill;
            tableLayoutPanel5.Dock = DockStyle.Fill;
            _splitTop.Panel1MinSize = 80;
            _splitTop.Panel2MinSize = 80;

            // 메인 SplitContainer: 상단(조건식+보유종목)(Panel1) vs 하단(차트+로그)(Panel2)
            _splitMain = new SplitContainer();
            _splitMain.Orientation = Orientation.Horizontal;
            _splitMain.Dock = DockStyle.None;
            _splitMain.SplitterWidth = 6;
            _splitMain.BackColor = Color.FromArgb(220, 225, 235);
            _splitMain.Panel1.Controls.Add(_splitTop);
            _splitMain.Panel2.Controls.Add(tableLayoutPanel4);
            tableLayoutPanel4.Dock = DockStyle.Fill;
            _splitMain.Panel1MinSize = 100;
            _splitMain.Panel2MinSize = 100;

            this.Controls.Add(_splitMain);

            // 스플리터 커서 변경
            _splitMain.Cursor = Cursors.Default;
            _splitTop.Cursor = Cursors.Default;
        }

        /// <summary>
        /// 섹션 제목 라벨 생성
        /// </summary>
        private Label CreateSectionLabel(string text)
        {
            var lbl = new Label();
            lbl.Text = text;
            lbl.Font = new Font("맑은 고딕", 9f, FontStyle.Bold);
            lbl.ForeColor = Color.FromArgb(50, 70, 100);
            lbl.BackColor = Color.FromArgb(235, 240, 248);
            lbl.Height = 22;
            lbl.TextAlign = ContentAlignment.MiddleLeft;
            lbl.Padding = new Padding(6, 0, 0, 0);
            return lbl;
        }

        /// <summary>
        /// 폼 크기 변경 시 모든 패널을 동적으로 재배치
        /// </summary>
        private void AdjustLayout()
        {
            if (_splitMain == null || _splitTop == null) return;

            const int margin = 12;
            const int topBarRow1Height = 36;
            const int topBarRow2Height = 30;
            const int gap = 3;

            int cw = this.ClientSize.Width;
            int ch = this.ClientSize.Height;
            int contentWidth = cw - margin * 2;

            if (contentWidth < 100 || ch < 200) return;

            // === 상단 바 1행: 좌측 고정 버튼 배치 ===
            GetConditionButton.Location = new Point(margin, 12);
            ATStartButton.Location = new Point(GetConditionButton.Right + 8, 12);
            ATStopButton.Location = new Point(ATStartButton.Location.X, ATStartButton.Location.Y);
            ATStopButton.Size = ATStartButton.Size;
            _historyButton.Location = new Point(ATStartButton.Right + 12, 12);
            _performanceButton.Location = new Point(_historyButton.Right + 6, 12);

            // === 상단 바 1행: 비상정지 버튼을 tableLayoutPanel1 기준 우측 배치 ===
            int rightX = tableLayoutPanel1.Left - 8;
            LoginButton.Location = new Point(cw - margin - LoginButton.Width, 12);
            tableLayoutPanel1.Location = new Point(LoginButton.Left - 8 - tableLayoutPanel1.Width, 12);
            _emergencyStopButton.Location = new Point(tableLayoutPanel1.Left - 8 - _emergencyStopButton.Width, 10);

            // 1행에 테스트 컨트롤이 들어갈 공간이 있는지 확인
            int sellRight = _emergencyStopButton.Left - 6;
            int neededWidth = testCode.Width + testPrice.Width + testAmount.Width
                            + BuyTestButton.Width + SellTestButton.Width + 6 * 4;
            bool fitsInRow1 = (sellRight - neededWidth) > _performanceButton.Right + 20;

            bool twoRows; // 2행 필요 여부
            if (fitsInRow1)
            {
                // 1행에 배치
                SellTestButton.Location = new Point(sellRight - SellTestButton.Width, 12);
                BuyTestButton.Location = new Point(SellTestButton.Left - 6 - BuyTestButton.Width, 12);
                testAmount.Location = new Point(BuyTestButton.Left - 6 - testAmount.Width, 13);
                testPrice.Location = new Point(testAmount.Left - 6 - testPrice.Width, 13);
                testCode.Location = new Point(testPrice.Left - 6 - testCode.Width, 13);
                twoRows = false;
            }
            else
            {
                // 2행에 배치 (좌측 정렬)
                int row2Y = topBarRow1Height + 2;
                testCode.Location = new Point(margin, row2Y);
                testPrice.Location = new Point(testCode.Right + 4, row2Y);
                testAmount.Location = new Point(testPrice.Right + 4, row2Y);
                BuyTestButton.Location = new Point(testAmount.Right + 4, row2Y - 1);
                SellTestButton.Location = new Point(BuyTestButton.Right + 4, row2Y - 1);
                twoRows = true;
            }

            testCode.Visible = true;
            testPrice.Visible = true;
            testAmount.Visible = true;
            BuyTestButton.Visible = true;
            SellTestButton.Visible = true;

            // 대시보드 strip
            int topY = (twoRows ? topBarRow1Height + topBarRow2Height : topBarRow1Height) + gap + 2;
            const int dashH = 24;
            _dashboardLabel.SetBounds(margin, topY, contentWidth, dashH);

            // SplitContainer 영역: 대시보드 아래 ~ 폼 하단
            int splitY = topY + dashH + gap;
            int splitH = Math.Max(200, ch - splitY - margin);
            _splitMain.SetBounds(margin, splitY, contentWidth, splitH);

            // 최초 로드 시에만 비율 설정 (이후 사용자가 드래그로 조절 가능)
            if (!_splitInitialized && _splitMain.Height > 100 && _splitTop.Height > 100)
            {
                int mainDist = (int)(_splitMain.Height * 0.65);
                if (mainDist > 0 && mainDist < _splitMain.Height - _splitMain.SplitterWidth - _splitMain.Panel2MinSize)
                    _splitMain.SplitterDistance = mainDist;

                int topDist = (int)(_splitTop.Height * 0.35);
                if (topDist > 0 && topDist < _splitTop.Height - _splitTop.SplitterWidth - _splitTop.Panel2MinSize)
                    _splitTop.SplitterDistance = topDist;

                _splitInitialized = true;
            }

            // 상단 바 버튼들이 패널에 가려지지 않도록 Z-Order 최상위
            _dashboardLabel.BringToFront();
            GetConditionButton.BringToFront();
            ATStartButton.BringToFront();
            ATStopButton.BringToFront();
            _emergencyStopButton.BringToFront();
            _historyButton.BringToFront();
            _performanceButton.BringToFront();
            LoginButton.BringToFront();
            testCode.BringToFront();
            testPrice.BringToFront();
            testAmount.BringToFront();
            BuyTestButton.BringToFront();
            SellTestButton.BringToFront();
        }

        /// <summary>
        /// 앱 아이콘 동적 생성 - 주식 차트 캔들스틱 + 상승 화살표 디자인
        /// </summary>
        private Icon CreateAppIcon()
        {
            int size = 32;
            using (Bitmap bmp = new Bitmap(size, size, PixelFormat.Format32bppArgb))
            using (Graphics g = Graphics.FromImage(bmp))
            {
                g.SmoothingMode = SmoothingMode.AntiAlias;

                // 배경: 둥근 사각형 (어두운 네이비)
                using (var bgBrush = new SolidBrush(Color.FromArgb(20, 30, 48)))
                {
                    g.FillRectangle(bgBrush, 0, 0, size, size);
                }

                // 캔들스틱 3개 (녹색 상승, 빨강 하락, 녹색 상승)
                using (var greenBrush = new SolidBrush(Color.FromArgb(0, 200, 120)))
                using (var redBrush = new SolidBrush(Color.FromArgb(220, 60, 60)))
                using (var greenPen = new Pen(Color.FromArgb(0, 200, 120), 1f))
                using (var redPen = new Pen(Color.FromArgb(220, 60, 60), 1f))
                {
                    // 캔들 1 (녹색): x=6
                    g.DrawLine(greenPen, 8, 18, 8, 8);
                    g.FillRectangle(greenBrush, 6, 10, 5, 8);

                    // 캔들 2 (빨강): x=14
                    g.DrawLine(redPen, 16, 22, 16, 10);
                    g.FillRectangle(redBrush, 14, 12, 5, 8);

                    // 캔들 3 (녹색, 큰 상승): x=22
                    g.DrawLine(greenPen, 24, 16, 24, 4);
                    g.FillRectangle(greenBrush, 22, 6, 5, 10);
                }

                // 상승 화살표 (우상단)
                using (var arrowPen = new Pen(Color.FromArgb(60, 180, 255), 2f))
                {
                    arrowPen.EndCap = LineCap.ArrowAnchor;
                    g.DrawLine(arrowPen, 4, 26, 28, 6);
                }

                IntPtr hIcon = bmp.GetHicon();
                return Icon.FromHandle(hIcon);
            }
        }

        /// <summary>
        /// UI 전체 스타일 통일 적용
        /// </summary>
        private void ApplyUIStyle()
        {
            // 폼 배경
            Color formBg = Color.FromArgb(240, 243, 247);
            this.BackColor = formBg;

            // 색상 팔레트
            Color darkBg = Color.FromArgb(30, 40, 55);
            Color accentBlue = Color.FromArgb(50, 130, 240);
            Color accentGreen = Color.FromArgb(0, 180, 100);
            Color accentRed = Color.FromArgb(220, 60, 60);
            Color headerBg = Color.FromArgb(45, 55, 72);
            Color cellBg = Color.FromArgb(255, 255, 255);
            Color altRowBg = Color.FromArgb(245, 248, 252);
            Color gridBorder = Color.FromArgb(200, 210, 225);

            // 버튼 스타일 적용
            StyleButton(LoginButton, accentBlue);
            StyleButton(GetConditionButton, Color.FromArgb(80, 100, 130));
            StyleButton(ATStartButton, accentGreen);
            StyleButton(ATStopButton, accentRed);
            StyleButton(BuyTestButton, accentRed);
            StyleButton(SellTestButton, accentBlue);
            StyleButton(_historyButton, Color.FromArgb(210, 120, 20));
            StyleButton(_performanceButton, Color.FromArgb(0, 160, 130));

            // DataGridView 공통 스타일
            StyleGrid(conditionFilteredGridView, headerBg, cellBg, altRowBg, gridBorder);
            StyleGrid(holdJongmokGridView, headerBg, cellBg, altRowBg, gridBorder);

            // 계좌정보 패널 스타일
            tableLayoutPanel2.BackColor = Color.White;
            tableLayoutPanel2.CellBorderStyle = TableLayoutPanelCellBorderStyle.Single;
            foreach (Control ctrl in tableLayoutPanel2.Controls)
            {
                if (ctrl is Label lbl)
                {
                    lbl.BackColor = Color.White;
                    lbl.Font = new Font("맑은 고딕", 9f, FontStyle.Regular);
                }
            }
            // 항목명은 약간 볼드
            label2.Font = new Font("맑은 고딕", 9f, FontStyle.Bold);
            label3.Font = new Font("맑은 고딕", 9f, FontStyle.Bold);
            label4.Font = new Font("맑은 고딕", 9f, FontStyle.Bold);
            label5.Font = new Font("맑은 고딕", 9f, FontStyle.Bold);
            label6.Font = new Font("맑은 고딕", 9f, FontStyle.Bold);
            label2.BackColor = Color.FromArgb(248, 250, 252);
            label3.BackColor = Color.FromArgb(248, 250, 252);
            label4.BackColor = Color.FromArgb(248, 250, 252);
            label5.BackColor = Color.FromArgb(248, 250, 252);
            label6.BackColor = Color.FromArgb(248, 250, 252);

            // 로그 텍스트박스 스타일
            logTextBox.BackColor = Color.FromArgb(25, 32, 44);
            logTextBox.ForeColor = Color.FromArgb(180, 220, 255);
            logTextBox.Font = new Font("Consolas", 9f, FontStyle.Regular);

            // 조건식 체크리스트 스타일
            conditionCheckedListBox.BackColor = Color.White;
            conditionCheckedListBox.Font = new Font("맑은 고딕", 10f, FontStyle.Regular);

            // 차트 배경
            chart1.BackColor = Color.White;
            chart1.ChartAreas[0].BackColor = Color.White;
            chart1.ChartAreas[1].BackColor = Color.FromArgb(250, 252, 255);

            // 계좌정보 TableLayout1 스타일
            tableLayoutPanel1.BackColor = Color.White;

            // ── 패널 경계선 스타일 ──
            Color panelBorder = Color.FromArgb(195, 205, 220);
            Color panelBg = Color.White;

            // 상단 패널 (조건식 + 그리드 + 계좌정보)
            StylePanel(tableLayoutPanel3, panelBg, panelBorder);

            // 중간 패널 (보유종목)
            StylePanel(tableLayoutPanel5, panelBg, panelBorder);

            // 하단 차트 패널
            StylePanel(panel1, panelBg, panelBorder);

            // 하단 로그 패널
            StylePanel(panel3, Color.FromArgb(25, 32, 44), panelBorder);

            // 하단 컨테이너 (투명 배경 - 자식 패널이 border 가짐)
            tableLayoutPanel4.BackColor = formBg;

            // 테스트 입력 필드 PlaceholderText 효과
            testCode.Font = new Font("맑은 고딕", 9f);
            testPrice.Font = new Font("맑은 고딕", 9f);
            testAmount.Font = new Font("맑은 고딕", 9f);
            SetPlaceholder(testCode, "종목코드");
            SetPlaceholder(testPrice, "가격");
            SetPlaceholder(testAmount, "수량");
        }

        private void StyleButton(Button btn, Color bgColor)
        {
            btn.FlatStyle = FlatStyle.Flat;
            btn.FlatAppearance.BorderSize = 0;
            btn.BackColor = bgColor;
            btn.ForeColor = Color.White;
            btn.Font = new Font("맑은 고딕", 9f, FontStyle.Bold);
            btn.Cursor = Cursors.Hand;

            // 마우스 호버 효과
            btn.MouseEnter += (s, e) => btn.BackColor = ControlPaint.Light(bgColor, 0.15f);
            btn.MouseLeave += (s, e) => btn.BackColor = bgColor;
        }

        private void StyleGrid(DataGridView grid, Color headerBg, Color cellBg, Color altRowBg, Color borderColor)
        {
            grid.EnableHeadersVisualStyles = false;
            grid.BorderStyle = BorderStyle.None;
            grid.CellBorderStyle = DataGridViewCellBorderStyle.SingleHorizontal;
            grid.GridColor = Color.FromArgb(230, 235, 245);
            grid.BackgroundColor = cellBg;

            // 헤더 스타일
            grid.ColumnHeadersDefaultCellStyle.BackColor = headerBg;
            grid.ColumnHeadersDefaultCellStyle.ForeColor = Color.White;
            grid.ColumnHeadersDefaultCellStyle.Font = new Font("맑은 고딕", 9f, FontStyle.Bold);
            grid.ColumnHeadersDefaultCellStyle.Alignment = DataGridViewContentAlignment.MiddleCenter;
            grid.ColumnHeadersDefaultCellStyle.SelectionBackColor = headerBg;
            grid.ColumnHeadersHeight = 32;

            // 셀 스타일
            grid.DefaultCellStyle.BackColor = cellBg;
            grid.DefaultCellStyle.ForeColor = Color.FromArgb(40, 50, 70);
            grid.DefaultCellStyle.Font = new Font("맑은 고딕", 9f);
            grid.DefaultCellStyle.SelectionBackColor = Color.FromArgb(220, 234, 252);
            grid.DefaultCellStyle.SelectionForeColor = Color.FromArgb(30, 40, 60);
            grid.DefaultCellStyle.Padding = new Padding(2);
            grid.DefaultCellStyle.WrapMode = DataGridViewTriState.False;

            // 교차 행 색상
            grid.AlternatingRowsDefaultCellStyle.BackColor = altRowBg;

            // 행 헤더 숨기기 (깔끔하게)
            grid.RowHeadersVisible = false;

            // 행 높이 고정 (텍스트 줄바꿈 방지)
            grid.AutoSizeRowsMode = DataGridViewAutoSizeRowsMode.None;
            grid.RowTemplate.Height = 24;

            // 자동 사이즈
            grid.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill;
        }

        private void StylePanel(Control panel, Color bgColor, Color borderColor)
        {
            panel.BackColor = bgColor;
            panel.Padding = new Padding(1);
            panel.Paint += (s, e) =>
            {
                var ctrl = (Control)s;
                using (var pen = new Pen(borderColor, 1f))
                {
                    e.Graphics.DrawRectangle(pen, 0, 0, ctrl.Width - 1, ctrl.Height - 1);
                }
                // 미세 그림자 (하단+우측)
                using (var shadowPen = new Pen(Color.FromArgb(40, 0, 0, 0), 1f))
                {
                    e.Graphics.DrawLine(shadowPen, 1, ctrl.Height - 1, ctrl.Width - 1, ctrl.Height - 1);
                    e.Graphics.DrawLine(shadowPen, ctrl.Width - 1, 1, ctrl.Width - 1, ctrl.Height - 1);
                }
            };
        }


        // 숫자 문자열 비교 (콤마 제거 후 숫자로 비교, 실패 시 문자열 비교)
        private int CompareGridValues(string val1, string val2)
        {
            string s1 = (val1 ?? "").Replace(",", "");
            string s2 = (val2 ?? "").Replace(",", "");
            double d1, d2;
            if (double.TryParse(s1, out d1) && double.TryParse(s2, out d2))
                return d1.CompareTo(d2);
            return string.Compare(s1, s2, StringComparison.Ordinal);
        }

        // conditionFilteredGridView 숫자/문자열 혼합 정렬
        private void conditionGridView_SortCompare(object sender, DataGridViewSortCompareEventArgs e)
        {
            e.SortResult = CompareGridValues(e.CellValue1?.ToString(), e.CellValue2?.ToString());
            e.Handled = true;
        }

        // conditionFilteredGridView 헤더 클릭 → 오름차순/내림차순 정렬
        private void conditionGridView_ColumnHeaderMouseClick(object sender, DataGridViewCellMouseEventArgs e)
        {
            if (m_conditionSortCol == e.ColumnIndex)
                m_conditionSortOrder = m_conditionSortOrder == SortOrder.Ascending ? SortOrder.Descending : SortOrder.Ascending;
            else
            {
                m_conditionSortCol = e.ColumnIndex;
                m_conditionSortOrder = SortOrder.Ascending;
            }

            conditionFilteredGridView.Sort(
                conditionFilteredGridView.Columns[e.ColumnIndex],
                m_conditionSortOrder == SortOrder.Ascending
                    ? System.ComponentModel.ListSortDirection.Ascending
                    : System.ComponentModel.ListSortDirection.Descending);

            conditionFilteredGridView.Columns[e.ColumnIndex].HeaderCell.SortGlyphDirection = m_conditionSortOrder;
        }

        // holdJongmokGridView 헤더 클릭 → 오름차순/내림차순 정렬
        private void holdGridView_ColumnHeaderMouseClick(object sender, DataGridViewCellMouseEventArgs e)
        {
            if (m_holdSortCol == e.ColumnIndex)
                m_holdSortOrder = m_holdSortOrder == SortOrder.Ascending ? SortOrder.Descending : SortOrder.Ascending;
            else
            {
                m_holdSortCol = e.ColumnIndex;
                m_holdSortOrder = SortOrder.Ascending;
            }

            string propName = holdJongmokGridView.Columns[e.ColumnIndex].DataPropertyName;
            if (string.IsNullOrEmpty(propName)) return;

            var prop = typeof(DBInfo).GetProperty(propName);
            if (prop == null) return;

            if (m_holdSortOrder == SortOrder.Ascending)
                m_HoldingDbInfoList.Sort((a, b) => Comparer<object>.Default.Compare(prop.GetValue(a), prop.GetValue(b)));
            else
                m_HoldingDbInfoList.Sort((a, b) => Comparer<object>.Default.Compare(prop.GetValue(b), prop.GetValue(a)));

            _holdGridBindingSource.DataSource = m_HoldingDbInfoList;
            FormatHoldGrid();

            if (holdJongmokGridView.Columns.Count > e.ColumnIndex)
                holdJongmokGridView.Columns[e.ColumnIndex].HeaderCell.SortGlyphDirection = m_holdSortOrder;
        }

        /// <summary>
        /// 보유종목 그리드 컬럼 순서/표시/포맷 설정
        /// </summary>
        private void FormatHoldGrid()
        {
            if (holdJongmokGridView.Columns.Count == 0) return;

            // DataSource 재할당 시 bool 컬럼이 중복 자동생성되는 것 방지
            holdJongmokGridView.AutoGenerateColumns = false;

            // 빈 신규입력 행 제거
            holdJongmokGridView.AllowUserToAddRows = false;

            // nR절반매도 bool 컬럼 → 텍스트(O/X) 표시로 교체
            if (holdJongmokGridView.Columns.Contains("nR절반매도"))
            {
                holdJongmokGridView.Columns.Remove("nR절반매도");
                var txtCol = new DataGridViewTextBoxColumn();
                txtCol.Name = "nR절반매도";
                txtCol.HeaderText = "nR익절";
                txtCol.Width = 50;
                txtCol.ReadOnly = true;
                txtCol.AutoSizeMode = DataGridViewAutoSizeColumnMode.None;
                txtCol.DefaultCellStyle.Alignment = DataGridViewContentAlignment.MiddleCenter;
                holdJongmokGridView.Columns.Add(txtCol);
                for (int i = 0; i < m_HoldingDbInfoList.Count; i++)
                    holdJongmokGridView["nR절반매도", i].Value = m_HoldingDbInfoList[i].nR절반매도 ? "O" : "X";
            }

            // 보여줄 컬럼 순서 정의
            var displayOrder = new (string name, string header, int width, string format)[]
            {
                ("종목명", "종목명", 110, null),
                ("종목코드", "종목코드", 70, null),
                ("매수전략", "매수전략", 110, null),
                ("매수가격", "매수가격", 82, "#,##0"),
                ("현재가", "현재가", 82, "#,##0"),
                ("평가금", "평가금", 90, "#,##0"),
                ("현재수익률", "수익률(%)", 68, "0.00"),
                ("현재수익금", "수익금", 82, "#,##0"),
                ("매수수량", "매수수량", 58, "#,##0"),
                ("보유수량", "보유수량", 58, "#,##0"),
                ("보유일", "보유일", 48, null),
                ("로스컷가격", "로스컷", 82, "#,##0"),
                ("로스컷단계", "LC단계", 48, null),
                ("nR절반매도", "nR익절", 48, null),
                ("매수일", "매수일", 82, null),
            };

            int order = 0;
            foreach (var col in displayOrder)
            {
                if (holdJongmokGridView.Columns.Contains(col.name))
                {
                    var c = holdJongmokGridView.Columns[col.name];
                    c.HeaderText = col.header;
                    c.DisplayIndex = order++;
                    c.Visible = true;
                    c.Width = col.width;
                    c.AutoSizeMode = DataGridViewAutoSizeColumnMode.None;
                    if (col.format != null)
                        c.DefaultCellStyle.Format = col.format;
                    c.DefaultCellStyle.Alignment = DataGridViewContentAlignment.MiddleRight;
                }
            }

            // 나머지 컬럼 숨김
            var visibleSet = new HashSet<string>(displayOrder.Select(d => d.name));
            foreach (DataGridViewColumn c in holdJongmokGridView.Columns)
            {
                if (!visibleSet.Contains(c.Name))
                    c.Visible = false;
            }

            // 종목명은 왼쪽 정렬
            if (holdJongmokGridView.Columns.Contains("종목명"))
                holdJongmokGridView.Columns["종목명"].DefaultCellStyle.Alignment = DataGridViewContentAlignment.MiddleLeft;
            if (holdJongmokGridView.Columns.Contains("매수전략"))
                holdJongmokGridView.Columns["매수전략"].DefaultCellStyle.Alignment = DataGridViewContentAlignment.MiddleLeft;
        }

    }


}