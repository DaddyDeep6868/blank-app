import json
import os
import sys
import threading
import shutil
import subprocess
import re
import time
from datetime import datetime
from pathlib import Path

import requests
from flask import Flask, jsonify, request

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "server_data"
DATA_DIR.mkdir(exist_ok=True)
STATE_PATH = DATA_DIR / "dingerlab_server_state.json"
LOCK = threading.Lock()

app = Flask(__name__, static_folder=str(APP_DIR), static_url_path="")

ODDSBLAZE_DEFAULT_KEY = "14485da5-3b9e-4061-aea1-9d1ed356b253"
ODDSBLAZE_BOOKS = {"draftkings", "fanatics", "betmgm", "caesars"}

DEFAULT_STATE = {
    "savedParlays": [],
    "boardSnapshots": {},
    "modelExports": [],
    "updatedAt": None,
}


def now_ms():
    return int(time.time() * 1000)


def load_state():
    with LOCK:
        if not STATE_PATH.exists():
            return dict(DEFAULT_STATE)
        try:
            data = json.loads(STATE_PATH.read_text("utf-8"))
        except Exception:
            return dict(DEFAULT_STATE)
        out = dict(DEFAULT_STATE)
        out.update(data if isinstance(data, dict) else {})
        out.setdefault("savedParlays", [])
        out.setdefault("boardSnapshots", {})
        out.setdefault("modelExports", [])
        return out


def save_state(state):
    state["updatedAt"] = datetime.utcnow().isoformat() + "Z"
    tmp = STATE_PATH.with_suffix(".tmp")
    with LOCK:
        tmp.write_text(json.dumps(state, indent=2, sort_keys=True), "utf-8")
        tmp.replace(STATE_PATH)


def merge_by_id(old, new):
    old = old if isinstance(old, list) else []
    new = new if isinstance(new, list) else []
    by = {}
    for item in old + new:
        if not isinstance(item, dict):
            continue
        key = str(item.get("id") or item.get("savedAt") or json.dumps(item, sort_keys=True))
        if key in by:
            prev = by[key]
            # Prefer the object with the latest saved/graded/update timestamp.
            prev_t = max(int(prev.get("serverUpdatedAt") or 0), int(prev.get("savedAt") or 0), int(prev.get("gradedAt") or 0))
            item_t = max(int(item.get("serverUpdatedAt") or 0), int(item.get("savedAt") or 0), int(item.get("gradedAt") or 0))
            if item_t >= prev_t:
                by[key] = item
        else:
            by[key] = item
    return sorted(by.values(), key=lambda x: int(x.get("savedAt") or 0), reverse=True)


def merge_exports(old, new):
    old = old if isinstance(old, list) else []
    new = new if isinstance(new, list) else []
    by = {}
    for ex in old + new:
        if not isinstance(ex, dict):
            continue
        key = f"{ex.get('slateDate','')}::{ex.get('exportedAt','')}::{(ex.get('summary') or {}).get('totalHRs','')}"
        by[key] = ex
    return sorted(by.values(), key=lambda x: str(x.get("slateDate") or ""), reverse=True)[:200]


@app.get("/")
def index():
    html = (APP_DIR / "DingerLab.html").read_text("utf-8")
    inject = "<script>window.DL_SERVER_MODE=true;</script>"
    if "</head>" in html:
        html = html.replace("</head>", inject + "</head>", 1)
    else:
        html = inject + html
    return html


@app.get("/api/state")
def api_state():
    return jsonify(load_state())


