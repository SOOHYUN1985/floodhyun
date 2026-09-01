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

from config import STOP_LOSS_STAGES, DAILY_BACKTEST_DIR as REPORTS_DIR
from portfolio_backtest import simulate_portfolio, format_portfolio_report


class ReportGenerator:
    """리포트 생성기"""
    
    def __init__(self, market_name: str, current_price: float, 
                 trend_type: str, trend_confidence: int,
                 selected_strategies: List[Dict],
                 df: pd.DataFrame = None,
                 ensemble_results: Dict = None,
                 bull_strategies: List[Dict] = None,
                 bull_ensemble_results: Dict = None,
                 future_outlook: Dict = None,
                 sell_dedup_stats: Dict = None,
                 buy_dedup_stats: Dict = None):
        self.market_name = market_name
        self.current_price = current_price
        self.trend_type = trend_type
        self.trend_confidence = trend_confidence
        self.strategies = selected_strategies
        self.df = df
        self.ensemble_results = ensemble_results
        self.bull_strategies = bull_strategies or []
        self.bull_ensemble_results = bull_ensemble_results
        self.future_outlook = future_outlook or {}
        self.sell_dedup_stats = sell_dedup_stats or {}
        self.buy_dedup_stats = buy_dedup_stats or {}
        self.current_date = (
            self.df.index[-1].strftime('%Y-%m-%d')
            if self.df is not None and not self.df.empty
            else datetime.now().strftime('%Y-%m-%d')
        )
    
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

{self._generate_ma_levels_section()}

---

{self._generate_drawdown_section()}

---

{self._generate_technical_signals_section()}

---

## 📊 시장 추세 판단

| 항목 | 결과 |
|------|------|
| **시장 추세** | {self._get_trend_emoji()} **{self._get_trend_name()}** |
| **신뢰도** | {self.trend_confidence}% |
| **적응 전략** | {self.trend_type.upper()} 시장 최적화 |

---

{self._generate_future_outlook_section()}

---

{self._generate_scenario_section()}

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
| **평균 Profit Factor** | {self._get_avg_profit_factor()} |
| **상향돌파 전략** | {sum(1 for s in self.strategies if s['type'] == 'breakout')}개 |
| **하락반전 전략** | {sum(1 for s in self.strategies if s['type'] == 'reversal')}개 |
| **매도 후보 중복 정리** | {self._format_dedup_stats(self.sell_dedup_stats)} |
| **매수 후보 중복 정리** | {self._format_dedup_stats(self.buy_dedup_stats)} |

{self._generate_validation_summary()}

{self._generate_ensemble_analysis()}

{self._generate_risk_metrics_section()}

{self._generate_signal_countdown_section()}

{self._generate_correlation_section()}

{self._generate_portfolio_section()}

{self._generate_direction_summary_section()}

{self._generate_bull_strategies_section()}

{self._generate_return_distribution_section()}

### 선정된 전략 목록

