"""
리포트 생성 — Markdown + HTML(차트 포함) + Excel

- Markdown: 사람이 읽는 종합 리포트 (대시보드→시장상세→유사구간→분포→국면→백테스트→해석)
- HTML: 동일 내용 + Forward 경로/자산곡선 차트 (bat 실행 시 자동 오픈)
- Excel: Summary / KOSPI / KOSDAQ / Similar_Dates / Forward_Returns / Backtest 시트
"""

import os
import numpy as np
import pandas as pd

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

for _f in ('Malgun Gothic', 'AppleGothic', 'NanumGothic'):
    try:
        plt.rcParams['font.family'] = _f
        break
    except Exception:
        pass
plt.rcParams['axes.unicode_minus'] = False

import config as C

HORIZON_LABEL = {1: 'D+1', 3: 'D+3', 5: 'D+5', 10: 'D+10',
                 20: 'D+20', 60: 'D+60', 120: 'D+120'}


# ─────────────────── 용어 사전 (초보자용 부록) ───────────────────
# (표시용어, 앵커슬러그, 설명) — 본문에서 [[표시용어]] 로 감싸면 클릭 가능 링크가 된다.
GLOSSARY = [
    ('워크포워드', 'walkforward',
     "‘그 시점에 실제로 알 수 있던 데이터만으로 매번 새로 판단하고, 그 판단을 이후 실제 시장에 "
     "적용해 성과를 쌓아가는’ 정직한 검증 방식입니다. 미래를 몰래 훔쳐보는 실수(Look-ahead)를 막습니다. "
     "이 리포트는 리밸런싱 시점마다 그 이전 데이터로만 비중을 정하고, 그 비중을 이후 실제 수익률에 "
     "적용하는 과정을 700번 넘게 반복합니다. 시험 볼 때 뒷장 정답을 절대 보지 않고 그날까지 배운 것만으로 "
     "매번 새로 푸는 것과 같습니다."),
    ('파라미터 민감도', 'sensitivity',
     "특정 설정값(예: 참고할 유사사례 개수 K=20/40/60) 하나에만 성과가 의존하지 않는지 확인하는 검사입니다. "
     "값을 넓게 바꿔도 성과가 비슷하게 유지되면 ‘우연히 특정 숫자에 맞춘 것(과적합)’이 아니라 "
     "튼튼한 전략이라는 뜻입니다."),
    ('부트스트랩 신뢰구간', 'bootstrap',
     "과거 수익 기록을 컴퓨터가 1,000번 무작위로 다시 섞어(블록 단위) 돌려보며, 성과가 어느 범위에 "
     "들어오는지 추정하는 방법입니다. 예: ‘CAGR 5~95% 구간이 +2%~+8%’라면, 미래에 사건 순서만 조금 "
     "달라져도 대략 이 범위의 성과가 나올 수 있다는 뜻입니다. 하나의 숫자를 맹신하지 않기 위한 장치입니다."),
    ('국면별 성과 분해', 'regimesplit',
     "코스피가 200일 이동평균선(MA200) 위에 있을 때(추세장)와 아래에 있을 때(역추세장)로 나눠, "
     "각 상황에서 전략이 어떻게 작동했는지 따로 보여줍니다. 상승장에서만 잘 되는지, 하락장 방어도 되는지 "
     "구분할 수 있습니다."),
    ('거래비용 민감도', 'costsens',
     "실제로 사고팔 때 드는 수수료·슬리피지(체결 미끄러짐)를 회당 0~0.3%까지 반영해도 성과가 유지되는지 "
     "확인하는 검사입니다. 비용을 넣어도 크게 나빠지지 않아야 현실적으로 쓸 수 있는 전략입니다."),
    ('CAGR', 'cagr',
     "연평균 복리 수익률(Compound Annual Growth Rate). 전체 기간의 성장을 ‘매년 몇 %씩 복리로 불었는가’로 "
     "환산한 값입니다. 예: CAGR +5%는 매년 평균 5% 복리 성장."),
    ('MDD', 'mdd',
     "최대 낙폭(Maximum Drawdown). 자산이 고점에서 저점까지 최대로 얼마나 빠졌는지(%)를 뜻합니다. "
     "-30%면 한때 고점 대비 30% 손실을 겪었다는 의미로, 위험(고통)의 크기를 나타냅니다."),
    ('Sharpe', 'sharpe',
     "샤프 지수. ‘위험(변동성) 한 단위당 얼마나 초과수익을 냈는가’입니다. 높을수록 같은 위험으로 더 많은 "
     "수익을 낸 것이라 효율이 좋습니다. 보통 1 이상이면 우수합니다."),
    ('Sortino', 'sortino',
     "소르티노 지수. 샤프와 비슷하지만 ‘하락 변동성’만 위험으로 봅니다. 올라서 생긴 변동은 벌점을 주지 않아, "
     "손실 위험 대비 효율을 더 잘 보여줍니다."),
    ('Calmar', 'calmar',
     "칼마 지수 = CAGR ÷ |MDD|. ‘얼마나 큰 낙폭을 견디고 그만큼 벌었는가’를 봅니다. 높을수록 낙폭 대비 "
     "수익 효율이 좋습니다."),
    ('변동성', 'vol',
     "수익률이 위아래로 흔들리는 정도(연율화 %). 클수록 급등락이 심해 위험이 큽니다."),
    ('RSI', 'rsi',
     "상대강도지수(0~100). 최근 상승·하락 압력의 균형을 보여줍니다. 통상 70 이상은 과열(과매수), "
     "30 이하는 침체(과매도)로 해석하지만, 이 시스템은 RSI 하나만으로 판단하지 않습니다."),
    ('이격도', 'disparity',
     "현재 가격이 이동평균선에서 얼마나 떨어져 있는지(%). 예: 20일 이격도 105%는 현재가가 20일 평균보다 "
     "5% 위에 있다는 뜻으로, 단기 과열/과매도 가늠에 씁니다."),
    ('ADX', 'adx',
     "추세강도지수(J.W. Wilder, 1978). 추세의 '방향'이 아니라 '힘'을 0~100으로 잽니다. 통상 20 미만은 "
     "무추세(횡보), 25 이상은 뚜렷한 추세, 40 이상은 강한 추세로 봅니다. 이 시스템은 ADX로 상승/하락장과 "
     "횡보·보합장을 먼저 가른 뒤, 200일선(Faber)·20% 룰·12개월 모멘텀으로 국면을 확정합니다."),
    ('수급 z', 'flowz',
     "외국인·기관의 순매수 강도를 과거 평균 대비 표준편차(z-score)로 나타낸 값입니다. +2면 평소보다 "
     "훨씬 강하게 사들이는 중, -2면 강하게 파는 중이라는 뜻입니다."),
    ('MFE/MAE', 'mfemae',
     "MFE(최대유리이동)는 보유 기간 중 최대로 올랐던 폭, MAE(최대불리이동)는 최대로 빠졌던 폭입니다. "
     "‘결국 +5%로 끝났어도 중간에 -10%까지 빠졌을 수 있다’는 경로상의 위험을 보여줍니다."),
    ('Direction', 'direction',
     "방향 점수 = 앞으로 오를 확률(%). 여러 기간(5·10·20·60일)의 상승확률을 가중 평균해 계산합니다."),
    ('기대수익', 'expret',
     "유사 사례들의 20일 뒤 수익률 ‘중앙값’입니다. 평균 대신 중앙값을 쓰는 이유는 한두 개의 극단값에 "
     "휘둘리지 않기 위해서입니다."),
    ('하방위험', 'downside',
     "나쁠 때 얼마나 빠질 수 있는지입니다. 유사 사례 하위 10% 수익률과 경로상 최대낙폭(MAE) 중 큰 쪽을 "
     "씁니다. 위험을 보수적으로 잡기 위함입니다."),
    ('신뢰도', 'confidence',
     "이 판단을 얼마나 믿을 수 있는지(0~100). 표본 수(N)가 많고, 방향이 일관되며, 결과 분포가 좁을수록 "
     "높아집니다. 신뢰도가 낮으면 권장비중이 중립(50%) 쪽으로 자동 수축합니다."),
    ('히스테리시스', 'hysteresis',
     "비중 변화가 ±10% 미만이면 무시하는 장치입니다. ‘70%→71%→70%’처럼 쓸데없이 자주 매매하는 것을 "
     "막아 거래비용과 피로를 줄입니다."),
    ('Look-ahead', 'lookahead',
     "‘미래 훔쳐보기’. 과거 시점을 판단할 때 그 이후 데이터를 (실수로) 쓰는 것입니다. 백테스트 성적을 "
     "가짜로 좋게 만들어 실전에서 무너지게 하는 가장 흔한 함정이며, 이 시스템은 이를 원천 차단합니다."),
    ('유사구간', 'analog',
     "지금의 시장 상태(수익률·이격도·RSI·수급 등 여러 지표의 조합)와 가장 비슷했던 과거의 날짜들입니다. "
     "‘그때 이후 실제로 어떻게 됐는가’가 이 시스템 예측의 핵심 근거입니다."),
    ('Forward Return', 'forward',
     "유사했던 과거 날짜 이후 1·3·5·10·20·60·120일 뒤에 실제로 시장이 얼마나 움직였는지(수익률)입니다."),
    ('B&H', 'bnh',
     "매수 후 보유(Buy & Hold). 아무 판단 없이 그냥 사서 계속 들고 있는 기준 전략으로, 우리 전략과 비교하는 "
     "잣대(벤치마크)입니다."),
    ('표본 수', 'nsamples',
     "통계에 사용된 유사 사례의 개수(N)입니다. N이 작으면(예: 5 이하) 결과가 우연일 수 있어 신뢰도가 "
     "낮아집니다. 항상 N과 함께 해석해야 합니다."),
    ('종합점수', 'composite',
     "방향(0.45)·기대수익(0.30)·위험(0.25)을 가중 합산한 0~100 점수입니다. 여기에 신뢰도와 투자성향을 "
     "곱해 최종 권장비중을 만듭니다."),
]
TERM2SLUG = {term: slug for term, slug, _ in GLOSSARY}



