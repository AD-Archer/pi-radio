#!/usr/bin/env python3
"""Keeps Mopidy's tracklist in sync with a Navidrome playlist and looping.

Runs periodically (see radio-playlist-sync.timer). Any track present in the
Navidrome playlist but not yet in Mopidy's tracklist gets appended - existing
queue position/playback is untouched. Repeat is kept on so the queue loops
forever, picking up newly-appended tracks as part of the loop.

Also self-heals two kinds of Bluetooth trouble:
1. After a reboot/power cycle, BlueZ powers the adapter back on but does NOT
   reconnect to the FM transmitter on its own (the Pi is the connecting
   side, not the dongle) - each run checks the connection and reconnects if
   needed, before touching playback.
2. Occasionally the Bluetooth audio link stalls mid-track: Mopidy reports
   "playing" and never errors, but the playback position simply stops
   advancing forever. Each run compares (track, position) against what was
   seen last run (2 minutes earlier via the timer); if both are identical
   while "playing", that's not a coincidence, it's stuck - reconnect
   Bluetooth and restart playback.

Configure via environment variables (see radio-playlist-sync.service) rather
than editing this file - RADIO_PLAYLIST_ID (Navidrome playlist ID, found in
its URL) and RADIO_BLUETOOTH_MAC (your paired dongle's address, from
`bluetoothctl devices`) are specific to each install.
"""
import configparser
import json
import os
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, f"/usr/local/lib/python3.{sys.version_info.minor}/dist-packages")
from mopidy_subsonic.client import SubsonicRemoteClient  # noqa: E402

PLAYLIST_ID = os.environ.get("RADIO_PLAYLIST_ID", "1OfGteB2iY40tKxcmugen9")  # "Radio" playlist
BLUETOOTH_MAC = os.environ.get("RADIO_BLUETOOTH_MAC", "41:42:BD:42:27:E5")  # FM02
MOPIDY_RPC = "http://localhost:6680/mopidy/rpc"
MOPIDY_CONF = "/etc/mopidy/mopidy.conf"
STATE_FILE = "/var/lib/mopidy/.radio-sync-last.json"


def ensure_bluetooth_connected():
    info = subprocess.run(
        ["bluetoothctl", "info", BLUETOOTH_MAC],
        capture_output=True, text=True,
    ).stdout
    if "Connected: yes" in info:
        return
    print(f"{BLUETOOTH_MAC} not connected, reconnecting...")
    subprocess.run(["bluetoothctl", "connect", BLUETOOTH_MAC], capture_output=True, text=True)
    time.sleep(3)  # give the A2DP profile a moment to negotiate before playback


def load_last_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def save_last_state(state):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except OSError:
        pass


def recover_stuck_playback():
    print("Playback stuck (same track/position since last check) - reconnecting Bluetooth and restarting playback.")
    subprocess.run(["bluetoothctl", "disconnect", BLUETOOTH_MAC], capture_output=True, text=True)
    time.sleep(2)
    subprocess.run(["bluetoothctl", "connect", BLUETOOTH_MAC], capture_output=True, text=True)
    time.sleep(3)
    rpc("core.playback.stop")
    time.sleep(1)
    rpc("core.playback.play")


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


def main():
    ensure_bluetooth_connected()

    state = rpc("core.playback.get_state")
    track = rpc("core.playback.get_current_track") or {}
    position = rpc("core.playback.get_time_position")
    last = load_last_state()
    if (
        state == "playing"
        and last is not None
        and track.get("uri") == last.get("uri")
        and position == last.get("position")
    ):
        recover_stuck_playback()
    save_last_state({"uri": track.get("uri"), "position": position})

    cfg = configparser.ConfigParser()
    cfg.read(MOPIDY_CONF)
    s = cfg["subsonic"]
    client = SubsonicRemoteClient(
        s["hostname"],
        s["port"],
        s["username"],
        s["password"],
        s.getboolean("ssl"),
        s.get("context", ""),
    )

    data = client.api.getPlaylist(pid=PLAYLIST_ID)
    entries = data.get("playlist", {}).get("entry", [])
    if isinstance(entries, dict):
        entries = [entries]
    uris = [f"subsonic://{e['id']}" for e in entries]

    if not uris:
        print("Radio playlist has no songs yet, nothing to queue.")
    else:
        current = rpc("core.tracklist.get_tracks") or []
        current_uris = {t["uri"] for t in current}
        new_uris = [u for u in uris if u not in current_uris]
        if new_uris:
            rpc("core.tracklist.add", {"uris": new_uris})
            print(f"Added {len(new_uris)} new track(s) from Radio playlist.")
        else:
            print("No new tracks.")

    rpc("core.tracklist.set_repeat", {"value": True})
    rpc("core.tracklist.set_consume", {"value": False})

    if uris and rpc("core.playback.get_state") != "playing":
        rpc("core.playback.play")
        print("Playback was stopped, started it.")


if __name__ == "__main__":
    main()
