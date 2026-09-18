"""Shared helpers for radio-playlist-sync.py and radio-webapp.py.

Deployed to /usr/local/bin alongside the scripts that import it (both add
that directory to sys.path before importing) - not a real installed package,
just a shared module for two small personal scripts.
"""
import configparser
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, f"/usr/local/lib/python3.{sys.version_info.minor}/dist-packages")
from mopidy_subsonic.client import SubsonicRemoteClient  # noqa: E402

DEFAULT_PLAYLIST_ID = os.environ.get("RADIO_PLAYLIST_ID", "1OfGteB2iY40tKxcmugen9")  # "Radio" playlist
BLUETOOTH_MAC = os.environ.get("RADIO_BLUETOOTH_MAC", "41:42:BD:42:27:E5")  # FM02
MOPIDY_RPC = "http://localhost:6680/mopidy/rpc"
MOPIDY_CONF = "/etc/mopidy/mopidy.conf"
OVERRIDE_STATE_FILE = "/var/lib/mopidy/.radio-override.json"


def rpc(method, params=None):
    payload = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        payload["params"] = params
    req = urllib.request.Request(
        MOPIDY_RPC,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.load(resp).get("result")


def get_subsonic_client():
    cfg = configparser.ConfigParser()
    cfg.read(MOPIDY_CONF)
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
    """Clear the queue, load only this playlist's tracks, loop, and play."""
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


def read_raw_override():
    """Returns the override record regardless of expiry, or None if there
    isn't one at all. Use load_override() unless you specifically need to
    tell "never set" apart from "set but expired"."""
    try:
        with open(OVERRIDE_STATE_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


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
    os.makedirs(os.path.dirname(OVERRIDE_STATE_FILE), exist_ok=True)
    with open(OVERRIDE_STATE_FILE, "w") as f:
        json.dump(state, f)
    return state


def clear_override():
    try:
        os.remove(OVERRIDE_STATE_FILE)
    except FileNotFoundError:
        pass
