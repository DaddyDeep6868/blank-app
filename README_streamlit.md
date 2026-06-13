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

## New in v1.38 — The Analytics Layer
- **🎲 Monte Carlo simulator** (Tracking tab → "Simulate card"): runs 10,000 simulated days
  over all pending saved parlays. Shared legs across parlays win/lose together, and legs in the
  same game are correlated (Gaussian copula, ρ=0.18). Shows expected P&L, P(profitable day),
  P(losing every bet), 5th/95th percentiles, a P&L histogram, and a per-parlay simulated win%.
  Parlays without a stake are assumed $10 (noted in the output).
- **📋 Model report card** (Tracking tab, appears at 5+ graded legs): leg-level calibration
  table (predicted band vs actual hit rate), Brier score with a skill score vs the naive
  baseline, and per-market accuracy breakdown.
- **Auto-grader upgraded to all 5 markets**: HR, 1+ Hit, 2+ Hits, 2+ Total Bases (computed from
  hits/doubles/triples/HR), and 1+ RBI are now graded from final box scores — and individual
  legs get graded even while a parlay waits on other games.
- Saved legs now also store the model's per-leg probability (powers the report card and sim).
- Fixed: Tracking-tab buttons showed literal "\ud83e..." text instead of emoji.

## New in v1.39 — The Awareness Layer
- **👀 "What changed" feed** (top of Games tab): a persistent, chronological diff of the slate
  across refreshes *and* sessions — lineups locking 📋, probable-starter changes 🔁, temp swings
  ≥5°F 🌡️, wind-to-CF shifts ≥5 mph 💨, roof open/close calls 🏟️, and the biggest price moves
  📈📉 (≥1.5 implied pts). Events touching players in your saved pending parlays or current slip
  get a blue **"your play"** tag plus a heads-up toast. Survives closing the browser; Clear
  button wipes it. Updates on slate load, odds refresh, and lineup checks.

## New in v1.40 — Matchup DNA (pitch-type modeling)
- **🧬 New model factor**: the HR model now adjusts for *how this batter's power profile matches
  this pitcher's actual arsenal*. The Streamlit wrapper fetches Baseball Savant's public
  pitch-arsenal leaderboards server-side (cached 6h): each pitcher's usage% by pitch type, and
  each batter's ISO + PA by pitch type.
- **The math**: batter's usage-weighted expected ISO vs this arsenal ÷ his overall ISO, with
  each pitch-type ISO shrunk toward his overall by sample size (k=30 PA), clamped ×0.70–×1.35,
  neutral below 40 total PA. A fastball crusher facing a slider-heavy starter gets faded; facing
  a fastball-heavy starter gets boosted.
- **In the UI**: a purple 🧬 chip appears on player rows when the factor moves ≥5% (hover for
  the arsenal breakdown), and "Matchup DNA (pitch types)" shows in every player's factors
  dropdown. The sidebar reports how many arsenals/profiles loaded; the activity log confirms it
  in-app.
- **Graceful degradation**: if Savant data can't be fetched (or when running the HTML without
  the wrapper), every multiplier is ×1.00 and the app behaves exactly as before. Applies to the
  HR market only.

## v1.41 — Insights fix
- **Fixed: "No HR prices yet" on a loaded slate.** The cheat sheet / Top 5 / heatmap / Coach
  mode / Command Center all required a *two-sided* (Over+Under) market to compute a devigged
  fair probability — but HR props are often posted one-sided, so the whole Insights layer could
  stay empty even with prices loaded. Now falls back to the implied probability of the best
  price when no Under exists (rows carry a fairSrc flag: novig vs implied).
- Empty states are now diagnostic: they distinguish "no HR odds loaded at all" (key/quota or
  books haven't posted props yet), "lineups filter hiding everyone" (Confirmed-only before
  lineups post), and "filters too strict".

## v1.42 — Wager calculator on parlay cards
- Cross-game pair cards and N-leg builder cards now show **Wager / Potential payout /
  Potential profit** rows under Suggested stake. The wager input is editable and recalculates
  live using the same best decimal odds the card's EV uses (same-book best, falling back to
  mixed-books). Defaults to the Kelly suggested stake when it's a bet, otherwise $10.

## Server-side sync mode

Use `dingerlab_server.py` when you want the same tracking data across devices.

### Run locally

```bash
pip install -r requirements.txt
python dingerlab_server.py
```