@app.post("/api/state")
def api_state_post():
    incoming = request.get_json(silent=True) or {}
    state = load_state()
    if "savedParlays" in incoming:
        if incoming.get("replaceSavedParlays"):
            state["savedParlays"] = incoming.get("savedParlays") if isinstance(incoming.get("savedParlays"), list) else []
        else:
            state["savedParlays"] = merge_by_id(state.get("savedParlays"), incoming.get("savedParlays"))
    if "boardSnapshots" in incoming and isinstance(incoming.get("boardSnapshots"), dict):
        bs = state.get("boardSnapshots") or {}
        bs.update(incoming["boardSnapshots"])
        state["boardSnapshots"] = bs
    if "modelExports" in incoming:
        state["modelExports"] = merge_exports(state.get("modelExports"), incoming.get("modelExports"))
    save_state(state)
    return jsonify({"ok": True, "state": state})


@app.get("/api/oddsblaze")
def api_oddsblaze():
    sportsbook = (request.args.get("sportsbook") or "").strip().lower()
    league = (request.args.get("league") or "mlb").strip().lower()
    if sportsbook not in ODDSBLAZE_BOOKS:
        return jsonify({"error": "unsupported sportsbook"}), 400
    key = (os.environ.get("ODDSBLAZE_KEY") or ODDSBLAZE_DEFAULT_KEY).strip()
    try:
        data = jget(
            "https://odds.oddsblaze.com/",
            params={"key": key, "sportsbook": sportsbook, "league": league},
        )
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e), "sportsbook": sportsbook, "league": league}), 502


def jget(url, **kwargs):
    r = requests.get(url, timeout=30, headers={"user-agent": "DingerLab server sync"}, **kwargs)
    r.raise_for_status()
    return r.json()


def final_status_by_game(dates):
    status = {}
    for d in sorted(set(dates)):
        if not d:
            continue
        try:
            sch = jget("https://statsapi.mlb.com/api/v1/schedule", params={"sportId": 1, "date": d})
            for dd in sch.get("dates", []):
                for g in dd.get("games", []):
                    status[str(g.get("gamePk"))] = ((g.get("status") or {}).get("abstractGameState") or "")
        except Exception as e:
            print("schedule error", d, e)
    return status


def boxscore_stats(game_pk):
    bs = jget("https:" + "//statsapi.mlb.com/api/v1/game/" + str(game_pk) + "/boxscore")
    out = {}
    for side in ("home", "away"):
        players = (((bs.get("teams") or {}).get(side) or {}).get("players") or {})
        for _, prx in players.items():
            person = prx.get("person") or {}
            bat = ((prx.get("stats") or {}).get("batting") or {})
            pid = person.get("id")
            if pid is None or not bat:
                continue
            h = int(bat.get("hits") or 0)
            d2 = int(bat.get("doubles") or 0)
            t3 = int(bat.get("triples") or 0)
            hr = int(bat.get("homeRuns") or 0)
            out[str(pid)] = {
                "hr": hr,
                "h": h,
                "rbi": int(bat.get("rbi") or 0),
                "tb": h + d2 + 2 * t3 + 3 * hr,
                "pa": int(bat.get("plateAppearances") if bat.get("plateAppearances") is not None else (bat.get("atBats") or 0)),
            }
    return out


def live_feed_hr_ids(game_pk):
    # v1.1 feed/live is the reliable endpoint for full play data.
    data = jget("https:" + "//statsapi.mlb.com/api/v1.1/game/" + str(game_pk) + "/feed/live")
    ids = set()
    plays = (((data.get("liveData") or {}).get("plays") or {}).get("allPlays") or [])
    for play in plays:
        res = play.get("result") or {}
        if (res.get("eventType") or res.get("event")) != "home_run":
            continue
        batter = ((play.get("matchup") or {}).get("batter") or {})
        if batter.get("id") is not None:
            ids.add(str(batter.get("id")))
    return ids


