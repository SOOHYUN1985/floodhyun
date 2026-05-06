"""
코스피 MDD 기반 담보대출 전략 계산기
- 현재 코스피 MDD 상태 확인
- MDD 구간별 담보대출 투자 전략 시뮬레이션
- 담보비율 계산 및 청산 위험도 평가
- 역사적 위기 시뮬레이션 (IMF, 금융위기, 코로나)
"""

import os
import sys
import numpy as np
import pandas as pd
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from config import DB_PATH
from data_loader import DataLoader

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 설정
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LIQUIDATION_RATIO = 140   # 강제 청산 기준 (%)
SAFE_RATIO = 300          # 안전 기준 (%)
MDD_STEPS = [-15, -20, -25, -30, -35, -40]  # 투자 단계별 MDD

# 전략 옵션 (각 단계당 초기자본 대비 %)
STRATEGIES = {
    "옵션1_균형형": {
        "desc": "8% × 4단계 (MDD -30%까지)",
        "steps": [(-15, 8), (-20, 8), (-25, 8), (-30, 8)],
    },
    "옵션2_보수형": {
        "desc": "10% × 3단계 (MDD -25%까지)",
        "steps": [(-15, 10), (-20, 10), (-25, 10)],
    },
    "옵션3_공격형": {
        "desc": "6~4% × 6단계 (MDD -40%까지)",
        "steps": [(-15, 6), (-20, 6), (-25, 6), (-30, 6), (-35, 5), (-40, 4)],
    },
    "옵션4_최강안전": {
        "desc": "4% × 6단계 (MDD -40%까지, IMF 대비)",
        "steps": [(-15, 4), (-20, 4), (-25, 4), (-30, 4), (-35, 4), (-40, 4)],
    },
    "옵션5_피라미드": {
        "desc": "8~1% × 8단계 (MDD -50%까지, 중반집중)",
        "steps": [(-15, 8), (-20, 14), (-25, 12), (-30, 8), (-35, 5), (-40, 3), (-45, 2), (-50, 1)],
        "recommended": True,
    },
    "옵션6_피라미드개선": {
        "desc": "5~1% × 8단계 (MDD -50%까지, 비중축소)",
        "steps": [(-15, 5), (-20, 9), (-25, 8), (-30, 5), (-35, 3), (-40, 2), (-45, 1), (-50, 1)],
    },
}

# 역사적 위기 시나리오
CRISIS_SCENARIOS = [
    ("코로나 (2020)", -43.9),
    ("글로벌 금융위기 (2008)", -54.5),
    ("IMF 외환위기 (1997)", -64.7),
]


def calc_collateral_ratio(initial, investments, current_mdd):
    """
    현재 MDD에서의 담보비율 계산

    Args:
        initial: 초기 투자금 (100 기준)
        investments: [(투자시점MDD%, 투자비율%), ...] - 이미 실행된 투자들
        current_mdd: 현재 MDD (%)
    Returns:
        (담보가치, 총대출금, 담보비율)
    """
    current_index = 100 + current_mdd  # MDD -30% → 지수 70

    # 초기 자산 가치
    portfolio_value = initial * (current_index / 100)

    # 각 투자 단계의 현재 가치
    total_loan = 0
    for entry_mdd, pct in investments:
        entry_index = 100 + entry_mdd  # 투자 시점 지수
        invest_amount = initial * pct / 100
        total_loan += invest_amount
        portfolio_value += invest_amount * (current_index / entry_index)

    if total_loan == 0:
        return portfolio_value, 0, float('inf')

    ratio = portfolio_value / total_loan * 100
    return portfolio_value, total_loan, ratio


def simulate_strategy(strategy, initial=100):
    """전략별 MDD 구간에서의 담보비율 계산"""
    results = []
    steps = strategy["steps"]

    for i, (mdd, pct) in enumerate(steps):
        # 이 단계까지 실행된 투자들
        executed = steps[:i + 1]
        portfolio, loan, ratio = calc_collateral_ratio(initial, executed, mdd)
        results.append({
            "step": i + 1,
            "mdd": mdd,
            "pct": pct,
            "invest": initial * pct / 100,
            "cum_loan": sum(initial * p / 100 for _, p in executed),
            "portfolio": portfolio,
            "ratio": ratio,
        })

    return results


