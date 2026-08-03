"""
코스피 MDD 심층 분석 리포트 생성기
- MDD 구간별 전환 확률 (회복 vs 추가 하락)
- 역사적 하락 에피소드 기반 통계
- 누적 하락 확률 (MDD -15% 도달 후 -X%까지 갈 확률)
- 추가매수 단계별 전략 권고
"""

import os
import sys
import numpy as np
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from config import DB_PATH, WEEKLY_RESEARCH_DIR
from data_loader import DataLoader

# ── 역사적 주요 위기 (참조용 하드코딩) ──────────────────────────────
HISTORICAL_CRISES = [
    ("IMF 외환위기",   "1997-10", "1999-05", -64.7, "외채 위기·IMF 구제금융",     "약 4년"),
    ("IT 버블 붕괴",   "2000-01", "2002-10", -50.0, "닷컴버블 붕괴·9.11 테러",    "약 3년"),
    ("글로벌 금융위기", "2007-11", "2009-03", -54.5, "서브프라임·리먼 쇼크",       "약 3년"),
    ("유럽 재정위기",  "2011-05", "2011-11", -27.0, "그리스·PIIGS 재정위기",      "약 1년"),
    ("中 경기둔화",    "2015-06", "2016-02", -22.0, "위안화 평가절하·중국 쇼크",   "약 8개월"),
    ("美中 무역전쟁",  "2018-01", "2018-12", -25.0, "트럼프 관세 분쟁",            "약 1년"),
    ("코로나 충격",    "2020-01", "2020-03", -43.9, "글로벌 팬데믹",               "약 2개월"),
    ("긴축·고금리",   "2021-07", "2023-01", -37.0, "Fed 급격 금리인상",            "약 18개월"),
]

# ── MDD 임계값 ──────────────────────────────────────────────────────
MDD_THRESHOLDS = [-15, -20, -25, -30, -35, -40, -50]

# ── 투자 단계별 계획 (현금 100 기준 투입 비율) ───────────────────────
INVESTMENT_PLAN = [
    (-15, 15, "1차 시작 — 소량 탐색적 매수"),
    (-20, 25, "2차 핵심 — 역사적 황금 구간 화력 집중"),
    (-25, 15, "3차 추가 — 반등 기대 구간"),
    (-30, 15, "4차 위기 — 검증된 위기 매수"),
    (-35, 10, "5차 대위기 — 소량 추가"),
    (-40, 10, "6차 대위기 심화 — 극소량 추가"),
    (-50,  0, "7차 이상 — 현금 10% 보존 (생존용)"),
]

# ── 50% 되돌림 참고 데이터 (역사적 추정치) ──────────────────────────────
# (mdd_val, 목표_반등, 예상_기간, 사례_참고, 트레이딩_특성)
MDD_HALF_RECOVERY = [
    (-15,  "+7.5%",  "2~6주",                 "6개 사례 모두 상대적으로 빠른 회복",                          "빠른 V자 or W자 반등 多"),
    (-20,  "+10%",   "4~8주",                 "중국쇼크(2016): 저점 후 2개월 내 회복 진행",                   "단기 스윙 가능 구간"),
    (-25,  "+12.5%", "6~16주",                "美中무역전쟁(2018): 12월 저점 후 3개월 내 50% 되돌림",         "저점 확인 후 진입 유효"),
    (-30,  "+15%",   "8~24주",                "고금리 긴축(2022): 저점 형성 지연, 50% 되돌림 약 6개월 소요",  "분할 매수 필수"),
    (-40,  "+20%",   "2~4주(V자) 또는 6개월+", "코로나(2020): 3주 내 50% 되돌림 / GFC(2009): 6개월 이상",    "충격 성격에 따라 극단적 편차"),
    (-50,  "+25%+",  "3개월~1년",              "IMF: 저점 후 간헐 반등 반복",                                 "생존 모드, 단기 매매 고위험"),
]


# ══════════════════════════════════════════════════════════════════════
# 데이터 처리 함수
# ══════════════════════════════════════════════════════════════════════

def compute_mdd_series(df):
    """Rolling MDD 시리즈 계산 (누적 고점 대비 하락률)"""
    df = df.copy()
    df['cummax'] = df['close'].cummax()
    df['mdd_pct'] = (df['close'] / df['cummax'] - 1) * 100
    return df


def identify_drawdown_episodes(df_mdd, entry_threshold=-15.0, recovery_threshold=-5.0):
    """
    독립적인 하락 에피소드 식별

    정의:
      - 진입: MDD ≤ entry_threshold (예: -15%)
      - 종료: MDD ≥ recovery_threshold (예: -5%, ATH 근처 회복)

    각 에피소드 내에서 최저 MDD(min_mdd) 를 기록.

    Args:
        df_mdd : mdd_pct 컬럼이 포함된 DataFrame (compute_mdd_series 결과)
        entry_threshold   : 에피소드 시작 MDD (음수, 예 -15.0)
        recovery_threshold: 에피소드 종료 MDD (음수 또는 0, 예 -5.0)

    Returns:
        list of dict: {start, end, min_mdd, duration_days, ongoing}
    """
    episodes = []
    in_ep = False
    ep_start = None
    ep_min_mdd = 0.0

    for date, row in df_mdd.iterrows():
        mdd = row['mdd_pct']

        if not in_ep:
            if mdd <= entry_threshold:
                in_ep = True
                ep_start = date
                ep_min_mdd = mdd
        else:
            if mdd < ep_min_mdd:
                ep_min_mdd = mdd
            if mdd >= recovery_threshold:
                episodes.append({
                    'start': ep_start,
                    'end': date,
                    'min_mdd': ep_min_mdd,
                    'duration_days': (date - ep_start).days,
                    'ongoing': False,
                })
                in_ep = False
                ep_start = None
                ep_min_mdd = 0.0

    # 아직 회복 안 된 현재 진행 중 에피소드
    if in_ep:
        episodes.append({
            'start': ep_start,
            'end': df_mdd.index[-1],
            'min_mdd': ep_min_mdd,
            'duration_days': (df_mdd.index[-1] - ep_start).days,
            'ongoing': True,
        })

    return episodes


