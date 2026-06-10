import json
import os
import threading
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
