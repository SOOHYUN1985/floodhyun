using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.ComponentModel;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;
using System.Windows.Forms.DataVisualization.Charting;
using AutoTradingTest.Core;
using AxKHOpenAPILib;
using Microsoft.VisualBasic;

namespace AutoTradingTest;

public class Form1 : Form
{
	private CancellationTokenSource m_ConditionCts;

	private object m_ConditionLock = new object();

	private CancellationTokenSource m_MonitoringCts;

	private object m_MonitoringLock = new object();

	private CancellationTokenSource m_SellMonitorCts;

	private bool m_SellMonitorRunning;

	private int _scrNum = 5050;

	private DbManager _dbManager;

	private ConditionManager _conditionManager;

	private StrategyManager _strategyManager;

	private OrderManager _orderManager;

	private SellStrategyManager _sellStrategyManager;

	private StrategyConfig _strategyConfig;

	private BindingSource _holdGridBindingSource = new BindingSource();

	private ConcurrentDictionary<string, RealTimePrice> m_RealTimePrices = new ConcurrentDictionary<string, RealTimePrice>();

	private ConcurrentDictionary<string, long> m_Max50DayVolume = new ConcurrentDictionary<string, long>();

	private ConcurrentDictionary<string, Dictionary<int, int>> m_HoldingEMA = new ConcurrentDictionary<string, Dictionary<int, int>>();

	private ConcurrentQueue<string> m_holdingDailyQueue = new ConcurrentQueue<string>();

	private Button _emergencyStopButton;

	private SplitContainer _splitMain;

	private SplitContainer _splitTop;

	private bool _splitInitialized;

	private List<PriceInfoEntityObject> m_PriceInfoList;

	private Series m_PriceSeries;

	private Series m_VolumeSeries;

	private Dictionary<string, string> m_monitoring = new Dictionary<string, string>();

	private ConcurrentQueue<string> m_monitoringQueue = new ConcurrentQueue<string>();

	private ConcurrentDictionary<string, string> m_dicBuyOrder = new ConcurrentDictionary<string, string>();

	private ConcurrentDictionary<string, string> m_dicSellOrder = new ConcurrentDictionary<string, string>();

	private ConcurrentDictionary<string, string> m_PendingBuyOrders = new ConcurrentDictionary<string, string>();

	private ConcurrentDictionary<string, string> m_PendingSellOrders = new ConcurrentDictionary<string, string>();

	private ConcurrentDictionary<string, DateTime> m_BuyOrderTime = new ConcurrentDictionary<string, DateTime>();

	private const int BUY_TIMEOUT_SEC = 300;

	private ConcurrentDictionary<string, string> m_BuyOrderScreen = new ConcurrentDictionary<string, string>();

	private ConcurrentDictionary<string, string> m_BuyOrderNo = new ConcurrentDictionary<string, string>();

	private ConcurrentDictionary<string, long> m_BuyOrderAmount = new ConcurrentDictionary<string, long>();

	private int m_buyScreenIdx = 9;

	private List<DBInfo> m_HoldingDbInfoList = new List<DBInfo>();

	private readonly object m_HoldingLock = new object();

	private List<DBInfo> m_HistoryDbInfoList = new List<DBInfo>();

