#!/usr/bin/env python3
"""Keeps Mopidy playing continuously, in priority order:

1. A one-off "play X for N minutes" override set via radio-webapp.py, if
   still active - left completely alone until it expires.
2. A recurring daily schedule entry (also set via radio-webapp.py) whose
   time-of-day has arrived - switched to automatically, every day, forever.
3. Otherwise, a randomly-picked playlist (excluding anything marked
   excluded in radio-webapp.py), looped forever, with newly-added Navidrome
   tracks appended in automatically. The random pick is made once on
   entering this mode and stays stable - it doesn't reshuffle every run.

Runs periodically (see radio-playlist-sync.timer).

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
than editing this file - RADIO_PLAYLIST_ID (default/fallback Navidrome
playlist ID, found in its URL) and RADIO_BLUETOOTH_MAC (your paired dongle's
address, from `bluetoothctl devices`) are specific to each install.
"""
import json
import subprocess
import sys
import time

sys.path.insert(0, "/usr/local/bin")
from radio_common import (  # noqa: E402
    BLUETOOTH_MAC,
    clear_override,
    get_subsonic_client,
    load_default_state,
    load_exclusions,
    load_override,
    load_schedule_state,
    load_schedules,
    play_playlist_now,
    playlist_track_uris,
    radio_lock,
    read_raw_override,
    resolve_active_schedule,
    resume_or_pick_default,
    rpc,
    save_schedule_state,
)

STUCK_STATE_FILE = "/var/lib/mopidy/.radio-sync-last.json"
UNSET = object()  # sentinel: distinguishes "no schedule state file yet" from "no schedule active"


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


def load_stuck_state():
    try:
        with open(STUCK_STATE_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def save_stuck_state(state):
    try:
        with open(STUCK_STATE_FILE, "w") as f:
            json.dump(state, f)
    except OSError:
        pass


def ensure_playing(playlist_id_if_empty):
    """If playback isn't running, resume it - but if the tracklist is
    actually empty (e.g. a real Mopidy service restart wiped it, not just
    a pause), a plain play() is a no-op, so do a full re-queue instead."""
    with radio_lock():
        if rpc("core.tracklist.get_length") == 0:
            play_playlist_now(playlist_id_if_empty)
        else:
            rpc("core.playback.play")


def recover_stuck_playback():
    print("Playback stuck (same track/position since last check) - reconnecting Bluetooth and restarting playback.")
    subprocess.run(["bluetoothctl", "disconnect", BLUETOOTH_MAC], capture_output=True, text=True)
    time.sleep(2)
    subprocess.run(["bluetoothctl", "connect", BLUETOOTH_MAC], capture_output=True, text=True)
    time.sleep(3)
    with radio_lock():
        rpc("core.playback.stop")
        time.sleep(1)
        rpc("core.playback.play")


def sync_playlist(playlist_id, label):
    """Steady-state behaviour: append any new tracks from the given
    playlist without disturbing the current queue position."""
    with radio_lock():
        client = get_subsonic_client()
        uris = playlist_track_uris(client, playlist_id)

        if not uris:
            print(f"{label} has no songs, nothing to queue.")
        else:
            current = rpc("core.tracklist.get_tracks") or []
            current_uris = {t["uri"] for t in current}
            new_uris = [u for u in uris if u not in current_uris]
            if new_uris:
                rpc("core.tracklist.add", {"uris": new_uris})
                print(f"Added {len(new_uris)} new track(s) from {label}.")
            else:
                print("No new tracks.")

        rpc("core.tracklist.set_repeat", {"value": True})
        rpc("core.tracklist.set_consume", {"value": False})

        if uris and rpc("core.playback.get_state") != "playing":
            rpc("core.playback.play")
            print("Playback was stopped, started it.")


def main():
    ensure_bluetooth_connected()

    state = rpc("core.playback.get_state")
    track = rpc("core.playback.get_current_track") or {}
    position = rpc("core.playback.get_time_position")
    last = load_stuck_state()
    if (
        state == "playing"
        and last is not None
        and track.get("uri") == last.get("uri")
        and position == last.get("position")
    ):
        recover_stuck_playback()
    save_stuck_state({"uri": track.get("uri"), "position": position})

    override = load_override()
    if override is not None:
        print(f"Manual override active ({override['name']!r}).")
        if state != "playing":
            ensure_playing(override["playlist_id"])
            print("Playback wasn't playing, started/resumed it.")
        return

    if read_raw_override() is not None:
        print("A manual override just expired, clearing it.")
        clear_override()

    schedules = load_schedules()
    active = resolve_active_schedule(schedules)
    active_id = active["id"] if active else None
    schedule_state = load_schedule_state()
    stored_id = schedule_state["active_schedule_id"] if schedule_state is not None else UNSET

    if active_id != stored_id:
        if active is not None:
            print(f"Schedule change: switching to {active['name']!r} ({active['time']}).")
            with radio_lock():
                play_playlist_now(active["playlist_id"])
        else:
            with radio_lock():
                _, name, _ = resume_or_pick_default()
            print(f"Schedule change: no schedule active, back to default ({name!r}).")
        save_schedule_state(active_id)
        return

    if active is not None:
        print(f"Schedule {active['name']!r} still active.")
        if state != "playing":
            ensure_playing(active["playlist_id"])
            print("Playback wasn't playing, started/resumed it.")
        return

    default_state = load_default_state()
    if default_state is None or default_state["playlist_id"] in load_exclusions():
        with radio_lock():
            _, name, _ = resume_or_pick_default()
        print(f"Default playlist no longer eligible, switched to {name!r}.")
        return

    sync_playlist(default_state["playlist_id"], f"default playlist {default_state['name']!r}")


if __name__ == "__main__":
    main()
