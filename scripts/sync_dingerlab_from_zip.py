#!/usr/bin/env python3
import argparse
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REQUIRED = [
    'DingerLab.html',
    'streamlit_app.py',
    'login_wallpaper.png',
    'requirements.txt',
    'README_streamlit.md',
]

def run(cmd, cwd=None, check=True):
    print('+', ' '.join(cmd))
    return subprocess.run(cmd, cwd=cwd, check=check)

def main():
    parser = argparse.ArgumentParser(description='Sync DingerLab build files from a zip into the current repo.')
    parser.add_argument('--zip', required=True, help='Path to DingerLab_streamlit zip file')
    parser.add_argument('--repo', default='.', help='Path to target git repo')
    parser.add_argument('--commit-message', default='Update DingerLab build', help='Commit message to use')
    parser.add_argument('--push', action='store_true', help='Push after committing')
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    zip_path = Path(args.zip).resolve()
    if not zip_path.exists():
        raise SystemExit(f'Zip not found: {zip_path}')
    if not (repo / '.git').exists():
        raise SystemExit(f'Target is not a git repo: {repo}')

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp)
        missing = [name for name in REQUIRED if not (tmp / name).exists()]
        if missing:
            raise SystemExit(f'Missing required files in zip: {", ".join(missing)}')
        for name in REQUIRED:
            shutil.copy2(tmp / name, repo / name)

    run(['git', 'add', *REQUIRED], cwd=repo)
    status = subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=repo)
    if status.returncode == 0:
        print('No changes to commit.')
        return
    run(['git', 'commit', '-m', args.commit_message], cwd=repo)
    if args.push:
        run(['git', 'push'], cwd=repo)

if __name__ == '__main__':
    main()
