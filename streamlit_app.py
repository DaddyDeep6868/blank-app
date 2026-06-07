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
    DEFAULT_KEY = "14485da5-3b9e-4061-aea1-9d1ed356b253"


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

# Odds are auto-fetched server-side (cached) and injected into the app, so a
# single in-app button ("Load slate + HR odds") does everything.
raw = {}
for b in BOOKS:
    try:
        raw[b] = fetch_book(key, b, league)
    except Exception as e:  # noqa: BLE001
        st.sidebar.warning(f"{b}: {e}")
n = len([1 for v in raw.values() if v])
st.sidebar.caption(
    f"Live odds ready: {n}/{len(BOOKS)} books. Click **Load slate + HR odds** in the app."
)

html = load_html()
payload = json.dumps(raw).replace("</", "<\\/")
inject = "<script>window.DL_RAW_ODDS = " + payload + ";</script>"
if "</head>" in html:
    html = html.replace("</head>", inject + "</head>", 1)
else:
    html = inject + html

components.html(html, height=1600, scrolling=True)
