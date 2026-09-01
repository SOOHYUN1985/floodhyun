import util
from util import logging
from datetime import datetime

initBuget = 100000000

# 매매 전략
def One_Day_Minervini_Mark_V1(profit_loss_ratio, data, logger, logLevel, strategy, jisu_data, index_data):
    strategy_name = f"{strategy[0]}_Sell"
    for medo in strategy[1]:
        strategy_name += f"_{medo}"
    
    buy_signals = []
    sell_signals = []
    holding = False
    total_profit = 0
    total_trades = 0
    win_trades = 0
    loss_trades = 0
    buyIndex = 0
    buy_price = 0
    
    loss_cut_price = 0
    loss_cut_n = 1
    loss_cut_n_init = loss_cut_n
    
    initial_qty = 0
    remaining_qty = 0
    nTime = len(strategy[1])
    sell_list = [False] * nTime
    sell_count = 0
    final_profit = 0 #최종 전량 매도시 수익률
    
    Alread_Get_R = False
    #Deviced_Get_R = 0 #R단위 부분익절
    #bubun_iksul_count = 1 #R단위 부분익절
    
    singo = 0
    singo_lower_bound = 0
    singo_upper_bound = 0
    singo_lower_day_bound = 0
    singo_upper_day_bound = 10
    #singo_upper_day_bound = 1
    singo_after_day = 0
    
    sell_lower_day_bound = 10
    sell_after_day = sell_lower_day_bound + 1
    
    buy_after_day = 0
    buy_upper_day_bound = 20

    date_data = data['date'].tolist()
    close_data = data['close'].tolist()
    open_data = data['open'].tolist()
    high_data = data['high'].tolist()
    low_data = data['low'].tolist()
    singo_data = data[f'SINGO_{strategy[0]}'].tolist()
    singo_high_data = data[f'SINGOHIGH_{strategy[0]}'].tolist()
    sinju_data = data[f'SINJU_{300}'].tolist()
    ma1_data = data[f'MA_{1}'].tolist()
    ma2_data = data[f'MA_{2}'].tolist()
    ma3_data = data[f'MA_{3}'].tolist()
    ma5_data = data[f'MA_{5}'].tolist()
    ma10_data = data[f'MA_{10}'].tolist()
    ma20_data = data[f'MA_{20}'].tolist()
    ma33_data = data[f'MA_{33}'].tolist()
    ma40_data = data[f'MA_{40}'].tolist()
    ma50_data = data[f'MA_{50}'].tolist()
    ma60_data = data[f'MA_{60}'].tolist()
    ma150_data = data[f'MA_{150}'].tolist()
    ma200_data = data[f'MA_{200}'].tolist()
    ma240_data = data[f'MA_{240}'].tolist()
    market_cap_data = data['시가총액'].tolist()
    
    ema1_data = data[f'EMA_{1}'].tolist()
    ema2_data = data[f'EMA_{2}'].tolist()
    ema3_data = data[f'EMA_{3}'].tolist()
    ema5_data = data[f'EMA_{5}'].tolist()
    ema10_data = data[f'EMA_{10}'].tolist()
    ema12_data = data[f'EMA_{12}'].tolist()
    ema15_data = data[f'EMA_{15}'].tolist()
    ema20_data = data[f'EMA_{20}'].tolist()
    ema33_data = data[f'EMA_{33}'].tolist()
    ema40_data = data[f'EMA_{40}'].tolist()
    ema50_data = data[f'EMA_{50}'].tolist()

    ma5_jisu_data = jisu_data[f'MA_{5}'].tolist()
    ma10_jisu_data = jisu_data[f'MA_{10}'].tolist()
    ma15_jisu_data = jisu_data[f'MA_{15}'].tolist()
    ma20_jisu_data = jisu_data[f'MA_{20}'].tolist()
    ma33_jisu_data = jisu_data[f'MA_{33}'].tolist()
    ma45_jisu_data = jisu_data[f'MA_{45}'].tolist()
    ma50_jisu_data = jisu_data[f'MA_{50}'].tolist()
    ma60_jisu_data = jisu_data[f'MA_{60}'].tolist()
    ma120_jisu_data = jisu_data[f'MA_{120}'].tolist()
    ma200_jisu_data = jisu_data[f'MA_{200}'].tolist()
    close_jisu_data = jisu_data['close'].tolist()
    open_jisu_data = jisu_data['open'].tolist()
    
    volume_data = data['volume'].tolist()
    volume_5_data = data['VOLUME_5'].tolist()
    volume_50_data = data['VOLUME_50'].tolist()
    volume_60_data = data['VOLUME_60'].tolist()

    # 매도 이평선(전략별) 값들을 미리 리스트로 변환해 핫루프에서 .iloc 접근을 피한다.
    sell_ema_data = [data[f'EMA_{window}'].tolist() for window in strategy[1]]

    index_date_data = index_data['date'].tolist()
    index_jisu_data = index_data['jisu_index'].tolist()

    target_date = datetime(2015, 6, 15)
    jisu_indexing = False
    index_start = 0

    for i in range(59, len(data)):
        if (date_data[i].to_pydatetime() < target_date):
            continue
        
        close = close_data[i]
        open_val = open_data[i]
        high = high_data[i]
        low = low_data[i]
        singo = singo_data[i]
        singo_high = singo_high_data[i]
        sinju = sinju_data[i]
        values_ma1 = ma1_data[i]
        values_ma2 = ma2_data[i]
        values_ma3 = ma3_data[i]
        values_ma5 = ma5_data[i]
        values_ma10 = ma10_data[i]
        values_ma20 = ma20_data[i]  
        values_ma33 = ma33_data[i]
        values_ma50 = ma50_data[i]
        ma20 = ma20_data[i]
        ma50 = ma50_data[i]
        ma60 = ma60_data[i]
        ma150 = ma150_data[i]
        ma200 = ma200_data[i]
        ma240 = ma240_data[i]
        
        ema5 = ema5_data[i]
        ema10 = ema10_data[i]
        ema12 = ema12_data[i]
        ema15 = ema15_data[i]
        ema20 = ema20_data[i]
        ema33 = ema33_data[i]        
        ema50 = ema50_data[i]        
        
        market_cap = market_cap_data[i]
        values = [values_ma10, values_ma20]
        values.sort()
        
        if jisu_indexing == False:
            index_start = i
            i_index = index_date_data.index(date_data[i])
            jisu_indexing = True
            
        jisu_index = index_jisu_data[i_index + i - index_start]
        
        ma5_jisu = ma5_jisu_data[jisu_index]
        ma20_jisu = ma20_jisu_data[jisu_index]
        ma33_jisu = ma33_jisu_data[jisu_index]
        ma45_jisu = ma45_jisu_data[jisu_index]
        ma50_jisu = ma50_jisu_data[jisu_index]
        ma60_jisu = ma60_jisu_data[jisu_index]
        ma120_jisu = ma120_jisu_data[jisu_index]
        ma200_jisu = ma200_jisu_data[jisu_index]
        close_jisu = close_jisu_data[jisu_index]
        prev_close_jisu = close_jisu_data[jisu_index - 1] if jisu_index > 0 else close_jisu
        open_jisu = open_jisu_data[jisu_index]      

        if close >= singo and not holding:
            singo = close
            singo_after_day = 1        
        
        for j in range(loss_cut_n, profit_loss_ratio[1] + 100):
            #if holding and close >= buy_price * (1 + (profit_loss_ratio[0] * j)/100):
            if holding and close >= buy_price * (1 + (profit_loss_ratio[0] * j)/100):
                if j == loss_cut_n_init : 
                    loss_cut_price = buy_price                    
                else :
                    loss_cut_price = buy_price * (1 + profit_loss_ratio[0]*(j-1)/100)                
                loss_cut_n += 1
                        
        if not holding:
            sell_after_day += 1

        conditions = []
        conditions.append(lambda: (close_data[i-1] <   close <= close_data[i-1]*1.14) or (close > close_data[i-1]*1.14 and (high/close_data[i-1] - close/close_data[i-1])*100 <= 10))
        conditions.append(lambda: not holding)                                                          # 매수중인 경우 추가매수 하지 않음 (추후 불타기에서 수정필요)
        conditions.append(lambda: close > ma50 > ma150)                                        # 종가 > 50일 이평선 > 150일 이평선 > 200일 이평 (초수익)   
        conditions.append(lambda: market_cap >= 500000000000)                                           # 시가총액  > 1조이상
        conditions.append(lambda: singo_lower_day_bound <= singo_after_day <= singo_upper_day_bound)    # 신고가후 singo_lower_day_bound ~ singo_upper_day_bound Day사이에만 매수
        conditions.append(lambda: close_jisu >= ma60_jisu)                                             # 지수가 45일 이평선이 60일보다 좋음
        conditions.append(lambda: close_jisu > prev_close_jisu*0.96)                              # 지수가 +인경우
        conditions.append(lambda: (values[0] * 1.1 >= values[-1]))                                      # 가장 큰 값이 가장 작은 값의 110%(즉, 10% 이내 증가) 이하인지 확인
        conditions.append(lambda: close >= sinju * 1.3)                                                # 240일 신저가대비보다 30프로 이상 높은 경우 (초수익)
        #conditions.append(lambda: sell_lower_day_bound <   sell_after_day)                               # 전량 매도 후 재매수 금지기간
        
        buy_condition = True
        for condition in conditions:
            if not condition():
                buy_condition = False
                break
            
        if buy_condition and open_val != high != close:
            recent_50_days_volume = volume_data[i-50:i] # 최근 30일간의 거래량 데이터
            max_volume = max(recent_50_days_volume)       # 최근 50일간의 최대 거래량     
            today_volume = volume_data[i]                 # 오늘의 거래량
            recent_200_days_close_price = close_data[i-200:i]    # 최근 50일간의 가격 데이터
            recent_breakout_high_price = high_data[max(0, i-strategy[0]):i]
            max_close_price = max(recent_200_days_close_price)         # 최근 50일간의 최고 가격
            max_high_price = max(recent_breakout_high_price)
            long_conditions = []
            long_conditions.append(lambda: volume_5_data[i-2] * 2  <   volume_data[i] or volume_5_data[i-1] * 2  <   volume_data[i])                    # 최근 5일간 거래량보다 당일 거래량이 2배 많은 경우
            long_conditions.append(lambda: ma50 > ma50_data[i-10])                                      # 금일 50일 이평선이 10일전 50일 이평선보다 높은 경우. 즉 장기 우상향인 경우 (초수익)
            long_conditions.append(lambda: volume_60_data[i] > volume_60_data[i-5])                     # 최근 거래량은 증가를 위해 60일 거래량 이평선이 상승추세인 종목 
            long_conditions.append(lambda: volume_5_data[i] > volume_5_data[i-20])      # 5일 거래량 이평선이 20일전대비 감소
            long_conditions.append(lambda: volume_50_data[i-1] >= volume_data[i-1] or volume_50_data[i-2] >= volume_data[i-2] or volume_50_data[i-3] >= volume_data[i-3])
            long_conditions.append(lambda: max_high_price <= close)
            #long_conditions.append(lambda: max_high_price <= high)
            
            #RS대용 : 5~300일간 지수대비 2.5배 아웃퍼폼한 종목
            RS_Rate = 2
            for n in [5, 10, 20, 30, 50] :
                if (close_jisu_data[i] - close_jisu_data[i-n] <= -1) :
                    long_conditions.append(lambda n=n: ((close_data[i]- close_data[i-n]) / close_data[i-n]) * 100 > ((close_jisu_data[i] - close_jisu_data[i-n]) / close_jisu_data[i-n]) * 100 / RS_Rate)
                elif (-1 <   close_jisu_data[i] - close_jisu_data[i-n] <   0) : 
                    long_conditions.append(lambda n=n: ((close_data[i]- close_data[i-n]) / close_data[i-n]) * 100 > 1)
                elif (0 <= close_jisu_data[i] - close_jisu_data[i-n] <   1) : 
                    long_conditions.append(lambda n=n: ((close_data[i]- close_data[i-n]) / close_data[i-n]) * 100 > RS_Rate)
                else :
                    long_conditions.append(lambda n=n: ((close_data[i]- close_data[i-n]) / close_data[i-n]) * 100 > ((close_jisu_data[i] - close_jisu_data[i-n]) / close_jisu_data[i-n]) * 100 * RS_Rate)
            
            
            RS_Long_Rate = 2
            for n in [100, 200, 299] :
                if (close_jisu_data[i] - close_jisu_data[i-n] <= -1) :
                    long_conditions.append(lambda n=n: ((close_data[i]- close_data[i-n]) / close_data[i-n]) * 100 > ((close_jisu_data[i] - close_jisu_data[i-n]) / close_jisu_data[i-n]) * 100 / RS_Long_Rate)
                elif (-1 <   close_jisu_data[i] - close_jisu_data[i-n] <   0) : 
                    long_conditions.append(lambda n=n: ((close_data[i]- close_data[i-n]) / close_data[i-n]) * 100 > 1)
                elif (0 <= close_jisu_data[i] - close_jisu_data[i-n] <   1) : 
                    long_conditions.append(lambda n=n: ((close_data[i]- close_data[i-n]) / close_data[i-n]) * 100 > RS_Long_Rate)
                else :
                    long_conditions.append(lambda n=n: ((close_data[i]- close_data[i-n]) / close_data[i-n]) * 100 > ((close_jisu_data[i] - close_jisu_data[i-n]) / close_jisu_data[i-n]) * 100 * RS_Long_Rate)
            
            long_buy_condition = True
            for long_condition in long_conditions:
                if not long_condition():
                    long_buy_condition = False
                    break

            if buy_condition and long_buy_condition:
            #if buy_condition and long_buy_condition and close <= max_high_price and (max_high_price/close)*100 - 100 < 2 :
                if (singo_high <= close) :
                    print(f"close : {close}, singo :{singo}, singo_high:{singo_high}")
                
                buget = initBuget
                buy_signals.append(date_data[i])
                holding = True
                #buy_price = close #close_data[buyIndex] # 매수 / 매도 종가 기준                
                #loss_cut_price = int(close * (1 - profit_loss_ratio[0]/ 100))
                
                if max_high_price <= high : 
                    if open_val >= max_high_price :
                        buy_price = (open_val + close) /2
                    else :
                        buy_price = (max_high_price + close) /2
                else :
                    buy_price = close #close_data[buyIndex] # 매수 / 매도 종가 기준
                '''
                if max_high_price <= high : 
                    buy_price = (max_high_price + close) /2
                
               
                loss_cut_price = int(buy_price * (1 - profit_loss_ratio[0]/ 100))
                '''
                loss_cut_n = 1
                Alread_Get_R = False
                buy_price = int(buy_price * (1 + util.SLIPPAGE_BUY / 100))
                loss_cut_price = int(buy_price * (1 - profit_loss_ratio[0] / 100))  # 초기 손절가 설정
                initial_qty = int(buget / buy_price)
                remaining_qty = initial_qty
                buget = buget - (initial_qty * buy_price)
                for sell_index in range(nTime):
                    sell_list[sell_index]= False
                sell_count = 0
                buy_after_day = 0
        elif holding:
            sell_price = close
            sell_price = int(sell_price * (1 - util.SLIPPAGE_SELL / 100))
            buy_after_day += 1
            today_volume = volume_data[i]
            max_volume = max(volume_data[max(0, i-50):i]) if i >= 50 else max(volume_data[0:i]) if i > 0 else 0

            # 거래정지
            if volume_data[i] == 0:
                continue            
            # 쩜하
            if (open_val == high == close == low) and close <    close_data[i-1]:
                continue            
            # 쩜하는 아닌 하한가 거래량 없어서 못파는
            if (close == low) and close <    close_data[i-1]*0.81 and volume_data[i] <    volume_5_data[i]*1.5:
                continue
            
            
            if not Alread_Get_R and close >= buy_price * (1 + (profit_loss_ratio[0] * profit_loss_ratio[1]) / 100):  # profit_loss_ratio[0]* profit_loss_ratio[1]이상이면 절반 익절
                sell_signals.append(date_data[i])
                sell_qty = int(remaining_qty * 0.5)
                remaining_qty -= sell_qty
                profit = (sell_price - buy_price) / buy_price * 100
                buget = buget + sell_qty * sell_price
                final_profit = (buget - initBuget) / initBuget * 100
                logging(logger, logLevel, f"매수일: {buy_signals[-1]}, {profit_loss_ratio[0]* profit_loss_ratio[1]}% 이상 수익 발생 절반 매도일: {sell_signals[-1]}, 수익률: {profit:.2f}%, 자산: {buget:.2f} 남은주식: {remaining_qty}")
                Alread_Get_R = True
                continue            
            
            '''
            if close >= buy_price * (1 + (profit_loss_ratio[0] * profit_loss_ratio[1]) / 100):  # profit_loss_ratio[0]* profit_loss_ratio[1]이상이면 전량 익절
                sell_signals.append(date_data[i])
                sell_qty = remaining_qty
                remaining_qty = 0
                profit = (sell_price - buy_price) / buy_price * 100
                buget = buget + sell_qty * sell_price
                final_profit = (buget - initBuget) / initBuget * 100
                total_profit += final_profit
                total_trades += 1
                if final_profit > 0:
                    win_trades += 1
                else:
                    loss_trades += 1
                sell_after_day = 0
                logging(logger, logLevel, f"매수일: {buy_signals[-1]}, {profit_loss_ratio[0]* profit_loss_ratio[1]}% 이상 수익 발생 전량 매도일: {sell_signals[-1]}, 수익률: {profit:.2f}%, 자산: {buget:.2f}, 최종수익률: {final_profit:.2f}%, 보유일: {sell_signals[-1]-buy_signals[-1]}")
                holding = False
                continue
            
            
            
            if close >= buy_price * 2:  # 100%이상 수익나면 전량 익절
                sell_signals.append(date_data[i])
                sell_qty = remaining_qty
                remaining_qty = 0
                profit = (sell_price - buy_price) / buy_price * 100
                buget = buget + sell_qty * sell_price
                final_profit = (buget - initBuget) / initBuget * 100
                total_profit += final_profit
                total_trades += 1
                if final_profit > 0:
                    win_trades += 1
                else:
                    loss_trades += 1
                sell_after_day = 0
                logging(logger, logLevel, f"매수일: {buy_signals[-1]}, {100}% 이상 수익 발생 전량 매도일: {sell_signals[-1]}, 수익률: {profit:.2f}%, 자산: {buget:.2f}, 최종수익률: {final_profit:.2f}%, 보유일: {sell_signals[-1]-buy_signals[-1]}")
                holding = False
                continue
            
            
            
            if max_price*0.8 >= close:  #  최근 100일내 최고점대비 n%고가가 낮으면 매도
                sell_signals.append(date_data[i])
                sell_qty = remaining_qty
                remaining_qty = 0
                profit = (sell_price - buy_price) / buy_price * 100
                buget = buget + sell_qty * sell_price
                final_profit = (buget - initBuget) / initBuget * 100
                total_profit += final_profit
                total_trades += 1
                if final_profit > 0:
                    win_trades += 1
                else:
                    loss_trades += 1
                sell_after_day = 0
                logging(logger, logLevel, f"매수일: {buy_signals[-1]}, 고점대비 30%하락 로스컷 전량 매도일: {sell_signals[-1]}, 수익률: {profit:.2f}%, 자산: {buget:.2f}, 최종수익률: {final_profit:.2f}%, 보유일: {sell_signals[-1]-buy_signals[-1]}")
                holding = False
                continue
            '''

            if close <   loss_cut_price:  #  -profit_loss_ratio % 깨면 매도
                sell_signals.append(date_data[i])
                sell_qty = remaining_qty
                remaining_qty = 0
                profit = (sell_price - buy_price) / buy_price * 100
                buget = buget + sell_qty * sell_price
                final_profit = (buget - initBuget) / initBuget * 100
                total_profit += final_profit
                total_trades += 1
                if final_profit > 0:
                    win_trades += 1
                else:
                    loss_trades += 1
                loss_cut_ratio = -profit_loss_ratio[0]+ (loss_cut_n-1)*profit_loss_ratio[0]
                sell_after_day = 0
                logging(logger, logLevel, f"매수일: {buy_signals[-1]}, {loss_cut_ratio}% 로스컷 전량 매도일: {sell_signals[-1]}, 수익률: {profit:.2f}%, 자산: {buget:.2f}, 최종수익률: {final_profit:.2f}%, 보유일: {sell_signals[-1]-buy_signals[-1]}")
                holding = False
                continue
            
            # 거래량이 많고 고점대비 저점이 15%이상나오면 전량매도 (깡토's Recommand = 10%)
            if today_volume >= max_volume *0.618 and (high/close_data[i-1] - close/close_data[i-1])*100 >= 15 :                 
                sell_signals.append(date_data[i])
                sell_qty = remaining_qty
                remaining_qty = 0
                profit = (sell_price - buy_price) / buy_price * 100
                buget = buget + sell_qty * sell_price
                final_profit = (buget - initBuget) / initBuget * 100
                total_profit += final_profit
                total_trades += 1
                if final_profit > 0:
                    win_trades += 1
                else:
                    loss_trades += 1
                sell_after_day = 0
                logging(logger, logLevel, f"매수일: {buy_signals[-1]}, 고가대비 {high/close_data[i-1] - close/close_data[i-1]}%하락 전량 매도일: {sell_signals[-1]}, 수익률: {profit:.2f}%, 자산: {buget:.2f}, 최종수익률: {final_profit:.2f}%, 보유일: {sell_signals[-1]-buy_signals[-1]}")
                holding = False
                continue     
            
            # 어제 종가대비 13%이상 하락하면 전량매도
            if close/close_data[i-1] * 100 <= 86.5 : 
                sell_signals.append(date_data[i])
                sell_qty = remaining_qty
                remaining_qty = 0
                profit = (sell_price - buy_price) / buy_price * 100
                buget = buget + sell_qty * sell_price
                final_profit = (buget - initBuget) / initBuget * 100
                total_profit += final_profit
                total_trades += 1
                if final_profit > 0:
                    win_trades += 1
                else:
                    loss_trades += 1
                loss_cut_ratio = -profit_loss_ratio[0]+ (loss_cut_n-1)*profit_loss_ratio[0]
                sell_after_day = 0
                logging(logger, logLevel, f"매수일: {buy_signals[-1]}, 전일대비 {(1 - close/close_data[i-1])*100}% 하락 전량 매도일: {sell_signals[-1]}, 수익률: {profit:.2f}%, 자산: {buget:.2f}, 최종수익률: {final_profit:.2f}%, 보유일: {sell_signals[-1]-buy_signals[-1]}")
                holding = False
                continue
                        
            if buy_upper_day_bound <     buy_after_day and sell_price <     buy_price :
                sell_signals.append(date_data[i])
                sell_qty = remaining_qty
                remaining_qty = 0
                profit = (sell_price - buy_price) / buy_price * 100
                buget = buget + sell_qty * sell_price
                final_profit = (buget - initBuget) / initBuget * 100
                total_profit += final_profit
                total_trades += 1
                if final_profit > 0:
                    win_trades += 1
                else:
                    loss_trades += 1
                loss_cut_ratio = -profit_loss_ratio[0]+ (loss_cut_n-1)*profit_loss_ratio[0]
                sell_after_day = 0
                logging(logger, logLevel, f"매수일: {buy_signals[-1]}, {buy_after_day} 최대보유일 매도일: {sell_signals[-1]}, 수익률: {profit:.2f}%, 자산: {buget:.2f}, 최종수익률: {final_profit:.2f}%, 보유일: {sell_signals[-1]-buy_signals[-1]}")
                holding = False
                continue
                
            
            for j in range(nTime):
                #if close <  data[f'MA_{strategy[1][j]}'].iloc[i]and sell_list[j]== False and buy_price <  sell_price:  # n일선 깨면 매도
                if close <  sell_ema_data[j][i]and sell_list[j]== False and buy_price <   sell_price :
                    sell_list[j] = True
                    sell_qty = int(remaining_qty * 1/(nTime-sell_count))
                    remaining_qty -= sell_qty
                    sell_signals.append(date_data[i])
                    profit = (sell_price - buy_price) / buy_price * 100
                    buget = buget + sell_qty * sell_price
                    final_profit = (buget - initBuget) / initBuget * 100
                    if remaining_qty == 0:
                        total_trades += 1
                        total_profit += final_profit
                        sell_after_day = 0
                        logging(logger, logLevel, f"매수일: {buy_signals[-1]}, {strategy[1][j]}선 매도일: {sell_signals[-1]}, 수익률: {profit:.2f}%, 자산: {buget:.2f} 남은주식: {remaining_qty}, 최종수익률: {final_profit:.2f}%, 보유일: {sell_signals[-1]-buy_signals[-1]}")
                        holding = False
                        if final_profit > 0:
                            win_trades += 1
                        else:
                            loss_trades += 1
                    else:
                        logging(logger, logLevel, f"매수일: {buy_signals[-1]}, {strategy[1][j]}선 매도일: {sell_signals[-1]}, 수익률: {profit:.2f}%, 자산: {buget:.2f} 남은주식: {remaining_qty}")
                    sell_count += 1
            
            
        singo_after_day += 1

    if holding and remaining_qty > 0:
        sell_price = int(close_data[-1] * (1 - util.SLIPPAGE_SELL / 100))
        sell_signals.append(date_data[-1])
        buget += remaining_qty * sell_price
        remaining_qty = 0
        final_profit = (buget - initBuget) / initBuget * 100
        total_profit += final_profit
        total_trades += 1
        if final_profit > 0:
            win_trades += 1
        else:
            loss_trades += 1
        logging(logger, logLevel, f"매수일: {buy_signals[-1]}, 백테스트 종료 전량 매도일: {sell_signals[-1]}, 자산: {buget:.2f}, 최종수익률: {final_profit:.2f}%, 보유일: {sell_signals[-1]-buy_signals[-1]}")

    win_rate = win_trades / total_trades * 100 if total_trades > 0 else 0
    loss_rate = loss_trades / total_trades * 100 if total_trades > 0 else 0
    total_profit = total_profit if total_trades > 0 else 0

    logging(logger, logLevel, f"총 거래 횟수: {total_trades}, 이익 거래 비율: {win_rate:.2f}%, 손실 거래 비율: {loss_rate:.2f}%, 수익률합산: {total_profit:.2f}%")
    return buy_signals, sell_signals, total_profit, total_trades, win_trades, loss_trades