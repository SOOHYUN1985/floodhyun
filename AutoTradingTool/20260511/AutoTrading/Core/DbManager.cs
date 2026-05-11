using System;
using System.Collections.Generic;
using System.Data.SQLite;

namespace AutoTradingTest.Core
{
    public class DbManager
    {
        private readonly string _dbPath;
        private readonly string _holdingTable = "HoldingTable";
        private readonly string _historyTable = "HistoryTable";

        public DbManager(string dbPath)
        {
            _dbPath = dbPath;
        }

        public SQLiteConnection GetConnection()
        {
            return new SQLiteConnection(_dbPath);
        }

        /// <summary>
        /// DB 테이블 생성 (없으면 생성)
        /// </summary>
        public void EnsureTables()
        {
            using (var conn = new SQLiteConnection(_dbPath))
            {
                conn.Open();
                string createQuery = "CREATE TABLE IF NOT EXISTS {0} (" +
                    "종목명 TEXT, 종목코드 TEXT, 매수일 TEXT, 매수전략 TEXT, " +
                    "전량매도일 TEXT, 전량매도이유 TEXT, 매도가격 INTEGER, 최종수익률 REAL, 최종수익금 INTEGER, " +
                    "매수수량 INTEGER, 보유수량 INTEGER, 매수가격 INTEGER, 로스컷단계 INTEGER, 로스컷가격 INTEGER, 보유일 INTEGER, " +
                    "돌파매수 INTEGER, nR절반매도일자 TEXT, nR절반매도 INTEGER, nR절반매도가격 INTEGER, nR절반매도수량 INTEGER, " +
                    "이평매도일자 TEXT, 이평매도가격 INTEGER, 이평매도수량 INTEGER)";

                using (var cmd = new SQLiteCommand(string.Format(createQuery, _holdingTable), conn))
                    cmd.ExecuteNonQuery();
                using (var cmd = new SQLiteCommand(string.Format(createQuery, _historyTable), conn))
                    cmd.ExecuteNonQuery();
            }
        }

        /// <summary>
        /// 테이블에서 전체 DBInfo 목록 읽기
        /// </summary>
        public List<DBInfo> LoadAll(string tableName)
        {
            var list = new List<DBInfo>();
            using (var conn = new SQLiteConnection(_dbPath))
            {
                conn.Open();
                using (var cmd = new SQLiteCommand($"SELECT * FROM {tableName}", conn))
                using (var reader = cmd.ExecuteReader())
                {
                    while (reader.Read())
                    {
                        list.Add(ReadDbInfo(reader));
                    }
                }
            }
            return list;
        }

        /// <summary>
        /// DBInfo INSERT
        /// </summary>
        public void Insert(string tableName, DBInfo info)
        {
            using (var conn = new SQLiteConnection(_dbPath))
            {
                conn.Open();
                string sql = $"INSERT INTO {tableName} (" +
                    "종목명, 종목코드, 매수일, 매수전략, 전량매도일, 전량매도이유, 매도가격, 최종수익률, 최종수익금, " +
                    "매수수량, 보유수량, 매수가격, 로스컷단계, 로스컷가격, 보유일, " +
                    "돌파매수, nR절반매도일자, nR절반매도, nR절반매도가격, nR절반매도수량, " +
                    "이평매도일자, 이평매도가격, 이평매도수량) VALUES (" +
                    "@종목명, @종목코드, @매수일, @매수전략, @전량매도일, @전량매도이유, @매도가격, @최종수익률, @최종수익금, " +
                    "@매수수량, @보유수량, @매수가격, @로스컷단계, @로스컷가격, @보유일, " +
                    "@돌파매수, @nR절반매도일자, @nR절반매도, @nR절반매도가격, @nR절반매도수량, " +
                    "@이평매도일자, @이평매도가격, @이평매도수량)";

                using (var cmd = new SQLiteCommand(sql, conn))
                {
                    BindAllParameters(cmd, info);
                    cmd.ExecuteNonQuery();
                }
            }
        }

        /// <summary>
        /// DBInfo UPDATE (종목명+매수일+매수전략으로 식별)
        /// </summary>
        public void Update(string tableName, DBInfo info)
        {
            using (var conn = new SQLiteConnection(_dbPath))
            {
                conn.Open();
                string sql = $"UPDATE {tableName} SET 종목코드=@종목코드, " +
                    "전량매도일=@전량매도일, 전량매도이유=@전량매도이유, 매도가격=@매도가격, 최종수익률=@최종수익률, 최종수익금=@최종수익금, " +
                    "매수수량=@매수수량, 보유수량=@보유수량, 매수가격=@매수가격, 로스컷단계=@로스컷단계, 로스컷가격=@로스컷가격, 보유일=@보유일, " +
                    "돌파매수=@돌파매수, nR절반매도일자=@nR절반매도일자, nR절반매도=@nR절반매도, nR절반매도가격=@nR절반매도가격, nR절반매도수량=@nR절반매도수량, " +
                    "이평매도일자=@이평매도일자, 이평매도가격=@이평매도가격, 이평매도수량=@이평매도수량 " +
                    "WHERE 종목명=@종목명 AND 매수일=@매수일 AND 매수전략=@매수전략";

                using (var cmd = new SQLiteCommand(sql, conn))
                {
                    BindAllParameters(cmd, info);
                    cmd.ExecuteNonQuery();
                }
            }
        }