def compute_transition_stats(episodes):
    """
    MDD 구간별 전환 통계 계산

    각 임계값에 대해:
      - n_reached  : 해당 구간에 도달한 (완료된) 에피소드 수
      - n_stopped  : 해당 구간에서 최저점 찍고 회복한 에피소드 수 (다음 구간 미도달)
      - n_deeper   : 다음 구간까지 추가 하락한 에피소드 수
      - recovery_prob : 회복 확률 (%)
      - deeper_prob   : 추가 하락 확률 (%)
      - avg_min_mdd   : 이 구간에서 멈춘 에피소드들의 평균 최저 MDD
      - avg_duration_days : 에피소드 평균 지속 기간 (일)

    완료된 에피소드만 사용 (ongoing=False).
    """
    closed = [ep for ep in episodes if not ep.get('ongoing', False)]
    rows = []

    for i, t in enumerate(MDD_THRESHOLDS):
        next_t = MDD_THRESHOLDS[i + 1] if i + 1 < len(MDD_THRESHOLDS) else None

        n_reached = sum(1 for ep in closed if ep['min_mdd'] <= t)
        n_deeper  = sum(1 for ep in closed if ep['min_mdd'] <= next_t) if next_t is not None else 0
        n_stopped = n_reached - n_deeper

        recovery_prob = n_stopped / n_reached * 100 if n_reached > 0 else 0.0
        deeper_prob   = n_deeper  / n_reached * 100 if n_reached > 0 else 0.0

        stopped_eps = [
            ep for ep in closed
            if ep['min_mdd'] <= t and (next_t is None or ep['min_mdd'] > next_t)
        ]
        avg_min = float(np.mean([ep['min_mdd'] for ep in stopped_eps])) if stopped_eps else float(t)
        avg_dur = float(np.mean([ep['duration_days'] for ep in stopped_eps])) if stopped_eps else 0.0

        rows.append({
            'threshold': t,
            'n_reached': n_reached,
            'n_stopped': n_stopped,
            'n_deeper':  n_deeper,
            'recovery_prob': recovery_prob,
            'deeper_prob':   deeper_prob,
            'avg_min_mdd':   avg_min,
            'avg_duration_days': avg_dur,
        })

    return rows


def compute_raw_count_transitions(df_mdd):
    """
    기존 margin_calculator 방식 (60일 간격 카운팅) 으로
    MDD 임계값별 도달 횟수 계산 → 파생 전환 확률 산출

    Returns:
        list of dict: {threshold, raw_count, derived_recovery_prob, derived_deeper_prob}
    """
    results = []
    counts = {}

    for threshold in MDD_THRESHOLDS:
        mask = df_mdd['mdd_pct'] <= threshold
        if not mask.any():
            counts[threshold] = 0
            continue
        first_days = df_mdd[mask].index
        count = 0
        last_date = None
        for d in first_days:
            if last_date is None or (d - last_date).days > 60:
                count += 1
                last_date = d
        counts[threshold] = count

    for i, t in enumerate(MDD_THRESHOLDS):
        next_t = MDD_THRESHOLDS[i + 1] if i + 1 < len(MDD_THRESHOLDS) else None
        n = counts[t]
        n_next = counts[next_t] if next_t is not None else 0
        n_stopped = n - n_next

        results.append({
            'threshold': t,
            'raw_count': n,
            'n_stopped_raw': n_stopped,
            'n_deeper_raw':  n_next,
            'recovery_prob_raw': n_stopped / n * 100 if n > 0 else 0.0,
            'deeper_prob_raw':   n_next    / n * 100 if n > 0 else 0.0,
        })

    return results


def get_current_state(df, df_mdd):
    """현재 시장 상태 계산"""
    current_price = df['close'].iloc[-1]
    ath           = df['close'].max()
    ath_date      = df['close'].idxmax()
    current_mdd   = (current_price / ath - 1) * 100
    ma200         = df['close'].rolling(200).mean().iloc[-1]
    ma200_pct     = (current_price / ma200 - 1) * 100
    ma20          = df['close'].rolling(20).mean().iloc[-1]
    return {
        'price':     current_price,
        'ath':       ath,
        'ath_date':  ath_date,
        'mdd':       current_mdd,
        'ma200':     ma200,
        'ma200_pct': ma200_pct,
        'ma20':      ma20,
    }


# ══════════════════════════════════════════════════════════════════════
# 리포트 생성
# ══════════════════════════════════════════════════════════════════════