def simulate_crisis(strategy, crisis_mdd, initial=100):
    """역사적 위기 시나리오에서의 담보비율 계산"""
    steps = strategy["steps"]
    # 위기 MDD보다 얕은 단계만 실행됨
    executed = [(m, p) for m, p in steps if m >= crisis_mdd]
    if not executed:
        executed = steps  # 모든 단계 실행

    portfolio, loan, ratio = calc_collateral_ratio(initial, executed, crisis_mdd)
    return portfolio, loan, ratio


def get_mdd_history(df):
    """역사적 MDD 에피소드 추출"""
    df = df.copy()
    df['cummax'] = df['close'].cummax()
    df['mdd'] = (df['close'] / df['cummax'] - 1) * 100

    episodes = []
    threshold_mdds = [-15, -20, -25, -30, -35, -40, -50]

    for threshold in threshold_mdds:
        mask = df['mdd'] <= threshold
        if mask.any():
            # 처음 도달한 날들 (각 에피소드)
            first_days = df[mask].index
            count = 0
            last_date = None
            for d in first_days:
                if last_date is None or (d - last_date).days > 60:
                    count += 1
                    last_date = d

            # 최근 도달일
            last_hit = first_days[-1]
            episodes.append({
                "mdd": threshold,
                "episodes": count,
                "last_hit": last_hit.strftime("%Y-%m-%d"),
                "total_days": mask.sum(),
            })

    return episodes