        /// <summary>
        /// 보유종목 삭제 후 히스토리에 이동 (트랜잭션)
        /// </summary>
        public void MoveToHistory(DBInfo info)
        {
            using (var conn = new SQLiteConnection(_dbPath))
            {
                conn.Open();
                using (var tx = conn.BeginTransaction())
                {
                    string deleteSql = $"DELETE FROM {_holdingTable} WHERE 종목명=@종목명 AND 매수일=@매수일 AND 매수전략=@매수전략";
                    using (var cmd = new SQLiteCommand(deleteSql, conn, tx))
                    {
                        cmd.Parameters.AddWithValue("@종목명", info.종목명);
                        cmd.Parameters.AddWithValue("@매수일", info.매수일);
                        cmd.Parameters.AddWithValue("@매수전략", info.매수전략);
                        cmd.ExecuteNonQuery();
                    }

                    string insertSql = $"INSERT INTO {_historyTable} (" +
                        "종목명, 종목코드, 매수일, 매수전략, 전량매도일, 전량매도이유, 매도가격, 최종수익률, 최종수익금, " +
                        "매수수량, 보유수량, 매수가격, 로스컷단계, 로스컷가격, 보유일, " +
                        "돌파매수, nR절반매도일자, nR절반매도, nR절반매도가격, nR절반매도수량, " +
                        "이평매도일자, 이평매도가격, 이평매도수량) VALUES (" +
                        "@종목명, @종목코드, @매수일, @매수전략, @전량매도일, @전량매도이유, @매도가격, @최종수익률, @최종수익금, " +
                        "@매수수량, @보유수량, @매수가격, @로스컷단계, @로스컷가격, @보유일, " +
                        "@돌파매수, @nR절반매도일자, @nR절반매도, @nR절반매도가격, @nR절반매도수량, " +
                        "@이평매도일자, @이평매도가격, @이평매도수량)";
                    using (var cmd = new SQLiteCommand(insertSql, conn, tx))
                    {
                        BindAllParameters(cmd, info);
                        cmd.ExecuteNonQuery();
                    }

                    tx.Commit();
                }
            }
        }

        /// <summary>
        /// 전체 보유종목 일괄 UPDATE (트랜잭션)
        /// </summary>
        public void UpdateAll(List<DBInfo> holdings)
        {
            using (var conn = new SQLiteConnection(_dbPath))
            {
                conn.Open();
                using (var tx = conn.BeginTransaction())
                {
                    foreach (var info in holdings)
                    {
                        string sql = $"UPDATE {_holdingTable} SET 종목코드=@종목코드, " +
                            "전량매도일=@전량매도일, 전량매도이유=@전량매도이유, 매도가격=@매도가격, 최종수익률=@최종수익률, 최종수익금=@최종수익금, " +
                            "매수수량=@매수수량, 보유수량=@보유수량, 매수가격=@매수가격, 로스컷단계=@로스컷단계, 로스컷가격=@로스컷가격, 보유일=@보유일, " +
                            "돌파매수=@돌파매수, nR절반매도일자=@nR절반매도일자, nR절반매도=@nR절반매도, nR절반매도가격=@nR절반매도가격, nR절반매도수량=@nR절반매도수량, " +
                            "이평매도일자=@이평매도일자, 이평매도가격=@이평매도가격, 이평매도수량=@이평매도수량 " +
                            "WHERE 종목명=@종목명 AND 매수일=@매수일 AND 매수전략=@매수전략";

                        using (var cmd = new SQLiteCommand(sql, conn, tx))
                        {
                            BindAllParameters(cmd, info);
                            cmd.ExecuteNonQuery();
                        }
                    }
                    tx.Commit();
                }
            }
        }

        private void BindAllParameters(SQLiteCommand cmd, DBInfo info)
        {
            cmd.Parameters.AddWithValue("@종목명", info.종목명);
            cmd.Parameters.AddWithValue("@종목코드", info.종목코드);
            cmd.Parameters.AddWithValue("@매수일", info.매수일);
            cmd.Parameters.AddWithValue("@매수전략", info.매수전략);
            cmd.Parameters.AddWithValue("@전량매도일", info.전량매도일);
            cmd.Parameters.AddWithValue("@전량매도이유", info.전량매도이유);
            cmd.Parameters.AddWithValue("@매도가격", info.매도가격);
            cmd.Parameters.AddWithValue("@최종수익률", info.최종수익률);
            cmd.Parameters.AddWithValue("@최종수익금", info.최종수익금);
            cmd.Parameters.AddWithValue("@매수수량", info.매수수량);
            cmd.Parameters.AddWithValue("@보유수량", info.보유수량);
            cmd.Parameters.AddWithValue("@매수가격", info.매수가격);
            cmd.Parameters.AddWithValue("@로스컷단계", info.로스컷단계);
            cmd.Parameters.AddWithValue("@로스컷가격", info.로스컷가격);
            cmd.Parameters.AddWithValue("@보유일", info.보유일);
            cmd.Parameters.AddWithValue("@돌파매수", info.돌파매수 ? 1 : 0);
            cmd.Parameters.AddWithValue("@nR절반매도일자", info.nR절반매도일자);
            cmd.Parameters.AddWithValue("@nR절반매도", info.nR절반매도 ? 1 : 0);
            cmd.Parameters.AddWithValue("@nR절반매도가격", info.nR절반매도가격);
            cmd.Parameters.AddWithValue("@nR절반매도수량", info.nR절반매도수량);
            cmd.Parameters.AddWithValue("@이평매도일자", info.이평매도일자);
            cmd.Parameters.AddWithValue("@이평매도가격", info.이평매도가격);
            cmd.Parameters.AddWithValue("@이평매도수량", info.이평매도수량);
        }

