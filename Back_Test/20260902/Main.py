import os
import sys
import json
import pandas as pd
import sqlite3
import logging
import concurrent.futures
import matplotlib.pyplot as plt
import glob
import re
import itertools
from tqdm import tqdm
from threading import Thread, Lock
from datetime import datetime
import shutil
import random
# Ours
import util
from strategy.One_Day_Minervini_Mark_V1 import One_Day_Minervini_Mark_V1

os.chdir(os.path.dirname(os.path.realpath(__file__)))

plt.rcParams['font.family']='Malgun Gothic'
plt.rcParams['axes.unicode_minus']=False

lock = Lock()
BACKTEST_WORKERS = 18


def normalize_backtest_parameters(strategies, profit_loss_ratios):
    normalized_strategies = []
    seen_strategies = set()
    for strategy in strategies:
        if not isinstance(strategy, list) or len(strategy) != 2:
            raise ValueError(f"잘못된 전략 형식: {strategy}")

        breakout_window, sell_windows = strategy
        if not isinstance(breakout_window, int) or breakout_window < 60:
            raise ValueError(f"신고가 기간은 60일 이상의 정수여야 합니다: {strategy}")
        if not isinstance(sell_windows, list) or not sell_windows:
            raise ValueError(f"매도 이평선은 하나 이상이어야 합니다: {strategy}")

        normalized_sell_windows = tuple(sorted(set(sell_windows)))
        if any(not isinstance(window, int) or window < 2 for window in normalized_sell_windows):
            raise ValueError(f"매도 이평선은 2일 이상의 정수여야 합니다: {strategy}")

        key = (breakout_window, normalized_sell_windows)
        if key not in seen_strategies:
            seen_strategies.add(key)
            normalized_strategies.append([breakout_window, list(normalized_sell_windows)])

    normalized_ratios = []
    seen_ratios = set()
    for ratio in profit_loss_ratios:
        if not isinstance(ratio, list) or len(ratio) != 2:
            raise ValueError(f"잘못된 손익비 형식: {ratio}")

        stop_percent, max_r_step = ratio
        if not isinstance(stop_percent, int) or stop_percent <= 0:
            raise ValueError(f"손절 폭은 양의 정수여야 합니다: {ratio}")
        if not isinstance(max_r_step, int) or max_r_step < 1:
            raise ValueError(f"최대 R 단계는 양의 정수여야 합니다: {ratio}")

        key = (stop_percent, max_r_step)
        if key not in seen_ratios:
            seen_ratios.add(key)
            normalized_ratios.append([stop_percent, max_r_step])

    if not normalized_strategies or not normalized_ratios:
        raise ValueError("백테스트 전략과 손익비는 각각 하나 이상이어야 합니다.")

    return normalized_strategies, normalized_ratios


def run_backtests(globalConstVariable, tables, strategies, profit_loss_ratios):
    # 종목 단위로 작업을 분배한다. 종목 하나당 지표를 1회만 계산하고
    # 모든 전략/손익비 조합을 한 워커에서 처리하므로 DB 재읽기와 지표 재계산을 없앤다.
    combos_per_table = len(strategies) * len(profit_loss_ratios)
    total_tasks = len(tables) * combos_per_table
    task_iterator = iter(
        (globalConstVariable, table, strategies, profit_loss_ratios)
        for table in tables
    )
    results = []

    with concurrent.futures.ProcessPoolExecutor(max_workers=BACKTEST_WORKERS) as executor:
        pending = {
            executor.submit(process_table, task): task
            for task in itertools.islice(task_iterator, BACKTEST_WORKERS)
        }
        with tqdm(total=total_tasks, desc='백테스트', unit='건') as progress:
            while pending:
                completed, _ = concurrent.futures.wait(
                    pending,
                    return_when=concurrent.futures.FIRST_COMPLETED,
                )
                for future in completed:
                    del pending[future]
                    results.extend(future.result())
                    progress.update(combos_per_table)

                    try:
                        next_task = next(task_iterator)
                    except StopIteration:
                        continue
                    pending[executor.submit(process_table, next_task)] = next_task

    return results