def leg_hit(leg, stats, hr_ids):
    mk = leg.get("mk") or "hr"
    pid = str(leg.get("mlbId")) if leg.get("mlbId") is not None else None
    st = stats.get(pid) if pid else None
    if mk == "hr":
        if pid and pid in hr_ids:
            return True, "live_feed_hr"
        if st is not None:
            return (int(st.get("hr") or 0) >= 1), "boxscore"
        return None, None
    if st is None:
        return None, None
    if mk == "hits":
        return int(st.get("h") or 0) >= 1, "boxscore"
    if mk == "hits2":
        return int(st.get("h") or 0) >= 2, "boxscore"
    if mk == "tb":
        return int(st.get("tb") or 0) >= 2, "boxscore"
    if mk == "rbi":
        return int(st.get("rbi") or 0) >= 1, "boxscore"
    return None, None


def perform_grade():
    state = load_state()
    all_slips = state.get("savedParlays") or []
    pending = [x for x in all_slips if (x.get("result") or "pending") == "pending" and isinstance(x.get("legData"), list)]
    dates, pks = set(), set()
    for pp in pending:
        for l in pp.get("legData") or []:
            if l.get("date"):
                dates.add(str(l.get("date")))
            if l.get("gamePk"):
                pks.add(str(l.get("gamePk")))
    status = final_status_by_game(dates)
    boxes, hr_sets = {}, {}
    for pk in sorted(pks):
        if status.get(pk) != "Final":
            continue
        try:
            boxes[pk] = boxscore_stats(pk)
        except Exception as e:
            print("boxscore error", pk, e)
            boxes[pk] = {}
        try:
            hr_sets[pk] = live_feed_hr_ids(pk)
        except Exception as e:
            print("feed/live error", pk, e)
            hr_sets[pk] = set()
    graded_slips = 0
    graded_legs = 0
    waiting = 0
    for pp in pending:
        ready = True
        win = True
        for l in pp.get("legData") or []:
            pk = str(l.get("gamePk")) if l.get("gamePk") is not None else ""
            if l.get("hit") is None:
                if status.get(pk) != "Final":
                    ready = False
                    continue
                hit, source = leg_hit(l, boxes.get(pk) or {}, hr_sets.get(pk) or set())
                if hit is None:
                    ready = False
                    continue
                l["hit"] = bool(hit)
                l["gradedAt"] = now_ms()
                l["gradeSource"] = source
                graded_legs += 1
            if l.get("hit") is False:
                win = False
        if not ready:
            waiting += 1
            continue
        pp["result"] = "win" if win else "loss"
        pp["gradedAt"] = now_ms()
        pp["serverUpdatedAt"] = now_ms()
        graded_slips += 1
    if graded_slips or graded_legs:
        save_state(state)
    else:
        state["updatedAt"] = state.get("updatedAt")
    return {
        "ok": True,
        "gradedSlips": graded_slips,
        "gradedLegs": graded_legs,
        "waiting": waiting,
        "state": state,
    }


# ============================ Research Assistant connector (v4.9) ============================
def _extra_bin_dirs():
    home = str(Path.home())
    dirs = [
        os.path.join(home, ".local", "bin"),
        os.path.join(home, "bin"),
        os.path.join(home, ".local", "pipx", "venvs"),
        "/usr/local/bin",
        "/opt/homebrew/bin",
        os.path.join(home, "Library", "Python", "3.11", "bin"),
        os.path.join(home, "Library", "Python", "3.12", "bin"),
        os.path.join(home, "Library", "Python", "3.13", "bin"),
        os.path.join(home, "AppData", "Roaming", "Python", "Scripts"),
    ]
    return [d for d in dirs if os.path.isdir(d)]


def _augment_path():
    parts = (os.environ.get("PATH") or "").split(os.pathsep)
    changed = False
    for d in _extra_bin_dirs():
        if d not in parts:
            parts.append(d)
            changed = True
    if changed:
        os.environ["PATH"] = os.pathsep.join([p for p in parts if p])
    return os.environ.get("PATH", "")


