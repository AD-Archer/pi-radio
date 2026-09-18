"""Shared helpers for radio-playlist-sync.py and radio-webapp.py.

Deployed to /usr/local/bin alongside the scripts that import it (both add
that directory to sys.path before importing) - not a real installed package,
just a shared module for two small personal scripts.
"""
import configparser
import contextlib
import datetime
import fcntl
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
import uuid

sys.path.insert(0, f"/usr/local/lib/python3.{sys.version_info.minor}/dist-packages")
from mopidy_subsonic.client import SubsonicRemoteClient  # noqa: E402

# Fallback used only if random default selection has nothing to pick from
# (e.g. every playlist has been excluded, or Navidrome has none at all).
FALLBACK_PLAYLIST_ID = os.environ.get("RADIO_PLAYLIST_ID", "1OfGteB2iY40tKxcmugen9")
BLUETOOTH_MAC = os.environ.get("RADIO_BLUETOOTH_MAC", "41:42:BD:42:27:E5")  # FM02
MOPIDY_RPC = "http://localhost:6680/mopidy/rpc"
MOPIDY_CONF = "/etc/mopidy/mopidy.conf"
STATE_DIR = "/var/lib/mopidy"
OVERRIDE_STATE_FILE = f"{STATE_DIR}/.radio-override.json"
SCHEDULE_FILE = f"{STATE_DIR}/.radio-schedules.json"
SCHEDULE_STATE_FILE = f"{STATE_DIR}/.radio-schedule-state.json"
DEFAULT_STATE_FILE = f"{STATE_DIR}/.radio-default-state.json"
EXCLUSIONS_FILE = f"{STATE_DIR}/.radio-exclusions.json"
LOCK_FILE = f"{STATE_DIR}/.radio.lock"


class RpcError(RuntimeError):
    pass


