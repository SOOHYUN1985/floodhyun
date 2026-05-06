"""
보통주 vs 우선주 괴리율 통합 분석
- 여러 종목을 한 번에 분석하여 하나의 통합 리포트 생성
- 종목 추가: STOCK_PAIRS 리스트에 (종목코드, 우선주코드, 종목명) 추가

괴리율 = (우선주가격 / 보통주가격 - 1) × 100
- 괴리율이 낮을수록 우선주가 저평가 (우선주 매수 유리)
- 괴리율이 높을수록 우선주가 고평가 (보통주 매수 유리)
"""

import os
import shutil
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime
import certifi
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

# ── SSL 인증서 한글 경로 우회 ──────────────────────────
_cert_src = certifi.where()
_cert_dst = r'C:\temp\cacert.pem'
if not os.path.exists(_cert_dst) or os.path.getmtime(_cert_src) > os.path.getmtime(_cert_dst):
    os.makedirs(os.path.dirname(_cert_dst), exist_ok=True)
    shutil.copy2(_cert_src, _cert_dst)
os.environ['CURL_CA_BUNDLE'] = _cert_dst
os.environ['SSL_CERT_FILE'] = _cert_dst
os.environ['REQUESTS_CA_BUNDLE'] = _cert_dst

import yfinance as yf

# DB 경로
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'data', 'market_data.db')

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📌 분석할 종목 리스트 — 여기에 추가하면 자동 반영
# (보통주코드, 우선주코드, 종목명)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STOCK_PAIRS = [
    # (보통주코드, 우선주코드, 종목명, [우선주명(생략시 종목명+우)])
    ("005930", "005935", "삼성전자"),
    ("009150", "009155", "삼성전기"),
    ("005380", "005385", "현대차"),
    ("006800", "006805", "미래에셋증권"),
    ("001040", "001045", "CJ"),
    ("001680", "001685", "대상"),
    ("034730", "03473K", "SK", "SK우"),
    ("000880", "00088K", "한화", "한화3우B"),
    ("003550", "003555", "LG"),
    ("078930", "078935", "GS"),
    ("000150", "000155", "두산"),
    ("090430", "090435", "아모레퍼시픽"),
    # ── 추가 대형주 (시총 5천억+) ──
    ("051910", "051915", "LG화학"),
    ("006400", "006405", "삼성SDI"),
    ("066570", "066575", "LG전자"),
    ("000810", "000815", "삼성화재"),
    ("010950", "010955", "S-Oil"),
    ("003490", "003495", "대한항공"),
    ("000100", "000105", "유한양행"),
    ("051900", "051905", "LG생활건강"),
    ("097950", "097955", "CJ제일제당"),
    # ── 추가 지주사/대형주 (시총 5천억+) ──
    ("000720", "000725", "현대건설"),
    ("011780", "011785", "금호석유"),
    ("120110", "120115", "코오롱인더"),
    ("002020", "002025", "코오롱"),
    ("008770", "008775", "호텔신라"),
    ("000210", "000215", "DL"),
    # ── 추가 금융지주/대형주 ──
    ("071050", "071055", "한국금융지주"),
    ("028260", "02826K", "삼성물산", "삼성물산우B"),
    ("002790", "002795", "아모레G"),
    ("000070", "000075", "삼양홀딩스"),
    ("005940", "005945", "NH투자증권"),
]

# 분석 기준 시작일 (2008 금융위기 등 이상치 제외)
ANALYSIS_START_DATE = "2010-01-01"


