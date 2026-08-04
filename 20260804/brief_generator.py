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

def _get_foreign_status(df: pd.DataFrame) -> str:
    """현재 외국인 매매 상태 한 줄 요약"""
    if df is None or 'foreign_net' not in df.columns:
        return ""
    cur = df.iloc[-1]
    net    = cur.get('foreign_net', 0)
    pct    = cur.get('foreign_roll_pct')
    cum5   = cur.get('foreign_5d_cum', 0)
    cum20  = cur.get('foreign_20d_cum', 0)

    if pct is None or pd.isna(pct):
        return f"외국인 당일 {net:+,.0f}억"

    if pct >= 95:
        strength = "🟢 극강 매수 (상위5%)"
    elif pct >= 90:
        strength = "🟢 강한 매수 (상위10%)"
    elif pct >= 60:
        strength = "🟡 보통 매수"
    elif pct <= 5:
        strength = "🔴 극강 매도 (하위5%)"
    elif pct <= 10:
        strength = "🔴 강한 매도 (하위10%)"
    elif pct <= 40:
        strength = "🟠 보통 매도"
    else:
        strength = "⚪ 중립"

    return (f"외국인: 당일 **{net:+,.0f}억** {strength} "
            f"| 5일 누적 {cum5:+,.0f}억 | 20일 누적 {cum20:+,.0f}억")


def _drawdown_context(df: pd.DataFrame) -> dict:
    """최근 250일 고점 이후 저점과 현재 회복 위치를 계산한다."""
    if df is None or len(df) < 30 or "close" not in df.columns:
        return {}

    window = df["close"].tail(250)
    peak_date = window.idxmax()
    peak_price = float(window.loc[peak_date])
    post_peak = df.loc[peak_date:, "close"]
    trough_date = post_peak.idxmin()
    trough_price = float(post_peak.loc[trough_date])
    current_price = float(df["close"].iloc[-1])
    days_since_trough = len(post_peak.loc[trough_date:]) - 1

    return {
        "peak_date": peak_date,
        "peak_price": peak_price,
        "trough_date": trough_date,
        "trough_price": trough_price,
        "trough_mdd": (trough_price / peak_price - 1) * 100,
        "current_mdd": (current_price / peak_price - 1) * 100,
        "recovery_pct": (current_price / trough_price - 1) * 100,
        "days_since_trough": days_since_trough,
    }


def _get_mdd_status(df: pd.DataFrame, price: float) -> str:
    """현재 MDD와 최근 저점 이후 회복 상태를 한 줄로 요약한다."""
    if df is None or 'rolling_mdd' not in df.columns:
        # fallback: 직접 계산
        if df is not None and len(df) > 10:
            hi = float(df['close'].tail(250).max())
            mdd = (price - hi) / hi * 100 if hi > 0 else 0
        else:
            return ""
    else:
        mdd = float(df['rolling_mdd'].iloc[-1])

    if mdd <= -40: tag = "🔴 폭락 구간 (-40%↓)"
    elif mdd <= -30: tag = "🔴 극단 하락 (-30%↓)"
    elif mdd <= -20: tag = "🟠 심각 하락 (-20%↓) — 약세장 진입"
    elif mdd <= -10: tag = "🟡 중간 조정 (-10%↓)"
    else:           tag = "🟢 정상 범위"
    context = _drawdown_context(df)
    if context and context["days_since_trough"] > 0:
        return (f"MDD: **{mdd:+.1f}%** {tag} | 최근 저점 "
                f"{context['trough_date'].strftime('%m/%d')} {context['trough_mdd']:+.1f}% "
                f"후 **{context['recovery_pct']:+.1f}%** 회복 (D+{context['days_since_trough']})")
    return f"MDD: **{mdd:+.1f}%** {tag}"


def _format_grade(grade: str) -> str:
    return {"A+": "🏆 A+", "A": "⭐ A", "B": "✅ B", "C": "⚠️ C", "D": "❌ D"}.get(grade, grade)


