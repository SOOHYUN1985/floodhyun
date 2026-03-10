"""
리포트 생성기
- 과열 게이지 대시보드 (프로그레스바 + 신호등)
- 상승/하락 별 매도 전략 시각화
- 전략 간 독립성(상관관계) 표시
- 전략별 상세 분석 (매도일, 지수, 5/10/15/20일 후 수익률)
"""

import os
import re as _re
from datetime import datetime
from typing import List, Dict
import pandas as pd
import numpy as np

from config import STOP_LOSS_STAGES, REPORTS_DIR


class ReportGenerator:
    """리포트 생성기"""
    
    def __init__(self, market_name: str, current_price: float, 
                 trend_type: str, trend_confidence: int,
                 selected_strategies: List[Dict],
                 df: pd.DataFrame = None):
        self.market_name = market_name
        self.current_price = current_price
        self.trend_type = trend_type
        self.trend_confidence = trend_confidence
        self.strategies = selected_strategies
        self.df = df
        self.current_date = datetime.now().strftime('%Y-%m-%d')
    
    def generate(self) -> str:
        """
        리포트 생성
        
        Returns:
            리포트 파일 경로
        """
        os.makedirs(REPORTS_DIR, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{self.market_name}_고점판독리포트_{timestamp}.md"
        filepath = os.path.join(REPORTS_DIR, filename)
        
        report = self._build_report()
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"\n✅ 리포트 저장: {filepath}")
        
        return filepath
    
    def _build_report(self) -> str:
        """리포트 내용 생성"""
        report = f"""# 🚨 {self.market_name} 고점 판독 리포트

**생성일시**: {datetime.now().strftime('%Y년 %m월 %d일 %H시 %M분')}  
**기준일**: {self.current_date}  
**현재 지수**: {self.current_price:,.2f}

---

{self._generate_overheat_dashboard()}

---

## 📊 시장 추세 판단

| 항목 | 결과 |
|------|------|
| **시장 추세** | {self._get_trend_emoji()} **{self._get_trend_name()}** |
| **신뢰도** | {self.trend_confidence}% |
| **적응 전략** | {self.trend_type.upper()} 시장 최적화 |

---

{self._generate_action_summary()}

---

{self._generate_sell_strategy_table()}

{self._generate_stop_loss_table()}

---

{self._generate_independence_analysis()}

---

## 📈 백테스트 결과 요약

| 항목 | 결과 |
|------|------|
| **선정된 전략 수** | {len(self.strategies)}개 |
| **평균 승률** | {self._get_avg_win_rate():.1f}% |
| **상향돌파 전략** | {sum(1 for s in self.strategies if s['type'] == 'breakout')}개 |
| **하락반전 전략** | {sum(1 for s in self.strategies if s['type'] == 'reversal')}개 |

### 선정된 전략 목록

| 순위 | 전략명 | 유형 | 승률 | 신호수 |
|:----:|--------|:----:|-----:|:------:|
{self._generate_strategy_list_table()}

---

{self._generate_strategy_details()}

---

## ⚠️ 리스크 관리 가이드

### 필수 준수 사항

1. **분할 매도 원칙**
   - 5단계로 나누어 단계적 매도
   - 한 번에 전량 매도 금지
   - 각 단계별 20% 씩

2. **손절가 설정**
   - 1단계: 현재가 기준 -3%
   - 2단계: 현재가 기준 -5%
   - 3단계 이후: 이전 단계 진입가 -3%

3. **상황별 대응**
   - 급등: 예정보다 빠른 매도
   - 급락: 손절가 즉시 실행
   - 횡보: 계획대로 단계적 진행

---

**생성**: {datetime.now().strftime('%Y년 %m월 %d일 %H시 %M분')}  
**시스템**: MarketTop v2 - 고점 판독 시스템
"""
        return report
    
    # ──────────────────────────────────────────────────────────
    # 과열 게이지 대시보드
    # ──────────────────────────────────────────────────────────
    def _generate_overheat_dashboard(self) -> str:
        """과열 상태 대시보드 - 프로그레스바 + 신호등"""
        if self.df is None:
            return ""
        
        cur = self.df.iloc[-1]
        
        # 지표별 과열 수준 계산 (0~100 스케일)
        indicators = []
        
        # RSI (0-100, 70+ 과열)
        rsi = cur.get('RSI')
        if rsi is not None and not pd.isna(rsi):
            level = min(100, max(0, (rsi - 30) / 0.7))  # 30=0%, 100=100%
            indicators.append({
                'name': 'RSI', 'value': rsi, 'level': level,
                'format': f'{rsi:.1f}', 'zone': '과열' if rsi >= 70 else ('중립' if rsi >= 50 else '과매도'),
                'threshold': 70
            })
        
        # Stochastic %K (0-100, 80+ 과열)
        stoch = cur.get('Stoch_K')
        if stoch is not None and not pd.isna(stoch):
            level = min(100, max(0, stoch))
            indicators.append({
                'name': 'Stochastic', 'value': stoch, 'level': level,
                'format': f'{stoch:.1f}', 'zone': '과열' if stoch >= 80 else ('중립' if stoch >= 20 else '과매도'),
                'threshold': 80
            })
        
        # MFI (0-100, 80+ 과열)
        mfi = cur.get('MFI')
        if mfi is not None and not pd.isna(mfi):
            level = min(100, max(0, mfi))
            indicators.append({
                'name': 'MFI', 'value': mfi, 'level': level,
                'format': f'{mfi:.1f}', 'zone': '과열' if mfi >= 80 else ('중립' if mfi >= 20 else '과매도'),
                'threshold': 80
            })
        
        # CCI (일반 -200~+200, 100+ 과열)
        cci = cur.get('CCI')
        if cci is not None and not pd.isna(cci):
            level = min(100, max(0, (cci + 200) / 4))  # -200=0%, +200=100%
            indicators.append({
                'name': 'CCI', 'value': cci, 'level': level,
                'format': f'{cci:.0f}', 'zone': '과열' if cci >= 100 else ('중립' if cci >= -100 else '과매도'),
                'threshold': 100
            })
        
        # BB 위치 (0~100%, 90%+ 과열)
        bb_upper = cur.get('BB_upper')
        bb_lower = cur.get('BB_lower')
        if bb_upper is not None and bb_lower is not None and not pd.isna(bb_upper):
            bb_range = bb_upper - bb_lower
            if bb_range > 0:
                bb_pos = (self.current_price - bb_lower) / bb_range * 100
                bb_pos = min(100, max(0, bb_pos))
                indicators.append({
                    'name': 'BB위치', 'value': bb_pos, 'level': bb_pos,
                    'format': f'{bb_pos:.0f}%', 'zone': '상단' if bb_pos >= 80 else ('중간' if bb_pos >= 20 else '하단'),
                    'threshold': 80
                })
        
        # ADX (추세 강도, 25+ 강한 추세)
        adx = cur.get('ADX')
        if adx is not None and not pd.isna(adx):
            level = min(100, max(0, adx * 2))  # 50=100%
            indicators.append({
                'name': 'ADX(추세강도)', 'value': adx, 'level': level,
                'format': f'{adx:.1f}', 'zone': '강한추세' if adx >= 40 else ('추세' if adx >= 25 else '약한추세'),
                'threshold': 25
            })
        
        # MACD 히스토그램 상태 (과거 대비 상대적 위치)
        macd_hist = cur.get('MACD_Hist')
        macd = cur.get('MACD')
        macd_signal = cur.get('MACD_Signal')
        
        if macd_hist is not None and not pd.isna(macd_hist):
            # 최근 250일 MACD_Hist 기준 percentile → 0~100 스케일
            hist_series = self.df['MACD_Hist'].dropna().tail(250)
            if len(hist_series) > 10:
                rank = (hist_series < macd_hist).sum()
                level = rank / len(hist_series) * 100
            else:
                level = 50
            zone = '강세' if macd_hist > 0 else '약세'
            cross_note = ''
            if macd is not None and macd_signal is not None:
                if not pd.isna(macd) and not pd.isna(macd_signal):
                    prev_hist = self.df['MACD_Hist'].iloc[-2] if len(self.df) > 1 else 0
                    if not pd.isna(prev_hist):
                        if prev_hist > 0 and macd_hist <= 0:
                            cross_note = ' ⚠️데드'
                        elif prev_hist <= 0 and macd_hist > 0:
                            cross_note = ' ✅골든'
            indicators.append({
                'name': f'MACD{cross_note}', 'value': macd_hist, 'level': level,
                'format': f'{macd_hist:.2f}', 'zone': zone,
                'threshold': None
            })
        
        if not indicators:
            return ""
        
        # 종합 과열 점수 계산 (RSI, Stoch, MFI, CCI, BB 기준)
        heat_scores = [ind['level'] for ind in indicators if ind['name'] in ['RSI', 'Stochastic', 'MFI', 'CCI', 'BB위치']]
        overall_heat = sum(heat_scores) / len(heat_scores) if heat_scores else 50
        
        # 종합 신호등
        if overall_heat >= 75:
            overall_signal = '🔴'
            overall_text = '과열 위험'
            overall_desc = '다수 지표가 과열 구간입니다. 매도 전략을 적극적으로 실행하세요.'
        elif overall_heat >= 60:
            overall_signal = '🟡'
            overall_text = '주의 구간'
            overall_desc = '일부 지표가 과열 접근 중입니다. 매도 준비를 시작하세요.'
        elif overall_heat >= 40:
            overall_signal = '🟢'
            overall_text = '정상 구간'
            overall_desc = '대부분의 지표가 정상 범위입니다. 기존 포지션을 유지하세요.'
        else:
            overall_signal = '🔵'
            overall_text = '과매도/저평가'
            overall_desc = '지표가 낮은 구간에 있습니다. 매수 기회를 탐색하세요.'
        
        heat_score_text = f"{overall_heat:.0f}"
        bar_text = self._make_progress_bar(overall_heat, 100, 20)
        
        text = f"""## 🌡️ 현재 과열 상태 대시보드

### {overall_signal} 종합 판정: **{overall_text}** ({heat_score_text}/100)

{bar_text} **{heat_score_text}점**

> {overall_desc}

### 📊 개별 지표 과열 게이지

| 지표 | 현재값 | 과열 게이지 | 상태 |
|------|-------:|------------|:----:|
"""
        
        for ind in indicators:
            bar = self._make_progress_bar(ind['level'], 100, 15)
            signal = self._get_indicator_signal(ind['level'])
            text += f"| **{ind['name']}** | {ind['format']} | {bar} | {signal} {ind['zone']} |\n"
        
        # 과열 지표 개수 요약
        hot_count = sum(1 for ind in indicators if ind['level'] >= 70 and ind['name'] not in ['ADX(추세강도)'] and 'MACD' not in ind['name'])
        text += f"\n**⚡ 과열 지표 수**: {hot_count} / {len([i for i in indicators if i['name'] not in ['ADX(추세강도)'] and 'MACD' not in i['name']])}개"
        if hot_count >= 3:
            text += " → 🔴 **매도 신호 강함**\n"
        elif hot_count >= 2:
            text += " → 🟡 **매도 주의**\n"
        else:
            text += " → 🟢 **안전 구간**\n"
        
        return text
    
    def _make_progress_bar(self, value: float, max_val: float, width: int = 15) -> str:
        """텍스트 프로그레스바 생성"""
        ratio = min(1.0, max(0.0, value / max_val))
        filled = int(ratio * width)
        empty = width - filled
        
        # 구간별 색상 (이모지 블록)
        if ratio >= 0.75:
            fill_char = '🟥'
        elif ratio >= 0.6:
            fill_char = '🟧'
        elif ratio >= 0.4:
            fill_char = '🟨'
        else:
            fill_char = '🟩'
        
        bar = fill_char * filled + '⬜' * empty
        return bar
    
    def _get_indicator_signal(self, level: float) -> str:
        """지표 레벨에 따른 신호등"""
        if level >= 80:
            return '🔴'
        elif level >= 60:
            return '🟡'
        elif level >= 40:
            return '🟢'
        else:
            return '🔵'
    
    # ──────────────────────────────────────────────────────────
    # 즉시 행동 요약 (상승/하락 분리)
    # ──────────────────────────────────────────────────────────
    def _generate_action_summary(self) -> str:
        """상승/하락 시나리오별 핵심 행동 요약"""
        breakout = [s for s in self.strategies if s['type'] == 'breakout']
        reversal = [s for s in self.strategies if s['type'] == 'reversal']
        
        # 상승 시 최근접 매도 목표
        nearest_target = None
        for s in breakout:
            tp = self._calculate_trigger_price(s)
            if tp is not None:
                pct = (tp - self.current_price) / self.current_price * 100
                if nearest_target is None or tp < nearest_target['price']:
                    nearest_target = {'price': tp, 'pct': pct, 'name': s['name'], 'win_rate': s['win_rate']}
        
        # 이미 발동된 전략
        triggered = []
        for s in breakout:
            tp = self._calculate_trigger_price(s)
            if tp is not None:
                pct = (tp - self.current_price) / self.current_price * 100
                if pct <= 0:
                    triggered.append({'name': s['name'], 'price': tp, 'pct': pct})
        
        lines = ["## 🎯 지금 해야 할 것", "", "### 📈 지수가 계속 상승하면?"]
        
        if triggered:
            lines.append("")
            lines.append("🔴 **즉시 매도 필요!** — 아래 전략이 이미 발동되었습니다:")
            lines.append("")
            for t in triggered:
                lines.append(f"  - **{t['name']}** (목표가 {t['price']:,.0f}, 현재 {t['pct']:+.1f}%)")
            lines.append("")
        elif nearest_target:
            price_text = f"{nearest_target['price']:,.0f}"
            pct_text = f"{nearest_target['pct']:+.1f}%"
            wr_text = f"{nearest_target['win_rate']:.1f}%"
            lines.append("")
            lines.append("| 항목 | 내용 |")
            lines.append("|------|------|")
            lines.append(f"| **다음 매도 목표가** | **{price_text}** (현재 대비 {pct_text}) |")
            lines.append(f"| **사용 전략** | {nearest_target['name']} |")
            lines.append(f"| **해당 전략 승률** | {wr_text} |")
            lines.append("| **행동** | 목표가 도달 시 **20% 분할 매도** 실행 |")
            lines.append("")
        else:
            lines.append("")
            lines.append("⚠️ 상향돌파 전략 목표가 미산출 — 아래 상세표 참고")
            lines.append("")
        
        lines.append("### 📉 지수가 하락하면?")
        
        if reversal:
            top = reversal[0]
            defense_price = f"{self.current_price * 0.97:,.0f}"
            wr_text = f"{top['win_rate']:.1f}%"
            lines.append("")
            lines.append("| 항목 | 내용 |")
            lines.append("|------|------|")
            lines.append(f"| **1차 방어선** | 현재가 -3% = **{defense_price}** |")
            lines.append(f"| **핵심 하락 감지 전략** | {top['name']} (승률 {wr_text}) |")
            lines.append("| **행동** | 하락반전 신호 발동 시 **30% 즉시 매도** |")
            lines.append("")
            if len(reversal) >= 2:
                lines.append(f"> 💡 하락반전 전략 {len(reversal)}개 중 **2개 이상 동시 발동 시** → 50% 이상 즉시 청산")
                lines.append("")
        else:
            defense_price = f"{self.current_price * 0.97:,.0f}"
            lines.append("")
            lines.append("| 항목 | 내용 |")
            lines.append("|------|------|")
            lines.append(f"| **1차 방어선** | 현재가 -3% = **{defense_price}** |")
            lines.append("| **행동** | 손절가 도달 시 **30% 매도** |")
            lines.append("")
        
        return "\n".join(lines)

    # ──────────────────────────────────────────────────────────
    # 전략 독립성 분석
    # ──────────────────────────────────────────────────────────
    def _generate_independence_analysis(self) -> str:
        """전략 간 독립성(상관관계) 분석"""
        if len(self.strategies) < 2:
            return ""
        
        text = """## 🔗 전략 독립성 분석

> 선정된 전략들이 서로 **다른 지표**를 사용할수록 신뢰도가 높습니다.  
> 동일 지표 기반 전략은 함께 맞거나 틀릴 가능성이 높아 분산 효과가 낮습니다.

"""
        # 각 전략에서 사용 지표 추출
        indicator_keywords = {
            'RSI': 'RSI',
            'Stoch': 'Stochastic',
            'MFI': 'MFI',
            'CCI': 'CCI',
            'MACD': 'MACD',
            'BB': 'Bollinger',
            'ADX': 'ADX',
            'DMI': 'DMI',
            'OBV': 'OBV',
            'VWAP': 'VWAP',
            '거래량': 'Volume',
            '이격도': 'Disparity',
        }
        
        strategy_indicators = []
        for s in self.strategies:
            used = set()
            for key, label in indicator_keywords.items():
                if key in s['name']:
                    used.add(label)
            # 이격도는 대부분의 전략에 기본 포함
            if 'Disparity' not in used and s['type'] == 'breakout':
                used.add('Disparity')
            strategy_indicators.append({'strategy': s, 'indicators': used})
        
        # 지표 사용 매트릭스 표
        all_indicators = sorted(set(ind for si in strategy_indicators for ind in si['indicators']))
        
        text += "### 📊 지표 사용 매트릭스\n\n"
        
        # 행: 전략, 열: 지표
        header = "| 전략 | " + " | ".join(all_indicators) + " | 독립지표 수 |\n"
        sep = "|------|" + "|".join([":---:" for _ in all_indicators]) + "|:---:|\n"
        text += header + sep
        
        for si in strategy_indicators:
            short_name = si['strategy']['name']
            if len(short_name) > 25:
                short_name = short_name[:22] + "..."
            row = f"| {short_name} | "
            for ind in all_indicators:
                row += "✅" if ind in si['indicators'] else "·"
                row += " | "
            non_disparity = [i for i in si['indicators'] if i != 'Disparity']
            row += f"**{len(non_disparity)}** |\n"
            text += row
        
        text += "\n"
        
        # 신호 겹침 분석 (실제 발동일 기준)
        text += "### 📈 신호 독립성 (발동일 겹침률)\n\n"
        
        # 상향돌파끼리, 하락반전끼리 분석
        for type_name, type_label in [('breakout', '상향돌파'), ('reversal', '하락반전')]:
            type_strategies = [si for si in strategy_indicators if si['strategy']['type'] == type_name]
            if len(type_strategies) < 2:
                continue
            
            text += f"**{type_label} 전략 간 겹침률:**\n\n"
            text += "| 전략 A | 전략 B | 신호 겹침률 | 독립성 |\n"
            text += "|--------|--------|:----------:|:------:|\n"
            
            for i in range(len(type_strategies)):
                for j in range(i + 1, len(type_strategies)):
                    si_a = type_strategies[i]
                    si_b = type_strategies[j]
                    
                    signals_a = set(fr['signal_date'] for fr in si_a['strategy']['forward_returns'])
                    signals_b = set(fr['signal_date'] for fr in si_b['strategy']['forward_returns'])
                    
                    if len(signals_a) == 0 or len(signals_b) == 0:
                        continue
                    
                    overlap = len(signals_a & signals_b)
                    similarity = overlap / max(len(signals_a), len(signals_b)) * 100
                    
                    if similarity <= 5:
                        independence = "🟢 **매우 독립**"
                    elif similarity <= 15:
                        independence = "🟢 독립적"
                    elif similarity <= 30:
                        independence = "🟡 보통"
                    else:
                        independence = "🔴 유사"
                    
                    name_a = si_a['strategy']['name']
                    if len(name_a) > 20:
                        name_a = name_a[:17] + "..."
                    name_b = si_b['strategy']['name']
                    if len(name_b) > 20:
                        name_b = name_b[:17] + "..."
                    
                    text += f"| {name_a} | {name_b} | {similarity:.0f}% | {independence} |\n"
            
            text += "\n"
        
        # 종합 독립성 평점
        all_pairs = []
        for i in range(len(strategy_indicators)):
            for j in range(i + 1, len(strategy_indicators)):
                si_a = strategy_indicators[i]
                si_b = strategy_indicators[j]
                
                # 지표 겹침
                common = si_a['indicators'] & si_b['indicators']
                total = si_a['indicators'] | si_b['indicators']
                indicator_overlap = len(common) / len(total) * 100 if total else 0
                
                # 신호 겹침
                signals_a = set(fr['signal_date'] for fr in si_a['strategy']['forward_returns'])
                signals_b = set(fr['signal_date'] for fr in si_b['strategy']['forward_returns'])
                if signals_a and signals_b:
                    signal_overlap = len(signals_a & signals_b) / max(len(signals_a), len(signals_b)) * 100
                else:
                    signal_overlap = 0
                
                all_pairs.append({'indicator_overlap': indicator_overlap, 'signal_overlap': signal_overlap})
        
        if all_pairs:
            avg_signal_overlap = np.mean([p['signal_overlap'] for p in all_pairs])
            avg_indicator_overlap = np.mean([p['indicator_overlap'] for p in all_pairs])
            
            if avg_signal_overlap <= 10:
                grade = '🟢 **A** (매우 우수)'
            elif avg_signal_overlap <= 20:
                grade = '🟢 **B** (우수)'
            elif avg_signal_overlap <= 35:
                grade = '🟡 **C** (보통)'
            else:
                grade = '🔴 **D** (개선 필요)'
            
            text += f"### 종합 독립성 평가\n\n"
            text += f"| 항목 | 값 |\n|------|----|\n"
            text += f"| **평균 신호 겹침률** | {avg_signal_overlap:.1f}% |\n"
            text += f"| **평균 지표 겹침률** | {avg_indicator_overlap:.1f}% |\n"
            text += f"| **독립성 등급** | {grade} |\n\n"
            text += "> 💡 신호 겹침률이 낮을수록 전략 조합의 분산 효과가 높습니다.\n"
        
        return text

    def _generate_sell_strategy_table(self) -> str:
        """분할매도 전략 표 생성 - 전략 발동가 기반"""
        breakout_strategies = [s for s in self.strategies if s['type'] == 'breakout']
        
        text = """## 📍 분할매도 전략 (상세)

### 📊 백테스트 기반 상향돌파 신호

상향돌파 전략은 **이격도 상승과 기술적 과열**을 감지합니다.  
각 전략의 **발동 목표가**는 현재 이동평균값과 이격도 조건으로부터 산출된 **실제 지수**입니다.  
해당 목표가에 도달하면 전략이 발동되므로, 이때 단계적 매도를 실행하세요.

"""
        
        if not breakout_strategies:
            text += "\n⚠️ **상향돌파 전략 미선정**\n\n"
            return text
        
        # 각 전략의 실제 발동 가격 계산
        trigger_list = []
        no_trigger_list = []
        
        for s in breakout_strategies:
            trigger_price = self._calculate_trigger_price(s)
            if trigger_price is not None:
                pct_change = (trigger_price - self.current_price) / self.current_price * 100
                trigger_list.append({
                    'strategy': s,
                    'trigger_price': trigger_price,
                    'pct_change': pct_change,
                })
            else:
                no_trigger_list.append(s)
        
        # 발동가 오름차순 정렬
        trigger_list.sort(key=lambda x: x['trigger_price'])
        
        # 발동가가 없는 전략(DMI/VWAP 등)은 마지막에 추가
        for s in no_trigger_list:
            trigger_list.append({
                'strategy': s,
                'trigger_price': None,
                'pct_change': None,
            })
        
        # 전체 전략 요약 표 (발동가 포함)
        text += "| 우선순위 | 상향돌파 전략 | 승률 | 신호수 | 발동 조건 | 발동 목표가 |\n"
        text += "|:--------:|--------------|-----:|:------:|-----------|:-----------:|\n"
        
        for i, item in enumerate(trigger_list, 1):
            s = item['strategy']
            condition = self._parse_breakout_condition(s['name'])
            if item['trigger_price'] is not None:
                trigger_text = f"**{item['trigger_price']:,.0f}** ({item['pct_change']:+.1f}%)"
            else:
                trigger_text = "조건 충족 시"
            text += f"| **{i}순위** | {s['name']} | **{s['win_rate']:.1f}%** | {s['signal_count']} | {condition} | {trigger_text} |\n"
        
        avg_breakout_winrate = sum(s['win_rate'] for s in breakout_strategies) / len(breakout_strategies)
        text += f"\n**💡 평균 승률**: **{avg_breakout_winrate:.1f}%** (전체 {len(breakout_strategies)}개 전략)\n\n"
        
        # 발동가가 있는 전략만 단계별 표에 사용
        priced_list = [item for item in trigger_list if item['trigger_price'] is not None]
        
        if not priced_list:
            text += "\n⚠️ **발동 목표가를 산출할 수 있는 전략이 없습니다.**\n"
            return text
        
        # 지표 조합 다양성 기반 단계 배정
        # 같은 보조지표 조합의 전략은 최대 2개까지만 배치
        indicator_keywords = ['RSI', 'Stoch', 'MFI', 'CCI', 'MACD', 'BB', 'ADX', 'DMI',
                              'OBV', 'VWAP', '거래량']
        
        def get_secondary_indicators(name):
            return frozenset(k for k in indicator_keywords if k in name)
        
        MAX_PER_INDICATOR_GROUP = 2
        group_counts = {}  # indicator_set -> count
        diverse_list = []
        skipped = []
        
        for item in priced_list:
            ind_set = get_secondary_indicators(item['strategy']['name'])
            count = group_counts.get(ind_set, 0)
            if count < MAX_PER_INDICATOR_GROUP:
                diverse_list.append(item)
                group_counts[ind_set] = count + 1
            else:
                skipped.append(item)
        
        # 단계 수는 다양화된 전략 수 (최대 5)
        n_stages = min(len(diverse_list), 5)
        unique_groups = len(group_counts)
        
        ratio_map = {
            5: [20, 20, 20, 20, 20],
            4: [20, 20, 25, 35],
            3: [25, 35, 40],
            2: [40, 60],
            1: [100],
        }
        ratios = ratio_map.get(n_stages, [100])
        
        stage_descs = {1: '초기 익절', 2: '추가 익절', 3: '주요 익절', 4: '대부분 익절', 5: '완전 청산'}
        
        # 스킵된 전략이 있으면 다양성 설명 추가
        if skipped:
            text += f"> ⚠️ **지표 다양성 필터 적용**: 동일 보조지표 조합의 전략은 최대 {MAX_PER_INDICATOR_GROUP}개까지만 단계에 배치합니다.  \n"
            text += f"> 전체 {len(priced_list)}개 중 **{len(diverse_list)}개** 선정 (독립 지표 그룹 {unique_groups}개)  \n"
            skipped_names = ', '.join(s['strategy']['name'] for s in skipped)
            text += f"> 제외: {skipped_names}  \n\n"
        
        text += """
### 📍 단계별 목표가 및 전략

> 각 전략의 **이격도 조건 x 현재 이동평균값**으로 산출된 실제 발동 목표가입니다.  
> 지수가 목표가에 도달하고 보조지표 조건이 충족되면 전략이 발동됩니다.

| 단계 | 매도<br>비중 | 목표가 | 등락률 | 사용 전략 | 승률 | 상태 | 권고 행동 |
|:----:|:----:|-------:|:------:|-----------|:----:|:----:|-----------|
"""
        
        for i in range(n_stages):
            item = diverse_list[i]
            s = item['strategy']
            trigger_price = item['trigger_price']
            pct_change = item['pct_change']
            ratio = ratios[i]
            stage_num = i + 1
            stage_desc = stage_descs.get(stage_num, '추가 익절')
            
            # 상태 결정
            if pct_change <= 0:
                status = "🔴 **발동중**"
                action = "**즉시 매도 실행**"
            elif pct_change < 2:
                status = "⚡ **임박**"
                action = f"지수 **{trigger_price:,.0f}** 도달 시<br>**즉시 매도**"
            elif pct_change < 5:
                status = "🎯 **근접**"
                action = f"지수 **{trigger_price:,.0f}** 도달 시<br>**매도 실행**"
            else:
                status = "⏳ **대기**"
                action = f"지수 **{trigger_price:,.0f}** 도달 시<br>**매도 실행**"
            
            # MA 기간 정보 추출
            ma_period = s.get('ma_period')
            disparity = s.get('disparity')
            if ma_period and disparity and self.df is not None:
                ma_col = f'MA{ma_period}'
                if ma_col in self.df.columns:
                    current_ma = self.df[ma_col].iloc[-1]
                    action += f"<br>_(MA{ma_period}={current_ma:,.0f} x {disparity}%)_"
            
            strategy_text = s['name'].replace(' + ', '<br>+ ')
            
            text += f"| **{stage_num}단계**<br>{stage_desc} | **{ratio}%** | "
            text += f"**{trigger_price:,.0f}** | **{pct_change:+.1f}%** | {strategy_text} | **{s['win_rate']:.1f}%** | {status} | {action} |\n"
        
        # 실행 요약
        triggered = [item for item in diverse_list[:n_stages] if item['pct_change'] <= 0]
        near = [item for item in diverse_list[:n_stages] if 0 < item['pct_change'] < 5]
        waiting = [item for item in diverse_list[:n_stages] if item['pct_change'] >= 5]
        
        text += "\n**💡 실행 요약**\n"
        if triggered:
            text += f"- 🔴 **{len(triggered)}개 전략 이미 발동** - 즉시 매도 검토 필요\n"
            for item in triggered:
                text += f"  - {item['strategy']['name']} (목표가 {item['trigger_price']:,.0f}, 현재 {item['pct_change']:+.1f}%)\n"
        if near:
            first_near = near[0]
            text += f"- 🎯 **다음 목표가**: {first_near['trigger_price']:,.0f} ({first_near['pct_change']:+.1f}%) → {first_near['strategy']['name']}\n"
        if waiting:
            text += f"- ⏳ **{len(waiting)}개 전략 대기 중** - 추가 상승 시 단계적 청산\n"
        if not triggered and not near:
            text += "- 🟢 **현재 안전 구간** - 매도 신호 없음\n"
        
        text += "\n"
        
        return text
    
    def _calculate_trigger_price(self, strategy: Dict) -> float:
        """전략의 실제 발동 가격 계산
        
        상향돌파 전략의 경우: 목표가 = 현재 MA값 x (이격도 / 100)
        """
        if self.df is None:
            return None
        
        disparity = strategy.get('disparity')
        ma_period = strategy.get('ma_period')
        
        if disparity is None or ma_period is None:
            return None
        
        ma_col = f'MA{ma_period}'
        if ma_col in self.df.columns:
            current_ma = self.df[ma_col].iloc[-1]
        else:
            current_ma = self.df['close'].rolling(window=ma_period).mean().iloc[-1]
        
        if pd.isna(current_ma):
            return None
        
        return current_ma * (disparity / 100)
    
    def _generate_stop_loss_table(self) -> str:
        """하락 시 손절 전략 표 생성 - 백테스트 기반 하락반전 전략 포함"""
        
        # 하락반전 전략 필터링
        reversal_strategies = [s for s in self.strategies if s['type'] == 'reversal']
        
        text = """## 🛑 하락 시 손절/방어 전략 (상세)

### 📊 백테스트 기반 하락반전 신호

하락반전 전략은 **과열 상태에서의 하락 전환**을 감지합니다. 아래 전략들의 신호가 발생하면 즉시 대응하세요.

"""
        
        if reversal_strategies:
            # 하락반전 전략 목록 (유사도가 낮은 다양한 전략)
            text += "| 우선순위 | 하락반전 전략 | 승률 | 신호수 | 발동 조건 | 권고 행동 |\n"
            text += "|:--------:|--------------|-----:|:------:|-----------|----------|\n"
            
            for i, s in enumerate(reversal_strategies, 1):
                # 전략명에서 발동 조건 추출
                strategy_name = s['name']
                
                # 승률에 따른 권고 행동
                if s['win_rate'] >= 85:
                    action = "**⚡ 즉시 50% 매도**<br>잔여 분할 청산"
                elif s['win_rate'] >= 80:
                    action = "**🔴 30% 1차 매도**<br>관망 후 추가 매도"
                elif s['win_rate'] >= 75:
                    action = "**⚠️ 20% 방어적 매도**<br>추이 관찰"
                else:
                    action = "**📍 주의 관찰**<br>다른 신호 확인"
                
                # 발동 조건 (전략명 요약)
                condition = self._parse_reversal_condition(strategy_name)
                
                text += f"| **{i}순위** | {strategy_name} | **{s['win_rate']:.1f}%** | {s['signal_count']} | {condition} | {action} |\n"
            
            # 하락반전 신호 해석
            avg_reversal_winrate = sum(s['win_rate'] for s in reversal_strategies) / len(reversal_strategies)
            text += f"""
**💡 하락반전 전략 활용법**
- 평균 승률: **{avg_reversal_winrate:.1f}%** (전체 {len(reversal_strategies)}개 전략)
- 🔴 **2개 이상 동시 발동 시** → 강력 매도 신호, 50% 이상 즉시 청산
- 🟠 **1개 발동 시** → 주의 신호, 20-30% 방어적 매도
- 🟢 **미발동 시** → 상향돌파 전략 기준 유지


"""
        else:
            text += "\n⚠️ **하락반전 전략 미선정**\n\n"
            text += "이번 백테스트에서 조건을 충족하는 하락반전 전략이 발견되지 않았습니다.\n"
            text += "아래 기본 손절 전략을 따르세요.\n\n"
        
        # 각 손절 단계별 하락반전 전략 매핑
        stoploss_strategies = {
            1: reversal_strategies[0]['name'] if len(reversal_strategies) > 0 else "하락반전 전략",
            2: reversal_strategies[1]['name'] if len(reversal_strategies) > 1 else "하락반전 전략",
            3: reversal_strategies[2]['name'] if len(reversal_strategies) > 2 else "하락반전 전략",
        }
        
        # 각 손절 단계별 전략 객체도 저장
        stoploss_strategy_objs = {
            1: reversal_strategies[0] if len(reversal_strategies) > 0 else None,
            2: reversal_strategies[1] if len(reversal_strategies) > 1 else None,
            3: reversal_strategies[2] if len(reversal_strategies) > 2 else None,
        }
        
        # 기본 손절가 테이블
        text += "### 📍 단계별 손절가 기준\n\n"
        text += "| 단계 | 매도<br>비중 | 손절가 | 등락률 | 사용 전략 | 승률 | 상태 | 권고 행동 | 핵심 이유 |\n"
        text += "|:----:|:----:|-------:|:------:|-----------|:----:|:----:|-----------|-----------|\n"
        
        for stage in STOP_LOSS_STAGES:
            target_price = self.current_price * (1 + stage['target_pct'] / 100)
            diff_pct = stage['target_pct']
            
            # 상태 결정 (하락은 아직 안 일어났으므로 대기)
            status = "⏳ **대기**"
            action = f"**{diff_pct:.1f}% 하락시**<br>손절 실행"
            
            # 이유
            reasons = {
                1: "• 초기 하락 시 빠른 대응<br>• 손실 최소화<br>• 추가 하락 대비",
                2: "• 추세 전환 가능성<br>• 주요 지지선 이탈<br>• 리스크 관리 필수",
                3: "• 급락 시 전량 청산<br>• 추가 손실 방지<br>• 저점 매수 기회 대기"
            }
            
            # 사용 전략 포맷팅 (2줄로 표시)
            strategy_text = stoploss_strategies[stage['stage']].replace(' + ', '<br>+ ')
            strategy_obj = stoploss_strategy_objs[stage['stage']]
            strategy_winrate = f"{strategy_obj['win_rate']:.1f}%" if strategy_obj else "N/A"
            
            text += f"| **{stage['stage']}단계**<br>{stage['desc']} | **{stage['ratio']}%** | "
            text += f"**{target_price:,.0f}** | **{diff_pct:.1f}%** | {strategy_text} | **{strategy_winrate}** | {status} | {action} | "
            text += f"{reasons[stage['stage']]} |\n"
        
        # 손절 실행 요약
        text += "\n**⚠️ 손절 실행 원칙**\n"
        text += "- 🔴 **-3% 하락 시** - 30% 1차 손절 (손실 제한)\n"
        text += "- 🔴 **-5% 하락 시** - 30% 2차 손절 (추세 전환 대비)\n"
        text += "- 🔴 **-8% 하락 시** - 40% 전량 손절 (급락 방어)\n"
        text += "- ⚡ **하락반전 신호 발동 시** - 손절가 도달 전에도 선제적 매도 고려\n"
        
        return text
    
    def _parse_breakout_condition(self, strategy_name: str) -> str:
        """전략명에서 상향돌파 발동 조건 요약 추출"""
        conditions = []
        
        if '이격도' in strategy_name:
            # 이격도 수치 추출
            import re
            match = re.search(r'이격도(\d+)', strategy_name)
            if match:
                disp = match.group(1)
                conditions.append(f"이격도 {disp}%+")
        
        if 'RSI' in strategy_name:
            conditions.append("RSI 과열")
        if 'CCI' in strategy_name:
            conditions.append("CCI 상승")
        if 'Stoch' in strategy_name:
            conditions.append("Stoch 과열")
        if 'MFI' in strategy_name:
            conditions.append("MFI 상승")
        if 'ROC' in strategy_name:
            conditions.append("ROC 급등")
        if '거래량' in strategy_name:
            conditions.append("거래량 급증")
        if 'VWAP' in strategy_name:
            conditions.append("VWAP 상승")
        if 'DMI' in strategy_name:
            conditions.append("DMI 강세")
        
        if not conditions:
            return "복합 기술적 지표"
        
        return " + ".join(conditions[:3])  # 최대 3개
    
    def _parse_reversal_condition(self, strategy_name: str) -> str:
        """전략명에서 발동 조건 요약 추출"""
        # 주요 키워드 매핑
        conditions = []
        
        if 'RSI' in strategy_name:
            conditions.append("RSI 과열")
        if 'CCI' in strategy_name:
            conditions.append("CCI 과열")
        if 'MACD데드' in strategy_name:
            conditions.append("MACD 데드크로스")
        if 'Stoch' in strategy_name or 'Stoch데드' in strategy_name:
            conditions.append("Stoch 과열/데드")
        if 'Williams' in strategy_name:
            conditions.append("Williams %R 과매수")
        if 'MFI' in strategy_name:
            conditions.append("MFI 과열")
        if 'BB' in strategy_name:
            conditions.append("BB 상단 터치")
        if '이격도' in strategy_name:
            conditions.append("이격도 과열")
        if 'ADX' in strategy_name:
            conditions.append("추세 강화")
        if '반전' in strategy_name:
            conditions.append("하락 전환")
        if '동시' in strategy_name:
            conditions.append("복합 신호")
        
        if not conditions:
            return "복합 기술적 지표"
        
        return " + ".join(conditions[:3])  # 최대 3개
    
    def _generate_strategy_list_table(self) -> str:
        """전략 목록 표 생성"""
        rows = []
        for i, s in enumerate(self.strategies, 1):
            type_name = "상향돌파" if s['type'] == 'breakout' else "하락반전"
            rows.append(f"| {i} | {s['name']} | {type_name} | {s['win_rate']:.1f}% | {s['signal_count']} |")
        return "\n".join(rows)
    
    def _generate_strategy_details(self) -> str:
        """전략별 상세 분석 생성"""
        text = "## 📋 전략별 신호 상세 분석\n\n"
        text += "각 전략의 매도 신호 발생 시점과 그 이후의 실제 수익률입니다.\n"
        text += "- 🟢 **녹색**: 하락 (매도 성공)\n"
        text += "- 🔴 **빨강**: 상승 (매도 후 추가 상승)\n\n"
        
        for i, strategy in enumerate(self.strategies, 1):
            text += f"### {i}. {strategy['name']}\n\n"
            text += f"**유형**: {self._get_type_name(strategy['type'])} | "
            text += f"**승률**: {strategy['win_rate']:.1f}% | "
            text += f"**신호 수**: {strategy['signal_count']}개\n\n"
            
            # 신호 상세 테이블
            text += "| 매도 신호일 | 당시 지수 | 5일 후 | 10일 후 | 15일 후 | 20일 후 |\n"
            text += "|:----------:|----------:|:------:|:-------:|:-------:|:-------:|\n"
            
            total_5d = []
            total_10d = []
            total_15d = []
            total_20d = []
            
            for fr in strategy['forward_returns']:
                signal_date = fr['signal_date'].strftime('%Y-%m-%d')
                signal_price = fr['signal_price']
                
                ret_5d = fr.get('return_5d')
                ret_10d = fr.get('return_10d')
                ret_15d = fr.get('return_15d')
                ret_20d = fr.get('return_20d')
                
                text += f"| {signal_date} | {signal_price:,.0f} | "
                text += f"{self._format_return(ret_5d)} | "
                text += f"{self._format_return(ret_10d)} | "
                text += f"{self._format_return(ret_15d)} | "
                text += f"{self._format_return(ret_20d)} |\n"
                
                if ret_5d is not None: total_5d.append(ret_5d)
                if ret_10d is not None: total_10d.append(ret_10d)
                if ret_15d is not None: total_15d.append(ret_15d)
                if ret_20d is not None: total_20d.append(ret_20d)
            
            # 평균 행
            avg_5d = sum(total_5d) / len(total_5d) if total_5d else 0
            avg_10d = sum(total_10d) / len(total_10d) if total_10d else 0
            avg_15d = sum(total_15d) / len(total_15d) if total_15d else 0
            avg_20d = sum(total_20d) / len(total_20d) if total_20d else 0
            
            text += f"| **평균** | - | **{avg_5d:+.2f}%** | **{avg_10d:+.2f}%** | "
            text += f"**{avg_15d:+.2f}%** | **{avg_20d:+.2f}%** |\n\n"
            
            # 해석
            if avg_20d < -5:
                text += f"✅ **매우 우수**: 20일 평균 {avg_20d:.2f}% 하락 → 매도 타이밍 매우 적절\n\n"
            elif avg_20d < -2:
                text += f"✅ **우수**: 20일 평균 {avg_20d:.2f}% 하락 → 매도 타이밍 적절\n\n"
            elif avg_20d < 0:
                text += f"⚠️ **양호**: 20일 평균 {avg_20d:.2f}% 하락 → 일부 효과\n\n"
            else:
                text += f"❌ **주의**: 20일 평균 {avg_20d:+.2f}% 상승 → 타이밍 재검토 필요\n\n"
        
        return text
    
    def _format_return(self, ret: float) -> str:
        """수익률 포맷팅 (그린/레드 시그널)"""
        if ret is None:
            return "N/A"
        
        # 하락이 목표이므로: 하락 = 녹색(성공), 상승 = 빨강(실패)
        if ret <= -3:
            return f"🟢 **{ret:+.1f}%**"
        elif ret < 0:
            return f"🟢 {ret:+.1f}%"
        elif ret >= 3:
            return f"🔴 **{ret:+.1f}%**"
        else:
            return f"🔴 {ret:+.1f}%"
    
    def _get_trend_emoji(self) -> str:
        """추세 이모지"""
        emojis = {
            'bull': '📈',
            'sideways': '↔️',
            'bear': '📉'
        }
        return emojis.get(self.trend_type, '❓')
    
    def _get_trend_name(self) -> str:
        """추세명"""
        names = {
            'bull': '상승장 (Bull Market)',
            'sideways': '횡보장 (Sideways)',
            'bear': '하락장 (Bear Market)'
        }
        return names.get(self.trend_type, '알 수 없음')
    
    def _get_type_name(self, strategy_type: str) -> str:
        """전략 유형명"""
        return "상향돌파 매도" if strategy_type == 'breakout' else "하락반전 매도"
    
    def _get_avg_win_rate(self) -> float:
        """평균 승률"""
        if not self.strategies:
            return 0
        return sum(s['win_rate'] for s in self.strategies) / len(self.strategies)


def generate_report(market_name: str, current_price: float,
                   trend_type: str, trend_confidence: int,
                   selected_strategies: List[Dict]) -> str:
    """
    간편 리포트 생성 함수
    
    Returns:
        리포트 파일 경로
    """
    generator = ReportGenerator(
        market_name, current_price,
        trend_type, trend_confidence,
        selected_strategies
    )
    return generator.generate()