def _bar(value, lo=0, hi=100, width=20):
    frac = np.clip((value - lo) / (hi - lo), 0, 1)
    fill = int(round(frac * width))
    return '█' * fill + '░' * (width - fill)


def _combined_weight(markets: dict) -> float:
    ws = [m['alloc']['weight_pct'] for m in markets.values()]
    return round(float(np.mean(ws)), 1)


# ────────────────────────────── Markdown ──────────────────────────────
def build_markdown(analysis: dict) -> str:
    from datetime import datetime
    asof = analysis['asof'].strftime('%Y-%m-%d')
    gen = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    markets = analysis['markets']
    L = []
    L.append(f"# 시장 국면·유사구간 기반 주식비중 리포트")
    L.append(f"\n**기준일:** {asof}  |  **생성시각:** {gen}  |  "
             f"**분석 표본:** 과거 20년 일봉 + 투자자 수급\n")
    L.append("> 모든 통계는 기준일 이전 데이터만 사용([[Look-ahead]] 차단). "
             "AI 주관이 아니라 과거 [[유사구간]] 사례의 실제 결과를 근거로 한다. "
             "**밑줄 친 용어는 클릭하면 맨 아래 부록에서 쉬운 설명을 볼 수 있습니다.**\n")

    # ── 대시보드 ──
    L.append("## 1. MARKET DASHBOARD\n")
    for mk, m in markets.items():
        r, reg, al = m['row'], m['regime'], m['alloc']
        L.append(f"### {C.MARKETS[mk]['name']}")
        L.append(f"- 시장국면: **{reg['regime']}** "
                 f"(추세 {reg['trend_score']} / 모멘텀 {reg['momentum_score']} / 종합 {reg['composite_score']})")
        L.append(f"- 추세강도([[ADX]]): **{reg.get('trend_strength', '-')}** "
                 f"(ADX {reg.get('adx', float('nan'))}) · "
                 f"장기추세 {'200일선 위' if reg.get('above_ma200') else '200일선 아래'} · "
                 f"방향 {'상승(+DI≥-DI)' if reg.get('dmi_up') else '하락(-DI>+DI)'}")
        flags = []
        if reg['overheated']:
            flags.append('과열')
        if reg['oversold']:
            flags.append('과매도·침체')
        L.append(f"- 상태: {reg['vol_regime']}{' · ' + ', '.join(flags) if flags else ''}")
        L.append(f"- [[RSI]]14: {r.get('rsi14', float('nan')):.1f}  |  "
                 f"20일[[이격도]]: {r.get('disp20', float('nan')):.1f}%  |  "
                 f"120일[[MDD]]: {r.get('mdd120', float('nan')):.1f}%  |  "
                 f"20일[[변동성]]: {r.get('vol20', float('nan')):.1f}%")
        fz = r.get('foreign_z20', float('nan'))
        iz = r.get('inst_z20', float('nan'))
        L.append(f"- 외국인 [[수급 z]](20일): {fz:+.2f}  |  기관 수급z(20일): {iz:+.2f}")
        L.append(f"- 권장 주식비중: **{al['weight_pct']:.0f}%** ({al['band']})  "
                 f"`{_bar(al['weight_pct'])}`")
        L.append("")

    combined = _combined_weight(markets)
    L.append(f"### 종합 권장 주식비중: **{combined:.0f}%**\n")

    # ── 시장별 상세 + 유사구간 + Forward ──
    for mk, m in markets.items():
        name = C.MARKETS[mk]['name']
        an, al = m['analog'], m['alloc']
        L.append(f"## 2. {name} 상세 분석\n")
        L.append(f"- 유사 사례 수([[표본 수]] N): {an['n_analogs']}  |  통계 [[신뢰도]]: "
                 f"{'충분' if al['reliable'] else '낮음(표본 부족)'} "
                 f"(confidence {al['confidence']:.0f}/100)")
        L.append(f"- [[Direction]](상승확률): {al['direction']:.0f}%  |  "
                 f"[[기대수익]](중앙값 {C.ALLOC['primary_horizon']}일): {al['expected_return']:+.2f}%  |  "
                 f"예상 [[하방위험]]: {al['risk']:+.2f}%\n")

        # Forward Return 표
        L.append("**[[Forward Return]] 분포 (유사 사례 기준)**\n")
        L.append("| 구간 | N | 평균 | 중앙값 | 상승확률 | +5%↑ | -5%↓ | 하위10% | 상위10% |")
        L.append("|---|---|---|---|---|---|---|---|---|")
        for h in C.FORWARD_HORIZONS:
            s = an['forward'].get(h, {})
            if s.get('n', 0) == 0:
                L.append(f"| {HORIZON_LABEL[h]} | 0 | - | - | - | - | - | - | - |")
                continue
            L.append(f"| {HORIZON_LABEL[h]} | {s['n']} | {s['mean']:+.2f}% | {s['median']:+.2f}% | "
                     f"{s['prob_up']:.0f}% | {s['prob_up5']:.0f}% | {s['prob_dn5']:.0f}% | "
                     f"{s['p10']:+.1f}% | {s['p90']:+.1f}% |")
        L.append("")

        exc = m['analog'].get('excursion', {})
        if exc.get('n', 0):
            L.append(f"- 경로상 위험([[MFE/MAE]], D+{C.ALLOC['primary_horizon']}): "
                     f"평균 최대상승 {exc['mfe_mean']:+.1f}% / "
                     f"평균 최대하락 {exc['mae_mean']:+.1f}% / 최악 {exc['mae_worst']:+.1f}%\n")

        # 유사 Top 사례 — 날짜 + 당시 국면 + 이후 실제 결과
        detail = m['analog'].get('analog_detail', [])[:15]
        if detail:
            L.append("**현재와 가장 유사했던 과거 Top 15 (그 이후 실제 결과 포함)**  "
                     "*그날의 지표·다구간 실제수익 상세표는 하단 부록 B 참조*\n")
            L.append("| 순위 | 유사날짜 | 당시 국면 | 거리 | 이후 20일 실제 | 이후 60일 실제 |")
            L.append("|---|---|---|---|---|---|")
            for i, d in enumerate(detail, 1):
                r20 = f"{d['ret20']:+.1f}%" if d['ret20'] is not None else '-'
                r60 = f"{d['ret60']:+.1f}%" if d['ret60'] is not None else '-'
                L.append(f"| {i} | {d['date'].strftime('%Y-%m-%d')} | {d['regime']} | "
                         f"{d['distance']:.2f} | {r20} | {r60} |")
            L.append("")

        # 상승/하락을 가른 변수
        disc = m['analog'].get('discriminator')
        if disc is not None and len(disc):
            L.append(f"**상승/하락을 가른 변수 (상승 {disc.attrs.get('n_up','?')} vs "
                     f"하락 {disc.attrs.get('n_dn','?')})**\n")
            L.append("| Feature | 상승사례 평균 | 하락사례 평균 | 표준화차이 |")
            L.append("|---|---|---|---|")
            for feat_name, row in disc.head(6).iterrows():
                L.append(f"| {feat_name} | {row['상승사례_평균']:.2f} | "
                         f"{row['하락사례_평균']:.2f} | {row['표준화차이']:+.2f} |")
            L.append("")

    # ── 백테스트 ──
    bt = analysis.get('backtest')
    if bt:
        L.append("## 3. [[워크포워드]] 포트폴리오 백테스트\n")
        L.append(f"- 기간: {bt['period']}  |  리밸런싱: {bt['rebalance_days']}거래일마다 "
                 f"(각 시점 이전 데이터만 사용)")
        L.append(f"- **검증 규모**: 리밸런싱(의사결정) **{bt['n_rebalances']}회** × 2시장 = "
                 f"유사구간 검색 **{bt['n_analog_searches']:,}회**, "
                 f"서로 다른 전략 시뮬레이션 **{bt['n_strategy_sims']}종**")
        L.append("- 각 리밸런싱은 '그 시점에 알 수 있던 데이터만'으로 새로 판단한 독립 Out-of-Sample 테스트입니다.\n")

        L.append("**전략별 성과 비교** (성향 3종 + 단순 baseline + [[B&H]] 등 벤치마크 5종)\n")
        L.append("| 전략 | 총수익 | [[CAGR]] | [[변동성]] | [[Sharpe]] | [[Sortino]] | [[MDD]] | [[Calmar]] | 승률 |")
        L.append("|---|---|---|---|---|---|---|---|---|")
        for name, mm in bt['metrics'].items():
            if not mm:
                continue
            L.append(f"| {name} | {mm['total_return']:+.0f}% | {mm['cagr']:+.1f}% | {mm['vol']:.1f}% | "
                     f"{mm['sharpe']:.2f} | {mm['sortino']:.2f} | {mm['mdd']:.0f}% | "
                     f"{mm['calmar']:.2f} | {mm['win_rate']:.0f}% |")
        L.append("")

        # 파라미터 민감도
        sens = bt.get('sensitivity')
        if sens:
            L.append("**[[파라미터 민감도]] — 유사사례 수 K (균형형)**  "
                     "*넓은 범위에서 성과가 유지되면 과적합이 아님*\n")
            L.append("| K(유사사례 수) | CAGR | MDD | Sharpe | Calmar |")
            L.append("|---|---|---|---|---|")
            for K, s in sens.items():
                L.append(f"| {K} | {s['cagr']:+.1f}% | {s['mdd']:.0f}% | {s['sharpe']:.2f} | {s['calmar']:.2f} |")
            L.append("")

        # 연도별
        ann = bt.get('annual')
        if ann:
            L.append("**연도별 성과 (균형형 vs 코스피)**\n")
            L.append("| 연도 | 균형형 | 코스피 |")
            L.append("|---|---|---|")
            for y, a in ann.items():
                L.append(f"| {y} | {a['bal']:+.1f}% | {a['kospi']:+.1f}% |")
            L.append("")

        # 부트스트랩
        bs = bt.get('bootstrap')
        if bs:
            L.append(f"**[[부트스트랩 신뢰구간]] (균형형, {bs['n_iter']}회 블록 리샘플링)**\n")
            L.append(f"- CAGR: 중앙값 {bs['cagr_p50']:+.1f}% "
                     f"(5~95%: {bs['cagr_p5']:+.1f}% ~ {bs['cagr_p95']:+.1f}%)")
            L.append(f"- MDD: 중앙값 {bs['mdd_p50']:.0f}% "
                     f"(5~95%: {bs['mdd_p95']:.0f}% ~ {bs['mdd_p5']:.0f}%)")
            L.append("- 미래 경로가 과거와 순서만 달라도 이 범위 정도의 성과 변동이 가능함을 의미합니다.\n")

        # 거래비용 민감도
        cost = bt.get('cost')
        if cost:
            L.append("**[[거래비용 민감도]] (균형형, 회전율×수수료)**  "
                     "*비용을 반영해도 성과가 유지되는지 확인*\n")
            L.append("| 회당 비용 | CAGR | MDD | Sharpe | Calmar |")
            L.append("|---|---|---|---|---|")
            for fee, c in cost.items():
                L.append(f"| {fee*100:.1f}% | {c['cagr']:+.1f}% | {c['mdd']:.0f}% | "
                         f"{c['sharpe']:.2f} | {c['calmar']:.2f} |")
            L.append("")

        # 국면별 성과 분해
        reg = bt.get('regime')
        if reg:
            L.append("**[[국면별 성과 분해]] (균형형, 코스피 MA200 기준)**  "
                     "*추세장/역추세장에서 각각 어떻게 작동했는지*\n")
            L.append("| 국면 | 리밸런싱 횟수 | 회당 평균수익 | 승률 | 누적수익 |")
            L.append("|---|---|---|---|---|")
            for label, r in reg.items():
                L.append(f"| {label} | {r['n']}회 | {r['avg']:+.2f}% | "
                         f"{r['win_rate']:.0f}% | {r['cum']:+.1f}% |")
            L.append("")

        # 이격도 × 이동평균 전략 그리드
        disp = bt.get('disparity')
        if disp and disp.get('cells'):
            cells = disp['cells']
            periods = disp['periods']
            ths = disp['thresholds']
            L.append("**[[이격도]] × 이동평균선 전략 그리드**  "
                     f"*이동평균 {len(periods)}종(MA{periods[0]}~MA{periods[-1]}) × "
                     f"[[이격도]] 임계값 {len(ths)}종({ths[0]}~{ths[-1]}) = {len(cells)}개 조합. "
                     "규칙: 가격>MA 이면서 이격도≤임계값(과열 아님)일 때만 100% 노출*\n")

            # CAGR 매트릭스 (행=이동평균, 열=이격도 임계값)
            L.append("_CAGR 매트릭스_ (행=이동평균선, 열=이격도 임계값)\n")
            L.append("| MA＼이격 | " + " | ".join(f"≤{t}" for t in ths) + " |")
            L.append("|" + "---|" * (len(ths) + 1))
            for p in periods:
                row = [f"MA{p}"]
                for t in ths:
                    c = cells.get(f'MA{p}·이격≤{t}')
                    row.append(f"{c['cagr']:+.1f}%" if c else "-")
                L.append("| " + " | ".join(row) + " |")
            L.append("")

            # Sharpe 매트릭스
            L.append("_Sharpe 매트릭스_ (행=이동평균선, 열=이격도 임계값)\n")
            L.append("| MA＼이격 | " + " | ".join(f"≤{t}" for t in ths) + " |")
            L.append("|" + "---|" * (len(ths) + 1))
            for p in periods:
                row = [f"MA{p}"]
                for t in ths:
                    c = cells.get(f'MA{p}·이격≤{t}')
                    row.append(f"{c['sharpe']:.2f}" if c else "-")
                L.append("| " + " | ".join(row) + " |")
            L.append("")

            # 최고 성과 조합 요약
            best = max(cells.items(), key=lambda kv: kv[1]['sharpe'])
            bn, bm = best
            L.append(f"- 이 그리드에서 Sharpe 최고 조합: **{bn}** "
                     f"(CAGR {bm['cagr']:+.1f}% / MDD {bm['mdd']:.0f}% / "
                     f"Sharpe {bm['sharpe']:.2f} / Calmar {bm['calmar']:.2f} / "
                     f"평균투자비중 {bm['invested']:.0f}%)\n")

    # ── 최종 해석 ──
    L.append("## 4. 종합 해석\n")
    L.append(_interpretation(analysis))

    # ── 경고 ──
    if analysis.get('warnings'):
        L.append("\n## 데이터 검증 경고\n")
        for w in analysis['warnings']:
            L.append(f"- {w}")

    L.append("\n---\n*본 리포트는 과거 데이터 기반 통계이며 미래 수익을 보장하지 않습니다. "
             "표본 수(N)와 신뢰도를 반드시 함께 확인하세요.*")
    return '\n'.join(L)


