#!/usr/bin/env python3
"""Tiny LAN webpage: search Navidrome playlists, play one exclusively for a
chosen duration (or indefinitely), then auto-revert to the default playlist.

Talks to Mopidy via JSON-RPC and writes the same override state file that
radio-playlist-sync.py reads, so the two cooperate: this page sets what
should play, the sync timer enforces it / reverts it when the timer's up.

Run standalone: python3 radio-webapp.py (see radio-webapp.service for the
systemd unit). Listens on 0.0.0.0:5050.
"""
import sys

sys.path.insert(0, "/usr/local/bin")
from radio_common import (  # noqa: E402
    DEFAULT_PLAYLIST_ID,
    clear_override,
    get_subsonic_client,
    load_override,
    play_playlist_now,
    rpc,
    save_override,
)

from flask import Flask, jsonify, request  # noqa: E402

app = Flask(__name__)

PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Radio</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 480px; margin: 2rem auto; padding: 0 1rem; background: #111; color: #eee; }
  h1 { font-size: 1.3rem; }
  input, select, button { font-size: 1rem; padding: 0.5rem; border-radius: 6px; border: 1px solid #444; background: #222; color: #eee; }
  input[type=text] { width: 100%; box-sizing: border-box; margin-bottom: 0.5rem; }
  #results { margin-top: 1rem; }
  .row { display: flex; justify-content: space-between; align-items: center; padding: 0.6rem 0; border-bottom: 1px solid #333; }
  .name { flex: 1; margin-right: 0.5rem; }
  button { cursor: pointer; }
  button:hover { background: #333; }
  #status { margin-top: 1.5rem; padding: 0.8rem; border-radius: 8px; background: #1c1c1c; border: 1px solid #333; }
  #controls { display: flex; gap: 0.5rem; margin-bottom: 1rem; }
  .muted { color: #999; font-size: 0.9rem; }
</style>
</head>
<body>
<h1>Radio playlist picker</h1>

<div id="controls">
  <input type="text" id="q" placeholder="Search playlists..." oninput="search()">
  <select id="minutes">
    <option value="15">15 min</option>
    <option value="30">30 min</option>
    <option value="60" selected>1 hour</option>
    <option value="120">2 hours</option>
    <option value="240">4 hours</option>
    <option value="">Until changed</option>
  </select>
</div>

<div id="results"></div>

<div id="status">Loading status...</div>

<script>
async function search() {
  const q = document.getElementById('q').value;
  const res = await fetch('/api/playlists?q=' + encodeURIComponent(q));
  const playlists = await res.json();
  const el = document.getElementById('results');
  el.innerHTML = '';
  playlists.forEach(p => {
    const row = document.createElement('div');
    row.className = 'row';
    row.innerHTML = `<span class="name">${p.name} <span class="muted">(${p.songCount} songs)</span></span>`;
    const btn = document.createElement('button');
    btn.textContent = 'Play';
    btn.onclick = () => play(p.id, p.name);
    row.appendChild(btn);
    el.appendChild(row);
  });
}

async function play(id, name) {
  const minutes = document.getElementById('minutes').value;
  await fetch('/api/play', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({playlist_id: id, name: name, minutes: minutes ? parseInt(minutes) : null})
  });
  refreshStatus();
}

async function cancelOverride() {
  await fetch('/api/cancel', {method: 'POST'});
  refreshStatus();
}

async function refreshStatus() {
  const res = await fetch('/api/status');
  const s = await res.json();
  const el = document.getElementById('status');
  if (s.override) {
    const mins = s.seconds_left != null ? Math.round(s.seconds_left / 60) + ' min left' : 'no time limit';
    el.innerHTML = `Now playing on loop: <b>${s.override.name}</b> (${mins})<br>
      <button onclick="cancelOverride()">Back to default Radio now</button>`;
  } else {
    el.innerHTML = `Playing the default Radio playlist on loop.`;
  }
}

search();
refreshStatus();
setInterval(refreshStatus, 5000);
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return PAGE


@app.route("/api/playlists")
def api_playlists():
    q = request.args.get("q", "").strip().lower()
    client = get_subsonic_client()
    data = client.api.getPlaylists()
    entries = data.get("playlists", {}).get("playlist", [])
    if isinstance(entries, dict):
        entries = [entries]
    if q:
        entries = [e for e in entries if q in e.get("name", "").lower()]
    return jsonify([
        {"id": e["id"], "name": e["name"], "songCount": e.get("songCount", 0)}
        for e in entries
    ])


@app.route("/api/play", methods=["POST"])
def api_play():
    body = request.get_json(force=True)
    playlist_id = body["playlist_id"]
    name = body["name"]
    minutes = body.get("minutes")
    count = play_playlist_now(playlist_id)
    save_override(playlist_id, name, minutes)
    return jsonify({"queued": count})


@app.route("/api/cancel", methods=["POST"])
def api_cancel():
    clear_override()
    count = play_playlist_now(DEFAULT_PLAYLIST_ID)
    return jsonify({"queued": count})


@app.route("/api/status")
def api_status():
    override = load_override()
    seconds_left = None
    if override is not None and override.get("expires_at") is not None:
        import time
        seconds_left = max(0, override["expires_at"] - time.time())
    current_track = rpc("core.playback.get_current_track")
    return jsonify({
        "override": override,
        "seconds_left": seconds_left,
        "current_track": current_track,
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050)
