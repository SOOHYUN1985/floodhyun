"""
코스피 Forward PER / PBR 밸류에이션 밴드 차트
- 22년 역사적 데이터 기반
- 현재 코스피 위치 표시
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import os

# ── 한글 폰트 설정 ──
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

# ── 22년 역사적 데이터 (코스피_밸류에이션_현황.md 기반) ──
data = {
    'year':    [2003,2004,2005,2006,2007,2008,2009,2010,2011,2012,
                2013,2014,2015,2016,2017,2018,2019,2020,2021,2022,
                2023,2024],
    'kospi':   [810.71, 895.92, 1379.37, 1434.46, 1897.13, 1124.47,
                1682.77, 2051.00, 1825.74, 1997.05, 2011.34, 1915.59,
                1961.31, 2026.46, 2467.49, 2041.04, 2197.67, 2873.47,
                2977.65, 2236.40, 2655.28, 2399.49],
    'fwd_per': [9.8, 8.5, 10.2, 9.8, 10.5, 9.5, 10.8, 9.5, 8.8, 9.2,
                9.0, 9.6, 10.1, 9.5, 9.2, 8.4, 11.5, 14.2, 10.0, 10.5,
                11.0, 9.0],
    'pbr':     [1.19, 1.13, 1.59, 1.49, 1.81, 0.93, 1.52, 1.50, 1.10, 1.10,
                1.04, 0.97, 0.99, 0.97, 1.08, 0.85, 0.86, 1.18, 1.08, 0.83,
                0.92, 0.86],
    'fwd_eps': [83, 105, 135, 146, 181, 118, 156, 216, 208, 217,
                224, 200, 194, 213, 268, 243, 191, 202, 298, 213,
                241, 267],
    'bps':     [681, 793, 868, 963, 1048, 1209, 1107, 1367, 1660, 1816,
                1934, 1975, 1981, 2089, 2285, 2401, 2555, 2435, 2757, 2695,
                2886, 2790],
}

# ── 밸류에이션 상수는 config.py에서 중앙 관리 ──
from config import CURRENT_FWD_EPS, CURRENT_FWD_BPS, DB_PATH
CURRENT_BPS = CURRENT_FWD_BPS

# ── 현재 코스피 지수 (DB 우선 → yfinance 보조) ──
import datetime
import sqlite3

CURRENT_KOSPI = None

# 1순위: DB에서 최신 종가 조회 (update_market_data.py가 먼저 실행됨)
try:
    if os.path.exists(DB_PATH):
        _conn = sqlite3.connect(DB_PATH)
        _cur = _conn.cursor()
        _cur.execute("SELECT close FROM index_data WHERE index_name='KS11' ORDER BY date DESC LIMIT 1")
        _row = _cur.fetchone()
        if _row:
            CURRENT_KOSPI = round(float(_row[0]), 2)
            print(f'  [밸류] DB에서 코스피 조회: {CURRENT_KOSPI:,.2f}')
        _conn.close()
except Exception as e:
    print(f'  [밸류] DB 조회 실패: {e}')

# 2순위: yfinance (DB 실패 시)
if CURRENT_KOSPI is None:
    try:
        import yfinance as yf
        _ticker = yf.Ticker('^KS11')
        _hist = _ticker.history(period='5d')
        if not _hist.empty:
            CURRENT_KOSPI = round(float(_hist['Close'].iloc[-1]), 2)
            print(f'  [밸류] yfinance에서 코스피 조회: {CURRENT_KOSPI:,.2f}')
        else:
            CURRENT_KOSPI = 5234.05  # fallback
    except Exception:
        CURRENT_KOSPI = 5234.05  # fallback (오프라인)

CURRENT_FWD_PER = CURRENT_KOSPI / CURRENT_FWD_EPS
CURRENT_PBR = CURRENT_KOSPI / CURRENT_BPS
CURRENT_YEAR = datetime.date.today().year
TODAY_STR = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
TODAY_DISPLAY = datetime.date.today().strftime('%Y-%m-%d')

# ── PER 밴드 구간 정의 (5년 통계) ──
PER_BANDS = {
    '-2σ (7.8)': 7.8,
    '-1σ (9.0)': 9.0,
    '5Y평균 (10.2)': 10.2,
    '+1σ (11.4)': 11.4,
    '+2σ (12.6)': 12.6,
}

# ── PBR 밴드 구간 정의 ──
PBR_BANDS = {
    '22Y최저 (0.83)': 0.83,
    '22Y평균 (1.14)': 1.14,
    '+2σ (1.40)': 1.40,
    '현재 (~1.46)': CURRENT_PBR,
    '22Y최고 (1.81)': 1.81,
}

years = data['year'] + [CURRENT_YEAR]
fwd_eps_arr = data['fwd_eps'] + [CURRENT_FWD_EPS]
bps_arr = data['bps'] + [CURRENT_BPS]


def make_per_band_chart(ax):
    """Forward PER 밴드 + 실제 코스피 오버레이"""
    colors = ['#1a5276', '#2980b9', '#27ae60', '#f39c12', '#e74c3c']
    band_names = list(PER_BANDS.keys())
    band_vals  = list(PER_BANDS.values())

    # PER 밴드별 적정 지수 계산 (EPS × PER)
    for i, (name, per) in enumerate(zip(band_names, band_vals)):
        implied = [eps * per for eps in fwd_eps_arr]
        ax.plot(years, implied, color=colors[i], linewidth=1.5,
                label=f'PER {name}', alpha=0.85)
        ax.annotate(f'{per}배\n({implied[-1]:,.0f})',
                    xy=(years[-1], implied[-1]),
                    xytext=(8, 0), textcoords='offset points',
                    fontsize=7.5, color=colors[i], fontweight='bold',
                    va='center')

    # 밴드 사이 색칠
    for i in range(len(band_vals) - 1):
        lower = [eps * band_vals[i] for eps in fwd_eps_arr]
        upper = [eps * band_vals[i+1] for eps in fwd_eps_arr]
        ax.fill_between(years, lower, upper, color=colors[i], alpha=0.08)

    # 실제 코스피
    actual_kospi = data['kospi'] + [CURRENT_KOSPI]
    ax.plot(years, actual_kospi, color='black', linewidth=2.5,
            marker='o', markersize=4, label='실제 KOSPI', zorder=5)

    # 현재 위치 강조
    ax.scatter([CURRENT_YEAR], [CURRENT_KOSPI], color='red', s=200,
               zorder=10, edgecolors='darkred', linewidth=2, marker='*')
    ax.annotate(f'현재 {CURRENT_KOSPI:,.0f}\nFwd PER {CURRENT_FWD_PER:.1f}배',
                xy=(CURRENT_YEAR, CURRENT_KOSPI),
                xytext=(-120, 30), textcoords='offset points',
                fontsize=9, fontweight='bold', color='red',
                arrowprops=dict(arrowstyle='->', color='red', lw=1.5),
                bbox=dict(boxstyle='round,pad=0.4', facecolor='#fff3f3',
                          edgecolor='red', alpha=0.9))

    ax.set_title('코스피 Forward PER 밸류에이션 밴드 (2003~현재)',
                 fontsize=14, fontweight='bold', pad=12)
    ax.set_ylabel('KOSPI 지수', fontsize=11)
    ax.legend(loc='upper left', fontsize=8, framealpha=0.9)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))
    ax.grid(True, alpha=0.3)
    ax.set_xlim(2002.5, 2027.5)


def make_pbr_band_chart(ax):
    """PBR 밴드 + 실제 코스피 오버레이"""
    pbr_levels = [0.83, 1.00, 1.14, 1.40, 1.81]
    pbr_labels = ['22Y최저 (0.83)', 'PBR 1.0배', '22Y평균 (1.14)', '+2σ (1.40)', '22Y최고 (1.81)']
    colors = ['#1a5276', '#7f8c8d', '#27ae60', '#f39c12', '#e74c3c']

    for pbr, name, col in zip(pbr_levels, pbr_labels, colors):
        implied = [bps * pbr for bps in bps_arr]
        ax.plot(years, implied, color=col, linewidth=1.5,
                label=f'PBR {name}', alpha=0.85)
        ax.annotate(f'{pbr}배\n({implied[-1]:,.0f})',
                    xy=(years[-1], implied[-1]),
                    xytext=(8, 0), textcoords='offset points',
                    fontsize=7.5, color=col, fontweight='bold',
                    va='center')

    # 밴드 사이 색칠
    for i in range(len(pbr_levels) - 1):
        lower = [bps * pbr_levels[i] for bps in bps_arr]
        upper = [bps * pbr_levels[i+1] for bps in bps_arr]
        ax.fill_between(years, lower, upper, color=colors[i], alpha=0.08)

    # 실제 코스피
    actual_kospi = data['kospi'] + [CURRENT_KOSPI]
    ax.plot(years, actual_kospi, color='black', linewidth=2.5,
            marker='o', markersize=4, label='실제 KOSPI', zorder=5)

    # 현재 위치 강조
    ax.scatter([CURRENT_YEAR], [CURRENT_KOSPI], color='red', s=200,
               zorder=10, edgecolors='darkred', linewidth=2, marker='*')
    ax.annotate(f'현재 {CURRENT_KOSPI:,.0f}\nPBR {CURRENT_PBR:.2f}배',
                xy=(CURRENT_YEAR, CURRENT_KOSPI),
                xytext=(-120, 30), textcoords='offset points',
                fontsize=9, fontweight='bold', color='red',
                arrowprops=dict(arrowstyle='->', color='red', lw=1.5),
                bbox=dict(boxstyle='round,pad=0.4', facecolor='#fff3f3',
                          edgecolor='red', alpha=0.9))

    ax.set_title('코스피 PBR 밸류에이션 밴드 (2003~현재)',
                 fontsize=14, fontweight='bold', pad=12)
    ax.set_ylabel('KOSPI 지수', fontsize=11)
    ax.legend(loc='upper left', fontsize=8, framealpha=0.9)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))
    ax.grid(True, alpha=0.3)
    ax.set_xlim(2002.5, 2027.5)


def make_gauge_chart(ax, title, current_val, min_val, max_val, avg_val, bands, unit='배'):
    """게이지 스타일 가로 바 차트"""
    ax.set_xlim(min_val - (max_val - min_val) * 0.05,
                max_val + (max_val - min_val) * 0.15)
    ax.set_ylim(-0.5, 1.5)

    # 배경 그라데이션 바
    gradient_colors = ['#27ae60', '#2ecc71', '#f1c40f', '#e67e22', '#e74c3c']
    n = len(gradient_colors)
    seg_w = (max_val - min_val) / n
    for i, c in enumerate(gradient_colors):
        ax.barh(0.5, seg_w, left=min_val + i * seg_w, height=0.6,
                color=c, alpha=0.3, edgecolor='none')

    # 밴드 마커
    for label, val in bands.items():
        ax.axvline(val, color='gray', linestyle='--', alpha=0.5, linewidth=0.8)
        ax.text(val, 1.15, f'{val}{unit}', ha='center', fontsize=7, color='gray')

    # 평균선
    ax.axvline(avg_val, color='#2c3e50', linestyle='-', alpha=0.8, linewidth=2)
    ax.text(avg_val, 1.35, f'평균 {avg_val}{unit}', ha='center', fontsize=8,
            fontweight='bold', color='#2c3e50')

    # 현재 위치 화살표
    ax.annotate('', xy=(current_val, 0.5), xytext=(current_val, -0.3),
                arrowprops=dict(arrowstyle='->', color='red', lw=3))
    ax.scatter([current_val], [0.5], color='red', s=150, zorder=10,
               edgecolors='darkred', linewidth=2, marker='D')
    ax.text(current_val, -0.4, f'현재\n{current_val:.1f}{unit}',
            ha='center', fontsize=10, fontweight='bold', color='red')

    ax.set_title(title, fontsize=12, fontweight='bold', pad=10)
    ax.set_yticks([])
    ax.spines['top'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['right'].set_visible(False)


def main():
    fig = plt.figure(figsize=(18, 20))
    fig.suptitle(f'코스피 밸류에이션 현황 ({TODAY_DISPLAY}, KOSPI {CURRENT_KOSPI:,.2f})',
                 fontsize=18, fontweight='bold', y=0.98)

    # ── 1행: Forward PER 게이지 ──
    ax1 = fig.add_axes([0.06, 0.82, 0.88, 0.10])
    make_gauge_chart(ax1,
                     f'Forward PER 위치 — 현재 {CURRENT_FWD_PER:.1f}배 (22년 범위: 8.4~14.2)',
                     CURRENT_FWD_PER, 7.5, 15.0, 9.9,
                     {'-2σ': 7.8, '-1σ': 9.0, '평균': 10.2, '+1σ': 11.4, '+2σ': 12.6})

    # ── 2행: PBR 게이지 ──
    ax2 = fig.add_axes([0.06, 0.70, 0.88, 0.10])
    make_gauge_chart(ax2,
                     f'PBR 위치 — 현재 {CURRENT_PBR:.2f}배 (22년 범위: 0.83~1.81)',
                     CURRENT_PBR, 0.7, 2.0, 1.14,
                     {'최저': 0.83, '1.0배': 1.00, '평균': 1.14, '+2σ': 1.40, '최고': 1.81})

    # ── 3행: Forward PER 밴드 차트 ──
    ax3 = fig.add_axes([0.06, 0.37, 0.83, 0.28])
    make_per_band_chart(ax3)

    # ── 4행: PBR 밴드 차트 ──
    ax4 = fig.add_axes([0.06, 0.04, 0.83, 0.28])
    make_pbr_band_chart(ax4)

    # 저장 — backtest 리포트와 같은 폴더, 같은 네이밍 규칙
    from config import DAILY_BACKTEST_DIR
    out_path = os.path.join(DAILY_BACKTEST_DIR,
                            f'코스피_밸류에이션차트_{TODAY_STR}.png')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()

    print(f'\n✅ 차트 저장 완료: {out_path}')
    print(f'\n{"="*60}')
    print(f'  코스피 밸류에이션 요약 ({TODAY_DISPLAY})')
    print(f'{"="*60}')
    print(f'  현재 코스피: {CURRENT_KOSPI:,.2f}')
    print(f'  12M Forward EPS: {CURRENT_FWD_EPS:.1f}')
    print(f'  12M Forward BPS: {CURRENT_BPS:.1f}')
    print(f'  Forward PER: {CURRENT_FWD_PER:.2f}배 (22Y평균 9.9배)')
    print(f'  PBR:         {CURRENT_PBR:.2f}배 (22Y평균 1.14배)')
    print(f'{"="*60}')

    # PER 기준 적정지수 테이블
    print(f'\n📊 Forward PER 기준 적정 코스피 지수')
    print(f'{"─"*50}')
    for name, per in PER_BANDS.items():
        implied = CURRENT_FWD_EPS * per
        gap = (implied - CURRENT_KOSPI) / CURRENT_KOSPI * 100
        marker = ' ◀ 현재 근처' if abs(gap) < 5 else ''
        print(f'  PER {per:5.1f}배 ({name:>12s}): {implied:>8,.0f} ({gap:+.1f}%){marker}')

    print(f'\n📊 PBR 기준 적정 코스피 지수')
    print(f'{"─"*50}')
    pbr_ref = [0.83, 1.00, 1.14, 1.40, 1.50, 1.81]
    pbr_names = ['22Y최저', 'PBR 1.0배', '22Y평균', '+2σ', '현재', '22Y최고']
    for pbr, name in zip(pbr_ref, pbr_names):
        implied = CURRENT_BPS * pbr
        gap = (implied - CURRENT_KOSPI) / CURRENT_KOSPI * 100
        marker = ' ◀ 현재' if name == '현재' else ''
        print(f'  PBR {pbr:5.2f}배 ({name:>8s}): {implied:>8,.0f} ({gap:+.1f}%){marker}')


if __name__ == '__main__':
    main()