def _tool_path(name):
    _augment_path()
    p = shutil.which(name)
    if p:
        return p
    # Direct probe of common bins, including pipx venv layout (~/.local/pipx/venvs/<pkg>/bin/<name>)
    exe_names = [name, name + ".exe", name + ".cmd"]
    for d in _extra_bin_dirs():
        for en in exe_names:
            cand = os.path.join(d, en)
            if os.path.isfile(cand) and os.access(cand, os.X_OK):
                return cand
        # pipx venvs/<pkg>/bin/<name>
        if d.endswith("venvs"):
            try:
                for pkg in os.listdir(d):
                    cand = os.path.join(d, pkg, "bin", name)
                    if os.path.isfile(cand) and os.access(cand, os.X_OK):
                        return cand
            except Exception:
                pass
    return None


def _run_cmd(cmd, timeout=25):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        out = (p.stdout or "") + (("\n" + p.stderr) if p.stderr else "")
        return {"ok": p.returncode == 0, "code": p.returncode, "output": out[:12000], "cmd": " ".join(cmd)}
    except Exception as e:
        return {"ok": False, "code": -1, "output": str(e), "cmd": " ".join(cmd)}


def _research_tools():
    return {
        "agent_reach": bool(_tool_path("agent-reach")),
        "twitter_cli": bool(_tool_path("twitter")),
        "opencli": bool(_tool_path("opencli")),
        "gh": bool(_tool_path("gh")),
        "yt_dlp": bool(_tool_path("yt-dlp")),
    }


@app.get("/api/research/status")
def api_research_status():
    tools = _research_tools()
    doctor = None
    if tools.get("agent_reach"):
        doctor = _run_cmd([_tool_path("agent-reach"), "doctor"], timeout=20)
    return jsonify({
        "ok": True,
        "tools": tools,
        "doctor": doctor,
        "note": "Twitter/X research should use your own local logged-in browser/cookie setup. DingerLab does not store cookies or secrets.",
    })


def _github_repo_from_url(url):
    m = re.search(r"github\.com/([^/]+)/([^/#?]+)", url or "")
    if not m:
        return None
    return m.group(1) + "/" + m.group(2).replace(".git", "")


