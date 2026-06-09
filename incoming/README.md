Drop a new DingerLab zip in this folder to trigger the GitHub Action.

Recommended filename pattern:
- DingerLab_streamlit_v1.34.zip
- DingerLab_streamlit_v1.35.zip

What happens next:
1. The workflow reads the newest zip in this folder.
2. It extracts the required DingerLab files.
3. It overwrites the repo root copies of:
   - DingerLab.html
   - streamlit_app.py
   - login_wallpaper.png
   - requirements.txt
   - README_streamlit.md
4. It commits and pushes the update automatically.