def generate_report(df, initial_capital=1_000_000):
    """담보대출 전략 리포트 생성"""
    # 현재 상태 계산
    current_price = df['close'].iloc[-1]
    ath = df['close'].max()
    ath_date = df['close'].idxmax().strftime("%Y-%m-%d")
    current_mdd = (current_price / ath - 1) * 100

    # MDD 에피소드 히스토리
    mdd_episodes = get_mdd_history(df)

    # 리포트 시작
    report_date = datetime.now().strftime('%Y%m%d_%H%M%S')
    from config import WEEKLY_RESEARCH_DIR
    os.makedirs(WEEKLY_RESEARCH_DIR, exist_ok=True)
    filename = os.path.join(WEEKLY_RESEARCH_DIR, f"담보대출_전략_{report_date}.md")

    scale = initial_capital / 100  # 100만원 기준 → 실제 금액 변환

    with open(filename, 'w', encoding='utf-8') as f:
        f.write("# 💰 코스피 MDD 기반 담보대출 전략 계산기\n\n")
        f.write(f"**생성일시**: {datetime.now().strftime('%Y년 %m월 %d일 %H:%M')}\n")
        f.write(f"**초기 투자금**: {initial_capital:,.0f}원 기준\n\n")

        # 최우선 추천 배너
        rec_name = None
        rec_strategy = None
        for n, s in STRATEGIES.items():
            if s.get('recommended'):
                rec_name = n
                rec_strategy = s
                break
        if rec_name:
            rec_display = rec_name.replace('_', ' ')
            rec_results = simulate_strategy(rec_strategy)
            rec_total_pct = sum(p for _, p in rec_strategy['steps'])
            rec_crisis = []
            for cn, cm in CRISIS_SCENARIOS:
                _, _, ratio = simulate_crisis(rec_strategy, cm)
                emoji = "✅" if ratio >= SAFE_RATIO else ("⚠️" if ratio >= LIQUIDATION_RATIO else "❌")
                rec_crisis.append(f"{cn}: {emoji} {ratio:.0f}%")
            f.write("> ## ⭐ 최우선 추천: " + rec_display + "\n>\n")
            f.write(f"> **{rec_strategy['desc']}** | 총 투자 비중: **{rec_total_pct}%**\n>\n")
            f.write("> **핵심 강점**: 자주 발생하는 MDD -20~25% 구간에 화력 집중 (14%, 12%), "
                    "8단계 분산으로 MDD -50%까지 커버\n>\n")
            f.write(f"> 위기 시뮬레이션: {' | '.join(rec_crisis)}\n\n")

        f.write("---\n\n")

        # ── 현재 코스피 상태 ──
        f.write("## 📊 현재 코스피 상태\n\n")
        f.write("| 항목 | 값 |\n")
        f.write("|:----:|:---|\n")
        f.write(f"| 현재 코스피 | **{current_price:,.2f}** |\n")
        f.write(f"| 역대 고점 | {ath:,.2f} ({ath_date}) |\n")
        f.write(f"| 현재 MDD | **{current_mdd:.1f}%** |\n")

        # 현재 MDD에서 다음 투자 단계 판단
        next_step = None
        for mdd in [-15, -20, -25, -30, -35, -40]:
            if current_mdd > mdd:
                next_step = mdd
                break
        if next_step:
            f.write(f"| 다음 투자 단계 | MDD {next_step}% (코스피 {ath * (1 + next_step / 100):,.0f}) |\n")
            gap = next_step - current_mdd
            f.write(f"| 다음 단계까지 | **{abs(gap):.1f}%p 추가 하락 필요** |\n")
        else:
            # 이미 어떤 단계에 진입
            passed = [m for m in [-15, -20, -25, -30, -35, -40] if current_mdd <= m]
            if passed:
                f.write(f"| 진입 구간 | **MDD {passed[-1]}% 구간 진입 중** ⚠️ |\n")
            else:
                f.write(f"| 상태 | 아직 MDD -15% 미달 (투자 대기) |\n")
        f.write("\n")

        # ── 전제 조건 ──
        f.write("## ⚙️ 전제 조건\n\n")
        f.write(f"- 초기 투자금: **{initial_capital:,.0f}원** (지수 고점 근처에서 투자)\n")
        f.write(f"- MDD -15%부터 단계적 담보대출 투자 시작\n")
        f.write(f"- **담보비율 {SAFE_RATIO}% 이상 유지** (안전 기준)\n")
        f.write(f"- **담보비율 {LIQUIDATION_RATIO}% 미만 시 강제 청산** (절대 라인)\n\n")
        f.write("---\n\n")

        # ── MDD 발생 빈도 ──
        f.write("## 📅 역사적 MDD 발생 빈도\n\n")
        data_years = (df.index[-1] - df.index[0]).days / 365.25
        f.write(f"**데이터 기간**: {df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')} ({data_years:.0f}년)\n\n")
        f.write("| MDD 구간 | 발생 횟수 | 주기 | 마지막 발생 | 총 해당 일수 |\n")
        f.write("|:--------:|:--------:|:----:|:----------:|:----------:|\n")
        for ep in mdd_episodes:
            freq = f"{data_years / ep['episodes']:.1f}년" if ep['episodes'] > 0 else "-"
            f.write(f"| {ep['mdd']}% | {ep['episodes']}회 | ~{freq} | {ep['last_hit']} | {ep['total_days']:,}일 |\n")
        f.write("\n")

        # ── 전략별 상세 비교 ──
        f.write("---\n\n")
        f.write("## 📋 전략별 상세 비교\n\n")

        for name, strategy in STRATEGIES.items():
            display_name = name.replace("_", " ")
            is_rec = strategy.get('recommended', False)
            if is_rec:
                f.write(f"### ⭐ {display_name}: {strategy['desc']} — 최우선 추천\n\n")
            else:
                f.write(f"### {display_name}: {strategy['desc']}\n\n")

            results = simulate_strategy(strategy)

            f.write("| 단계 | MDD | 추가 투자 | 초기자본 대비 | 누적 대출 | 담보비율 | 위험도 |\n")
            f.write("|:---:|:---:|:--------:|:----------:|:--------:|:------:|:-----:|\n")

            for r in results:
                invest_str = f"{r['invest'] * scale:,.0f}원"
                loan_str = f"{r['cum_loan'] * scale:,.0f}원"

                if r['ratio'] >= SAFE_RATIO:
                    risk = "✅ 안전"
                elif r['ratio'] >= LIQUIDATION_RATIO:
                    risk = "⚠️ 위험"
                else:
                    risk = "❌ 청산"

                f.write(f"| {r['step']}차 | {r['mdd']}% | {invest_str} | {r['pct']}% "
                        f"| {loan_str} | **{r['ratio']:.0f}%** | {risk} |\n")
            f.write("\n")

            # 위기 시뮬레이션
            f.write("**역사적 위기 시뮬레이션:**\n\n")
            f.write("| 위기 | MDD | 담보가치 | 대출금 | 담보비율 | 결과 |\n")
            f.write("|:----:|:---:|:-------:|:-----:|:------:|:----:|\n")

            for crisis_name, crisis_mdd in CRISIS_SCENARIOS:
                portfolio, loan, ratio = simulate_crisis(strategy, crisis_mdd)
                portfolio_str = f"{portfolio * scale:,.0f}원"
                loan_str = f"{loan * scale:,.0f}원"

                if ratio >= SAFE_RATIO:
                    result = "✅ 안전"
                elif ratio >= LIQUIDATION_RATIO:
                    result = "⚠️ 생존(위험)"
                else:
                    result = "❌ **청산!**"

                f.write(f"| {crisis_name} | {crisis_mdd}% | {portfolio_str} | {loan_str} | **{ratio:.0f}%** | {result} |\n")
            f.write("\n---\n\n")

        # ── 전략 요약 비교표 ──
        f.write("## 🎯 전략 요약 비교\n\n")
        f.write("| 전략 | 단계별 비중 | 총 대출액 | 초기자본 대비 | 커버 범위 | 담보비율(최종) |")
        for cn, cm in CRISIS_SCENARIOS:
            short = cn.split(" ")[0]
            f.write(f" {short} |")
        f.write("\n")
        f.write("|:----:|:--------:|:-------:|:----------:|:--------:|:------------:|")
        for _ in CRISIS_SCENARIOS:
            f.write(":--------:|")
        f.write("\n")

        for name, strategy in STRATEGIES.items():
            display_name = name.replace("_", " ")
            is_rec = strategy.get('recommended', False)
            results = simulate_strategy(strategy)
            last = results[-1]

            steps_desc = strategy['desc'].split('(')[0].strip()
            total_loan = f"{last['cum_loan'] * scale:,.0f}원"
            total_pct = sum(p for _, p in strategy['steps'])
            cover_mdd = strategy['steps'][-1][0]

            label = f"⭐ **{display_name}**" if is_rec else f"**{display_name}**"
            f.write(f"| {label} | {steps_desc} | {total_loan} | {total_pct}% | MDD {cover_mdd}% | {last['ratio']:.0f}% |")

            for cn, cm in CRISIS_SCENARIOS:
                _, _, ratio = simulate_crisis(strategy, cm)
                if ratio >= SAFE_RATIO:
                    emoji = "✅"
                elif ratio >= LIQUIDATION_RATIO:
                    emoji = "⚠️"
                else:
                    emoji = "❌"
                f.write(f" {emoji} {ratio:.0f}% |")
            f.write("\n")
        f.write("\n")

        # ── 현재 상황 기반 추천 ──
        f.write("---\n\n")
        f.write("## 💡 현재 상황 기반 조언\n\n")

        if current_mdd > -10:
            f.write(f"현재 MDD **{current_mdd:.1f}%**로, 아직 투자 대기 구간입니다.\n\n")
            f.write(f"- 첫 투자 시작점(MDD -15%)까지 코스피가 **{ath * 0.85:,.0f}**까지 하락해야 합니다\n")
            f.write(f"- 현재 코스피 {current_price:,.0f}에서 **{(current_price - ath * 0.85) / current_price * 100:.1f}% 추가 하락** 필요\n")
            f.write(f"- 지금은 **현금 비중을 확보**하고 대기하세요\n\n")
        elif current_mdd > -15:
            gap_to_15 = -15 - current_mdd
            f.write(f"현재 MDD **{current_mdd:.1f}%**로, 첫 투자 시작점(-15%)에 근접합니다.\n\n")
            f.write(f"- MDD -15% 도달 가격: **{ath * 0.85:,.0f}** (현재 대비 {abs(gap_to_15):.1f}%p 추가 하락)\n")
            f.write(f"- 전략을 미리 선택하고, 현금을 준비하세요\n\n")
        else:
            # 이미 MDD -15% 이하
            passed_steps = [m for m in [-15, -20, -25, -30, -35, -40] if current_mdd <= m]
            f.write(f"⚠️ 현재 MDD **{current_mdd:.1f}%**로, 투자 구간에 진입했습니다!\n\n")
            f.write(f"- **이미 통과한 단계**: {', '.join(f'MDD {m}%' for m in passed_steps)}\n")

            # 각 전략별 현재 상황
            f.write(f"\n### 각 전략별 현재 담보비율\n\n")
            f.write("| 전략 | 실행된 단계 | 투자 총액 | 현재 담보비율 | 상태 |\n")
            f.write("|:----:|:--------:|:-------:|:----------:|:----:|\n")
            for name, strategy in STRATEGIES.items():
                executed = [(m, p) for m, p in strategy['steps'] if current_mdd <= m]
                if executed:
                    portfolio, loan, ratio = calc_collateral_ratio(100, executed, current_mdd)
                    total_invest = sum(p for _, p in executed) * scale
                    risk = "✅" if ratio >= SAFE_RATIO else ("⚠️" if ratio >= LIQUIDATION_RATIO else "❌")
                    f.write(f"| {name.replace('_', ' ')} | {len(executed)}단계 | {total_invest:,.0f}원 | {ratio:.0f}% | {risk} |\n")
                else:
                    f.write(f"| {name.replace('_', ' ')} | 미진입 | - | - | 대기 |\n")
            f.write("\n")

        # ── 실전 금액표 ──
        f.write("---\n\n")
        f.write("## 📊 실전 투자 금액표\n\n")
        f.write(f"**초기 투자금 {initial_capital:,.0f}원 기준**\n\n")

        for name, strategy in STRATEGIES.items():
            display_name = name.replace("_", " ")
            f.write(f"### {display_name}\n\n")
            f.write("| 단계 | MDD | 코스피 도달가 | 투자금액 | 누적 대출 |\n")
            f.write("|:---:|:---:|:-----------:|:-------:|:--------:|\n")

            cum = 0
            for mdd, pct in strategy['steps']:
                target_price = ath * (1 + mdd / 100)
                invest = initial_capital * pct / 100
                cum += invest
                f.write(f"| MDD {mdd}% | {mdd}% | {target_price:,.0f} | **{invest:,.0f}원** | {cum:,.0f}원 |\n")
            f.write("\n")

        # ── 최우선 추천 상세 분석 ──
        if rec_name and rec_strategy:
            f.write("---\n\n")
            f.write("## ⭐ 최우선 추천 전략 상세 분석\n\n")
            rec_display = rec_name.replace('_', ' ')
            f.write(f"### 왜 {rec_display}인가?\n\n")
            f.write("**1. 빈도 기반 최적 배분**\n")
            f.write("- MDD -20~25%는 역사적으로 가장 자주 발생하는 유의미한 조정 구간\n")
            f.write("- 이 구간에 14%, 12%로 화력을 집중 → 가장 높은 투자 기대값\n")
            f.write("- MDD -30% 이상의 대폭락은 발생 빈도가 극히 낮음\n\n")
            f.write("**2. 8단계 分散의 강점**\n")
            f.write("- 4~6단계 전략들보다 정밀한 대응 가능\n")
            f.write("- MDD -50%까지 커버하여 글로벌 금융위기급에도 대응\n")
            f.write("- 깊은 하락 구간(-35~50%)에서는 소량만 투자(5→3→2→1%)하여 리스크 제한\n\n")
            f.write("**3. 수익 극대화**\n")
            rec_total = sum(p for _, p in rec_strategy['steps'])
            f.write(f"- 총 투자 비중 {rec_total}%로 다른 전략 대비 가장 높은 투자 규모\n")
            f.write("- 반등 시 수익도 압도적 (더 많이 투자했으므로 더 많이 회복)\n")
            f.write("- 중반 집중 구조로 평균 매수단가가 유리\n\n")
            f.write("**4. 위기 생존 검증 (청산 기준 140%)**\n\n")
            f.write("| 위기 시나리오 | MDD | 담보비율 | 청산까지 여유 | 판정 |\n")
            f.write("|:----------:|:---:|:------:|:----------:|:----:|\n")
            for cn, cm in CRISIS_SCENARIOS:
                _, _, ratio = simulate_crisis(rec_strategy, cm)
                margin = ratio - LIQUIDATION_RATIO
                if ratio >= SAFE_RATIO:
                    result = "✅ 안전"
                elif ratio >= LIQUIDATION_RATIO:
                    result = "⚠️ 생존"
                else:
                    result = "❌ 청산"
                f.write(f"| {cn} | {cm}% | **{ratio:.0f}%** | {margin:+.0f}%p | {result} |\n")
            f.write("\n")
            f.write("> **결론**: IMF 외환위기(-64.7%)를 제외한 모든 역사적 위기에서 생존하며, "
                    "투자 비중이 가장 높아 반등 시 수익 극대화 가능\n\n")

        # ── 핵심 인사이트 ──
        f.write("---\n\n")
        f.write("## 🔑 핵심 인사이트\n\n")
        f.write(f"1. **청산 기준은 {LIQUIDATION_RATIO}%**, 안전 기준은 {SAFE_RATIO}%\n")
        f.write(f"   - {LIQUIDATION_RATIO}% 미만: 강제 청산\n")
        f.write(f"   - {LIQUIDATION_RATIO}~{SAFE_RATIO}%: 청산은 면하지만 위험 구간\n")
        f.write(f"   - {SAFE_RATIO}% 이상: 안전 구간\n\n")
        f.write("2. **역사상 최악의 위기들**\n")
        f.write("   - IMF 외환위기: **MDD -64.7%** (1997) — 역대 1위\n")
        f.write("   - 글로벌 금융위기: **MDD -54.5%** (2008) — 역대 2위\n")
        f.write("   - 코로나 팬데믹: **MDD -43.9%** (2020) — 역대 3위\n\n")
        f.write("3. **⭐ 추천 전략: 피라미드형 (중반집중)**\n")
        f.write("   - MDD -20~25% 구간에 화력 집중 → 빈도 대비 최적 수익\n")
        f.write("   - 8단계 분산으로 MDD -50%까지 커버\n")
        f.write("   - IMF급(-64.7%) 제외 모든 위기 생존 (청산 기준 140%)\n")
        f.write("   - 총 53% 투자로 반등 시 수익 극대화\n\n")
        f.write("4. **핵심 교훈**\n")
        f.write("   - 담보비율 300%는 극도로 보수적인 제약\n")
        f.write("   - **빈도 기반 배분**이 균등 배분보다 효율적\n")
        f.write("   - 분할 매수가 한 번에 매수보다 **훨씬 안전**\n\n")

        f.write("---\n\n")
        f.write("**분석 도구**: Python + 코스피 31년 데이터  \n")
        f.write(f"**데이터 출처**: Yahoo Finance (via market_data.db)\n")

    return filename


