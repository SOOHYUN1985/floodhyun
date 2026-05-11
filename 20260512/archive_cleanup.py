"""
archive_cleanup.py - archive 폴더 정리 스크립트
archive_cleanup.bat 에서 호출됨
사용법: python archive_cleanup.py <mode>
  mode 1: 최근 5회분만 보관
  mode 2: 7일 이전 파일 삭제
  mode 3: 30일 이전 파일 삭제
"""
import os
import re
import sys
import time


def remove_empty_dirs(base):
    for root, dirs, files in os.walk(base, topdown=False):
        for d in dirs:
            dp = os.path.join(root, d)
            if not os.listdir(dp):
                os.rmdir(dp)


def keep_recent_n(base, n=5):
    total_deleted = 0
    for sub in ['daily_backtest', 'daily_position', 'weekly_research']:
        sub_dir = os.path.join(base, sub)
        if not os.path.isdir(sub_dir):
            continue
        all_files = []
        for root, dirs, files in os.walk(sub_dir):
            for f in files:
                all_files.append(os.path.join(root, f))
        stamps = set()
        for fp in all_files:
            m = re.search(r'(\d{8}_\d{6}|\d{8})', os.path.basename(fp))
            if m:
                stamps.add(m.group(1)[:8])
        keep = sorted(stamps)[-n:]
        deleted = 0
        for fp in all_files:
            m = re.search(r'(\d{8}_\d{6}|\d{8})', os.path.basename(fp))
            if m and m.group(1)[:8] not in keep:
                os.remove(fp)
                deleted += 1
        total_deleted += deleted
        print(f'  [{sub}] {deleted}개 삭제 (최근 {n}회 초과)')
    print(f'  총 {total_deleted}개 파일 삭제 (최근 {n}회 초과)')
    remove_empty_dirs(base)


def keep_after_days(base, days):
    cutoff = time.time() - days * 24 * 3600
    n = 0
    for root, dirs, files in os.walk(base):
        for f in files:
            fp = os.path.join(root, f)
            if os.path.getmtime(fp) < cutoff:
                os.remove(fp)
                n += 1
    print(f'  {n}개 파일 삭제 ({days}일 이전)')
    remove_empty_dirs(base)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('[ERROR] mode 인자 필요 (1/2/3)')
        sys.exit(1)

    mode = sys.argv[1]
    base = 'results/archive'

    if mode == '1':
        keep_recent_n(base, 5)
    elif mode == '2':
        keep_after_days(base, 7)
    elif mode == '3':
        keep_after_days(base, 30)
    else:
        print(f'[ERROR] 알 수 없는 mode: {mode}')
        sys.exit(1)