class PremiumAnalyzer:
    """단일 종목 보통주/우선주 괴리율 분석기"""

    def __init__(self, common_code: str, preferred_code: str, name: str, preferred_name: str = None):
        self.common_ticker = f"{common_code}.KS"
        self.preferred_ticker = f"{preferred_code}.KS"
        self.common_code = common_code
        self.preferred_code = preferred_code
        self.name = name
        self.preferred_name = preferred_name or f"{name}우"
        self.data = None

    def fetch_data(self, period="max") -> bool:
        """데이터 수집 — DB 우선, 없으면 yfinance fallback"""
        try:
            # ① DB에서 로드 시도
            if os.path.exists(DB_PATH):
                conn = sqlite3.connect(DB_PATH)
                try:
                    common_db = pd.read_sql_query(
                        "SELECT date, close FROM stock_data WHERE stock_code = ? ORDER BY date",
                        conn, params=(self.common_code,), parse_dates=['date'], index_col='date',
                    )
                    preferred_db = pd.read_sql_query(
                        "SELECT date, close FROM stock_data WHERE stock_code = ? ORDER BY date",
                        conn, params=(self.preferred_code,), parse_dates=['date'], index_col='date',
                    )
                    conn.close()

                    if len(common_db) > 100 and len(preferred_db) > 100:
                        common_db.columns = ['common_price']
                        preferred_db.columns = ['preferred_price']
                        self.data = pd.merge(common_db, preferred_db, left_index=True, right_index=True, how='inner')
                        self.data['premium_rate'] = (self.data['preferred_price'] / self.data['common_price'] - 1) * 100
                        self.data['discount_rate'] = -self.data['premium_rate']
                        self._data_source = 'DB'
                        return True
                except Exception:
                    conn.close()

            # ② yfinance fallback
            common_data = yf.download(self.common_ticker, period=period, progress=False)
            if isinstance(common_data.columns, pd.MultiIndex):
                common_data.columns = [col[0] for col in common_data.columns]
            common = common_data[['Close']].copy()
            common.columns = ['common_price']

            preferred_data = yf.download(self.preferred_ticker, period=period, progress=False)
            if isinstance(preferred_data.columns, pd.MultiIndex):
                preferred_data.columns = [col[0] for col in preferred_data.columns]
            preferred = preferred_data[['Close']].copy()
            preferred.columns = ['preferred_price']

            self.data = pd.merge(common, preferred, left_index=True, right_index=True, how='inner')
            self.data['premium_rate'] = (self.data['preferred_price'] / self.data['common_price'] - 1) * 100
            self.data['discount_rate'] = -self.data['premium_rate']
            self._data_source = 'yfinance'

            return len(self.data) > 0
        except Exception as e:
            print(f"  ❌ {self.name} 데이터 수집 실패: {e}")
            return False

    def analyze(self) -> dict:
        """전체 분석 수행 → 결과 dict 반환"""
        if self.data is None or len(self.data) == 0:
            return None

        # 2010년 이후 데이터를 주 분석 기준으로 사용 (2008 금융위기 이상치 제거)
        primary = self.data[self.data.index >= ANALYSIS_START_DATE]
        if len(primary) == 0:
            primary = self.data
        has_pre_period = len(self.data) > len(primary)

        current = self.data.iloc[-1]
        premium = current['premium_rate']
        mean = primary['premium_rate'].mean()
        std = primary['premium_rate'].std()
        median = primary['premium_rate'].median()
        percentile = (primary['premium_rate'] < premium).sum() / len(primary) * 100
        z_score = (premium - mean) / std

        # 점수 계산
        score = 0
        details = []

        if percentile < 10:
            details.append("✅ 역사적 하위 10% (우선주 매우 저평가)")
            score += 40
        elif percentile < 25:
            details.append("✅ 역사적 하위 25% (우선주 저평가)")
            score += 25
        elif percentile > 90:
            details.append("❌ 역사적 상위 10% (우선주 매우 고평가)")
            score -= 40
        elif percentile > 75:
            details.append("❌ 역사적 상위 25% (우선주 고평가)")
            score -= 25

        if z_score < -1.5:
            details.append("✅ 평균 대비 1.5σ 이상 낮음")
            score += 30
        elif z_score < -1.0:
            details.append("✅ 평균 대비 1.0σ 이상 낮음")
            score += 20
        elif z_score > 1.5:
            details.append("❌ 평균 대비 1.5σ 이상 높음")
            score -= 30
        elif z_score > 1.0:
            details.append("❌ 평균 대비 1.0σ 이상 높음")
            score -= 20

        recent_30d = self.data.iloc[-30:]['premium_rate'].mean()
        if premium < recent_30d - 1:
            details.append("✅ 최근 30일 평균보다 1%p 이상 낮음")
            score += 10
        elif premium > recent_30d + 1:
            details.append("❌ 최근 30일 평균보다 1%p 이상 높음")
            score -= 10

        # 추천 판정
        if score >= 40:
            verdict = "🟦 우선주 강력 매수"
            emoji = "🟦"
        elif score >= 20:
            verdict = "🟦 우선주 매수"
            emoji = "🟦"
        elif score <= -40:
            verdict = "🟥 보통주 강력 매수"
            emoji = "🟥"
        elif score <= -20:
            verdict = "🟥 보통주 매수"
            emoji = "🟥"
        else:
            verdict = "⚪ 중립"
            emoji = "⚪"

        prob_preferred = 100 - percentile  # 우선주가 역사적으로 더 비쌌던 비율

        # 기간별 분석
        periods = {}
        period_defs = [('1개월', 30), ('3개월', 90), ('6개월', 180), ('1년', 365), ('3년', 1095), ('5년', 1825)]
        for pname, days in period_defs:
            if len(self.data) >= days:
                pd_data = self.data.iloc[-days:]
                periods[pname] = {
                    'mean': pd_data['premium_rate'].mean(),
                    'min': pd_data['premium_rate'].min(),
                    'max': pd_data['premium_rate'].max(),
                    'diff': premium - pd_data['premium_rate'].mean(),
                }

        # 시장 상황별 (primary 기준)
        self.data['common_ma60'] = self.data['common_price'].rolling(window=60).mean()
        self.data['trend'] = 'neutral'
        self.data.loc[self.data['common_price'] > self.data['common_ma60'] * 1.05, 'trend'] = 'bull'
        self.data.loc[self.data['common_price'] < self.data['common_ma60'] * 0.95, 'trend'] = 'bear'

        primary_trend = self.data[self.data.index >= ANALYSIS_START_DATE] if has_pre_period else self.data
        bull_data = primary_trend[primary_trend['trend'] == 'bull']
        bear_data = primary_trend[primary_trend['trend'] == 'bear']
        bull_avg = bull_data['premium_rate'].mean() if len(bull_data) > 0 else mean
        bear_avg = bear_data['premium_rate'].mean() if len(bear_data) > 0 else mean

        # 변동성
        self.data['premium_change'] = self.data['premium_rate'].diff()

        # 백분위 (primary 기준)
        p10 = np.percentile(primary['premium_rate'], 10)
        p25 = np.percentile(primary['premium_rate'], 25)
        p50 = np.percentile(primary['premium_rate'], 50)
        p75 = np.percentile(primary['premium_rate'], 75)
        p90 = np.percentile(primary['premium_rate'], 90)

        # Top 5 기회 (primary 기준)
        best_preferred = primary.nsmallest(5, 'premium_rate')[['common_price', 'preferred_price', 'premium_rate']]
        best_common = primary.nlargest(5, 'premium_rate')[['common_price', 'preferred_price', 'premium_rate']]

        # 추세별 통계 (primary 기준)
        trend_stats = {}
        for trend_key, trend_name in [('bull', '상승장'), ('bear', '하락장'), ('neutral', '중립장')]:
            td = primary_trend[primary_trend['trend'] == trend_key]
            if len(td) > 0:
                trend_stats[trend_name] = {
                    'count': len(td),
                    'pct': len(td) / len(primary) * 100,
                    'mean': td['premium_rate'].mean(),
                    'median': td['premium_rate'].median(),
                    'std': td['premium_rate'].std(),
                    'min': td['premium_rate'].min(),
                    'max': td['premium_rate'].max(),
                }

        # 전체 기간 참고 통계 (2010 이전 데이터가 있는 경우만)
        full_stats = None
        if has_pre_period:
            full_stats = {
                'data_start': self.data.index[0].strftime('%Y-%m-%d'),
                'data_count': len(self.data),
                'mean': self.data['premium_rate'].mean(),
                'std': self.data['premium_rate'].std(),
                'median': self.data['premium_rate'].median(),
                'min': self.data['premium_rate'].min(),
                'max': self.data['premium_rate'].max(),
                'p10': np.percentile(self.data['premium_rate'], 10),
                'p25': np.percentile(self.data['premium_rate'], 25),
                'p50': np.percentile(self.data['premium_rate'], 50),
                'p75': np.percentile(self.data['premium_rate'], 75),
                'p90': np.percentile(self.data['premium_rate'], 90),
            }

        return {
            'name': self.name,
            'preferred_name': self.preferred_name,
            'common_code': self.common_code,
            'preferred_code': self.preferred_code,
            'common_price': current['common_price'],
            'preferred_price': current['preferred_price'],
            'premium': premium,
            'discount': current['discount_rate'],
            'mean': mean,
            'median': median,
            'std': std,
            'min': primary['premium_rate'].min(),
            'max': primary['premium_rate'].max(),
            'percentile': percentile,
            'z_score': z_score,
            'score': score,
            'verdict': verdict,
            'emoji': emoji,
            'prob_preferred': prob_preferred,
            'details': details,
            'periods': periods,
            'bull_avg': bull_avg,
            'bear_avg': bear_avg,
            'bull_pattern': "상승장에서 우선주가 더 저렴" if bull_avg < bear_avg else "하락장에서 우선주가 더 저렴",
            'daily_vol': abs(self.data['premium_change']).mean(),
            'p10': p10, 'p25': p25, 'p50': p50, 'p75': p75, 'p90': p90,
            'best_preferred': best_preferred,
            'best_common': best_common,
            'trend_stats': trend_stats,
            'data_start': primary.index[0].strftime('%Y-%m-%d'),
            'data_end': self.data.index[-1].strftime('%Y-%m-%d'),
            'data_count': len(primary),
            'has_pre_period': has_pre_period,
            'full_stats': full_stats,
        }

    def create_chart(self, filepath: str):
        """차트 생성"""
        if self.data is None:
            return None

        fig = plt.figure(figsize=(16, 8))

        ax1 = plt.subplot(2, 1, 1)
        ax1.plot(self.data.index, self.data['common_price'], label=self.name, linewidth=1.5, color='#0066cc')
        ax1.plot(self.data.index, self.data['preferred_price'], label=self.preferred_name, linewidth=1.5, color='#ff6600')
        ax1.set_ylabel('주가 (원)', fontsize=11, fontweight='bold')
        ax1.set_title(f'{self.name} vs {self.preferred_name} 주가 추이', fontsize=13, fontweight='bold', pad=15)
        ax1.legend(loc='upper left', fontsize=9)
        ax1.grid(True, alpha=0.3)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))

        ax2 = plt.subplot(2, 1, 2)
        ax2.plot(self.data.index, self.data['premium_rate'], linewidth=1.5, color='#9933cc')
        # 2010년 이후 데이터 기준으로 통계선 표시
        primary_chart = self.data[self.data.index >= ANALYSIS_START_DATE]
        if len(primary_chart) == 0:
            primary_chart = self.data
        ax2.axhline(y=primary_chart['premium_rate'].mean(), color='red', linestyle='--', linewidth=1, alpha=0.7, label='평균(2010~)')
        p25 = np.percentile(primary_chart['premium_rate'], 25)
        p75 = np.percentile(primary_chart['premium_rate'], 75)
        ax2.axhline(y=p25, color='blue', linestyle=':', linewidth=1, alpha=0.5, label='25%ile')
        ax2.axhline(y=p75, color='orange', linestyle=':', linewidth=1, alpha=0.5, label='75%ile')
        ax2.fill_between(self.data.index, p25, p75, alpha=0.1, color='gray')
        ax2.set_ylabel('괴리율 (%)', fontsize=11, fontweight='bold')
        ax2.set_title('괴리율 추이', fontsize=13, fontweight='bold', pad=15)
        # 분석 기준 시작선
        cutoff = pd.Timestamp(ANALYSIS_START_DATE)
        if self.data.index[0] < cutoff:
            ax1.axvline(x=cutoff, color='red', linestyle='--', linewidth=1, alpha=0.5)
            ax1.text(cutoff, ax1.get_ylim()[1], ' 분석기준', color='red', fontsize=8, va='top')
            ax2.axvline(x=cutoff, color='red', linestyle='--', linewidth=1, alpha=0.5)
        ax2.legend(loc='upper left', fontsize=9)
        ax2.grid(True, alpha=0.3)
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))

        plt.tight_layout()
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()
        return filepath


