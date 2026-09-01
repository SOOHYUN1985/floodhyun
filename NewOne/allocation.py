"""
적정 주식비중 산출 모델

요구사항 29~32: 단순히 "상승확률=비중" 이 아니라
Direction / Expected Return / Risk / Confidence 4요소를 분리 계산한 뒤
위험조정 노출(Risk-adjusted Exposure) 방식으로 0~100% 비중을 산출한다.

표본 수(N)가 부족하면 신뢰도로 비중을 중립(50%)쪽으로 수축시켜
데이터보다 강한 확신을 갖지 않도록 한다.
"""

import numpy as np

import config as C

# 투자성향(목적함수)별 프로필 — 같은 통계에서 배분 기준만 달라진다.
#   risk_aversion 클수로 보수적, tilt 클수로 신호를 공격적으로 증폭
PROFILES = {
    '공격형': {'risk_aversion': 1.2, 'tilt': 1.35, 'cap': 1.0,  'floor': 0.0},
    '균형형': {'risk_aversion': 2.0, 'tilt': 1.00, 'cap': 1.0,  'floor': 0.0},
    '안정형': {'risk_aversion': 3.5, 'tilt': 0.70, 'cap': 0.9,  'floor': 0.0},
}


def _blend_prob_up(forward: dict) -> float:
    weights = {5: 0.2, 10: 0.15, 20: 0.4, 60: 0.25}
    num = den = 0.0
    for h, w in weights.items():
        s = forward.get(h, {})
        if s.get('n', 0) >= 5:
            num += w * s['prob_up']
            den += w
    if den == 0:
        return 50.0
    return num / den


def compute(forward: dict, excursion: dict | None,
            risk_aversion: float | None = None, tilt: float = 1.0,
            cap: float | None = None, floor: float | None = None) -> dict:
    """forward: analog.forward_stats 결과, excursion: MFE/MAE 결과.
    risk_aversion/tilt/cap/floor 로 투자성향 프로필을 적용할 수 있다."""
    ra = risk_aversion if risk_aversion is not None else C.ALLOC['risk_aversion']
    cap = cap if cap is not None else C.ALLOC['weight_cap']
    floor = floor if floor is not None else C.ALLOC['weight_floor']
    h = C.ALLOC['primary_horizon']
    prim = forward.get(h, {})
    n = prim.get('n', 0)

    if n < 1:
        return {
            'weight_pct': 50.0, 'band': '40~60%',
            'direction': 50.0, 'expected_return': 0.0,
            'risk': 0.0, 'confidence': 0.0, 'reliable': False,
            'note': '유사 표본 없음 — 중립',
        }

    # ── 4요소 ──
    direction = _blend_prob_up(forward)                 # 0~100
    expected_return = prim.get('median', 0.0)           # % (중앙값 = 이상치에 강건)

    downside_candidates = [abs(prim.get('p10', 0.0))]
    if excursion and excursion.get('n', 0) > 0:
        downside_candidates.append(abs(excursion.get('mae_p10', 0.0)))
    downside = max(downside_candidates) if downside_candidates else 5.0
    downside = max(downside, 1e-6)

    # 신뢰도: 표본 수 + 방향 일관성 + 분산
    n_conf = np.clip(n / 40.0, 0, 1)
    agree = abs(direction - 50) / 50.0                  # 0~1
    disp = prim.get('std', 10.0)
    disp_conf = np.clip(1.0 - (disp - 5) / 25.0, 0.2, 1.0)
    confidence = float(np.clip(n_conf * (0.5 + 0.5 * agree) * disp_conf, 0, 1) * 100)

    # ── 점수화 (0~100) ──
    direction_score = direction
    return_score = 50 + 50 * np.tanh(expected_return / 5.0)
    reward_risk = expected_return / (ra * downside)
    risk_score = float(np.clip(50 + 50 * np.tanh(reward_risk), 0, 100))

    composite = 0.45 * direction_score + 0.30 * return_score + 0.25 * risk_score

    # 신뢰도로 중립(50) 쪽 수축 + 프로필 tilt
    conf_frac = confidence / 100.0
    weight = 50 + (composite - 50) * conf_frac * tilt
    weight = float(np.clip(weight, floor * 100, cap * 100))

    bands = [(0, 20), (20, 40), (40, 60), (60, 80), (80, 100)]
    band = next((f'{lo}~{hi}%' for lo, hi in bands if lo <= weight <= hi), '40~60%')

    return {
        'weight_pct': round(weight, 1),
        'band': band,
        'direction': round(direction, 1),
        'expected_return': round(expected_return, 2),
        'risk': round(-downside, 2),          # 음수로 표기 (예상 하방)
        'confidence': round(confidence, 1),
        'reliable': bool(n >= C.ALLOC['min_samples']),
        'composite': round(composite, 1),
        'n': int(n),
    }