| 순위 | 전략명 | 유형 | 승률 | 레짐승률 | PF | Sharpe | 평균수익 | MFE | 최적보유 | 신호수 | WF창 | MAE |
|:----:|--------|:----:|-----:|:-------:|---:|-------:|--------:|----:|:-------:|:------:|:---:|:---:|
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

    @staticmethod
    def _format_dedup_stats(stats: Dict) -> str:
        if not stats:
            return '정보 없음'
        removed = stats['before'] - stats['after']
        return (
            f"{stats['before']} → {stats['after']}개 ({removed}개 제거: "
            f"완전중복 {stats['exact_removed']}, 유사신호 {stats['similar_removed']})"
        )

    # ──────────────────────────────────────────────────────────
    # 현재 유사국면 기반 미래 흐름
    # ──────────────────────────────────────────────────────────
    def _generate_future_outlook_section(self) -> str:
        """D+1~D+120 유사국면 전망과 워크포워드 신뢰도를 표시한다."""
        outlook = self.future_outlook
        if not outlook.get('available'):
            reason = outlook.get('reason', '분석 결과 없음')
            return f"## 🔭 앞으로의 흐름 전망\n\n> ⚠️ {reason}"

        forecasts = outlook['forecasts']
        by_days = {item['days']: item for item in forecasts}
        validation = outlook.get('validation', {})

        def validation_accuracy(days):
            available_days = [key for key in validation if key <= days]
            key = max(available_days) if available_days else min(validation, default=None)
            return validation[key]['direction_accuracy'] if key is not None else 50.0

        def opportunity_score(item):
            """기간 차이를 보정한 기대수익에서 하방·불확실성을 차감한다."""
            width = item['upper_return'] - item['lower_return']
            downside = abs(min(item['lower_return'], 0))
            supported_upside = max(item['lower_return'], 0) * 0.4
            raw_reward = (
                item['median_return'] + supported_upside
                - downside * 0.8 - width * 0.08
            ) / np.sqrt(max(item['days'], 1))
            confidence = (
                item['up_probability'] / 100
                * (0.5 + validation_accuracy(item['days']) / 200)
            )
            return raw_reward * confidence

        eligible = [
            item for item in forecasts
            if item['days'] >= 5
            and item['median_return'] > 0
            and item['up_probability'] >= 55
            and validation_accuracy(item['days']) >= 50
        ]
        ranked_opportunities = sorted(
            eligible or forecasts,
            key=opportunity_score,
            reverse=True,
        )
        best = ranked_opportunities[0]
        runner_up = ranked_opportunities[1] if len(ranked_opportunities) > 1 else None

        def direction(item):
            probability = item['up_probability']
            median = item['median_return']
            if probability >= 60 and median > 0:
                return '🟢 상승 우세'
            if probability <= 40 and median < 0:
                return '🔴 하락 우세'
            if median >= 0:
                return '🟡 완만한 상승'
            return '🟠 약세/혼조'

        def reliability(days):
            accuracy = validation_accuracy(days)
            if not validation:
                return '검증 부족'
            if accuracy >= 65:
                return f'높음 ({accuracy:.0f}%)'
            if accuracy >= 55:
                return f'보통 ({accuracy:.0f}%)'
            return f'낮음 ({accuracy:.0f}%)'

        key_periods = [(5, '단기'), (20, '1개월'), (60, '3개월'), (120, '6개월')]
        lines = [
            '## 🔭 앞으로의 흐름 전망: 1일~6개월',
            '',
            f"> 현재 MDD·추세·모멘텀·변동성·외국인 수급과 가까운 과거의 **독립 유사국면 {outlook['analog_count']}개**를 비교했습니다.",
            '> 수치는 예언이 아니라 과거 조건부 분포입니다. **중앙값을 기본 경로**, 25~75% 범위를 현실적인 변동 구간으로 봅니다.',
            '',
            f"> ### ⭐⭐⭐ BEST: **{best['label']} 전후**",
            f"> **예상 중심 {best['target_price']:,.0f} · 중앙수익 {best['median_return']:+.1f}% · 상승확률 {best['up_probability']:.0f}%**  ",
            f"> 25~75% 범위 {best['lower_return']:+.1f}%~{best['upper_return']:+.1f}% · 과거 방향검증 {validation_accuracy(best['days']):.0f}%  ",
            '> 기대수익만 가장 큰 구간이 아니라 **기간·하방위험·불확실성·검증 신뢰도를 함께 고려한 최적 구간**입니다.',
            '',
            '### 핵심 시간축 대시보드',
            '',
            '| 구간 | 방향 | 중앙 기대수익 | 예상 지수 | 상승확률 | 과거 검증 |',
            '|:---:|:---:|---:|---:|---:|:---:|',
        ]
        for days, label in key_periods:
            item = by_days[days]
            lines.append(
                f"| **{label}** | {direction(item)} | **{item['median_return']:+.1f}%** | "
                f"**{item['target_price']:,.0f}** | {item['up_probability']:.0f}% | {reliability(days)} |"
            )

        lines.extend([
            '',
            '### 시간축별 예상 경로',
            '',
            '| 추천 | 시점 | 흐름 판정 | 가중 평균 | 중앙값 | 25~75% 범위 | 예상 지수 | 상승확률 |',
            '|:---:|:---:|:---:|---:|---:|:---:|---:|---:|',
        ])
        for item in forecasts:
            if item is best:
                badge = '⭐⭐⭐ **BEST**'
                label = f"⭐ **{item['label']}**"
            elif runner_up is not None and item is runner_up:
                badge = '⭐⭐ 차선'
                label = f"✨ **{item['label']}**"
            else:
                badge = '·'
                label = f"**{item['label']}**"
            lines.append(
                f"| {badge} | {label} | {direction(item)} | {item['mean_return']:+.1f}% | "
                f"**{item['median_return']:+.1f}%** | {item['lower_return']:+.1f}% ~ "
                f"{item['upper_return']:+.1f}% | **{item['target_price']:,.0f}** | "
                f"{item['up_probability']:.0f}% |"
            )

        short = by_days[5]
        month = by_days[20]
        quarter = by_days[60]
        half_year = by_days[120]
        lines.extend([
            '',
            '### 경로 해석과 대응',
            '',
            f"- **향후 1주:** {direction(short)}. 중앙값 {short['median_return']:+.1f}%, "
            f"변동 범위 {short['lower_return']:+.1f}%~{short['upper_return']:+.1f}%로 단기 흔들림을 우선 고려합니다.",
            f"- **향후 1개월:** {direction(month)}. 예상 중심값 {month['target_price']:,.0f}, "
            f"상승확률 {month['up_probability']:.0f}%입니다.",
            f"- **향후 3개월:** {direction(quarter)}. 중앙 경로 {quarter['median_return']:+.1f}%이나 "
            f"하단 시나리오 {quarter['lower_return']:+.1f}%를 손실 관리 기준으로 함께 봅니다.",
            f"- **향후 6개월:** {direction(half_year)}. 장기 분산이 크므로 목표가보다 "
            f"{half_year['lower_return']:+.1f}%~{half_year['upper_return']:+.1f}% 범위를 우선합니다.",
            '',
            '### 과거 워크포워드 검증',
            '',
            '> 각 검증일 당시 알 수 있었던 과거 자료만 사용했습니다. 50% 이하는 방향 판단력이 낮다는 뜻입니다.',
            '',
            '| 검증 시점 | 표본 | 방향 적중률 | 수익률 오차(MAE) | 해석 |',
            '|:---:|---:|---:|---:|:---:|',
        ])
        for days in [5, 20, 60, 120]:
            metric = validation.get(days)
            if not metric:
                continue
            grade = '🟢 유효' if metric['direction_accuracy'] >= 60 else (
                '🟡 참고' if metric['direction_accuracy'] >= 50 else '🔴 낮은 신뢰'
            )
            lines.append(
                f"| D+{days} | {metric['samples']}회 | **{metric['direction_accuracy']:.1f}%** | "
                f"{metric['mae']:.1f}%p | {grade} |"
            )

        lines.extend([
            '',
            '### 가장 가까웠던 과거 국면',
            '',
            '| 순위 | 기준일 | 당시 MDD | 당시 20일 수익률 | 유사거리 |',
            '|:---:|:---:|---:|---:|---:|',
        ])
        for rank, analog in enumerate(outlook['analogs'][:7], 1):
            lines.append(
                f"| {rank} | {analog['date']:%Y-%m-%d} | {analog['mdd']:+.1f}% | "
                f"{analog['ret_20d']:+.1f}% | {analog['distance']:.2f} |"
            )
        lines.extend([
            '',
            f"**방법론:** {outlook['method']}. 후보 시점 이후 120거래일 데이터가 존재하는 경우만 사용하며, 인접 신호는 하나의 국면으로 간주했습니다.",
        ])
        return '\n'.join(lines)
    
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
    
    # ──────────────────────────────────────────────────────────
    # 이동평균 레벨 분석
    # ──────────────────────────────────────────────────────────
    def _generate_ma_levels_section(self) -> str:
        """주요 이동평균 대비 현재 위치 + 지지/저항 레벨"""
        if self.df is None or len(self.df) < 5:
            return ""

        cur = self.df.iloc[-1]
        price = self.current_price
        lines = []
        lines.append("## 📐 이동평균 레벨 & 지지/저항")
        lines.append("")
        lines.append("> 현재 지수와 주요 이동평균의 위치 관계. "
                     "MA 위 = 지지 작용 가능, MA 아래 = 저항으로 전환.")
        lines.append("")

        # ── MA 레벨 테이블
        ma_rows = []
        for period, label in [(10, '단기'), (20, '단기'), (40, '중기'), (60, '중기'),
                               (120, '장기')]:
            col = f'MA{period}'
            val = cur.get(col)
            if val is None or (hasattr(val, '__float__') and pd.isna(float(val))):
                continue
            try:
                val = float(val)
            except Exception:
                continue
            if val <= 0:
                continue
            disp = price / val * 100  # 이격도
            diff_pct = (price - val) / val * 100
            if diff_pct >= 3:
                status = "⬆️ 위"
                signal = "🟢"
            elif diff_pct >= 0:
                status = "↔️ 근접"
                signal = "🟡"
            elif diff_pct >= -3:
                status = "↔️ 근접↓"
                signal = "🟠"
            else:
                status = "⬇️ 아래"
                signal = "🔴"
            ma_rows.append((period, label, val, disp, diff_pct, status, signal))

        if ma_rows:
            lines.append("| MA | 구분 | MA값 | 이격도 | 현재가 대비 | 상태 |")
            lines.append("|:--:|:----:|-----:|:------:|:-----------:|:----:|")
            for period, label, val, disp, diff_pct, status, signal in ma_rows:
                lines.append(
                    f"| **MA{period}** | {label} | {val:,.1f} | {disp:.1f}% | "
                    f"{diff_pct:+.2f}% | {signal} {status} |"
                )
            lines.append("")

        # ── ATR 기반 변동폭 & 지지/저항 밴드
        atr = cur.get('ATR')
        if atr is not None:
            try:
                atr = float(atr)
                atr_pct = atr / price * 100
                lines.append(f"**ATR(14)**: {atr:,.1f}pt ({atr_pct:.2f}%) — "
                              f"일간 기대 변동폭 ±{atr_pct:.1f}%")
                lines.append("")
                lines.append("| 구간 | 지수 | 현재가 대비 |")
                lines.append("|:----:|-----:|:-----------:|")
                for n, label in [(2, '2ATR 상단'), (1, '1ATR 상단'),
                                  (-1, '1ATR 하단'), (-2, '2ATR 하단')]:
                    tgt = price + n * atr
                    pct = n * atr_pct
                    lines.append(f"| {label} | {tgt:,.1f} | {pct:+.1f}% |")
                lines.append("")
            except Exception:
                pass

        # ── +DI / -DI (추세 방향)
        plus_di = cur.get('+DI')
        minus_di = cur.get('-DI')
        adx = cur.get('ADX')
        if plus_di is not None and minus_di is not None:
            try:
                plus_di = float(plus_di)
                minus_di = float(minus_di)
                adx_v = float(adx) if adx is not None else 0
                if plus_di > minus_di:
                    di_signal = "🟢 +DI 우세 (상승 압력)"
                else:
                    di_signal = "🔴 -DI 우세 (하락 압력)"
                lines.append(f"**DMI**: +DI={plus_di:.1f} / -DI={minus_di:.1f} / ADX={adx_v:.1f} → {di_signal}")
                lines.append("")
            except Exception:
                pass

        return "\n".join(lines)

    # ──────────────────────────────────────────────────────────
    # 현재 MDD & 역사적 낙폭 맥락
    # ──────────────────────────────────────────────────────────
    def _generate_drawdown_section(self) -> str:
        """현재 MDD + 역사적 주요 하락 사례 비교"""
        if self.df is None or len(self.df) < 60:
            return ""

        closes = self.df['close'].dropna()
        price = self.current_price

        # 52주 고점 (약 250거래일)
        w52 = closes.tail(250)
        high_52w = float(w52.max())
        dd_52w = (price - high_52w) / high_52w * 100

        # 3년 고점
        w3y = closes.tail(750)
        high_3y = float(w3y.max())
        dd_3y = (price - high_3y) / high_3y * 100

        # 전체 역사적 MDD 계산 (각 날짜에서의 이전 고점 대비)
        roll_max = closes.cummax()
        dd_series = (closes - roll_max) / roll_max * 100  # 음수

        # 현재 낙폭의 역사적 퍼센타일
        current_dd = float(dd_series.iloc[-1])
        pct_rank = (dd_series >= current_dd).mean() * 100  # 현재보다 작은(덜 하락한) 비율
        worse_pct = 100 - pct_rank  # 더 심하게 하락했던 비율

        # 역사적 주요 하락 사례 (MDD -20% 이하)
        historical_crashes = []
        in_crash = False
        crash_start = None
        crash_peak = None
        for date, dd in dd_series.items():
            if not in_crash and dd <= -15:
                in_crash = True
                crash_start = date
                crash_peak = closes.loc[:date].max()
            elif in_crash:
                if dd >= -5:
                    # 회복
                    crash_low_idx = dd_series.loc[crash_start:date].idxmin()
                    crash_low = float(closes.loc[crash_low_idx])
                    max_dd = float(dd_series.loc[crash_start:date].min())
                    # 회복 기간 (거래일)
                    recovery_days = len(closes.loc[crash_low_idx:date])
                    historical_crashes.append({
                        'start': crash_start, 'low_date': crash_low_idx,
                        'max_dd': max_dd, 'recovery_days': recovery_days
                    })
                    in_crash = False

        lines = []
        lines.append("## 📉 현재 낙폭(MDD) 분석")
        lines.append("")

        # 현재 MDD 요약
        dd_52w_str = f"{dd_52w:+.1f}%"
        dd_3y_str = f"{dd_3y:+.1f}%"
        dd_cur_str = f"{current_dd:+.1f}%"

        if current_dd <= -30:
            mdd_grade = "🔴 극단적 하락 (역사적 대형 조정 수준)"
        elif current_dd <= -20:
            mdd_grade = "🟠 심각한 하락 (약세장 진입 수준)"
        elif current_dd <= -10:
            mdd_grade = "🟡 유의미한 조정 (중간 조정 수준)"
        else:
            mdd_grade = "🟢 일반 조정 범위"

        lines.append(f"| 기준 | 고점 | 현재 낙폭 | 등급 |")
        lines.append(f"|:----:|-----:|:--------:|:----:|")
        lines.append(f"| 52주 고점 | {high_52w:,.1f} | **{dd_52w_str}** | {mdd_grade} |")
        lines.append(f"| 3년 고점 | {high_3y:,.1f} | **{dd_3y_str}** | — |")
        lines.append(f"| 전 고점(역사) | {float(closes.max()):,.1f} | **{dd_cur_str}** | — |")
        lines.append("")
        lines.append(f"> 📊 역사적으로 현재 낙폭보다 **더 심하게 하락한 경우**: "
                     f"전체 거래일 중 **{worse_pct:.1f}%**")
        lines.append("")

        # 역사적 주요 하락 사례
        if historical_crashes:
            # 현재 낙폭과 유사한 사례 선별 (-25%~-35% 범위)
            similar = [c for c in historical_crashes
                       if abs(c['max_dd'] - current_dd) <= 15 and c['max_dd'] <= -10]
            if not similar:
                similar = sorted(historical_crashes, key=lambda x: abs(x['max_dd'] - current_dd))[:5]

            lines.append("### 역사적 유사 하락 사례 (낙폭 기준)")
            lines.append("")
            lines.append("| 하락 시작 | 최대 낙폭 | 저점 날짜 | 회복 기간(거래일) |")
            lines.append("|:---------:|:--------:|:---------:|:----------------:|")
            for c in similar[:6]:
                start_str = c['start'].strftime('%Y-%m') if hasattr(c['start'], 'strftime') else str(c['start'])[:7]
                low_str = c['low_date'].strftime('%Y-%m') if hasattr(c['low_date'], 'strftime') else str(c['low_date'])[:7]
                rec = f"{c['recovery_days']}일" if c['recovery_days'] < 9999 else "진행중"
                lines.append(f"| {start_str} | **{c['max_dd']:+.1f}%** | {low_str} | {rec} |")
            lines.append("")

            # 통계 요약
            all_dds = [c['max_dd'] for c in historical_crashes]
            all_recs = [c['recovery_days'] for c in historical_crashes if c['recovery_days'] < 9999]
            if all_recs:
                med_rec = sorted(all_recs)[len(all_recs) // 2]
                lines.append(f"> 💡 역사적 하락 후 평균 회복 기간(중앙값): **{med_rec}거래일** "
                              f"(약 {med_rec // 20}개월)")
                lines.append("")

        return "\n".join(lines)

    # ──────────────────────────────────────────────────────────
    # 기술적 신호 종합 (다이버전스 · BB Squeeze · 거래량)
    # ──────────────────────────────────────────────────────────
    def _generate_technical_signals_section(self) -> str:
        """RSI 다이버전스 · BB Squeeze · 거래량 분석"""
        if self.df is None or len(self.df) < 30:
            return ""

        df = self.df
        cur = df.iloc[-1]
        lines = []
        lines.append("## 🔍 기술적 신호 종합")
        lines.append("")

        signals_found = []

        # ── 1. RSI 다이버전스 (상승 다이버전스 = 강한 매수 신호)
        rsi_series = df['RSI'].dropna()
        close_series = df['close'].dropna()
        if len(rsi_series) >= 30:
            recent = df.tail(30)
            # 최근 30일 내 2개의 저점 탐색
            lows_idx = []
            for i in range(2, len(recent) - 2):
                c = recent['close'].iloc[i]
                if (c < recent['close'].iloc[i-1] and c < recent['close'].iloc[i-2]
                        and c < recent['close'].iloc[i+1] and c < recent['close'].iloc[i+2]):
                    lows_idx.append(i)

            if len(lows_idx) >= 2:
                i1, i2 = lows_idx[-2], lows_idx[-1]
                p1 = float(recent['close'].iloc[i1])
                p2 = float(recent['close'].iloc[i2])
                r1 = float(recent['RSI'].iloc[i1]) if not pd.isna(recent['RSI'].iloc[i1]) else None
                r2 = float(recent['RSI'].iloc[i2]) if not pd.isna(recent['RSI'].iloc[i2]) else None

                if r1 is not None and r2 is not None:
                    if p2 < p1 and r2 > r1:
                        div_type = "🟢 **상승 다이버전스** (가격 저점↓, RSI 저점↑)"
                        div_desc = "가격이 더 낮은 저점을 형성했지만 RSI는 더 높은 저점 → **강한 저점 반전 신호**"
                        signals_found.append(('buy', div_type))
                    elif p2 > p1 and r2 < r1:
                        div_type = "🔴 **하락 다이버전스** (가격 고점↑, RSI 고점↓)"
                        div_desc = "가격이 더 높은 고점을 형성했지만 RSI는 더 낮은 고점 → **하락 전환 경고**"
                        signals_found.append(('sell', div_type))
                    else:
                        div_type = "⚪ 다이버전스 없음"
                        div_desc = "현재 가격과 RSI가 같은 방향으로 움직임."

                    lines.append("### 1️⃣ RSI 다이버전스")
                    lines.append("")
                    lines.append(f"**판정**: {div_type}")
                    lines.append(f"> {div_desc}")
                    lines.append("")
                    lines.append(f"| | 저점 1 | 저점 2 (최근) |")
                    lines.append(f"|---|------:|------------:|")
                    lines.append(f"| 가격 | {p1:,.1f} | {p2:,.1f} |")
                    lines.append(f"| RSI | {r1:.1f} | {r2:.1f} |")
                    lines.append("")

        # ── 2. BB Squeeze (변동성 압축 → 폭발 임박)
        bb_width = cur.get('BB_width')
        if bb_width is not None and not pd.isna(bb_width):
            bb_width = float(bb_width)
            hist_widths = df['BB_width'].dropna().tail(500)
            if len(hist_widths) > 50:
                pct = (hist_widths < bb_width).mean() * 100
                if pct <= 10:
                    squeeze_signal = "🔴 **극단적 수축** (하위 10%) — 대형 변동 임박"
                    signals_found.append(('neutral', 'BB Squeeze'))
                elif pct <= 25:
                    squeeze_signal = "🟡 **수축 구간** (하위 25%) — 변동성 폭발 준비"
                elif pct >= 90:
                    squeeze_signal = "🟢 **극단적 확장** (상위 10%) — 변동성 소진"
                else:
                    squeeze_signal = f"⚪ 보통 수준 ({pct:.0f} 퍼센타일)"
                lines.append("### 2️⃣ 볼린저밴드 Squeeze (변동성)")
                lines.append("")
                lines.append(f"**BB폭**: {bb_width:.2f}% | **역사적 위치**: {pct:.0f} 퍼센타일")
                lines.append(f"**판정**: {squeeze_signal}")
                lines.append("")

        # ── 3. 거래량 분석
        vol_ratio = cur.get('Volume_Ratio')
        volume = cur.get('volume')
        vol_ma20 = cur.get('Volume_MA20')
        if vol_ratio is not None and not pd.isna(vol_ratio):
            vol_ratio = float(vol_ratio)
            if vol_ratio >= 2.5:
                vol_signal = "🔴 **거래량 급증** (평균 대비 2.5배↑) — 강한 방향성 확인 필요"
                signals_found.append(('neutral', '거래량급증'))
            elif vol_ratio >= 1.5:
                vol_signal = "🟡 **거래량 증가** (평균 대비 1.5배↑) — 방향성 주의"
            elif vol_ratio <= 0.5:
                vol_signal = "🟢 **거래량 감소** (평균 대비 0.5배↓) — 관망세"
            else:
                vol_signal = f"⚪ 보통 수준 ({vol_ratio:.1f}배)"

            lines.append("### 3️⃣ 거래량 분석")
            lines.append("")
            lines.append(f"**거래량 비율**: {vol_ratio:.2f}배 (20일 평균 대비)")
            lines.append(f"**판정**: {vol_signal}")

            # 최근 5일 거래량 추이
            recent5 = df[['volume', 'close']].tail(5)
            if len(recent5) >= 3:
                lines.append("")
                lines.append("| 날짜 | 거래량 | 종가 | 등락 |")
                lines.append("|:----:|-------:|-----:|:----:|")
                prev_close = None
                for idx, row in recent5.iterrows():
                    date_str = str(idx)[:10] if hasattr(idx, '__str__') else ""
                    vol_v = row.get('volume', 0)
                    cls_v = row.get('close', 0)
                    chg = ""
                    if prev_close and prev_close > 0:
                        chg_pct = (cls_v - prev_close) / prev_close * 100
                        chg = f"{chg_pct:+.2f}%"
                    prev_close = cls_v
                    try:
                        lines.append(f"| {date_str} | {int(vol_v):,} | {cls_v:,.2f} | {chg} |")
                    except Exception:
                        pass
            lines.append("")

        # ── 4. Stochastic 골든/데드 크로스
        stoch_k = cur.get('Stoch_K')
        stoch_d = cur.get('Stoch_D')
        if stoch_k is not None and stoch_d is not None:
            try:
                stoch_k = float(stoch_k)
                stoch_d = float(stoch_d)
                if len(df) >= 2:
                    prev_k = float(df['Stoch_K'].iloc[-2]) if not pd.isna(df['Stoch_K'].iloc[-2]) else stoch_k
                    prev_d = float(df['Stoch_D'].iloc[-2]) if not pd.isna(df['Stoch_D'].iloc[-2]) else stoch_d
                    if prev_k <= prev_d and stoch_k > stoch_d and stoch_k < 30:
                        st_signal = "🟢 **과매도 골든크로스** (%K가 %D 상향돌파, 30 이하) → 강한 매수 신호"
                        signals_found.append(('buy', 'Stoch골든'))
                    elif prev_k >= prev_d and stoch_k < stoch_d and stoch_k > 70:
                        st_signal = "🔴 **과열 데드크로스** (%K가 %D 하향돌파, 70 이상) → 매도 신호"
                        signals_found.append(('sell', 'Stoch데드'))
                    else:
                        st_signal = f"⚪ 중립 (K={stoch_k:.1f}, D={stoch_d:.1f})"

                    lines.append("### 4️⃣ Stochastic 크로스 신호")
                    lines.append("")
                    lines.append(f"**판정**: {st_signal}")
                    lines.append("")
            except Exception:
                pass

        # ── 종합 신호 요약
        buy_signals = [s[1] for s in signals_found if s[0] == 'buy']
        sell_signals = [s[1] for s in signals_found if s[0] == 'sell']

        lines.append("### 📌 기술적 신호 종합")
        lines.append("")
        if buy_signals:
            lines.append(f"🟢 **매수 신호**: {', '.join(buy_signals)}")
        if sell_signals:
            lines.append(f"🔴 **매도 신호**: {', '.join(sell_signals)}")
        if not buy_signals and not sell_signals:
            lines.append("⚪ 현재 강한 방향성 신호 없음 — 백테스트 전략 조건 대기")
        lines.append("")

        return "\n".join(lines)

    # ──────────────────────────────────────────────────────────
    # 3-시나리오 예상 경로
    # ──────────────────────────────────────────────────────────
    def _generate_scenario_section(self) -> str:
        """강세/기본/약세 3-시나리오 예상 경로 (ATR + MA 기반)"""
        if self.df is None or len(self.df) < 20:
            return ""

        cur = self.df.iloc[-1]
        price = self.current_price

        # ATR 기반 밴드
        atr_raw = cur.get('ATR')
        try:
            atr = float(atr_raw) if atr_raw is not None and not pd.isna(atr_raw) else price * 0.015
        except Exception:
            atr = price * 0.015

        # 주요 MA 레벨
        ma_targets = {}
        for period in [20, 40, 60, 120]:
            col = f'MA{period}'
            v = cur.get(col)
            if v is not None:
                try:
                    v = float(v)
                    if v > 0:
                        ma_targets[period] = v
                except Exception:
                    pass

        # 시나리오 목표가 계산 — 항상 약세 < 현재가 < 기본 < 강세 순서 유지
        # 강세: 현재가 위 MA 중 가장 가까운 것 또는 3ATR
        ma_above = sorted([v for v in ma_targets.values() if v > price])
        ma_below = sorted([v for v in ma_targets.values() if v < price], reverse=True)

        # 강세: 위 MA 중 2번째(여유 있는 목표) or 5ATR
        if len(ma_above) >= 2:
            bull_target = ma_above[1]
        elif len(ma_above) == 1:
            bull_target = ma_above[0]
        else:
            bull_target = price + 5 * atr

        # 기본: 위 MA 중 가장 가까운 것 or 2ATR
        if ma_above:
            base_target = ma_above[0]
        else:
            base_target = price + 2 * atr

        # 강세/기본 같아질 때 강세에 1ATR 더 추가
        if bull_target <= base_target:
            bull_target = base_target + atr

        # 약세: 아래 MA 중 가장 가까운 것 or -3ATR
        recent_lows = self.df['low'].tail(60).dropna()
        if ma_below:
            bear_target = ma_below[0]
        elif len(recent_lows) > 0:
            bear_target = float(recent_lows.min())
        else:
            bear_target = price - 3 * atr

        # 약세가 현재가보다 위라면 -3ATR 강제 적용
        if bear_target >= price:
            bear_target = price - 3 * atr

        def pct(t):
            return (t - price) / price * 100

        # 시장 추세에 따른 시나리오 확률
        if self.trend_type == 'bull':
            p_bull, p_base, p_bear = 50, 35, 15
        elif self.trend_type == 'bear':
            p_bull, p_base, p_bear = 15, 35, 50
        else:
            p_bull, p_base, p_bear = 30, 40, 30

        lines = []
        lines.append("## 🎲 시나리오별 예상 경로")
        lines.append("")
        lines.append(f"*(현재가 {price:,.2f} 기준, ATR={atr:,.1f}pt)*")
        lines.append("")
        lines.append("| 시나리오 | 추세 가중 | 목표 지수 | 현재가 대비 | 조건 | 전략 |")
        lines.append("|:--------:|:----:|----------:|:-----------:|------|------|")

        # 강세
        bull_cond = "MA 돌파 + 외국인 순매수 전환" if self.trend_type == 'bear' else "추세 지속 + 거래량 확인"
        lines.append(
            f"| 🟢 **강세** | {p_bull}% | **{bull_target:,.0f}** | "
            f"{pct(bull_target):+.1f}% | {bull_cond} | 보유 유지 + 목표가 매도 |"
        )

        # 기본
        base_cond = "기술적 반등 후 재조정" if self.trend_type == 'bear' else "현 수준 횡보"
        lines.append(
            f"| 🟡 **기본** | {p_base}% | **{base_target:,.0f}** | "
            f"{pct(base_target):+.1f}% | {base_cond} | 단기 반등 후 관망 |"
        )

        # 약세
        bear_cond = "추가 하락 + 지지선 이탈" if self.trend_type == 'bear' else "하락 반전 + 외국인 이탈"
        lines.append(
            f"| 🔴 **약세** | {p_bear}% | **{bear_target:,.0f}** | "
            f"{pct(bear_target):+.1f}% | {bear_cond} | 손절 원칙 준수 |"
        )

        lines.append("")

        lines.append("> **추세 가중은 통계 확률이 아닙니다.** 현재 이동평균 배열과 추세 강도를 3개 경로에 배분한 위험관리 비중입니다.")
        lines.append("")

        # 현재 추세와 유사국면 전망을 함께 해석
        if self.trend_type == 'bear':
            outlook_20d = next(
                (item for item in self.future_outlook.get('forecasts', []) if item['days'] == 20),
                None,
            )
            if outlook_20d and outlook_20d['median_return'] > 0:
                lines.append(
                    f"> ⚖️ **종합 판정: 하락 추세 속 조건부 반등 구간.** 추세 자체는 약세지만, "
                    f"유사국면은 1개월 중앙값 {outlook_20d['median_return']:+.1f}%·상승확률 "
                    f"{outlook_20d['up_probability']:.0f}%를 가리킵니다. MA20 회복과 외국인 "
                    "순매수 확인 전에는 이를 추세 전환이 아닌 기술적 반등으로 취급합니다."
                )
            else:
                lines.append("> ⚠️ **현재 하락장**: 반등 시 매도 전략, 추가 하락 시 손절 원칙을 지키세요.")
        elif self.trend_type == 'bull':
            lines.append("> ✅ **현재 상승장**: 강세 시나리오가 우세합니다. "
                         "매도 목표가 도달 시 단계적 익절을 실행하세요.")
        else:
            lines.append("> ↔️ **현재 횡보장**: 방향성 돌파 여부를 확인 후 대응하세요.")
        lines.append("")

        return "\n".join(lines)

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
        
        lines = ["## 🎯 지금 해야 할 것", ""]

        # 원라인 행동 지침
        all_trigger_pcts = []
        for s in breakout:
            tp = self._calculate_trigger_price(s)
            if tp is not None:
                all_trigger_pcts.append((tp - self.current_price) / self.current_price * 100)
        n_exceeded = sum(1 for p in all_trigger_pcts if p <= 0)
        n_total = len(all_trigger_pcts)

        if n_total > 0 and n_exceeded == n_total:
            lines.append(f"> 🚨 **매도 목표 전 {n_exceeded}단계 초과 — 보유분 즉시 축소 권장**")
        elif n_exceeded > 0:
            next_pct = min((p for p in all_trigger_pcts if p > 0), default=None)
            if next_pct is not None:
                next_price = self.current_price * (1 + next_pct / 100)
                lines.append(f"> ⚠️ **{n_exceeded}/{n_total}단계 초과 — 초과분 매도 실행, 다음 목표 {next_price:,.0f}(+{next_pct:.1f}%) 대기**")
        elif n_total > 0:
            first_pct = min(all_trigger_pcts)
            first_price = self.current_price * (1 + first_pct / 100)
            lines.append(f"> ✅ **다음 매도 목표 {first_price:,.0f}({first_pct:+.1f}%) 대기**")
        lines.append("")

        lines.append("### 📈 지수가 계속 상승하면?")
        
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
        
        # 이미 초과된 전략과 미래 전략 분리
        exceeded_list = [item for item in diverse_list[:n_stages] if item['pct_change'] <= 0]
        future_list = [item for item in diverse_list[:n_stages] if item['pct_change'] > 0]

        # 초과 전략 경고
        if exceeded_list:
            text += f"\n### 🚨 이미 초과된 매도 목표 ({len(exceeded_list)}개)\n\n"
            text += "> 아래 전략의 목표가가 현재가 이하입니다. **즉시 매도를 검토**하세요.\n\n"
            text += "| 전략 | 목표가 | 초과폭 | 승률 | 틀렸을 때 상승 | 권고 |\n"
            text += "|------|-------:|:------:|:----:|:---:|------|\n"
            for item in exceeded_list:
                s = item['strategy']
                fr = s.get('forward_returns', [])
                wrong_returns = [r['return_20d'] for r in fr if r.get('return_20d') is not None and r['return_20d'] > 0]
                if wrong_returns:
                    wrong_info = f"평균+{np.mean(wrong_returns):.1f}%, 최대+{max(wrong_returns):.1f}%"
                else:
                    wrong_info = "해당없음"
                text += f"| {s['name']} | {item['trigger_price']:,.0f} | {item['pct_change']:+.1f}% | **{s['win_rate']:.1f}%** | {wrong_info} | **즉시 매도** |\n"
            text += "\n"
            text += "> 💡 **승률** = 매도 후 20일 내 하락한 비율. **틀렸을 때 상승** = 매도 신호 후 오히려 상승한 경우의 상승폭\n\n"

        # 미래 단계만 분할매도 표에 표시
        if not future_list:
            text += "\n### ⚠️ 모든 매도 목표가 초과\n\n"
            text += "> 전 단계 목표가가 현재가를 하회합니다. **보유분 즉시 축소를 권장**합니다.\n\n"
            return text

        future_n = len(future_list)
        future_ratios = ratio_map.get(future_n, [100])

        text += """
### 📍 단계별 목표가 및 전략

> 각 전략의 **이격도 조건 x 현재 이동평균값**으로 산출된 실제 발동 목표가입니다.  
> 지수가 목표가에 도달하고 보조지표 조건이 충족되면 전략이 발동됩니다.

| 단계 | 매도<br>비중 | 목표가 | 등락률 | 사용 전략 | 승률 | 상태 | 권고 행동 |
|:----:|:----:|-------:|:------:|-----------|:----:|:----:|-----------|
"""
        
        for i in range(future_n):
            item = future_list[i]
            s = item['strategy']
            trigger_price = item['trigger_price']
            pct_change = item['pct_change']
            ratio = future_ratios[i]
            stage_num = i + 1
            stage_desc = stage_descs.get(stage_num, '추가 익절')
            
            # 상태 결정 (이제 future_list만이므로 pct_change > 0)
            if pct_change < 2:
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
        text += "\n**💡 실행 요약**\n"
        if exceeded_list:
            text += f"- 🔴 **{len(exceeded_list)}개 전략 이미 초과** — 즉시 매도 검토 필요\n"
            for item in exceeded_list:
                text += f"  - {item['strategy']['name']} (목표가 {item['trigger_price']:,.0f}, 현재 {item['pct_change']:+.1f}%)\n"
        near = [item for item in future_list if item['pct_change'] < 5]
        waiting = [item for item in future_list if item['pct_change'] >= 5]
        if near:
            first_near = near[0]
            text += f"- 🎯 **다음 목표가**: {first_near['trigger_price']:,.0f} ({first_near['pct_change']:+.1f}%) → {first_near['strategy']['name']}\n"
        if waiting:
            text += f"- ⏳ **{len(waiting)}개 전략 대기 중** — 추가 상승 시 단계적 청산\n"
        if not exceeded_list and not near:
            text += "- 🟢 **현재 안전 구간** — 매도 신호 없음\n"
        
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
        """전략 목록 표 생성 (MFE·레짐승률·최적보유일·WF창 추가)"""
        rows = []
        for i, s in enumerate(self.strategies, 1):
            type_name = "상향돌파" if s['type'] == 'breakout' else "하락반전"
            win_rate = s.get('win_rate_net', s['win_rate'])
            pf = s.get('profit_factor_net', s.get('profit_factor', 0))
            avg_ret = s.get('avg_return_net', s.get('avg_return', 0))
            pf_str = f"{pf:.1f}" if pf != float('inf') else "∞"

            # 레짐 승률 (현재 시장 국면 한정)
            regime_wr = s.get('regime_win_rate')
            regime_str = f"**{regime_wr:.0f}%**" if regime_wr is not None else "—"

            # Sharpe
            sharpe = s.get('sharpe_ratio', 0)
            sharpe_str = f"{sharpe:.2f}"

            # MFE (최대 유리 이동)
            mfe = s.get('avg_mfe', 0)
            mfe_str = f"{mfe:+.1f}%"

            # 최적 보유일
            opt_d = s.get('optimal_hold_days', 20)
            opt_str = f"D+{opt_d}"

            # WF 윈도우 통과 정보
            wf_windows = s.get('wf_windows', 0)
            wf_pass = s.get('wf_pass_count', None)
            if wf_windows > 0 and wf_pass is not None:
                wf_str = f"{wf_pass}/{wf_windows}"
            elif s.get('oos_win_rate') is not None:
                wf_str = f"{s['oos_win_rate']:.0f}%"
            else:
                wf_str = "N/A"

            # MAE
            mae = s.get('max_adverse', 0)
            mae_str = f"+{mae:.1f}%"

            rows.append(
                f"| {i} | {s['name']} | {type_name} | {win_rate:.1f}% | {regime_str} | {pf_str} | "
                f"{sharpe_str} | {avg_ret:+.1f}% | {mfe_str} | {opt_str} | {s['signal_count']} | "
                f"{wf_str} | {mae_str} |"
            )
        return "\n".join(rows)
    
    def _generate_validation_summary(self) -> str:
        """FDR 보정 및 Walk-Forward 검증 요약"""
        text = "### 🔬 통계 검증 결과\n\n"
        
        # FDR 요약
        fdr_strategies = [s for s in self.strategies if 'p_value' in s]
        if fdr_strategies:
            text += "**다중검정 보정 (Benjamini-Hochberg FDR)**\n\n"
            text += "| 전략 | p-value | FDR 통과 |\n"
            text += "|------|:-------:|:--------:|\n"
            for s in fdr_strategies:
                pv = s.get('p_value', 1.0)
                passed = "✅" if s.get('fdr_significant', False) else "❌"
                text += f"| {s['name']} | {pv:.4f} | {passed} |\n"
            text += "\n> 💡 p-value가 낮을수록 해당 전략의 승률이 우연이 아닐 확률이 높습니다.\n\n"
        
        # Walk-Forward 요약 (롤링 다중 윈도우 정보 포함)
        wf_strategies = [s for s in self.strategies if s.get('oos_win_rate') is not None]
        if wf_strategies:
            text += "**Walk-Forward 검증 (Rolling Multi-Window OOS)**\n\n"
            text += "| 전략 | IS 승률 | OOS 승률(평균) | 하락폭 | WF창 | 검증 |\n"
            text += "|------|:-------:|:--------------:|:------:|:----:|:----:|\n"
            for s in wf_strategies:
                is_wr  = s.get('is_win_rate', s['win_rate'])
                oos_wr = s['oos_win_rate']
                degrad = s.get('wf_degradation', 0)
                wf_n   = s.get('wf_windows', 1)
                wf_p   = s.get('wf_pass_count', None)
                wf_info = f"{wf_p}/{wf_n}" if wf_p is not None else f"1/{wf_n}"
                validated = "✅" if s.get('wf_validated', False) else "⚠️"
                text += (f"| {s['name']} | {is_wr:.0f}% | {oos_wr:.0f}% | "
                         f"{degrad:+.0f}%p | {wf_info} | {validated} |\n")
            text += ("\n> 💡 WF창 = 통과한 롤링 윈도우 수 / 전체 검증 윈도우 수. "
                     "과반 통과 시 ✅ (과적합 위험 낮음)\n\n")
        
        no_oos = [s for s in self.strategies if s.get('oos_win_rate') is None and s.get('oos_count', 0) == 0]
        if no_oos:
            text += f"> ⚠️ {len(no_oos)}개 전략은 검증기간 데이터 부족으로 OOS 검증 불가\n\n"
        
        return text
    
    def _generate_ensemble_analysis(self) -> str:
        """앙상블 투표 백테스트 결과"""
        if not self.ensemble_results:
            return ""
        
        stats = self.ensemble_results.get('stats', {})
        if not stats:
            return ""
        
        best_n = self.ensemble_results['best_n']
        best_wr = self.ensemble_results['best_win_rate']
        
        text = "### 🗳️ 앙상블 투표 백테스트\n\n"
        text += "> 여러 전략이 **동시에 매도 신호**를 발생시킬 때의 과거 성과입니다.\n\n"
        text += "| 동시 발동 수 (N) | 신호 횟수 | 승률 | PF |\n"
        text += "|:----------------:|:---------:|:----:|:---:|\n"
        
        for n in sorted(stats.keys()):
            s = stats[n]
            pf = s['profit_factor']
            pf_str = f"{pf:.1f}" if pf != float('inf') else "∞"
            marker = " ⭐" if n == best_n else ""
            text += f"| **{n}개 이상** | {s['signal_count']}회 | **{s['win_rate']:.1f}%**{marker} | {pf_str} |\n"
        
        text += f"\n> 💡 **최적 N={best_n}** (승률 {best_wr:.1f}%) — {best_n}개 이상 동시 발동 시 가장 높은 승률\n\n"
        
        return text
    
    def _generate_risk_metrics_section(self) -> str:
        """리스크 조정 지표 + Monte Carlo CI + 거래비용 영향 분석"""
        if not self.strategies:
            return ""
        text = "### 🛡️ 리스크 조정 지표\n\n"
        text += "거래비용(0.315%) 차감 후 산출, 부트스트랩 1,000회로 신뢰구간 계산.\n\n"
        text += "| 순위 | 전략 | Gross 승률 | Net 승률 | 95% CI | Sharpe | Sortino | Calmar | Half-Kelly | Inv. WR |\n"
        text += "|:----:|------|:----------:|:--------:|:------:|:------:|:-------:|:------:|:----------:|:-------:|\n"
        
        for i, s in enumerate(self.strategies, 1):
            wr_gross = s.get('win_rate', 0)
            wr_net = s.get('win_rate_net', wr_gross)
            ci = s.get('win_rate_ci', {})
            ci_str = f"{ci.get('lower', 0):.0f}–{ci.get('upper', 0):.0f}%" if ci else "N/A"
            sharpe = s.get('sharpe_ratio', 0)
            sortino = s.get('sortino_ratio', 0)
            sortino_str = f"{sortino:.2f}" if sortino != float('inf') else "∞"
            calmar = s.get('calmar_ratio', 0)
            calmar_str = f"{calmar:.2f}" if calmar != float('inf') else "∞"
            half_k = s.get('half_kelly', 0)
            inv_wr = s.get('inverse_win_rate')
            inv_str = f"{inv_wr:.0f}%" if inv_wr is not None else "N/A"
            inv_flag = "" if s.get('inverse_passed', True) else " ⚠️"
            
            text += (
                f"| {i} | {s['name']} | {wr_gross:.1f}% | {wr_net:.1f}% | {ci_str} | "
                f"{sharpe:.2f} | {sortino_str} | {calmar_str} | {half_k*100:.0f}% | "
                f"{inv_str}{inv_flag} |\n"
            )
        
        text += "\n> 💡 **Sharpe ≥ 1.0** = 우수, **Sortino ≥ 1.5** = 하방위험 잘 통제, "
        text += "**Half-Kelly** = 권장 비중(보수). **Inv. WR**가 45% 이상이면 단순 추세성 신호(⚠️).\n\n"
        return text
    
    def _generate_signal_countdown_section(self) -> str:
        """현재 시점 신호 발생까지 남은 거리 (각 전략별)"""
        if not self.strategies or self.df is None or len(self.df) == 0:
            return ""
        text = "### 📊 현재 신호 카운트다운\n\n"
        text += "각 전략이 매도 신호를 발생시키기까지 현재 지수가 얼마나 떨어져 있는지 표시.\n\n"
        text += "| 전략 | 트리거 조건 | 현재 값 | 신호 임박도 |\n"
        text += "|------|-------------|--------:|:-----------:|\n"
        
        try:
            last = self.df.iloc[-1]
            close = last.get('close', 0)
        except Exception:
            return ""
        
        for s in self.strategies[:10]:  # 상위 10개
            name = s['name']
            stype = s['type']
            
            if stype == 'breakout':
                ma_p = s.get('ma_period', 60)
                disp = s.get('disparity', 110)
                ma_col = f'ma_{ma_p}'
                if ma_col not in self.df.columns:
                    continue
                ma_val = last.get(ma_col)
                if pd.isna(ma_val) or ma_val == 0:
                    continue
                trigger_price = ma_val * (disp / 100)
                cur_disp = (close / ma_val) * 100
                gap_pct = (trigger_price - close) / close * 100
                if gap_pct <= 0:
                    impend = "🔴 발동중"
                elif gap_pct < 2:
                    impend = "🟠 임박(≤2%)"
                elif gap_pct < 5:
                    impend = "🟡 근접(≤5%)"
                else:
                    impend = f"⚪ 여유({gap_pct:+.1f}%)"
                trigger_str = f"이격도 ≥ {disp}% (MA{ma_p})"
                cur_str = f"{cur_disp:.1f}%"
                text += f"| {name} | {trigger_str} | {cur_str} | {impend} |\n"
            else:
                # reversal: 단순 표시
                text += f"| {name} | 하락반전 패턴 | — | (조건 충족 시 발동) |\n"
        
        text += "\n> 💡 🔴=이미 발동, 🟠=2% 이내, 🟡=5% 이내, ⚪=여유 있음\n\n"
        return text
    
    def _generate_correlation_section(self) -> str:
        """선정 전략 간 신호 상관관계 매트릭스"""
        if len(self.strategies) < 2:
            return ""
        text = "### 🔗 전략 간 신호 상관관계\n\n"
        text += "선정 전략들의 매도 신호 일자가 얼마나 겹치는지(Jaccard 유사도).\n\n"
        
        n = min(len(self.strategies), 8)
        strats = self.strategies[:n]
        
        # 헤더
        text += "| | " + " | ".join(f"S{i+1}" for i in range(n)) + " |\n"
        text += "|---|" + "---|" * n + "\n"
        
        sig_sets = []
        for s in strats:
            sigs = set(fr['signal_date'] for fr in s.get('forward_returns', []))
            sig_sets.append(sigs)
        
        for i, s_i in enumerate(strats):
            row = f"| **S{i+1}** "
            for j in range(n):
                if i == j:
                    row += "| — "
                else:
                    a, b = sig_sets[i], sig_sets[j]
                    union = len(a | b)
                    inter = len(a & b)
                    jacc = (inter / union * 100) if union > 0 else 0
                    # 색상 표시
                    if jacc < 20:
                        cell = f"{jacc:.0f}% 🟢"
                    elif jacc < 50:
                        cell = f"{jacc:.0f}% 🟡"
                    else:
                        cell = f"{jacc:.0f}% 🔴"
                    row += f"| {cell} "
            row += "|\n"
            text += row
        
        text += "\n**전략명:** " + " / ".join(f"S{i+1}={strats[i]['name']}" for i in range(n)) + "\n\n"
        text += "> 💡 🟢=독립(<20%), 🟡=중간(<50%), 🔴=중복(≥50%). 🔴 페어는 동일 신호의 다른 표현일 수 있음.\n\n"
        return text
    
    def _generate_portfolio_section(self) -> str:
        """포트폴리오 백테스트 결과 섹션"""
        if self.df is None or not self.strategies:
            return ""
        try:
            result = simulate_portfolio(self.df, self.strategies)
            return format_portfolio_report(result)
        except Exception as e:
            return f"<!-- 포트폴리오 백테스트 실패: {e} -->\n"
    
    def _generate_direction_summary_section(self) -> str:
        """방향성 종합 판단 — 매도/매수 신호 동시 검토"""
        sell_n = len(self.strategies)
        buy_n = len(self.bull_strategies)
        if sell_n == 0 and buy_n == 0:
            return ""
        
        # 평균 승률 (매도/매수)
        def _avg(items, key='win_rate'):
            vals = [s.get(key, 0) for s in items if s.get(key) is not None]
            return sum(vals) / len(vals) if vals else 0
        
        sell_wr = _avg(self.strategies)
        buy_wr = _avg(self.bull_strategies)
        
        # 예상 평균 수익률 (가공)
        sell_avg = _avg(self.strategies, 'avg_return')
        buy_avg = _avg(self.bull_strategies, 'avg_return')
        
        # 신호 임박도 — 매도 측 (이미 발동 + 5%이내)
        sell_imminent = 0
        if self.df is not None:
            for s in self.strategies:
                tp = self._calc_trigger_price_simple(s)
                if tp is not None:
                    gap = (tp - self.current_price) / self.current_price * 100
                    if gap <= 5:
                        sell_imminent += 1
        
        text = "### 🎯 종합 방향성 판단 (상승 vs 하락)\n\n"
        text += "현재 시장의 매도 신호와 매수 신호를 동시에 검토하여 향후 방향을 가늠합니다.\n\n"
        text += "| 방향 | 발견 전략 수 | 평균 승률 | 평균 예상 변동 | 임박 신호 |\n"
        text += "|:----:|:----------:|:--------:|:--------------:|:--------:|\n"
        text += f"| 🔴 **하락** (매도 신호) | {sell_n}개 | {sell_wr:.1f}% | {sell_avg:+.2f}% | {sell_imminent}개 |\n"
        text += f"| 🟢 **상승** (매수 신호) | {buy_n}개 | {buy_wr:.1f}% | {buy_avg:+.2f}% | — |\n\n"
        
        # 종합 판정
        verdict = self._direction_verdict(sell_n, buy_n, sell_wr, buy_wr, sell_imminent)
        text += f"> {verdict}\n\n"
        return text
    
    def _direction_verdict(self, sell_n, buy_n, sell_wr, buy_wr, sell_imminent) -> str:
        """방향성 종합 판정 문구"""
        if sell_n == 0 and buy_n == 0:
            return "🟡 명확한 신호 없음 — 관망 권장"
        sell_strength = sell_n * (sell_wr / 100) * (1 + sell_imminent * 0.3)
        buy_strength = buy_n * (buy_wr / 100)
        
        if sell_imminent > 0 and sell_strength > buy_strength * 1.5:
            return f"🔴 **하락 우세** — 매도 신호 {sell_imminent}개 임박, 보유분 단계적 축소 권장"
        elif sell_strength > buy_strength * 1.2:
            return f"🟠 **약한 하락** — 추가 매수 자제, 보유분 일부 익절 고려"
        elif buy_strength > sell_strength * 1.5:
            return f"🟢 **상승 우세** — 매수 신호 우위, 분할 매수 기회"
        elif buy_strength > sell_strength * 1.2:
            return f"🟡 **약한 상승** — 분할 매수 검토, 신중 진입"
        else:
            return f"⚪ **방향 혼조** — 양방향 신호 균형, 관망 권장"
    
    def _calc_trigger_price_simple(self, s) -> float:
        """전략 트리거가 단순 계산"""
        if s.get('type') not in ['breakout', 'breakdown']:
            return None
        if self.df is None or s.get('ma_period') is None or s.get('disparity') is None:
            return None
        try:
            ma_col = f'MA{int(s["ma_period"])}'
            if ma_col not in self.df.columns:
                return None
            ma_val = self.df[ma_col].iloc[-1]
            if pd.isna(ma_val) or ma_val == 0:
                return None
            return float(ma_val * (s['disparity'] / 100))
        except Exception:
            return None
    
    def _generate_bull_strategies_section(self) -> str:
        """매수 전략 (저점 판독) 섹션"""
        if not self.bull_strategies:
            return ""
        text = "### 🟢 매수 전략 (저점 판독)\n\n"
        text += "저점 후 상승 패턴에 기반한 매수 신호 전략입니다.\n\n"
        text += "| 순위 | 전략명 | 유형 | 승률 | PF | Sharpe | Kelly | 평균상승 | 신호수 | OOS승률 | MAE |\n"
        text += "|:----:|--------|:----:|-----:|---:|-------:|-----:|--------:|:------:|:-------:|:---:|\n"
        for i, s in enumerate(self.bull_strategies, 1):
            type_name = "하향이격" if s['type'] == 'breakdown' else "저점반전"
            wr = s.get('win_rate_net', s['win_rate'])
            pf = s.get('profit_factor_net', s.get('profit_factor', 0))
            pf_str = f"{pf:.1f}" if pf != float('inf') else "∞"
            avg = s.get('avg_return_net', s.get('avg_return', 0))
            sharpe = s.get('sharpe_ratio', 0)
            half_k = s.get('half_kelly', 0)
            mae = s.get('max_adverse', 0)
            oos_wr = s.get('oos_win_rate')
            oos_str = f"{oos_wr:.0f}%" if oos_wr is not None else "N/A"
            text += (
                f"| {i} | {s['name']} | {type_name} | {wr:.1f}% | {pf_str} | "
                f"{sharpe:.2f} | {half_k*100:.0f}% | {avg:+.1f}% | {s['signal_count']} | "
                f"{oos_str} | -{mae:.1f}% |"
                "\n"
            )
        text += "\n> 💡 매수 신호 발동 시 Half-Kelly 비중만큼 분할 매수 검토. MAE는 최대 추가 하락폭.\n\n"
        return text
    
    def _generate_return_distribution_section(self) -> str:
        """수익률 분포 (분위수) 섹션 — 변동 폭 예측"""
        if not self.strategies and not self.bull_strategies:
            return ""
        text = "### 📐 신호 발동 시 변동 폭 분포 (20일 기준)\n\n"
        text += "각 전략의 과거 신호 발동 후 20일 수익률 분포로, **현재 시점에서 비슷한 신호가 발동될 경우의 예상 범위**를 제공합니다.\n\n"
        
        def _add_table(items, label, direction_arrow):
            t = f"**{label}**\n\n"
            t += "| 전략 | 5%분위 (최악) | 25%분위 | 중앙값 | 75%분위 | 95%분위 (최선) | 표준편차 |\n"
            t += "|------|:------------:|:-------:|:------:|:-------:|:--------------:|:--------:|\n"
            for s in items[:6]:
                d = s.get('return_distribution', {})
                if not d:
                    continue
                t += (
                    f"| {s['name']} | {d.get('p5',0):+.1f}% | {d.get('p25',0):+.1f}% | "
                    f"**{d.get('median',0):+.1f}%** | {d.get('p75',0):+.1f}% | {d.get('p95',0):+.1f}% | "
                    f"{d.get('std',0):.1f}%p |\n"
                )
            return t + "\n"
        
        if self.strategies:
            text += _add_table(self.strategies, "🔴 매도 신호 (음수일수록 좋음)", "↓")
        if self.bull_strategies:
            text += _add_table(self.bull_strategies, "🟢 매수 신호 (양수일수록 좋음)", "↑")
        
        # Forward days별 분포 (Top 1 전략만)
        if self.strategies:
            top = self.strategies[0]
            mh = top.get('multi_horizon_distribution', {})
            if mh:
                text += f"**🔍 [{top['name']}] 기간별 수익률 분포**\n\n"
                text += "| 기간 | 평균 | 5% | 25% | 중앙값 | 75% | 95% |\n"
                text += "|:----:|-----:|----:|----:|------:|----:|----:|\n"
                for days in ['5d', '10d', '15d', '20d']:
                    d = mh.get(days, {})
                    if d:
                        text += (
                            f"| {days} | {d.get('mean',0):+.2f}% | {d.get('p5',0):+.1f}% | "
                            f"{d.get('p25',0):+.1f}% | **{d.get('median',0):+.1f}%** | "
                            f"{d.get('p75',0):+.1f}% | {d.get('p95',0):+.1f}% |\n"
                        )
                text += "\n"
        
        text += "> 💡 **중앙값(50%분위)** = 가장 가능성 높은 결과. **5%-95% 구간** = 90% 신뢰구간. 표준편차가 클수록 변동성 높음.\n\n"
        return text
    
    def _generate_strategy_details(self) -> str:
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

    def _get_avg_profit_factor(self) -> str:
        """평균 Profit Factor"""
        if not self.strategies:
            return "N/A"
        pfs = [min(s.get('profit_factor', 1.0), 99) for s in self.strategies]
        avg_pf = sum(pfs) / len(pfs)
        return f"{avg_pf:.1f}"


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
