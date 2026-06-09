# DingerLab on Streamlit Community Cloud

Run DingerLab from any device (phone, work laptop, etc.) via a free Streamlit
Community Cloud deployment.

## Files
- `DingerLab.html` - the full app (unchanged behavior; now also accepts odds injected by the wrapper)
- `streamlit_app.py` - thin Streamlit wrapper that fetches OddsBlaze odds server-side and renders the app
- `requirements.txt` - Python dependencies

## Why a wrapper?
OddsBlaze blocks direct browser calls (CORS), which is why the local version
uses `oddsblaze_proxy.py` on `localhost:8787`. Remote users can't reach your
localhost, so the wrapper fetches odds **server-side** (no CORS) and injects
them into the app as `window.DL_RAW_ODDS`. The in-app **Load odds** button then
uses that data automatically.

## Deploy steps
1. Create a **GitHub repo** (public or private) and add these 3 files:
   - `DingerLab.html`
   - `streamlit_app.py`
   - `requirements.txt`
2. Go to https://share.streamlit.io and sign in with GitHub.
3. Click **Create app** -> **Deploy a public app from GitHub**.
4. Pick your repo/branch, set **Main file path** to `streamlit_app.py`, click **Deploy**.
5. Wait ~1-2 minutes. You'll get a public URL like `https://<you>-dingerlab.streamlit.app`.

## Keep your API key private (recommended)
Don't hardcode your key if the repo is public. Instead:
1. In the deployed app, open **Manage app -> Settings -> Secrets**.
2. Add:
   ```
   ODDSBLAZE_KEY = "your-oddsblaze-key"
   ```
3. Save. The wrapper reads `st.secrets["ODDSBLAZE_KEY"]` automatically.

## Using the app
1. In the left sidebar, confirm your key and click **Fetch live odds**.
2. Inside the app, click **Load odds** as usual - it now uses the injected data.
3. Build parlays, save them, and track results.

## Notes / limitations
- **Saved parlays & calibration** use the browser's localStorage, scoped to the
  app's embedded frame. They persist per browser/device (not synced across
  devices).
- The **stake prompt** on Save may be suppressed inside the embedded frame on
  some browsers; if so the parlay still saves (stake blank) and you can ignore it.
- Free Streamlit apps sleep after inactivity and wake on the next visit.
- `oddsblaze_proxy.py` is only needed for running locally; it is not used on Streamlit.

## New in v1.37 — The Sharp Layer
- **🔥 Steam radar** (Games tab): compares all 4 books against each other over a rolling
  15-minute window. When one book moves sharply (>=2.5 implied-prob pts) and another lags,
  the lagging book is flagged as potential **stale value**, with a toast alert on new hits.
  Works best with auto-refresh (60s) on.
- **📈 CLV tracker** (Tracking tab): every saved parlay leg now stores its bet-time price and
  devigged fair probability. While odds keep refreshing, the app snapshots each leg's line and
  freezes the last one seen before first pitch as the *closing line*. The Tracking tab shows a
  CLV scorecard (beat-the-close %, avg CLV in prob points) plus a per-parlay CLV chip.
  Beating the close consistently = real edge, visible in weeks instead of months.
- Auto-grader now skips non-HR legs instead of silently grading them as HR bets.
