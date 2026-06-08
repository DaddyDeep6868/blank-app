import base64
import json

import requests
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="DingerLab", page_icon="⚾", layout="wide")

APP_PASSWORD = "adi11"
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
        f"""
        <style>
        [data-testid="stSidebar"], [data-testid="stSidebarNav"] 
            display: none !important;
        
        .stApp {{
            background: linear-gradient(rgba(0,0,0,.48), rgba(0,0,0,.62)),
                        url("data:image/png;base64,{WALLPAPER}") center/cover fixed no-repeat;
        }}
        .block-container 
            max-width: 520px;
            padding-top: 12vh;
        
        div[data-testid="stForm"] 
            background: rgba(20,22,24,.86);
            border: 1px solid rgba(255,255,255,.22);
            border-radius: 20px;
            padding: 30px 30px 24px;
            box-shadow: 0 22px 70px rgba(0,0,0,.45);
            backdrop-filter: blur(10px);
        
        div[data-testid="stForm"] h1,
        div[data-testid="stForm"] p,
        div[data-testid="stForm"] label 
            color: #f5f5f5 !important;
        
        div[data-testid="stForm"] [data-testid="stCaptionContainer"] 
            color: rgba(255,255,255,.72) !important;
        
        </style>
        """,
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


if not st.session_state.get("dl_unlocked"):
    show_login()

with st.sidebar:
    st.title("⚾ DingerLab")
    st.caption("Cross-game HR parlay lab")
    if st.button("Lock app", use_container_width=True):
        st.session_state["dl_unlocked"] = False
        st.rerun()
    key = st.text_input("OddsBlaze API key", value=DEFAULT_KEY, type="password")
    league = st.selectbox("League", ["mlb"], index=0)

# Odds are auto-fetched server-side (cached) and injected into the app, so a
# single in-app button ("Load slate + all-market odds") does everything.
raw = {}
for b in BOOKS:
    try:
        raw[b] = fetch_book(key, b, league)
    except Exception as e:  # noqa: BLE001
        st.sidebar.warning(f"{b}: {e}")
n = len([1 for v in raw.values() if v])
st.sidebar.caption(
    f"Live odds ready: {n}/{len(BOOKS)} books. Click **Load slate + all-market odds** in the app."
)

html = load_html()
payload = json.dumps(raw).replace("</", "<\\/")
inject = (
    "<script>"
    "sessionStorage.setItem('dingerlab_unlocked_v1','1');"
    "window.DL_RAW_ODDS = " + payload + ";"
    "</script>"
)
if "</head>" in html:
    html = html.replace("</head>", inject + "</head>", 1)
else:
    html = inject + html

components.html(html, height=1600, scrolling=True)