def _interpretation(analysis: dict) -> str:
    markets = analysis['markets']
    parts = []
    for mk, m in markets.items():
        name = C.MARKETS[mk]['name']
        reg, al = m['regime'], m['alloc']
        h = C.ALLOC['primary_horizon']
        s = m['analog']['forward'].get(h, {})
        if s.get('n', 0) == 0:
            parts.append(f"- **{name}**: 유사 표본이 부족하여 통계적 신뢰도가 낮습니다. 중립 비중을 권고합니다.")
            continue
        direction = al['direction']
        conf = '높음' if al['reliable'] and al['confidence'] >= 50 else '낮음'
        risk_txt = f"하위 10% 사례에서는 {s['p10']:+.1f}% 수준의 하락도 관찰"
        row = m['row']
        mdd120 = row.get('mdd120', 0.0)
        ret60 = row.get('ret60', 0.0)
        caution = ''
        if reg['regime'] == '하락후 반등':
            caution = (f" ⚠️ 다만 장기추세 필터(200일선, Faber 2007) 아래에 있고 최근 120일 낙폭 "
                       f"{mdd120:.0f}%·60일 수익률 {ret60:+.0f}%로 20% 룰상 약세장 국면이 해소되지 "
                       "않은 **약세장 내 되돌림(bear-market rally)** 구간입니다. Dow 이론의 1차(하락) "
                       "추세는 더 높은 고점이 확인되기 전까지 유효하므로, 단기 반등을 상승장으로 "
                       "단정하지 말고 되돌림 위험을 함께 보세요.")
        parts.append(
            f"- **{name}**: 현재 국면은 **{reg['regime']}**이며, 과거 유사 {s['n']}개 사례에서 "
            f"{h}일 후 상승확률은 {s['prob_up']:.0f}%, 중앙값 수익률은 {s['median']:+.1f}%였습니다. "
            f"다만 {risk_txt}되어 위험도 존재합니다. 신뢰도는 {conf}이며, "
            f"이를 종합한 권장 주식비중은 **{al['weight_pct']:.0f}%**입니다.{caution}")
    combined = _combined_weight(markets)
    parts.append(f"\n**종합**: 두 시장을 합산한 권장 주식비중은 **{combined:.0f}%**입니다. "
                 "이는 방향(상승확률)·기대수익·하방위험·표본 신뢰도를 분리 계산한 뒤 "
                 "위험조정 노출로 산출한 값이며, 신뢰도가 낮을수록 중립(50%)에 가깝게 수축됩니다.")
    return '\n'.join(parts)