def generate_report(results: list, chart_files: list) -> str:
    """통합 리포트 생성"""
    report_date = datetime.now().strftime('%Y%m%d_%H%M%S')
    from config import DAILY_BACKTEST_DIR
    prem_dir = os.path.join(DAILY_BACKTEST_DIR, 'premium')
    os.makedirs(prem_dir, exist_ok=True)
    filename = os.path.join(prem_dir, f"괴리율분석리포트_{report_date}.md")

    with open(filename, 'w', encoding='utf-8') as f:
        f.write("# 📊 보통주 vs 우선주 괴리율 분석 리포트\n\n")
        f.write(f"**분석일시**: {datetime.now().strftime('%Y년 %m월 %d일 %H:%M:%S')}\n")
        f.write(f"**분석 기준**: {ANALYSIS_START_DATE[:4]}년 이후 데이터 (금융위기 등 이상치 제외)\n\n")
        f.write("---\n\n")

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # Part 1: 오늘의 투자 결론 요약표
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        f.write("## 🎯 오늘의 투자 결론\n\n")

        f.write("| 종목 | 보통주 | 우선주 | 현재 괴리율 | 역사적 위치 | 판정 | 추천 |\n")
        f.write("|:----:|-------:|-------:|:----------:|:----------:|:----:|:-----|\n")
        for r in results:
            pct_label = f"하위 {r['percentile']:.0f}%"
            f.write(f"| **{r['name']}** | {r['common_price']:,.0f}원 | {r['preferred_price']:,.0f}원 "
                    f"| {r['premium']:.2f}% | {pct_label} | {r['emoji']} | {r['verdict']} |\n")
        f.write("\n")

        # 간결한 해석
        f.write("### 💡 핵심 요약\n\n")
        for r in results:
            diff = r['premium'] - r['mean']
            if r['score'] >= 20:
                reason = (f"우선주가 역사적 평균({r['mean']:.1f}%)보다 {abs(diff):.1f}%p 더 저렴. "
                          f"과거 {r['prob_preferred']:.0f}%의 경우보다 우선주가 싸므로 "
                          f"**{r['preferred_name']} 매수 유리** (승률 ~{r['prob_preferred']:.0f}%)")
            elif r['score'] <= -20:
                prob_common = r['percentile']
                reason = (f"우선주가 역사적 평균({r['mean']:.1f}%)보다 {abs(diff):.1f}%p 비쌈. "
                          f"과거 {prob_common:.0f}%의 경우보다 우선주가 비싸므로 "
                          f"**{r['name']}(보통주) 매수 유리** (승률 ~{prob_common:.0f}%)")
            else:
                reason = (f"괴리율({r['premium']:.1f}%)이 평균({r['mean']:.1f}%) 부근. "
                          f"**선호도에 따라 선택** (배당→우선주, 의결권→보통주)")
            f.write(f"- **{r['name']}**: {reason}\n")
        f.write("\n")

        # 투자 시점 가이드표
        f.write("### 📋 투자 시점 가이드\n\n")
        f.write("| 종목 | 우선주 매수 구간 | 중립 구간 | 보통주 매수 구간 |\n")
        f.write("|:----:|:---------------:|:---------:|:---------------:|\n")
        for r in results:
            f.write(f"| {r['name']} | 괴리율 < {r['p25']:.1f}% | "
                    f"{r['p25']:.1f}% ~ {r['p75']:.1f}% | 괴리율 > {r['p75']:.1f}% |\n")
        f.write("\n")

        # 시장 상황별 전략
        f.write("### 📈 시장 상황별 전략\n\n")
        f.write("| 종목 | 상승장 예상 | 하락장 예상 | 패턴 |\n")
        f.write("|:----:|:----------:|:----------:|:-----|\n")
        for r in results:
            if r['bull_avg'] < r['bear_avg']:
                bull_rec = f"우선주({r['preferred_name']})"
                bear_rec = f"보통주({r['name']})"
            else:
                bull_rec = f"보통주({r['name']})"
                bear_rec = f"우선주({r['preferred_name']})"
            f.write(f"| {r['name']} | {bull_rec} | {bear_rec} | {r['bull_pattern']} |\n")
        f.write("\n")

        f.write("---\n\n")

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # Part 2: 종목별 상세 분석
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        for i, r in enumerate(results):
            f.write(f"## 📌 {r['name']} ({r['common_code']}) vs {r['preferred_name']} ({r['preferred_code']})\n\n")

            f.write(f"**분석 기간**: {r['data_start']} ~ {r['data_end']} ({r['data_count']:,}일)\n")
            if r['has_pre_period'] and r['full_stats']:
                f.write(f"**전체 데이터**: {r['full_stats']['data_start']} ~ {r['data_end']} ({r['full_stats']['data_count']:,}일) — {ANALYSIS_START_DATE[:4]}년 이전은 참고용\n")
            f.write("\n")

            # 현재 상황
            f.write("### 현재 상황\n\n")
            f.write("| 항목 | 값 |\n")
            f.write("|:----:|:---|\n")
            f.write(f"| {r['name']} | {r['common_price']:,.0f}원 |\n")
            f.write(f"| {r['preferred_name']} | {r['preferred_price']:,.0f}원 |\n")
            f.write(f"| **현재 괴리율** | **{r['premium']:.2f}%** |\n")
            f.write(f"| 우선주 할인율 | {r['discount']:.2f}% |\n")
            f.write(f"| 역사적 위치 | 하위 {r['percentile']:.1f}% |\n")
            f.write(f"| Z-Score | {r['z_score']:.2f}σ |\n")
            f.write(f"| 종합 점수 | {r['score']}점 (±100점 만점) |\n")
            f.write(f"| **판정** | **{r['verdict']}** |\n\n")

            # 세부 근거
            if r['details']:
                f.write("**판정 근거:**\n\n")
                for d in r['details']:
                    f.write(f"- {d}\n")
                f.write("\n")

            # 역사적 통계
            period_label = f" ({ANALYSIS_START_DATE[:4]}년~)" if r['has_pre_period'] else ""
            f.write(f"### 괴리율 통계{period_label}\n\n")
            f.write("| 지표 | 값 |\n")
            f.write("|:----:|:---|\n")
            f.write(f"| 평균 | {r['mean']:.2f}% |\n")
            f.write(f"| 중간값 | {r['median']:.2f}% |\n")
            f.write(f"| 표준편차 | {r['std']:.2f}% |\n")
            f.write(f"| 최소 (우선주 최저평가) | {r['min']:.2f}% |\n")
            f.write(f"| 최대 (우선주 최고평가) | {r['max']:.2f}% |\n\n")

            f.write("| 백분위 | 괴리율 | 의미 |\n")
            f.write("|:-----:|:------:|:-----|\n")
            f.write(f"| 10% | {r['p10']:.2f}% | 우선주 매우 저평가 |\n")
            f.write(f"| 25% | {r['p25']:.2f}% | 우선주 저평가 |\n")
            f.write(f"| 50% | {r['p50']:.2f}% | 중간값 |\n")
            f.write(f"| 75% | {r['p75']:.2f}% | 우선주 고평가 |\n")
            f.write(f"| 90% | {r['p90']:.2f}% | 우선주 매우 고평가 |\n\n")

            # 전체 기간 참고 비교
            if r['has_pre_period'] and r['full_stats']:
                fs = r['full_stats']
                f.write(f"**📎 참고: 전체 기간 ({fs['data_start']}~) 통계 비교**\n\n")
                f.write(f"| 지표 | {ANALYSIS_START_DATE[:4]}년 이후 | 전체 기간 |\n")
                f.write("|:----:|:----------:|:---------:|\n")
                f.write(f"| 평균 | {r['mean']:.2f}% | {fs['mean']:.2f}% |\n")
                f.write(f"| 중간값 | {r['median']:.2f}% | {fs['median']:.2f}% |\n")
                f.write(f"| 표준편차 | {r['std']:.2f}% | {fs['std']:.2f}% |\n")
                f.write(f"| 최소 | {r['min']:.2f}% | {fs['min']:.2f}% |\n")
                f.write(f"| 최대 | {r['max']:.2f}% | {fs['max']:.2f}% |\n\n")

            # 기간별 분석
            if r['periods']:
                f.write("### 기간별 괴리율\n\n")
                f.write("| 기간 | 평균 | 최소 | 최대 | 현재 대비 |\n")
                f.write("|:----:|:----:|:----:|:----:|:---------:|\n")
                for pname, pd in r['periods'].items():
                    f.write(f"| 최근 {pname} | {pd['mean']:.2f}% | {pd['min']:.2f}% | {pd['max']:.2f}% | {pd['diff']:+.2f}%p |\n")
                f.write("\n")

            # 시장 상황별
            f.write("### 시장 상황별 괴리율\n\n")
            f.write("| 구분 | 기간 | 평균 괴리율 | 중간값 |\n")
            f.write("|:----:|:----:|:----------:|:------:|\n")
            for tname, ts in r['trend_stats'].items():
                f.write(f"| {tname} | {ts['count']}일 ({ts['pct']:.1f}%) | {ts['mean']:.2f}% | {ts['median']:.2f}% |\n")
            f.write("\n")

            # Top 5 극단 기회
            f.write("### 역사적 극단값 (Top 5)\n\n")
            f.write(f"**🟦 우선주 최저평가 시점 (괴리율 최저)**\n\n")
            f.write(f"| 날짜 | {r['name']} | {r['preferred_name']} | 괴리율 |\n")
            f.write("|:----:|--------:|----------:|:------:|\n")
            for date, row in r['best_preferred'].iterrows():
                f.write(f"| {date.strftime('%Y-%m-%d')} | {row['common_price']:,.0f}원 | {row['preferred_price']:,.0f}원 | **{row['premium_rate']:.2f}%** |\n")
            f.write("\n")

            f.write(f"**🟥 보통주 최저평가 시점 (괴리율 최고)**\n\n")
            f.write(f"| 날짜 | {r['name']} | {r['preferred_name']} | 괴리율 |\n")
            f.write("|:----:|--------:|----------:|:------:|\n")
            for date, row in r['best_common'].iterrows():
                f.write(f"| {date.strftime('%Y-%m-%d')} | {row['common_price']:,.0f}원 | {row['preferred_price']:,.0f}원 | **{row['premium_rate']:.2f}%** |\n")
            f.write("\n")

            # 차트
            if i < len(chart_files) and chart_files[i]:
                f.write(f"### 차트\n\n")
                f.write(f"![{r['name']} 괴리율 차트]({os.path.basename(chart_files[i])})\n\n")

            f.write("---\n\n")

        # 공통 안내
        f.write("## ⚠️ 주의사항\n\n")
        f.write("1. **괴리율은 평균 회귀 경향**이 있지만, 장기간 지속될 수도 있습니다.\n")
        f.write("2. **우선주는 유동성이 낮아** 대량 매매 시 슬리피지가 발생할 수 있습니다.\n")
        f.write("3. **배당 기준일 전후**로 괴리율이 일시적으로 변동할 수 있습니다.\n")
        f.write("4. 이 분석은 **참고용**이며, 투자 판단은 본인의 책임입니다.\n\n")

        f.write("---\n\n")
        f.write("**데이터 출처**: market_data.db (SQLite) / Yahoo Finance (fallback)  \n")
        f.write("**분석 도구**: Python + pandas\n")

    return filename