@app.post("/api/research/search")
def api_research_search():
    body = request.get_json(silent=True) or {}
    query = (body.get("query") or "").strip()
    url = (body.get("url") or "").strip()
    source = (body.get("source") or "All").strip()
    if not query and not url:
        return jsonify({"ok": False, "error": "query or url required"}), 400
    tools = _research_tools()
    results = []
    mode = source

    # Twitter/X: intentionally uses local CLI/browser-login setup when available.
    if source in ("Twitter/X", "All"):
        if tools.get("twitter_cli"):
            cmd = [_tool_path("twitter"), "tweet", url] if url and ("x.com" in url or "twitter.com" in url) else [_tool_path("twitter"), "search", query or url]
            res = _run_cmd(cmd, timeout=30)
            results.append({"source": "Twitter/X via local twitter-cli", "title": "Twitter/X local scan", "url": url, "text": res.get("output", ""), "ok": res.get("ok"), "cmd": res.get("cmd")})
        elif tools.get("opencli"):
            cmd = [_tool_path("opencli"), "twitter", "search", query or url]
            res = _run_cmd(cmd, timeout=30)
            results.append({"source": "Twitter/X via OpenCLI", "title": "Twitter/X local scan", "url": url, "text": res.get("output", ""), "ok": res.get("ok"), "cmd": res.get("cmd")})
        elif source == "Twitter/X":
            return jsonify({"ok": False, "error": "Twitter/X connector is not configured. Install agent-reach/twitter-cli/OpenCLI locally and authenticate with your own Twitter login/cookies."}), 503

    if source in ("Reddit", "All"):
        if tools.get("opencli"):
            res = _run_cmd([_tool_path("opencli"), "reddit", "search", query or url], timeout=30)
            results.append({"source": "Reddit via OpenCLI", "title": "Reddit local scan", "url": url, "text": res.get("output", ""), "ok": res.get("ok"), "cmd": res.get("cmd")})
        elif source == "Reddit":
            return jsonify({"ok": False, "error": "Reddit connector is not configured. Agent-Reach notes Reddit needs browser login state/OpenCLI or cookies."}), 503

    if source in ("GitHub", "All"):
        if tools.get("gh"):
            repo = _github_repo_from_url(url)
            if repo:
                cmd = [_tool_path("gh"), "repo", "view", repo, "--json", "name,description,url,stargazerCount,issues"]
            else:
                cmd = [_tool_path("gh"), "search", "repos", query or url, "--limit", "8"]
            res = _run_cmd(cmd, timeout=30)
            results.append({"source": "GitHub via gh", "title": "GitHub scan", "url": url, "text": res.get("output", ""), "ok": res.get("ok"), "cmd": res.get("cmd")})
        elif source == "GitHub":
            return jsonify({"ok": False, "error": "GitHub CLI is not installed/configured."}), 503

    if source in ("YouTube", "All"):
        if tools.get("yt_dlp"):
            target = url if url else "ytsearch5:" + (query or "MLB props")
            res = _run_cmd([_tool_path("yt-dlp"), "--dump-json", "--skip-download", target], timeout=35)
            results.append({"source": "YouTube via yt-dlp", "title": "YouTube scan", "url": url, "text": res.get("output", ""), "ok": res.get("ok"), "cmd": res.get("cmd")})
        elif source == "YouTube":
            return jsonify({"ok": False, "error": "yt-dlp is not installed/configured."}), 503

    if source in ("Web", "All") and url:
        try:
            r = requests.get(url, timeout=18, headers={"user-agent": "DingerLab research assistant"})
            results.append({"source": "Web", "title": url, "url": url, "text": r.text[:6000], "ok": r.ok})
        except Exception as e:
            results.append({"source": "Web", "title": url, "url": url, "text": str(e), "ok": False})

    if not results:
        return jsonify({"ok": False, "error": "No configured connector found for this source. Manual research log is still available."}), 503
    return jsonify({"ok": True, "mode": mode, "tools": tools, "results": results})


# ===================== Automated Twitter/X login setup (v4.11) =====================
# All of this runs on the LOCAL machine hosting DingerLab. Cookies/login stay local.
# No credentials are hardcoded and nothing is sent off-box by these endpoints.

def _tw_config_dir():
    base = os.environ.get("DINGERLAB_RESEARCH_HOME") or os.path.join(str(Path.home()), ".dingerlab", "research")
    try:
        os.makedirs(base, exist_ok=True)
    except Exception:
        pass
    return base


def _in_virtualenv():
    """True if running inside a virtualenv/venv (where --user installs fail)."""
    try:
        if os.environ.get("VIRTUAL_ENV"):
            return True
        base = getattr(sys, "base_prefix", None) or getattr(sys, "real_prefix", None)
        return bool(base) and base != sys.prefix
    except Exception:
        return False


def _is_server_host():
    """Best-effort detection of a remote/headless host (Render, Heroku, containers, no display)."""
    try:
        if any(os.environ.get(k) for k in ("RENDER", "RENDER_SERVICE_ID", "DYNO", "KUBERNETES_SERVICE_HOST", "AWS_EXECUTION_ENV", "FLY_APP_NAME")):
            return True
        exe = sys.executable or ""
        if "/opt/render/" in exe or exe.startswith("/app/"):
            return True
        if sys.platform.startswith("linux") and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
            return True
    except Exception:
        pass
    return False


def _pip_cmds(pkg):
    """Return ordered install command candidates for a package.
    Inside a virtualenv a '--user' install is impossible, so we skip it to avoid
    a noisy, guaranteed failure."""
    cmds = []
    pipx = shutil.which("pipx")
    if pipx:
        cmds.append([pipx, "install", pkg])
        cmds.append([pipx, "install", "--force", pkg])
    py = sys.executable or shutil.which("python3") or shutil.which("python") or "python3"
    if not _in_virtualenv():
        cmds.append([py, "-m", "pip", "install", "--user", pkg])
    cmds.append([py, "-m", "pip", "install", pkg])
    return cmds


