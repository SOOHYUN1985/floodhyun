"""
핵심 브리핑 생성기 — 딱 이것만 보면 된다
- 코스피·코스닥 핵심 정보를 1페이지로 압축
- 과열점수 / 현재 낙폭 / 즉시 행동 / 시나리오만 표시
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Dict, Optional

from config import DAILY_BACKTEST_DIR as REPORTS_DIR


# ──────────────────────────────────────────────────────────
# 유틸
# ──────────────────────────────────────────────────────────

def _trend_badge(t: str) -> str:
    return {"bull": "📈 상승장", "sideways": "↔️ 횡보장", "bear": "📉 하락장"}.get(t, "❓")

def _heat_label(score: float) -> str:
    if score >= 75: return "🔴 과열"
    if score >= 60: return "🟡 주의"
    if score >= 40: return "🟢 정상"
    return "🔵 과매도"

def _dd_label(dd: float) -> str:
    if dd <= -30: return "🔴 극단 하락"
    if dd <= -20: return "🟠 심각 하락"
    if dd <= -10: return "🟡 중간 조정"
    return "🟢 일반 조정"

def _calc_heat(df: pd.DataFrame) -> float:
    if df is None or df.empty:
        return 50
    cur = df.iloc[-1]
    scores = []
    for col, lo, hi in [("RSI", 30, 100), ("Stoch_K", 0, 100),
                         ("MFI", 0, 100), ("CCI", -200, 200)]:
        v = cur.get(col)
        if v is not None and not pd.isna(v):
            scores.append(min(100, max(0, (v - lo) / (hi - lo) * 100)))
    bb_u = cur.get("BB_upper"); bb_l = cur.get("BB_lower")
    close = cur.get("close", df["close"].iloc[-1])
    if bb_u and bb_l and not pd.isna(bb_u):
        rng = bb_u - bb_l
        if rng > 0:
            scores.append(min(100, max(0, (close - bb_l) / rng * 100)))
    return sum(scores) / len(scores) if scores else 50

def _mdd_52w(df: pd.DataFrame, price: float) -> float:
    if df is None or len(df) < 10:
        return 0.0
    high = float(df["close"].tail(250).max())
    return (price - high) / high * 100 if high > 0 else 0.0

def _trigger_price(s: Dict, df: pd.DataFrame) -> Optional[float]:
    disp = s.get("disparity"); ma = s.get("ma_period")
    if not disp or not ma or df is None:
        return None
    col = f"MA{ma}"
    ma_val = df[col].iloc[-1] if col in df.columns else \
             df["close"].rolling(ma).mean().iloc[-1]
    return ma_val * (disp / 100) if not pd.isna(ma_val) else None

def _rsi_divergence(df: pd.DataFrame) -> str:
    """최근 30일 내 RSI 상승 다이버전스 여부"""
    if df is None or len(df) < 10:
        return "⚪ 없음"
    recent = df.tail(30).copy()
    lows = []
    for i in range(2, len(recent) - 2):
        c = recent["close"].iloc[i]
        if (c < recent["close"].iloc[i-1] and c < recent["close"].iloc[i-2]
                and c < recent["close"].iloc[i+1] and c < recent["close"].iloc[i+2]):
            lows.append(i)
    if len(lows) >= 2:
        i1, i2 = lows[-2], lows[-1]
        p1, p2 = float(recent["close"].iloc[i1]), float(recent["close"].iloc[i2])
        r1 = recent["RSI"].iloc[i1]; r2 = recent["RSI"].iloc[i2]
        if not pd.isna(r1) and not pd.isna(r2):
            if p2 < p1 and float(r2) > float(r1):
                return "🟢 상승 다이버전스 (저점 반전 신호)"
            if p2 > p1 and float(r2) < float(r1):
                return "🔴 하락 다이버전스 (고점 전환 경고)"
    return "⚪ 없음"

def _get_indicators(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {}
    cur = df.iloc[-1]
    return {
        "RSI":   cur.get("RSI"),
        "Stoch": cur.get("Stoch_K"),
        "MFI":   cur.get("MFI"),
        "ADX":   cur.get("ADX"),
        "MACD_cross": _macd_cross(df),
        "+DI":   cur.get("+DI"),
        "-DI":   cur.get("-DI"),
        "ATR":   cur.get("ATR"),
        "vol_ratio": cur.get("Volume_Ratio"),
    }

def _macd_cross(df: pd.DataFrame) -> str:
    if df is None or len(df) < 2:
        return ""
    h0 = df["MACD_Hist"].iloc[-1]; h1 = df["MACD_Hist"].iloc[-2]
    if pd.isna(h0) or pd.isna(h1):
        return ""
    if h1 > 0 and h0 <= 0: return "⚠️ 데드크로스"
    if h1 <= 0 and h0 > 0: return "✅ 골든크로스"
    return "🔵 음전" if h0 < 0 else "🟢 양전"


# ──────────────────────────────────────────────────────────
# 한 시장 카드 생성
# ──────────────────────────────────────────────────────────

def _market_card(r: Dict) -> str:
    name  = r["market_name"]
    price = r["current_price"]
    trend = r["trend_type"]
    conf  = r["trend_confidence"]
    df    = r.get("df")
    strats     = r.get("selected_strategies", [])
    bull_strats = r.get("bull_strategies", [])
    ens   = r.get("ensemble_results")

    heat   = _calc_heat(df)
    mdd_52 = _mdd_52w(df, price)
    inds   = _get_indicators(df)
    rsi_div = _rsi_divergence(df)

    breakout  = [s for s in strats if s["type"] == "breakout"]
    reversal  = [s for s in strats if s["type"] in ("reversal",)]

    # ── 상승 목표가 (근접 순으로 정렬) ──
    sell_targets = []
    for s in breakout:
        tp = _trigger_price(s, df)
        if tp and tp > price:
            sell_targets.append((tp, s.get("win_rate", 0), s["name"]))
    sell_targets.sort(key=lambda x: x[0])  # 가장 가까운 목표부터

    # ── 손절선 ──
    stop_pcts = [-3, -5, -8]
    stop_prices = [price * (1 + p / 100) for p in stop_pcts]
    stop_strats = reversal[:3] if reversal else []

    # ── 앙상블 동시발동 기준 ──
    best_n = ens["best_n"] if ens else None
    best_wr = ens["best_win_rate"] if ens else None

    # ── 시나리오 (ATR 기반) ──
    atr = inds.get("ATR") or price * 0.015
    ma_vals = {}
    if df is not None:
        for p in [10, 20, 40, 60, 120]:
            col = f"MA{p}"
            if col in df.columns:
                v = df[col].iloc[-1]
                if not pd.isna(v):
                    ma_vals[p] = float(v)
    ma_above = sorted([v for v in ma_vals.values() if v > price])
    ma_below = sorted([v for v in ma_vals.values() if v <= price], reverse=True)
    sc_base = ma_above[0] if ma_above else price + 2 * atr
    sc_bull = ma_above[1] if len(ma_above) >= 2 else sc_base + atr
    sc_bear = ma_below[0] if ma_below else price - 3 * atr

    if trend == "bear":
        p_bull, p_base, p_bear = 15, 35, 50
    elif trend == "bull":
        p_bull, p_base, p_bear = 50, 35, 15
    else:
        p_bull, p_base, p_bear = 30, 40, 30

    # ── RSI / ADX 텍스트 ──
    rsi_v = inds.get("RSI")
    adx_v = inds.get("ADX")
    stoch_v = inds.get("Stoch")
    macd_cross = inds.get("MACD_cross", "")
    minus_di = inds.get("-DI"); plus_di = inds.get("+DI")
    di_txt = ""
    if minus_di and plus_di:
        di_txt = f"-DI {minus_di:.0f} > +DI {plus_di:.0f} 하락압력" if minus_di > plus_di \
                 else f"+DI {plus_di:.0f} > -DI {minus_di:.0f} 상승압력"

    vol_r = inds.get("vol_ratio")
    vol_txt = ""
    if vol_r is not None and not pd.isna(vol_r):
        if vol_r >= 2.0:
            vol_txt = f"| 거래량 **{vol_r:.1f}배** 급증 ⚠️"
        elif vol_r <= 0.5:
            vol_txt = f"| 거래량 **{vol_r:.1f}배** 감소"

    lines = []

    # ━━━ 헤더 ━━━
    lines.append(f"---")
    lines.append(f"")
    lines.append(f"## {name}  `{price:,.2f}`  {_trend_badge(trend)} (신뢰도 {conf}%)")
    lines.append(f"")

    # ━━━ 상태 한 줄 ━━━
    heat_bar = "█" * int(heat / 10) + "░" * (10 - int(heat / 10))
    lines.append(f"```")
    lines.append(f"  과열점수  [{heat_bar}] {heat:.0f}/100  {_heat_label(heat)}")
    lines.append(f"  52주낙폭  {mdd_52:+.1f}%  {_dd_label(mdd_52)}")
    if rsi_v is not None:
        rsi_state = "극단 과매도" if rsi_v < 25 else ("과매도" if rsi_v < 35 else ("중립" if rsi_v < 65 else "과열"))
        lines.append(f"  RSI {rsi_v:.1f}  {rsi_state}  |  Stoch {stoch_v:.1f}  |  ADX {adx_v:.1f}  {di_txt}")
    if macd_cross:
        lines.append(f"  MACD {macd_cross}  {vol_txt}")
    lines.append(f"  다이버전스 {rsi_div}")
    lines.append(f"```")
    lines.append(f"")

    # ━━━ 즉시 행동 ━━━
    lines.append(f"### ▶ 즉시 행동")
    lines.append(f"")

    if sell_targets:
        tp, wr, sn = sell_targets[0]
        pct = (tp - price) / price * 100
        lines.append(f"| 📈 **상승 시** | **{tp:,.0f}** 도달 → {pct:+.1f}%  \`{sn[:30]}\` 승률 {wr:.0f}% |")
        lines.append(f"|:---|:---|")
        for tp2, wr2, sn2 in sell_targets[1:3]:
            pct2 = (tp2 - price) / price * 100
            lines.append(f"| 2차 목표 | **{tp2:,.0f}** ({pct2:+.1f}%)  \`{sn2[:28]}\` 승률 {wr2:.0f}% |")
    else:
        lines.append(f"| 📈 **상승 시** | 상향돌파 목표가 미산출 — 상세 리포트 참고 |")
        lines.append(f"|:---|:---|")

    for i, (sp, stg) in enumerate(zip(stop_prices, stop_strats), 1):
        pct = stop_pcts[i-1]
        sname = stg["name"][:32] if stg else "—"
        swr   = stg["win_rate"] if stg else 0
        lines.append(f"| {'🛑' if i==1 else '⛔'} **{i}차 손절 ({pct}%)** | **{sp:,.0f}** → {i*30 if i<3 else 40}% 청산  \`{sname}\` 승률 {swr:.0f}% |")

    if len(stop_strats) < 3:
        for i in range(len(stop_strats) + 1, 4):
            pct = stop_pcts[i - 1]
            sp = stop_prices[i - 1]
            lines.append(f"| {'🛑' if i==1 else '⛔'} **{i}차 손절 ({pct}%)** | **{sp:,.0f}** |")

    lines.append(f"")

    # ━━━ 앙상블 ━━━
    if best_n and best_wr:
        n_sell  = len([s for s in strats if s["type"] in ("breakout", "reversal")])
        n_buy   = len(bull_strats)
        lines.append(f"> 매도 전략 **{n_sell}개** | 매수 전략 **{n_buy}개** "
                     f"— **{best_n}개 이상 동시 발동 시** 즉시 50% 청산 (검증 승률 **{best_wr:.0f}%**)")
        lines.append(f"")

    # ━━━ 시나리오 ━━━
    lines.append(f"### ▶ 시나리오")
    lines.append(f"")
    lines.append(f"| 🟢 강세 {p_bull}% | 🟡 기본 {p_base}% | 🔴 약세 {p_bear}% |")
    lines.append(f"|:---:|:---:|:---:|")
    bc = (sc_bull - price) / price * 100
    nc = (sc_base - price) / price * 100
    wc = (sc_bear - price) / price * 100
    lines.append(f"| **{sc_bull:,.0f}** ({bc:+.1f}%) | **{sc_base:,.0f}** ({nc:+.1f}%) | **{sc_bear:,.0f}** ({wc:+.1f}%) |")
    lines.append(f"")

    # ━━━ 매수 전략 Top1 ━━━
    if bull_strats:
        top_bull = bull_strats[0]
        b_avg  = top_bull.get("avg_return", 0) or top_bull.get("avg_return_net", 0)
        b_wr   = top_bull.get("win_rate", 0)
        b_mae  = top_bull.get("max_adverse", 0)
        b_mfe  = top_bull.get("avg_mfe", 0)
        b_optd = top_bull.get("optimal_hold_days", 20)
        regime_wr = top_bull.get("regime_win_rate")
        regime_txt = f" | 현재레짐 **{regime_wr:.0f}%**" if regime_wr else ""
        lines.append(f"> 💡 **매수 Top1** `{top_bull['name']}` — "
                     f"승률 **{b_wr:.0f}%**{regime_txt} | 평균 +{b_avg:.1f}% | "
                     f"MFE +{b_mfe:.1f}% | 최적보유 D+{b_optd} | MAE -{b_mae:.1f}%")
        lines.append(f"")

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────
# 공개 API
# ──────────────────────────────────────────────────────────

def generate_brief(market_results: List[Dict]) -> str:
    """핵심 브리핑 파일 생성, 저장 경로 반환"""
    if not market_results:
        return ""

    os.makedirs(REPORTS_DIR, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    date = datetime.now().strftime("%Y년 %m월 %d일 %H:%M")
    path = os.path.join(REPORTS_DIR, f"핵심브리핑_{ts}.md")

    # ── 오늘의 종합 판단 ──
    bear_count  = sum(1 for r in market_results if r["trend_type"] == "bear")
    bull_count  = sum(1 for r in market_results if r["trend_type"] == "bull")
    heat_scores = [_calc_heat(r.get("df")) for r in market_results]
    avg_heat    = sum(heat_scores) / len(heat_scores) if heat_scores else 50
    mdds        = [_mdd_52w(r.get("df"), r["current_price"]) for r in market_results]
    avg_mdd     = sum(mdds) / len(mdds) if mdds else 0

    if avg_heat >= 70:
        verdict = "🔴 **과열 주의** — 매도 전략 점검, 손절선 확인 필수"
    elif avg_heat <= 25 and avg_mdd <= -20:
        verdict = "🔵 **극단 과매도 + 대형 낙폭** — 역사적 저점 구간, 분할 매수 검토 (단, 추세 전환 확인 후)"
    elif avg_heat <= 30:
        verdict = "🔵 **과매도 구간** — 매수 전략 검토, 반전 신호 대기"
    elif bear_count == len(market_results):
        verdict = "📉 **전 시장 하락장** — 신규 매수 자제, 보유분 손절 원칙 준수"
    elif bull_count == len(market_results):
        verdict = "📈 **전 시장 상승장** — 보유 유지, 매도 목표가 단계별 익절"
    else:
        verdict = "↔️ **혼조장** — 방향성 확인 후 대응, 분할 접근 권장"

    lines = [
        f"# ⚡ 핵심 브리핑 — {date}",
        f"",
        f"> {verdict}",
        f"",
        f"| 시장 | 지수 | 추세 | 과열점수 | 52주 낙폭 |",
        f"|:----:|-----:|:----:|:-------:|:--------:|",
    ]
    for r, heat, mdd in zip(market_results, heat_scores, mdds):
        lines.append(
            f"| **{r['market_name']}** | {r['current_price']:,.2f} | "
            f"{_trend_badge(r['trend_type'])} | {heat:.0f}/100 {_heat_label(heat)} | "
            f"{mdd:+.1f}% {_dd_label(mdd)} |"
        )
    lines.append(f"")
    lines.append(f"")

    # ── 시장별 카드 ──
    for r in market_results:
        lines.append(_market_card(r))
        lines.append(f"")

    lines.append(f"---")
    lines.append(f"")
    lines.append(f"*생성: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | MarketTop v2*")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"  ⚡ 핵심 브리핑: {path}")
    return path