def get_table_names(globalConstVariable):
    conn = sqlite3.connect(globalConstVariable['db_fileName'])
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cur.fetchall()
    conn.close()
    return tables

def setup_logger(globalConstVariable, table_name, strategy_name, profit_loss_ratio):
    logger = logging.getLogger(f"{table_name}_{strategy_name}_{profit_loss_ratio}")
    logger.setLevel(logging.INFO)

    if globalConstVariable['logLevel'] == util.LOG_LEVEL_DEBUG_FILE:
        # 첫 번째 핸들러: 테이블 이름별 로그 파일
        handler1 = logging.FileHandler(f"{globalConstVariable['folder_name']}/{strategy_name}_{profit_loss_ratio}/{table_name}.txt", encoding='utf-8')
        handler1.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(handler1)

    return logger

def plot_graph(globalConstVariable, df, buy_signals, sell_signals, total_return, table_name, strategy_name):
    plt.figure(figsize=(10, 6))
    plt.plot(df['date'], df['open'], label='가격')
    plt.plot(df['date'], df['MA_33'], label='33일 이평선')
    plt.scatter(buy_signals, df.loc[df['date'].isin(buy_signals), 'close'], marker='^', color='g', label='매수 신호')
    plt.scatter(sell_signals, df.loc[df['date'].isin(sell_signals), 'close'], marker='v', color='r', label='매도 신호')
    plt.legend()
    plt.savefig(f"{globalConstVariable['folder_name']}/{strategy_name}/{round(total_return, 0)}_{table_name}.png")
    plt.close()

