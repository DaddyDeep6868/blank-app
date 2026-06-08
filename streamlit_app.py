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