@app.post("/api/research/twitter/install")
def api_tw_install():
    logs = []
    def log(line):
        logs.append(line)

    log("python: " + (sys.executable or "?"))
    log("environment: " + ("remote/server host" if _is_server_host() else "local machine") + (" (virtualenv)" if _in_virtualenv() else ""))
    log("PATH bins detected: " + (", ".join(_extra_bin_dirs()) or "(none of the usual user bins exist yet)"))

    # Step A: install agent-reach (the umbrella tool).
    if not _tool_path("agent-reach"):
        for cmd in _pip_cmds("agent-reach"):
            res = _run_cmd(cmd, timeout=300)
            log("$ " + res.get("cmd", "") + "\n" + (res.get("output") or ""))
            if _tool_path("agent-reach"):
                break

    # Step B: prefer agent-reach's own installer to set up the sub-CLIs (twitter-cli, etc.).
    ar = _tool_path("agent-reach")
    if ar and not _tool_path("twitter"):
        for sub in ([ar, "install"], [ar, "install", "twitter"], [ar, "setup"]):
            res = _run_cmd(sub, timeout=300)
            log("$ " + res.get("cmd", "") + "\n" + (res.get("output") or ""))
            if _tool_path("twitter"):
                break

    # Step C: direct install of the twitter CLI, trying known package names.
    if not _tool_path("twitter"):
        for pkg in ("twitter-cli", "twitter-api-client", "twscrape", "tweety-ns"):
            installed = False
            for cmd in _pip_cmds(pkg):
                res = _run_cmd(cmd, timeout=300)
                log("$ " + res.get("cmd", "") + "\n" + (res.get("output") or ""))
                if _tool_path("twitter"):
                    installed = True
                    break
            if installed:
                break

    tools = _research_tools()
    tw = _tool_path("twitter")
    server = _is_server_host()
    if tw:
        log("\nOK: twitter CLI is installed and detected at " + tw + ".")
        log("This is the only tool DingerLab needs to read MLB prop tweets. The 'agent-reach' umbrella package is OPTIONAL (it is just an installer/orchestrator) and is NOT required \u2014 you can safely ignore any agent-reach install errors above.")
        if server:
            log("\nThis is a remote/server host (no browser here). Next step: click 'Paste cookies instead' and paste your own x.com cookies exported with the Cookie-Editor browser extension, then click Verify. 'Import login from this browser' only works on a local computer.")
        else:
            log("\nNext: connect your own Twitter/X login (Import login from this browser, or Paste cookies), then click Verify.")
    else:
        log("\nNOTE: the 'twitter' command was still not found on PATH. If pip reported a successful install, the executable is likely in a bin that is not on this host's PATH. Restart dingerlab_server.py from a fresh shell, or run 'pipx install twitter-cli' manually, then click Run diagnostics.")
    return jsonify({"ok": True, "tools": tools, "twitterPath": tw, "agentReachPath": _tool_path("agent-reach"), "serverHost": server, "twitterReady": bool(tw), "output": "\n\n".join(logs)})


@app.post("/api/research/twitter/doctor")
def api_tw_doctor():
    ar = _tool_path("agent-reach")
    out = ""
    if ar:
        out = (_run_cmd([ar, "doctor"], timeout=40).get("output") or "")
    else:
        tw = _tool_path("twitter")
        if tw:
            out = "agent-reach (optional umbrella tool) is not installed \u2014 that's fine. The twitter CLI is installed at " + tw + ", which is all DingerLab needs. Connect your login (paste cookies on a server host) and click Verify."
        else:
            out = "Neither agent-reach nor the twitter CLI is installed yet. Run step 1 (Install connector) first."
    return jsonify({"ok": True, "tools": _research_tools(), "output": out})