# ────────────────────────────── Charts ──────────────────────────────
def make_charts(analysis: dict, outdir: str) -> dict:
    paths = {}
    # Forward 경로 (코스피 우선)
    for mk, m in analysis['markets'].items():
        path = m['analog'].get('path60')
        if not path:
            continue
        fig, ax = plt.subplots(figsize=(7, 4))
        days = path['days']
        ax.fill_between(days, path['p10'], path['p90'], alpha=0.15, color='steelblue', label='10~90%')
        ax.fill_between(days, path['p25'], path['p75'], alpha=0.3, color='steelblue', label='25~75%')
        ax.plot(days, path['median'], color='navy', lw=2, label='중앙값 경로')
        ax.axhline(0, color='gray', lw=0.8)
        ax.set_title(f"{C.MARKETS[mk]['name']} 유사구간 이후 60일 경로 (N={path['n']})")
        ax.set_xlabel('경과 거래일'); ax.set_ylabel('누적수익률 (%)'); ax.legend(fontsize=8)
        fig.tight_layout()
        p = os.path.join(outdir, f'path_{mk}.png')
        fig.savefig(p, dpi=110); plt.close(fig)
        paths[f'path_{mk}'] = p

    # 개별 유사사례 경로(스파게티) — 각 사례가 이후 60일 어떻게 움직였나
    for mk, m in analysis['markets'].items():
        path = m['analog'].get('path60')
        if not path or not path.get('paths'):
            continue
        cases = path['paths']
        days = path['days']
        fig, ax = plt.subplots(figsize=(7, 4))
        n_up = n_dn = 0
        for cp in cases:
            up = cp[-1] >= 0
            n_up += up; n_dn += (not up)
            ax.plot(days, cp, lw=0.7, alpha=0.35,
                    color='#c0392b' if up else '#2c6fbb')
        ax.plot(days, path['median'], color='black', lw=2.4, label='중앙값')
        ax.axhline(0, color='gray', lw=0.8)
        ax.set_title(f"{C.MARKETS[mk]['name']} 개별 유사사례 이후 60일 경로 "
                     f"(빨강=상승 {n_up} / 파랑=하락 {n_dn})")
        ax.set_xlabel('경과 거래일'); ax.set_ylabel('누적수익률 (%)'); ax.legend(fontsize=8)
        fig.tight_layout()
        p = os.path.join(outdir, f'cases_{mk}.png')
        fig.savefig(p, dpi=110); plt.close(fig)
        paths[f'cases_{mk}'] = p

    # 자산곡선
    bt = analysis.get('backtest')
    if bt:
        fig, ax = plt.subplots(figsize=(8, 4.2))
        dates = pd.to_datetime(bt['dates'])
        for name in ['균형형', '공격형', '안정형', '50:50 B&H', '코스피 B&H']:
            mm = bt['metrics'].get(name)
            if mm and mm.get('equity'):
                eq = mm['equity']
                ax.plot(dates[:len(eq)], eq, label=name, lw=1.8 if name == '균형형' else 1.0)
        ax.set_title('Walk-forward 자산곡선 (초기=1.0)')
        ax.set_ylabel('누적 배수'); ax.legend(fontsize=8); ax.grid(alpha=0.3)
        fig.tight_layout()
        p = os.path.join(outdir, 'equity_curve.png')
        fig.savefig(p, dpi=110); plt.close(fig)
        paths['equity'] = p
    return paths


