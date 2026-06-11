import base64
import csv as _csv
import io as _io
import json
from datetime import date

import requests
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="DingerLab", page_icon="⚾", layout="wide")

BOOKS = ["draftkings", "fanatics", "betmgm", "caesars"]


def asset_b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


WALLPAPER = asset_b64("login_wallpaper.png")

# Prefer the key from Streamlit secrets (Settings -> Secrets) so it never lives in your repo.
try:
    DEFAULT_KEY = st.secrets["ODDSBLAZE_KEY"]
except Exception:
    DEFAULT_KEY = "14485da5-3b9e-4061-aea1-9d1ed356b253"


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def fetch_matchup_data(year):
    """Pitch-type matchup data from Baseball Savant (public CSV leaderboards).

    Pitchers: usage%% per pitch type. Batters: ISO + PA per pitch type.
    Cached 6h - this is season-level data, not live odds.
    """
    base = "https://baseballsavant.mlb.com/leaderboard/pitch-arsenal-stats"
    headers = {"accept": "text/csv", "user-agent": "Mozilla/5.0 (DingerLab)"}

    def grab(kind):
        r = requests.get(
            base,
            params={"type": kind, "pitchType": "", "year": str(year),
                    "position": "", "team": "", "min": "5", "csv": "true"},
            headers=headers, timeout=45,
        )
        r.raise_for_status()
        return list(_csv.DictReader(_io.StringIO(r.text)))

    def fnum(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    pitchers = {}
    for row in grab("pitcher"):
        pid, pt = row.get("player_id"), row.get("pitch_type")
        if not pid or not pt:
            continue
        u = fnum(row.get("pitch_usage"))
        if u is None:
            continue
        pitchers.setdefault(str(pid).strip(), {})[pt.strip()] = {"u": round(u, 1)}

    batters = {}
    for row in grab("batter"):
        pid, pt = row.get("player_id"), row.get("pitch_type")
        if not pid or not pt:
            continue
        slg, ba, pa = fnum(row.get("slg")), fnum(row.get("ba")), fnum(row.get("pa"))
        if slg is None or ba is None or not pa:
            continue
        batters.setdefault(str(pid).strip(), {})[pt.strip()] = {
            "iso": round(max(0.0, slg - ba), 3), "pa": int(pa)}

    if not pitchers or not batters:
        raise RuntimeError("Savant returned no usable rows (CSV format may have changed)")
    return {"pitchers": pitchers, "batters": batters, "year": year}


@st.cache_data(ttl=20, show_spinner=False)
def fetch_book(key, book, league):
    r = requests.get(
        "https://odds.oddsblaze.com/",
        params={"key": key, "sportsbook": book, "league": league},
        headers={"accept": "application/json"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def load_html():
    with open("DingerLab.html", "r", encoding="utf-8") as f:
        return f.read()


def show_login():
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"], [data-testid="stSidebarNav"] {
            display: none !important;
        }
        .stApp {
            background-image:
                linear-gradient(rgba(0,0,0,.18), rgba(0,0,0,.42)),
                url("data:image/png;base64,__WALLPAPER__");
            background-position: center center;
            background-size: cover;
            background-repeat: no-repeat;
            background-attachment: fixed;
        }
        .stApp::before {
            content: "";
            position: fixed;
            inset: 0;
            pointer-events: none;
            background:
                radial-gradient(circle at 28% 18%, rgba(255,69,199,.18), transparent 30%),
                radial-gradient(circle at 70% 76%, rgba(56,189,248,.16), transparent 32%);
            z-index: 0;
        }
        .block-container {
            max-width: 520px;
            padding-top: 14vh;
            position: relative;
            z-index: 1;
        }
        div[data-testid="stForm"] {
            background: rgba(5, 8, 14, .58);
            border: 1px solid rgba(255,255,255,.25);
            border-radius: 22px;
            padding: 30px 30px 24px;
            box-shadow: 0 24px 80px rgba(0,0,0,.52);
            backdrop-filter: blur(12px);
            animation: loginCardIn .22s ease-out both;
        }
        div[data-testid="stForm"]:has(button:active) {
            animation: loginCardOut .16s ease-out forwards;
        }
        div[data-testid="stForm"] h1,
        div[data-testid="stForm"] p,
        div[data-testid="stForm"] label {
            color: #f8fafc !important;
        }
        div[data-testid="stForm"] [data-testid="stCaptionContainer"] {
            color: rgba(248,250,252,.80) !important;
        }
        div[data-testid="stTextInput"] input {
            background: rgba(255,255,255,.13) !important;
            color: #fff !important;
            border-color: rgba(255,255,255,.35) !important;
        }
        div[data-testid="stFormSubmitButton"] button {
            transition: transform .12s ease, filter .12s ease, opacity .12s ease;
        }
        div[data-testid="stFormSubmitButton"] button:active {
            transform: scale(.985);
            filter: brightness(1.2);
        }
        @keyframes loginCardIn {
            from { opacity: 0; transform: translateY(10px) scale(.985); }
            to { opacity: 1; transform: translateY(0) scale(1); }
        }
        @keyframes loginCardOut {
            to { opacity: 0; transform: translateY(-8px) scale(.985); filter: blur(6px); }
        }
        </style>
        """.replace("__WALLPAPER__", WALLPAPER),
        unsafe_allow_html=True,
    )
    with st.form("login_form", clear_on_submit=False):
        st.markdown("# ⚾ DingerLab")
        st.caption("Enter the password to unlock the app, API key panel, and live odds tools.")
        pw = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Unlock", use_container_width=True)
        if submitted:
            if pw == APP_PASSWORD:
                st.session_state["dl_unlocked"] = True
                st.rerun()
            else:
                st.error("Wrong password. Try again.")
    st.stop()


# Password screen disabled in v1.46.
st.session_state["dl_unlocked"] = True

with st.sidebar:
    st.title("⚾ DingerLab")
    st.caption("Cross-game HR parlay lab")
    key = st.text_input("OddsBlaze API key", value=DEFAULT_KEY, type="password")
    league = st.selectbox("League", ["mlb"], index=0)
    force_fetch = st.button("Refresh live odds", use_container_width=True)

raw = {}
for b in BOOKS:
    try:
        raw[b] = fetch_book(key, b, league)
    except Exception as e:  # noqa: BLE001
        st.sidebar.warning(f"{b}: {e}")

n = len([1 for v in raw.values() if v])
if force_fetch:
    st.sidebar.caption(
        f"Live odds refreshed: {n}/{len(BOOKS)} books. Click **Load slate + all-market odds** in the app."
    )
else:
    st.sidebar.caption(
        f"Live odds ready: {n}/{len(BOOKS)} books. Click **Load slate + all-market odds** in the app."
    )

MATCHUP = None
try:
    MATCHUP = fetch_matchup_data(date.today().year)
    st.sidebar.caption(
        f"\U0001F9EC Matchup DNA: {len(MATCHUP['pitchers'])} pitcher arsenals \u00b7 "
        f"{len(MATCHUP['batters'])} batter profiles ({MATCHUP['year']})."
    )
except Exception as e:  # noqa: BLE001
    st.sidebar.warning(f"Matchup DNA unavailable: {e}")

st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    .stApp {
        background:
            radial-gradient(circle at 18% 14%, rgba(56,189,248,.08), transparent 35%),
            radial-gradient(circle at 72% 78%, rgba(255,69,199,.07), transparent 38%),
            linear-gradient(180deg, #070b12 0%, #0b1220 55%, #070b12 100%);
    }

    .block-container { padding-top: 1.25rem; }

    section[data-testid="stSidebar"] {
        background: rgba(5, 8, 14, .72);
        border-right: 1px solid rgba(255,255,255,.08);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

html = load_html()
payload = json.dumps(raw).replace("</", "<\\/")
matchup_payload = (json.dumps(MATCHUP).replace("</", "<\\/") if MATCHUP else "null")
inject = (
    "<script>"
    "sessionStorage.setItem('dingerlab_unlocked_v1','1');"
    "window.DL_RAW_ODDS = " + payload + ";"
    "window.DL_MATCHUP = " + matchup_payload + ";"
    "</script>"
)
if "</head>" in html:
    html = html.replace("</head>", inject + "</head>", 1)
else:
    html = inject + html

components.html(html, height=1600, scrolling=True)
