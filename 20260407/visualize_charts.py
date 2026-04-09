"""
코스피 시각화 차트 생성
1. 추세 구간별 색상 차트 (상승=빨강, 횡보=녹색, 하락=파랑)
2. MDD + 코스피 복합 차트
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Patch
from datetime import datetime

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
from config import DB_PATH


from data_loader import DataLoader
from trend_analyzer import TrendAnalyzer


def load_market_data(market: str = 'kospi') -> pd.DataFrame:
    """DB에서 시장 데이터 로드 (지표 포함)"""
    loader = DataLoader(DB_PATH)
    df = loader.load_market_data(market)
    df = loader.calculate_indicators(df)
    return df


def classify_trend(df: pd.DataFrame, window: int = 60) -> pd.Series:
    """
    각 시점의 추세를 판단 (rolling 방식)
    - MA20 > MA60 > MA120 → 상승
    - MA20 < MA60 < MA120 → 하락
    - 그 외 → 횡보
    """
    ma20 = df['close'].rolling(20).mean()
    ma60 = df['close'].rolling(60).mean()
    ma120 = df['close'].rolling(120).mean()

    trend = pd.Series('sideways', index=df.index)

    bull = (df['close'] > ma20) & (ma20 > ma60) & (ma60 > ma120)
    bear = (df['close'] < ma20) & (ma20 < ma60) & (ma60 < ma120)

    trend[bull] = 'bull'
    trend[bear] = 'bear'

    return trend


def compute_mdd(df: pd.DataFrame) -> pd.DataFrame:
    """MDD(Maximum Drawdown) 계산"""
    cummax = df['close'].cummax()
    drawdown = (df['close'] - cummax) / cummax * 100  # %
    return drawdown


def chart1_trend(df: pd.DataFrame, trend: pd.Series, save_path: str, market_name: str = '코스피'):
    """차트 1: 추세 구간별 색상 차트 (MACD 확인 신호 반영)"""
    fig, axes = plt.subplots(2, 1, figsize=(22, 12), height_ratios=[3, 1],
                              gridspec_kw={'hspace': 0.08})
    ax = axes[0]
    ax_bar = axes[1]

    colors = {'bull': '#E53935', 'sideways': '#43A047', 'bear': '#1E88E5'}
    labels = {'bull': '상승장', 'sideways': '횡보장', 'bear': '하락장'}
    bg_colors = {'bull': '#FFEBEE', 'sideways': '#F1F8E9', 'bear': '#E3F2FD'}

    # 구간별로 색 분리하여 그리기 + 배경색
    prev_trend = trend.iloc[0]
    seg_start = 0

    for i in range(1, len(trend)):
        if trend.iloc[i] != prev_trend or i == len(trend) - 1:
            end = i + 1 if i == len(trend) - 1 else i + 1
            seg = df.iloc[seg_start:end]
            ax.plot(seg.index, seg['close'],
                    color=colors[prev_trend], linewidth=0.9, alpha=0.9)
            ax.fill_between(seg.index, seg['close'].min() * 0.95, seg['close'],
                           color=bg_colors[prev_trend], alpha=0.3)
            prev_trend = trend.iloc[i]
            seg_start = i

    # MA 표시
    if 'MA60' in df.columns:
        ax.plot(df.index, df['MA60'], color='#FF9800', linewidth=0.6,
                alpha=0.5, linestyle='--', label='MA60')
    if 'MA120' in df.columns:
        ax.plot(df.index, df['MA120'], color='#9C27B0', linewidth=0.6,
                alpha=0.5, linestyle='--', label='MA120')

    # 범례
    legend_patches = [Patch(color=colors[k], label=labels[k]) for k in ['bull', 'sideways', 'bear']]
    ax.legend(handles=legend_patches, loc='upper left', fontsize=12,
              framealpha=0.9, edgecolor='gray')

    # 서식
    start_year = df.index[0].strftime('%Y')
    ax.set_title(f'{market_name} 추세 구간 차트 ({start_year}~현재) [MA배열 + MACD 확인]',
                 fontsize=18, fontweight='bold', pad=15)
    ax.set_ylabel(f'{market_name} 지수', fontsize=13)
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    ax.tick_params(axis='x', rotation=45, labelbottom=False)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_xlim(df.index[0], df.index[-1])

    # 추세 비율 표시
    total = len(trend.dropna())
    for t, label in labels.items():
        pct = (trend == t).sum() / total * 100
        days = (trend == t).sum()
        ax.text(0.99, 0.97 - list(labels.keys()).index(t) * 0.06,
                f'{label}: {pct:.1f}% ({days:,}일)',
                transform=ax.transAxes, ha='right', va='top',
                fontsize=11, color=colors[t], fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))

    # 현재가 표시
    current_price = df['close'].iloc[-1]
    current_trend = trend.iloc[-1]
    ax.annotate(f'현재: {current_price:,.0f} ({labels[current_trend]})',
                xy=(df.index[-1], current_price),
                xytext=(-150, 20), textcoords='offset points',
                fontsize=11, color=colors[current_trend], fontweight='bold',
                arrowprops=dict(arrowstyle='->', color=colors[current_trend], lw=1.5),
                bbox=dict(boxstyle='round,pad=0.4', facecolor='white', alpha=0.9))

    # 하단: 추세 구간 바 차트 (연도별 추세 비율)
    yearly_data = _compute_yearly_trend_ratio(df, trend)
    bottom_bull = np.zeros(len(yearly_data))
    bottom_side = yearly_data['bull'].values
    bottom_bear = yearly_data['bull'].values + yearly_data['sideways'].values

    ax_bar.bar(yearly_data.index, yearly_data['bull'], color=colors['bull'], alpha=0.8, label='상승')
    ax_bar.bar(yearly_data.index, yearly_data['sideways'], bottom=bottom_side, color=colors['sideways'], alpha=0.8, label='횡보')
    ax_bar.bar(yearly_data.index, yearly_data['bear'], bottom=bottom_bear, color=colors['bear'], alpha=0.8, label='하락')
    ax_bar.set_ylabel('비율 (%)', fontsize=11)
    ax_bar.set_ylim(0, 100)
    ax_bar.set_xlim(int(start_year) - 0.5, int(df.index[-1].strftime('%Y')) + 0.5)
    ax_bar.grid(True, alpha=0.2, linestyle='--', axis='y')
    ax_bar.legend(loc='upper right', fontsize=9, ncol=3)
    ax_bar.set_title('연도별 추세 비율', fontsize=12, fontweight='bold')

    fig.subplots_adjust(hspace=0.08)
    fig.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"✅ 추세 구간 차트 저장: {save_path}")


def _compute_yearly_trend_ratio(df: pd.DataFrame, trend: pd.Series) -> pd.DataFrame:
    """연도별 추세 비율 계산"""
    combined = pd.DataFrame({'trend': trend}, index=df.index)
    combined['year'] = combined.index.year
    yearly = combined.groupby('year')['trend'].value_counts(normalize=True).unstack(fill_value=0) * 100
    for col in ['bull', 'sideways', 'bear']:
        if col not in yearly.columns:
            yearly[col] = 0
    return yearly[['bull', 'sideways', 'bear']]


def chart2_mdd(df: pd.DataFrame, save_path: str, market_name: str = '코스피'):
    """차트 2: 시장 지수 + MDD 복합 차트"""
    drawdown = compute_mdd(df)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(20, 10),
                                    height_ratios=[2, 1],
                                    sharex=True)
    fig.subplots_adjust(hspace=0.05)

    # 상단: 지수 + 고점 라인
    ax1.plot(df.index, df['close'], color='#1565C0', linewidth=0.8, label=market_name)
    cummax = df['close'].cummax()
    ax1.plot(df.index, cummax, color='#E53935', linewidth=0.6, alpha=0.5,
             linestyle='--', label='역대 고점')
    ax1.fill_between(df.index, df['close'], cummax,
                     where=(df['close'] < cummax),
                     color='#E53935', alpha=0.08)
    ax1.set_ylabel(f'{market_name} 지수', fontsize=13)
    ax1.legend(loc='upper left', fontsize=11, framealpha=0.9)
    ax1.set_title(f'{market_name} 지수 & MDD (Maximum Drawdown)', fontsize=18,
                  fontweight='bold', pad=15)
    ax1.grid(True, alpha=0.3, linestyle='--')

    # 주요 MDD 구간 표시
    worst_idx = drawdown.idxmin()
    worst_val = drawdown.min()
    ax1.annotate(f'MDD {worst_val:.1f}%\n({worst_idx.strftime("%Y-%m-%d")})',
                 xy=(worst_idx, df.loc[worst_idx, 'close']),
                 xytext=(30, 30), textcoords='offset points',
                 fontsize=10, color='#C62828', fontweight='bold',
                 arrowprops=dict(arrowstyle='->', color='#C62828', lw=1.5),
                 bbox=dict(boxstyle='round,pad=0.4', facecolor='#FFEBEE', alpha=0.9))

    # 하단: MDD 차트
    ax2.fill_between(df.index, drawdown, 0,
                     color='#E53935', alpha=0.4)
    ax2.plot(df.index, drawdown, color='#C62828', linewidth=0.5)
    ax2.set_ylabel('MDD (%)', fontsize=13)
    ax2.set_xlabel('')
    ax2.grid(True, alpha=0.3, linestyle='--')
    ax2.set_ylim(drawdown.min() * 1.1, 5)

    # MDD 기준선
    for level, color, label in [(-20, '#FF9800', '-20%'), (-40, '#E53935', '-40%'), (-60, '#B71C1C', '-60%')]:
        if drawdown.min() < level:
            ax2.axhline(y=level, color=color, linestyle=':', alpha=0.7, linewidth=1)
            ax2.text(df.index[10], level + 1.5, label,
                     fontsize=9, color=color, fontweight='bold')

    # 현재 MDD
    current_mdd = drawdown.iloc[-1]
    current_date = df.index[-1]
    ax2.annotate(f'현재 MDD: {current_mdd:.1f}%',
                 xy=(current_date, current_mdd),
                 xytext=(-120, -30), textcoords='offset points',
                 fontsize=11, color='#1565C0', fontweight='bold',
                 arrowprops=dict(arrowstyle='->', color='#1565C0', lw=1.5),
                 bbox=dict(boxstyle='round,pad=0.4', facecolor='#E3F2FD', alpha=0.9))

    ax2.xaxis.set_major_locator(mdates.YearLocator(2))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    ax2.tick_params(axis='x', rotation=45)
    ax2.set_xlim(df.index[0], df.index[-1])

    fig.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"✅ 차트 2 저장: {save_path}")


def generate_market_charts(market: str = 'kospi'):
    """특정 시장의 추세/MDD 차트 생성"""
    from config import MARKETS
    market_name = MARKETS[market]['name']
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    output_dir = os.path.join(BASE_DIR, 'results', 'analysis')
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n📂 {market_name} 데이터 로드 중...")
    df = load_market_data(market)
    print(f"   ✅ {len(df):,}건 로드 ({df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')})")

    # TrendAnalyzer v2로 추세 레이블링 (MA배열 + MACD 확인)
    print(f"\n📊 {market_name} 추세 분석 중 (TrendAnalyzer v2)...")
    analyzer = TrendAnalyzer(df)
    analyzer.analyze()
    trend = analyzer.label_all_trends()

    # 차트 1: 추세 구간 차트
    print(f"\n📊 {market_name} 추세 구간 차트 생성 중...")
    path1 = os.path.join(output_dir, f'{market_name}_추세구간_차트_{timestamp}.png')
    chart1_trend(df, trend, path1, market_name)

    # 차트 2: MDD 복합 차트
    print(f"\n📊 {market_name} MDD 차트 생성 중...")
    path2 = os.path.join(output_dir, f'{market_name}_MDD_차트_{timestamp}.png')
    chart2_mdd(df, path2, market_name)

    return path1, path2


def chart3_valuation_overlay(current_kospi: float, save_path: str):
    """차트 3: KOSPI vs Forward PER 22년 오버레이 차트"""
    from config import CURRENT_FWD_EPS, HIST_VALUATION

    # 현재 Fwd PER 자동 계산: KOSPI / Fwd EPS
    current_fwd_per = round(current_kospi / CURRENT_FWD_EPS, 1)

    years = sorted(HIST_VALUATION.keys())
    kospi_vals = [HIST_VALUATION[y][0] for y in years]
    fwd_per_vals = [HIST_VALUATION[y][1] for y in years]

    # 현재 데이터 추가
    current_year = datetime.now().year
    years.append(current_year)
    kospi_vals.append(current_kospi)
    fwd_per_vals.append(current_fwd_per)

    # 통계
    avg_per = np.mean(fwd_per_vals[:-1])  # 현재 제외 역사 평균
    min_per = min(fwd_per_vals)
    max_per = max(fwd_per_vals)

    # 다크 테마
    fig, ax1 = plt.subplots(figsize=(20, 10))
    fig.patch.set_facecolor('#1a1a2e')
    ax1.set_facecolor('#1a1a2e')

    # KOSPI (왼쪽 축)
    color_kospi = '#00d2ff'
    ax1.plot(years, kospi_vals, color=color_kospi, linewidth=2.5,
             marker='o', markersize=6, label='KOSPI', zorder=3)
    ax1.fill_between(years, kospi_vals, alpha=0.15, color=color_kospi)
    ax1.set_ylabel('KOSPI 지수', fontsize=14, color=color_kospi, fontweight='bold')
    ax1.tick_params(axis='y', labelcolor=color_kospi, labelsize=11)
    ax1.set_xlabel('')

    # Fwd PER (오른쪽 축, 반전)
    ax2 = ax1.twinx()
    color_per = '#ff6b6b'
    ax2.plot(years, fwd_per_vals, color=color_per, linewidth=2.5,
             marker='s', markersize=6, label='Fwd PER', zorder=3)
    ax2.fill_between(years, fwd_per_vals, alpha=0.12, color=color_per)
    ax2.set_ylabel('12M Forward PER (배) - 축 반전', fontsize=14,
                    color=color_per, fontweight='bold')
    ax2.tick_params(axis='y', labelcolor=color_per, labelsize=11)
    ax2.invert_yaxis()

    # 평균선
    ax2.axhline(y=avg_per, color='#ffd93d', linestyle='--', linewidth=1.5, alpha=0.7)
    ax2.text(years[1], avg_per + 0.15, f'22Y 평균 {avg_per:.1f}배',
             color='#ffd93d', fontsize=11, fontweight='bold')

    # 현재 포인트 강조
    ax1.annotate(f'KOSPI\n{current_kospi:,.0f}',
                 xy=(current_year, current_kospi),
                 xytext=(-80, 30), textcoords='offset points',
                 fontsize=12, color=color_kospi, fontweight='bold',
                 arrowprops=dict(arrowstyle='->', color=color_kospi, lw=2),
                 bbox=dict(boxstyle='round,pad=0.4', facecolor='#1a1a2e',
                          edgecolor=color_kospi, alpha=0.9))

    ax2.annotate(f'Fwd PER\n{current_fwd_per}배',
                 xy=(current_year, current_fwd_per),
                 xytext=(30, -40), textcoords='offset points',
                 fontsize=12, color=color_per, fontweight='bold',
                 arrowprops=dict(arrowstyle='->', color=color_per, lw=2),
                 bbox=dict(boxstyle='round,pad=0.4', facecolor='#1a1a2e',
                          edgecolor=color_per, alpha=0.9))

    # 타이틀 & 범례
    ax1.set_title(f'KOSPI vs 12M Forward PER ({years[0]}~{current_year})',
                  fontsize=18, fontweight='bold', color='white', pad=20)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2,
               loc='upper left', fontsize=12, framealpha=0.3,
               facecolor='#1a1a2e', edgecolor='gray', labelcolor='white')

    # 스타일
    ax1.grid(True, alpha=0.15, color='white', linestyle='--')
    ax1.tick_params(axis='x', colors='white', labelsize=11, rotation=45)
    for spine in ax1.spines.values():
        spine.set_color('#333')
    for spine in ax2.spines.values():
        spine.set_color('#333')

    # 해석 텍스트
    note = (f'* PER 축 반전: 낮은 PER(저평가) = 위쪽\n'
            f'* 현재 Fwd PER {current_fwd_per}배 (KOSPI {current_kospi:,.0f} / EPS {CURRENT_FWD_EPS}), '
            f'평균 {avg_per:.1f}배, 범위 {min_per:.1f}~{max_per:.1f}배)')
    fig.text(0.12, 0.02, note, fontsize=10, color='#aaa',
             style='italic', ha='left')

    fig.tight_layout(rect=[0, 0.05, 1, 1])
    fig.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
    plt.close(fig)
    print(f"✅ 밸류에이션 오버레이 차트 저장: {save_path}")


if __name__ == '__main__':
    print("=" * 60)
    print("  코스피/코스닥 시각화 차트 생성")
    print("=" * 60)

    all_paths = []
    for market in ['kospi', 'kosdaq']:
        paths = generate_market_charts(market)
        all_paths.extend(paths)

    print(f"\n{'='*60}")
    print("✅ 모든 차트 생성 완료!")
    for p in all_paths:
        print(f"   • {p}")
    print(f"{'='*60}")