# ────────────────────────────── HTML ──────────────────────────────
def build_appendix(analysis: dict) -> str:
    """부록 HTML — ① 비중 산출 상세 근거(시장별) + ② 초보자용 용어 사전.
    모두 <details>로 접혀 있고, 본문의 밑줄 용어를 클릭하면 해당 항목이 열린다."""
    import html as _html
    P = []
    P.append('<h2 id="appendix">📖 부록 · 상세 근거와 용어 사전 (초보자용)</h2>')
    P.append('<p class="apx-note">아래 항목의 제목을 클릭하면 펼쳐집니다. '
             '본문에서 <a class="term" href="#appendix">밑줄 친 용어</a>를 클릭하면 '
             '해당 설명으로 자동 이동·펼쳐집니다.</p>')

    # ── A. 비중 산출 근거 (왜 이 비중인가) ──
    P.append('<h3>A. 왜 이 주식비중이 나왔나 (시장별 계산 근거)</h3>')
    for mk, m in analysis['markets'].items():
        name = C.MARKETS[mk]['name']
        al = m['alloc']
        reg = m['regime']
        comp = al.get('composite', 50.0)
        conf = al.get('confidence', 0.0)
        shrink = (comp - 50) * (conf / 100.0)
        body = [
            f'<p><b>현재 국면:</b> {_html.escape(reg["regime"])} · '
            f'<b>유사사례 N:</b> {al.get("n", 0)}개 · '
            f'<b>신뢰도:</b> {conf:.0f}/100 '
            f'({"충분" if al.get("reliable") else "낮음(표본 부족)"})</p>',
            '<p>4가지 요소를 따로 계산한 뒤 합쳐 비중을 만듭니다:</p>',
            '<ol>',
            f'<li><b>방향(Direction)</b> = 상승확률 <b>{al["direction"]:.0f}%</b> '
            '— 여러 기간(5·10·20·60일) 상승확률의 가중 평균</li>',
            f'<li><b>기대수익</b> = 20일 뒤 수익률 중앙값 <b>{al["expected_return"]:+.2f}%</b> '
            '— 극단값에 강건한 중앙값 사용</li>',
            f'<li><b>하방위험</b> = <b>{al["risk"]:+.2f}%</b> '
            '— 하위 10% 수익률과 경로상 최대낙폭 중 나쁜 쪽</li>',
            f'<li><b>신뢰도</b> = <b>{conf:.0f}/100</b> '
            '— 표본 수·방향 일관성·분포 산포로 산출</li>',
            '</ol>',
            f'<p><b>종합점수</b> = 0.45×방향 + 0.30×수익 + 0.25×위험 = '
            f'<b>{comp:.0f}/100</b></p>',
            f'<p><b>신뢰도 수축</b>: 중립 50에서 (종합−50)×(신뢰도/100) = '
            f'({comp:.0f}−50)×{conf:.0f}% = <b>{shrink:+.1f}</b> 만큼 이동 '
            f'→ 최종 <b>50 {shrink:+.1f}</b> ≈ <b>권장 주식비중 {al["weight_pct"]:.0f}%</b> '
            f'({_html.escape(al["band"])})</p>',
            '<p class="apx-hint">💡 신뢰도가 낮을수록 결과가 50%(중립)에 가깝게 수축합니다. '
            '데이터가 확실하지 않으면 “잘 모르니 중간만 가자”가 되도록 설계했습니다.</p>',
        ]
        P.append(f'<details class="reason" id="why-{mk}">'
                 f'<summary>▶ {_html.escape(name)} — 권장비중 '
                 f'{al["weight_pct"]:.0f}% 가 나온 과정</summary>'
                 f'<div class="apx-body">{"".join(body)}</div></details>')

    # ── B. 유사사례 상세 (Top 15의 그날 지표 + 이후 실제 결과) ──
    P.append('<h3>B. 유사사례 상세 — 그날은 어떤 상황이었고, 이후 실제로 어떻게 됐나</h3>')
    P.append('<p class="apx-note">본문 Top 15의 각 사례를 더 자세히 봅니다. '
             '“그날의 시장 지표”와 “이후 실제 수익률(여러 기간)”을 함께 보여주므로, '
             '지금과 비슷했던 과거가 실제로 어떻게 흘러갔는지 확인할 수 있습니다. '
             '<b>+Nd</b>는 해당일로부터 N거래일 뒤 실제 수익률이며, ‘-’는 아직 그만큼 시간이 '
             '지나지 않아 실현되지 않은 경우입니다.</p>')

    def _fmt(v, suf='', sign=False):
        if v is None:
            return '-'
        return (f'{v:+.1f}{suf}' if sign else f'{v:.1f}{suf}')

    for mk, m in analysis['markets'].items():
        name = C.MARKETS[mk]['name']
        detail = m['analog'].get('analog_detail', [])[:15]
        if not detail:
            continue
        rows = ['<table class="apx-table"><tr>'
                '<th>#</th><th>유사날짜</th><th>당시 국면</th><th>거리</th>'
                '<th>RSI</th><th>이격20</th><th>이격60</th>'
                '<th>외국인z</th><th>기관z</th><th>120MDD</th>'
                '<th>+5d</th><th>+10d</th><th>+20d</th><th>+60d</th><th>+120d</th></tr>']
        for i, d in enumerate(detail, 1):
            ind = d.get('indicators', {})
            fwd = d.get('forward', {})

            def _cell(v, sign=False):
                if v is None:
                    return '<td>-</td>'
                return f'<td>{v:+.1f}</td>' if sign else f'<td>{v:.1f}</td>'
            rows.append(
                '<tr>'
                f'<td>{i}</td><td>{d["date"].strftime("%Y-%m-%d")}</td>'
                f'<td>{_html.escape(d["regime"])}</td><td>{d["distance"]:.2f}</td>'
                f'{_cell(ind.get("rsi14"))}{_cell(ind.get("disp20"))}{_cell(ind.get("disp60"))}'
                f'{_cell(ind.get("foreign_z20"), True)}{_cell(ind.get("inst_z20"), True)}'
                f'{_cell(ind.get("mdd120"), True)}'
                f'{_cell(fwd.get(5), True)}{_cell(fwd.get(10), True)}{_cell(fwd.get(20), True)}'
                f'{_cell(fwd.get(60), True)}{_cell(fwd.get(120), True)}'
                '</tr>')
        rows.append('</table>')
        P.append(f'<details class="reason" id="cases-{mk}" open>'
                 f'<summary>▶ {_html.escape(name)} — 유사 Top 15 상세표</summary>'
                 f'<div class="apx-body">{"".join(rows)}</div></details>')

    # ── C. 용어 사전 ──
    P.append('<h3>C. 용어 사전 — 어려운 말 쉽게</h3>')
    for term, slug, desc in GLOSSARY:
        P.append(
            f'<details class="glossary" id="gl-{slug}">'
            f'<summary>{_html.escape(term)}</summary>'
            f'<div class="apx-body">{_html.escape(desc)}</div></details>')
    return '\n'.join(P)


