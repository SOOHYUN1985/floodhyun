"""
메인 파이프라인

실행:
    python main.py                # 최신일 기준, 백테스트 포함, 리포트 생성
    python main.py --asof 20200320  # 특정 시점(그날까지의 데이터만) 분석
    python main.py --no-backtest    # 유사구간·비중 분석만 (빠름)

절차: 로딩→검증→Feature→정렬→국면→유사구간→Forward통계→비중→백테스트→리포트
"""

import os
import sys
import argparse
import numpy as np
import pandas as pd

# 한글 콘솔(cp949)에서도 출력이 깨지지 않도록 UTF-8로 재설정
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

import config as C
import data_layer
import features
import regime
import analog
import allocation
import backtest
import report


def _align(feats: dict) -> dict:
    common = None
    for df in feats.values():
        common = df.index if common is None else common.intersection(df.index)
    return {k: v.loc[common].copy() for k, v in feats.items()}


def run(asof: str | None = None, do_backtest: bool = True) -> dict:
    print('[1/6] 데이터 로딩 & 검증 ...')
    raw, warnings = data_layer.load_all()
    for w in warnings:
        print('   [!]', w)

    print('[2/6] Feature 계산 ...')
    feats = {mk: features.build_features(df) for mk, df in raw.items()}
    features.add_relative_strength(feats)
    feats = _align(feats)

    # as-of 위치 결정
    master_idx = next(iter(feats.values())).index

    # 유사도 Feature가 두 시장 모두 완비된 마지막 날짜만 as-of 후보로 사용한다.
    # (지수 가격과 투자자 수급의 최신일이 다를 수 있어 발생하는 NaN 문제 방지)
    cols = [c for c in C.ANALOG_FEATURES if all(c in f.columns for f in feats.values())]
    complete = pd.Series(True, index=master_idx)
    for f in feats.values():
        complete &= ~f[cols].isna().any(axis=1)

    if asof:
        target = pd.Timestamp(asof)
        pos = int(master_idx.searchsorted(target, side='right')) - 1
        if pos < 0:
            raise SystemExit(f'as-of 날짜가 데이터 범위 이전입니다: {asof}')
    else:
        pos = len(master_idx) - 1

    # 요청/최신 위치에서 뒤로 이동하여 Feature 완비된 마지막 날짜로 스냅
    snap = complete.to_numpy()[:pos + 1]
    if snap.any():
        real_pos = int(np.nonzero(snap)[0][-1])
        if real_pos != pos:
            print(f"   (데이터 최신일 정렬: {master_idx[pos].date()} → "
                  f"{master_idx[real_pos].date()}, Feature 완비 기준)")
        pos = real_pos
    asof_date = master_idx[pos]
    print(f'[3/6] 기준일 = {asof_date.date()} (position {pos})')

    print('[4/6] 시장국면 · 유사구간 · Forward · 비중 ...')
    markets = {}
    for mk, feat in feats.items():
        row = feat.iloc[pos]
        reg = regime.classify_row(row)
        an = analog.analyze(feat, pos, full=True)
        al = allocation.compute(an['forward'], an.get('excursion'))
        markets[mk] = {'row': row, 'regime': reg, 'analog': an, 'alloc': al}
        print(f"   - {C.MARKETS[mk]['name']}: 국면={reg['regime']}, "
              f"N={an['n_analogs']}, 권장비중={al['weight_pct']:.0f}%")

    analysis = {'asof': asof_date, 'markets': markets, 'warnings': warnings}

    if do_backtest:
        print('[5/6] Walk-forward 포트폴리오 백테스트 (다중 전략·민감도·부트스트랩) ...')
        analysis['backtest'] = backtest.run(feats['KOSPI'], feats['KOSDAQ'])
        bt = analysis['backtest']
        bal = bt['metrics'].get('균형형', {})
        print(f"   - 리밸런싱 {bt['n_rebalances']}회 × 2시장 = 유사구간검색 {bt['n_analog_searches']}회, "
              f"전략 시뮬레이션 {bt['n_strategy_sims']}종")
        print(f"   - 균형형 CAGR {bal.get('cagr')}% / MDD {bal.get('mdd')}% / Sharpe {bal.get('sharpe')}")
    else:
        print('[5/6] 백테스트 생략(--no-backtest)')

    print('[6/6] 리포트 생성 ...')
    # 하루에 여러 번 실행할 수 있으므로 결과 폴더에 실행 시각(HHMMSS)까지 포함
    from datetime import datetime
    run_time = datetime.now().strftime('%H%M%S')
    outdir = os.path.join(C.RESULTS_DIR, f"{asof_date.strftime('%Y%m%d')}_{run_time}")
    paths = report.generate(analysis, outdir)
    print(f"   [OK] Markdown: {paths['markdown']}")
    print(f"   [OK] HTML    : {paths['html']}")
    print(f"   [OK] Excel   : {paths['excel']}")
    analysis['paths'] = paths
    return analysis


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--asof', default=None, help='기준일 YYYYMMDD (기본: 최신)')
    ap.add_argument('--no-backtest', action='store_true', help='백테스트 생략')
    ap.add_argument('--open', action='store_true', help='완료 후 HTML 리포트 자동 열기')
    args = ap.parse_args()
    analysis = run(asof=args.asof, do_backtest=not args.no_backtest)

    html_path = analysis['paths']['html']
    # bat 등에서 참조할 수 있도록 최신 HTML 경로 기록
    with open(os.path.join(C.RESULTS_DIR, 'latest_report.txt'), 'w', encoding='utf-8') as f:
        f.write(html_path)

    if args.open:
        try:
            os.startfile(html_path)   # 한글 경로도 안전하게 열림
        except Exception as e:
            print(f'   (자동 열기 실패: {e})')

    print('\n완료. HTML 리포트를 브라우저에서 확인하세요.')


if __name__ == '__main__':
    main()