def _buy_entry_status(df: pd.DataFrame, trend: str) -> dict:
    """추세와 반전 확인 신호를 함께 반영한 신규 매수 판단."""
    if df is None or len(df) < 2:
        return {"label": "판단 보류", "detail": "지표 데이터 부족", "count": 0, "total": 0}

    cur = df.iloc[-1]
    rsi = float(cur.get("RSI", 50) or 50)
    stoch = float(cur.get("Stoch_K", 50) or 50)
    adx = float(cur.get("ADX", 0) or 0)
    volume_ratio = float(cur.get("Volume_Ratio", 1) or 1)
    foreign_turn = bool(cur.get("foreign_turn_buy", False))
    h0 = cur.get("MACD_Hist")
    h1 = df["MACD_Hist"].iloc[-2] if "MACD_Hist" in df.columns else None
    macd_gold = (h0 is not None and h1 is not None and
                 not pd.isna(h0) and not pd.isna(h1) and h1 <= 0 < h0)
    divergence = "상승 다이버전스" in _rsi_divergence(df)

    confirmations = [
        foreign_turn,
        rsi > 35,
        macd_gold,
        stoch > 20,
        volume_ratio > 1.5,
        divergence,
        adx < 40,
    ]
    count = sum(confirmations)
    total = len(confirmations)
    strong_downtrend = trend == "bear" and adx >= 40

    if strong_downtrend:
        return {
            "label": "신규 매수 보류",
            "detail": f"ADX {adx:.1f}의 강한 하락 추세: 추세 완화·매수 전환 확인 후 접근",
            "count": count,
            "total": total,
        }
    if count >= 5:
        return {
            "label": "분할 매수 가능",
            "detail": "반전 확인 신호 다수 충족: 1차 비중부터 분할 접근",
            "count": count,
            "total": total,
        }
    if count >= 3:
        return {
            "label": "소량 관찰 매수",
            "detail": "추가 반전 확인 전까지 최소 비중만 허용",
            "count": count,
            "total": total,
        }
    return {
        "label": "현금 유지",
        "detail": "반전 확인 신호 부족: 관망 우선",
        "count": count,
        "total": total,
    }


# ──────────────────────────────────────────────────────────
# 정밀 진단 섹션
# ──────────────────────────────────────────────────────────

def _count_buy_signals(df: pd.DataFrame, price: float) -> dict:
    """현재 발동 중인 과매도/저점 신호 집계"""
    if df is None or df.empty:
        return {"count": 0, "signals": [], "total": 0}
    cur = df.iloc[-1]
    signals = []
    def _chk(cond: bool, label: str):
        signals.append({"ok": cond, "label": label})

    rsi   = cur.get("RSI", 50);  rsi = 50 if pd.isna(rsi) else float(rsi)
    stoch = cur.get("Stoch_K",50); stoch = 50 if pd.isna(stoch) else float(stoch)
    mfi   = cur.get("MFI", 50);  mfi = 50 if pd.isna(mfi) else float(mfi)
    bb_u  = cur.get("BB_upper"); bb_l = cur.get("BB_lower")
    mdd   = float(df["rolling_mdd"].iloc[-1]) if "rolling_mdd" in df.columns else 0.0
    f_turn = bool(cur.get("foreign_turn_buy", False))
    f_cum5 = float(cur.get("foreign_5d_cum", 0) or 0)
    rsi_up = bool(cur.get("rsi_mom_up", False))
    vol_r  = float(cur.get("Volume_Ratio", 1) or 1)
    macd_h = df["MACD_Hist"] if "MACD_Hist" in df.columns else None

    _chk(rsi < 30,    f"RSI {rsi:.1f} < 30 (극단 과매도)")
    _chk(stoch < 20,  f"Stoch {stoch:.1f} < 20 (과매도)")
    _chk(mfi < 30,    f"MFI {mfi:.1f} < 30 (과매도)")
    if mdd <= -30:
        _chk(True, f"MDD {mdd:.1f}% (극단 하락)")
    else:
        _chk(mdd <= -20, f"MDD {mdd:.1f}% (심각 하락)")
    _chk(rsi_up,      "RSI 상승 모멘텀 반전")
    if bb_u is not None and bb_l is not None and not pd.isna(bb_u):
        rng = bb_u - bb_l
        bb_pos = (price - bb_l) / rng * 100 if rng > 0 else 50
        _chk(bb_pos < 15, f"BB 하단 근접 ({bb_pos:.0f}%)")
    _chk(f_turn, "외국인 순매수 전환 (매도→매수)")
    _chk(f_cum5 > 0, f"외국인 5일 누적 순매수 ({f_cum5:+,.0f}억)")
    if macd_h is not None and len(macd_h.dropna()) >= 3:
        h0, h1, h2 = macd_h.iloc[-1], macd_h.iloc[-2], macd_h.iloc[-3]
        improving = (not pd.isna(h0) and not pd.isna(h1) and not pd.isna(h2)
                     and h0 < 0 and h0 > h1 and h1 > h2)
        _chk(improving, "MACD 히스토그램 연속 개선 (반전 준비)")
    _chk(vol_r < 0.6, f"거래량 급감 ({vol_r:.1f}배) — 매도 소진 징후")

    count = sum(1 for s in signals if s["ok"])
    return {"count": count, "signals": signals, "total": len(signals)}