@app.post("/api/research/twitter/login")
def api_tw_login():
    tw = _tool_path("twitter")
    ar = _tool_path("agent-reach")
    if not (tw or ar):
        return jsonify({"ok": False, "error": "No Twitter connector installed. Run step 1 first."}), 503
    # Try to launch the local interactive browser-login flow. This only works on a
    # machine with a real browser/display; in headless hosting it will report back
    # so the user can use the cookie-paste path instead.
    cmd = [tw, "login"] if tw else [ar, "twitter", "login"]
    res = _run_cmd(cmd, timeout=90)
    note = "If no browser opened, this host is headless — use 'Paste cookies instead' with cookies exported from your own logged-in browser."
    return jsonify({"ok": True, "output": (res.get("output") or "") + "\n\n" + note, "note": note})


@app.post("/api/research/twitter/cookies")
def api_tw_cookies():
    body = request.get_json(silent=True) or {}
    cookies = (body.get("cookies") or "").strip()
    if not cookies:
        return jsonify({"ok": False, "error": "No cookies provided"}), 400
    cfg = _tw_config_dir()
    is_json = cookies.lstrip().startswith("{") or cookies.lstrip().startswith("[")
    fname = "twitter_cookies.json" if is_json else "twitter_cookies.txt"
    path = os.path.join(cfg, fname)
    try:
        with open(path, "w") as f:
            f.write(cookies)
        try:
            os.chmod(path, 0o600)
        except Exception:
            pass
    except Exception as e:
        return jsonify({"ok": False, "error": "Could not write cookie file: " + str(e)}), 500
    # Point common connectors at the cookie file via env for this process where supported.
    os.environ["TWITTER_COOKIES"] = path
    os.environ["AGENT_REACH_TWITTER_COOKIES"] = path
    return jsonify({"ok": True, "path": path, "format": ("json" if is_json else "netscape"), "output": "Saved your Twitter/X login cookies locally (permissions 600). They never leave this machine."})


@app.post("/api/research/twitter/verify")
def api_tw_verify():
    tw = _tool_path("twitter")
    if not tw:
        ar = _tool_path("agent-reach")
        msg = "The 'twitter' command is not on this server's PATH yet."
        if ar:
            msg += " agent-reach IS installed (" + ar + "), so run 'agent-reach install' in your terminal to add the Twitter CLI, then restart dingerlab_server.py."
        else:
            msg += " Run step 1 (Install connector) first, or install manually: pipx install agent-reach && agent-reach install."
        return jsonify({"ok": True, "authenticated": False, "serverHost": _is_server_host(), "output": msg})
    res = _run_cmd([tw, "search", "MLB home run", "--limit", "1"], timeout=45)
    out = res.get("output") or ""
    low = out.lower()
    authed = res.get("ok") and not any(k in low for k in ("please log in", "please login", "not logged in", "login required", "authentication required", "unauthorized", "401", "403", "no cookies", "missing cookie", "cookies not found"))
    return jsonify({"ok": True, "authenticated": bool(authed), "serverHost": _is_server_host(), "output": out})