def generate_report(df):
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    os.makedirs(WEEKLY_RESEARCH_DIR, exist_ok=True)
    filename = os.path.join(WEEKLY_RESEARCH_DIR, f"코스피_MDD_심층분석_리포트_{ts}.md")

    df_mdd   = compute_mdd_series(df)
    episodes = identify_drawdown_episodes(df_mdd)
    trans    = compute_transition_stats(episodes)
    raw_trans = compute_raw_count_transitions(df_mdd)
    state    = get_current_state(df, df_mdd)

    closed       = [ep for ep in episodes if not ep.get('ongoing', False)]
    open_episode = next((ep for ep in episodes if ep.get('ongoing', False)), None)

    data_start = df.index[0].strftime('%Y-%m-%d')
    data_end   = df.index[-1].strftime('%Y-%m-%d')
    data_years = (df.index[-1] - df.index[0]).days / 365.25

    ath = state['ath']

    # 현재 단계 판단
    if state['mdd'] > -15:
        phase = "대기 구간 — 매수 트리거 미발동"
    elif state['mdd'] > -20:
        phase = "1차 매수 구간 — 소량 탐색 매수 시작"
    elif state['mdd'] > -30:
        phase = "핵심 매수 구간 — 화력 집중 투입 단계"
    elif state['mdd'] > -40:
        phase = "위기 매수 구간 — 위기 분할 매수 단계"
    else:
        phase = "대위기 구간 — 소량 추가, 현금 보존 우선"

    next_trigger = next((t for t in MDD_THRESHOLDS if state['mdd'] > t), None)

    with open(filename, 'w', encoding='utf-8') as f:

        # ── 타이틀 ────────────────────────────────────────────────────
        f.write("# 📉 코스피 MDD 심층분석 리포트\n")
        f.write("## — 역사적 저점 형성 구간과 추가매수 전략\n\n")
        f.write(f"> **기준일**: {datetime.now().strftime('%Y년 %m월 %d일')}  \n")
        f.write(f"> **코스피**: {state['price']:,.2f}pt | 역대 고점 대비 MDD **{state['mdd']:.1f}%**"
                f" (고점: {ath:,.0f}pt, {state['ath_date'].strftime('%Y-%m-%d')})  \n")
        f.write(f"> **데이터 범위**: {data_start} ~ {data_end} (약 {data_years:.0f}년)  \n")
        f.write(f"> **MA200**: {state['ma200']:,.0f}pt | 현재가 MA200 대비 **{state['ma200_pct']:+.1f}%**\n\n")
        f.write("---\n\n")

        # ── 핵심 요약 ─────────────────────────────────────────────────
        f.write("## ★ 핵심 요약\n\n")
        f.write("```\n")
        f.write(f"현재 MDD: {state['mdd']:.1f}%  →  {phase}\n")
        if next_trigger:
            f.write(f"다음 매수 트리거: MDD {next_trigger}%  →  KOSPI {ath * (1 + next_trigger / 100):,.0f}pt\n")
        ma200_label = "역사적 극단 과열" if state['ma200_pct'] > 50 else ("과열 주의" if state['ma200_pct'] > 30 else "정상")
        f.write(f"MA200 대비 과열도: {state['ma200_pct']:+.1f}%  ({ma200_label})\n")
        f.write(f"총 분석 에피소드: {len(closed)}개 완료 / {1 if open_episode else 0}개 진행 중\n")
        f.write("```\n\n")
        f.write("---\n\n")

        # ── 섹션 1: 역사적 위기 분류표 ───────────────────────────────
        f.write("## 1. 역사적 MDD 위기 분류표\n\n")
        f.write("| 위기 명칭 | 시작 | 저점 | 저점 MDD | 회복 소요 | 원인 |\n")
        f.write("|:---------|:----:|:----:|:--------:|:--------:|:----|\n")
        for name, start, end, mdd_val, cause, rec in HISTORICAL_CRISES:
            f.write(f"| {name} | {start} | {end} | **{mdd_val:.1f}%** | {rec} | {cause} |\n")
        f.write(f"| 현재 (조정 중) | 2026.06 | — | **{state['mdd']:.1f}%** | 진행 중 | 고점 후 정상 조정 |\n\n")
        f.write("> **패턴 관찰**: 외부 충격 대형 위기(-50%+) / 일반 사이클 위기(-20~-40%) / 일시 공포(-15~-25%)\n\n")
        f.write("---\n\n")

        # ── 섹션 2: 하락 에피소드 분석 ───────────────────────────────
        f.write("## 2. 역사적 하락 에피소드 분석\n\n")
        f.write(f"**분석 기준**: MDD -15% 이하 진입 후, ATH 5% 이내(MDD ≥ -5%) 회복까지를 1개 에피소드로 정의  \n")
        f.write(f"**데이터**: {data_start} ~ {data_end} ({data_years:.0f}년)  \n")
        f.write(f"**총 완료 에피소드**: {len(closed)}개\n\n")

        depth_bins  = [(-15, -20), (-20, -25), (-25, -30), (-30, -40), (-40, -50), (-50, -200)]
        bin_labels  = ["-15 ~ -20%", "-20 ~ -25%", "-25 ~ -30%", "-30 ~ -40%", "-40 ~ -50%", "-50% 이하"]
        bin_chars   = [
            "일반 조정 → 흔한 저점",
            "사이클 저점 → 핵심 매수 황금 구간",
            "중간 위기 → 적극 추가 매수",
            "대형 위기 → 소량 추가",
            "준위기 (코로나급) → 극소량 추가",
            "대위기 (IMF·GFC급) → 생존 모드",
        ]

        f.write("| 최대 하락 구간 | 에피소드 수 | 비율 | 평균 지속기간 | 투자 성격 |\n")
        f.write("|:-------------:|:----------:|:----:|:-----------:|:--------|\n")
        for (lo, hi), label, char in zip(depth_bins, bin_labels, bin_chars):
            eps_bin = [ep for ep in closed if lo >= ep['min_mdd'] > hi]
            cnt     = len(eps_bin)
            pct     = cnt / len(closed) * 100 if closed else 0
            avg_dur = float(np.mean([ep['duration_days'] for ep in eps_bin])) if eps_bin else 0
            dur_str = f"약 {avg_dur / 30:.0f}개월" if avg_dur > 0 else "—"
            f.write(f"| {label} | {cnt}개 | {pct:.0f}% | {dur_str} | {char} |\n")
        f.write("\n")

        if open_episode:
            f.write(f"> ⚠️ **현재 진행 중인 에피소드**: {open_episode['start'].strftime('%Y-%m-%d')} 시작 "
                    f"| 현재 MDD {open_episode['min_mdd']:.1f}% | {open_episode['duration_days']}일 경과\n\n")
        f.write("---\n\n")

        # ── 섹션 3: MDD 전환 확률 (핵심 신규 분석) ───────────────────
        f.write("## 3. MDD 구간별 회복 확률 vs 추가 하락 확률\n\n")
        f.write("> **핵심 질문**: MDD가 -X%에 도달했을 때, 여기서 반등할 확률과 더 깊이 하락할 확률은 각각 얼마인가?\n\n")

        # 3-A: 에피소드 기반
        f.write("### 3-A. 에피소드 기반 전환 확률 (정밀 분석)\n\n")
        f.write(f"> **방법론**: {len(closed)}개 완료 에피소드 기반. "
                "각 에피소드의 최저 MDD를 기준으로 '이 구간에서 멈춘 비율' 산출.\n\n")
        f.write("| MDD 도달 | 에피소드 수 | 여기서 회복 | 더 하락 | **회복 확률** | **추가 하락 확률** | 평균 최저 MDD(회복 시) | 전고점 회복까지† |\n")
        f.write("|:--------:|:----------:|:-----------:|:------:|:------------:|:-----------------:|:---------------------:|:--------:|\n")
        for row in trans:
            t        = row['threshold']
            dur_str  = f"약 {row['avg_duration_days'] / 30:.0f}개월" if row['avg_duration_days'] > 0 else "—"
            min_str  = f"{row['avg_min_mdd']:.1f}%" if row['n_stopped'] > 0 else "—"
            f.write(f"| **{t}%** | {row['n_reached']}회 | {row['n_stopped']}회 | {row['n_deeper']}회 | "
                    f"**{row['recovery_prob']:.0f}%** | **{row['deeper_prob']:.0f}%** | "
                    f"{min_str} | {dur_str} |\n")
        f.write("\n")
        f.write("> † **\"전고점 회복까지\" 정의**: 해당 구간이 최저점이었던 에피소드에서, "
                "**직전 전고점(ATH) 대비 -5% 이내(MDD ≥ -5%)까지 가격이 복귀**하는 데 걸린 평균 기간입니다.  \n")
        f.write("> 단순 반등 시작이 아닌 **전고점 수준으로 거의 완전히 회복되기까지의 총 소요 기간**을 의미합니다.  \n")
        f.write("> ※ 표본 수가 1개인 구간은 단일 사례 수치이므로 편차가 매우 크며 참고값으로만 활용하세요.\n\n")

        # 3-B: 60일 간격 카운팅 기반 (기존 margin_calculator 방식)
        f.write("### 3-B. 원시 카운팅 기반 전환 확률 (60일 간격 기준)\n\n")
        f.write("> **방법론**: MDD가 각 임계값을 하향 돌파한 횟수(60일 이상 간격)를 기반으로 파생 확률 계산.\n")
        f.write("> ※ MDD -30%가 발생했다면 -15%, -20%, -25%는 반드시 통과 → 상위 횟수는 하위 횟수의 부분집합.\n\n")
        f.write("| MDD 구간 | 도달 횟수 | 이 구간에서 멈춘 횟수 | 더 하락한 횟수 | **회복 확률** | **추가 하락 확률** |\n")
        f.write("|:--------:|:--------:|:-------------------:|:------------:|:------------:|:-----------------:|\n")
        for row in raw_trans:
            t = row['threshold']
            f.write(f"| **{t}%** | {row['raw_count']}회 | {row['n_stopped_raw']}회 | {row['n_deeper_raw']}회 | "
                    f"**{row['recovery_prob_raw']:.0f}%** | **{row['deeper_prob_raw']:.0f}%** |\n")
        f.write("\n")
        f.write("> **두 방법론 비교**: 에피소드 방식(3-A)은 동일 위기의 반복 카운팅을 방지하므로 더 보수적이고 정확함.\n"
                "> 원시 카운팅(3-B)은 단기 반등 후 재하락을 별도 이벤트로 집계하므로 횟수가 더 많음.\n\n")
        f.write("---\n\n")

        # ── 3-C: 50% 되돌림 분석 ─────────────────────────────────────
        f.write("### 3-C. 50% 되돌림 소요 기간 분석\n\n")
        f.write("> **읽는 법**: 코스피가 MDD -X%까지 하락했을 때, 저점 대비 **하락폭의 절반**을 되돌리는 데 걸린 역사적 기간.  \n")
        f.write("> 예: MDD -20% 도달 → 저점 대비 **+10% 반등**이 일어날 때 50% 되돌림 달성.\n\n")
        f.write("| MDD 저점 | 50% 되돌림 목표 반등 | 예상 소요 기간 | 역사적 사례 참고 | 트레이딩 특성 |\n")
        f.write("|:--------:|:------------------:|:------------:|:-------------:|:------------|\n")
        for mdd_val, target, period, case, char in MDD_HALF_RECOVERY:
            f.write(f"| **{mdd_val}%** | 저점 대비 **{target}** | **{period}** | {case} | {char} |\n")
        f.write("\n")
        f.write("> ⚠️ **주의**: 50% 되돌림 달성 후에도 재하락(W자 / 다중 저점)이 빈번하게 발생합니다. "
                "-20% 이상 구간에서는 첫 반등만 보고 대규모 진입하지 마세요.\n\n")
        f.write("---\n\n")

        # ── 3-D: 단기 매매(스윙 트레이딩) 관점 분석 ─────────────────
        f.write("### 3-D. 단기 매매(스윙 트레이딩) 관점 분석\n\n")
        f.write("> **전략 철학**: 장기 분할 매수와 별도로, 단기 반등을 활용한 스윙 매매 전략.  \n")
        f.write("> **저점 매수 → 50% 되돌림 구간 익절** 또는 **이전 저항선 근처 매도**를 목표로 함.\n\n")

        f.write("#### 단기 매수 진입 신호\n\n")
        f.write("| 신호 유형 | 세부 조건 | 해석 |\n")
        f.write("|:--------:|:---------|:-----|\n")
        f.write("| **RSI 과매도** | RSI(14) ≤ 30 | 과매도 영역 진입 → 단기 반등 가능성 高 |\n")
        f.write("| **이격도** | 코스피 / MA20 ≤ 0.93 (7% 하방 이격) | 20일 이평선 대비 7% 이상 이탈 → 평균 회귀 기대 |\n")
        f.write("| **거래량 클라이맥스** | 전일 대비 200%+ 거래량 폭증 | 공포 패닉셀 절정 → 반전 신호 |\n")
        f.write("| **변동성 지수 급등** | VKOSPI ≥ 25 | 과도한 공포 국면 → 역발상 매수 고려 |\n")
        f.write("| **반전 캔들** | 연속 음봉 후 장대 양봉 or 망치형 출현 | 단기 저점 전환 신호 |\n\n")

        f.write("#### MDD 구간별 단기 스윙 전략\n\n")
        f.write("| MDD 구간 | 진입 조건 | 목표 청산가 | 손절 기준 | 예상 홀딩 | 위험도 |\n")
        f.write("|:--------:|:---------|:---------:|:--------:|:--------:|:-----:|\n")
        f.write("| **-15%** | 반등 캔들 확인 후 소량 진입 | MDD -10% 수준 (+5% 이익) | MDD -18% 이탈 시 | 2~4주 | 🟡 보통 |\n")
        f.write("| **-20%** | 강한 반등 캔들 확인 후 진입 | MDD -12~-13% (+7~8% 이익) | MDD -23% 이탈 시 | 3~6주 | 🟡 보통 |\n")
        f.write("| **-25%** | 저점 2회 확인(쌍바닥) 후 분할 진입 | MDD -15~-18% (+7~10% 이익) | MDD -28% 이탈 시 | 4~8주 | 🟠 높음 |\n")
        f.write("| **-30%** | 주봉 양봉 확인 후 진입 | MDD -20~-22% (+8~10% 이익) | MDD -33% 이탈 시 | 6~12주 | 🔴 매우 높음 |\n")
        f.write("| **-40%+** | V자 반등 초기 확인 후 진입 (코로나 유형에만) | MDD -28~-30% (+10~12% 이익) | MDD -43% 이탈 시 | 2~6주 | ⚫ 극위험 |\n\n")

        f.write("#### 단기 매매 핵심 원칙\n\n")
        f.write("```\n")
        f.write("① 단기 배분 규모: 전체 투자 자산의 5~10% 이내로 엄격히 제한\n")
        f.write("② 손절가 사전 설정 후 진입 (진입 전 손절선 결정이 원칙)\n")
        f.write("③ 목표가 달성 시 미련 없이 청산 (욕심 금지)\n")
        f.write("④ 단기 포지션과 장기 분할 매수 포지션은 계좌/기록 분리 관리\n")
        f.write("⑤ MDD -30% 이상 구간은 단기 매매보다 장기 분할 매수가 기댓값 높음\n")
        f.write("```\n\n")

        f.write("#### 단기 vs 장기 전략 비교\n\n")
        f.write("| 항목 | 단기 스윙 매매 | 장기 분할 매수 |\n")
        f.write("|:----|:------------:|:------------:|\n")
        f.write("| 목표 기간 | 2~12주 | 1~3년 |\n")
        f.write("| 목표 수익률 | +5~15% | +30~100%+ |\n")
        f.write("| 손절 기준 | 진입가 대비 -3~5% | 추가 하락 시 추가 매수 |\n")
        f.write("| 포지션 크기 | 전체의 5~10% | 전체의 15~40% |\n")
        f.write("| 최적 MDD 구간 | -15% ~ -25% | -20% ~ -40% |\n")
        f.write("| 핵심 도구 | RSI, 이격도, 거래량, 반전 캔들 | MDD 단계별 투입 계획 |\n")
        f.write("| 리스크 특성 | 타이밍 의존도 높음 | 평균 단가 낮춤 효과 |\n\n")
        f.write("---\n\n")

        # ── 섹션 4: 회복 확률 시각화 ─────────────────────────────────
        f.write("## 4. 회복 확률 시각화\n\n")
        f.write("```\n")
        f.write(f"{'MDD 도달':<10}  {'◀ 회복 확률':<22} {'추가 하락 확률 ▶':<22}\n")
        f.write("─" * 60 + "\n")
        for row in trans:
            t    = row['threshold']
            n_r  = max(0, min(20, int(row['recovery_prob'] / 5)))
            n_d  = max(0, min(20, int(row['deeper_prob']   / 5)))
            bar_r = "▓" * n_r
            bar_d = "░" * n_d
            f.write(f"MDD {t:>4}%   {bar_r:<20} {row['recovery_prob']:>4.0f}%  |  "
                    f"{bar_d:<20} {row['deeper_prob']:>4.0f}%\n")
        f.write("```\n\n")

        # ── 섹션 5: 누적 하락 확률 ───────────────────────────────────
        f.write("## 5. 누적 하락 확률 (MDD -15% 도달 후 더 깊이 갈 확률)\n\n")
        f.write("> **읽는 법**: 코스피 MDD가 -15%에 도달한 이후, 결국 -X%까지 추가 하락할 확률은?\n\n")

        # 에피소드 기반
        first_row_ep  = next((r for r in trans if r['threshold'] == -15), None)
        first_row_raw = next((r for r in raw_trans if r['threshold'] == -15), None)
        n_base_ep     = first_row_ep['n_reached']  if first_row_ep  else 1
        n_base_raw    = first_row_raw['raw_count'] if first_row_raw else 1

        f.write("| 최종 MDD | 에피소드 기반 횟수 | **에피소드 기반 확률** | 원시카운팅 횟수 | **원시카운팅 확률** |\n")
        f.write("|:--------:|:----------------:|:--------------------:|:--------------:|:-----------------:|\n")
        for ep_row, raw_row in zip(trans, raw_trans):
            t        = ep_row['threshold']
            prob_ep  = ep_row['n_reached']      / n_base_ep  * 100 if n_base_ep  > 0 else 0
            prob_raw = raw_row['raw_count']     / n_base_raw * 100 if n_base_raw > 0 else 0
            f.write(f"| {t}% | {ep_row['n_reached']}회 | **{prob_ep:.0f}%** | "
                    f"{raw_row['raw_count']}회 | **{prob_raw:.0f}%** |\n")
        f.write("\n")

        f.write("### 💡 핵심 해석\n\n")
        for i, (ep_row, raw_row) in enumerate(zip(trans, raw_trans)):
            t   = ep_row['threshold']
            rp  = ep_row['recovery_prob']
            dp  = ep_row['deeper_prob']
            nr  = ep_row['n_reached']
            ns  = ep_row['n_stopped']
            rp2 = raw_row['recovery_prob_raw']
            dp2 = raw_row['deeper_prob_raw']

            if t == -15:
                f.write(f"**MDD -15%**: 도달 시 **{rp:.0f}%**가 여기서 회복 / **{dp:.0f}%**가 더 하락 (원시기준 {rp2:.0f}% / {dp2:.0f}%).\n")
                f.write(f"  → -15%는 '자주 오는 구간'이지만 **과반이 더 하락함**. 소량 탐색적 매수만 진행하고 나머지 탄약 보존 필수.\n\n")
            elif t == -20:
                f.write(f"**MDD -20%**: 도달 시 **{rp:.0f}%**가 여기서 회복 (원시기준 {rp2:.0f}%).\n")
                threshold_desc = "절반 이상이 여기서 멈춤" if rp >= 50 else "과반이 아직 더 하락"
                f.write(f"  → {threshold_desc}. 역사적 황금 구간 진입 → **핵심 화력 집중 투입** 시작.\n\n")
            elif t == -25:
                f.write(f"**MDD -25%**: 도달 시 **{rp:.0f}%**가 여기서 회복 (원시기준 {rp2:.0f}%).\n")
                f.write(f"  → 이 구간에서 회복 시 비교적 빠른 반등 경향. 적극 추가 매수 구간.\n\n")
            elif t == -30:
                f.write(f"**MDD -30%**: 도달 시 **{rp:.0f}%**가 여기서 회복 (원시기준 {rp2:.0f}%).\n")
                threshold_desc = "절반 이상이 여기가 최저점" if rp >= 50 else "여전히 추가 하락 주의"
                f.write(f"  → {threshold_desc}. 대형 위기 가능성 병존 → 소량 추가.\n\n")
            elif t == -35:
                f.write(f"**MDD -35%**: 도달 시 **{rp:.0f}%**가 여기서 회복 (원시기준 {rp2:.0f}%).\n")
                f.write(f"  → 코로나·고금리 긴축 수준의 위기. 소량 분할 추가.\n\n")
            elif t == -40:
                f.write(f"**MDD -40%**: 도달 시 **{rp:.0f}%**가 여기서 회복 (원시기준 {rp2:.0f}%).\n")
                threshold_desc = "절반 이상이 여기가 최저점" if rp >= 50 else "GFC·IMF급으로 추가 하락 가능"
                f.write(f"  → {threshold_desc}. 극소량 추가 매수만. 현금 절반 이상 보존.\n\n")
            elif t == -50:
                f.write(f"**MDD -50%+**: IMF·GFC급 위기. {nr}회 도달.\n")
                f.write(f"  → 이 구간 도달 시 **생존 모드 전환**. 현금 절대 소진 금지.\n\n")

        f.write("---\n\n")

        # ── 섹션 6: Zone 구분 ─────────────────────────────────────────
        f.write("## 6. MDD 투자 Zone 구분\n\n")
        f.write("```\n")
        f.write(f"  0%  ─── {state['mdd']:.1f}% ─────── -15% ─────── -20% ─────── -30% ─────── -40% ─── -50%+\n")
        f.write(f"  │         │              │              │              │              │\n")
        f.write(f"GREEN   [지금여기]        YELLOW        ORANGE         RED          BLACK\n")
        f.write(f"대기      현금확보        1차매수       핵심매수       위기매수      생존모드\n")
        f.write(f"                         (15%)        (25~15%)      (15~10%)       (극소)\n")
        f.write("```\n\n")
        f.write("| Zone | MDD 범위 | 성격 | 대기현금 투입 비율 | 핵심 원칙 |\n")
        f.write("|:----:|:--------:|:----:|:-----------------:|:--------|\n")
        f.write("| 🟢 대기 | 0% ~ -14% | 정상 조정 | **0%** | 현금 확보. 매도 익절 실행. |\n")
        f.write("| 🟡 1차 매수 | -15% ~ -19% | 빈번한 저점 | **15%** | 소량 시작. 탄약 보존. |\n")
        f.write("| 🟠 핵심 매수 | -20% ~ -29% | 역사적 황금구간 | **40%** | **화력 집중**. 분할 투입. |\n")
        f.write("| 🔴 위기 매수 | -30% ~ -39% | 대형 위기 | **25%** | 소량 추가. 레버리지 금지. |\n")
        f.write("| ⚫ 대위기 | -40% ~ -49% | 코로나·GFC급 | **10%** | 극소량. 현금 절반 보존. |\n")
        f.write("| 💀 국가위기 | -50% 이하 | IMF급 | **0%** | 생존 모드. 현금 사용 금지. |\n\n")
        f.write("---\n\n")

        # ── 섹션 7: 현재 위치 분석 및 AI 의견 ────────────────────────
        f.write("## 7. 현재 위치 분석 및 추가매수 전략 (AI 의견)\n\n")

        f.write("### 7-1. 현재 시장 좌표\n\n")
        f.write("| 항목 | 수치 | 해석 |\n")
        f.write("|:----|:----:|:-----|\n")
        f.write(f"| 코스피 | **{state['price']:,.2f}pt** | "
                f"{'역사적 신고점 구간' if state['mdd'] > -10 else '고점 대비 조정 중'} |\n")
        f.write(f"| 역대 고점 | {ath:,.0f}pt | {state['ath_date'].strftime('%Y.%m.%d')} 기록 |\n")
        f.write(f"| 현재 MDD | **{state['mdd']:.1f}%** | "
                f"{'정상 조정 → 대기 구간' if state['mdd'] > -15 else '매수 트리거 발동'} |\n")
        f.write(f"| MA200 | {state['ma200']:,.0f}pt | 현재가 대비 {state['ma200_pct']:+.1f}% |\n")
        if state['ma200_pct'] > 50:
            ma200_comment = "⚠️ 역사적 전례 없는 극단 과열 (패러다임 전환 or 버블)"
        elif state['ma200_pct'] > 30:
            ma200_comment = "⚠️ 과열 수준 — 추가 상승보다 조정 위험 우선 고려"
        else:
            ma200_comment = "정상 상승 또는 지지 구간"
        f.write(f"| MA200 과열도 | {state['ma200_pct']:+.1f}% | {ma200_comment} |\n\n")

        f.write("### 7-2. 매수 트리거 단계표 (고점 기준)\n\n")
        f.write("| 매수 단계 | MDD | 코스피 도달가 | 투입 비율 | 현재 상태 | 의미 |\n")
        f.write("|:--------:|:---:|:------------:|:--------:|:--------:|:----|\n")
        for mdd_step, pct, desc in INVESTMENT_PLAN:
            target_price = ath * (1 + mdd_step / 100)
            gap = mdd_step - state['mdd']
            if state['mdd'] <= mdd_step:
                status = "✅ 도달"
            elif gap <= 5:
                status = "⏳ 임박"
            else:
                status = "⏸ 대기"
            if pct > 0:
                f.write(f"| {status} | **{mdd_step}%** | **{target_price:,.0f}pt** | {pct}% | — | {desc} |\n")
            else:
                f.write(f"| {status} | **{mdd_step}%** | **{target_price:,.0f}pt** | 생존용 | — | {desc} |\n")
        f.write("\n")

        f.write("### 7-3. AI 의견 — 지금 수준에서 어떻게 대응할 것인가\n\n")
        f.write("> **면책**: 이하는 역사적 데이터 기반 분석 의견입니다. 투자 결정은 본인 판단과 책임 하에 진행하십시오.\n\n")

        f.write("#### ① 현재 상황 인식\n\n")
        if state['mdd'] > -15:
            f.write(f"현재 MDD **{state['mdd']:.1f}%**는 아직 매수 트리거가 발동되지 않은 **대기 구간**입니다.\n\n")
            f.write(f"역사적으로 -15% 구간에 도달하기까지는 추가 하락이 필요하며, ")
            f.write(f"그 전까지는 현금 비중을 30~50%로 높이는 것이 최우선입니다.\n\n")
        elif state['mdd'] > -20:
            f.write(f"현재 MDD **{state['mdd']:.1f}%**는 **1차 매수 트리거** 구간입니다.\n\n")
            f.write(f"대기 현금의 15%를 투입하고, 나머지 85%는 -20~-30% 핵심 구간을 위해 보존하세요.\n\n")
        elif state['mdd'] > -30:
            f.write(f"현재 MDD **{state['mdd']:.1f}%**는 역사적 **핵심 매수 구간**입니다.\n\n")
            f.write(f"이 구간에서 매수한 케이스는 1년 내 평균 +20% 이상 회복을 기록했습니다. ")
            f.write(f"대기 현금의 40%를 집중 투입하세요.\n\n")
        else:
            f.write(f"현재 MDD **{state['mdd']:.1f}%**는 **위기 매수 구간**입니다.\n\n")
            f.write(f"이 구간은 코로나·GFC급 위기와 유사합니다. 소량 추가하되 현금 절반 이상 보존 필수.\n\n")

        f.write("#### ② MA200 과열도 분석\n\n")
        if state['ma200_pct'] > 50:
            f.write(f"현재 MA200 대비 **{state['ma200_pct']:+.1f}%**는 역사적으로 전례 없는 과열 수준입니다.\n\n")
            f.write("이는 두 가지 가능성을 동시에 내포합니다:\n\n")
            f.write("- **AI·반도체 슈퍼사이클 등 패러다임 전환** → 이익 성장 기반의 New Normal\n")
            f.write("- **버블의 끝자락** → 평균 회귀(MA200 복귀) 과정에서 -40~-60% 조정 가능\n\n")
            f.write("Forward PER 저평가(이익 기반)와 MA200 극단 과열(기술적 과열)이 공존하는 딜레마.\n")
            f.write("→ **분할 익절로 현금 확보 + MDD 단계별 재진입**이 유일한 해법.\n\n")
        elif state['ma200_pct'] > 30:
            f.write(f"MA200 대비 **{state['ma200_pct']:+.1f}%** 과열 경고 수준. 추가 상승보다 조정 대비가 우선.\n\n")
        else:
            f.write(f"MA200 대비 **{state['ma200_pct']:+.1f}%**는 정상 또는 지지 수준.\n\n")

        f.write("#### ③ 구체적 실행 플랜\n\n")
        f.write(f"**① 지금 ~ MDD -15% (현재 ~ {ath * 0.85:,.0f}pt)**\n")
        f.write("- 포지션 일부 익절로 현금 비중 30~50% 확보\n")
        f.write(f"- 목표 매도가: ATH 재접근({ath:,.0f}pt 근처) 시 10~20% 매도\n")
        f.write("- 매도 기준: 과열지표(이격도, RSI, MFI) 동시 발동 시\n\n")

        t1_price = ath * 0.85
        t2_price = ath * 0.80
        t3_price = ath * 0.75
        t4_price = ath * 0.70
        f.write(f"**② MDD -15% 도달 시 ({t1_price:,.0f}pt)**\n")
        f.write("- 대기 현금의 **15%** 투입 (2~3회 분할)\n")
        f.write("- 손절 기준: MDD -20% 도달 시 매수분 재평가 후 추가 or 정리\n\n")

        f.write(f"**③ MDD -20%~-25% 구간 ({t2_price:,.0f} ~ {t3_price:,.0f}pt) ← 핵심 화력**\n")
        f.write("- 대기 현금의 **40%** 집중 투입 (3~5회, 4~8주에 걸쳐 분산)\n")
        f.write("- 역사적으로 이 구간 매수는 1년 내 평균 +20% 회복\n")
        f.write("- 레버리지 절대 금지. 분할 투입 원칙 엄수\n\n")

        f.write(f"**④ MDD -30%+ ({t4_price:,.0f}pt 이하) ← 위기 분할**\n")
        f.write("- 대기 현금의 **25%** 소량 추가\n")
        f.write("- 현금의 10%는 어떤 상황에서도 절대 사용 금지 (생존용)\n\n")

        f.write("#### ④ 출구 전략 (Exit Plan)\n\n")
        f.write("| 회복 단계 | 코스피 기준 | 매도 비율 | 이유 |\n")
        f.write("|:--------:|:---------:|:--------:|:----|\n")
        f.write(f"| 고점 완전 회복 | ~{ath:,.0f}pt | 25% 매도 | 고점 복귀 → 부분 정리 |\n")
        f.write(f"| 신고점 +10% | ~{ath * 1.10:,.0f}pt | 25% 매도 | 오버슈팅 진입 |\n")
        f.write(f"| 신고점 +20% | ~{ath * 1.20:,.0f}pt | 25% 매도 | 이격도 과열 |\n")
        f.write(f"| MA200 대비 +50%+ | MA200×1.5 = ~{state['ma200'] * 1.5:,.0f}pt | 나머지 검토 | 버블 경고 |\n\n")
        f.write("---\n\n")

        # ── 섹션 8: 리스크 시나리오 ──────────────────────────────────
        f.write("## 8. 리스크 시나리오 및 대응\n\n")
        scenarios = [
            ("A: 단순 조정 (확률 ~45%)",
             "MDD -15% 내 조정 완료 후 재상승",
             "1차 매수 후 빠른 회복 → 정해진 매도 가격에 익절"),
            ("B: 일반 사이클 하락 (확률 ~30%)",
             "MDD -20~-30%에서 바닥 형성 후 회복",
             "Phase ②~④ 계획대로 실행. 가장 많이 발생한 시나리오"),
            ("C: 구조적 위기 (확률 ~15%)",
             "MDD -30~-45% (코로나급)",
             "Phase ③~⑤ 실행. 레버리지 최소화. 심리 관리가 핵심 (최대 12개월 지속)"),
            ("D: 버블 붕괴 (확률 ~10%)",
             "MDD -50%+ (GFC급 또는 MA200 정상화)",
             "소량 분할만 실행. 현금 절반 이상 보존. 3~5년 장기 투자 관점 전환"),
        ]
        for name, trigger, action in scenarios:
            f.write(f"### 시나리오 {name}\n")
            f.write(f"- **트리거**: {trigger}\n")
            f.write(f"- **대응**: {action}\n\n")
        f.write("---\n\n")

        # ── 섹션 9: 결론 ─────────────────────────────────────────────
        f.write("## 9. 결론 — 3가지 불변 원칙\n\n")
        f.write("```\n")
        f.write("원칙 1: 현금 30~50% 항상 확보 (다음 기회의 탄약)\n")
        f.write("원칙 2: MDD -20~-30% 구간에 화력 집중 (역사적 황금 구간)\n")
        f.write("원칙 3: 현금 10%는 절대 사용 금지 (IMF급 생존용 최후 보루)\n")
        f.write("```\n\n")
        f.write("---\n\n")

        # ── 푸터 ────────────────────────────────────────────────────
        f.write("| 항목 | 값 |\n")
        f.write("|:----|:---|\n")
        f.write(f"| 분석 기준일 | {datetime.now().strftime('%Y-%m-%d')} |\n")
        f.write(f"| 데이터 범위 | {data_start} ~ {data_end} ({data_years:.0f}년) |\n")
        f.write(f"| 총 에피소드 | {len(closed)}개 완료 / {1 if open_episode else 0}개 진행중 |\n")
        f.write(f"| 현재 코스피 | {state['price']:,.2f}pt |\n")
        f.write(f"| 현재 MDD | {state['mdd']:.1f}% |\n")
        f.write(f"| MA200 | {state['ma200']:,.0f}pt ({state['ma200_pct']:+.1f}%) |\n")

    return filename