	private static readonly string DB_PATH = "Data Source=" + Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "BujaGazua.sqlite") + ";Pooling=true";

	private string m_HoldingTable = "HoldingTable";

	private string m_HistoryTable = "HistoryTable";

	private List<ConditionInfo> m_ConditionList = new List<ConditionInfo>();

	private List<HoldJongmok> m_HoldJongmokList = new List<HoldJongmok>();

	private Dictionary<string, ConditionCheck> m_conditionCheck = new Dictionary<string, ConditionCheck>();

	private Label _dashboardLabel;

	private long m_estimatedBalance;

	private long m_availableBalance;

	private volatile bool m_IsMarketOpen;

	private volatile int m_RealtimeJisuPrice;

	private volatile bool m_JisuBelowMA60;

	private int m_TodayBuyCount;

	private int m_TodaySellCount;

	private System.Windows.Forms.Timer _balanceRefreshTimer;

	private System.Windows.Forms.Timer _sellConfirmTimer;

	private System.Windows.Forms.Timer _holdingUIRefreshTimer;

	private volatile bool m_DbLoaded;

	private bool m_InitialLoginDone;

	private System.Windows.Forms.Timer _connectionCheckTimer;

	private int m_conditionSortCol = -1;

	private SortOrder m_conditionSortOrder;

	private int m_holdSortCol = -1;

	private SortOrder m_holdSortOrder;

	private IContainer components;

	private AxKHOpenAPI axKHOpenAPI1;

	private Button LoginButton;

	private TableLayoutPanel tableLayoutPanel1;

	private Label ServerGubun;

	private Label label1;

	private Label UserID;

	private ComboBox AccountList;

	private TableLayoutPanel tableLayoutPanel2;

	private Label 수익률label;

	private Label 평가금label;

	private Label 매수금label;

	private Label 예수금label;

	private Label label2;

	private Label label3;

	private Label label4;

	private Label label5;

	private Label label6;

	private Label 평가수익label;

	private CheckedListBox conditionCheckedListBox;

	private Button GetConditionButton;

	private DataGridView conditionFilteredGridView;

	private TextBox logTextBox;

	private Button ATStartButton;

	private Chart chart1;

	private Label chartYLabel;

	private Panel panel1;

	private Panel panel3;

	private Button ATStopButton;

	private DataGridViewTextBoxColumn 조건명;

	private DataGridViewTextBoxColumn 종목명;

	private DataGridViewTextBoxColumn 종목코드;

	private DataGridViewTextBoxColumn 현재가;

	private DataGridViewTextBoxColumn 전일대비;

	private DataGridViewTextBoxColumn 등락률;

	private DataGridViewTextBoxColumn 거래량;

	private DataGridViewTextBoxColumn 시가;

	private DataGridViewTextBoxColumn 고가;

	private DataGridViewTextBoxColumn 저가;

	private DataGridView holdJongmokGridView;

	private TableLayoutPanel tableLayoutPanel3;

	private TableLayoutPanel tableLayoutPanel4;

	private TableLayoutPanel tableLayoutPanel5;

	private Button BuyTestButton;

	private Button SellTestButton;

	private TextBox testCode;

	private TextBox testPrice;

	private TextBox testAmount;

	public Form1()
	{
		_dbManager = new DbManager(DB_PATH);
		_conditionManager = new ConditionManager();
		_strategyManager = new StrategyManager();
		_orderManager = new OrderManager();
		_strategyConfig = StrategyConfig.Load();
		_sellStrategyManager = new SellStrategyManager(_strategyConfig);
		InitializeComponent();
		base.Icon = CreateAppIcon();
		Text = "AutoTrading";
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
		_emergencyStopButton.Click += delegate
		{
			EmergencyStop();
		};
		base.Controls.Add(_emergencyStopButton);
		_emergencyStopButton.BringToFront();
		base.KeyPreview = true;
		base.KeyDown += delegate(object s, KeyEventArgs ev)
		{
			if (ev.KeyCode == Keys.F12)
			{
				EmergencyStop();
			}
		};
		_dashboardLabel = new Label();
		_dashboardLabel.AutoSize = false;
		_dashboardLabel.TextAlign = ContentAlignment.MiddleLeft;
		_dashboardLabel.Font = new Font("맑은 고딕", 9f, FontStyle.Regular);
		_dashboardLabel.ForeColor = Color.FromArgb(200, 200, 200);
		_dashboardLabel.BackColor = Color.FromArgb(35, 40, 50);
		_dashboardLabel.Padding = new Padding(8, 0, 0, 0);
		_dashboardLabel.Text = "보유 0종목 | 총 수익금 0원";
		base.Controls.Add(_dashboardLabel);
		_dashboardLabel.BringToFront();
		SetupSplitContainers();
		ApplyUIStyle();
		DoubleBuffered = true;
		SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer, value: true);
		base.ResizeBegin += delegate
		{
			SuspendLayout();
		};
		base.ResizeEnd += delegate
		{
			ResumeLayout(performLayout: true);
			AdjustLayout();
		};
		base.Resize += delegate
		{
			if (base.WindowState != FormWindowState.Minimized)
			{
				AdjustLayout();
			}
		};
		BuyTestButton.Click += buyTestButton;
		SellTestButton.Click += sellTestButton;
		LoginButton.Click += loginButton;
		axKHOpenAPI1.OnEventConnect += onEventconect;
		axKHOpenAPI1.OnReceiveTrData += onReceiveTrData;
		axKHOpenAPI1.OnReceiveRealData += onReceiveRealData;
		GetConditionButton.Click += getConditionButton;
		axKHOpenAPI1.OnReceiveConditionVer += onReceiveConditionVer;
		conditionCheckedListBox.SelectedIndexChanged += conditionSelectedChanged;
		axKHOpenAPI1.OnReceiveTrCondition += onReceiveTrCondition;
		axKHOpenAPI1.OnReceiveRealCondition += onReceiveRealCondition;
		axKHOpenAPI1.OnReceiveChejanData += OnReceiveChejanData;
		m_PriceSeries = chart1.Series["priceSeries"];
		m_PriceSeries["PriceUpColor"] = "Red";
		m_PriceSeries["PriceDownColor"] = "Blue";
		m_VolumeSeries = chart1.Series["volumeSeries"];
		chart1.AxisViewChanged += chart1_AxisViewChanged;
		chart1.MouseMove += chart1_MouseMove;
		chart1.ChartAreas[0].AxisY.LabelStyle.Format = "#,##0";
		chart1.ChartAreas[1].AxisY.LabelStyle.Format = "#,##0,K";
		conditionFilteredGridView.DoubleClick += showChart;
		ContextMenuStrip contextMenuStrip = new ContextMenuStrip();
		ToolStripMenuItem toolStripMenuItem = new ToolStripMenuItem("복사 (Ctrl+C)");
		ToolStripMenuItem toolStripMenuItem2 = new ToolStripMenuItem("전체 선택 (Ctrl+A)");
		ToolStripMenuItem toolStripMenuItem3 = new ToolStripMenuItem("전체 로그 복사");
		toolStripMenuItem.Click += delegate
		{
			if (logTextBox.SelectionLength > 0)
			{
				Clipboard.SetText(logTextBox.SelectedText);
			}
		};
		toolStripMenuItem2.Click += delegate
		{
			logTextBox.SelectAll();
		};
		toolStripMenuItem3.Click += delegate
		{
			if (!string.IsNullOrEmpty(logTextBox.Text))
			{
				Clipboard.SetText(logTextBox.Text);
			}
		};
		contextMenuStrip.Items.AddRange(new ToolStripItem[4]
		{
			toolStripMenuItem,
			toolStripMenuItem2,
			new ToolStripSeparator(),
			toolStripMenuItem3
		});
		logTextBox.ContextMenuStrip = contextMenuStrip;
		conditionFilteredGridView.ColumnHeaderMouseClick += conditionGridView_ColumnHeaderMouseClick;
		conditionFilteredGridView.SortCompare += conditionGridView_SortCompare;
		holdJongmokGridView.ColumnHeaderMouseClick += holdGridView_ColumnHeaderMouseClick;
		holdJongmokGridView.DataError += delegate(object s, DataGridViewDataErrorEventArgs ev)
		{
			ev.ThrowException = false;
		};
		holdJongmokGridView.DataSource = _holdGridBindingSource;
		ContextMenuStrip contextMenuStrip2 = new ContextMenuStrip();
		ToolStripMenuItem toolStripMenuItem4 = new ToolStripMenuItem("전량 매도 (시장가)");
		ToolStripMenuItem toolStripMenuItem5 = new ToolStripMenuItem("수량 지정 매도");
		ToolStripMenuItem toolStripMenuItem6 = new ToolStripMenuItem("지정가 매도");
		ToolStripMenuItem toolStripMenuItem7 = new ToolStripMenuItem("차트 보기");
		ToolStripMenuItem toolStripMenuItem8 = new ToolStripMenuItem("종목코드 복사");
		toolStripMenuItem4.Click += HoldGrid_SellAll_Click;
		toolStripMenuItem5.Click += HoldGrid_SellPartial_Click;
		toolStripMenuItem6.Click += HoldGrid_SellLimit_Click;
		toolStripMenuItem7.Click += HoldGrid_ViewChart_Click;
		toolStripMenuItem8.Click += HoldGrid_CopyCode_Click;
		contextMenuStrip2.Items.AddRange(new ToolStripItem[6]
		{
			toolStripMenuItem4,
			toolStripMenuItem5,
			toolStripMenuItem6,
			new ToolStripSeparator(),
			toolStripMenuItem7,
			toolStripMenuItem8
		});
		holdJongmokGridView.ContextMenuStrip = contextMenuStrip2;
		holdJongmokGridView.CellMouseDown += delegate(object s, DataGridViewCellMouseEventArgs ev)
		{
			if (ev.Button == MouseButtons.Right && ev.RowIndex >= 0)
			{
				holdJongmokGridView.ClearSelection();
				holdJongmokGridView.Rows[ev.RowIndex].Selected = true;
				holdJongmokGridView.CurrentCell = holdJongmokGridView.Rows[ev.RowIndex].Cells[0];
			}
		};
		holdJongmokGridView.CellDoubleClick += delegate(object s, DataGridViewCellEventArgs ev)
		{
			if (ev.RowIndex >= 0 && ev.RowIndex < m_HoldingDbInfoList.Count)
			{
				string text = m_HoldingDbInfoList[ev.RowIndex].종목코드;
				if (!string.IsNullOrEmpty(text))
				{
					requestDailyChart(text);
				}
			}
		};
		ContextMenuStrip contextMenuStrip3 = new ContextMenuStrip();
		ToolStripMenuItem toolStripMenuItem9 = new ToolStripMenuItem("차트 보기");
		ToolStripMenuItem toolStripMenuItem10 = new ToolStripMenuItem("수동 매수");
		ToolStripMenuItem toolStripMenuItem11 = new ToolStripMenuItem("종목코드 복사");
		toolStripMenuItem9.Click += CondGrid_ViewChart_Click;
		toolStripMenuItem10.Click += CondGrid_ManualBuy_Click;
		toolStripMenuItem11.Click += CondGrid_CopyCode_Click;
		contextMenuStrip3.Items.AddRange(new ToolStripItem[4]
		{
			toolStripMenuItem10,
			new ToolStripSeparator(),
			toolStripMenuItem9,
			toolStripMenuItem11
		});
		conditionFilteredGridView.ContextMenuStrip = contextMenuStrip3;
		conditionFilteredGridView.CellMouseDown += delegate(object s, DataGridViewCellMouseEventArgs ev)
		{
			if (ev.Button == MouseButtons.Right && ev.RowIndex >= 0)
			{
				conditionFilteredGridView.ClearSelection();
				conditionFilteredGridView.Rows[ev.RowIndex].Selected = true;
				conditionFilteredGridView.CurrentCell = conditionFilteredGridView.Rows[ev.RowIndex].Cells[0];
			}
		};
		ATStartButton.Click += atStartButton;
		ATStopButton.Click += atStopButton;
		base.FormClosing += Form1_FormClosing;
		_balanceRefreshTimer = new System.Windows.Forms.Timer();
		_balanceRefreshTimer.Interval = 30000;
		_balanceRefreshTimer.Tick += delegate
		{
			if (m_IsMarketOpen && !string.IsNullOrEmpty(AccountList.Text))
			{
				updateAccountInfo();
			}
		};
		_sellConfirmTimer = new System.Windows.Forms.Timer();
		_sellConfirmTimer.Interval = 5000;
		_sellConfirmTimer.Tick += delegate
		{
			_sellConfirmTimer.Stop();
			if (!string.IsNullOrEmpty(AccountList.Text))
			{
				updateAccountInfo();
			}
		};
		_holdingUIRefreshTimer = new System.Windows.Forms.Timer();
		_holdingUIRefreshTimer.Interval = 3000;
		_holdingUIRefreshTimer.Tick += delegate
		{
			if (m_IsMarketOpen && m_HoldingDbInfoList.Count > 0)
			{
				RefreshHoldGrid();
			}
		};
		base.Load += delegate
		{
			AdjustLayout();
		};
		LoadDbAsync();
		axKHOpenAPI1.SetRealReg("5000", "", "215;20;214", "0");
	}

	private void sellTestButton(object sender, EventArgs e)
	{
		string text = testCode.Text.Trim();
		int result;
		int result2;
		if (string.IsNullOrEmpty(text) || text == "종목코드")
		{
			if (GetSelectedHolding() == null)
			{
				MessageBox.Show("보유종목 그리드에서 매도할 종목을 선택하거나,\n상단에 종목코드/가격/수량을 입력해주세요.", "매도 대상 없음", MessageBoxButtons.OK, MessageBoxIcon.Asterisk);
			}
			else
			{
				HoldGrid_SellAll_Click(sender, e);
			}
		}
		else if (!int.TryParse(testAmount.Text, out result) || !int.TryParse(testPrice.Text, out result2))
		{
			MessageBox.Show("수량/가격을 올바르게 입력해주세요.", "입력 오류", MessageBoxButtons.OK, MessageBoxIcon.Exclamation);
		}
		else if (MessageBox.Show($"[매도] {text} {result}주 @ {result2}원\n주문하시겠습니까?", "주문 확인", MessageBoxButtons.YesNo, MessageBoxIcon.Question) == DialogResult.Yes)
		{
			axKHOpenAPI1.SendOrder("매도주문;Test", "5004", AccountList.Text, 2, text, result, result2, "00", "");
		}
	}

	private void buyTestButton(object sender, EventArgs e)
	{
		if (!int.TryParse(testAmount.Text, out var result) || !int.TryParse(testPrice.Text, out var result2))
		{
			MessageBox.Show("수량/가격을 올바르게 입력해주세요.", "입력 오류", MessageBoxButtons.OK, MessageBoxIcon.Exclamation);
		}
		else if (MessageBox.Show($"[매수] {testCode.Text} {result}주 @ {result2}원\n주문하시겠습니까?", "주문 확인", MessageBoxButtons.YesNo, MessageBoxIcon.Question) == DialogResult.Yes)
		{
			axKHOpenAPI1.SendOrder("매수주문;Test", "5003", AccountList.Text, 1, testCode.Text, result, result2, "00", "");
		}
	}

	private void OnReceiveChejanData(object sender, _DKHOpenAPIEvents_OnReceiveChejanDataEvent e)
	{
		LogMessage("[체잔] sGubun=" + e.sGubun);
		if (!(e.sGubun == "0"))
		{
			return;
		}
		LogMessage("주문번호 " + axKHOpenAPI1.GetChejanData(9203) + " 종목코드 " + axKHOpenAPI1.GetChejanData(9001) + " 주문상태 " + axKHOpenAPI1.GetChejanData(913) + " 종목명 " + axKHOpenAPI1.GetChejanData(302).Replace(" ", string.Empty) + " 주문수량 " + axKHOpenAPI1.GetChejanData(900) + " 주문가격 " + axKHOpenAPI1.GetChejanData(901) + " 미체결수량 " + axKHOpenAPI1.GetChejanData(902) + " 원주문번호 " + axKHOpenAPI1.GetChejanData(904) + " 매매구분 " + axKHOpenAPI1.GetChejanData(906) + " 매도수구분 " + axKHOpenAPI1.GetChejanData(907) + " 체결가 " + axKHOpenAPI1.GetChejanData(910) + " 화면번호 " + axKHOpenAPI1.GetChejanData(920));
		string text = axKHOpenAPI1.GetChejanData(913).Trim();
		string value;
		if (text == "접수거부" || text == "확인거부")
		{
			string chejanData = axKHOpenAPI1.GetChejanData(9203);
			string stockCode = GetStockCode(axKHOpenAPI1.GetChejanData(9001));
			LogMessage("[주문거부] " + text + " — 주문번호: " + chejanData + " 종목: " + stockCode);
			m_dicBuyOrder.TryRemove(chejanData, out value);
			if (m_PendingBuyOrders.TryRemove(stockCode, out value))
			{
				m_BuyOrderTime.TryRemove(stockCode, out var _);
				int.TryParse(axKHOpenAPI1.GetChejanData(900), out var result);
				int.TryParse(axKHOpenAPI1.GetChejanData(901), out var result2);
				if (result > 0 && result2 > 0)
				{
					m_availableBalance += (long)result * (long)result2;
				}
			}
			m_dicSellOrder.TryRemove(chejanData, out value);
			if (m_PendingSellOrders.ContainsKey(stockCode))
			{
				m_PendingSellOrders.TryRemove(stockCode, out value);
			}
		}
		else
		{
			if (!int.TryParse(axKHOpenAPI1.GetChejanData(902), out var result3))
			{
				return;
			}
			if (result3 != 0)
			{
				if (int.TryParse(axKHOpenAPI1.GetChejanData(907), out var result4) && result4 == 2)
				{
					string chejanData2 = axKHOpenAPI1.GetChejanData(9203);
					string stockCode2 = GetStockCode(axKHOpenAPI1.GetChejanData(9001));
					if (!string.IsNullOrEmpty(chejanData2) && !m_dicBuyOrder.ContainsKey(chejanData2) && m_PendingBuyOrders.TryGetValue(stockCode2, out var value3))
					{
						m_dicBuyOrder[chejanData2] = value3;
						m_BuyOrderNo[stockCode2] = chejanData2;
						LogMessage("[접수확인] " + stockCode2 + " 주문번호=" + chejanData2 + " 등록");
					}
				}
			}
			else
			{
				if (!int.TryParse(axKHOpenAPI1.GetChejanData(907), out var result5))
				{
					return;
				}
				string chejanData3 = axKHOpenAPI1.GetChejanData(9203);
				if (result5 == 1)
				{
					LogMessage("매도완 주문번호 " + chejanData3 + " " + axKHOpenAPI1.GetChejanData(302));
					string text2 = "";
					string text3 = "";
					if (m_dicSellOrder.TryGetValue(chejanData3, out var value4))
					{
						string[] array = value4.Split(';');
						text2 = array[0];
						text3 = ((array.Length >= 2) ? array[1] : "");
					}
					else
					{
						LogMessage("매도 주문번호 미등록 — 종목코드 기반 처리: " + chejanData3);
						text2 = "수동";
						text3 = "전량매도";
					}
					int.TryParse(axKHOpenAPI1.GetChejanData(910), out var result6);
					int.TryParse(axKHOpenAPI1.GetChejanData(900), out var result7);
					string text4 = axKHOpenAPI1.GetChejanData(302).Replace(" ", string.Empty);
					string stockCode3 = GetStockCode(axKHOpenAPI1.GetChejanData(9001));
					DBInfo dBInfo = null;
					int num = -1;
					if (!string.IsNullOrEmpty(text2) && text2 != "수동")
					{
						for (int i = 0; i < m_HoldingDbInfoList.Count; i++)
						{
							if (m_HoldingDbInfoList[i].종목명 == text4 && m_HoldingDbInfoList[i].매수전략 == text2)
							{
								dBInfo = m_HoldingDbInfoList[i];
								num = i;
								break;
							}
						}
					}
					if (dBInfo == null)
					{
						for (int j = 0; j < m_HoldingDbInfoList.Count; j++)
						{
							if (m_HoldingDbInfoList[j].종목코드 == stockCode3)
							{
								dBInfo = m_HoldingDbInfoList[j];
								num = j;
								text2 = dBInfo.매수전략;
								break;
							}
						}
					}
					if (dBInfo == null)
					{
						for (int k = 0; k < m_HoldingDbInfoList.Count; k++)
						{
							if (m_HoldingDbInfoList[k].종목명 == text4)
							{
								dBInfo = m_HoldingDbInfoList[k];
								num = k;
								text2 = dBInfo.매수전략;
								break;
							}
						}
					}
					if (dBInfo == null)
					{
						LogMessage("매도완료 종목을 보유목록에서 찾을 수 없음: " + text4 + "(" + stockCode3 + ")");
						m_dicSellOrder.TryRemove(chejanData3, out value);
						m_PendingSellOrders.TryRemove(stockCode3, out value);
						return;
					}
					bool flag = result7 < dBInfo.보유수량;
					if (flag)
					{
						dBInfo.보유수량 -= result7;
						if (dBInfo.보유수량 <= 0)
						{
							flag = false;
						}
						else
						{
							if (text3 == "이평이탈")
							{
								dBInfo.이평매도수량 += result7;
								dBInfo.이평매도가격 = result6;
								HashSet<int> hashSet = new HashSet<int>();
								if (!string.IsNullOrEmpty(dBInfo.이평매도일자))
								{
									string[] array2 = dBInfo.이평매도일자.Split(',');
									for (int l = 0; l < array2.Length; l++)
									{
										if (int.TryParse(array2[l].Trim(), out var result8))
										{
											hashSet.Add(result8);
										}
									}
								}
								foreach (int item in _strategyConfig.EMA매도기간.OrderBy((int p) => p))
								{
									if (!hashSet.Contains(item))
									{
										dBInfo.이평매도일자 = SellStrategyManager.RecordEmaStage(dBInfo.이평매도일자, item);
										break;
									}
								}
							}
							else
							{
								dBInfo.nR절반매도 = true;
								dBInfo.nR절반매도일자 = DateTime.Now.ToString("yyyyMMdd");
								dBInfo.nR절반매도가격 = result6;
								dBInfo.nR절반매도수량 = result7;
							}
							updateHoldingDB(dBInfo);
							LogMessage($"[부분매도] {dBInfo.종목명} {text3} {result7}주 @ {result6:N0}원 (잔여 {dBInfo.보유수량}주)");
							m_TodaySellCount++;
						}
					}
					if (!flag)
					{
						dBInfo.전량매도일 = DateTime.Now.ToString("yyyyMMdd");
						dBInfo.전량매도이유 = (string.IsNullOrEmpty(text3) ? text2 : text3);
						dBInfo.매도가격 = result6;
						int num2 = 0;
						int num3 = 0;
						if (dBInfo.nR절반매도 && dBInfo.nR절반매도수량 > 0 && dBInfo.nR절반매도가격 > 0)
						{
							num2 += (dBInfo.nR절반매도가격 - dBInfo.매수가격) * dBInfo.nR절반매도수량;
							num3 += dBInfo.nR절반매도수량;
						}
						if (dBInfo.이평매도수량 > 0 && dBInfo.이평매도가격 > 0)
						{
							num2 += (dBInfo.이평매도가격 - dBInfo.매수가격) * dBInfo.이평매도수량;
							num3 += dBInfo.이평매도수량;
						}
						if (num3 > 0)
						{
							int val = dBInfo.매수수량 - num3;
							int num4 = (dBInfo.매도가격 - dBInfo.매수가격) * Math.Max(val, 0);
							dBInfo.최종수익금 = num2 + num4;
						}
						else
						{
							dBInfo.최종수익금 = (dBInfo.매도가격 - dBInfo.매수가격) * dBInfo.매수수량;
						}
						int num5 = dBInfo.매수가격 * dBInfo.매수수량;
						dBInfo.최종수익률 = ((num5 != 0) ? ((float)dBInfo.최종수익금 / (float)num5 * 100f) : 0f);
						m_HistoryDbInfoList.Add(dBInfo);
						deleteHoldingInsertHistory(dBInfo);
						if (num >= 0)
						{
							lock (m_HoldingLock)
							{
								m_HoldingDbInfoList.RemoveAt(num);
							}
						}
						if (!string.IsNullOrEmpty(dBInfo.종목코드))
						{
							axKHOpenAPI1.SetRealRemove("5007", dBInfo.종목코드);
							m_RealTimePrices.TryRemove(dBInfo.종목코드, out var _);
						}
						LogMessage($"[전량매도] {dBInfo.종목명} @ {result6:N0}원 수익률 {dBInfo.최종수익률:F2}% 수익금 {dBInfo.최종수익금:N0}원");
						m_TodaySellCount++;
					}
					RefreshHoldGrid();
					updateAccountInfo();
					m_dicSellOrder.TryRemove(chejanData3, out value);
					if (!string.IsNullOrEmpty(dBInfo.종목코드))
					{
						m_PendingSellOrders.TryRemove(dBInfo.종목코드, out value);
					}
					return;
				}
				LogMessage("매수완 주문번호 " + chejanData3 + " " + axKHOpenAPI1.GetChejanData(302));
				if (!m_dicBuyOrder.TryGetValue(chejanData3, out var value6))
				{
					LogMessage("매수 주문번호를 찾을 수 없음: " + chejanData3);
					return;
				}
				int.TryParse(axKHOpenAPI1.GetChejanData(900), out var result9);
				int.TryParse(axKHOpenAPI1.GetChejanData(910), out var result10);
				DBInfo obj = new DBInfo
				{
					종목명 = axKHOpenAPI1.GetChejanData(302).Replace(" ", string.Empty),
					종목코드 = GetStockCode(axKHOpenAPI1.GetChejanData(9001))
				};
				DateTime value2 = DateTime.Now;
				obj.매수일 = value2.ToString("yyyyMMdd");
				obj.매수전략 = value6;
				obj.전량매도일 = "";
				obj.전량매도이유 = "";
				obj.매도가격 = 0;
				obj.최종수익률 = 0f;
				obj.최종수익금 = 0;
				obj.매수수량 = result9;
				obj.보유수량 = result9;
				obj.매수가격 = result10;
				obj.로스컷단계 = 0;
				obj.로스컷가격 = 0;
				obj.보유일 = 1;
				obj.돌파매수 = false;
				obj.nR절반매도일자 = "";
				obj.nR절반매도 = false;
				obj.nR절반매도가격 = 0;
				obj.nR절반매도수량 = 0;
				obj.이평매도일자 = "";
				obj.이평매도가격 = 0;
				obj.이평매도수량 = 0;
				DBInfo dBInfo2 = obj;
				dBInfo2.로스컷가격 = (int)((double)dBInfo2.매수가격 * (1.0 - _strategyConfig.R값 / 100.0));
				lock (m_HoldingLock)
				{
					m_HoldingDbInfoList.Add(dBInfo2);
				}
				insertDB(m_HoldingTable, dBInfo2);
				if (!string.IsNullOrEmpty(dBInfo2.종목코드))
				{
					axKHOpenAPI1.SetRealReg("5007", dBInfo2.종목코드, "10;11;12;15;16;17;18", "1");
					LogMessage($"[매수완료] {dBInfo2.종목명}({dBInfo2.종목코드}) {result9}주 @ {result10:N0}원 LC={dBInfo2.로스컷가격:N0}원 → 실시간 등록");
				}
				m_TodayBuyCount++;
				RefreshHoldGrid();
				updateAccountInfo();
				m_dicBuyOrder.TryRemove(chejanData3, out value);
				if (!string.IsNullOrEmpty(dBInfo2.종목코드))
				{
					m_PendingBuyOrders.TryRemove(dBInfo2.종목코드, out value);
					m_BuyOrderTime.TryRemove(dBInfo2.종목코드, out value2);
					m_BuyOrderScreen.TryRemove(dBInfo2.종목코드, out value);
					m_BuyOrderNo.TryRemove(dBInfo2.종목코드, out value);
				}
			}
		}
	}

	private void onReceiveRealData(object sender, _DKHOpenAPIEvents_OnReceiveRealDataEvent e)
	{
		if (e.sRealType == "주식체결")
		{
			string 종목코드 = e.sRealKey;
			int.TryParse(axKHOpenAPI1.GetCommRealData(e.sRealType, 10).Replace("+", "").Replace("-", ""), out var result);
			result = Math.Abs(result);
			DBInfo dBInfo = null;
			lock (m_HoldingLock)
			{
				dBInfo = m_HoldingDbInfoList.FirstOrDefault((DBInfo h) => h.종목코드 == 종목코드);
			}
			if (dBInfo != null && result > 0)
			{
				dBInfo.현재가 = result;
				dBInfo.평가금 = result * dBInfo.보유수량;
				if (dBInfo.매수가격 > 0)
				{
					dBInfo.현재수익률 = (float)(result - dBInfo.매수가격) / (float)dBInfo.매수가격 * 100f;
					dBInfo.현재수익금 = (result - dBInfo.매수가격) * dBInfo.보유수량;
				}
				_sellStrategyManager.UpdateTrailingStop(dBInfo, result);
				int.TryParse(axKHOpenAPI1.GetCommRealData(e.sRealType, 16).Replace("+", "").Replace("-", ""), out var result2);
				int.TryParse(axKHOpenAPI1.GetCommRealData(e.sRealType, 17).Replace("+", "").Replace("-", ""), out var result3);
				int.TryParse(axKHOpenAPI1.GetCommRealData(e.sRealType, 18).Replace("+", "").Replace("-", ""), out var result4);
				long.TryParse(axKHOpenAPI1.GetCommRealData(e.sRealType, 15).Replace("+", "").Replace("-", ""), out var result5);
				int.TryParse(axKHOpenAPI1.GetCommRealData(e.sRealType, 11), out var result6);
				m_RealTimePrices[종목코드] = new RealTimePrice
				{
					종목코드 = 종목코드,
					현재가 = result,
					시가 = Math.Abs(result2),
					고가 = Math.Abs(result3),
					저가 = Math.Abs(result4),
					거래량 = Math.Abs(result5),
					전일종가 = result - result6
				};
			}
		}
		else
		{
			if (e.sRealType == "업종지수")
			{
				if (!(e.sRealKey == "001"))
				{
					return;
				}
				int.TryParse(axKHOpenAPI1.GetCommRealData(e.sRealType, 10).Replace("+", "").Replace("-", "")
					.Replace(".", ""), out var result7);
				if (result7 <= 0)
				{
					return;
				}
				m_RealtimeJisuPrice = result7;
				lock (m_MonitoringLock)
				{
					if (m_conditionCheck.TryGetValue("지수", out var value) && value.이동평균.TryGetValue("ma60", out var value2) && value2.Count > 0)
					{
						bool jisuBelowMA = m_JisuBelowMA60;
						m_JisuBelowMA60 = result7 < value2[0];
						if (m_JisuBelowMA60 && !jisuBelowMA)
						{
							LogMessage($"[지수경고] 코스피({result7}) MA60({value2[0]}) 하회 → 신규 매수 차단");
						}
						else if (!m_JisuBelowMA60 && jisuBelowMA)
						{
							LogMessage($"[지수회복] 코스피({result7}) MA60({value2[0]}) 상회 → 매수 허용");
						}
					}
					return;
				}
			}
			if (!(e.sRealType == "장시작시간"))
			{
				return;
			}
			string text = axKHOpenAPI1.GetCommRealData(e.sRealType, 215).Trim();
			LogMessage("장운영 구분 " + text + " 현재시간 " + axKHOpenAPI1.GetCommRealData(e.sRealType, 20) + " 남은시간 " + axKHOpenAPI1.GetCommRealData(e.sRealType, 214));
			switch (text)
			{
			case "3":
				m_IsMarketOpen = true;
				LogMessage("장 개시 - 보유종목 실시간 등록 및 보유일 갱신");
				if (!m_DbLoaded)
				{
					LogMessage("[대기] DB 로드 완료 대기 중...");
					for (int num = 0; num < 50; num++)
					{
						if (m_DbLoaded)
						{
							break;
						}
						Thread.Sleep(100);
					}
					if (!m_DbLoaded)
					{
						LogMessage("[경고] DB 로드 타임아웃 — 보유종목 없이 계속 진행");
					}
				}
				requestJisuInfo();
				foreach (DBInfo holdingDbInfo in m_HoldingDbInfoList)
				{
					if (!string.IsNullOrEmpty(holdingDbInfo.매수일))
					{
						try
						{
							holdingDbInfo.보유일 = (DateTime.Now.Date - DateTime.ParseExact(holdingDbInfo.매수일, "yyyyMMdd", null)).Days + 1;
						}
						catch
						{
							holdingDbInfo.보유일++;
						}
					}
					else
					{
						holdingDbInfo.보유일++;
					}
				}
				RegisterHoldingsRealTime();
				if (m_MonitoringCts != null && !m_MonitoringCts.IsCancellationRequested)
				{
					Task.Run(() => FetchHoldingsDailyData(m_MonitoringCts.Token));
				}
				StartSellMonitor();
				RefreshHoldGrid();
				break;
			case "2":
				LogMessage("장 마감 알림 - 매도 모니터 중지");
				m_IsMarketOpen = false;
				StopSellMonitor();
				break;
			case "4":
				LogMessage("장 마감 - DB 일괄 저장");
				m_IsMarketOpen = false;
				StopSellMonitor();
				updateAllHoldingDB();
				GenerateDailyReport();
				break;
			}
		}
	}

	private void requestJisuInfo()
	{
		LogMessage("requestJisuInfo");
		axKHOpenAPI1.SetInputValue("업종코드", "001");
		axKHOpenAPI1.SetInputValue("기준일자", DateTime.Now.ToString("yyyyMMdd"));
		axKHOpenAPI1.CommRqData("지수일봉조회", "OPT20006", 0, GetScrNum());
	}

	public void requestJongmokDaily(string stockCode)
	{
		LogMessage("requestJongmokDaily");
		axKHOpenAPI1.SetInputValue("종목코드", stockCode);
		axKHOpenAPI1.SetInputValue("기준일자", DateTime.Now.ToString("yyyyMMdd"));
		axKHOpenAPI1.SetInputValue("수정주가구분", "1");
		axKHOpenAPI1.GetMasterCodeName(stockCode);
		_ = 0;
		LogMessage("종목 일봉 정보요청 실패 " + axKHOpenAPI1.GetMasterCodeName(stockCode));
	}

	private void deleteHoldingInsertHistory(DBInfo dbInfo)
	{
		_dbManager.MoveToHistory(dbInfo);
	}

	private void updateHoldingDays()
	{
		List<DBInfo> holdings;
		lock (m_HoldingLock)
		{
			foreach (DBInfo holdingDbInfo in m_HoldingDbInfoList)
			{
				try
				{
					holdingDbInfo.보유일 = (DateTime.Now.Date - DateTime.ParseExact(holdingDbInfo.매수일, "yyyyMMdd", null)).Days + 1;
				}
				catch
				{
					holdingDbInfo.보유일++;
				}
			}
			holdings = m_HoldingDbInfoList.ToList();
		}
		_dbManager.UpdateAll(holdings);
	}

	private void insertDB(string tableName, DBInfo dbInfo)
	{
		if (dbInfo != null)
		{
			_dbManager.Insert(tableName, dbInfo);
		}
	}

	private void updateAllHoldingDB()
	{
		List<DBInfo> holdings;
		lock (m_HoldingLock)
		{
			holdings = m_HoldingDbInfoList.ToList();
		}
		_dbManager.UpdateAll(holdings);
	}

	private void updateHoldingDB(DBInfo holding)
	{
		_dbManager.Update(m_HoldingTable, holding);
	}

	private async Task LoadDbAsync()
	{
		await AsyncHelper.RunSafeAsync(async delegate
		{
			await Task.Run(delegate
			{
				_dbManager.EnsureTables();
				m_HoldingDbInfoList = _dbManager.LoadAll(m_HoldingTable);
				m_HistoryDbInfoList = _dbManager.LoadAll(m_HistoryTable);
			});
			RefreshHoldGrid();
			m_DbLoaded = true;
			LogMessage($"DB 로드 완료 - 보유 {m_HoldingDbInfoList.Count}건, 히스토리 {m_HistoryDbInfoList.Count}건");
		}, delegate(Exception ex)
		{
			AsyncHelper.RunOnUIThread(this, delegate
			{
				MessageBox.Show("DB 로딩 오류: " + ex.Message, "오류", MessageBoxButtons.OK, MessageBoxIcon.Hand);
			});
		});
	}

	private void RefreshHoldGrid()
	{
		List<DBInfo> list;
		lock (m_HoldingLock)
		{
			list = m_HoldingDbInfoList.ToList();
		}
		_holdGridBindingSource.DataSource = list;
		FormatHoldGrid();
		for (int i = 0; i < list.Count; i++)
		{
			if (list[i].현재수익률 < 0f)
			{
				holdJongmokGridView["현재수익률", i].Style.ForeColor = Color.Blue;
			}
			else if (list[i].현재수익률 > 0f)
			{
				holdJongmokGridView["현재수익률", i].Style.ForeColor = Color.Red;
			}
		}
		UpdateHoldingSummaryLabels(list);
		UpdateDashboard();
	}

	private void UpdateHoldingSummaryLabels(List<DBInfo> snapshot)
	{
		try
		{
			if (snapshot != null && snapshot.Count != 0)
			{
				long num = snapshot.Sum((DBInfo h) => (long)h.매수가격 * (long)h.보유수량);
				long num2 = ((IEnumerable<DBInfo>)snapshot).Sum((Func<DBInfo, long>)((DBInfo h) => h.현재수익금));
				float num3 = ((num > 0) ? ((float)num2 / (float)num * 100f) : 0f);
				평가수익label.Text = string.Format("{0}{1:N0}", (num2 >= 0) ? "+" : "", num2);
				수익률label.Text = string.Format("{0}{1:F2}%", (num3 >= 0f) ? "+" : "", num3);
				평가수익label.ForeColor = ((num2 >= 0) ? Color.FromArgb(220, 50, 50) : Color.FromArgb(50, 50, 220));
				수익률label.ForeColor = ((num3 >= 0f) ? Color.FromArgb(220, 50, 50) : Color.FromArgb(50, 50, 220));
			}
		}
		catch
		{
		}
	}

	private void UpdateDashboard()
	{
		try
		{
			int count;
			long totalProfit;
			long num;
			string text;
			lock (m_HoldingLock)
			{
				count = m_HoldingDbInfoList.Count;
				totalProfit = ((IEnumerable<DBInfo>)m_HoldingDbInfoList).Sum((Func<DBInfo, long>)((DBInfo h) => h.현재수익금));
				num = m_HoldingDbInfoList.Sum((DBInfo h) => (long)h.매수가격 * (long)h.보유수량);
				text = ((count > 0) ? string.Join(" | ", from h in m_HoldingDbInfoList
					orderby h.현재수익률 descending
					select string.Format("{0} {1}{2:F1}%", h.종목명, (h.현재수익률 >= 0f) ? "+" : "", h.현재수익률)) : "");
			}
			float num2 = ((num > 0) ? ((float)totalProfit / (float)num * 100f) : 0f);
			string text2 = (m_SellMonitorRunning ? "가동중" : "중지");
			string arg = ((totalProfit >= 0) ? "+" : "");
			string text3 = ((m_RealtimeJisuPrice <= 0) ? "—" : (m_JisuBelowMA60 ? $"▼{m_RealtimeJisuPrice}" : $"▲{m_RealtimeJisuPrice}"));
			string text4 = $"보유 {count}종목 | " + $"보유수익 {arg}{totalProfit:N0}원 ({num2:F2}%) | " + $"매수 {m_TodayBuyCount} 매도 {m_TodaySellCount} | " + "코스피 " + text3 + " | 매도모니터: " + text2 + ((count > 0) ? ("  ▸ " + text) : "");
			if (_dashboardLabel.InvokeRequired)
			{
				_dashboardLabel.BeginInvoke((Action)delegate
				{
					_dashboardLabel.Text = text4;
					_dashboardLabel.ForeColor = ((totalProfit >= 0) ? Color.FromArgb(255, 120, 120) : Color.FromArgb(100, 150, 255));
				});
			}
			else
			{
				_dashboardLabel.Text = text4;
				_dashboardLabel.ForeColor = ((totalProfit >= 0) ? Color.FromArgb(255, 120, 120) : Color.FromArgb(100, 150, 255));
			}
		}
		catch (Exception ex)
		{
			LogMessage("[Dashboard] " + ex.Message);
		}
	}

	private void GenerateDailyReport()
	{
		try
		{
			string today = DateTime.Now.ToString("yyyyMMdd");
			List<DBInfo> list = m_HistoryDbInfoList.Where((DBInfo h) => h.전량매도일 == today).ToList();
			long num = m_HoldingDbInfoList.Sum((DBInfo h) => (long)h.현재가 * (long)h.보유수량);
			long num2 = m_HoldingDbInfoList.Sum((DBInfo h) => (long)h.매수가격 * (long)h.보유수량);
			long num3 = ((IEnumerable<DBInfo>)m_HoldingDbInfoList).Sum((Func<DBInfo, long>)((DBInfo h) => h.현재수익금));
			float num4 = ((num2 > 0) ? ((float)num3 / (float)num2 * 100f) : 0f);
			long num5 = ((IEnumerable<DBInfo>)list).Sum((Func<DBInfo, long>)((DBInfo h) => h.최종수익금));
			int num6 = list.Count((DBInfo h) => h.최종수익금 > 0);
			int num7 = list.Count((DBInfo h) => h.최종수익금 <= 0);
			LogMessage("═══════════════════════════════════════");
			LogMessage($"  \ud83d\udcca 일일 리포트 ({DateTime.Now:yyyy-MM-dd})");
			LogMessage("═══════════════════════════════════════");
			LogMessage($"  매수 {m_TodayBuyCount}건 | 매도 {m_TodaySellCount}건 (전량 {list.Count}건)");
			if (list.Count > 0)
			{
				LogMessage($"  매도 승/패: {num6}승 {num7}패 (승률 {((list.Count > 0) ? ((double)num6 * 100.0 / (double)list.Count) : 0.0):F1}%)");
				LogMessage($"  금일 실현손익: {num5:N0}원");
				foreach (DBInfo item in list)
				{
					LogMessage($"    {item.종목명} {item.전량매도이유} → {item.최종수익률:F2}% ({item.최종수익금:N0}원)");
				}
			}
			LogMessage($"  보유 {m_HoldingDbInfoList.Count}종목 | 평가 {num:N0}원 | 수익금 {num3:N0}원 ({num4:F2}%)");
			foreach (DBInfo holdingDbInfo in m_HoldingDbInfoList)
			{
				LogMessage($"    {holdingDbInfo.종목명} {holdingDbInfo.현재수익률:F2}% ({holdingDbInfo.현재수익금:N0}원) D+{holdingDbInfo.보유일} LC:{holdingDbInfo.로스컷가격:N0}");
			}
			LogMessage($"  예탁자산: {m_estimatedBalance:N0}원");
			LogMessage("═══════════════════════════════════════");
			DailyAssetRecord record = new DailyAssetRecord
			{
				날짜 = today,
				추정예탁자산 = m_estimatedBalance,
				총매입금액 = num2,
				총평가금액 = num,
				보유평가손익 = num3,
				당일실현손익 = num5,
				보유종목수 = m_HoldingDbInfoList.Count,
				당일매수건수 = m_TodayBuyCount,
				당일매도건수 = list.Count,
				당일매도승수 = num6,
				당일매도패수 = num7
			};
			_dbManager.UpsertDailyAsset(record);
			LogMessage($"  [자산추이] {today} 기록 저장 완료 — 예탁자산 {m_estimatedBalance:N0}원");
			m_TodayBuyCount = 0;
			m_TodaySellCount = 0;
		}
		catch (Exception ex)
		{
			LogManager.Log("일일 리포트 생성 오류: " + ex.Message);
		}
	}

	private void RegisterHoldingsRealTime()
	{
		if (m_HoldingDbInfoList.Count != 0)
		{
			string text = string.Join(";", from h in m_HoldingDbInfoList
				select h.종목코드 into c
				where !string.IsNullOrEmpty(c)
				select c);
			if (!string.IsNullOrEmpty(text))
			{
				axKHOpenAPI1.SetRealReg("5007", text, "10;11;12;15;16;17;18", "0");
				LogMessage($"보유종목 실시간 시세 등록: {m_HoldingDbInfoList.Count}건");
			}
		}
	}

	private void ExecuteSellOrder(SellSignal signal, DBInfo holding)
	{
		if (signal != null && holding != null && signal.매도수량 > 0 && !string.IsNullOrEmpty(holding.종목코드))
		{
			int num = _sellStrategyManager.CalculateSellPrice(holding.현재가);
			if (num <= 0)
			{
				num = holding.현재가;
			}
			string text = $"매도주문;{holding.매수전략};{signal.매도유형}";
			LogMessage($"[매도주문] {holding.종목명}({holding.종목코드}) {signal.매도유형} " + $"{signal.매도수량}주 @ {num:N0}원 | {signal.매도이유}");
			if (axKHOpenAPI1.SendOrder(text, "5004", AccountList.Text, 2, holding.종목코드, signal.매도수량, num, "00", "") == 0)
			{
				m_PendingSellOrders[holding.종목코드] = text;
			}
		}
	}

	private void StartSellMonitor()
	{
		if (m_SellMonitorRunning)
		{
			return;
		}
		lock (m_HoldingLock)
		{
			foreach (DBInfo holdingDbInfo in m_HoldingDbInfoList)
			{
				if (holdingDbInfo.로스컷가격 <= 0 && holdingDbInfo.매수가격 > 0)
				{
					holdingDbInfo.로스컷가격 = (int)((double)holdingDbInfo.매수가격 * (1.0 - _strategyConfig.R값 / 100.0));
					_dbManager.Update(m_HoldingTable, holdingDbInfo);
					LogMessage($"[LC복원] {holdingDbInfo.종목명}({holdingDbInfo.종목코드}) 로스컷가격={holdingDbInfo.로스컷가격:N0}원 (매수가={holdingDbInfo.매수가격:N0}원, R={_strategyConfig.R값}%)");
				}
			}
		}
		m_SellMonitorCts = new CancellationTokenSource();
		m_SellMonitorRunning = true;
		CancellationToken token = m_SellMonitorCts.Token;
		Task.Run(async delegate
		{
			LogMessage("매도 모니터 시작");
			while (!token.IsCancellationRequested)
			{
				try
				{
					List<DBInfo> list;
					lock (m_HoldingLock)
					{
						list = m_HoldingDbInfoList.ToList();
					}
					foreach (DBInfo holding in list)
					{
						if (token.IsCancellationRequested)
						{
							break;
						}
						if (!string.IsNullOrEmpty(holding.종목코드))
						{
							m_RealTimePrices.TryGetValue(holding.종목코드, out var value);
							if (value != null)
							{
								m_Max50DayVolume.TryGetValue(holding.종목코드, out var value2);
								m_HoldingEMA.TryGetValue(holding.종목코드, out var value3);
								SellSignal signal = _sellStrategyManager.CheckSellConditions(holding, value, value2, value3);
								if (signal != null && !m_PendingSellOrders.ContainsKey(holding.종목코드))
								{
									m_PendingSellOrders[holding.종목코드] = signal.매도유형.ToString();
									BeginInvoke((Action)delegate
									{
										ExecuteSellOrder(signal, holding);
									});
									await Task.Delay(300, token);
								}
							}
						}
					}
				}
				catch (OperationCanceledException)
				{
					break;
				}
				catch (Exception ex2)
				{
					LogManager.Log("매도 모니터 오류: " + ex2.Message);
				}
				try
				{
					DateTime now = DateTime.Now;
					KeyValuePair<string, DateTime>[] array = m_BuyOrderTime.ToArray();
					for (int num = 0; num < array.Length; num++)
					{
						KeyValuePair<string, DateTime> keyValuePair = array[num];
						if ((now - keyValuePair.Value).TotalSeconds >= 300.0)
						{
							string code = keyValuePair.Key;
							if (m_PendingBuyOrders.TryRemove(code, out var _))
							{
								m_BuyOrderTime.TryRemove(code, out var _);
								BeginInvoke((Action)delegate
								{
									string value6;
									string text = (m_BuyOrderScreen.TryGetValue(code, out value6) ? value6 : "5003");
									string value7;
									string text2 = (m_BuyOrderNo.TryGetValue(code, out value7) ? value7 : "");
									LogMessage($"[미체결취소] {code} — {300}초 초과 → 매수취소 시도 (스크린={text} 원주문={text2})");
									axKHOpenAPI1.SendOrder("매수취소;타임아웃", text, AccountList.Text, 3, code, 0, 0, "03", text2);
									m_BuyOrderScreen.TryRemove(code, out var value8);
									m_BuyOrderNo.TryRemove(code, out value8);
									if (m_BuyOrderAmount.TryRemove(code, out var value9))
									{
										m_availableBalance += value9;
									}
								});
							}
						}
					}
				}
				catch (Exception ex3)
				{
					LogManager.Log("미체결 취소 오류: " + ex3.Message);
				}
				try
				{
					await Task.Delay(2000, token);
				}
				catch (OperationCanceledException)
				{
					break;
				}
			}
			m_SellMonitorRunning = false;
			LogMessage("매도 모니터 종료");
		}, token);
	}

	private void StopSellMonitor()
	{
		if (m_SellMonitorCts != null && !m_SellMonitorCts.IsCancellationRequested)
		{
			m_SellMonitorCts.Cancel();
			m_SellMonitorCts.Dispose();
			m_SellMonitorCts = null;
		}
	}

	private void EmergencyStop()
	{
		LogMessage("!!! 비상 정지 발동 !!!");
		StopSellMonitor();
		m_ConditionCts?.Cancel();
		m_MonitoringCts?.Cancel();
		try
		{
			foreach (KeyValuePair<string, string> pendingBuyOrder in m_PendingBuyOrders)
			{
				string key = pendingBuyOrder.Key;
				string value;
				string text = (m_BuyOrderScreen.TryGetValue(key, out value) ? value : "5003");
				string value2;
				string text2 = (m_BuyOrderNo.TryGetValue(key, out value2) ? value2 : "");
				LogMessage("[비상정지] 매수취소 시도: " + key + " (스크린=" + text + " 원주문=" + text2 + ")");
				axKHOpenAPI1.SendOrder("매수취소;비상정지", text, AccountList.Text, 3, key, 0, 0, "03", text2);
			}
			m_PendingBuyOrders.Clear();
		}
		catch (Exception ex)
		{
			LogMessage("매수취소 오류: " + ex.Message);
		}
		try
		{
			foreach (KeyValuePair<string, string> pendingSellOrder in m_PendingSellOrders)
			{
				string key2 = pendingSellOrder.Key;
				LogMessage("[비상정지] 매도취소 시도: " + key2);
				axKHOpenAPI1.SendOrder("매도취소;비상정지", "5004", AccountList.Text, 4, key2, 0, 0, "00", "");
			}
			m_PendingSellOrders.Clear();
		}
		catch (Exception ex2)
		{
			LogMessage("매도취소 오류: " + ex2.Message);
		}
		LogMessage("모든 자동매매 모니터 중지 + 미체결 취소 시도 완료");
		MessageBox.Show("비상 정지가 발동되었습니다.\n모든 자동매매가 중지되고 미체결 주문 취소를 시도했습니다.", "비상 정지", MessageBoxButtons.OK, MessageBoxIcon.Exclamation);
	}

	private DBInfo GetSelectedHolding()
	{
		if (holdJongmokGridView.CurrentRow == null || holdJongmokGridView.CurrentRow.Index < 0 || holdJongmokGridView.CurrentRow.Index >= m_HoldingDbInfoList.Count)
		{
			return null;
		}
		return m_HoldingDbInfoList[holdJongmokGridView.CurrentRow.Index];
	}

	private void HoldGrid_SellAll_Click(object sender, EventArgs e)
	{
		DBInfo holding = GetSelectedHolding();
		if (holding == null)
		{
			return;
		}
		if (holding.보유수량 <= 0)
		{
			MessageBox.Show("보유수량이 0입니다.", "매도 불가", MessageBoxButtons.OK, MessageBoxIcon.Exclamation);
			return;
		}
		int num = holding.보유수량;
		HoldJongmok holdJongmok = m_HoldJongmokList.FirstOrDefault((HoldJongmok h) => h.종목코드 == holding.종목코드);
		if (holdJongmok != null && int.TryParse(holdJongmok.잔고수량, out var result) && result > 0)
		{
			if (result != holding.보유수량)
			{
				LogMessage($"[잔고차이] {holding.종목명} DB={holding.보유수량} 계좌={result} → 계좌 기준 매도");
			}
			num = result;
		}
		int.TryParse(axKHOpenAPI1.GetMasterLastPrice(holding.종목코드).Replace("+", "").Replace("-", "")
			.Trim(), out var result2);
		if (result2 <= 0)
		{
			result2 = holding.현재가;
		}
		if (MessageBox.Show($"[전량 시장가 매도]\n종목: {holding.종목명} ({holding.종목코드})\n수량: {num}주\n현재가: {result2:N0}원 (시장가 주문)\n\n주문하시겠습니까?", "전량 매도 확인", MessageBoxButtons.YesNo, MessageBoxIcon.Question) == DialogResult.Yes)
		{
			m_PendingSellOrders.TryRemove(holding.종목코드, out var _);
			string text = "매도주문;수동;전량매도";
			int num2 = axKHOpenAPI1.SendOrder(text, "5004", AccountList.Text, 2, holding.종목코드, num, 0, "03", "");
			if (num2 != 0)
			{
				LogMessage($"[수동매도 실패] {holding.종목명}({holding.종목코드}) SendOrder 반환={num2}");
				MessageBox.Show($"매도 주문 실패 (에러코드: {num2})\n\n이전 미체결 주문이 남아있으면\n키움HTS에서 먼저 취소해주세요.", "주문 실패", MessageBoxButtons.OK, MessageBoxIcon.Exclamation);
			}
			else
			{
				m_PendingSellOrders[holding.종목코드] = text;
				LogMessage($"[수동매도] {holding.종목명}({holding.종목코드}) 전량 {num}주 (시장가)");
			}
		}
	}

	private void HoldGrid_SellPartial_Click(object sender, EventArgs e)
	{
		DBInfo holding = GetSelectedHolding();
		if (holding == null)
		{
			return;
		}
		int num = holding.보유수량;
		HoldJongmok holdJongmok = m_HoldJongmokList.FirstOrDefault((HoldJongmok h) => h.종목코드 == holding.종목코드);
		if (holdJongmok != null && int.TryParse(holdJongmok.잔고수량, out var result) && result > 0)
		{
			num = result;
		}
		if (num <= 0)
		{
			MessageBox.Show("보유수량이 0입니다.", "매도 불가", MessageBoxButtons.OK, MessageBoxIcon.Exclamation);
			return;
		}
		string text = Interaction.InputBox($"{holding.종목명} ({holding.종목코드})\n보유: {num}주\n\n매도할 수량을 입력하세요:", "수량 지정 매도", num.ToString());
		if (string.IsNullOrEmpty(text))
		{
			return;
		}
		if (!int.TryParse(text, out var result2) || result2 <= 0 || result2 > num)
		{
			MessageBox.Show($"유효한 수량을 입력해주세요. (1~{num})", "입력 오류", MessageBoxButtons.OK, MessageBoxIcon.Exclamation);
			return;
		}
		int.TryParse(axKHOpenAPI1.GetMasterLastPrice(holding.종목코드).Replace("+", "").Replace("-", "")
			.Trim(), out var result3);
		if (result3 <= 0)
		{
			result3 = holding.현재가;
		}
		if (MessageBox.Show($"[부분 시장가 매도]\n종목: {holding.종목명} ({holding.종목코드})\n수량: {result2}주 / 보유 {holding.보유수량}주\n현재가: {result3:N0}원 (시장가 주문)\n\n주문하시겠습니까?", "부분 매도 확인", MessageBoxButtons.YesNo, MessageBoxIcon.Question) == DialogResult.Yes)
		{
			m_PendingSellOrders.TryRemove(holding.종목코드, out var _);
			string text2 = "매도주문;수동;부분매도";
			int num2 = axKHOpenAPI1.SendOrder(text2, "5004", AccountList.Text, 2, holding.종목코드, result2, 0, "03", "");
			if (num2 != 0)
			{
				LogMessage($"[수동매도 실패] {holding.종목명}({holding.종목코드}) SendOrder 반환={num2}");
				MessageBox.Show($"매도 주문 실패 (에러코드: {num2})\n\n이전 미체결 주문이 남아있으면\n키움HTS에서 먼저 취소해주세요.", "주문 실패", MessageBoxButtons.OK, MessageBoxIcon.Exclamation);
			}
			else
			{
				m_PendingSellOrders[holding.종목코드] = text2;
				LogMessage($"[수동매도] {holding.종목명}({holding.종목코드}) {result2}주 (시장가)");
			}
		}
	}

	private void HoldGrid_SellLimit_Click(object sender, EventArgs e)
	{
		DBInfo selectedHolding = GetSelectedHolding();
		if (selectedHolding == null)
		{
			return;
		}
		if (selectedHolding.보유수량 <= 0)
		{
			MessageBox.Show("보유수량이 0입니다.", "매도 불가", MessageBoxButtons.OK, MessageBoxIcon.Exclamation);
			return;
		}
		int.TryParse(axKHOpenAPI1.GetMasterLastPrice(selectedHolding.종목코드).Replace("+", "").Replace("-", "")
			.Trim(), out var result);
		if (result <= 0)
		{
			result = selectedHolding.현재가;
		}
		string text = Interaction.InputBox($"{selectedHolding.종목명} ({selectedHolding.종목코드})\n보유: {selectedHolding.보유수량}주 | 현재가: {result:N0}원\n\n매도 수량:", "지정가 매도 - 수량", selectedHolding.보유수량.ToString());
		if (string.IsNullOrEmpty(text))
		{
			return;
		}
		if (!int.TryParse(text, out var result2) || result2 <= 0 || result2 > selectedHolding.보유수량)
		{
			MessageBox.Show($"유효한 수량을 입력해주세요. (1~{selectedHolding.보유수량})", "입력 오류", MessageBoxButtons.OK, MessageBoxIcon.Exclamation);
			return;
		}
		string text2 = Interaction.InputBox($"{selectedHolding.종목명} ({selectedHolding.종목코드})\n현재가: {result:N0}원\n\n매도 가격:", "지정가 매도 - 가격", result.ToString());
		if (string.IsNullOrEmpty(text2))
		{
			return;
		}
		if (!int.TryParse(text2, out var result3) || result3 <= 0)
		{
			MessageBox.Show("유효한 가격을 입력해주세요.", "입력 오류", MessageBoxButtons.OK, MessageBoxIcon.Exclamation);
		}
		else if (MessageBox.Show($"[지정가 매도]\n종목: {selectedHolding.종목명} ({selectedHolding.종목코드})\n수량: {result2}주\n가격: {result3:N0}원\n\n주문하시겠습니까?", "지정가 매도 확인", MessageBoxButtons.YesNo, MessageBoxIcon.Question) == DialogResult.Yes)
		{
			m_PendingSellOrders.TryRemove(selectedHolding.종목코드, out var _);
			string text3 = "매도주문;수동;지정가";
			int num = axKHOpenAPI1.SendOrder(text3, "5004", AccountList.Text, 2, selectedHolding.종목코드, result2, result3, "00", "");
			if (num != 0)
			{
				LogMessage($"[수동매도 실패] {selectedHolding.종목명}({selectedHolding.종목코드}) SendOrder 반환={num}");
				MessageBox.Show($"매도 주문 실패 (에러코드: {num})", "주문 실패", MessageBoxButtons.OK, MessageBoxIcon.Exclamation);
				return;
			}
			m_PendingSellOrders[selectedHolding.종목코드] = text3;
			LogMessage($"[수동매도] {selectedHolding.종목명}({selectedHolding.종목코드}) {result2}주 @ {result3:N0}원 (지정가)");
		}
	}

	private void HoldGrid_ViewChart_Click(object sender, EventArgs e)
	{
		DBInfo selectedHolding = GetSelectedHolding();
		if (selectedHolding != null && !string.IsNullOrEmpty(selectedHolding.종목코드))
		{
			requestDailyChart(selectedHolding.종목코드);
		}
	}

	private void HoldGrid_CopyCode_Click(object sender, EventArgs e)
	{
		DBInfo selectedHolding = GetSelectedHolding();
		if (selectedHolding != null && !string.IsNullOrEmpty(selectedHolding.종목코드))
		{
			Clipboard.SetText(selectedHolding.종목코드);
		}
	}

	private void CondGrid_ViewChart_Click(object sender, EventArgs e)
	{
		if (conditionFilteredGridView.CurrentRow != null)
		{
			string text = conditionFilteredGridView.CurrentRow.Cells["종목코드"].Value?.ToString() ?? "";
			if (!string.IsNullOrEmpty(text))
			{
				requestDailyChart(text);
			}
		}
	}

	private void CondGrid_ManualBuy_Click(object sender, EventArgs e)
	{
		if (conditionFilteredGridView.CurrentRow == null)
		{
			return;
		}
		string text = conditionFilteredGridView.CurrentRow.Cells["종목코드"].Value?.ToString() ?? "";
		string text2 = conditionFilteredGridView.CurrentRow.Cells["종목명"].Value?.ToString() ?? "";
		if (string.IsNullOrEmpty(text))
		{
			return;
		}
		int.TryParse(axKHOpenAPI1.GetMasterLastPrice(text).Replace("+", "").Replace("-", "")
			.Trim(), out var result);
		if (result <= 0)
		{
			return;
		}
		int num = _sellStrategyManager.CalculateBuyPrice(result);
		int num2 = _strategyConfig.종목당최대투자금 / num;
		if (num2 <= 0)
		{
			MessageBox.Show($"투자금({_strategyConfig.종목당최대투자금:N0}) 대비 가격({num:N0}) 초과", "매수 불가", MessageBoxButtons.OK, MessageBoxIcon.Exclamation);
			return;
		}
		string text3 = Interaction.InputBox($"{text2} ({text})\n현재가: {result:N0}원 | 매수가: {num:N0}원\n\n매수 수량:", "수동 매수 - 수량", num2.ToString());
		if (!string.IsNullOrEmpty(text3))
		{
			if (!int.TryParse(text3, out var result2) || result2 <= 0)
			{
				MessageBox.Show("유효한 수량을 입력해주세요.", "입력 오류", MessageBoxButtons.OK, MessageBoxIcon.Exclamation);
			}
			else if (MessageBox.Show($"[수동 매수]\n종목: {text2} ({text})\n수량: {result2}주\n매수가: {num:N0}원\n총액: {(long)num * (long)result2:N0}원\n\n주문하시겠습니까?", "수동 매수 확인", MessageBoxButtons.YesNo, MessageBoxIcon.Question) == DialogResult.Yes)
			{
				m_PendingBuyOrders[text] = "수동매수";
				axKHOpenAPI1.SendOrder("매수주문;수동", "5003", AccountList.Text, 1, text, result2, num, "00", "");
				LogMessage($"[수동매수] {text2}({text}) {result2}주 @ {num:N0}원");
			}
		}
	}

	private void CondGrid_CopyCode_Click(object sender, EventArgs e)
	{
		if (conditionFilteredGridView.CurrentRow != null)
		{
			string value = conditionFilteredGridView.CurrentRow.Cells["종목코드"].Value?.ToString() ?? "";
			if (!string.IsNullOrEmpty(value))
			{
				Clipboard.SetText(value);
			}
		}
	}

	private void TryAutoBuy(string 종목코드, string 종목명, string 조건명)
	{
		if (!m_IsMarketOpen)
		{
			LogMessage("[매수스킵] " + 종목명 + "(" + 종목코드 + ") — 장 운영시간 아님");
			return;
		}
		try
		{
			string masterStockState = axKHOpenAPI1.GetMasterStockState(종목코드);
			if (!string.IsNullOrEmpty(masterStockState) && masterStockState.Contains("ETF"))
			{
				LogMessage("[매수스킵] " + 종목명 + "(" + 종목코드 + ") — ETF 종목 제외");
				return;
			}
		}
		catch
		{
		}
		string[] obj2 = new string[19]
		{
			"금리", "채권", "국채", "회사채", "레버리지", "인버스", "선물", "옵션", "머니마켓", "단기자금",
			"CD금리", "KORIBOR", "통안채", "국고채", "하이일드", "크레딧", "BOND", "TREASURY", "금현물"
		};
		string text = 종목명.ToUpper();
		string[] array = obj2;
		foreach (string text2 in array)
		{
			if (text.Contains(text2.ToUpper()))
			{
				LogMessage("[매수스킵] " + 종목명 + "(" + 종목코드 + ") — 비주식 종목 제외 (" + text2 + ")");
				return;
			}
		}
		array = new string[13]
		{
			"KODEX", "TIGER", "RISE", "HANARO", "ACE ", "SOL ", "PLUS ", "1Q ", "KIWOOM", "ARIRANG",
			"TIMEFOLIO", "TIME Korea", "KB "
		};
		foreach (string text3 in array)
		{
			if (text.StartsWith(text3.ToUpper()))
			{
				LogMessage("[매수스킵] " + 종목명 + "(" + 종목코드 + ") — ETF 제외 (" + text3.Trim() + ")");
				return;
			}
		}
		bool flag;
		int count;
		lock (m_HoldingLock)
		{
			flag = m_HoldingDbInfoList.Any((DBInfo h) => h.종목코드 == 종목코드);
			count = m_HoldingDbInfoList.Count;
		}
		if (flag)
		{
			LogMessage("[매수스킵] " + 종목명 + "(" + 종목코드 + ") — 이미 보유 중");
			return;
		}
		DateTime value;
		if (_strategyConfig.재매수금지기간 > 0)
		{
			DBInfo dBInfo = (from h in m_HistoryDbInfoList
				where h.종목코드 == 종목코드 && !string.IsNullOrEmpty(h.전량매도일)
				orderby h.전량매도일 descending
				select h).FirstOrDefault();
			if (dBInfo != null)
			{
				try
				{
					DateTime dateTime = DateTime.ParseExact(dBInfo.전량매도일, "yyyyMMdd", null);
					value = DateTime.Now;
					int days = (value.Date - dateTime.Date).Days;
					if (days < _strategyConfig.재매수금지기간)
					{
						LogMessage($"[매수스킵] {종목명}({종목코드}) — 재매수금지 ({days}/{_strategyConfig.재매수금지기간}일)");
						return;
					}
				}
				catch
				{
				}
			}
		}
		if (m_JisuBelowMA60 && m_RealtimeJisuPrice > 0)
		{
			LogMessage($"[매수스킵] {종목명}({종목코드}) — 실시간 코스피({m_RealtimeJisuPrice}) MA60 하회 중");
			return;
		}
		lock (m_MonitoringLock)
		{
			if (!m_conditionCheck.TryGetValue("지수", out var value2) || value2.priceInfoList.Count < 2 || !value2.이동평균.TryGetValue("ma60", out var value3) || value3.Count <= 0)
			{
				LogMessage("[매수스킵] " + 종목명 + "(" + 종목코드 + ") — 코스피 지수 데이터 미수신");
				return;
			}
			int 종가 = value2.priceInfoList[0].종가;
			int num = value3[0];
			int 종가2 = value2.priceInfoList[1].종가;
			if (종가 < num)
			{
				LogMessage($"[매수스킵] {종목명}({종목코드}) — 코스피({종가}) < MA60({num})");
				return;
			}
			if (종가 < (int)((double)종가2 * 0.96))
			{
				LogMessage($"[매수스킵] {종목명}({종목코드}) — 코스피 전일대비 -4%↓ ({종가} vs 전일{종가2})");
				return;
			}
		}
		if (count >= _strategyConfig.최대보유종목수)
		{
			LogMessage($"[매수스킵] {종목명}({종목코드}) — 최대보유 {_strategyConfig.최대보유종목수}종목 도달");
			return;
		}
		if (m_PendingBuyOrders.ContainsKey(종목코드))
		{
			LogMessage("[매수스킵] " + 종목명 + "(" + 종목코드 + ") — 매수 주문 진행 중");
			return;
		}
		if (!int.TryParse(axKHOpenAPI1.GetMasterLastPrice(종목코드).Replace("+", "").Replace("-", "")
			.Trim(), out var result) || result <= 0)
		{
			LogMessage("[매수스킵] " + 종목명 + "(" + 종목코드 + ") — 현재가 조회 실패");
			return;
		}
		int num2 = _sellStrategyManager.CalculateBuyPrice(result);
		if (num2 <= 0)
		{
			num2 = result;
		}
		int num3 = _strategyConfig.종목당최대투자금 / num2;
		if (num3 <= 0)
		{
			LogMessage($"[매수스킵] {종목명}({종목코드}) — 투자금({_strategyConfig.종목당최대투자금:N0}) 대비 가격({num2:N0}) 초과");
			return;
		}
		long num4 = (long)num2 * (long)num3;
		string value7;
		if (num4 > m_availableBalance)
		{
			if (m_BuyOrderTime.Count > 0)
			{
				string key = m_BuyOrderTime.OrderBy((KeyValuePair<string, DateTime> x) => x.Value).First().Key;
				m_PendingBuyOrders.TryRemove(key, out var _);
				m_BuyOrderTime.TryRemove(key, out value);
				string masterCodeName = axKHOpenAPI1.GetMasterCodeName(key);
				string value5;
				string text4 = (m_BuyOrderScreen.TryGetValue(key, out value5) ? value5 : "5003");
				string value6;
				string sOrgOrderNo = (m_BuyOrderNo.TryGetValue(key, out value6) ? value6 : "");
				LogMessage("[미체결취소] " + masterCodeName + "(" + key + ") — 신규 매수(" + 종목명 + ") 위해 기존 미체결 취소 (스크린=" + text4 + ")");
				axKHOpenAPI1.SendOrder("매수취소;자금확보", text4, AccountList.Text, 3, key, 0, 0, "03", sOrgOrderNo);
				m_BuyOrderScreen.TryRemove(key, out value7);
				m_BuyOrderNo.TryRemove(key, out value7);
			}
			LogMessage($"[매수스킵] {종목명}({종목코드}) — 잔고부족 (주문={num4:N0} vs 주문가능={m_availableBalance:N0})");
			return;
		}
		m_availableBalance -= num4;
		if (m_availableBalance < 0)
		{
			m_availableBalance = 0L;
		}
		int num5 = Interlocked.Increment(ref m_buyScreenIdx) % 90 + 10;
		string text5 = (5000 + num5).ToString("D4");
		string sRQName = "매수주문;" + 조건명 + ";" + 종목코드;
		LogMessage($"[자동매수] {종목명}({종목코드}) {num3}주 시장가 | 조건식: {조건명} | 스크린={text5} 계좌={AccountList.Text}");
		m_PendingBuyOrders[종목코드] = 조건명;
		m_BuyOrderTime[종목코드] = DateTime.Now;
		m_BuyOrderScreen[종목코드] = text5;
		m_BuyOrderAmount[종목코드] = num4;
		int num6 = axKHOpenAPI1.SendOrder(sRQName, text5, AccountList.Text, 1, 종목코드, num3, 0, "03", "");
		if (num6 != 0)
		{
			LogMessage($"[매수실패] SendOrder 오류 ret={num6}: {종목명}({종목코드}) {num3}주 스크린={text5}");
			m_availableBalance += num4;
			m_PendingBuyOrders.TryRemove(종목코드, out value7);
			m_BuyOrderTime.TryRemove(종목코드, out value);
			m_BuyOrderScreen.TryRemove(종목코드, out value7);
			m_BuyOrderAmount.TryRemove(종목코드, out var _);
		}
	}

	private async Task FetchHoldingsDailyData(CancellationToken token)
	{
		foreach (DBInfo holdingDbInfo in m_HoldingDbInfoList)
		{
			if (!string.IsNullOrEmpty(holdingDbInfo.종목코드))
			{
				m_holdingDailyQueue.Enqueue(holdingDbInfo.종목코드);
			}
		}
		LogMessage($"보유종목 일봉 데이터 조회 시작: {m_holdingDailyQueue.Count}건");
		while (true)
		{
			if (token.IsCancellationRequested || !m_holdingDailyQueue.TryDequeue(out var 종목코드))
			{
				break;
			}
			try
			{
				Invoke((Action)delegate
				{
					string masterCodeName = axKHOpenAPI1.GetMasterCodeName(종목코드);
					axKHOpenAPI1.SetInputValue("종목코드", 종목코드);
					axKHOpenAPI1.SetInputValue("기준일자", DateTime.Now.ToString("yyyyMMdd"));
					axKHOpenAPI1.SetInputValue("수정주가구분", "1");
					axKHOpenAPI1.CommRqData("보유종목일봉조회;" + masterCodeName + ";" + 종목코드, "OPT10081", 0, "5005");
				});
			}
			catch (Exception ex)
			{
				LogManager.Log("일봉 조회 오류: " + ex.Message);
			}
			try
			{
				await Task.Delay(3600, token);
			}
			catch (OperationCanceledException)
			{
				break;
			}
		}
		LogMessage($"보유종목 일봉 데이터 조회 완료 (캐싱 {m_Max50DayVolume.Count}건)");
	}

	private void showChart(object sender, EventArgs e)
	{
		string text = "";
		if (sender.Equals(conditionFilteredGridView))
		{
			if (conditionFilteredGridView.CurrentRow == null)
			{
				return;
			}
			text = conditionFilteredGridView.CurrentRow.Cells["종목코드"].Value?.ToString() ?? "";
		}
		if (!string.IsNullOrEmpty(text))
		{
			requestDailyChart(text);
		}
	}

	private void onReceiveRealCondition(object sender, _DKHOpenAPIEvents_OnReceiveRealConditionEvent e)
	{
		LogMessage("onReceiveRealCondition");
		string _종목코드 = GetStockCode(e.sTrCode);
		string _종목명 = axKHOpenAPI1.GetMasterCodeName(_종목코드);
		string _조건명 = e.strConditionName;
		string strConditionIndex = e.strConditionIndex;
		if (!int.TryParse(strConditionIndex, out var result) || result < 0 || result >= m_ConditionList.Count)
		{
			LogMessage("잘못된 조건식 인덱스: " + strConditionIndex);
			return;
		}
		if (e.strType.Equals("I"))
		{
			LogMessage("편입 " + _조건명 + " " + _종목코드 + " " + _종목명);
			bool flag = false;
			lock (m_ConditionLock)
			{
				foreach (StockItemInfo stockItem in m_ConditionList[result].stockItemList)
				{
					if (stockItem.종목코드 == _종목코드)
					{
						LogMessage("이미 있음 : " + _조건명 + " " + _종목코드 + " " + _종목명);
						flag = true;
						break;
					}
				}
				if (!flag)
				{
					m_ConditionList[result].stockItemList.Add(new StockItemInfo
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
					TryAutoBuy(_종목코드, _종목명, _조건명);
				}
				return;
			}
		}
		if (!e.strType.Equals("D"))
		{
			return;
		}
		LogMessage("편출 " + _조건명 + " " + _종목코드 + " " + _종목명);
		lock (m_ConditionLock)
		{
			m_ConditionList[result].stockItemList.RemoveAll((StockItemInfo p) => p.종목코드 == _종목코드);
			bool isDelete = false;
			Action action = delegate
			{
				for (int num = conditionFilteredGridView.Rows.Count - 1; num >= 0; num--)
				{
					DataGridViewRow dataGridViewRow = conditionFilteredGridView.Rows[num];
					if (!dataGridViewRow.IsNewRow)
					{
						string text = dataGridViewRow.Cells["조건명"].Value?.ToString();
						string text2 = dataGridViewRow.Cells["종목코드"].Value?.ToString();
						if (_조건명 == text && _종목코드 == text2)
						{
							LogMessage("편출 종목 삭제 완료 " + _종목명);
							conditionFilteredGridView.Rows.RemoveAt(num);
							isDelete = true;
							break;
						}
					}
				}
			};
			if (conditionFilteredGridView.InvokeRequired)
			{
				conditionFilteredGridView.Invoke(action);
			}
			else
			{
				action();
			}
			if (!isDelete)
			{
				LogMessage("편출 종목 이미 삭제됨");
			}
		}
	}

	private async void atStopButton(object sender, EventArgs e)
	{
		if (conditionCheckedListBox.CheckedItems.Count <= 0)
		{
			return;
		}
		LogMessage("자동 매매 종료!!");
		m_ConditionCts?.Cancel();
		ATStopButton.Visible = false;
		CheckedListBox.CheckedIndexCollection checkedIndices = conditionCheckedListBox.CheckedIndices;
		foreach (int item in checkedIndices)
		{
			axKHOpenAPI1.SendConditionStop("5006", m_ConditionList[item].조건식이름, m_ConditionList[item].조건식번호);
			m_ConditionList[item].실시간등록여부 = false;
			m_ConditionList[item].stockItemList.Clear();
			await Task.Delay(500);
		}
		conditionCheckedListBox.Enabled = true;
		ATStartButton.Visible = true;
		ATStartButton.BringToFront();
	}

	private void Form1_FormClosing(object sender, FormClosingEventArgs e)
	{
		_balanceRefreshTimer?.Stop();
		_balanceRefreshTimer?.Dispose();
		_holdingUIRefreshTimer?.Stop();
		_holdingUIRefreshTimer?.Dispose();
		m_ConditionCts?.Cancel();
		m_ConditionCts?.Dispose();
		m_MonitoringCts?.Cancel();
		m_MonitoringCts?.Dispose();
		StopSellMonitor();
		try
		{
			for (int i = 0; i < m_ConditionList.Count; i++)
			{
				if (m_ConditionList[i].실시간등록여부)
				{
					axKHOpenAPI1.SendConditionStop("5006", m_ConditionList[i].조건식이름, m_ConditionList[i].조건식번호);
				}
			}
		}
		catch
		{
		}
		try
		{
			updateAllHoldingDB();
		}
		catch
		{
		}
		try
		{
			_strategyConfig.Save();
		}
		catch
		{
		}
	}

	private async void atStartButton(object sender, EventArgs e)
	{
		if (conditionCheckedListBox.CheckedItems.Count > 0)
		{
			ATStartButton.Visible = false;
			conditionFilteredGridView.Rows.Clear();
			conditionFilteredGridView.Refresh();
			conditionCheckedListBox.Enabled = false;
			CheckedListBox.CheckedIndexCollection checkedIndices = conditionCheckedListBox.CheckedIndices;
			foreach (int index in checkedIndices)
			{
				int retryCount = 0;
				bool registered = false;
				while (retryCount < 5)
				{
					if (axKHOpenAPI1.SendCondition("5006", m_ConditionList[index].조건식이름, m_ConditionList[index].조건식번호, 1) > 0)
					{
						LogMessage("자동 매매 시작!! " + m_ConditionList[index].조건식이름);
						m_ConditionList[index].stockItemList = new List<StockItemInfo>();
						m_ConditionList[index].실시간등록여부 = true;
						registered = true;
						break;
					}
					retryCount++;
					LogMessage($"자동 매매 조건검색 대기!! ({retryCount}/{5})");
					await Task.Delay(10000);
				}
				if (!registered)
				{
					LogMessage($"[경고] 조건식 등록 실패: {m_ConditionList[index].조건식이름} — {5}회 재시도 초과");
				}
				await Task.Delay(1000);
			}
			LogMessage("자동 매매 시작!!");
			TimeSpan timeOfDay = DateTime.Now.TimeOfDay;
			if (!m_IsMarketOpen && timeOfDay >= new TimeSpan(9, 0, 0) && timeOfDay < new TimeSpan(15, 30, 0))
			{
				m_IsMarketOpen = true;
				LogMessage("[장중 복원] 자동매매 재시작 — m_IsMarketOpen = true");
				if (!m_SellMonitorRunning)
				{
					StartSellMonitor();
				}
			}
			ATStopButton.Visible = true;
			ATStopButton.BringToFront();
			m_ConditionCts = new CancellationTokenSource();
			Task.Run(() => realConditionUpdater(m_ConditionCts.Token));
		}
		else
		{
			LogMessage("체크된 조건식이 없습니다.");
		}
	}

	private async Task DelayAsync(int ms, CancellationToken token = default(CancellationToken))
	{
		await Task.Delay(ms, token);
	}

	public async Task realConditionUpdater(CancellationToken token)
	{
		while (!token.IsCancellationRequested)
		{
			foreach (ConditionInfo condition in m_ConditionList)
			{
				if (token.IsCancellationRequested)
				{
					break;
				}
				if (!condition.실시간등록여부)
				{
					continue;
				}
				List<string> codeListAll = new List<string>();
				lock (m_ConditionLock)
				{
					foreach (StockItemInfo stockItem in condition.stockItemList)
					{
						codeListAll.Add(stockItem.종목코드);
						if (!m_monitoring.ContainsKey(stockItem.종목코드))
						{
							m_monitoring.Add(stockItem.종목코드, stockItem.종목명);
							m_monitoringQueue.Enqueue(stockItem.종목코드);
						}
					}
				}
				for (int batchStart = 0; batchStart < codeListAll.Count; batchStart += 100)
				{
					if (token.IsCancellationRequested)
					{
						break;
					}
					List<string> batch = codeListAll.Skip(batchStart).Take(100).ToList();
					string codeList = string.Join(";", batch) + ";";
					Invoke((Action)delegate
					{
						axKHOpenAPI1.CommKwRqData(codeList, 0, batch.Count, 0, "조건식종목정보;" + condition.조건식이름 + ";" + condition.조건식번호, "5002");
					});
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
				Invoke((Action)delegate
				{
					axKHOpenAPI1.SetInputValue("종목코드", _종목코드);
					axKHOpenAPI1.SetInputValue("기준일자", DateTime.Now.ToString("yyyyMMdd"));
					axKHOpenAPI1.SetInputValue("수정주가구분", "1");
					string masterCodeName = axKHOpenAPI1.GetMasterCodeName(_종목코드);
					axKHOpenAPI1.CommRqData("종목일봉차트조회;" + masterCodeName, "OPT10081", 0, "5005");
				});
			}
			await DelayAsync(5000, token);
		}
	}

	private void requestDailyChart(string stockCode)
	{
		axKHOpenAPI1.SetInputValue("종목코드", stockCode);
		axKHOpenAPI1.SetInputValue("기준일자", DateTime.Now.ToString("yyyyMMdd"));
		axKHOpenAPI1.SetInputValue("수정주가구분", "1");
		if (axKHOpenAPI1.CommRqData("주식일봉차트조회", "OPT10081", 0, "5005") == 0)
		{
			Console.WriteLine("주식 일봉 정보요청 성공");
		}
		else
		{
			Console.WriteLine("주식 일봉 정보요청 실패");
		}
	}

	private void requestStockInfo(string stockCode)
	{
		axKHOpenAPI1.SetInputValue("종목코드", stockCode);
		if (axKHOpenAPI1.CommRqData("JM_주식기본정보요청", "OPT10001", 0, GetScrNum()) == 0)
		{
			Console.WriteLine("주식기본정보요청 성공");
		}
		else
		{
			Console.WriteLine("주식기본정보요청 실패");
		}
	}

	private void chart1_MouseMove(object sender, MouseEventArgs e)
	{
		ChartArea chartArea = chart1.ChartAreas[0];
		ChartArea chartArea2 = chart1.ChartAreas[1];
		Point point = new Point(e.X, e.Y);
		if ((double)chart1.Height * 0.05 < (double)e.Y && (double)e.Y < (double)chart1.Height * 0.57)
		{
			chartYLabel.Visible = true;
			chartArea.CursorX.SetCursorPixelPosition(point, roundToBoundary: true);
			chartArea.CursorY.SetCursorPixelPosition(point, roundToBoundary: true);
			chartYLabel.Text = $"{chartArea.CursorY.Position:#,###}";
			chartYLabel.Location = new Point((int)((double)chart1.Width * 0.9), e.Y - chartYLabel.Height / 2);
		}
		else if ((double)chart1.Height * 0.605 < (double)e.Y && (double)e.Y < (double)chart1.Height * 0.915)
		{
			chartYLabel.Visible = true;
			chartArea2.CursorX.SetCursorPixelPosition(point, roundToBoundary: true);
			chartArea2.CursorY.SetCursorPixelPosition(point, roundToBoundary: true);
			chartYLabel.Text = $"{chartArea2.CursorY.Position:#,###}";
			chartYLabel.Location = new Point((int)((double)chart1.Width * 0.9), e.Y - chartYLabel.Height / 2);
		}
		else
		{
			chartYLabel.Visible = false;
		}
	}

	private void chart1_AxisViewChanged(object sender, ViewEventArgs e)
	{
		if (!sender.Equals(chart1) || m_PriceInfoList == null)
		{
			return;
		}
		try
		{
			int num = (int)e.Axis.ScaleView.ViewMinimum;
			int num2 = (int)e.Axis.ScaleView.ViewMaximum;
			int num3 = 0;
			int num4 = int.MaxValue;
			int num5 = 0;
			int num6 = int.MaxValue;
			for (int i = num - 1; i < num2 && i < m_PriceInfoList.Count; i++)
			{
				if (i < 0)
				{
					i = 0;
				}
				if (m_PriceInfoList[i].고가 > num3)
				{
					num3 = m_PriceInfoList[i].고가;
				}
				if (m_PriceInfoList[i].저가 < num4)
				{
					num4 = m_PriceInfoList[i].저가;
				}
				if (m_PriceInfoList[i].거래량 > num5)
				{
					num5 = m_PriceInfoList[i].거래량;
				}
				if (m_PriceInfoList[i].거래량 < num6)
				{
					num6 = m_PriceInfoList[i].거래량;
				}
			}
			double num7 = 0.2 * (double)(num3 - num4);
			chart1.ChartAreas[0].AxisY.Maximum = (double)num3 + num7;
			chart1.ChartAreas[0].AxisY.Minimum = (double)num4 - num7;
			double num8 = 0.2 * (double)(num5 - num6);
			chart1.ChartAreas[1].AxisY.Maximum = (double)num5 + num8;
			if ((double)num6 - num8 > 0.0)
			{
				chart1.ChartAreas[1].AxisY.Minimum = (double)num6 - num8;
			}
			else
			{
				chart1.ChartAreas[1].AxisY.Minimum = 0.0;
			}
		}
		catch (Exception ex)
		{
			Console.WriteLine(ex.Message.ToString());
		}
	}

	private void onReceiveTrCondition(object sender, _DKHOpenAPIEvents_OnReceiveTrConditionEvent e)
	{
		LogMessage("onReceiveTrCondition");
		string text = e.strCodeList.Trim();
		string strConditionName = e.strConditionName;
		int nIndex = e.nIndex;
		if (text.Length > 0)
		{
			text = text.Remove(text.Length - 1);
		}
		_ = text.Trim().Split(';').Length;
		string[] array = text.Split(';');
		if (e.nNext == 2)
		{
			axKHOpenAPI1.SendCondition(e.sScrNo, e.strConditionName, e.nIndex, 2);
		}
		string[] array2 = array;
		foreach (string text2 in array2)
		{
			if (!(text2 == ""))
			{
				string masterCodeName = axKHOpenAPI1.GetMasterCodeName(text2);
				m_ConditionList[nIndex].stockItemList.Add(new StockItemInfo
				{
					조건명 = strConditionName,
					종목명 = masterCodeName,
					종목코드 = text2,
					현재가 = "",
					전일대비 = "",
					등락률 = "",
					거래량 = "",
					시가 = "",
					고가 = "",
					저가 = ""
				});
				continue;
			}
			break;
		}
	}

	private void conditionSelectedChanged(object sender, EventArgs e)
	{
		CheckedListBox checkedListBox = sender as CheckedListBox;
		if (!checkedListBox.Equals(conditionCheckedListBox))
		{
			return;
		}
		int selectedIndex = checkedListBox.SelectedIndex;
		if (selectedIndex < 0 || selectedIndex >= m_ConditionList.Count || checkedListBox.SelectedItem == null)
		{
			return;
		}
		checkedListBox.SelectedItem.ToString();
		if (axKHOpenAPI1.SendCondition(GetScrNum(), m_ConditionList[selectedIndex].조건식이름, m_ConditionList[selectedIndex].조건식번호, 0) > 0)
		{
			LogMessage("조건검색 성공");
			m_ConditionList[selectedIndex].stockItemList = new List<StockItemInfo>();
			conditionFilteredGridView.Rows.Clear();
			conditionFilteredGridView.Refresh();
			return;
		}
		LogMessage("조건검색 실패 (1분 대기)");
		conditionFilteredGridView.Rows.Clear();
		List<StockItemInfo> stockItemList = m_ConditionList[selectedIndex].stockItemList;
		for (int i = 0; i < stockItemList.Count; i++)
		{
			conditionFilteredGridView.Rows.Add();
			conditionFilteredGridView["조건명", conditionFilteredGridView.RowCount - 2].Value = stockItemList[i].조건명;
			conditionFilteredGridView["종목명", conditionFilteredGridView.RowCount - 2].Value = stockItemList[i].종목명;
			conditionFilteredGridView["종목코드", conditionFilteredGridView.RowCount - 2].Value = stockItemList[i].종목코드;
			conditionFilteredGridView["현재가", conditionFilteredGridView.RowCount - 2].Value = stockItemList[i].현재가;
			conditionFilteredGridView["전일대비", conditionFilteredGridView.RowCount - 2].Value = stockItemList[i].전일대비;
			conditionFilteredGridView["등락률", conditionFilteredGridView.RowCount - 2].Value = stockItemList[i].등락률;
			conditionFilteredGridView["거래량", conditionFilteredGridView.RowCount - 2].Value = stockItemList[i].거래량;
			conditionFilteredGridView["시가", conditionFilteredGridView.RowCount - 2].Value = stockItemList[i].시가;
			conditionFilteredGridView["고가", conditionFilteredGridView.RowCount - 2].Value = stockItemList[i].고가;
			conditionFilteredGridView["저가", conditionFilteredGridView.RowCount - 2].Value = stockItemList[i].저가;
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
		conditionCheckedListBox.Items.Clear();
		string[] array = axKHOpenAPI1.GetConditionNameList().Split(';');
		for (int i = 0; i < array.Length; i++)
		{
			string[] array2 = array[i].Split('^');
			if (array2.Length == 2)
			{
				m_ConditionList.Add(new ConditionInfo
				{
					조건식번호 = int.Parse(array2[0].Trim()),
					조건식이름 = array2[1].Trim()
				});
			}
		}
		m_ConditionList = m_ConditionList.OrderBy((ConditionInfo p) => p.조건식번호).ToList();
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
			int num = int.Parse(holdJongmok.잔고수량);
			int num2 = 0;
			int num3 = 0;
			lock (m_HoldingLock)
			{
				foreach (DBInfo holdingDbInfo in m_HoldingDbInfoList)
				{
					if (holdingDbInfo.종목명 == holdJongmok.종목명)
					{
						holdingDbInfo.현재가 = int.Parse(holdJongmok.현재가);
						holdingDbInfo.평가금 = holdingDbInfo.현재가 * holdingDbInfo.보유수량;
						holdingDbInfo.현재수익금 = (holdingDbInfo.현재가 - holdingDbInfo.매수가격) * holdingDbInfo.보유수량;
						holdingDbInfo.현재수익률 = ((holdingDbInfo.매수가격 > 0) ? ((float)Math.Round((float)(holdingDbInfo.현재가 - holdingDbInfo.매수가격) / (float)holdingDbInfo.매수가격 * 100f, 2)) : 0f);
						num2 += holdingDbInfo.보유수량;
						num3++;
					}
				}
			}
			if (num == num2)
			{
				if (num3 != 1)
				{
				}
				continue;
			}
			LogMessage("HoldJongmokSyncWithDB - 계좌/DB 잔고 불일치 " + holdJongmok.종목명 + "계좌 : " + num + " / DB : " + num2);
			lock (m_HoldingLock)
			{
				if (num3 == 1)
				{
					DBInfo dBInfo = m_HoldingDbInfoList.FirstOrDefault((DBInfo h) => h.종목명 == holdJongmok.종목명);
					if (dBInfo != null && num >= 0)
					{
						LogMessage($"[잔고동기화] {holdJongmok.종목명} DB 보유수량 {dBInfo.보유수량} → {num}");
						dBInfo.보유수량 = num;
						if (num <= 0)
						{
							m_HoldingDbInfoList.Remove(dBInfo);
							_dbManager.MoveToHistory(dBInfo);
							LogMessage("[잔고동기화] " + dBInfo.종목명 + "(" + dBInfo.매수전략 + ") 보유수량 0 → 히스토리로 이동");
						}
						else
						{
							updateHoldingDB(dBInfo);
						}
					}
				}
				else
				{
					if (num3 <= 1)
					{
						continue;
					}
					int num4 = num2 - num;
					foreach (DBInfo item in (from h in m_HoldingDbInfoList
						where h.종목명 == holdJongmok.종목명
						orderby h.매수전략 == "계좌복원" descending, h.보유수량
						select h).ToList())
					{
						if (num4 <= 0)
						{
							break;
						}
						if (item.보유수량 <= num4)
						{
							num4 -= item.보유수량;
							LogMessage($"[잔고동기화] {item.종목명}({item.매수전략}) 보유수량 {item.보유수량} → 0 (중복 제거)");
							item.보유수량 = 0;
							continue;
						}
						int num5 = item.보유수량 - num4;
						LogMessage($"[잔고동기화] {item.종목명}({item.매수전략}) 보유수량 {item.보유수량} → {num5} (다중전략)");
						item.보유수량 = num5;
						num4 = 0;
					}
					foreach (DBInfo item2 in m_HoldingDbInfoList.Where((DBInfo h) => h.종목명 == holdJongmok.종목명 && h.보유수량 <= 0).ToList())
					{
						m_HoldingDbInfoList.Remove(item2);
						_dbManager.MoveToHistory(item2);
						LogMessage("[중복제거] " + item2.종목명 + "(" + item2.매수전략 + ") 보유수량 0 → 히스토리로 이동");
					}
					foreach (DBInfo item3 in m_HoldingDbInfoList.Where((DBInfo h) => h.종목명 == holdJongmok.종목명))
					{
						item3.평가금 = item3.현재가 * item3.보유수량;
						item3.현재수익금 = (item3.현재가 - item3.매수가격) * item3.보유수량;
						updateHoldingDB(item3);
					}
					continue;
				}
			}
		}
		foreach (HoldJongmok accountItem in m_HoldJongmokList)
		{
			if (string.IsNullOrEmpty(accountItem.종목코드) || !int.TryParse(accountItem.잔고수량, out var result) || result <= 0)
			{
				continue;
			}
			bool flag;
			lock (m_HoldingLock)
			{
				flag = m_HoldingDbInfoList.Any((DBInfo h) => h.종목코드 == accountItem.종목코드 || h.종목명 == accountItem.종목명);
			}
			if (!flag)
			{
				int.TryParse(accountItem.현재가, out var result2);
				double.TryParse(accountItem.매입금액, out var result3);
				int num6 = ((result > 0) ? ((int)(result3 / (double)result)) : result2);
				if (num6 <= 0)
				{
					num6 = result2;
				}
				string text = _dbManager.FindLastStrategy(accountItem.종목코드);
				string text2 = _dbManager.FindLastBuyDate(accountItem.종목코드);
				string text3 = (string.IsNullOrEmpty(text) ? "계좌복원" : text);
				string text4 = ((!string.IsNullOrEmpty(text2)) ? text2 : DateTime.Now.ToString("yyyyMMdd"));
				int num7 = 1;
				if (DateTime.TryParseExact(text4, "yyyyMMdd", null, DateTimeStyles.None, out var result4))
				{
					num7 = Math.Max(1, (int)(DateTime.Now - result4).TotalDays + 1);
				}
				int num8 = (int)((double)num6 * (1.0 - _strategyConfig.R값 / 100.0));
				DBInfo dBInfo2 = new DBInfo
				{
					종목명 = accountItem.종목명,
					종목코드 = accountItem.종목코드,
					매수일 = text4,
					매수전략 = text3,
					매수수량 = result,
					보유수량 = result,
					매수가격 = num6,
					현재가 = result2,
					평가금 = result2 * result,
					현재수익금 = (result2 - num6) * result,
					현재수익률 = ((num6 > 0) ? ((float)(result2 - num6) / (float)num6 * 100f) : 0f),
					보유일 = num7,
					로스컷단계 = 0,
					로스컷가격 = num8
				};
				lock (m_HoldingLock)
				{
					m_HoldingDbInfoList.Add(dBInfo2);
				}
				insertDB(m_HoldingTable, dBInfo2);
				LogMessage("[계좌복원] " + accountItem.종목명 + "(" + accountItem.종목코드 + ") " + $"{result}주 매입단가 {num6:N0}원 LC={num8:N0}원 D+{num7} — 전략:{text3} 매수일:{text4}");
			}
		}
		if (m_HoldJongmokList.Count <= 0 || m_PendingSellOrders.Count <= 0)
		{
			return;
		}
		List<DBInfo> list = new List<DBInfo>();
		lock (m_HoldingLock)
		{
			foreach (DBInfo dbItem in m_HoldingDbInfoList.ToList())
			{
				if (!string.IsNullOrEmpty(dbItem.종목코드) && m_PendingSellOrders.ContainsKey(dbItem.종목코드) && m_HoldJongmokList.FirstOrDefault((HoldJongmok h) => h.종목코드 == dbItem.종목코드 || h.종목명 == dbItem.종목명) == null)
				{
					list.Add(dbItem);
				}
			}
		}
		foreach (DBInfo item4 in list)
		{
			LogMessage("[매도감지] " + item4.종목명 + "(" + item4.종목코드 + ") 계좌잔고에 없음 → 매도완료 처리");
			int num9 = ((item4.현재가 > 0) ? item4.현재가 : item4.매수가격);
			item4.전량매도일 = DateTime.Now.ToString("yyyyMMdd");
			item4.전량매도이유 = (m_PendingSellOrders.ContainsKey(item4.종목코드) ? "수동매도" : "외부매도");
			item4.매도가격 = num9;
			item4.최종수익금 = (num9 - item4.매수가격) * item4.매수수량;
			int num10 = item4.매수가격 * item4.매수수량;
			item4.최종수익률 = ((num10 != 0) ? ((float)item4.최종수익금 / (float)num10 * 100f) : 0f);
			m_HistoryDbInfoList.Add(item4);
			deleteHoldingInsertHistory(item4);
			lock (m_HoldingLock)
			{
				m_HoldingDbInfoList.Remove(item4);
			}
			axKHOpenAPI1.SetRealRemove("5007", item4.종목코드);
			m_RealTimePrices.TryRemove(item4.종목코드, out var _);
			m_PendingSellOrders.TryRemove(item4.종목코드, out var _);
			LogMessage($"[매도완료] {item4.종목명} 수익률 {item4.최종수익률:F2}% 수익금 {item4.최종수익금:N0}원");
			m_TodaySellCount++;
		}
		if (list.Count > 0)
		{
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
				int repeatCnt = axKHOpenAPI1.GetRepeatCnt(e.sTrCode, e.sRQName);
				m_HoldJongmokList = new List<HoldJongmok>();
				for (int i = 0; i < repeatCnt; i++)
				{
					int.TryParse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, i, "현재가").Trim(), out var result);
					double.TryParse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, i, "수익률(%)").Trim(), out var result2);
					double.TryParse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, i, "평가손익").Trim(), out var result3);
					double.TryParse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, i, "매입금액").Trim(), out var result4);
					int.TryParse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, i, "평가금액").Trim(), out var result5);
					double num = result3 - (double)(int)(result4 * 0.01);
					result2 /= 100.0;
					string stockCode = GetStockCode(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, i, "종목번호").Trim());
					int.TryParse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, i, "보유수량").Trim(), out var result6);
					m_HoldJongmokList.Add(new HoldJongmok
					{
						종목명 = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, i, "종목명").Trim(),
						종목코드 = stockCode,
						잔고수량 = result6.ToString(),
						매입금액 = result4.ToString(),
						평가금액 = result5.ToString(),
						손익금액 = num.ToString(),
						수익률 = result2.ToString(),
						현재가 = result.ToString()
					});
				}
				HoldJongmokSyncWithDB();
				RefreshHoldGrid();
				string s = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, 0, "총매입금액").Trim().Replace("+", "")
					.Replace("--", "-");
				string s2 = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, 0, "추정예탁자산").Trim().Replace("+", "")
					.Replace("--", "-");
				string s3 = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, 0, "총평가금액").Trim().Replace("+", "")
					.Replace("--", "-");
				string s4 = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, 0, "총평가손익금액").Trim().Replace("+", "")
					.Replace("--", "-");
				string s5 = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, 0, "총수익률(%)").Trim().Replace("+", "")
					.Replace("--", "-");
				long.TryParse(s, out var _);
				long.TryParse(s2, out var result8);
				long.TryParse(s3, out var result9);
				long.TryParse(s4, out var result10);
				float.TryParse(s5, out var result11);
				result11 /= 100f;
				if (result8 > 0)
				{
					m_estimatedBalance = result8;
				}
				long num2 = m_estimatedBalance - result9;
				if (num2 >= 0)
				{
					m_availableBalance = num2;
				}
				if (num2 < 0)
				{
					num2 = 0L;
				}
				매수금label.Text = $"{num2:N0}";
				예수금label.Text = $"{m_estimatedBalance:N0}";
				평가금label.Text = $"{result9:N0}";
				평가수익label.Text = string.Format("{0}{1:N0}", (result10 >= 0) ? "+" : "", result10);
				수익률label.Text = string.Format("{0}{1:F2}%", (result11 >= 0f) ? "+" : "", result11);
				평가수익label.ForeColor = ((result10 >= 0) ? Color.FromArgb(220, 50, 50) : Color.FromArgb(50, 50, 220));
				수익률label.ForeColor = ((result11 >= 0f) ? Color.FromArgb(220, 50, 50) : Color.FromArgb(50, 50, 220));
				return;
			}
			catch (Exception ex)
			{
				LogMessage("계좌잔고평가내역 처리 오류: " + ex.Message);
				return;
			}
		}
		if (e.sRQName.Contains("조건식종목정보"))
		{
			axKHOpenAPI1.DisconnectRealData("5002");
			string[] array = e.sRQName.Split(';');
			string text = array[1];
			int index = int.Parse(array[2]);
			int repeatCnt2 = axKHOpenAPI1.GetRepeatCnt(e.sTrCode, e.sRQName);
			for (int j = 0; j < repeatCnt2; j++)
			{
				string text2 = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, j, "종목명").Trim();
				string text3 = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, j, "종목코드").Trim();
				string value = ChangeStrToNumberStyle(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, j, "현재가").Trim());
				string value2 = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, j, "전일대비").Trim();
				string value3 = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, j, "등락율").Trim();
				string value4 = ChangeStrToNumberStyle(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, j, "거래량").Trim());
				string value5 = ChangeStrToNumberStyle(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, j, "시가").Trim());
				string value6 = ChangeStrToNumberStyle(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, j, "고가").Trim());
				string value7 = ChangeStrToNumberStyle(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, j, "저가").Trim());
				lock (m_ConditionLock)
				{
					foreach (StockItemInfo stockItem in m_ConditionList[index].stockItemList)
					{
						if (text3 == stockItem.종목코드)
						{
							stockItem.조건명 = text;
							stockItem.종목명 = text2;
							stockItem.현재가 = value;
							stockItem.전일대비 = value2;
							stockItem.등락률 = value3;
							stockItem.거래량 = value4;
							stockItem.시가 = value5;
							stockItem.고가 = value6;
							stockItem.저가 = value7;
							break;
						}
					}
					bool flag = false;
					for (int k = 0; k < conditionFilteredGridView.RowCount - 1; k++)
					{
						if (conditionFilteredGridView["조건명", k].Value.ToString() == text && conditionFilteredGridView["종목명", k].Value.ToString() == text2)
						{
							conditionFilteredGridView["종목코드", k].Value = text3;
							conditionFilteredGridView["현재가", k].Value = value;
							conditionFilteredGridView["전일대비", k].Value = value2;
							conditionFilteredGridView["등락률", k].Value = value3;
							conditionFilteredGridView["거래량", k].Value = value4;
							conditionFilteredGridView["시가", k].Value = value5;
							conditionFilteredGridView["고가", k].Value = value6;
							conditionFilteredGridView["저가", k].Value = value7;
							flag = true;
							break;
						}
					}
					if (!flag)
					{
						conditionFilteredGridView.Rows.Add();
						conditionFilteredGridView["조건명", conditionFilteredGridView.RowCount - 2].Value = text;
						conditionFilteredGridView["종목명", conditionFilteredGridView.RowCount - 2].Value = text2;
						conditionFilteredGridView["종목코드", conditionFilteredGridView.RowCount - 2].Value = text3;
						conditionFilteredGridView["현재가", conditionFilteredGridView.RowCount - 2].Value = value;
						conditionFilteredGridView["전일대비", conditionFilteredGridView.RowCount - 2].Value = value2;
						conditionFilteredGridView["등락률", conditionFilteredGridView.RowCount - 2].Value = value3;
						conditionFilteredGridView["거래량", conditionFilteredGridView.RowCount - 2].Value = value4;
						conditionFilteredGridView["시가", conditionFilteredGridView.RowCount - 2].Value = value5;
						conditionFilteredGridView["고가", conditionFilteredGridView.RowCount - 2].Value = value6;
						conditionFilteredGridView["저가", conditionFilteredGridView.RowCount - 2].Value = value7;
					}
				}
			}
			return;
		}
		if (e.sRQName.Contains("주식기본정보요청"))
		{
			LogMessage(e.sRQName);
			string[] array2 = e.sRQName.Split(';');
			string text4 = array2[1];
			int index2 = int.Parse(array2[2]);
			string text5 = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, 0, "종목명").Trim();
			string value8 = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, 0, "종목코드").Trim();
			string value9 = ChangeStrToNumberStyle(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, 0, "현재가").Trim());
			string value10 = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, 0, "전일대비").Trim();
			string value11 = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, 0, "등락율").Trim();
			string value12 = ChangeStrToNumberStyle(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, 0, "거래량").Trim());
			string value13 = ChangeStrToNumberStyle(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, 0, "시가").Trim());
			string value14 = ChangeStrToNumberStyle(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, 0, "고가").Trim());
			string value15 = ChangeStrToNumberStyle(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, 0, "저가").Trim());
			bool flag2 = false;
			lock (m_ConditionLock)
			{
				foreach (StockItemInfo stockItem2 in m_ConditionList[index2].stockItemList)
				{
					if (stockItem2.종목명 == text5)
					{
						LogMessage("이미 있음 : " + text4 + " " + text5);
						flag2 = true;
						break;
					}
				}
				if (!flag2)
				{
					LogMessage("신규 추가 : " + text4 + " " + text5);
					m_ConditionList[index2].stockItemList.Add(new StockItemInfo
					{
						조건명 = text4,
						종목명 = text5,
						종목코드 = value8,
						현재가 = value9,
						전일대비 = value10,
						등락률 = value11,
						거래량 = value12,
						시가 = value13,
						고가 = value14,
						저가 = value15
					});
					conditionFilteredGridView.Rows.Add();
					conditionFilteredGridView["조건명", conditionFilteredGridView.RowCount - 2].Value = text4;
					conditionFilteredGridView["종목명", conditionFilteredGridView.RowCount - 2].Value = text5;
					conditionFilteredGridView["종목코드", conditionFilteredGridView.RowCount - 2].Value = value8;
					conditionFilteredGridView["현재가", conditionFilteredGridView.RowCount - 2].Value = value9;
					conditionFilteredGridView["전일대비", conditionFilteredGridView.RowCount - 2].Value = value10;
					conditionFilteredGridView["등락률", conditionFilteredGridView.RowCount - 2].Value = value11;
					conditionFilteredGridView["거래량", conditionFilteredGridView.RowCount - 2].Value = value12;
					conditionFilteredGridView["시가", conditionFilteredGridView.RowCount - 2].Value = value13;
					conditionFilteredGridView["고가", conditionFilteredGridView.RowCount - 2].Value = value14;
					conditionFilteredGridView["저가", conditionFilteredGridView.RowCount - 2].Value = value15;
				}
				return;
			}
		}
		if (e.sRQName == "주식일봉차트조회")
		{
			try
			{
				axKHOpenAPI1.DisconnectRealData("5005");
				int repeatCnt3 = axKHOpenAPI1.GetRepeatCnt(e.sTrCode, e.sRQName);
				m_PriceInfoList = new List<PriceInfoEntityObject>();
				m_PriceSeries.Points.Clear();
				m_VolumeSeries.Points.Clear();
				chart1.ChartAreas[1].AxisY.LabelStyle.Format = "#,##0,K";
				ChartArea chartArea = chart1.ChartAreas["PriceChartArea"];
				do
				{
					chartArea.AxisX.ScaleView.ZoomReset();
				}
				while (chartArea.AxisX.ScaleView.IsZoomed);
				int num3 = 0;
				int num4 = int.MaxValue;
				for (int l = 0; l < repeatCnt3; l++)
				{
					if (e.sRQName == "JM_주식분봉차트조회" || e.sRQName == "JM_주식틱봉차트조회")
					{
						m_PriceInfoList.Add(new PriceInfoEntityObject
						{
							일자 = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, l, "체결시간").Trim(),
							시가 = Math.Abs(int.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, l, "시가").Trim())),
							고가 = Math.Abs(int.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, l, "고가").Trim())),
							저가 = Math.Abs(int.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, l, "저가").Trim())),
							종가 = Math.Abs(int.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, l, "현재가").Trim())),
							거래량 = int.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, l, "거래량").Trim())
						});
					}
					else
					{
						m_PriceInfoList.Add(new PriceInfoEntityObject
						{
							일자 = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, l, "일자").Trim(),
							시가 = int.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, l, "시가").Trim()),
							고가 = int.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, l, "고가").Trim()),
							저가 = int.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, l, "저가").Trim()),
							종가 = int.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, l, "현재가").Trim()),
							거래량 = int.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, l, "거래량").Trim())
						});
					}
					if (m_PriceInfoList[l].고가 > num3)
					{
						num3 = m_PriceInfoList[l].고가;
					}
					if (m_PriceInfoList[l].저가 < num4)
					{
						num4 = m_PriceInfoList[l].저가;
					}
					m_PriceSeries.Points.AddXY(m_PriceInfoList[l].일자, m_PriceInfoList[l].고가);
					m_PriceSeries.Points[l].YValues[1] = m_PriceInfoList[l].저가;
					m_PriceSeries.Points[l].YValues[2] = m_PriceInfoList[l].시가;
					m_PriceSeries.Points[l].YValues[3] = m_PriceInfoList[l].종가;
					m_PriceSeries.Points[l].ToolTip = "일자 : " + m_PriceInfoList[l].일자 + "\n시가 : " + $"{m_PriceInfoList[l].시가:#,###}" + "\n고가 : " + $"{m_PriceInfoList[l].고가:#,###}" + "\n저가 : " + $"{m_PriceInfoList[l].저가:#,###}" + "\n종가 : " + $"{m_PriceInfoList[l].종가:#,###}" + "\n거래량 : " + $"{m_PriceInfoList[l].거래량:#,###}";
					m_VolumeSeries.Points.AddXY(m_PriceInfoList[l].일자, m_PriceInfoList[l].거래량);
					m_VolumeSeries.Points[l].ToolTip = "일자 : " + m_PriceInfoList[l].일자 + "\n거래량 : " + $"{m_PriceInfoList[l].거래량:#,###}";
				}
				if (repeatCnt3 > 0)
				{
					chartArea.AxisX.ScaleView.ZoomReset();
					chartArea.AxisY.Maximum = num3;
					chartArea.AxisY.Minimum = num4;
					if (!chartArea.AxisX.ScaleView.IsZoomed)
					{
						chart1_AxisViewChanged(chart1, new ViewEventArgs(chartArea.AxisX, 0.0));
					}
				}
				return;
			}
			catch (Exception ex2)
			{
				Console.WriteLine(ex2.Message.ToString());
				return;
			}
		}
		if (e.sRQName.Contains("보유종목일봉조회"))
		{
			axKHOpenAPI1.DisconnectRealData("5005");
			string[] array3 = e.sRQName.Split(';');
			if (array3.Length < 3)
			{
				return;
			}
			string text6 = array3[1];
			string text7 = array3[2];
			int repeatCnt4 = axKHOpenAPI1.GetRepeatCnt(e.sTrCode, e.sRQName);
			if (repeatCnt4 <= 0)
			{
				return;
			}
			List<PriceInfoEntityObject> list = new List<PriceInfoEntityObject>();
			long num5 = 0L;
			int num6 = Math.Min(repeatCnt4, 300);
			for (int m = 0; m < num6; m++)
			{
				try
				{
					int 종가 = Math.Abs(int.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, m, "현재가").Trim()));
					long num7 = Math.Abs(long.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, m, "거래량").Trim()));
					list.Add(new PriceInfoEntityObject
					{
						일자 = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, m, "일자").Trim(),
						종가 = 종가,
						거래량 = (int)num7
					});
					if (m < 50 && num7 > num5)
					{
						num5 = num7;
					}
				}
				catch
				{
					break;
				}
			}
			m_Max50DayVolume[text7] = num5;
			Dictionary<int, int> dictionary = new Dictionary<int, int>();
			int[] eMA매도기간 = _strategyConfig.EMA매도기간;
			foreach (int num8 in eMA매도기간)
			{
				if (list.Count >= num8)
				{
					List<int> list2 = StrategyManager.CalculateEMA(list, num8);
					if (list2.Count > 0)
					{
						dictionary[num8] = list2[0];
					}
				}
			}
			m_HoldingEMA[text7] = dictionary;
			string text8 = string.Join(", ", dictionary.Select((KeyValuePair<int, int> kv) => $"EMA{kv.Key}={kv.Value:N0}"));
			LogMessage($"일봉 캐싱: {text6}({text7}) 50일최대거래량={num5:N0} {text8}");
			return;
		}
		if (e.sRQName.Contains("종목일봉차트조회"))
		{
			axKHOpenAPI1.DisconnectRealData("5005");
			string key = e.sRQName.Split(';')[1];
			int repeatCnt5 = axKHOpenAPI1.GetRepeatCnt(e.sTrCode, e.sRQName);
			if (repeatCnt5 <= 0)
			{
				LogMessage("nCnt <= 0");
				return;
			}
			ConditionCheck conditionCheck = new ConditionCheck();
			List<PriceInfoEntityObject> list3 = new List<PriceInfoEntityObject>();
			int num9 = 0;
			int num10 = int.MaxValue;
			for (int num11 = 0; num11 < repeatCnt5; num11++)
			{
				try
				{
					list3.Add(new PriceInfoEntityObject
					{
						일자 = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, num11, "일자").Trim(),
						시가 = int.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, num11, "시가").Trim()),
						고가 = int.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, num11, "고가").Trim()),
						저가 = int.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, num11, "저가").Trim()),
						종가 = int.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, num11, "현재가").Trim()),
						거래량 = int.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, num11, "거래량").Trim())
					});
				}
				catch
				{
					break;
				}
				if (list3[num11].고가 > num9)
				{
					num9 = list3[num11].고가;
				}
				if (list3[num11].저가 < num10)
				{
					num10 = list3[num11].저가;
				}
			}
			conditionCheck.priceInfoList = list3;
			conditionCheck.최고가 = num9;
			conditionCheck.최저가 = num10;
			lock (m_MonitoringLock)
			{
				if (!m_conditionCheck.ContainsKey(key))
				{
					m_conditionCheck.Add(key, conditionCheck);
				}
				List<int> value16 = StrategyManager.CalculateSMA(list3, 10);
				m_conditionCheck[key].이동평균.Add("ema10", value16);
				return;
			}
		}
		if (e.sRQName == "지수일봉조회")
		{
			int repeatCnt6 = axKHOpenAPI1.GetRepeatCnt(e.sTrCode, e.sRQName);
			ConditionCheck conditionCheck2 = new ConditionCheck();
			List<PriceInfoEntityObject> list4 = new List<PriceInfoEntityObject>();
			for (int num12 = 0; num12 < repeatCnt6; num12++)
			{
				try
				{
					list4.Add(new PriceInfoEntityObject
					{
						일자 = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, num12, "일자").Trim(),
						시가 = int.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, num12, "시가").Trim()),
						고가 = int.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, num12, "고가").Trim()),
						저가 = int.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, num12, "저가").Trim()),
						종가 = int.Parse(axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, num12, "현재가").Trim())
					});
				}
				catch
				{
					break;
				}
			}
			conditionCheck2.priceInfoList = list4;
			lock (m_MonitoringLock)
			{
				m_conditionCheck["지수"] = conditionCheck2;
				List<int> list5 = StrategyManager.CalculateSMA(list4, 60);
				m_conditionCheck["지수"].이동평균["ma60"] = list5;
				if (list4.Count > 0)
				{
					LogMessage($"코스피 지수 데이터 갱신: {list4[0].일자} 종가={list4[0].종가} MA60={list5[0]}");
				}
				return;
			}
		}
		if (e.sRQName.Contains("매수주문"))
		{
			LogMessage(e.sRQName);
			string[] array4 = e.sRQName.Split(';');
			if (array4.Length < 3)
			{
				LogMessage("매수주문 RQName 파싱 실패");
				return;
			}
			string value17 = array4[1];
			string text9 = array4[2];
			string text10 = axKHOpenAPI1.GetCommData(e.sTrCode, e.sRQName, 0, "주문번호").Trim();
			LogMessage("매수TR sTrCode=[" + e.sTrCode + "] 주문번호=[" + text10 + "]");
			if (text10 == "")
			{
				LogMessage("[매수거부] " + text9 + " — 서버 즉시거부(주문번호 없음), pending 해제 및 잔고 복원");
				m_PendingBuyOrders.TryRemove(text9, out var value18);
				m_BuyOrderTime.TryRemove(text9, out var _);
				m_BuyOrderScreen.TryRemove(text9, out value18);
				if (m_BuyOrderAmount.TryRemove(text9, out var value20))
				{
					m_availableBalance += value20;
				}
			}
			else
			{
				m_dicBuyOrder[text10] = value17;
				m_BuyOrderNo[text9] = text10;
			}
		}
		else
		{
			if (!e.sRQName.Contains("매도주문"))
			{
				return;
			}
			LogMessage(e.sRQName);
			string[] array5 = e.sRQName.Split(';');
			if (array5.Length < 2)
			{
				LogMessage("매도주문 RQName 파싱 실패");
				return;
			}
			string text11 = array5[1];
			string text12 = ((array5.Length >= 3) ? array5[2] : "");
			string text13 = axKHOpenAPI1.GetCommData(e.sTrCode, "", 0, "주문번호").Trim();
			if (text13 == "")
			{
				LogMessage("매도 주문번호 미수신 (체결 콜백에서 처리됨)");
			}
			else
			{
				m_dicSellOrder[text13] = text11 + ";" + text12;
			}
			_sellConfirmTimer?.Stop();
			_sellConfirmTimer?.Start();
		}
	}

	private void updateAccountInfo()
	{
		string sValue = AccountList.Text;
		axKHOpenAPI1.SetInputValue("계좌번호", sValue);
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
				LogMessage("로그인 성공");
				string[] array = axKHOpenAPI1.GetLoginInfo("ACCLIST").Trim().Split(';');
				for (int i = 0; i < array.Length; i++)
				{
					AccountList.Items.Add(array[i]);
				}
				AccountList.SelectedIndex = 0;
				string loginInfo = axKHOpenAPI1.GetLoginInfo("USER_ID");
				UserID.Text = loginInfo;
				if (axKHOpenAPI1.GetLoginInfo("GetServerGubun") == "1")
				{
					ServerGubun.Text = "● 모의투자";
					ServerGubun.ForeColor = Color.FromArgb(50, 130, 240);
				}
				else
				{
					ServerGubun.Text = "● 실전";
					ServerGubun.ForeColor = Color.FromArgb(220, 60, 60);
				}
				Text = "AutoTrading - " + loginInfo + " [" + ServerGubun.Text.Replace("● ", "") + "]";
				LoginButton.Text = "✔ 접속됨";
				LoginButton.Enabled = false;
				LoginButton.BackColor = Color.FromArgb(60, 60, 60);
				LoginButton.ForeColor = Color.FromArgb(120, 200, 120);
				m_MonitoringCts = new CancellationTokenSource();
				Task.Run(() => realMonitoringUpdater(m_MonitoringCts.Token));
				Task.Run(() => FetchHoldingsDailyData(m_MonitoringCts.Token));
				_connectionCheckTimer = new System.Windows.Forms.Timer();
				_connectionCheckTimer.Interval = 30000;
				_connectionCheckTimer.Tick += ConnectionCheck_Tick;
				_connectionCheckTimer.Start();
				m_InitialLoginDone = true;
			}
			else
			{
				LogMessage("★ [재연결] 서버 재접속 감지 — 실시간 등록 복원 중...");
				ReRegisterConditionsAsync();
			}
			updateAccountInfo();
			requestJisuInfo();
			_balanceRefreshTimer?.Start();
			_holdingUIRefreshTimer?.Start();
			RegisterHoldingsRealTime();
			axKHOpenAPI1.SetRealReg("5008", "001", "20;10;11;12", "0");
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

	private async Task ReRegisterConditionsAsync()
	{
		int registered = 0;
		foreach (ConditionInfo condition in m_ConditionList)
		{
			if (!condition.실시간등록여부)
			{
				continue;
			}
			await Task.Delay(1000);
			int retryCount = 0;
			bool success = false;
			while (retryCount < 3)
			{
				int result = 0;
				Invoke((Action)delegate
				{
					result = axKHOpenAPI1.SendCondition("5006", condition.조건식이름, condition.조건식번호, 1);
				});
				if (result > 0)
				{
					LogMessage("  [재연결] 조건식 복원: " + condition.조건식이름);
					registered++;
					success = true;
					break;
				}
				retryCount++;
				await Task.Delay(5000);
			}
			if (!success)
			{
				LogMessage("  [재연결] 조건식 복원 실패: " + condition.조건식이름);
			}
		}
		if (registered > 0)
		{
			LogMessage($"★ [재연결] 조건식 {registered}개 복원 완료");
		}
	}

	private void ConnectionCheck_Tick(object sender, EventArgs e)
	{
		try
		{
			if (axKHOpenAPI1.GetConnectState() == 0)
			{
				LoginButton.Text = "⚠ 연결끊김";
				LoginButton.ForeColor = Color.FromArgb(255, 200, 50);
				LogMessage("[경고] 서버 연결 끊어짐 감지 — 자동 재연결 대기 중...");
			}
			else if (LoginButton.Text.Contains("연결끊김"))
			{
				LoginButton.Text = "✔ 접속됨";
				LoginButton.ForeColor = Color.FromArgb(120, 200, 120);
			}
		}
		catch
		{
		}
	}

	private string ChangeStrToNumberStyle(string strNumber, bool bIsAbs = true)
	{
		int num = int.Parse(strNumber);
		if (bIsAbs)
		{
			num = Math.Abs(num);
		}
		return $"{num:#,###}";
	}

	private string ChangeIntToNumberStyle(int nNumber)
	{
		return $"{nNumber:#,###}";
	}

	public string GetStockCode(string code)
	{
		return Regex.Replace(code, "\\D", "");
	}

	private void SetPlaceholder(TextBox tb, string placeholder)
	{
		tb.ForeColor = Color.Gray;
		tb.Text = placeholder;
		tb.GotFocus += delegate
		{
			if (tb.Text == placeholder)
			{
				tb.Text = "";
				tb.ForeColor = Color.Black;
			}
		};
		tb.LostFocus += delegate
		{
			if (string.IsNullOrWhiteSpace(tb.Text))
			{
				tb.ForeColor = Color.Gray;
				tb.Text = placeholder;
			}
		};
	}

	public int IntRound(int Value, int Digit)
	{
		double num = Math.Pow(10.0, Digit);
		return (int)(Math.Ceiling((double)Value * num) / num);
	}

	private string GetScrNum()
	{
		if (_scrNum < 5200)
		{
			_scrNum++;
		}
		else
		{
			_scrNum = 5050;
		}
		return _scrNum.ToString();
	}

	public bool LogMessage(string strMsg)
	{
		try
		{
			string strTotalLog = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.ff") + " : " + strMsg;
			Action action = delegate
			{
				logTextBox.AppendText(strTotalLog + Environment.NewLine);
				if (logTextBox.Lines.Length > 10000)
				{
					string[] lines = logTextBox.Lines.Skip(5000).ToArray();
					logTextBox.Lines = lines;
					logTextBox.SelectionStart = logTextBox.Text.Length;
					logTextBox.ScrollToCaret();
				}
			};
			if (logTextBox.InvokeRequired)
			{
				logTextBox.BeginInvoke(action);
			}
			else
			{
				action();
			}
			LogManager.Log(strMsg);
			return true;
		}
		catch (Exception ex)
		{
			try
			{
				LogManager.Log("[LogError] " + ex.Message);
			}
			catch
			{
			}
			return false;
		}
	}

	private DBInfo FindDbInfo(List<DBInfo> list, string 종목명, string 매수일, string 매수전략)
	{
		return list?.Find((DBInfo x) => x.종목명 == 종목명 && x.매수일 == 매수일 && x.매수전략 == 매수전략);
	}

	private void SetupSplitContainers()
	{
		base.Controls.Remove(tableLayoutPanel3);
		base.Controls.Remove(tableLayoutPanel5);
		base.Controls.Remove(tableLayoutPanel4);
		Label label = CreateSectionLabel("\ud83d\udccb 조건식 목록");
		Label label2 = CreateSectionLabel("\ud83d\udcca 조건식 편입종목");
		Label label3 = CreateSectionLabel("\ud83d\udcb0 보유종목 (우클릭: 매도)");
		Label label4 = CreateSectionLabel("\ud83d\udcc8 차트");
		Label label5 = CreateSectionLabel("\ud83d\udcdd 로그");
		Panel panel = new Panel();
		panel.Dock = DockStyle.Fill;
		label.Dock = DockStyle.Top;
		panel.Controls.Add(conditionCheckedListBox);
		panel.Controls.Add(label);
		conditionCheckedListBox.Dock = DockStyle.Fill;
		Panel panel2 = new Panel();
		panel2.Dock = DockStyle.Fill;
		label2.Dock = DockStyle.Top;
		panel2.Controls.Add(conditionFilteredGridView);
		panel2.Controls.Add(label2);
		conditionFilteredGridView.Dock = DockStyle.Fill;
		tableLayoutPanel3.Controls.Clear();
		tableLayoutPanel3.Controls.Add(panel, 0, 0);
		tableLayoutPanel3.Controls.Add(panel2, 1, 0);
		tableLayoutPanel3.Controls.Add(tableLayoutPanel2, 2, 0);
		Panel panel3 = new Panel();
		panel3.Dock = DockStyle.Fill;
		label3.Dock = DockStyle.Top;
		panel3.Controls.Add(holdJongmokGridView);
		panel3.Controls.Add(label3);
		holdJongmokGridView.Dock = DockStyle.Fill;
		tableLayoutPanel5.Controls.Clear();
		tableLayoutPanel5.Controls.Add(panel3, 0, 0);
		label4.Dock = DockStyle.Top;
		panel1.Controls.Add(label4);
		chart1.Dock = DockStyle.Fill;
		label5.Dock = DockStyle.Top;
		this.panel3.Controls.Add(label5);
		logTextBox.Dock = DockStyle.Fill;
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
		base.Controls.Add(_splitMain);
		_splitMain.Cursor = Cursors.Default;
		_splitTop.Cursor = Cursors.Default;
	}

	private Label CreateSectionLabel(string text)
	{
		return new Label
		{
			Text = text,
			Font = new Font("맑은 고딕", 9f, FontStyle.Bold),
			ForeColor = Color.FromArgb(50, 70, 100),
			BackColor = Color.FromArgb(235, 240, 248),
			Height = 22,
			TextAlign = ContentAlignment.MiddleLeft,
			Padding = new Padding(6, 0, 0, 0)
		};
	}

	private void AdjustLayout()
	{
		if (_splitMain == null || _splitTop == null)
		{
			return;
		}
		int num = base.ClientSize.Width;
		int num2 = base.ClientSize.Height;
		int num3 = num - 24;
		if (num3 < 100 || num2 < 200)
		{
			return;
		}
		GetConditionButton.Location = new Point(12, 12);
		ATStartButton.Location = new Point(GetConditionButton.Right + 8, 12);
		ATStopButton.Location = new Point(ATStartButton.Location.X, ATStartButton.Location.Y);
		ATStopButton.Size = ATStartButton.Size;
		_ = tableLayoutPanel1.Left;
		LoginButton.Location = new Point(num - 12 - LoginButton.Width, 12);
		tableLayoutPanel1.Location = new Point(LoginButton.Left - 8 - tableLayoutPanel1.Width, 12);
		_emergencyStopButton.Location = new Point(tableLayoutPanel1.Left - 8 - _emergencyStopButton.Width, 10);
		int num4 = _emergencyStopButton.Left - 6;
		int num5 = testCode.Width + testPrice.Width + testAmount.Width + BuyTestButton.Width + SellTestButton.Width + 24;
		bool flag;
		if (num4 - num5 > ATStartButton.Right + 20)
		{
			SellTestButton.Location = new Point(num4 - SellTestButton.Width, 12);
			BuyTestButton.Location = new Point(SellTestButton.Left - 6 - BuyTestButton.Width, 12);
			testAmount.Location = new Point(BuyTestButton.Left - 6 - testAmount.Width, 13);
			testPrice.Location = new Point(testAmount.Left - 6 - testPrice.Width, 13);
			testCode.Location = new Point(testPrice.Left - 6 - testCode.Width, 13);
			flag = false;
		}
		else
		{
			int num6 = 38;
			testCode.Location = new Point(12, num6);
			testPrice.Location = new Point(testCode.Right + 4, num6);
			testAmount.Location = new Point(testPrice.Right + 4, num6);
			BuyTestButton.Location = new Point(testAmount.Right + 4, num6 - 1);
			SellTestButton.Location = new Point(BuyTestButton.Right + 4, num6 - 1);
			flag = true;
		}
		testCode.Visible = true;
		testPrice.Visible = true;
		testAmount.Visible = true;
		BuyTestButton.Visible = true;
		SellTestButton.Visible = true;
		int num7 = (flag ? 66 : 36) + 3 + 2;
		_dashboardLabel.SetBounds(12, num7, num3, 24);
		int num8 = num7 + 24 + 3;
		int num9 = Math.Max(200, num2 - num8 - 12);
		_splitMain.SetBounds(12, num8, num3, num9);
		if (!_splitInitialized && _splitMain.Height > 100 && _splitTop.Height > 100)
		{
			int num10 = (int)((double)_splitMain.Height * 0.65);
			if (num10 > 0 && num10 < _splitMain.Height - _splitMain.SplitterWidth - _splitMain.Panel2MinSize)
			{
				_splitMain.SplitterDistance = num10;
			}
			int num11 = (int)((double)_splitTop.Height * 0.35);
			if (num11 > 0 && num11 < _splitTop.Height - _splitTop.SplitterWidth - _splitTop.Panel2MinSize)
			{
				_splitTop.SplitterDistance = num11;
			}
			_splitInitialized = true;
		}
		_dashboardLabel.BringToFront();
		GetConditionButton.BringToFront();
		ATStartButton.BringToFront();
		ATStopButton.BringToFront();
		_emergencyStopButton.BringToFront();
		LoginButton.BringToFront();
		testCode.BringToFront();
		testPrice.BringToFront();
		testAmount.BringToFront();
		BuyTestButton.BringToFront();
		SellTestButton.BringToFront();
	}

	private Icon CreateAppIcon()
	{
		int num = 32;
		using Bitmap bitmap = new Bitmap(num, num, PixelFormat.Format32bppArgb);
		using Graphics graphics = Graphics.FromImage(bitmap);
		graphics.SmoothingMode = SmoothingMode.AntiAlias;
		using (SolidBrush brush = new SolidBrush(Color.FromArgb(20, 30, 48)))
		{
			graphics.FillRectangle(brush, 0, 0, num, num);
		}
		using (SolidBrush brush2 = new SolidBrush(Color.FromArgb(0, 200, 120)))
		{
			using SolidBrush brush3 = new SolidBrush(Color.FromArgb(220, 60, 60));
			using Pen pen = new Pen(Color.FromArgb(0, 200, 120), 1f);
			using Pen pen2 = new Pen(Color.FromArgb(220, 60, 60), 1f);
			graphics.DrawLine(pen, 8, 18, 8, 8);
			graphics.FillRectangle(brush2, 6, 10, 5, 8);
			graphics.DrawLine(pen2, 16, 22, 16, 10);
			graphics.FillRectangle(brush3, 14, 12, 5, 8);
			graphics.DrawLine(pen, 24, 16, 24, 4);
			graphics.FillRectangle(brush2, 22, 6, 5, 10);
		}
		using (Pen pen3 = new Pen(Color.FromArgb(60, 180, 255), 2f))
		{
			pen3.EndCap = LineCap.ArrowAnchor;
			graphics.DrawLine(pen3, 4, 26, 28, 6);
		}
		return Icon.FromHandle(bitmap.GetHicon());
	}

	private void ApplyUIStyle()
	{
		Color backColor = (BackColor = Color.FromArgb(240, 243, 247));
		Color.FromArgb(30, 40, 55);
		Color bgColor = Color.FromArgb(50, 130, 240);
		Color bgColor2 = Color.FromArgb(0, 180, 100);
		Color bgColor3 = Color.FromArgb(220, 60, 60);
		Color headerBg = Color.FromArgb(45, 55, 72);
		Color cellBg = Color.FromArgb(255, 255, 255);
		Color altRowBg = Color.FromArgb(245, 248, 252);
		Color borderColor = Color.FromArgb(200, 210, 225);
		StyleButton(LoginButton, bgColor);
		StyleButton(GetConditionButton, Color.FromArgb(80, 100, 130));
		StyleButton(ATStartButton, bgColor2);
		StyleButton(ATStopButton, bgColor3);
		StyleButton(BuyTestButton, bgColor3);
		StyleButton(SellTestButton, bgColor);
		StyleGrid(conditionFilteredGridView, headerBg, cellBg, altRowBg, borderColor);
		StyleGrid(holdJongmokGridView, headerBg, cellBg, altRowBg, borderColor);
		tableLayoutPanel2.BackColor = Color.White;
		tableLayoutPanel2.CellBorderStyle = TableLayoutPanelCellBorderStyle.Single;
		foreach (Control control in tableLayoutPanel2.Controls)
		{
			if (control is Label label)
			{
				label.BackColor = Color.White;
				label.Font = new Font("맑은 고딕", 9f, FontStyle.Regular);
			}
		}
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
		logTextBox.BackColor = Color.FromArgb(25, 32, 44);
		logTextBox.ForeColor = Color.FromArgb(180, 220, 255);
		logTextBox.Font = new Font("Consolas", 9f, FontStyle.Regular);
		conditionCheckedListBox.BackColor = Color.White;
		conditionCheckedListBox.Font = new Font("맑은 고딕", 10f, FontStyle.Regular);
		chart1.BackColor = Color.White;
		chart1.ChartAreas[0].BackColor = Color.White;
		chart1.ChartAreas[1].BackColor = Color.FromArgb(250, 252, 255);
		tableLayoutPanel1.BackColor = Color.White;
		Color borderColor2 = Color.FromArgb(195, 205, 220);
		Color white = Color.White;
		StylePanel(tableLayoutPanel3, white, borderColor2);
		StylePanel(tableLayoutPanel5, white, borderColor2);
		StylePanel(panel1, white, borderColor2);
		StylePanel(panel3, Color.FromArgb(25, 32, 44), borderColor2);
		tableLayoutPanel4.BackColor = backColor;
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
		btn.MouseEnter += delegate
		{
			btn.BackColor = ControlPaint.Light(bgColor, 0.15f);
		};
		btn.MouseLeave += delegate
		{
			btn.BackColor = bgColor;
		};
	}

	private void StyleGrid(DataGridView grid, Color headerBg, Color cellBg, Color altRowBg, Color borderColor)
	{
		grid.EnableHeadersVisualStyles = false;
		grid.BorderStyle = BorderStyle.None;
		grid.CellBorderStyle = DataGridViewCellBorderStyle.SingleHorizontal;
		grid.GridColor = Color.FromArgb(230, 235, 245);
		grid.BackgroundColor = cellBg;
		grid.ColumnHeadersDefaultCellStyle.BackColor = headerBg;
		grid.ColumnHeadersDefaultCellStyle.ForeColor = Color.White;
		grid.ColumnHeadersDefaultCellStyle.Font = new Font("맑은 고딕", 9f, FontStyle.Bold);
		grid.ColumnHeadersDefaultCellStyle.Alignment = DataGridViewContentAlignment.MiddleCenter;
		grid.ColumnHeadersDefaultCellStyle.SelectionBackColor = headerBg;
		grid.ColumnHeadersHeight = 32;
		grid.DefaultCellStyle.BackColor = cellBg;
		grid.DefaultCellStyle.ForeColor = Color.FromArgb(40, 50, 70);
		grid.DefaultCellStyle.Font = new Font("맑은 고딕", 9f);
		grid.DefaultCellStyle.SelectionBackColor = Color.FromArgb(220, 234, 252);
		grid.DefaultCellStyle.SelectionForeColor = Color.FromArgb(30, 40, 60);
		grid.DefaultCellStyle.Padding = new Padding(2);
		grid.AlternatingRowsDefaultCellStyle.BackColor = altRowBg;
		grid.RowHeadersVisible = false;
		grid.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill;
	}

	private void StylePanel(Control panel, Color bgColor, Color borderColor)
	{
		panel.BackColor = bgColor;
		panel.Padding = new Padding(1);
		panel.Paint += delegate(object s, PaintEventArgs e)
		{
			Control control = (Control)s;
			using (Pen pen = new Pen(borderColor, 1f))
			{
				e.Graphics.DrawRectangle(pen, 0, 0, control.Width - 1, control.Height - 1);
			}
			using Pen pen2 = new Pen(Color.FromArgb(40, 0, 0, 0), 1f);
			e.Graphics.DrawLine(pen2, 1, control.Height - 1, control.Width - 1, control.Height - 1);
			e.Graphics.DrawLine(pen2, control.Width - 1, 1, control.Width - 1, control.Height - 1);
		};
	}

	private int CompareGridValues(string val1, string val2)
	{
		string text = (val1 ?? "").Replace(",", "");
		string text2 = (val2 ?? "").Replace(",", "");
		if (double.TryParse(text, out var result) && double.TryParse(text2, out var result2))
		{
			return result.CompareTo(result2);
		}
		return string.Compare(text, text2, StringComparison.Ordinal);
	}

	private void conditionGridView_SortCompare(object sender, DataGridViewSortCompareEventArgs e)
	{
		e.SortResult = CompareGridValues(e.CellValue1?.ToString(), e.CellValue2?.ToString());
		e.Handled = true;
	}

	private void conditionGridView_ColumnHeaderMouseClick(object sender, DataGridViewCellMouseEventArgs e)
	{
		if (m_conditionSortCol == e.ColumnIndex)
		{
			m_conditionSortOrder = ((m_conditionSortOrder != SortOrder.Ascending) ? SortOrder.Ascending : SortOrder.Descending);
		}
		else
		{
			m_conditionSortCol = e.ColumnIndex;
			m_conditionSortOrder = SortOrder.Ascending;
		}
		conditionFilteredGridView.Sort(conditionFilteredGridView.Columns[e.ColumnIndex], (m_conditionSortOrder != SortOrder.Ascending) ? ListSortDirection.Descending : ListSortDirection.Ascending);
		conditionFilteredGridView.Columns[e.ColumnIndex].HeaderCell.SortGlyphDirection = m_conditionSortOrder;
	}

	private void holdGridView_ColumnHeaderMouseClick(object sender, DataGridViewCellMouseEventArgs e)
	{
		if (m_holdSortCol == e.ColumnIndex)
		{
			m_holdSortOrder = ((m_holdSortOrder != SortOrder.Ascending) ? SortOrder.Ascending : SortOrder.Descending);
		}
		else
		{
			m_holdSortCol = e.ColumnIndex;
			m_holdSortOrder = SortOrder.Ascending;
		}
		string dataPropertyName = holdJongmokGridView.Columns[e.ColumnIndex].DataPropertyName;
		if (string.IsNullOrEmpty(dataPropertyName))
		{
			return;
		}
		PropertyInfo prop = typeof(DBInfo).GetProperty(dataPropertyName);
		if (prop == null)
		{
			return;
		}
		if (m_holdSortOrder == SortOrder.Ascending)
		{
			m_HoldingDbInfoList.Sort((DBInfo a, DBInfo b) => Comparer<object>.Default.Compare(prop.GetValue(a), prop.GetValue(b)));
		}
		else
		{
			m_HoldingDbInfoList.Sort((DBInfo a, DBInfo b) => Comparer<object>.Default.Compare(prop.GetValue(b), prop.GetValue(a)));
		}
		_holdGridBindingSource.DataSource = m_HoldingDbInfoList;
		FormatHoldGrid();
		if (holdJongmokGridView.Columns.Count > e.ColumnIndex)
		{
			holdJongmokGridView.Columns[e.ColumnIndex].HeaderCell.SortGlyphDirection = m_holdSortOrder;
		}
	}

	private void FormatHoldGrid()
	{
		if (holdJongmokGridView.Columns.Count == 0)
		{
			return;
		}
		holdJongmokGridView.AllowUserToAddRows = false;
		if (holdJongmokGridView.Columns.Contains("nR절반매도"))
		{
			holdJongmokGridView.Columns.Remove("nR절반매도");
			DataGridViewTextBoxColumn dataGridViewTextBoxColumn = new DataGridViewTextBoxColumn();
			dataGridViewTextBoxColumn.Name = "nR절반매도";
			dataGridViewTextBoxColumn.HeaderText = "nR익절";
			dataGridViewTextBoxColumn.Width = 50;
			dataGridViewTextBoxColumn.ReadOnly = true;
			dataGridViewTextBoxColumn.AutoSizeMode = DataGridViewAutoSizeColumnMode.None;
			dataGridViewTextBoxColumn.DefaultCellStyle.Alignment = DataGridViewContentAlignment.MiddleCenter;
			holdJongmokGridView.Columns.Add(dataGridViewTextBoxColumn);
			for (int i = 0; i < m_HoldingDbInfoList.Count; i++)
			{
				holdJongmokGridView["nR절반매도", i].Value = (m_HoldingDbInfoList[i].nR절반매도 ? "O" : "X");
			}
		}
		(string, string, int, string)[] array = new(string, string, int, string)[15]
		{
			("종목명", "종목명", 100, null),
			("종목코드", "종목코드", 75, null),
			("매수전략", "매수전략", 90, null),
			("매수가격", "매수가격", 80, "#,##0"),
			("현재가", "현재가", 80, "#,##0"),
			("평가금", "평가금", 90, "#,##0"),
			("현재수익률", "수익률(%)", 70, "0.00"),
			("현재수익금", "수익금", 80, "#,##0"),
			("매수수량", "매수수량", 60, "#,##0"),
			("보유수량", "보유수량", 60, "#,##0"),
			("보유일", "보유일", 50, null),
			("로스컷가격", "로스컷", 80, "#,##0"),
			("로스컷단계", "LC단계", 50, null),
			("nR절반매도", "nR익절", 50, null),
			("매수일", "매수일", 80, null)
		};
		int num = 0;
		(string, string, int, string)[] array2 = array;
		for (int j = 0; j < array2.Length; j++)
		{
			(string, string, int, string) tuple = array2[j];
			if (holdJongmokGridView.Columns.Contains(tuple.Item1))
			{
				DataGridViewColumn dataGridViewColumn = holdJongmokGridView.Columns[tuple.Item1];
				dataGridViewColumn.HeaderText = tuple.Item2;
				dataGridViewColumn.DisplayIndex = num++;
				dataGridViewColumn.Visible = true;
				dataGridViewColumn.Width = tuple.Item3;
				dataGridViewColumn.AutoSizeMode = DataGridViewAutoSizeColumnMode.None;
				if (tuple.Item4 != null)
				{
					dataGridViewColumn.DefaultCellStyle.Format = tuple.Item4;
				}
				dataGridViewColumn.DefaultCellStyle.Alignment = DataGridViewContentAlignment.MiddleRight;
			}
		}
		HashSet<string> hashSet = new HashSet<string>(array.Select(((string name, string header, int width, string format) d) => d.name));
		foreach (DataGridViewColumn column in holdJongmokGridView.Columns)
		{
			if (!hashSet.Contains(column.Name))
			{
				column.Visible = false;
			}
		}
		if (holdJongmokGridView.Columns.Contains("종목명"))
		{
			holdJongmokGridView.Columns["종목명"].DefaultCellStyle.Alignment = DataGridViewContentAlignment.MiddleLeft;
		}
		if (holdJongmokGridView.Columns.Contains("매수전략"))
		{
			holdJongmokGridView.Columns["매수전략"].DefaultCellStyle.Alignment = DataGridViewContentAlignment.MiddleLeft;
		}
	}

	protected override void Dispose(bool disposing)
	{
		if (disposing && components != null)
		{
			components.Dispose();
		}
		base.Dispose(disposing);
	}

	private void InitializeComponent()
	{
		System.ComponentModel.ComponentResourceManager resources = new System.ComponentModel.ComponentResourceManager(typeof(AutoTradingTest.Form1));
		System.Windows.Forms.DataGridViewCellStyle dataGridViewCellStyle = new System.Windows.Forms.DataGridViewCellStyle();
		System.Windows.Forms.DataVisualization.Charting.ChartArea chartArea = new System.Windows.Forms.DataVisualization.Charting.ChartArea();
		System.Windows.Forms.DataVisualization.Charting.ChartArea chartArea2 = new System.Windows.Forms.DataVisualization.Charting.ChartArea();
		System.Windows.Forms.DataVisualization.Charting.Series series = new System.Windows.Forms.DataVisualization.Charting.Series();
		System.Windows.Forms.DataVisualization.Charting.Series series2 = new System.Windows.Forms.DataVisualization.Charting.Series();
		this.axKHOpenAPI1 = new AxKHOpenAPILib.AxKHOpenAPI();
		this.LoginButton = new System.Windows.Forms.Button();
		this.tableLayoutPanel1 = new System.Windows.Forms.TableLayoutPanel();
		this.ServerGubun = new System.Windows.Forms.Label();
		this.label1 = new System.Windows.Forms.Label();
		this.UserID = new System.Windows.Forms.Label();
		this.AccountList = new System.Windows.Forms.ComboBox();
		this.tableLayoutPanel2 = new System.Windows.Forms.TableLayoutPanel();
		this.수익률label = new System.Windows.Forms.Label();
		this.평가금label = new System.Windows.Forms.Label();
		this.매수금label = new System.Windows.Forms.Label();
		this.예수금label = new System.Windows.Forms.Label();
		this.label2 = new System.Windows.Forms.Label();
		this.label3 = new System.Windows.Forms.Label();
		this.label4 = new System.Windows.Forms.Label();
		this.label5 = new System.Windows.Forms.Label();
		this.label6 = new System.Windows.Forms.Label();
		this.평가수익label = new System.Windows.Forms.Label();
		this.conditionCheckedListBox = new System.Windows.Forms.CheckedListBox();
		this.GetConditionButton = new System.Windows.Forms.Button();
		this.conditionFilteredGridView = new System.Windows.Forms.DataGridView();
		this.조건명 = new System.Windows.Forms.DataGridViewTextBoxColumn();
		this.종목명 = new System.Windows.Forms.DataGridViewTextBoxColumn();
		this.종목코드 = new System.Windows.Forms.DataGridViewTextBoxColumn();
		this.현재가 = new System.Windows.Forms.DataGridViewTextBoxColumn();
		this.전일대비 = new System.Windows.Forms.DataGridViewTextBoxColumn();
		this.등락률 = new System.Windows.Forms.DataGridViewTextBoxColumn();
		this.거래량 = new System.Windows.Forms.DataGridViewTextBoxColumn();
		this.시가 = new System.Windows.Forms.DataGridViewTextBoxColumn();
		this.고가 = new System.Windows.Forms.DataGridViewTextBoxColumn();
		this.저가 = new System.Windows.Forms.DataGridViewTextBoxColumn();
		this.logTextBox = new System.Windows.Forms.TextBox();
		this.ATStartButton = new System.Windows.Forms.Button();
		this.chart1 = new System.Windows.Forms.DataVisualization.Charting.Chart();
		this.chartYLabel = new System.Windows.Forms.Label();
		this.panel1 = new System.Windows.Forms.Panel();
		this.panel3 = new System.Windows.Forms.Panel();
		this.ATStopButton = new System.Windows.Forms.Button();
		this.holdJongmokGridView = new System.Windows.Forms.DataGridView();
		this.tableLayoutPanel3 = new System.Windows.Forms.TableLayoutPanel();
		this.tableLayoutPanel4 = new System.Windows.Forms.TableLayoutPanel();
		this.tableLayoutPanel5 = new System.Windows.Forms.TableLayoutPanel();
		this.BuyTestButton = new System.Windows.Forms.Button();
		this.SellTestButton = new System.Windows.Forms.Button();
		this.testCode = new System.Windows.Forms.TextBox();
		this.testPrice = new System.Windows.Forms.TextBox();
		this.testAmount = new System.Windows.Forms.TextBox();
		((System.ComponentModel.ISupportInitialize)this.axKHOpenAPI1).BeginInit();
		this.tableLayoutPanel1.SuspendLayout();
		this.tableLayoutPanel2.SuspendLayout();
		((System.ComponentModel.ISupportInitialize)this.conditionFilteredGridView).BeginInit();
		((System.ComponentModel.ISupportInitialize)this.chart1).BeginInit();
		this.panel1.SuspendLayout();
		this.panel3.SuspendLayout();
		((System.ComponentModel.ISupportInitialize)this.holdJongmokGridView).BeginInit();
		this.tableLayoutPanel3.SuspendLayout();
		this.tableLayoutPanel4.SuspendLayout();
		this.tableLayoutPanel5.SuspendLayout();
		base.SuspendLayout();
		this.axKHOpenAPI1.Enabled = true;
		this.axKHOpenAPI1.Location = new System.Drawing.Point(0, 0);
		this.axKHOpenAPI1.Name = "axKHOpenAPI1";
		this.axKHOpenAPI1.OcxState = (System.Windows.Forms.AxHost.State)resources.GetObject("axKHOpenAPI1.OcxState");
		this.axKHOpenAPI1.Size = new System.Drawing.Size(1, 1);
		this.axKHOpenAPI1.TabIndex = 0;
		this.axKHOpenAPI1.Visible = false;
		this.LoginButton.Anchor = System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Right;
		this.LoginButton.Location = new System.Drawing.Point(1591, 12);
		this.LoginButton.Name = "LoginButton";
		this.LoginButton.Size = new System.Drawing.Size(75, 23);
		this.LoginButton.TabIndex = 1;
		this.LoginButton.Text = "로그인";
		this.LoginButton.UseVisualStyleBackColor = true;
		this.tableLayoutPanel1.ColumnCount = 4;
		this.tableLayoutPanel1.ColumnStyles.Add(new System.Windows.Forms.ColumnStyle(System.Windows.Forms.SizeType.Percent, 25f));
		this.tableLayoutPanel1.ColumnStyles.Add(new System.Windows.Forms.ColumnStyle(System.Windows.Forms.SizeType.Percent, 25f));
		this.tableLayoutPanel1.ColumnStyles.Add(new System.Windows.Forms.ColumnStyle(System.Windows.Forms.SizeType.Percent, 25f));
		this.tableLayoutPanel1.ColumnStyles.Add(new System.Windows.Forms.ColumnStyle(System.Windows.Forms.SizeType.Percent, 25f));
		this.tableLayoutPanel1.Controls.Add(this.ServerGubun, 3, 0);
		this.tableLayoutPanel1.Controls.Add(this.label1, 0, 0);
		this.tableLayoutPanel1.Controls.Add(this.UserID, 2, 0);
		this.tableLayoutPanel1.Controls.Add(this.AccountList, 1, 0);
		this.tableLayoutPanel1.Anchor = System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Right;
		this.tableLayoutPanel1.Location = new System.Drawing.Point(1202, 12);
		this.tableLayoutPanel1.Name = "tableLayoutPanel1";
		this.tableLayoutPanel1.RowCount = 1;
		this.tableLayoutPanel1.RowStyles.Add(new System.Windows.Forms.RowStyle(System.Windows.Forms.SizeType.Percent, 100f));
		this.tableLayoutPanel1.Size = new System.Drawing.Size(383, 23);
		this.tableLayoutPanel1.TabIndex = 2;
		this.ServerGubun.Anchor = System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom | System.Windows.Forms.AnchorStyles.Left | System.Windows.Forms.AnchorStyles.Right;
		this.ServerGubun.AutoSize = true;
		this.ServerGubun.BackColor = System.Drawing.Color.White;
		this.ServerGubun.Location = new System.Drawing.Point(288, 0);
		this.ServerGubun.Name = "ServerGubun";
		this.ServerGubun.Size = new System.Drawing.Size(92, 23);
		this.ServerGubun.TabIndex = 2;
		this.ServerGubun.Text = "Server";
		this.ServerGubun.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
		this.label1.Anchor = System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom | System.Windows.Forms.AnchorStyles.Left | System.Windows.Forms.AnchorStyles.Right;
		this.label1.AutoSize = true;
		this.label1.BackColor = System.Drawing.Color.White;
		this.label1.Location = new System.Drawing.Point(3, 0);
		this.label1.Name = "label1";
		this.label1.Size = new System.Drawing.Size(89, 23);
		this.label1.TabIndex = 0;
		this.label1.Text = "계좌번호";
		this.label1.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
		this.UserID.Anchor = System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom | System.Windows.Forms.AnchorStyles.Left | System.Windows.Forms.AnchorStyles.Right;
		this.UserID.AutoSize = true;
		this.UserID.BackColor = System.Drawing.Color.White;
		this.UserID.Location = new System.Drawing.Point(193, 0);
		this.UserID.Name = "UserID";
		this.UserID.Size = new System.Drawing.Size(89, 23);
		this.UserID.TabIndex = 1;
		this.UserID.Text = "ID";
		this.UserID.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
		this.AccountList.Anchor = System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom | System.Windows.Forms.AnchorStyles.Left | System.Windows.Forms.AnchorStyles.Right;
		this.AccountList.FormattingEnabled = true;
		this.AccountList.Location = new System.Drawing.Point(98, 3);
		this.AccountList.Name = "AccountList";
		this.AccountList.Size = new System.Drawing.Size(89, 20);
		this.AccountList.TabIndex = 3;
		this.tableLayoutPanel2.Anchor = System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom | System.Windows.Forms.AnchorStyles.Left | System.Windows.Forms.AnchorStyles.Right;
		this.tableLayoutPanel2.ColumnCount = 2;
		this.tableLayoutPanel2.ColumnStyles.Add(new System.Windows.Forms.ColumnStyle(System.Windows.Forms.SizeType.Percent, 50f));
		this.tableLayoutPanel2.ColumnStyles.Add(new System.Windows.Forms.ColumnStyle(System.Windows.Forms.SizeType.Percent, 50f));
		this.tableLayoutPanel2.Controls.Add(this.수익률label, 1, 4);
		this.tableLayoutPanel2.Controls.Add(this.평가금label, 1, 2);
		this.tableLayoutPanel2.Controls.Add(this.매수금label, 1, 1);
		this.tableLayoutPanel2.Controls.Add(this.예수금label, 1, 0);
		this.tableLayoutPanel2.Controls.Add(this.label2, 0, 0);
		this.tableLayoutPanel2.Controls.Add(this.label3, 0, 1);
		this.tableLayoutPanel2.Controls.Add(this.label4, 0, 2);
		this.tableLayoutPanel2.Controls.Add(this.label5, 0, 3);
		this.tableLayoutPanel2.Controls.Add(this.label6, 0, 4);
		this.tableLayoutPanel2.Controls.Add(this.평가수익label, 1, 3);
		this.tableLayoutPanel2.Location = new System.Drawing.Point(1434, 3);
		this.tableLayoutPanel2.Name = "tableLayoutPanel2";
		this.tableLayoutPanel2.RowCount = 5;
		this.tableLayoutPanel2.RowStyles.Add(new System.Windows.Forms.RowStyle(System.Windows.Forms.SizeType.Percent, 20f));
		this.tableLayoutPanel2.RowStyles.Add(new System.Windows.Forms.RowStyle(System.Windows.Forms.SizeType.Percent, 20f));
		this.tableLayoutPanel2.RowStyles.Add(new System.Windows.Forms.RowStyle(System.Windows.Forms.SizeType.Percent, 20f));
		this.tableLayoutPanel2.RowStyles.Add(new System.Windows.Forms.RowStyle(System.Windows.Forms.SizeType.Percent, 20f));
		this.tableLayoutPanel2.RowStyles.Add(new System.Windows.Forms.RowStyle(System.Windows.Forms.SizeType.Percent, 20f));
		this.tableLayoutPanel2.Size = new System.Drawing.Size(317, 184);
		this.tableLayoutPanel2.TabIndex = 3;
		this.수익률label.Anchor = System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom | System.Windows.Forms.AnchorStyles.Left | System.Windows.Forms.AnchorStyles.Right;
		this.수익률label.AutoSize = true;
		this.수익률label.BackColor = System.Drawing.Color.White;
		this.수익률label.Location = new System.Drawing.Point(161, 144);
		this.수익률label.Name = "수익률label";
		this.수익률label.Size = new System.Drawing.Size(153, 40);
		this.수익률label.TabIndex = 9;
		this.수익률label.Text = "0";
		this.수익률label.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
		this.평가금label.Anchor = System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom | System.Windows.Forms.AnchorStyles.Left | System.Windows.Forms.AnchorStyles.Right;
		this.평가금label.AutoSize = true;
		this.평가금label.BackColor = System.Drawing.Color.White;
		this.평가금label.Location = new System.Drawing.Point(161, 72);
		this.평가금label.Name = "평가금label";
		this.평가금label.Size = new System.Drawing.Size(153, 36);
		this.평가금label.TabIndex = 7;
		this.평가금label.Text = "0";
		this.평가금label.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
		this.매수금label.Anchor = System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom | System.Windows.Forms.AnchorStyles.Left | System.Windows.Forms.AnchorStyles.Right;
		this.매수금label.AutoSize = true;
		this.매수금label.BackColor = System.Drawing.Color.White;
		this.매수금label.Location = new System.Drawing.Point(161, 36);
		this.매수금label.Name = "매수금label";
		this.매수금label.Size = new System.Drawing.Size(153, 36);
		this.매수금label.TabIndex = 6;
		this.매수금label.Text = "0";
		this.매수금label.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
		this.예수금label.Anchor = System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom | System.Windows.Forms.AnchorStyles.Left | System.Windows.Forms.AnchorStyles.Right;
		this.예수금label.AutoSize = true;
		this.예수금label.BackColor = System.Drawing.Color.White;
		this.예수금label.Location = new System.Drawing.Point(161, 0);
		this.예수금label.Name = "예수금label";
		this.예수금label.Size = new System.Drawing.Size(153, 36);
		this.예수금label.TabIndex = 5;
		this.예수금label.Text = "0";
		this.예수금label.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
		this.label2.Anchor = System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom | System.Windows.Forms.AnchorStyles.Left | System.Windows.Forms.AnchorStyles.Right;
		this.label2.AutoSize = true;
		this.label2.BackColor = System.Drawing.Color.White;
		this.label2.Location = new System.Drawing.Point(3, 0);
		this.label2.Name = "label2";
		this.label2.Size = new System.Drawing.Size(152, 36);
		this.label2.TabIndex = 0;
		this.label2.Text = "추정자산";
		this.label2.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
		this.label3.Anchor = System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom | System.Windows.Forms.AnchorStyles.Left | System.Windows.Forms.AnchorStyles.Right;
		this.label3.AutoSize = true;
		this.label3.BackColor = System.Drawing.Color.White;
		this.label3.Location = new System.Drawing.Point(3, 36);
		this.label3.Name = "label3";
		this.label3.Size = new System.Drawing.Size(152, 36);
		this.label3.TabIndex = 1;
		this.label3.Text = "주문가능";
		this.label3.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
		this.label4.Anchor = System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom | System.Windows.Forms.AnchorStyles.Left | System.Windows.Forms.AnchorStyles.Right;
		this.label4.AutoSize = true;
		this.label4.BackColor = System.Drawing.Color.White;
		this.label4.Location = new System.Drawing.Point(3, 72);
		this.label4.Name = "label4";
		this.label4.Size = new System.Drawing.Size(152, 36);
		this.label4.TabIndex = 2;
		this.label4.Text = "평가금(계좌)";
		this.label4.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
		this.label5.Anchor = System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom | System.Windows.Forms.AnchorStyles.Left | System.Windows.Forms.AnchorStyles.Right;
		this.label5.AutoSize = true;
		this.label5.BackColor = System.Drawing.Color.White;
		this.label5.Location = new System.Drawing.Point(3, 108);
		this.label5.Name = "label5";
		this.label5.Size = new System.Drawing.Size(152, 36);
		this.label5.TabIndex = 3;
		this.label5.Text = "평가수익";
		this.label5.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
		this.label6.Anchor = System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom | System.Windows.Forms.AnchorStyles.Left | System.Windows.Forms.AnchorStyles.Right;
		this.label6.AutoSize = true;
		this.label6.BackColor = System.Drawing.Color.White;
		this.label6.Location = new System.Drawing.Point(3, 144);
		this.label6.Name = "label6";
		this.label6.Size = new System.Drawing.Size(152, 40);
		this.label6.TabIndex = 4;
		this.label6.Text = "수익률";
		this.label6.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
		this.평가수익label.Anchor = System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom | System.Windows.Forms.AnchorStyles.Left | System.Windows.Forms.AnchorStyles.Right;
		this.평가수익label.AutoSize = true;
		this.평가수익label.BackColor = System.Drawing.Color.White;
		this.평가수익label.Location = new System.Drawing.Point(161, 108);
		this.평가수익label.Name = "평가수익label";
		this.평가수익label.Size = new System.Drawing.Size(153, 36);
		this.평가수익label.TabIndex = 8;
		this.평가수익label.Text = "0";
		this.평가수익label.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
		this.conditionCheckedListBox.Anchor = System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom | System.Windows.Forms.AnchorStyles.Left | System.Windows.Forms.AnchorStyles.Right;
		this.conditionCheckedListBox.Font = new System.Drawing.Font("굴림", 11.25f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 129);
		this.conditionCheckedListBox.FormattingEnabled = true;
		this.conditionCheckedListBox.Location = new System.Drawing.Point(3, 3);
		this.conditionCheckedListBox.Name = "conditionCheckedListBox";
		this.conditionCheckedListBox.Size = new System.Drawing.Size(276, 184);
		this.conditionCheckedListBox.TabIndex = 4;
		this.GetConditionButton.Location = new System.Drawing.Point(12, 12);
		this.GetConditionButton.Name = "GetConditionButton";
		this.GetConditionButton.Size = new System.Drawing.Size(110, 23);
		this.GetConditionButton.TabIndex = 5;
		this.GetConditionButton.Text = "조건식 Update";
		this.GetConditionButton.UseVisualStyleBackColor = true;
		this.conditionFilteredGridView.Anchor = System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom | System.Windows.Forms.AnchorStyles.Left | System.Windows.Forms.AnchorStyles.Right;
		dataGridViewCellStyle.Alignment = System.Windows.Forms.DataGridViewContentAlignment.MiddleCenter;
		dataGridViewCellStyle.BackColor = System.Drawing.SystemColors.Control;
		dataGridViewCellStyle.Font = new System.Drawing.Font("굴림", 9f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 129);
		dataGridViewCellStyle.ForeColor = System.Drawing.SystemColors.WindowText;
		dataGridViewCellStyle.SelectionBackColor = System.Drawing.SystemColors.Highlight;
		dataGridViewCellStyle.SelectionForeColor = System.Drawing.SystemColors.HighlightText;
		dataGridViewCellStyle.WrapMode = System.Windows.Forms.DataGridViewTriState.True;
		this.conditionFilteredGridView.ColumnHeadersDefaultCellStyle = dataGridViewCellStyle;
		this.conditionFilteredGridView.ColumnHeadersHeightSizeMode = System.Windows.Forms.DataGridViewColumnHeadersHeightSizeMode.AutoSize;
		this.conditionFilteredGridView.Columns.AddRange(this.조건명, this.종목명, this.종목코드, this.현재가, this.전일대비, this.등락률, this.거래량, this.시가, this.고가, this.저가);
		this.conditionFilteredGridView.Location = new System.Drawing.Point(285, 3);
		this.conditionFilteredGridView.Name = "conditionFilteredGridView";
		this.conditionFilteredGridView.ReadOnly = true;
		this.conditionFilteredGridView.RowTemplate.Height = 23;
		this.conditionFilteredGridView.Size = new System.Drawing.Size(1149, 184);
		this.conditionFilteredGridView.TabIndex = 6;
		this.조건명.HeaderText = "조건명";
		this.조건명.Name = "조건명";
		this.조건명.ReadOnly = true;
		this.조건명.SortMode = System.Windows.Forms.DataGridViewColumnSortMode.Programmatic;
		this.종목명.HeaderText = "종목명";
		this.종목명.Name = "종목명";
		this.종목명.ReadOnly = true;
		this.종목명.SortMode = System.Windows.Forms.DataGridViewColumnSortMode.Programmatic;
		this.종목코드.HeaderText = "종목코드";
		this.종목코드.Name = "종목코드";
		this.종목코드.ReadOnly = true;
		this.종목코드.SortMode = System.Windows.Forms.DataGridViewColumnSortMode.Programmatic;
		this.종목코드.Width = 80;
		this.현재가.HeaderText = "현재가";
		this.현재가.Name = "현재가";
		this.현재가.ReadOnly = true;
		this.현재가.SortMode = System.Windows.Forms.DataGridViewColumnSortMode.Programmatic;
		this.전일대비.HeaderText = "전일대비";
		this.전일대비.Name = "전일대비";
		this.전일대비.ReadOnly = true;
		this.전일대비.SortMode = System.Windows.Forms.DataGridViewColumnSortMode.Programmatic;
		this.등락률.HeaderText = "등락률";
		this.등락률.Name = "등락률";
		this.등락률.ReadOnly = true;
		this.등락률.SortMode = System.Windows.Forms.DataGridViewColumnSortMode.Programmatic;
		this.등락률.Width = 65;
		this.거래량.HeaderText = "거래량";
		this.거래량.Name = "거래량";
		this.거래량.ReadOnly = true;
		this.거래량.SortMode = System.Windows.Forms.DataGridViewColumnSortMode.Programmatic;
		this.시가.HeaderText = "시가";
		this.시가.Name = "시가";
		this.시가.ReadOnly = true;
		this.시가.SortMode = System.Windows.Forms.DataGridViewColumnSortMode.Programmatic;
		this.고가.HeaderText = "고가";
		this.고가.Name = "고가";
		this.고가.ReadOnly = true;
		this.고가.SortMode = System.Windows.Forms.DataGridViewColumnSortMode.Programmatic;
		this.저가.HeaderText = "저가";
		this.저가.Name = "저가";
		this.저가.ReadOnly = true;
		this.저가.SortMode = System.Windows.Forms.DataGridViewColumnSortMode.Programmatic;
		this.logTextBox.Anchor = System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom | System.Windows.Forms.AnchorStyles.Left | System.Windows.Forms.AnchorStyles.Right;
		this.logTextBox.BackColor = System.Drawing.SystemColors.Info;
		this.logTextBox.BorderStyle = System.Windows.Forms.BorderStyle.FixedSingle;
		this.logTextBox.Location = new System.Drawing.Point(3, 3);
		this.logTextBox.Multiline = true;
		this.logTextBox.Name = "logTextBox";
		this.logTextBox.ReadOnly = true;
		this.logTextBox.ScrollBars = System.Windows.Forms.ScrollBars.Vertical;
		this.logTextBox.Size = new System.Drawing.Size(587, 244);
		this.logTextBox.TabIndex = 7;
		this.ATStartButton.Location = new System.Drawing.Point(154, 12);
		this.ATStartButton.Name = "ATStartButton";
		this.ATStartButton.Size = new System.Drawing.Size(110, 23);
		this.ATStartButton.TabIndex = 8;
		this.ATStartButton.Text = "자동 매매 시작";
		this.ATStartButton.UseVisualStyleBackColor = true;
		this.chart1.Anchor = System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom | System.Windows.Forms.AnchorStyles.Left | System.Windows.Forms.AnchorStyles.Right;
		chartArea.AlignWithChartArea = "volumeChartArea";
		chartArea.AxisX.IsReversed = true;
		chartArea.AxisX.LabelStyle.Enabled = false;
		chartArea.AxisX.ScrollBar.Enabled = false;
		chartArea.AxisY.IsLabelAutoFit = false;
		chartArea.CursorX.IsUserSelectionEnabled = true;
		chartArea.InnerPlotPosition.Auto = false;
		chartArea.InnerPlotPosition.Height = 92.36364f;
		chartArea.InnerPlotPosition.Width = 90.32448f;
		chartArea.InnerPlotPosition.X = 1.675532f;
		chartArea.InnerPlotPosition.Y = 3.818182f;
		chartArea.Name = "PriceChartArea";
		chartArea.Position.Auto = false;
		chartArea.Position.Height = 55f;
		chartArea.Position.Width = 94f;
		chartArea.Position.X = 3f;
		chartArea.Position.Y = 3f;
		chartArea2.AxisX.IsReversed = true;
		chartArea2.AxisY.IsLabelAutoFit = false;
		chartArea2.CursorX.IsUserSelectionEnabled = true;
		chartArea2.InnerPlotPosition.Auto = false;
		chartArea2.InnerPlotPosition.Height = 80.86906f;
		chartArea2.InnerPlotPosition.Width = 90.32448f;
		chartArea2.InnerPlotPosition.X = 1.675532f;
		chartArea2.InnerPlotPosition.Y = 4.999996f;
		chartArea2.Name = "volumeChartArea";
		chartArea2.Position.Auto = false;
		chartArea2.Position.Height = 35f;
		chartArea2.Position.Width = 94f;
		chartArea2.Position.X = 3f;
		chartArea2.Position.Y = 59f;
		this.chart1.ChartAreas.Add(chartArea);
		this.chart1.ChartAreas.Add(chartArea2);
		this.chart1.Cursor = System.Windows.Forms.Cursors.Cross;
		this.chart1.Location = new System.Drawing.Point(3, 3);
		this.chart1.Name = "chart1";
		series.ChartArea = "PriceChartArea";
		series.ChartType = System.Windows.Forms.DataVisualization.Charting.SeriesChartType.Candlestick;
		series.Name = "priceSeries";
		series.YValuesPerPoint = 4;
		series2.ChartArea = "volumeChartArea";
		series2.Name = "volumeSeries";
		this.chart1.Series.Add(series);
		this.chart1.Series.Add(series2);
		this.chart1.Size = new System.Drawing.Size(1143, 244);
		this.chart1.TabIndex = 9;
		this.chart1.Text = "chart1";
		this.chartYLabel.Anchor = System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Right;
		this.chartYLabel.BackColor = System.Drawing.Color.NavajoWhite;
		this.chartYLabel.BorderStyle = System.Windows.Forms.BorderStyle.FixedSingle;
		this.chartYLabel.Location = new System.Drawing.Point(1078, 15);
		this.chartYLabel.Name = "chartYLabel";
		this.chartYLabel.Size = new System.Drawing.Size(71, 19);
		this.chartYLabel.TabIndex = 10;
		this.chartYLabel.TextAlign = System.Drawing.ContentAlignment.MiddleLeft;
		this.panel1.Anchor = System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom | System.Windows.Forms.AnchorStyles.Left | System.Windows.Forms.AnchorStyles.Right;
		this.panel1.Controls.Add(this.chartYLabel);
		this.panel1.Controls.Add(this.chart1);
		this.panel1.Location = new System.Drawing.Point(3, 3);
		this.panel1.Name = "panel1";
		this.panel1.Size = new System.Drawing.Size(1152, 250);
		this.panel1.TabIndex = 11;
		this.panel3.Anchor = System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom | System.Windows.Forms.AnchorStyles.Left | System.Windows.Forms.AnchorStyles.Right;
		this.panel3.Controls.Add(this.logTextBox);
		this.panel3.Location = new System.Drawing.Point(1161, 3);
		this.panel3.Name = "panel3";
		this.panel3.Size = new System.Drawing.Size(596, 250);
		this.panel3.TabIndex = 13;
		this.ATStopButton.Location = new System.Drawing.Point(273, 12);
		this.ATStopButton.Name = "ATStopButton";
		this.ATStopButton.Size = new System.Drawing.Size(110, 23);
		this.ATStopButton.TabIndex = 16;
		this.ATStopButton.Text = "자동 매매 종료";
		this.ATStopButton.UseVisualStyleBackColor = true;
		this.ATStopButton.Visible = false;
		this.holdJongmokGridView.Anchor = System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom | System.Windows.Forms.AnchorStyles.Left | System.Windows.Forms.AnchorStyles.Right;
		this.holdJongmokGridView.ColumnHeadersHeightSizeMode = System.Windows.Forms.DataGridViewColumnHeadersHeightSizeMode.AutoSize;
		this.holdJongmokGridView.Location = new System.Drawing.Point(3, 3);
		this.holdJongmokGridView.Name = "holdJongmokGridView";
		this.holdJongmokGridView.ReadOnly = true;
		this.holdJongmokGridView.RowTemplate.Height = 23;
		this.holdJongmokGridView.Size = new System.Drawing.Size(1754, 306);
		this.holdJongmokGridView.TabIndex = 14;
		this.tableLayoutPanel3.ColumnCount = 3;
		this.tableLayoutPanel3.ColumnStyles.Add(new System.Windows.Forms.ColumnStyle(System.Windows.Forms.SizeType.Percent, 19.7065f));
		this.tableLayoutPanel3.ColumnStyles.Add(new System.Windows.Forms.ColumnStyle(System.Windows.Forms.SizeType.Percent, 80.2935f));
		this.tableLayoutPanel3.ColumnStyles.Add(new System.Windows.Forms.ColumnStyle(System.Windows.Forms.SizeType.Absolute, 323f));
		this.tableLayoutPanel3.Controls.Add(this.conditionFilteredGridView, 1, 0);
		this.tableLayoutPanel3.Controls.Add(this.tableLayoutPanel2, 2, 0);
		this.tableLayoutPanel3.Controls.Add(this.conditionCheckedListBox, 0, 0);
		this.tableLayoutPanel3.Location = new System.Drawing.Point(12, 41);
		this.tableLayoutPanel3.Name = "tableLayoutPanel3";
		this.tableLayoutPanel3.RowCount = 1;
		this.tableLayoutPanel3.RowStyles.Add(new System.Windows.Forms.RowStyle(System.Windows.Forms.SizeType.Percent, 50f));
		this.tableLayoutPanel3.Size = new System.Drawing.Size(1760, 190);
		this.tableLayoutPanel3.TabIndex = 17;
		this.tableLayoutPanel4.ColumnCount = 2;
		this.tableLayoutPanel4.ColumnStyles.Add(new System.Windows.Forms.ColumnStyle(System.Windows.Forms.SizeType.Percent, 65.85088f));
		this.tableLayoutPanel4.ColumnStyles.Add(new System.Windows.Forms.ColumnStyle(System.Windows.Forms.SizeType.Percent, 34.14912f));
		this.tableLayoutPanel4.Controls.Add(this.panel3, 1, 0);
		this.tableLayoutPanel4.Controls.Add(this.panel1, 0, 0);
		this.tableLayoutPanel4.Location = new System.Drawing.Point(12, 694);
		this.tableLayoutPanel4.Name = "tableLayoutPanel4";
		this.tableLayoutPanel4.RowCount = 1;
		this.tableLayoutPanel4.RowStyles.Add(new System.Windows.Forms.RowStyle(System.Windows.Forms.SizeType.Percent, 50f));
		this.tableLayoutPanel4.Size = new System.Drawing.Size(1760, 256);
		this.tableLayoutPanel4.TabIndex = 18;
		this.tableLayoutPanel5.ColumnCount = 1;
		this.tableLayoutPanel5.ColumnStyles.Add(new System.Windows.Forms.ColumnStyle(System.Windows.Forms.SizeType.Percent, 50f));
		this.tableLayoutPanel5.Controls.Add(this.holdJongmokGridView, 0, 0);
		this.tableLayoutPanel5.Location = new System.Drawing.Point(12, 234);
		this.tableLayoutPanel5.Name = "tableLayoutPanel5";
		this.tableLayoutPanel5.RowCount = 1;
		this.tableLayoutPanel5.RowStyles.Add(new System.Windows.Forms.RowStyle(System.Windows.Forms.SizeType.Percent, 50f));
		this.tableLayoutPanel5.Size = new System.Drawing.Size(1760, 454);
		this.tableLayoutPanel5.TabIndex = 19;
		this.BuyTestButton.Location = new System.Drawing.Point(771, 12);
		this.BuyTestButton.Name = "BuyTestButton";
		this.BuyTestButton.Size = new System.Drawing.Size(75, 23);
		this.BuyTestButton.TabIndex = 20;
		this.BuyTestButton.Text = "매수";
		this.BuyTestButton.UseVisualStyleBackColor = true;
		this.SellTestButton.Location = new System.Drawing.Point(852, 12);
		this.SellTestButton.Name = "SellTestButton";
		this.SellTestButton.Size = new System.Drawing.Size(75, 23);
		this.SellTestButton.TabIndex = 21;
		this.SellTestButton.Text = "매도";
		this.SellTestButton.UseVisualStyleBackColor = true;
		this.testCode.Location = new System.Drawing.Point(432, 13);
		this.testCode.Name = "testCode";
		this.testCode.Size = new System.Drawing.Size(100, 21);
		this.testCode.TabIndex = 22;
		this.testPrice.Location = new System.Drawing.Point(538, 13);
		this.testPrice.Name = "testPrice";
		this.testPrice.Size = new System.Drawing.Size(100, 21);
		this.testPrice.TabIndex = 23;
		this.testAmount.Location = new System.Drawing.Point(644, 13);
		this.testAmount.Name = "testAmount";
		this.testAmount.Size = new System.Drawing.Size(100, 21);
		this.testAmount.TabIndex = 24;
		base.AutoScaleDimensions = new System.Drawing.SizeF(7f, 12f);
		base.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
		base.ClientSize = new System.Drawing.Size(1784, 965);
		base.Controls.Add(this.testAmount);
		base.Controls.Add(this.testPrice);
		base.Controls.Add(this.testCode);
		base.Controls.Add(this.SellTestButton);
		base.Controls.Add(this.BuyTestButton);
		base.Controls.Add(this.tableLayoutPanel5);
		base.Controls.Add(this.tableLayoutPanel4);
		base.Controls.Add(this.tableLayoutPanel3);
		base.Controls.Add(this.ATStopButton);
		base.Controls.Add(this.ATStartButton);
		base.Controls.Add(this.GetConditionButton);
		base.Controls.Add(this.tableLayoutPanel1);
		base.Controls.Add(this.LoginButton);
		base.Controls.Add(this.axKHOpenAPI1);
		base.Name = "Form1";
		this.MinimumSize = new System.Drawing.Size(1200, 700);
		base.StartPosition = System.Windows.Forms.FormStartPosition.CenterScreen;
		this.Text = "AutoTrading";
		((System.ComponentModel.ISupportInitialize)this.axKHOpenAPI1).EndInit();
		this.tableLayoutPanel1.ResumeLayout(false);
		this.tableLayoutPanel1.PerformLayout();
		this.tableLayoutPanel2.ResumeLayout(false);
		this.tableLayoutPanel2.PerformLayout();
		((System.ComponentModel.ISupportInitialize)this.conditionFilteredGridView).EndInit();
		((System.ComponentModel.ISupportInitialize)this.chart1).EndInit();
		this.panel1.ResumeLayout(false);
		this.panel3.ResumeLayout(false);
		this.panel3.PerformLayout();
		((System.ComponentModel.ISupportInitialize)this.holdJongmokGridView).EndInit();
		this.tableLayoutPanel3.ResumeLayout(false);
		this.tableLayoutPanel4.ResumeLayout(false);
		this.tableLayoutPanel5.ResumeLayout(false);
		base.ResumeLayout(false);
		base.PerformLayout();
	}
}