@app.post("/api/research/twitter/import_browser")
def api_tw_import_browser():
    body = request.get_json(silent=True) or {}
    which = (body.get("browser") or "auto").lower()
    try:
        import browser_cookie3  # type: ignore
    except Exception:
        _run_cmd([shutil.which("pip") or "pip", "install", "--user", "browser_cookie3"], timeout=180)
        try:
            import browser_cookie3  # type: ignore
        except Exception as e:
            return jsonify({"ok": False, "error": "Could not load browser_cookie3 to read your local browser session: " + str(e)}), 503

    loaders = {
        "chrome": getattr(browser_cookie3, "chrome", None),
        "edge": getattr(browser_cookie3, "edge", None),
        "brave": getattr(browser_cookie3, "brave", None),
        "firefox": getattr(browser_cookie3, "firefox", None),
        "safari": getattr(browser_cookie3, "safari", None),
        "opera": getattr(browser_cookie3, "opera", None),
    }
    order = [which] if which in loaders else ["chrome", "edge", "brave", "safari", "firefox", "opera"]

    jar = None
    used = None
    errs = []
    for name in order:
        fn = loaders.get(name)
        if not fn:
            continue
        try:
            jar = fn(domain_name="x.com")
            used = name
            if jar and len(list(jar)) == 0:
                jar = fn(domain_name="twitter.com")
            break
        except Exception as e:
            errs.append(name + ": " + str(e))
            continue
    if jar is None:
        return jsonify({"ok": False, "error": "No readable browser session found on this machine. " + "; ".join(errs[:4])}), 503

    cookies = [c for c in jar if ("x.com" in (c.domain or "") or "twitter.com" in (c.domain or ""))]
    if not cookies:
        return jsonify({"ok": False, "error": "You are logged into Twitter/X in your browser, but no x.com cookies were readable from this machine. Make sure DingerLab runs on the same computer/profile, or use Paste cookies instead."}), 404

    cfg = _tw_config_dir()
    # Netscape cookies.txt
    txt_path = os.path.join(cfg, "twitter_cookies.txt")
    lines = ["# Netscape HTTP Cookie File", "# Imported by DingerLab from your local browser (" + (used or "?") + ")"]
    json_obj = []
    for c in cookies:
        domain = c.domain or ".x.com"
        flag = "TRUE" if domain.startswith(".") else "FALSE"
        secure = "TRUE" if getattr(c, "secure", False) else "FALSE"
        expires = str(int(c.expires)) if getattr(c, "expires", None) else "0"
        lines.append("\t".join([domain, flag, c.path or "/", secure, expires, c.name, c.value or ""]))
        json_obj.append({"name": c.name, "value": c.value, "domain": domain, "path": c.path or "/", "secure": bool(getattr(c, "secure", False)), "expires": (int(c.expires) if getattr(c, "expires", None) else None)})
    try:
        with open(txt_path, "w") as f:
            f.write("\n".join(lines) + "\n")
        os.chmod(txt_path, 0o600)
        json_path = os.path.join(cfg, "twitter_cookies.json")
        with open(json_path, "w") as f:
            json.dump(json_obj, f)
        os.chmod(json_path, 0o600)
    except Exception as e:
        return jsonify({"ok": False, "error": "Read your session but could not save it locally: " + str(e)}), 500
    os.environ["TWITTER_COOKIES"] = txt_path
    os.environ["AGENT_REACH_TWITTER_COOKIES"] = txt_path
    return jsonify({"ok": True, "browser": used, "count": len(cookies), "path": txt_path, "output": "Imported " + str(len(cookies)) + " x.com cookies from your " + (used or "browser") + " session and saved them locally (permissions 600). Click Verify."})


@app.post("/api/grade")
def api_grade():
    return jsonify(perform_grade())


@app.get("/health")
def health():
    return {"ok": True, "statePath": str(STATE_PATH)}


def background_grade_loop():
    # Server-side auto-settlement: every 10 minutes, check final MLB games,
    # verify HR legs from feed/live, and sync pending bet outcomes.
    while True:
        try:
            res = perform_grade()
            if res.get("gradedSlips") or res.get("gradedLegs"):
                print("auto-grade", res.get("gradedSlips"), "slips", res.get("gradedLegs"), "legs")
        except Exception as e:
            print("auto-grade loop error", e)
        time.sleep(10 * 60)


def start_background_worker():
    if os.environ.get("DINGERLAB_DISABLE_BACKGROUND") == "1":
        return
    if getattr(start_background_worker, "started", False):
        return
    start_background_worker.started = True
    t = threading.Thread(target=background_grade_loop, daemon=True)
    t.start()


start_background_worker()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8501"))
    app.run(host="0.0.0.0", port=port, debug=False)