def extract_data(line):
    match_table_name = re.search(r'종목코드: (\w+),', line)
    match_buy_date = re.search(r'매수일: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
    match_sell_date = re.search(r'매도일: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
    match_final_return = re.search(r'최종수익률: ([-\d.]+)%', line)

    table_name = match_table_name.group(1) if match_table_name else None
    buy_date = match_buy_date.group(1) if match_buy_date else None
    sell_date = match_sell_date.group(1) if match_sell_date else None
    final_return = match_final_return.group(1) if match_final_return else None

    return table_name, buy_date, sell_date, final_return

def process_file(txt_file):
    all_traing_df = pd.DataFrame(columns=['종목코드','매수일', '전량 매도일', '최종수익률'])

    with open(txt_file, 'rb') as f:
        content = f.read().decode('utf-8', 'ignore')
        lines = content.split('\n')

    for line in lines:
        if '최종수익률' in line:
            table_name, buy_date, sell_date, final_return = extract_data(line)
            if table_name and buy_date and sell_date and final_return:
                new_data = pd.DataFrame({'종목코드': [table_name], '매수일': [buy_date], '전량 매도일': [sell_date], '최종수익률': [final_return]})
                all_traing_df = pd.concat([all_traing_df, new_data], ignore_index=True)

    return all_traing_df

def process_text_file(txt_file):
    all_traing_df = process_file(txt_file)
    excel_file = os.path.splitext(txt_file)[0]+ '.xlsx'
    all_traing_df.to_excel(excel_file, index=False)

    df = pd.read_excel(excel_file)
    df['매수일']= pd.to_datetime(df['매수일'])
    df['전량 매도일']= pd.to_datetime(df['전량 매도일'])
    df['연도']= df['매수일'].dt.year
    df['월']= df['매수일'].dt.month
    df['매매구분']= df['최종수익률'].apply(lambda x: '수익' if x > 0 else '손실')

    summary = df.groupby(['연도', '월']).agg({
        '매매구분': [('매매횟수', 'count'), 
                    ('수익횟수', lambda x: (x == '수익').sum()), 
                    ('손실횟수', lambda x: (x == '손실').sum())],
        '최종수익률': [('수익합계', 'sum')]
    })
    summary.columns = ['매매횟수', '수익횟수', '손실횟수', '수익합계']
    summary['승률']= (summary['수익횟수']/ summary['매매횟수']) * 100

    yearly_summary = df.groupby('연도').agg({
        '매매구분': [('매매횟수', 'count'), 
                    ('수익횟수', lambda x: (x == '수익').sum()), 
                    ('손실횟수', lambda x: (x == '손실').sum())],
        '최종수익률': [('수익합계', 'sum')]
    })
    yearly_summary.columns = ['매매횟수', '수익횟수', '손실횟수', '수익합계']
    yearly_summary['승률']= (yearly_summary['수익횟수']/ yearly_summary['매매횟수']) * 100

    total_summary = pd.DataFrame({
        '매매횟수': [df['매매구분'].count()],
        '수익횟수': [(df['매매구분']== '수익').sum()],
        '손실횟수': [(df['매매구분']== '손실').sum()],
        '수익합계': [df['최종수익률'].sum()]
    })
    total_summary['승률'] = round((total_summary['수익횟수']/ total_summary['매매횟수']) * 100, 2)
    total_summary['기대값']= round((total_summary['수익합계']/ total_summary['매매횟수']), 2)
    total_summary['켈리값']= round(((total_summary['수익횟수']/ total_summary['매매횟수']) * 100- ((100 - (total_summary['수익횟수']/ total_summary['매매횟수']) * 100) / ((total_summary['수익합계']/ total_summary['매매횟수'])))), 2)
    strategy_name = excel_file.split("\\")[-1].split(".")[0]
    
    with pd.ExcelWriter(excel_file, mode='a', engine='openpyxl') as writer:
        summary.to_excel(writer, sheet_name='Summary', startrow=0, startcol=0)
        yearly_summary.to_excel(writer, sheet_name='Yearly Summary', startrow=0, startcol=0)
        total_summary.to_excel(writer, sheet_name='Total Summary', startrow=0, startcol=0)
    
    return (strategy_name, total_summary) 

def get_excel_file(folder_name, file_pattern='singo*.xlsx'):
    file_path = glob.glob(os.path.join(folder_name, file_pattern))
    if file_path:
        return file_path[0]
    else:
        print(f"No file matches the pattern {file_pattern} in {folder_name}.")
        return None

def calculate_metrics(total_summary):
    TPI = ((total_summary['승률'].values[0]) / 100) * (1+(total_summary['수익합계'].values[0]) / (total_summary['매매횟수'].values[0]))
    Expected = ((total_summary['수익합계'].values[0]) / (total_summary['매매횟수'].values[0]))
    Kelly = (total_summary['승률'].values[0]- ((100 - total_summary['승률'].values[0]) / Expected))
    return TPI, Expected, Kelly

def process_text_files(folder_name):
    txt_files = glob.glob(os.path.join(folder_name, '*.txt'))

    with concurrent.futures.ProcessPoolExecutor(max_workers=BACKTEST_WORKERS) as executor:
        results = list(executor.map(process_text_file, txt_files))

    excel_file = get_excel_file(folder_name)

    results.sort(key=lambda x: x[1]['수익합계'].values[0], reverse=True)
    with open('result_list.txt', 'a', encoding='utf-8') as f:
        print(f"===============================================================================Total Reults===============================================================================")
        f.write(f"======================================================================Total Reults===============================================================================\n")
        for i, (strategy_name, total_summary) in enumerate(results, start=1):
            TPI, Expected, Kelly = calculate_metrics(total_summary)
            result_str = f"{i}. Strategy Name : {strategy_name}, 매매횟수: {total_summary['매매횟수'].values[0]}, 수익횟수: {total_summary['수익횟수'].values[0]}, 손실횟수: {total_summary['손실횟수'].values[0]}, 수익합계: {total_summary['수익합계'].values[0]:.2f}, 승률: {total_summary['승률'].values[0]:.2f}, TPI: {TPI:.2f}, 기대값: {Expected:.2f}, 켈리값: {Kelly:.2f}"
            print(result_str)
            f.write(result_str + "\n")

    if globalConstVariable['logLevel'] == util.LOG_LEVEL_DEBUG_FILE :
        df_duplicated = pd.read_excel(excel_file, sheet_name='Sheet1')
        df_duplicated['DateRange']= df_duplicated.apply(lambda row: pd.date_range(start=row['매수일'], end=row['전량 매도일']), axis=1)
        df_duplicated['보유일']= df_duplicated['DateRange'].apply(len)

        def count_overlaps(row): 
            overlaps = df_duplicated[df_duplicated['종목코드']!= row['종목코드']]['DateRange'].apply(lambda x: x.isin(row['DateRange']).any())
            return overlaps.sum()

        df_duplicated['Overlaps']= df_duplicated.apply(count_overlaps, axis=1)

        # 날짜별로 보유중인 종목 수 계산
        df_exploded = df_duplicated.explode('DateRange')
        df_grouped = df_exploded.groupby('DateRange')['종목코드'].count()

        # 결과를 새로운 DataFrame으로 만들기
        df_result = pd.DataFrame(df_grouped)
        df_result.columns = ['보유중인 종목 수']

        # 날짜별로 보유중인 종목 리스트 계산
        df_grouped_list = df_exploded.groupby('DateRange')['종목코드'].apply(list)

        # 결과를 새로운 DataFrame으로 만들기
        df_result_list = pd.DataFrame(df_grouped_list)
        df_result_list.columns = ['보유중인 종목 리스트']

        # 결과를 df_result에 병합
        df_result = pd.merge(df_result, df_result_list, left_index=True, right_index=True)

        # 월별로 보유중인 종목 수 계산
        df_exploded['Year']= df_exploded['DateRange'].dt.year  # 날짜를 연도로 변환
        df_exploded['Month']= df_exploded['DateRange'].dt.month  # 날짜를 월로 변환

        # 연도와 월별로 보유중인 종목 수 계산 (중복 제거)
        df_grouped_month = df_exploded.groupby(['Year', 'Month'])['종목코드'].nunique()

        # 결과를 새로운 DataFrame으로 만들기
        df_result_month = pd.DataFrame(df_grouped_month)
        df_result_month.columns = ['월별 보유중인 종목 수']

        # 결과를 excel_file의 Sheet3에 저장
        with pd.ExcelWriter(excel_file, engine='openpyxl', mode='a') as writer: 
            if 'Sheet3' in writer.book.sheetnames:
                idx = writer.book.sheetnames.index('Sheet3')  # find the index of 'Sheet3'
                writer.book.remove(writer.book.worksheets[idx])  # remove 'Sheet3'
                writer.sheets = {ws.title:ws for ws in writer.book.worksheets}
            df_result_month.to_excel(writer, sheet_name='Monthly_Unique_Stocks')

        # 결과를 excel_file의 Sheet2에 저장
        with pd.ExcelWriter(excel_file, engine='openpyxl', mode='a') as writer:
            df_result.to_excel(writer, sheet_name='Duplicated_Date')
        
        with pd.ExcelWriter(excel_file, engine='openpyxl', mode='a') as writer: 
            for sheet in writer.book.sheetnames:
                if sheet == 'Sheet1':
                    writer.book.remove(writer.book[sheet])
            df_duplicated.to_excel(writer, sheet_name='Stocks_Trading_History', index=False)

def keep_last_n_elements(df, n):
# 데이터프레임의 모든 컬럼에 대해 적용
    df = df.apply(lambda series: series[-n:] if len(series) >= n else series)
    return df

# 지수(A069500) 데이터는 모든 종목/전략에서 동일하다. 워커 프로세스별로 1회만 계산해 캐싱한다.
_JISU_CACHE = {}


def _load_jisu(globalConstVariable, conn):
    key = globalConstVariable['db_fileName']
    cached = _JISU_CACHE.get(key)
    if cached is not None:
        return cached

    jisu_df = pd.read_sql_query("SELECT * FROM A069500", conn)
    jisu_df['date'] = pd.to_datetime(jisu_df['date'], format='%Y%m%d')
    jisu_index_df = jisu_df.reset_index().rename(columns={'index': 'jisu_index'})
    jisu_df = jisu_df.assign(**{f'MA_{window}': jisu_df['close'].rolling(window=window).mean() for window in [5, 10, 15, 20, 33, 45, 50, 60, 120, 200]})

    _JISU_CACHE[key] = (jisu_df, jisu_index_df)
    return jisu_df, jisu_index_df


def _build_base_df(conn, table_name, jisu_df, jisu_index_df):
    # 전략(strategy)과 무관하게 종목별로 1회만 계산하면 되는 지표들.
    df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    df = keep_last_n_elements(df, len(jisu_df['date']))

    df['date'] = pd.to_datetime(df['date'], format='%Y%m%d')
    index_df = df.reset_index().rename(columns={'index': 'df_index'})

    merged_df = pd.merge(jisu_index_df, index_df, on='date', how='inner')
    index_df = merged_df[['jisu_index', 'df_index', 'date']]

    df = df.assign(**{f'VOLUME_{window}': df['volume'].rolling(window=window).mean() for window in [5, 10, 20, 50, 60, 120]})
    df = df.assign(**{f'MA_{window}': df['close'].rolling(window=window).mean() for window in [1, 2, 3, 5, 10, 20, 33, 40, 50]}) # DEFAULT SETTING for 수렴
    df = df.assign(**{f'MA_{window}': df['close'].rolling(window=window).mean() for window in [50, 60, 150, 200, 240, 300]})
    df = df.assign(**{f'EMA_{window}': df['close'].ewm(span=window).mean() for window in [1, 2, 3, 5, 10, 12, 15, 20, 33, 40, 50]})
    df = df.assign(**{f'SINJU_{window}': df['close'].rolling(window=window).min() for window in [240, 300]})

    return df, index_df


def _apply_strategy_columns(base_df, strategy):
    # 전략별로만 달라지는 지표(매도 이평선/신고가)를 추가한 새 DataFrame을 반환한다.
    new_columns = {}
    for window in strategy[1]:
        new_columns[f'MA_{window}'] = base_df['close'].rolling(window=window).mean()
        new_columns[f'EMA_{window}'] = base_df['close'].ewm(span=window).mean()
    new_columns[f'SINGO_{strategy[0]}'] = base_df['close'].rolling(window=strategy[0]).max()
    new_columns[f'SINGOHIGH_{strategy[0]}'] = base_df['high'].rolling(window=strategy[0]).max()
    return base_df.assign(**new_columns)


def process_table(args):
    globalConstVariable, table, strategies, profit_loss_ratios = args
    table_name = table[0]

    conn = sqlite3.connect(globalConstVariable['db_fileName'])
    try:
        jisu_df, jisu_index_df = _load_jisu(globalConstVariable, conn)
        base_df, index_df = _build_base_df(conn, table_name, jisu_df, jisu_index_df)

        results = []
        for strategy in strategies:
            df = _apply_strategy_columns(base_df, strategy)

            strategy_name = f"singo_{strategy[0]}_medo"
            for medo in strategy[1]:
                strategy_name += f"_{medo}"

            for profit_loss_ratio in profit_loss_ratios:
                logger = setup_logger(globalConstVariable, table_name, strategy_name, profit_loss_ratio)

                buy_signals, sell_signals, total_return, total_trades, win_trades, loss_trades = One_Day_Minervini_Mark_V1(
                    profit_loss_ratio, df, logger, globalConstVariable['logLevel'], strategy, jisu_df, index_df)

                if util.SAVE_LOG_FILE_CHART == True:
                    with lock:
                        plot_graph(globalConstVariable, df, buy_signals, sell_signals, total_return, table_name, strategy_name)

                for loggerHandler in list(logger.handlers):
                    logger.removeHandler(loggerHandler)

                new_data = pd.DataFrame({'table_name': [table_name], 'strategy': [strategy_name], 'total_return': [total_return], 'total_trades': [total_trades], 'win_trades': [win_trades], 'loss_trades': [loss_trades], 'profit_loss_ratio': [profit_loss_ratio]})
                if not new_data.empty and not new_data.isna().all().all():
                    results.append(new_data)
    finally:
        conn.close()

    return results

def sum_loger(folderPath):
    parent_folder = os.path.basename(os.path.dirname(folderPath))
    _, deepest_folder = os.path.split(folderPath)
    output_file_path = os.path.join(parent_folder, f"{deepest_folder}.txt")

    # 폴더 내의 모든 txt 파일을 읽어들여 합치기
    with open(output_file_path, "w", encoding="utf-8") as output_file:
        for filename in os.listdir(folderPath):
            if filename.endswith(".txt"):
                file_path = os.path.join(folderPath, filename)
                with open(file_path, "r", encoding="utf-8") as input_file:
                    #output_file.write(f"{filename}, ") #파일이름 추가 (디버깅 편의를 위해서)
                    #output_file.write(input_file.read() + "\n")  # 파일 내용을 읽어와 합칩니다.
                    file_name_without_extension = os.path.splitext(filename)[0]
                    for line in input_file.readlines():
                        if "총 거래 횟수: 0" in line:
                            break
                            
                        output_file.write(f"종목코드: {file_name_without_extension}, {line.strip()}\n")
    shutil.rmtree(folderPath)

def make_forder(globalConstVariable, strategies, profit_loss_ratios):
    for strategy in strategies:
        for profit_loss_ratio in profit_loss_ratios:
            strategy_name = f"singo_{strategy[0]}_medo"
            for medo in strategy[1]:
                strategy_name += f"_{medo}"
                
            if not os.path.exists(f"{globalConstVariable['folder_name']}/{strategy_name}_{profit_loss_ratio}"):
                os.mkdir(f"{globalConstVariable['folder_name']}/{strategy_name}_{profit_loss_ratio}")
    
    
if __name__ == '__main__':
    start_time = datetime.now()

    time_str = start_time.strftime('%Y-%m-%d_%H-%M-%S')
    
    globalConstVariable = {
        'db_fileName' : r'..\Database\stock_price(1day_total).db',
        #'db_fileName' : r'..\Database\240702_stock_price(1day_total).db',
        'logLevel' : util.LOG_LEVEL_DEBUG_FILE,
        #'logLevel' : util.LOG_LEVEL_RELEASE,
        'folder_name' : f'result_{time_str}',
        'file_name' : f'result_{time_str}/result_{time_str}.xlsx' 
    }
    
    if not os.path.exists(globalConstVariable['folder_name']):
        os.mkdir(globalConstVariable['folder_name'])
        
    result_df = pd.DataFrame(columns=['table_name', 'strategy', 'total_return', 'total_trades', 'win_trades', 'loss_trades'])
    
    # 설정 파일 로드 (커맨드라인 인자로 경로 지정 가능: python Main.py config.json)
    config_file = sys.argv[1] if len(sys.argv) > 1 else 'backtest_config.json'
    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        print(f"[Config] 설정 파일 로드: {config_file}")
        use_random_strategy = config.get('use_random_strategy', False)
    else:
        print(f"[Config] 설정 파일 없음, 기본값 사용")
        use_random_strategy = False
        config = None

    if use_random_strategy:
        rc = config['random_strategy_config'] if config else {}
        left_values = rc.get('left_values', [120, 200, 240, 299, 400])
        strategy_count = rc.get('count', 5)
        right_range = rc.get('right_range', [4, 50])
        right_step = rc.get('right_step', 5)
        num_values_range = rc.get('num_values_range', [2, 3])
        plr_count_range = rc.get('profit_loss_ratio_count_range', [2, 3])
        plr_left_range = rc.get('profit_loss_ratio_left_range', [6, 30])
        plr_right_range = rc.get('profit_loss_ratio_right_range', [99, 100])

        strategies = []
        for _ in range(strategy_count):
            valid_values = [i for i in range(right_range[0], right_range[1]) if i % right_step == 0]
            num_values = random.randint(num_values_range[0], num_values_range[1])
            right_values = sorted(random.sample(valid_values, num_values))
            random_strategy = [random.choice(left_values), right_values]
            strategies.append(random_strategy)
        
        profit_loss_ratios = [[random.randint(plr_left_range[0], plr_left_range[1]), random.randint(plr_right_range[0], plr_right_range[1])] for _ in range(random.randint(plr_count_range[0], plr_count_range[1]))]
    else:
        if config:
            strategies = config.get('strategies', [[299, [10]]])
            profit_loss_ratios = config.get('profit_loss_ratios', [[10, 200]])
        else:
            strategies = [[299, [10]]]
            profit_loss_ratios = [[10, 200]]

    original_case_count = len(strategies) * len(profit_loss_ratios)
    strategies, profit_loss_ratios = normalize_backtest_parameters(strategies, profit_loss_ratios)
    normalized_case_count = len(strategies) * len(profit_loss_ratios)
    if normalized_case_count != original_case_count:
        print(f"[Config] 중복 조합 제거: {original_case_count} -> {normalized_case_count}")
    
    print(f"strategies : {strategies}")
    print(f"profit_loss_ratios : {profit_loss_ratios}")

    tables = get_table_names(globalConstVariable)
    
    make_forder(globalConstVariable, strategies, profit_loss_ratios)
    
    use_one_item = False
    if not use_one_item:
        results = run_backtests(globalConstVariable, tables, strategies, profit_loss_ratios)
    else:
        results = []
        for table in tqdm(tables):
            if table[0] == 'A196170':
                results.extend(process_table([globalConstVariable, table, strategies, profit_loss_ratios]))
    
    
    end_time = datetime.now()
    elapsed_time = end_time - start_time
    print(f"[BackTest] 시작시간: {start_time}, 종료시간: {end_time}, 소요시간: {elapsed_time}")
        
    subfolders = [f.path for f in os.scandir(globalConstVariable['folder_name']) if f.is_dir()]    
    partial_start_time = datetime.now()
    #with concurrent.futures.ProcessPoolExecutor(max_workers=8) as executor:
    with concurrent.futures.ProcessPoolExecutor() as executor:
        executor.map(sum_loger, [(subfolder) for subfolder in subfolders])
    
    end_time = datetime.now()
    elapsed_time = end_time - partial_start_time
    print(f"[Sum loger] 시작시간: {partial_start_time}, 종료시간: {end_time}, 소요시간: {elapsed_time}")

    partial_start_time = datetime.now()
    result_df = pd.concat(results, ignore_index=True)

    with pd.ExcelWriter(globalConstVariable['file_name']) as writer:
        for strategy, profit_loss_ratio in itertools.product(strategies, profit_loss_ratios):
            # 전략 이름 설정
            strategy_name = f"singo_{strategy[0]}_medo"
            for medo in strategy[1]:
                strategy_name += f"_{medo}"
            
            # profit_loss_ratio를 문자열로 변환하여 시트 이름에 추가합니다.
            plr_str = '_'.join(map(str, profit_loss_ratio))
            sheet_name = f"{strategy_name}_{plr_str}"

            # 전략에 해당하는 결과 DataFrame 필터링
            strategy_df = result_df[(result_df['strategy'] == strategy_name) & (result_df['profit_loss_ratio'].apply(lambda x: str(x)) == str(profit_loss_ratio))]
            total_return_sum = strategy_df['total_return'].sum()

            strategy_df.to_excel(writer, sheet_name=sheet_name, index=False)

            sum_df = pd.DataFrame({'total_return_sum': [f"{total_return_sum:.2f}"]})
            sum_df.to_excel(writer, sheet_name=sheet_name, startrow=len(strategy_df)+1, index=False)

            if globalConstVariable['logLevel'] != util.LOG_LEVEL_DEBUG_FILE :
                print(f"Sheet Name: {sheet_name}, Total Return Sum: {total_return_sum}")
    
    end_time = datetime.now()
    elapsed_time = end_time - partial_start_time
    if globalConstVariable['logLevel'] != util.LOG_LEVEL_DEBUG_FILE :
        print(f"[Result Excel] 시작시간: {partial_start_time}, 종료시간: {end_time}, 소요시간: {elapsed_time}")

    if globalConstVariable['logLevel'] == util.LOG_LEVEL_DEBUG_FILE :
        partial_start_time = datetime.now()
        process_text_files(globalConstVariable['folder_name'])
        end_time = datetime.now()
        elapsed_time = end_time - partial_start_time
        print(f"[전략 Excel] 시작시간: {partial_start_time}, 종료시간: {end_time}, 소요시간: {elapsed_time}")

    end_time = datetime.now()
    elapsed_time = end_time - start_time
    
    print(f"시작시간: {start_time}, 종료시간: {end_time}, 총 소요시간: {elapsed_time}")