def _aggregate_bull_returns(bull_strats: list) -> dict:
    """상위 매수 전략들의 기간별 기대 수익률 가중 평균"""
    if not bull_strats:
        return {}
    top = [s for s in bull_strats[:5] if s.get("avg_returns_by_period")]
    period_data: dict = {}
    if not top:
        for s in bull_strats[:3]:
            avg = s.get("avg_return", 0) or 0
            wr  = s.get("win_rate", 70) or 70
            for d in [5, 10, 20, 30, 40]:
                period_data.setdefault(d, []).append((avg * d / 20, wr))
    else:
        for s in top:
            wr = s.get("win_rate", 70) or 70
            for d, ret in s["avg_returns_by_period"].items():
                period_data.setdefault(d, []).append((ret, wr))
    result = {}
    for d, vals in sorted(period_data.items()):
        ws = [v[1] for v in vals]; rs = [v[0] for v in vals]
        result[d] = sum(r * w for r, w in zip(rs, ws)) / sum(ws) if sum(ws) else 0
    return result


def _mdd_recovery_stats(df: pd.DataFrame, context: dict) -> dict:
    """유사한 MDD 저점 이후 같은 경과일의 회복/추가 하락 통계를 계산한다."""
    if df is None or "rolling_mdd" not in df.columns or len(df) < 300:
        return {}
    mdd_s = df["rolling_mdd"].dropna()
    close = df["close"]
    trough_mdd = context.get("trough_mdd")
    days = context.get("days_since_trough", 0)
    if trough_mdd is None:
        return {}

    tol = 8.0
    local_low = mdd_s <= mdd_s.rolling(11, center=True, min_periods=1).min()
    sim = mdd_s[local_low & (mdd_s >= trough_mdd - tol) & (mdd_s <= trough_mdd + tol)].index
    if len(sim) < 5:
        tol = 12.0
        sim = mdd_s[local_low & (mdd_s >= trough_mdd - tol) & (mdd_s <= trough_mdd + tol)].index
    if len(sim) < 3:
        return {}

    # 인접한 저점은 하나의 하락 에피소드로 간주해 가장 깊은 값만 유지한다.
    episodes = []
    for dt in sim:
        loc = df.index.get_loc(dt)
        if episodes and loc - episodes[-1] <= 20:
            if float(mdd_s.loc[dt]) < float(mdd_s.loc[df.index[episodes[-1]]]):
                episodes[-1] = loc
            continue
        episodes.append(loc)

    post_trough_returns, forward_declines = [], []
    for loc in episodes:
        current_loc = loc + days
        if current_loc + 20 >= len(close):
            continue
        base = float(close.iloc[loc])
        path = close.iloc[loc:current_loc + 1]
        forward_path = close.iloc[current_loc:current_loc + 21]
        post_trough_returns.append(float((path.iloc[-1] / base - 1) * 100))
        forward_declines.append(float((forward_path.min() / path.iloc[-1] - 1) * 100))
    if not post_trough_returns:
        return {}
    return {
        "sample_count": len(post_trough_returns),
        "post_trough_return_median": float(np.median(post_trough_returns)),
        "post_trough_return_best": float(max(post_trough_returns)),
        "forward_decline_median": float(np.median(forward_declines)),
        "forward_decline_worst": float(min(forward_declines)),
    }