def main():
    print("=" * 60)
    print("  코스피 MDD 기반 담보대출 전략 계산기")
    print("=" * 60)
    print()

    # 데이터 로드
    loader = DataLoader(DB_PATH)
    df = loader.load_market_data('kospi')
    print(f"📊 코스피 데이터 로드: {len(df):,}건")
    print(f"   기간: {df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')}")

    current_price = df['close'].iloc[-1]
    ath = df['close'].max()
    current_mdd = (current_price / ath - 1) * 100
    print(f"   현재: {current_price:,.2f} | 고점: {ath:,.2f} | MDD: {current_mdd:.1f}%")
    print()

    # 리포트 생성 (100만원 기준)
    filename = generate_report(df, initial_capital=1_000_000)

    print(f"✅ 리포트 생성 완료: {filename}")
    print()

    # 요약 출력
    print("📋 전략 요약 (100만원 기준):")
    print(f"{'전략':>16} | {'대출액':>10} | {'비중':>6} | 코로나  | 금융위기 | IMF")
    print("-" * 75)
    for name, strategy in STRATEGIES.items():
        results = simulate_strategy(strategy)
        total = results[-1]['cum_loan']

        crisis_results = []
        for cn, cm in CRISIS_SCENARIOS:
            _, _, ratio = simulate_crisis(strategy, cm)
            emoji = "✅" if ratio >= SAFE_RATIO else ("⚠️" if ratio >= LIQUIDATION_RATIO else "❌")
            crisis_results.append(f"{emoji}{ratio:>4.0f}%")

        total_pct = sum(p for _, p in strategy['steps'])
        print(f"{name.replace('_', ' '):>16} | {total * 10000:>8,.0f}원 | {total_pct:>4}% | {'  | '.join(crisis_results)}")

    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