Then open the shown server URL in your browser. Do **not** open `DingerLab.html` directly if you want sync.

### What syncs

- Saved slips / tracked plays
- Bet outcomes after grading
- Frozen board snapshots
- Model scorecard exports

The server writes data to:

```text
server_data/dingerlab_server_state.json
```

If you deploy this online, use a host with persistent disk/storage so this JSON file is not wiped between restarts.

### Server-side grading

The server checks pending tracked slips after games go final. For HR legs, it verifies homer results from MLB `feed/live`; for hits, 2+ hits, total bases, and RBI, it uses final MLB box scores. The browser also has a **☁️ Server sync** button and the **🤖 Grade pending** button calls the server when server mode is active.

### Deploy note

For multi-device use, deploy `dingerlab_server.py` on a small always-on host such as Render, Railway, Replit, Fly.io, or a VPS. Set `PORT` if your host requires it.
## New in v1.46 — No password screen + versioned zip
- Removed the password screen for direct app access.
- Updated the in-app version badge to v1.46.
- Zip artifacts should be named with the matching app version going forward.
- Confirmed pre-game filter remains included.
## New in v1.47 — Ready to Bet board + guardrails
- Added a user-friendly Dashboard board for actionable plays only: confirmed starter, pre-game, priced, positive edge, and positive EV.
- Added short Do Not Bet / Wait warnings for clutter-free guardrails.
- Added a simple max player exposure control and exposure snapshot.
- Updated the in-app version badge to v1.47.
## New in v1.48 — Hidden Streamlit sidebar
- Hid the Streamlit API-key/sidebar panel so the app opens directly into DingerLab.
- Odds and Matchup DNA still load automatically in the wrapper.
- Updated the in-app version badge to v1.48.
## New in v1.49 — Local slate date fix
- Fixed the Slate date default so late-night users do not get tomorrow's date from UTC time.
- Updated the board-empty warning to remind users to check the Slate date.
- Updated the in-app version badge to v1.49.
## New in v1.50 — Server odds proxy fix
- Added a Flask `/api/oddsblaze` proxy for Render/server mode so browser CORS no longer causes `Failed to fetch` for books.
- Fetch slate now uses the same-origin server proxy on `mlb-slate.onrender.com`.
- Updated the in-app version badge to v1.50.
## New in v1.51 — Player-filter empty-state fix
- Changed the confirmed pre-game filter empty-state from an alarming board-empty warning to a clear info message.
- When the filter is ON before lineups post, the app now explains that no confirmed starters are available yet.
- Updated the in-app version badge to v1.51.
## New in v2.0 — Command Center rebuild
- Added Dinger Score and 1–5 star ratings for every priced player-market.
- Rebuilt Dashboard into a v2 Command Center with top star plays, best combos, daily park report, and ready-board guardrails.
- Reworked game cards to show clean top star plays first, with advanced tables collapsed.
- Added click-through player detail drawer with all market ratings.
## New in v2.1 — Upgraded Daily Park Report
- Rebuilt Daily Park Report with ranked expandable cards, HR-vs-average boost, directional wind/carry adjustment, temperature, humidity/elevation, and roof/indoor handling.
- Park boost now separates park base, wind adjustment, temperature adjustment, and elevation/humidity instead of using a simple generic formula.
- Updated the in-app version badge to v2.1.
## New in v2.2 — Today’s Games v2 Board
- Rebuilt the Games tab into a modern Today’s Games board inspired by high-end MLB predictor dashboards.
- Added hero slate summary, projected HR total, filter-chip bar, ranked matchup cards, Watch These rows, and two-column team player cards.
- Player cards now show Dinger Score, model %, best odds, EV, edge, badges, and quick detail access while keeping advanced tables collapsed.
## New in v3.0 — Edge Engine + Due Meter
- Added a structured Edge Profile for every player-market with component scores: Power, Recent Form, Pitcher Matchup, Park/Weather, Lineup, Odds Value, Confidence, and Risk.
- Added earned badges such as Trophy, Star, Due Meter, Park Edge, P-Weak, Power, EV+, Lineup Lift, Steam, and Out.
- Added a Due Meter for HR targets using estimated HR drought vs expected HR gap, model probability, power, park/weather, and pitcher matchup. This is a signal, not a guarantee.
- Upgraded player detail drawer into an Intelligence Report with score breakdown, model consensus, reasons, and risks.
## New in v3.1 — Compact scrollable player reports
- Made the Player Intelligence Report smaller and easier to read on laptops.
- The report modal now has its own vertical scroll area, so mouse-wheel scrolling works while the pointer is on the report window.
- Tightened spacing, sticky header, compact score orb, compact due meter, smaller market rows, and four-column score breakdown on desktop.
## New in v3.2 — Fixed player report scrolling
- Forced the Player Intelligence Report to use a fixed-height internal scroll area.
- Added wheel/touch handlers that manually scroll the report window, which fixes cases where Streamlit/iframe/browser scrolling captures the mouse wheel.
- Added small scroll status text at the bottom of the report.
## New in v3.3 — Clickable filters + Cross Play Builder
- Made the Today’s Games filter chips clickable and active-state aware.
- Filters now actually narrow the player cards using the Edge Engine: HR Alert, Trophy, Star, Park Edge, P-Weak, EV, Due/Hot HR, Lineup/Sweet Spot, Matchup, etc.
- Added a Cross Play Builder directly on the Games page. Enter a custom number of legs, choose style and market scope, then build best-chance cross-game slips from the current slate data.
- Cross Play outputs include win chance, odds, EV, average edge, add-to-slip, track, and copy actions.
## New in v3.4 — Left section rail, system scrolling, Cross Play metrics
- Moved the main sections into a sticky left-side rail on desktop, with compact icon labels.
- Added system-wide custom momentum-style scrolling visuals and stable scrollbars across the app.
- Cross Play cards no longer show blank Odds/EV/Avg Edge. If book odds are missing, they show model Fair Odds, $10 return estimate, Value Grade, Avg Edge Score, Odds Value, Model Edge, and route status.
- When real book odds are available, Cross Play still shows priced EV.
## New in v4.0 — Data Intelligence Module
- Added a Data tab that builds a player-market feature store for prop and parlay modeling.
- Includes model probability, fair odds, best odds, edge/EV, Edge Score, Due Score, Barrel/HardHit/SweetSpot/Pull-Air proxies, ISO/wOBA handedness proxies, pitcher weakness, bullpen HR risk, bullpen exposure, park/weather boost, lineup status, and umpire placeholder.
- Added modern era weighting: 2023–2026 = 45%, 2018–2022 = 25%, 2015–2017 = 15%, 2008–2014 = 10%, 1996–2007 = 5%.
- Added model simulation readout plus CSV/JSON export for future training and calibration.
## New in v4.1 — Visible Data tab fix
- Fixed the v4.0 packaging issue where the Data engine code was present but the actual Data tab/panel was not inserted into the visible navigation.
- Data tab is now visible in the desktop left rail and the mobile quickbar.
## New in v4.2 — Power Classifier + Swing Power DNA
- Added Power Classifier based on 20-HR/30-HR/elite profile logic.
- Added Swing Power DNA inspired by bat-speed, impact force, rotational acceleration, launch path, and contact-efficiency research.
- Player cards now show DNA and Fade Risk chips.
- Intelligence Report now includes a Swing Power DNA card and Power Feature Importance table.
- Data tab exports new columns: powerClass, swingPowerScore, seasonPowerScore, batSpeedProxy, impactForceProxy, rotationalBurstProxy, launchPathScore, contactEfficiencyScore, powerTranslationScore, expectedPAScore, and fadeRiskScore.

## New in v4.3 — HR Probability + Edge Core
- Added a dedicated HR decision layer that computes a blended model HR probability (market model + season and recent per-PA rates, adjusted by pitcher, park/weather, Swing Power DNA, expected PA, and fade risk), its fair American odds, the sportsbook implied probability, and the resulting edge.
- Each HR play is labeled Strong Edge / Playable / Fair Price / Overpriced-Fade / Need Price, surfaced as chips on player cards and a full Edge Core panel in the Intelligence Report.
- Data tab feature store now exports HR probability, fair odds, book odds, market probability, edge %, and edge label columns; MLB.com standard stats are treated as the official fallback baseline.

## New in v4.4 — Persistent betslip launcher
- The betslip launcher (🧾 Slip · N) is now visible on every layout, not just mobile. Previously, hiding the slip on desktop left no way to reopen it except by adding another leg.
- The launcher is pinned bottom-right, shows the live leg count, opens/reopens the slip, and hides while the slip is open so the two never overlap. Mobile positioning (above the quickbar) is unchanged.
- Reuses the existing launcher wiring and leg-count label; no model or tracking behavior changed.