def _generate_diagnosis_section(r: Dict) -> list:
    """
    정밀 진단 섹션:
    ① 신호 강도 & 현재 위치  ② 반등 타이밍 예측
    ③ 진입 체크리스트        ④ 역사적 유사 사례
    """
    price = r["current_price"]
    df    = r.get("df")
    bull_strats = r.get("bull_strategies", [])
    lines = []

    # ── ① 신호 강도 집계 ────────────────────────────
    sd    = _count_buy_signals(df, price)
    count = sd["count"]; total = sd["total"]; signals = sd["signals"]

    entry = _buy_entry_status(df, r.get("trend_type", "sideways"))

    if count >= 7:
        zone = "🔵 **극강 과매도** — 역사적 저점 신호 대거 발동"
    elif count >= 5:
        zone = "🟡 **강한 과매도** — 저점 형성 가능성 높음"
    elif count >= 3:
        zone = "🟠 **과매도 진입** — 추가 하락 여지 있음"
    else:
        zone = "⚪ **신호 부족** — 저점 확인 대기"

    bar = "●" * count + "○" * (total - count)
    lines += [
        f"### 🔬 정밀 진단 — 지금 정확히 어디에 있나?",
        f"",
        f"**신호 강도**: [{bar}] {count}/{total}개 발동  →  {zone}",
        f"",
        f"> 🎯 **권장 행동**: {entry['label']} — {entry['detail']}",
        f"",
    ]
    active   = [s["label"] for s in signals if s["ok"]]
    inactive = [s["label"] for s in signals if not s["ok"]]
    if active:
        lines.append(f"**✅ 발동된 신호 ({len(active)}개)**")
        lines += [f"- ✅ {lb}" for lb in active]
        lines.append(f"")
    if inactive:
        lines.append(f"**⬜ 미발동 신호 ({len(inactive)}개)** — 추가 발동 시 확신↑")
        lines += [f"- ⬜ {lb}" for lb in inactive]
        lines.append(f"")

    # ── ② 반등 타이밍 예측 ──────────────────────────
    exp = _aggregate_bull_returns(bull_strats)
    if exp:
        lines += [
            f"### 📈 반등 타이밍 예측 (백테스트 통계)",
            f"",
            f"*현재 발동 매수 전략 상위 {min(5,len(bull_strats))}개 가중 평균 기대 수익*",
            f"",
            f"| 기간 | 기대 수익 | 목표 지수 | 해석 |",
            f"|:----:|:--------:|:--------:|:----:|",
        ]
        best_d = max(exp, key=lambda x: exp[x])
        for d in sorted(exp.keys()):
            ret = exp[d]; tgt = price * (1 + ret / 100)
            interp_map = {5:"단기 반등", 10:"1~2주", 15:"2~3주", 20:"1개월", 30:"1.5개월", 40:"2개월"}
            interp = interp_map.get(d, f"D+{d}")
            star = " ⭐" if d == best_d else ""
            lines.append(f"| **D+{d}** | **{ret:+.1f}%** | {tgt:,.0f} | {interp}{star} |")
        best_r = exp[best_d]
        if best_r > 0:
            lines += [
                f"",
                f"> 📌 **최적 보유**: D+{best_d} 전후 — 기대 **{best_r:+.1f}%** "
                f"(목표 {price*(1+best_r/100):,.0f})",
                f"",
            ]

    # ── ③ 진입 체크리스트 ───────────────────────────
    lines += [
        f"### ✅ 매수 진입 전 체크리스트",
        f"",
        f"*아래 조건 확인 후 진입 — 많이 충족될수록 승률↑*",
        f"",
    ]
    if df is not None and len(df) > 1:
        cur    = df.iloc[-1]
        rsi    = float(cur.get("RSI", 50) or 50)
        stoch  = float(cur.get("Stoch_K", 50) or 50)
        adx    = float(cur.get("ADX", 0) or 0)
        vol_r  = float(cur.get("Volume_Ratio", 1) or 1)
        f_turn = bool(cur.get("foreign_turn_buy", False))
        f_net  = float(cur.get("foreign_net", 0) or 0)
        rsi_div_txt = _rsi_divergence(df)
        h0 = df["MACD_Hist"].iloc[-1] if "MACD_Hist" in df.columns else None
        h1 = df["MACD_Hist"].iloc[-2] if "MACD_Hist" in df.columns else None
        macd_gold = (h0 is not None and h1 is not None and
                     not pd.isna(h0) and not pd.isna(h1) and h1 <= 0 < h0)

        checklist = [
            (f_turn or f_net > 0,
             f"외국인 순매수 전환 {'→ 오늘 전환!' if f_turn else '(미전환)'}",
             "매도→매수 전환일이 가장 강력한 매수 타이밍"),
            (rsi > 35,
             f"RSI 35 돌파 (현재 {rsi:.1f} {'✅' if rsi > 35 else f'→ {35-rsi:.1f}pt 남음'})",
             "RSI 35 이상 = 과매도 탈출, 반등 모멘텀 시작"),
            (macd_gold,
             f"MACD 골든크로스 {'✅ 발동' if macd_gold else '(대기)'}",
             "히스토그램 음→양 전환 = 모멘텀 전환 신호"),
            (stoch > 20,
             f"Stochastic 20 돌파 (현재 {stoch:.1f} {'✅' if stoch > 20 else ''})",
             "단기 과매도 해소 확인"),
            (vol_r > 1.5,
             f"거래량 급증 {'✅' if vol_r > 1.5 else f'(현재 {vol_r:.1f}배, 1.5배 이상 필요)'}",
             "저점에서 거래량 급증 = 세력 매집 신호"),
            ("상승 다이버전스" in rsi_div_txt,
             f"RSI 상승 다이버전스 {'✅ 감지!' if '상승 다이버전스' in rsi_div_txt else '(미감지)'}",
             "가격 저점↓ + RSI 저점↑ = 내부 강도 회복"),
            (adx < 40,
             f"ADX 하락추세 약화 {'✅' if adx < 40 else f'(현재 {adx:.1f} — 강한 추세 지속)'}",
             "ADX 40 미만으로 내려오면 하락 추세 약화"),
        ]
        done = sum(1 for c in checklist if c[0])
        lines.append(f"**현재 {done}/{len(checklist)}개 조건 충족**")
        lines.append(f"")
        for ok, label, desc in checklist:
            mark = "✅" if ok else "⬜"
            lines += [f"- {mark} **{label}**", f"  _{desc}_"]
        lines.append(f"")
        entry = _buy_entry_status(df, r.get("trend_type", "sideways"))
        lines.append(f"> **실행 판단: {entry['label']}** — {entry['detail']}")
        lines.append(f"")

    # ── ④ 최근 저점 경과 및 역사적 유사 사례 ─────────
    if df is not None and "rolling_mdd" in df.columns:
        context = _drawdown_context(df)
        if context:
            lines += [
                f"### 📉 최근 MDD 경과",
                f"",
                f"| 250일 고점 | 최근 저점 | 현재 위치 |",
                f"|:---:|:---:|:---:|",
                f"| {context['peak_date'].strftime('%Y-%m-%d')} **{context['peak_price']:,.0f}** | "
                f"{context['trough_date'].strftime('%Y-%m-%d')} **{context['trough_price']:,.0f}** "
                f"({context['trough_mdd']:+.1f}%) | "
                f"저점 후 D+{context['days_since_trough']} · **{context['recovery_pct']:+.1f}%** 회복 "
                f"(현재 MDD {context['current_mdd']:+.1f}%) |",
                f"",
            ]

        st = _mdd_recovery_stats(df, context)
        if st and context:
            lines += [
                f"### 📚 역사적 유사 사례 (저점 MDD {context['trough_mdd']:.0f}% 후 D+{context['days_since_trough']})",
                f"",
                f"*2000년 이후 유사한 저점 MDD 에피소드 {st['sample_count']}회 분석 — 현재처럼 저점 통과 후 경과일을 맞춰 비교*",
                f"",
                f"| 항목 | 통계값 | 투자 의미 |",
                f"|:----:|:------:|:--------:|",
                f"| 저점 후 수익 중앙값 | **{st['post_trough_return_median']:+.1f}%** | "
                f"현재 저점 후 {context['recovery_pct']:+.1f}%와 비교 |",
                f"| 저점 후 수익 최고 | **{st['post_trough_return_best']:+.1f}%** | 강한 초기 반등 사례 |",
                f"| D+{context['days_since_trough']} 이후 20일 추가 하락 중앙값 | "
                f"**{st['forward_decline_median']:+.1f}%** | 현재 시점 이후 단기 하방 위험 |",
                f"| D+{context['days_since_trough']} 이후 20일 추가 하락 최악 | "
                f"**{st['forward_decline_worst']:+.1f}%** | 반등 실패 시 단기 극단 위험 |",
                f"",
                f"> 💬 이미 {context['trough_date'].strftime('%m/%d')} 저점을 통과해 "
                f"**{context['recovery_pct']:+.1f}%** 회복했습니다. 이후 판단은 현재 MDD가 아니라 "
                f"저점 재이탈 여부와 반등 지속 신호를 중심으로 봅니다.",
                f"",
            ]

    return lines


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

    # ━━━ 상태 블록 ━━━
    heat_bar = "█" * int(heat / 10) + "░" * (10 - int(heat / 10))
    foreign_txt = _get_foreign_status(df)
    mdd_txt     = _get_mdd_status(df, price)

    lines.append(f"```")
    lines.append(f"  과열점수  [{heat_bar}] {heat:.0f}/100  {_heat_label(heat)}")
    lines.append(f"  {mdd_txt}")
    if rsi_v is not None:
        rsi_state = "극단 과매도" if rsi_v < 25 else ("과매도" if rsi_v < 35 else ("중립" if rsi_v < 65 else "과열"))
        lines.append(f"  RSI {rsi_v:.1f}  {rsi_state}  |  Stoch {stoch_v:.1f}  |  ADX {adx_v:.1f}  {di_txt}")
    if macd_cross:
        lines.append(f"  MACD {macd_cross}  {vol_txt}")
    lines.append(f"  다이버전스 {rsi_div}")
    if foreign_txt:
        lines.append(f"  {foreign_txt}")
    lines.append(f"```")
    lines.append(f"")

    # ━━━ 즉시 행동 ━━━
    lines.append(f"### ▶ 즉시 행동")
    lines.append(f"")

    entry = _buy_entry_status(df, trend)
    lines.append(f"| 신규 매수 | **{entry['label']}** ({entry['count']}/{entry['total']} 확인) — {entry['detail']} |")
    lines.append(f"|:---|:---|")

    if sell_targets:
        tp, wr, sn = sell_targets[0]
        pct = (tp - price) / price * 100
        lines.append(f"| 📈 **상승 시** | **{tp:,.0f}** 도달 → {pct:+.1f}%  `{sn[:30]}` 승률 {wr:.0f}% |")
        for tp2, wr2, sn2 in sell_targets[1:3]:
            pct2 = (tp2 - price) / price * 100
            lines.append(f"| 2차 목표 | **{tp2:,.0f}** ({pct2:+.1f}%)  `{sn2[:28]}` 승률 {wr2:.0f}% |")
    elif ma_above:
        # 선정된 상향돌파(breakout) 전략이 없거나 이미 임계값을 하회한 경우
        # → 이동평균선 기준 근접 저항선을 참고용으로 대체 제시
        near = ma_above[0]
        pct = (near - price) / price * 100
        reason = "상향돌파 전략 미선정" if not breakout else "선정 전략 임계값 이미 하회"
        lines.append(f"| 📈 **상승 시** | 백테스트 목표가 없음({reason}) → 참고 저항선 **{near:,.0f}** ({pct:+.1f}%, 근접 MA 기준) |")
        lines.append(f"|:---|:---|")
    else:
        lines.append(f"| 📈 **상승 시** | 상향돌파 목표가 미산출 — 상세 리포트 참고 |")
        lines.append(f"|:---|:---|")

    for i, (sp, stg) in enumerate(zip(stop_prices, stop_strats), 1):
        pct = stop_pcts[i-1]
        sname = stg["name"][:32] if stg else "—"
        swr   = stg["win_rate"] if stg else 0
        lines.append(f"| {'🛑' if i==1 else '⛔'} **{i}차 손절 ({pct}%)** | **{sp:,.0f}** → {i*30 if i<3 else 40}% 청산  `{sname}` 승률 {swr:.0f}% |")

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
        b_avg    = top_bull.get("avg_return", 0) or top_bull.get("avg_return_net", 0)
        b_wr     = top_bull.get("win_rate", 0)
        b_mae    = top_bull.get("max_adverse", 0)
        b_mfe    = top_bull.get("avg_mfe", 0)
        b_optd   = top_bull.get("optimal_hold_days", 20)
        regime_wr = top_bull.get("regime_win_rate")
        grade_str = _format_grade(top_bull.get("grade", ""))
        regime_txt = f" | 레짐 **{regime_wr:.0f}%**" if regime_wr else ""
        lines.append(f"> 💡 **매수 Top1** {grade_str} `{top_bull['name']}` — "
                     f"승률 **{b_wr:.0f}%**{regime_txt} | 평균 +{b_avg:.1f}% | "
                     f"MFE +{b_mfe:.1f}% | 최적보유 D+{b_optd} | MAE -{b_mae:.1f}%")
        lines.append(f"")

    # ━━━ 정밀 진단 섹션 삽입 ━━━
    diagnosis_lines = _generate_diagnosis_section(r)
    lines.extend(diagnosis_lines)

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