        private DBInfo ReadDbInfo(SQLiteDataReader reader)
        {
            return new DBInfo()
            {
                종목명 = reader["종목명"]?.ToString() ?? "",
                종목코드 = reader["종목코드"]?.ToString() ?? "",
                매수일 = reader["매수일"]?.ToString() ?? "",
                매수전략 = reader["매수전략"]?.ToString() ?? "",
                전량매도일 = reader["전량매도일"]?.ToString() ?? "",
                전량매도이유 = reader["전량매도이유"]?.ToString() ?? "",
                매도가격 = int.TryParse(reader["매도가격"]?.ToString(), out int v1) ? v1 : 0,
                최종수익률 = float.TryParse(reader["최종수익률"]?.ToString(), out float v2) ? v2 : 0f,
                최종수익금 = int.TryParse(reader["최종수익금"]?.ToString(), out int v3) ? v3 : 0,
                매수수량 = int.TryParse(reader["매수수량"]?.ToString(), out int v4) ? v4 : 0,
                보유수량 = int.TryParse(reader["보유수량"]?.ToString(), out int v5) ? v5 : 0,
                매수가격 = int.TryParse(reader["매수가격"]?.ToString(), out int v6) ? v6 : 0,
                로스컷단계 = int.TryParse(reader["로스컷단계"]?.ToString(), out int v7) ? v7 : 0,
                로스컷가격 = int.TryParse(reader["로스컷가격"]?.ToString(), out int v8) ? v8 : 0,
                보유일 = int.TryParse(reader["보유일"]?.ToString(), out int v9) ? v9 : 0,
                돌파매수 = int.TryParse(reader["돌파매수"]?.ToString(), out int v10) && v10 != 0,
                nR절반매도일자 = reader["nR절반매도일자"]?.ToString() ?? "",
                nR절반매도 = int.TryParse(reader["nR절반매도"]?.ToString(), out int v11) && v11 != 0,
                nR절반매도가격 = int.TryParse(reader["nR절반매도가격"]?.ToString(), out int v12) ? v12 : 0,
                nR절반매도수량 = int.TryParse(reader["nR절반매도수량"]?.ToString(), out int v13) ? v13 : 0,
                이평매도일자 = reader["이평매도일자"]?.ToString() ?? "",
                이평매도가격 = int.TryParse(reader["이평매도가격"]?.ToString(), out int v14) ? v14 : 0,
                이평매도수량 = int.TryParse(reader["이평매도수량"]?.ToString(), out int v15) ? v15 : 0,
            };
        }

        /// <summary>
        /// 히스토리에서 해당 종목의 가장 최근 매수전략을 조회
        /// </summary>
        public string FindLastStrategy(string 종목코드)
        {
            using (var conn = new SQLiteConnection(_dbPath))
            {
                conn.Open();
                string sql = $"SELECT 매수전략 FROM {_historyTable} WHERE 종목코드=@종목코드 AND 매수전략 != '계좌복원' ORDER BY 매수일 DESC LIMIT 1";
                using (var cmd = new SQLiteCommand(sql, conn))
                {
                    cmd.Parameters.AddWithValue("@종목코드", 종목코드);
                    var result = cmd.ExecuteScalar();
                    return result?.ToString();
                }
            }
        }

        /// <summary>
        /// 히스토리에서 해당 종목의 가장 최근 매수일을 조회 (계좌복원 시 실제 매수일 복원용)
        /// </summary>
        public string FindLastBuyDate(string 종목코드)
        {
            using (var conn = new SQLiteConnection(_dbPath))
            {
                conn.Open();
                string sql = $"SELECT 매수일 FROM {_historyTable} WHERE 종목코드=@종목코드 AND 매수전략 != '계좌복원' ORDER BY 매수일 DESC LIMIT 1";
                using (var cmd = new SQLiteCommand(sql, conn))
                {
                    cmd.Parameters.AddWithValue("@종목코드", 종목코드);
                    var result = cmd.ExecuteScalar();
                    return result?.ToString();
                }
            }
        }
    }
}
