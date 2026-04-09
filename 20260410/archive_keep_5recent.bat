@echo off
chcp 65001 >nul
echo ======================================================================
echo   Archive 정리 — 각 폴더별 최근 5회분만 보관
echo ======================================================================
echo.

cd /d "%~dp0"
set "PYTHON=%~dp0venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

"%PYTHON%" -c "
import os, re
from collections import defaultdict

base = 'results/archive'
n = 0

for sub in ['daily_backtest', 'daily_position', 'weekly_research']:
    sub_dir = os.path.join(base, sub)
    if not os.path.isdir(sub_dir):
        continue

    # premium 하위 포함 전체 파일
    all_files = []
    for root, dirs, files in os.walk(sub_dir):
        for f in files:
            all_files.append(os.path.join(root, f))

    # 타임스탬프 추출 (YYYYMMDD 또는 YYYYMMDD_HHMMSS)
    ts_pattern = re.compile(r'(\d{8}(?:_\d{6})?)')
    groups = defaultdict(list)
    for fp in all_files:
        m = ts_pattern.search(os.path.basename(fp))
        ts = m.group(1)[:8] if m else '00000000'  # 날짜만 기준
        groups[ts].append(fp)

    # 날짜 내림차순, 최근 5개 날짜 유지
    sorted_dates = sorted(groups.keys(), reverse=True)
    keep_dates = set(sorted_dates[:5])

    for ts, files in groups.items():
        if ts not in keep_dates:
            for fp in files:
                os.remove(fp)
                n += 1

    print(f'  {sub}: {len(sorted_dates)}날짜 중 {min(5, len(sorted_dates))}개 보관')

# 빈 폴더 정리
for root, dirs, files in os.walk(base, topdown=False):
    for d in dirs:
        dp = os.path.join(root, d)
        if not os.listdir(dp):
            os.rmdir(dp)

print(f'  총 {n}개 파일 삭제')
"

echo.
echo [OK] 완료
timeout /t 5
