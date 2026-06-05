import json

import requests
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="DingerLab", page_icon="\u26be", layout="wide")

BOOKS = ["draftkings", "fanatics", "betmgm", "caesars"]

# Prefer the key from Streamlit secrets (Settings -> Secrets) so it never lives in your repo.
try:
    DEFAULT_KEY = st.secrets["ODDSBLAZE_KEY"]
except Exception:
    DEFAULT_KEY = "1a569ce7-9274-4f4a-8279-ef68913e8ef8"


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


with st.sidebar:
    st.title("\u26be DingerLab")
    st.caption("Cross-game HR parlay lab")
    key = st.text_input("OddsBlaze API key", value=DEFAULT_KEY, type="password")
    league = st.selectbox("League", ["mlb"], index=0)
    fetch = st.button("\U0001F504 Fetch live odds", use_container_width=True)
    st.caption(
        "Odds are fetched server-side and injected into the app, so the in-app "
        "**Load odds** button works without a local proxy."
    )

if "raw_odds" not in st.session_state:
    st.session_state.raw_odds = {}

if fetch:
    raw = {}
    bar = st.sidebar.progress(0.0, text="Fetching odds\u2026")
    for i, b in enumerate(BOOKS):
        try:
            raw[b] = fetch_book(key, b, league)
        except Exception as e:  # noqa: BLE001
            st.sidebar.warning(f"{b}: {e}")
        bar.progress((i + 1) / len(BOOKS), text=f"Fetched {b}")
    bar.empty()
    st.session_state.raw_odds = raw
    n = len([1 for v in raw.values() if v])
    st.sidebar.success(
        f"Loaded {n}/{len(BOOKS)} books. Now click **Load odds** inside the app."
    )

html = load_html()
payload = json.dumps(st.session_state.raw_odds).replace("</", "<\\/")
inject = "<script>window.DL_RAW_ODDS = " + payload + ";</script>"
if "</head>" in html:
    html = html.replace("</head>", inject + "</head>", 1)
else:
    html = inject + html

components.html(html, height=1600, scrolling=True)