@contextlib.contextmanager
def radio_lock():
    """Serializes tracklist-mutating operations between the webapp and the
    sync timer (and between overlapping webapp requests), so two callers
    can never interleave a clear()/add()/play() sequence."""
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(LOCK_FILE, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def rpc(method, params=None, timeout=10):
    payload = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        payload["params"] = params
    req = urllib.request.Request(
        MOPIDY_RPC,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.load(resp)
    except urllib.error.URLError as e:
        raise RpcError(f"Could not reach Mopidy at {MOPIDY_RPC}: {e}") from e
    if "error" in body:
        raise RpcError(f"Mopidy RPC error calling {method}: {body['error']}")
    return body.get("result")


def get_subsonic_client():
    cfg = configparser.ConfigParser()
    if not cfg.read(MOPIDY_CONF):
        raise RuntimeError(f"Could not read {MOPIDY_CONF} (permissions? must run as root)")
    s = cfg["subsonic"]
    return SubsonicRemoteClient(
        s["hostname"],
        s["port"],
        s["username"],
        s["password"],
        s.getboolean("ssl"),
        s.get("context", ""),
    )


def playlist_track_uris(client, playlist_id):
    data = client.api.getPlaylist(pid=playlist_id)
    entries = data.get("playlist", {}).get("entry", [])
    if isinstance(entries, dict):
        entries = [entries]
    return [f"subsonic://{e['id']}" for e in entries]


def play_playlist_now(playlist_id):
    """Clear the queue, load only this playlist's tracks, loop, and play.
    Caller is responsible for holding radio_lock() around this."""
    client = get_subsonic_client()
    uris = playlist_track_uris(client, playlist_id)
    rpc("core.tracklist.clear")
    if uris:
        rpc("core.tracklist.add", {"uris": uris})
    rpc("core.tracklist.set_repeat", {"value": True})
    rpc("core.tracklist.set_consume", {"value": False})
    if uris:
        rpc("core.playback.play")
    return len(uris)


def _atomic_write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, path)  # atomic on POSIX - readers never see a partial file


def _read_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


# --- One-off "play X for N minutes" override --------------------------------

def read_raw_override():
    """Returns the override record regardless of expiry, or None if there
    isn't one at all. Use load_override() unless you specifically need to
    tell "never set" apart from "set but expired"."""
    return _read_json(OVERRIDE_STATE_FILE, None)


def load_override():
    state = read_raw_override()
    if state is None:
        return None
    if state.get("expires_at") is not None and time.time() >= state["expires_at"]:
        return None
    return state


def save_override(playlist_id, name, minutes):
    expires_at = time.time() + minutes * 60 if minutes else None
    state = {"playlist_id": playlist_id, "name": name, "expires_at": expires_at}
    _atomic_write_json(OVERRIDE_STATE_FILE, state)
    return state


def clear_override():
    try:
        os.remove(OVERRIDE_STATE_FILE)
    except FileNotFoundError:
        pass


# --- Recurring daily schedule -------------------------------------------------

def load_schedules():
    return _read_json(SCHEDULE_FILE, [])


def save_schedules(schedules):
    _atomic_write_json(SCHEDULE_FILE, schedules)


def add_schedule(playlist_id, name, time_str):
    """time_str is 'HH:MM', 24-hour, local time."""
    hh, mm = time_str.split(":")
    if not (0 <= int(hh) <= 23 and 0 <= int(mm) <= 59):
        raise ValueError(f"invalid time {time_str!r}")
    schedules = load_schedules()
    entry = {"id": uuid.uuid4().hex[:8], "playlist_id": playlist_id, "name": name, "time": time_str}
    schedules.append(entry)
    save_schedules(schedules)
    return entry


def remove_schedule(schedule_id):
    schedules = load_schedules()
    schedules = [s for s in schedules if s["id"] != schedule_id]
    save_schedules(schedules)


def resolve_active_schedule(schedules, now=None):
    """Of today's enabled schedules, returns whichever one's time-of-day is
    the most recent one at-or-before now - i.e. "what should be playing
    right now" on a simple 24-hour daily programming grid. Returns None if
    none have started yet today (or there are no schedules)."""
    now = now or datetime.datetime.now()
    current_minutes = now.hour * 60 + now.minute
    timed = []
    for s in schedules:
        hh, mm = s["time"].split(":")
        timed.append((int(hh) * 60 + int(mm), s))
    timed.sort(key=lambda pair: pair[0])
    active = None
    for minutes, s in timed:
        if minutes <= current_minutes:
            active = s
        else:
            break
    return active


def load_schedule_state():
    return _read_json(SCHEDULE_STATE_FILE, None)


def save_schedule_state(active_schedule_id):
    _atomic_write_json(SCHEDULE_STATE_FILE, {"active_schedule_id": active_schedule_id})


# --- Random default playlist rotation ----------------------------------------

def get_all_playlists(client):
    data = client.api.getPlaylists()
    entries = data.get("playlists", {}).get("playlist", [])
    if isinstance(entries, dict):
        entries = [entries]
    return entries


def load_exclusions():
    """List of Navidrome playlist IDs excluded from random default rotation."""
    return _read_json(EXCLUSIONS_FILE, [])


def set_exclusion(playlist_id, excluded):
    ids = set(load_exclusions())
    if excluded:
        ids.add(playlist_id)
    else:
        ids.discard(playlist_id)
    _atomic_write_json(EXCLUSIONS_FILE, sorted(ids))


def pick_random_playlist(client):
    """Random eligible playlist (excluded ones and empty ones don't count),
    or None if nothing qualifies."""
    excluded = set(load_exclusions())
    candidates = [
        p for p in get_all_playlists(client)
        if p["id"] not in excluded and p.get("songCount", 0) > 0
    ]
    if not candidates:
        return None
    chosen = random.choice(candidates)
    return {"id": chosen["id"], "name": chosen["name"]}


def load_default_state():
    return _read_json(DEFAULT_STATE_FILE, None)


def save_default_state(playlist_id, name):
    _atomic_write_json(DEFAULT_STATE_FILE, {"playlist_id": playlist_id, "name": name})


def resume_or_pick_default():
    """Resume the persisted default playlist if it's still eligible (not
    excluded), otherwise pick a fresh random one (or the fallback, if
    nothing qualifies). Switches the queue and starts playback. Returns
    (playlist_id, name, tracks_queued). Caller must hold radio_lock()."""
    state = load_default_state()
    excluded = set(load_exclusions())
    if state is not None and state["playlist_id"] not in excluded:
        count = play_playlist_now(state["playlist_id"])
        return state["playlist_id"], state["name"], count
    client = get_subsonic_client()
    chosen = pick_random_playlist(client) or {"id": FALLBACK_PLAYLIST_ID, "name": "fallback"}
    save_default_state(chosen["id"], chosen["name"])
    count = play_playlist_now(chosen["id"])
    return chosen["id"], chosen["name"], count


# --- Play one song next, then let the existing queue carry on ---------------

def search_tracks(query, limit=25):
    # This old Subsonic extension's search is genuinely slow (an
    # inefficient full-library scan under the hood) - give it real time
    # rather than a snappy default that'll just time out.
    result = rpc("core.library.search", {"query": {"any": [query]}}, timeout=45) or []
    tracks = []
    for r in result:
        tracks.extend(r.get("tracks") or [])
    return tracks[:limit]


def play_song_next(track_uri):
    """Insert a single track right after whatever's currently playing and
    jump to it. Once it ends, the untouched surrounding queue (whatever
    playlist/schedule/default was already looping) just continues on its
    own - no extra state needed to "go back" to it."""
    index = rpc("core.tracklist.index")
    at_position = (index + 1) if index is not None else 0
    added = rpc("core.tracklist.add", {"uris": [track_uri], "at_position": at_position})
    if not added:
        return False
    rpc("core.playback.play", {"tlid": added[0]["tlid"]})
    return True