def main():
    print("=" * 60)
    print("  보통주 vs 우선주 괴리율 통합 분석")
    print("=" * 60)
    print()

    results = []
    chart_files = []
    report_date = datetime.now().strftime('%Y%m%d_%H%M%S')

    for pair in STOCK_PAIRS:
        common_code, preferred_code, name = pair[0], pair[1], pair[2]
        pref_name = pair[3] if len(pair) > 3 else None
        print(f"📊 {name} ({common_code}/{preferred_code}) 분석 중...")
        analyzer = PremiumAnalyzer(common_code, preferred_code, name, pref_name)

        if not analyzer.fetch_data(period="max"):
            print(f"  ⚠️ {name} 건너뜀 (데이터 없음)")
            continue

        result = analyzer.analyze()
        if result is None:
            print(f"  ⚠️ {name} 건너뜀 (분석 실패)")
            continue

        results.append(result)

        # 차트 생성
        from config import DAILY_BACKTEST_DIR
        prem_dir = os.path.join(DAILY_BACKTEST_DIR, 'premium')
        os.makedirs(prem_dir, exist_ok=True)
        chart_path = os.path.join(prem_dir, f"괴리율_{name}_{report_date}_차트.png")
        analyzer.create_chart(chart_path)
        chart_files.append(chart_path)

        src = getattr(analyzer, '_data_source', 'yfinance')
        print(f"  ✅ {name}: 괴리율 {result['premium']:.2f}% (하위 {result['percentile']:.1f}%) → {result['verdict']}  [{src}]")

    if not results:
        print("❌ 분석된 종목이 없습니다.")
        return

    print()

    # 통합 리포트 생성
    filename = generate_report(results, chart_files)

    print(f"✅ 통합 리포트 생성 완료: {filename}")
    print()

    # 요약 출력
    print("📋 요약:")
    print(f"{'종목':>8} | {'괴리율':>8} | {'위치':>8} | 판정")
    print("-" * 50)
    for r in results:
        print(f"{r['name']:>8} | {r['premium']:>7.2f}% | 하위 {r['percentile']:>4.1f}% | {r['verdict']}")

    print()
    print("=" * 60)
    print("  분석 완료!")
    print("=" * 60)


if __name__ == "__main__":
    main()
