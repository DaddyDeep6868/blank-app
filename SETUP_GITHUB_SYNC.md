# DingerLab GitHub sync setup

This bundle is designed for the repo:
- DaddyDeep6868/blank-app

## What this adds
- Latest DingerLab app files at repo root
- A sync script: `scripts/sync_dingerlab_from_zip.py`
- A GitHub Actions workflow: `.github/workflows/sync-dingerlab-from-zip.yml`
- An `incoming/` folder for future build zips

## Easiest ongoing workflow
After these files are in your repo once:

1. Open the repo on GitHub.
2. Upload the newest `DingerLab_streamlit_vX.XX.zip` into `incoming/`.
3. The GitHub Action will:
   - extract the zip
   - overwrite the main app files
   - commit the update
   - push automatically

## Manual local option
If you want to do it locally instead:

```bash
python3 scripts/sync_dingerlab_from_zip.py       --zip incoming/DingerLab_streamlit_v1.34.zip       --repo .       --commit-message "Update DingerLab to v1.34"       --push
```

## First-time repo setup
Upload this bundle into `DaddyDeep6868/blank-app` and commit it.

Important folders/files included:
- `.github/workflows/sync-dingerlab-from-zip.yml`
- `scripts/sync_dingerlab_from_zip.py`
- `incoming/README.md`

## Notes
- The workflow uses the repository's built-in `GITHUB_TOKEN` to push commits.
- In repo settings, make sure GitHub Actions has permission to write contents if pushes are blocked.
- The workflow expects the zip to contain:
  - `DingerLab.html`
  - `streamlit_app.py`
  - `login_wallpaper.png`
  - `requirements.txt`
  - `README_streamlit.md`