def build_html(md_text: str, chart_paths: dict, outdir: str,
               appendix_html: str = '') -> str:
    import html as _html
    body = _md_to_html(md_text)
    imgs = ''
    for key, label in [('path_KOSPI', '코스피 유사구간 경로(분위수 밴드)'),
                       ('cases_KOSPI', '코스피 개별 유사사례 경로'),
                       ('path_KOSDAQ', '코스닥 유사구간 경로(분위수 밴드)'),
                       ('cases_KOSDAQ', '코스닥 개별 유사사례 경로'),
                       ('equity', 'Walk-forward 자산곡선')]:
        if key in chart_paths:
            rel = os.path.basename(chart_paths[key])
            imgs += f'<figure><img src="{rel}" alt="{label}"><figcaption>{_html.escape(label)}</figcaption></figure>\n'
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>시장 국면·유사구간 리포트</title>
<style>
 body{{font-family:'Malgun Gothic',sans-serif;max-width:1000px;margin:24px auto;padding:0 18px;color:#1a1a2e;line-height:1.6}}
 h1{{border-bottom:3px solid #16213e;padding-bottom:8px}}
 h2{{margin-top:32px;border-left:5px solid #0f3460;padding-left:10px}}
 h3{{color:#0f3460}}
 table{{border-collapse:collapse;width:100%;margin:12px 0;font-size:13px}}
 th,td{{border:1px solid #ccc;padding:6px 9px;text-align:center}}
 th{{background:#0f3460;color:#fff}}
 tr:nth-child(even){{background:#f5f6fa}}
 blockquote{{background:#eef3fb;border-left:4px solid #4a69bd;padding:8px 14px;color:#333}}
 code{{background:#eef;padding:1px 5px;border-radius:3px;font-family:Consolas,monospace}}
 figure{{margin:18px 0;text-align:center}} img{{max-width:100%;border:1px solid #ddd;border-radius:6px}}
 figcaption{{color:#555;font-size:13px;margin-top:4px}}
 a.term{{color:#0f3460;text-decoration:underline dotted #4a69bd;cursor:pointer;font-weight:600}}
 a.term:hover{{background:#eef3fb}}
 th a.term{{color:#fff;text-decoration:underline dotted #cfe0f5}}
 th a.term:hover{{background:#1b4a7a}}
 .apx-note{{color:#555;font-size:13px}}
 .apx-hint{{color:#0f3460;background:#eef3fb;padding:6px 10px;border-radius:4px;font-size:13px}}
 details.glossary,details.reason{{border:1px solid #d5dbe6;border-radius:6px;margin:8px 0;background:#fafbfe}}
 details.glossary>summary,details.reason>summary{{cursor:pointer;padding:9px 12px;font-weight:700;color:#0f3460}}
 details[open]>summary{{border-bottom:1px solid #d5dbe6;background:#eef3fb}}
 .apx-body{{padding:10px 14px;font-size:14px}}
 .apx-table{{font-size:12px}} .apx-table th{{background:#274b7a}}
 details.glossary:target,details.reason:target{{border-color:#e67e22;box-shadow:0 0 0 2px #f6d5b3}}
 details.glossary:target>summary{{background:#fdebd0}}
</style></head><body>
{body}
<h2>차트</h2>
{imgs}
{appendix_html}
<script>
 // 밑줄 용어 클릭 → 부록의 해당 항목을 펼치고 스크롤
 function openTarget(){{
   var h=location.hash; if(!h) return;
   var el=document.querySelector(h);
   if(el && el.tagName==='DETAILS'){{ el.open=true;
     el.scrollIntoView({{behavior:'smooth',block:'center'}}); }}
 }}
 window.addEventListener('hashchange', openTarget);
 window.addEventListener('load', openTarget);
 document.querySelectorAll('a.term').forEach(function(a){{
   a.addEventListener('click', function(){{ setTimeout(openTarget, 30); }});
 }});
</script>
</body></html>"""



def _md_to_html(md: str) -> str:
    """의존성 없는 경량 Markdown→HTML (제목/표/목록/굵게/코드)."""
    import html as _html
    lines = md.split('\n')
    out, in_table, in_list = [], False, False

    def close_list():
        nonlocal in_list
        if in_list:
            out.append('</ul>'); in_list = False

    i = 0
    while i < len(lines):
        ln = lines[i]
        # 표
        if ln.startswith('|'):
            rows = []
            while i < len(lines) and lines[i].startswith('|'):
                rows.append(lines[i]); i += 1
            close_list()
            out.append('<table>')
            for ri, row in enumerate(rows):
                cells = [c.strip() for c in row.strip('|').split('|')]
                if ri == 1 and set(''.join(cells)) <= set('-: '):
                    continue
                tag = 'th' if ri == 0 else 'td'
                out.append('<tr>' + ''.join(
                    f'<{tag}>{_inline(c)}</{tag}>' for c in cells) + '</tr>')
            out.append('</table>')
            continue
        if ln.startswith('### '):
            close_list(); out.append(f'<h3>{_inline(ln[4:])}</h3>')
        elif ln.startswith('## '):
            close_list(); out.append(f'<h2>{_inline(ln[3:])}</h2>')
        elif ln.startswith('# '):
            close_list(); out.append(f'<h1>{_inline(ln[2:])}</h1>')
        elif ln.startswith('> '):
            close_list(); out.append(f'<blockquote>{_inline(ln[2:])}</blockquote>')
        elif ln.startswith('- '):
            if not in_list:
                out.append('<ul>'); in_list = True
            out.append(f'<li>{_inline(ln[2:])}</li>')
        elif ln.strip() == '---':
            close_list(); out.append('<hr>')
        elif ln.strip() == '':
            close_list()
        else:
            close_list(); out.append(f'<p>{_inline(ln)}</p>')
        i += 1
    close_list()
    return '\n'.join(out)


def _inline(text: str) -> str:
    import re, html as _html
    t = _html.escape(text)
    t = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', t)
    t = re.sub(r'`(.+?)`', r'<code>\1</code>', t)

    # [[용어]] → 부록 용어사전으로 가는 클릭 가능한 링크
    def _term(m):
        term = m.group(1)
        slug = TERM2SLUG.get(term)
        if not slug:
            return term
        return (f'<a class="term" href="#gl-{slug}" '
                f'title="클릭하면 부록에서 쉬운 설명을 볼 수 있어요">{term}</a>')
    t = re.sub(r'\[\[(.+?)\]\]', _term, t)
    return t


def _strip_terms(md: str) -> str:
    """.md 파일 저장용 — [[용어]] 표기를 일반 텍스트로 되돌린다."""
    import re
    return re.sub(r'\[\[(.+?)\]\]', r'\1', md)



# ────────────────────────────── Excel ──────────────────────────────
def write_excel(analysis: dict, path: str) -> None:
    with pd.ExcelWriter(path, engine='openpyxl') as xl:
        # Summary
        rows = []
        for mk, m in analysis['markets'].items():
            al, reg = m['alloc'], m['regime']
            rows.append({
                '시장': C.MARKETS[mk]['name'], '국면': reg['regime'],
                '상승확률': al['direction'], '기대수익': al['expected_return'],
                '위험': al['risk'], '신뢰도': al['confidence'],
                '권장비중%': al['weight_pct'], 'N': al.get('n', 0),
            })
        pd.DataFrame(rows).to_excel(xl, sheet_name='Summary', index=False)

        for mk, m in analysis['markets'].items():
            name = C.MARKETS[mk]['name']
            fr = []
            for h in C.FORWARD_HORIZONS:
                s = m['analog']['forward'].get(h, {})
                if s.get('n', 0):
                    fr.append({'구간': HORIZON_LABEL[h], **s})
            if fr:
                pd.DataFrame(fr).to_excel(xl, sheet_name=f'{mk}_Forward', index=False)
            dts = m['analog'].get('analog_detail', [])
            if dts:
                def _r(v):
                    return round(v, 2) if v is not None else None
                pd.DataFrame([{
                    '유사날짜': d['date'].strftime('%Y-%m-%d'),
                    '당시국면': d['regime'],
                    '거리': round(d['distance'], 3),
                    'RSI14': _r(d.get('indicators', {}).get('rsi14')),
                    '이격도20': _r(d.get('indicators', {}).get('disp20')),
                    '이격도60': _r(d.get('indicators', {}).get('disp60')),
                    '외국인z20': _r(d.get('indicators', {}).get('foreign_z20')),
                    '기관z20': _r(d.get('indicators', {}).get('inst_z20')),
                    '120MDD': _r(d.get('indicators', {}).get('mdd120')),
                    '이후5일%': _r(d.get('forward', {}).get(5)),
                    '이후10일%': _r(d.get('forward', {}).get(10)),
                    '이후20일%': _r(d.get('forward', {}).get(20)),
                    '이후60일%': _r(d.get('forward', {}).get(60)),
                    '이후120일%': _r(d.get('forward', {}).get(120)),
                } for d in dts]).to_excel(xl, sheet_name=f'{mk}_Similar', index=False)

        bt = analysis.get('backtest')
        if bt:
            btrows = [{'전략': k, **{kk: vv for kk, vv in v.items() if kk != 'equity'}}
                      for k, v in bt['metrics'].items() if v]
            pd.DataFrame(btrows).to_excel(xl, sheet_name='Backtest', index=False)
            if bt.get('sensitivity'):
                pd.DataFrame([{'K': k, **v} for k, v in bt['sensitivity'].items()]).to_excel(
                    xl, sheet_name='Backtest_민감도', index=False)
            if bt.get('annual'):
                pd.DataFrame([{'연도': y, **a} for y, a in bt['annual'].items()]).to_excel(
                    xl, sheet_name='Backtest_연도별', index=False)
            if bt.get('cost'):
                pd.DataFrame([{'회당비용%': round(f*100, 1), **c}
                              for f, c in bt['cost'].items()]).to_excel(
                    xl, sheet_name='Backtest_거래비용', index=False)
            if bt.get('regime'):
                pd.DataFrame([{'국면': k, **v} for k, v in bt['regime'].items()]).to_excel(
                    xl, sheet_name='Backtest_국면별', index=False)
            if bt.get('disparity') and bt['disparity'].get('cells'):
                pd.DataFrame([{'전략': k, **v}
                              for k, v in bt['disparity']['cells'].items()]).to_excel(
                    xl, sheet_name='Backtest_이격도', index=False)


def generate(analysis: dict, outdir: str) -> dict:
    os.makedirs(outdir, exist_ok=True)
    tag = analysis['asof'].strftime('%Y%m%d')
    md = build_markdown(analysis)
    md_path = os.path.join(outdir, f'시장비중리포트_{tag}.md')
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(_strip_terms(md))   # .md 파일은 [[용어]] 표기를 일반 텍스트로

    charts = make_charts(analysis, outdir)
    appendix = build_appendix(analysis)
    html = build_html(md, charts, outdir, appendix)
    html_path = os.path.join(outdir, f'시장비중리포트_{tag}.html')
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)

    xlsx_path = os.path.join(outdir, f'시장비중리포트_{tag}.xlsx')
    try:
        write_excel(analysis, xlsx_path)
    except Exception as e:
        xlsx_path = f'(엑셀 생성 실패: {e})'

    return {'markdown': md_path, 'html': html_path, 'excel': xlsx_path, 'charts': charts}
