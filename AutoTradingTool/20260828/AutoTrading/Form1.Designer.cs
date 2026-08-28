
namespace AutoTradingTest
{
    partial class Form1
    {
        /// <summary>
        /// 필수 디자이너 변수입니다.
        /// </summary>
        private System.ComponentModel.IContainer components = null;

        /// <summary>
        /// 사용 중인 모든 리소스를 정리합니다.
        /// </summary>
        /// <param name="disposing">관리되는 리소스를 삭제해야 하면 true이고, 그렇지 않으면 false입니다.</param>
        protected override void Dispose(bool disposing)
        {
            if (disposing && (components != null))
            {
                components.Dispose();
            }
            base.Dispose(disposing);
        }

        #region Windows Form 디자이너에서 생성한 코드

        /// <summary>
        /// 디자이너 지원에 필요한 메서드입니다. 
        /// 이 메서드의 내용을 코드 편집기로 수정하지 마세요.
        /// </summary>
        private void InitializeComponent()
        {
            System.ComponentModel.ComponentResourceManager resources = new System.ComponentModel.ComponentResourceManager(typeof(Form1));
            System.Windows.Forms.DataGridViewCellStyle dataGridViewCellStyle1 = new System.Windows.Forms.DataGridViewCellStyle();
            System.Windows.Forms.DataVisualization.Charting.ChartArea chartArea1 = new System.Windows.Forms.DataVisualization.Charting.ChartArea();
            System.Windows.Forms.DataVisualization.Charting.ChartArea chartArea2 = new System.Windows.Forms.DataVisualization.Charting.ChartArea();
            System.Windows.Forms.DataVisualization.Charting.Series series1 = new System.Windows.Forms.DataVisualization.Charting.Series();
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
            ((System.ComponentModel.ISupportInitialize)(this.axKHOpenAPI1)).BeginInit();
            this.tableLayoutPanel1.SuspendLayout();
            this.tableLayoutPanel2.SuspendLayout();
            ((System.ComponentModel.ISupportInitialize)(this.conditionFilteredGridView)).BeginInit();
            ((System.ComponentModel.ISupportInitialize)(this.chart1)).BeginInit();
            this.panel1.SuspendLayout();
            this.panel3.SuspendLayout();
            ((System.ComponentModel.ISupportInitialize)(this.holdJongmokGridView)).BeginInit();
            this.tableLayoutPanel3.SuspendLayout();
            this.tableLayoutPanel4.SuspendLayout();
            this.tableLayoutPanel5.SuspendLayout();
            this.SuspendLayout();
            // 
            // axKHOpenAPI1
            // 
            this.axKHOpenAPI1.Enabled = true;
            this.axKHOpenAPI1.Location = new System.Drawing.Point(0, 0);
            this.axKHOpenAPI1.Name = "axKHOpenAPI1";
            this.axKHOpenAPI1.OcxState = ((System.Windows.Forms.AxHost.State)(resources.GetObject("axKHOpenAPI1.OcxState")));
            this.axKHOpenAPI1.Size = new System.Drawing.Size(1, 1);
            this.axKHOpenAPI1.TabIndex = 0;
            this.axKHOpenAPI1.Visible = false;
            // 
            // LoginButton
            // 
            this.LoginButton.Anchor = ((System.Windows.Forms.AnchorStyles)((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Right)));
            this.LoginButton.Location = new System.Drawing.Point(1591, 12);
            this.LoginButton.Name = "LoginButton";
            this.LoginButton.Size = new System.Drawing.Size(75, 23);
            this.LoginButton.TabIndex = 1;
            this.LoginButton.Text = "로그인";
            this.LoginButton.UseVisualStyleBackColor = true;
            // 
            // tableLayoutPanel1
            // 
            this.tableLayoutPanel1.ColumnCount = 4;
            this.tableLayoutPanel1.ColumnStyles.Add(new System.Windows.Forms.ColumnStyle(System.Windows.Forms.SizeType.Percent, 25F));
            this.tableLayoutPanel1.ColumnStyles.Add(new System.Windows.Forms.ColumnStyle(System.Windows.Forms.SizeType.Percent, 25F));
            this.tableLayoutPanel1.ColumnStyles.Add(new System.Windows.Forms.ColumnStyle(System.Windows.Forms.SizeType.Percent, 25F));
            this.tableLayoutPanel1.ColumnStyles.Add(new System.Windows.Forms.ColumnStyle(System.Windows.Forms.SizeType.Percent, 25F));
            this.tableLayoutPanel1.Controls.Add(this.ServerGubun, 3, 0);
            this.tableLayoutPanel1.Controls.Add(this.label1, 0, 0);
            this.tableLayoutPanel1.Controls.Add(this.UserID, 2, 0);
            this.tableLayoutPanel1.Controls.Add(this.AccountList, 1, 0);
            this.tableLayoutPanel1.Anchor = ((System.Windows.Forms.AnchorStyles)((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Right)));
            this.tableLayoutPanel1.Location = new System.Drawing.Point(1202, 12);
            this.tableLayoutPanel1.Name = "tableLayoutPanel1";
            this.tableLayoutPanel1.RowCount = 1;
            this.tableLayoutPanel1.RowStyles.Add(new System.Windows.Forms.RowStyle(System.Windows.Forms.SizeType.Percent, 100F));
            this.tableLayoutPanel1.Size = new System.Drawing.Size(383, 23);
            this.tableLayoutPanel1.TabIndex = 2;
            // 
            // ServerGubun
            // 
            this.ServerGubun.Anchor = ((System.Windows.Forms.AnchorStyles)((((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom) 
            | System.Windows.Forms.AnchorStyles.Left) 
            | System.Windows.Forms.AnchorStyles.Right)));
            this.ServerGubun.AutoSize = true;
            this.ServerGubun.BackColor = System.Drawing.Color.White;
            this.ServerGubun.Location = new System.Drawing.Point(288, 0);
            this.ServerGubun.Name = "ServerGubun";
            this.ServerGubun.Size = new System.Drawing.Size(92, 23);
            this.ServerGubun.TabIndex = 2;
            this.ServerGubun.Text = "Server";
            this.ServerGubun.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // label1
            // 
            this.label1.Anchor = ((System.Windows.Forms.AnchorStyles)((((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom) 
            | System.Windows.Forms.AnchorStyles.Left) 
            | System.Windows.Forms.AnchorStyles.Right)));
            this.label1.AutoSize = true;
            this.label1.BackColor = System.Drawing.Color.White;
            this.label1.Location = new System.Drawing.Point(3, 0);
            this.label1.Name = "label1";
            this.label1.Size = new System.Drawing.Size(89, 23);
            this.label1.TabIndex = 0;
            this.label1.Text = "계좌번호";
            this.label1.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // UserID
            // 
            this.UserID.Anchor = ((System.Windows.Forms.AnchorStyles)((((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom) 
            | System.Windows.Forms.AnchorStyles.Left) 
            | System.Windows.Forms.AnchorStyles.Right)));
            this.UserID.AutoSize = true;
            this.UserID.BackColor = System.Drawing.Color.White;
            this.UserID.Location = new System.Drawing.Point(193, 0);
            this.UserID.Name = "UserID";
            this.UserID.Size = new System.Drawing.Size(89, 23);
            this.UserID.TabIndex = 1;
            this.UserID.Text = "ID";
            this.UserID.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // AccountList
            // 
            this.AccountList.Anchor = ((System.Windows.Forms.AnchorStyles)((((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom) 
            | System.Windows.Forms.AnchorStyles.Left) 
            | System.Windows.Forms.AnchorStyles.Right)));
            this.AccountList.FormattingEnabled = true;
            this.AccountList.Location = new System.Drawing.Point(98, 3);
            this.AccountList.Name = "AccountList";
            this.AccountList.Size = new System.Drawing.Size(89, 20);
            this.AccountList.TabIndex = 3;
            // 
            // tableLayoutPanel2
            // 
            this.tableLayoutPanel2.Anchor = ((System.Windows.Forms.AnchorStyles)((((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom) 
            | System.Windows.Forms.AnchorStyles.Left) 
            | System.Windows.Forms.AnchorStyles.Right)));
            this.tableLayoutPanel2.ColumnCount = 2;
            this.tableLayoutPanel2.ColumnStyles.Add(new System.Windows.Forms.ColumnStyle(System.Windows.Forms.SizeType.Percent, 50F));
            this.tableLayoutPanel2.ColumnStyles.Add(new System.Windows.Forms.ColumnStyle(System.Windows.Forms.SizeType.Percent, 50F));
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
            this.tableLayoutPanel2.RowStyles.Add(new System.Windows.Forms.RowStyle(System.Windows.Forms.SizeType.Percent, 20F));
            this.tableLayoutPanel2.RowStyles.Add(new System.Windows.Forms.RowStyle(System.Windows.Forms.SizeType.Percent, 20F));
            this.tableLayoutPanel2.RowStyles.Add(new System.Windows.Forms.RowStyle(System.Windows.Forms.SizeType.Percent, 20F));
            this.tableLayoutPanel2.RowStyles.Add(new System.Windows.Forms.RowStyle(System.Windows.Forms.SizeType.Percent, 20F));
            this.tableLayoutPanel2.RowStyles.Add(new System.Windows.Forms.RowStyle(System.Windows.Forms.SizeType.Percent, 20F));
            this.tableLayoutPanel2.Size = new System.Drawing.Size(317, 184);
            this.tableLayoutPanel2.TabIndex = 3;
            // 
            // 수익률label
            // 
            this.수익률label.Anchor = ((System.Windows.Forms.AnchorStyles)((((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom) 
            | System.Windows.Forms.AnchorStyles.Left) 
            | System.Windows.Forms.AnchorStyles.Right)));
            this.수익률label.AutoSize = true;
            this.수익률label.BackColor = System.Drawing.Color.White;
            this.수익률label.Location = new System.Drawing.Point(161, 144);
            this.수익률label.Name = "수익률label";
            this.수익률label.Size = new System.Drawing.Size(153, 40);
            this.수익률label.TabIndex = 9;
            this.수익률label.Text = "0";
            this.수익률label.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // 평가금label
            // 
            this.평가금label.Anchor = ((System.Windows.Forms.AnchorStyles)((((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom) 
            | System.Windows.Forms.AnchorStyles.Left) 
            | System.Windows.Forms.AnchorStyles.Right)));
            this.평가금label.AutoSize = true;
            this.평가금label.BackColor = System.Drawing.Color.White;
            this.평가금label.Location = new System.Drawing.Point(161, 72);
            this.평가금label.Name = "평가금label";
            this.평가금label.Size = new System.Drawing.Size(153, 36);
            this.평가금label.TabIndex = 7;
            this.평가금label.Text = "0";
            this.평가금label.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // 매수금label
            // 
            this.매수금label.Anchor = ((System.Windows.Forms.AnchorStyles)((((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom) 
            | System.Windows.Forms.AnchorStyles.Left) 
            | System.Windows.Forms.AnchorStyles.Right)));
            this.매수금label.AutoSize = true;
            this.매수금label.BackColor = System.Drawing.Color.White;
            this.매수금label.Location = new System.Drawing.Point(161, 36);
            this.매수금label.Name = "매수금label";
            this.매수금label.Size = new System.Drawing.Size(153, 36);
            this.매수금label.TabIndex = 6;
            this.매수금label.Text = "0";
            this.매수금label.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // 예수금label
            // 
            this.예수금label.Anchor = ((System.Windows.Forms.AnchorStyles)((((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom) 
            | System.Windows.Forms.AnchorStyles.Left) 
            | System.Windows.Forms.AnchorStyles.Right)));
            this.예수금label.AutoSize = true;
            this.예수금label.BackColor = System.Drawing.Color.White;
            this.예수금label.Location = new System.Drawing.Point(161, 0);
            this.예수금label.Name = "예수금label";
            this.예수금label.Size = new System.Drawing.Size(153, 36);
            this.예수금label.TabIndex = 5;
            this.예수금label.Text = "0";
            this.예수금label.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // label2
            // 
            this.label2.Anchor = ((System.Windows.Forms.AnchorStyles)((((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom) 
            | System.Windows.Forms.AnchorStyles.Left) 
            | System.Windows.Forms.AnchorStyles.Right)));
            this.label2.AutoSize = true;
            this.label2.BackColor = System.Drawing.Color.White;
            this.label2.Location = new System.Drawing.Point(3, 0);
            this.label2.Name = "label2";
            this.label2.Size = new System.Drawing.Size(152, 36);
            this.label2.TabIndex = 0;
            this.label2.Text = "추정자산";
            this.label2.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // label3
            // 
            this.label3.Anchor = ((System.Windows.Forms.AnchorStyles)((((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom) 
            | System.Windows.Forms.AnchorStyles.Left) 
            | System.Windows.Forms.AnchorStyles.Right)));
            this.label3.AutoSize = true;
            this.label3.BackColor = System.Drawing.Color.White;
            this.label3.Location = new System.Drawing.Point(3, 36);
            this.label3.Name = "label3";
            this.label3.Size = new System.Drawing.Size(152, 36);
            this.label3.TabIndex = 1;
            this.label3.Text = "주문가능(추정)";
            this.label3.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // label4
            // 
            this.label4.Anchor = ((System.Windows.Forms.AnchorStyles)((((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom) 
            | System.Windows.Forms.AnchorStyles.Left) 
            | System.Windows.Forms.AnchorStyles.Right)));
            this.label4.AutoSize = true;
            this.label4.BackColor = System.Drawing.Color.White;
            this.label4.Location = new System.Drawing.Point(3, 72);
            this.label4.Name = "label4";
            this.label4.Size = new System.Drawing.Size(152, 36);
            this.label4.TabIndex = 2;
            this.label4.Text = "평가금(계좌)";
            this.label4.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // label5
            // 
            this.label5.Anchor = ((System.Windows.Forms.AnchorStyles)((((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom) 
            | System.Windows.Forms.AnchorStyles.Left) 
            | System.Windows.Forms.AnchorStyles.Right)));
            this.label5.AutoSize = true;
            this.label5.BackColor = System.Drawing.Color.White;
            this.label5.Location = new System.Drawing.Point(3, 108);
            this.label5.Name = "label5";
            this.label5.Size = new System.Drawing.Size(152, 36);
            this.label5.TabIndex = 3;
            this.label5.Text = "평가수익";
            this.label5.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // label6
            // 
            this.label6.Anchor = ((System.Windows.Forms.AnchorStyles)((((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom) 
            | System.Windows.Forms.AnchorStyles.Left) 
            | System.Windows.Forms.AnchorStyles.Right)));
            this.label6.AutoSize = true;
            this.label6.BackColor = System.Drawing.Color.White;
            this.label6.Location = new System.Drawing.Point(3, 144);
            this.label6.Name = "label6";
            this.label6.Size = new System.Drawing.Size(152, 40);
            this.label6.TabIndex = 4;
            this.label6.Text = "수익률";
            this.label6.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // 평가수익label
            // 
            this.평가수익label.Anchor = ((System.Windows.Forms.AnchorStyles)((((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom) 
            | System.Windows.Forms.AnchorStyles.Left) 
            | System.Windows.Forms.AnchorStyles.Right)));
            this.평가수익label.AutoSize = true;
            this.평가수익label.BackColor = System.Drawing.Color.White;
            this.평가수익label.Location = new System.Drawing.Point(161, 108);
            this.평가수익label.Name = "평가수익label";
            this.평가수익label.Size = new System.Drawing.Size(153, 36);
            this.평가수익label.TabIndex = 8;
            this.평가수익label.Text = "0";
            this.평가수익label.TextAlign = System.Drawing.ContentAlignment.MiddleCenter;
            // 
            // conditionCheckedListBox
            // 
            this.conditionCheckedListBox.Anchor = ((System.Windows.Forms.AnchorStyles)((((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom) 
            | System.Windows.Forms.AnchorStyles.Left) 
            | System.Windows.Forms.AnchorStyles.Right)));
            this.conditionCheckedListBox.Font = new System.Drawing.Font("굴림", 11.25F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(129)));
            this.conditionCheckedListBox.FormattingEnabled = true;
            this.conditionCheckedListBox.Location = new System.Drawing.Point(3, 3);
            this.conditionCheckedListBox.Name = "conditionCheckedListBox";
            this.conditionCheckedListBox.Size = new System.Drawing.Size(276, 184);
            this.conditionCheckedListBox.TabIndex = 4;
            // 
            // GetConditionButton
            // 
            this.GetConditionButton.Location = new System.Drawing.Point(12, 12);
            this.GetConditionButton.Name = "GetConditionButton";
            this.GetConditionButton.Size = new System.Drawing.Size(110, 23);
            this.GetConditionButton.TabIndex = 5;
            this.GetConditionButton.Text = "조건식 Update";
            this.GetConditionButton.UseVisualStyleBackColor = true;
            // 
            // conditionFilteredGridView
            // 
            this.conditionFilteredGridView.Anchor = ((System.Windows.Forms.AnchorStyles)((((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom) 
            | System.Windows.Forms.AnchorStyles.Left) 
            | System.Windows.Forms.AnchorStyles.Right)));
            dataGridViewCellStyle1.Alignment = System.Windows.Forms.DataGridViewContentAlignment.MiddleCenter;
            dataGridViewCellStyle1.BackColor = System.Drawing.SystemColors.Control;
            dataGridViewCellStyle1.Font = new System.Drawing.Font("굴림", 9F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(129)));
            dataGridViewCellStyle1.ForeColor = System.Drawing.SystemColors.WindowText;
            dataGridViewCellStyle1.SelectionBackColor = System.Drawing.SystemColors.Highlight;
            dataGridViewCellStyle1.SelectionForeColor = System.Drawing.SystemColors.HighlightText;
            dataGridViewCellStyle1.WrapMode = System.Windows.Forms.DataGridViewTriState.True;
            this.conditionFilteredGridView.ColumnHeadersDefaultCellStyle = dataGridViewCellStyle1;
            this.conditionFilteredGridView.ColumnHeadersHeightSizeMode = System.Windows.Forms.DataGridViewColumnHeadersHeightSizeMode.AutoSize;
            this.conditionFilteredGridView.Columns.AddRange(new System.Windows.Forms.DataGridViewColumn[] {
            this.조건명,
            this.종목명,
            this.종목코드,
            this.현재가,
            this.전일대비,
            this.등락률,
            this.거래량,
            this.시가,
            this.고가,
            this.저가});
            this.conditionFilteredGridView.Location = new System.Drawing.Point(285, 3);
            this.conditionFilteredGridView.Name = "conditionFilteredGridView";
            this.conditionFilteredGridView.ReadOnly = true;
            this.conditionFilteredGridView.RowTemplate.Height = 23;
            this.conditionFilteredGridView.Size = new System.Drawing.Size(1149, 184);
            this.conditionFilteredGridView.TabIndex = 6;
            // 
            // 조건명
            // 
            this.조건명.HeaderText = "조건명";
            this.조건명.Name = "조건명";
            this.조건명.ReadOnly = true;
            this.조건명.SortMode = System.Windows.Forms.DataGridViewColumnSortMode.Programmatic;
            // 
            // 종목명
            // 
            this.종목명.HeaderText = "종목명";
            this.종목명.Name = "종목명";
            this.종목명.ReadOnly = true;
            this.종목명.SortMode = System.Windows.Forms.DataGridViewColumnSortMode.Programmatic;
            // 
            // 종목코드
            // 
            this.종목코드.HeaderText = "종목코드";
            this.종목코드.Name = "종목코드";
            this.종목코드.ReadOnly = true;
            this.종목코드.SortMode = System.Windows.Forms.DataGridViewColumnSortMode.Programmatic;
            this.종목코드.Width = 80;
            // 
            // 현재가
            // 
            this.현재가.HeaderText = "현재가";
            this.현재가.Name = "현재가";
            this.현재가.ReadOnly = true;
            this.현재가.SortMode = System.Windows.Forms.DataGridViewColumnSortMode.Programmatic;
            // 
            // 전일대비
            // 
            this.전일대비.HeaderText = "전일대비";
            this.전일대비.Name = "전일대비";
            this.전일대비.ReadOnly = true;
            this.전일대비.SortMode = System.Windows.Forms.DataGridViewColumnSortMode.Programmatic;
            // 
            // 등락률
            // 
            this.등락률.HeaderText = "등락률";
            this.등락률.Name = "등락률";
            this.등락률.ReadOnly = true;
            this.등락률.SortMode = System.Windows.Forms.DataGridViewColumnSortMode.Programmatic;
            this.등락률.Width = 65;
            // 
            // 거래량
            // 
            this.거래량.HeaderText = "거래량";
            this.거래량.Name = "거래량";
            this.거래량.ReadOnly = true;
            this.거래량.SortMode = System.Windows.Forms.DataGridViewColumnSortMode.Programmatic;
            // 
            // 시가
            // 
            this.시가.HeaderText = "시가";
            this.시가.Name = "시가";
            this.시가.ReadOnly = true;
            this.시가.SortMode = System.Windows.Forms.DataGridViewColumnSortMode.Programmatic;
            // 
            // 고가
            // 
            this.고가.HeaderText = "고가";
            this.고가.Name = "고가";
            this.고가.ReadOnly = true;
            this.고가.SortMode = System.Windows.Forms.DataGridViewColumnSortMode.Programmatic;
            // 
            // 저가
            // 
            this.저가.HeaderText = "저가";
            this.저가.Name = "저가";
            this.저가.ReadOnly = true;
            this.저가.SortMode = System.Windows.Forms.DataGridViewColumnSortMode.Programmatic;
            // 
            // logTextBox
            // 
            this.logTextBox.Anchor = ((System.Windows.Forms.AnchorStyles)((((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom) 
            | System.Windows.Forms.AnchorStyles.Left) 
            | System.Windows.Forms.AnchorStyles.Right)));
            this.logTextBox.BackColor = System.Drawing.SystemColors.Info;
            this.logTextBox.BorderStyle = System.Windows.Forms.BorderStyle.FixedSingle;
            this.logTextBox.Location = new System.Drawing.Point(3, 3);
            this.logTextBox.Multiline = true;
            this.logTextBox.Name = "logTextBox";
            this.logTextBox.ReadOnly = true;
            this.logTextBox.ScrollBars = System.Windows.Forms.ScrollBars.Vertical;
            this.logTextBox.Size = new System.Drawing.Size(587, 244);
            this.logTextBox.TabIndex = 7;
            // 
            // ATStartButton
            // 
            this.ATStartButton.Location = new System.Drawing.Point(154, 12);
            this.ATStartButton.Name = "ATStartButton";
            this.ATStartButton.Size = new System.Drawing.Size(110, 23);
            this.ATStartButton.TabIndex = 8;
            this.ATStartButton.Text = "자동 매매 시작";
            this.ATStartButton.UseVisualStyleBackColor = true;
            // 
            // chart1
            // 
            this.chart1.Anchor = ((System.Windows.Forms.AnchorStyles)((((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom) 
            | System.Windows.Forms.AnchorStyles.Left) 
            | System.Windows.Forms.AnchorStyles.Right)));
            chartArea1.AlignWithChartArea = "volumeChartArea";
            chartArea1.AxisX.IsReversed = true;
            chartArea1.AxisX.LabelStyle.Enabled = false;
            chartArea1.AxisX.ScrollBar.Enabled = false;
            chartArea1.AxisY.IsLabelAutoFit = false;
            chartArea1.CursorX.IsUserSelectionEnabled = true;
            chartArea1.InnerPlotPosition.Auto = false;
            chartArea1.InnerPlotPosition.Height = 92.36364F;
            chartArea1.InnerPlotPosition.Width = 90.32448F;
            chartArea1.InnerPlotPosition.X = 1.675532F;
            chartArea1.InnerPlotPosition.Y = 3.818182F;
            chartArea1.Name = "PriceChartArea";
            chartArea1.Position.Auto = false;
            chartArea1.Position.Height = 55F;
            chartArea1.Position.Width = 94F;
            chartArea1.Position.X = 3F;
            chartArea1.Position.Y = 3F;
            chartArea2.AxisX.IsReversed = true;
            chartArea2.AxisY.IsLabelAutoFit = false;
            chartArea2.CursorX.IsUserSelectionEnabled = true;
            chartArea2.InnerPlotPosition.Auto = false;
            chartArea2.InnerPlotPosition.Height = 80.86906F;
            chartArea2.InnerPlotPosition.Width = 90.32448F;
            chartArea2.InnerPlotPosition.X = 1.675532F;
            chartArea2.InnerPlotPosition.Y = 4.999996F;
            chartArea2.Name = "volumeChartArea";
            chartArea2.Position.Auto = false;
            chartArea2.Position.Height = 35F;
            chartArea2.Position.Width = 94F;
            chartArea2.Position.X = 3F;
            chartArea2.Position.Y = 59F;
            this.chart1.ChartAreas.Add(chartArea1);
            this.chart1.ChartAreas.Add(chartArea2);
            this.chart1.Cursor = System.Windows.Forms.Cursors.Cross;
            this.chart1.Location = new System.Drawing.Point(3, 3);
            this.chart1.Name = "chart1";
            series1.ChartArea = "PriceChartArea";
            series1.ChartType = System.Windows.Forms.DataVisualization.Charting.SeriesChartType.Candlestick;
            series1.Name = "priceSeries";
            series1.YValuesPerPoint = 4;
            series2.ChartArea = "volumeChartArea";
            series2.Name = "volumeSeries";
            this.chart1.Series.Add(series1);
            this.chart1.Series.Add(series2);
            this.chart1.Size = new System.Drawing.Size(1143, 244);
            this.chart1.TabIndex = 9;
            this.chart1.Text = "chart1";
            // 
            // chartYLabel
            // 
            this.chartYLabel.Anchor = ((System.Windows.Forms.AnchorStyles)((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Right)));
            this.chartYLabel.BackColor = System.Drawing.Color.NavajoWhite;
            this.chartYLabel.BorderStyle = System.Windows.Forms.BorderStyle.FixedSingle;
            this.chartYLabel.Location = new System.Drawing.Point(1078, 15);
            this.chartYLabel.Name = "chartYLabel";
            this.chartYLabel.Size = new System.Drawing.Size(71, 19);
            this.chartYLabel.TabIndex = 10;
            this.chartYLabel.TextAlign = System.Drawing.ContentAlignment.MiddleLeft;
            // 
            // panel1
            // 
            this.panel1.Anchor = ((System.Windows.Forms.AnchorStyles)((((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom) 
            | System.Windows.Forms.AnchorStyles.Left) 
            | System.Windows.Forms.AnchorStyles.Right)));
            this.panel1.Controls.Add(this.chartYLabel);
            this.panel1.Controls.Add(this.chart1);
            this.panel1.Location = new System.Drawing.Point(3, 3);
            this.panel1.Name = "panel1";
            this.panel1.Size = new System.Drawing.Size(1152, 250);
            this.panel1.TabIndex = 11;
            // 
            // panel3
            // 
            this.panel3.Anchor = ((System.Windows.Forms.AnchorStyles)((((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom) 
            | System.Windows.Forms.AnchorStyles.Left) 
            | System.Windows.Forms.AnchorStyles.Right)));
            this.panel3.Controls.Add(this.logTextBox);
            this.panel3.Location = new System.Drawing.Point(1161, 3);
            this.panel3.Name = "panel3";
            this.panel3.Size = new System.Drawing.Size(596, 250);
            this.panel3.TabIndex = 13;
            // 
            // ATStopButton
            // 
            this.ATStopButton.Location = new System.Drawing.Point(273, 12);
            this.ATStopButton.Name = "ATStopButton";
            this.ATStopButton.Size = new System.Drawing.Size(110, 23);
            this.ATStopButton.TabIndex = 16;
            this.ATStopButton.Text = "자동 매매 종료";
            this.ATStopButton.UseVisualStyleBackColor = true;
            this.ATStopButton.Visible = false;
            // 
            // holdJongmokGridView
            // 
            this.holdJongmokGridView.Anchor = ((System.Windows.Forms.AnchorStyles)((((System.Windows.Forms.AnchorStyles.Top | System.Windows.Forms.AnchorStyles.Bottom) 
            | System.Windows.Forms.AnchorStyles.Left) 
            | System.Windows.Forms.AnchorStyles.Right)));
            this.holdJongmokGridView.ColumnHeadersHeightSizeMode = System.Windows.Forms.DataGridViewColumnHeadersHeightSizeMode.AutoSize;
            this.holdJongmokGridView.Location = new System.Drawing.Point(3, 3);
            this.holdJongmokGridView.Name = "holdJongmokGridView";
            this.holdJongmokGridView.ReadOnly = true;
            this.holdJongmokGridView.RowTemplate.Height = 23;
            this.holdJongmokGridView.Size = new System.Drawing.Size(1754, 306);
            this.holdJongmokGridView.TabIndex = 14;
            // 
            // tableLayoutPanel3
            // 
            this.tableLayoutPanel3.ColumnCount = 3;
            this.tableLayoutPanel3.ColumnStyles.Add(new System.Windows.Forms.ColumnStyle(System.Windows.Forms.SizeType.Percent, 19.7065F));
            this.tableLayoutPanel3.ColumnStyles.Add(new System.Windows.Forms.ColumnStyle(System.Windows.Forms.SizeType.Percent, 80.2935F));
            this.tableLayoutPanel3.ColumnStyles.Add(new System.Windows.Forms.ColumnStyle(System.Windows.Forms.SizeType.Absolute, 323F));
            this.tableLayoutPanel3.Controls.Add(this.conditionFilteredGridView, 1, 0);
            this.tableLayoutPanel3.Controls.Add(this.tableLayoutPanel2, 2, 0);
            this.tableLayoutPanel3.Controls.Add(this.conditionCheckedListBox, 0, 0);
            this.tableLayoutPanel3.Location = new System.Drawing.Point(12, 41);
            this.tableLayoutPanel3.Name = "tableLayoutPanel3";
            this.tableLayoutPanel3.RowCount = 1;
            this.tableLayoutPanel3.RowStyles.Add(new System.Windows.Forms.RowStyle(System.Windows.Forms.SizeType.Percent, 50F));
            this.tableLayoutPanel3.Size = new System.Drawing.Size(1760, 190);
            this.tableLayoutPanel3.TabIndex = 17;
            // 
            // tableLayoutPanel4
            // 
            this.tableLayoutPanel4.ColumnCount = 2;
            this.tableLayoutPanel4.ColumnStyles.Add(new System.Windows.Forms.ColumnStyle(System.Windows.Forms.SizeType.Percent, 65.85088F));
            this.tableLayoutPanel4.ColumnStyles.Add(new System.Windows.Forms.ColumnStyle(System.Windows.Forms.SizeType.Percent, 34.14912F));
            this.tableLayoutPanel4.Controls.Add(this.panel3, 1, 0);
            this.tableLayoutPanel4.Controls.Add(this.panel1, 0, 0);
            this.tableLayoutPanel4.Location = new System.Drawing.Point(12, 694);
            this.tableLayoutPanel4.Name = "tableLayoutPanel4";
            this.tableLayoutPanel4.RowCount = 1;
            this.tableLayoutPanel4.RowStyles.Add(new System.Windows.Forms.RowStyle(System.Windows.Forms.SizeType.Percent, 50F));
            this.tableLayoutPanel4.Size = new System.Drawing.Size(1760, 256);
            this.tableLayoutPanel4.TabIndex = 18;
            // 
            // tableLayoutPanel5
            // 
            this.tableLayoutPanel5.ColumnCount = 1;
            this.tableLayoutPanel5.ColumnStyles.Add(new System.Windows.Forms.ColumnStyle(System.Windows.Forms.SizeType.Percent, 50F));
            this.tableLayoutPanel5.Controls.Add(this.holdJongmokGridView, 0, 0);
            this.tableLayoutPanel5.Location = new System.Drawing.Point(12, 234);
            this.tableLayoutPanel5.Name = "tableLayoutPanel5";
            this.tableLayoutPanel5.RowCount = 1;
            this.tableLayoutPanel5.RowStyles.Add(new System.Windows.Forms.RowStyle(System.Windows.Forms.SizeType.Percent, 50F));
            this.tableLayoutPanel5.Size = new System.Drawing.Size(1760, 454);
            this.tableLayoutPanel5.TabIndex = 19;
            // 
            // BuyTestButton
            // 
            this.BuyTestButton.Location = new System.Drawing.Point(771, 12);
            this.BuyTestButton.Name = "BuyTestButton";
            this.BuyTestButton.Size = new System.Drawing.Size(75, 23);
            this.BuyTestButton.TabIndex = 20;
            this.BuyTestButton.Text = "매수";
            this.BuyTestButton.UseVisualStyleBackColor = true;
            // 
            // SellTestButton
            // 
            this.SellTestButton.Location = new System.Drawing.Point(852, 12);
            this.SellTestButton.Name = "SellTestButton";
            this.SellTestButton.Size = new System.Drawing.Size(75, 23);
            this.SellTestButton.TabIndex = 21;
            this.SellTestButton.Text = "매도";
            this.SellTestButton.UseVisualStyleBackColor = true;
            // 
            // testCode
            // 
            this.testCode.Location = new System.Drawing.Point(432, 13);
            this.testCode.Name = "testCode";
            this.testCode.Size = new System.Drawing.Size(100, 21);
            this.testCode.TabIndex = 22;
            // 
            // testPrice
            // 
            this.testPrice.Location = new System.Drawing.Point(538, 13);
            this.testPrice.Name = "testPrice";
            this.testPrice.Size = new System.Drawing.Size(100, 21);
            this.testPrice.TabIndex = 23;
            // 
            // testAmount
            // 
            this.testAmount.Location = new System.Drawing.Point(644, 13);
            this.testAmount.Name = "testAmount";
            this.testAmount.Size = new System.Drawing.Size(100, 21);
            this.testAmount.TabIndex = 24;
            // 
            // Form1
            // 
            this.AutoScaleDimensions = new System.Drawing.SizeF(7F, 12F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.ClientSize = new System.Drawing.Size(1784, 965);
            this.Controls.Add(this.testAmount);
            this.Controls.Add(this.testPrice);
            this.Controls.Add(this.testCode);
            this.Controls.Add(this.SellTestButton);
            this.Controls.Add(this.BuyTestButton);
            this.Controls.Add(this.tableLayoutPanel5);
            this.Controls.Add(this.tableLayoutPanel4);
            this.Controls.Add(this.tableLayoutPanel3);
            this.Controls.Add(this.ATStopButton);
            this.Controls.Add(this.ATStartButton);
            this.Controls.Add(this.GetConditionButton);
            this.Controls.Add(this.tableLayoutPanel1);
            this.Controls.Add(this.LoginButton);
            this.Controls.Add(this.axKHOpenAPI1);
            this.Name = "Form1";
            this.MinimumSize = new System.Drawing.Size(1200, 700);
            this.StartPosition = System.Windows.Forms.FormStartPosition.CenterScreen;
            this.Text = "AutoTrading";
            ((System.ComponentModel.ISupportInitialize)(this.axKHOpenAPI1)).EndInit();
            this.tableLayoutPanel1.ResumeLayout(false);
            this.tableLayoutPanel1.PerformLayout();
            this.tableLayoutPanel2.ResumeLayout(false);
            this.tableLayoutPanel2.PerformLayout();
            ((System.ComponentModel.ISupportInitialize)(this.conditionFilteredGridView)).EndInit();
            ((System.ComponentModel.ISupportInitialize)(this.chart1)).EndInit();
            this.panel1.ResumeLayout(false);
            this.panel3.ResumeLayout(false);
            this.panel3.PerformLayout();
            ((System.ComponentModel.ISupportInitialize)(this.holdJongmokGridView)).EndInit();
            this.tableLayoutPanel3.ResumeLayout(false);
            this.tableLayoutPanel4.ResumeLayout(false);
            this.tableLayoutPanel5.ResumeLayout(false);
            this.ResumeLayout(false);
            this.PerformLayout();

        }