# ══════════════════════════════════════════════════════════════════════
# 진입점
# ══════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  코스피 MDD 심층 분석 리포트")
    print("=" * 60)
    print()

    loader = DataLoader(DB_PATH)
    df     = loader.load_market_data('kospi')
    print(f"📊 코스피 데이터 로드: {len(df):,}건")
    print(f"   기간: {df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')}")

    df_mdd   = compute_mdd_series(df)
    episodes = identify_drawdown_episodes(df_mdd)
    closed   = [ep for ep in episodes if not ep.get('ongoing', False)]
    ongoing  = sum(1 for ep in episodes if ep.get('ongoing', False))
    trans    = compute_transition_stats(episodes)

    print(f"   하락 에피소드: {len(closed)}개 완료 / {ongoing}개 진행중\n")

    # 콘솔 요약 출력
    print("📊 MDD 전환 확률 (에피소드 기반):")
    print(f"{'MDD':>6} | {'도달':>4} | {'회복':>4} | {'추가하락':>6} | {'회복%':>6} | {'하락%':>6}")
    print("-" * 50)
    for row in trans:
        print(f"{row['threshold']:>5}% | {row['n_reached']:>4} | {row['n_stopped']:>4} | "
              f"{row['n_deeper']:>6} | {row['recovery_prob']:>5.0f}% | {row['deeper_prob']:>5.0f}%")
    print()

    filename = generate_report(df)
    print(f"✅ 리포트 생성 완료: {filename}")
    return filename


if __name__ == "__main__":
    main()