        #endregion

        private AxKHOpenAPILib.AxKHOpenAPI axKHOpenAPI1;
        private System.Windows.Forms.Button LoginButton;
        private System.Windows.Forms.TableLayoutPanel tableLayoutPanel1;
        private System.Windows.Forms.Label ServerGubun;
        private System.Windows.Forms.Label label1;
        private System.Windows.Forms.Label UserID;
        private System.Windows.Forms.ComboBox AccountList;
        private System.Windows.Forms.TableLayoutPanel tableLayoutPanel2;
        private System.Windows.Forms.Label 수익률label;
        private System.Windows.Forms.Label 평가금label;
        private System.Windows.Forms.Label 매수금label;
        private System.Windows.Forms.Label 예수금label;
        private System.Windows.Forms.Label label2;
        private System.Windows.Forms.Label label3;
        private System.Windows.Forms.Label label4;
        private System.Windows.Forms.Label label5;
        private System.Windows.Forms.Label label6;
        private System.Windows.Forms.Label 평가수익label;
        private System.Windows.Forms.CheckedListBox conditionCheckedListBox;
        private System.Windows.Forms.Button GetConditionButton;
        private System.Windows.Forms.DataGridView conditionFilteredGridView;
        private System.Windows.Forms.TextBox logTextBox;
        private System.Windows.Forms.Button ATStartButton;
        private System.Windows.Forms.DataVisualization.Charting.Chart chart1;
        private System.Windows.Forms.Label chartYLabel;
        private System.Windows.Forms.Panel panel1;
        private System.Windows.Forms.Panel panel3;
        private System.Windows.Forms.Button ATStopButton;
        private System.Windows.Forms.DataGridViewTextBoxColumn 조건명;
        private System.Windows.Forms.DataGridViewTextBoxColumn 종목명;
        private System.Windows.Forms.DataGridViewTextBoxColumn 종목코드;
        private System.Windows.Forms.DataGridViewTextBoxColumn 현재가;
        private System.Windows.Forms.DataGridViewTextBoxColumn 전일대비;
        private System.Windows.Forms.DataGridViewTextBoxColumn 등락률;
        private System.Windows.Forms.DataGridViewTextBoxColumn 거래량;
        private System.Windows.Forms.DataGridViewTextBoxColumn 시가;
        private System.Windows.Forms.DataGridViewTextBoxColumn 고가;
        private System.Windows.Forms.DataGridViewTextBoxColumn 저가;
        private System.Windows.Forms.DataGridView holdJongmokGridView;
        private System.Windows.Forms.TableLayoutPanel tableLayoutPanel3;
        private System.Windows.Forms.TableLayoutPanel tableLayoutPanel4;
        private System.Windows.Forms.TableLayoutPanel tableLayoutPanel5;
        private System.Windows.Forms.Button BuyTestButton;
        private System.Windows.Forms.Button SellTestButton;
        private System.Windows.Forms.TextBox testCode;
        private System.Windows.Forms.TextBox testPrice;
        private System.Windows.Forms.TextBox testAmount;
    }
}
