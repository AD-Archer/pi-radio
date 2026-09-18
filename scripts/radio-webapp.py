#!/usr/bin/env python3
"""Tiny LAN webpage: search Navidrome playlists, play one exclusively for a
chosen duration (or indefinitely), or pin one to a recurring daily time slot.

Talks to Mopidy via JSON-RPC and writes the same state files that
radio-playlist-sync.py reads, so the two cooperate: this page decides what
should play, the sync timer (every 2 min) enforces it and reverts/switches
on schedule. All tracklist-mutating calls go through radio_lock() so this
webapp and the sync timer can never interleave and corrupt the queue.

Run standalone: python3 radio-webapp.py (see radio-webapp.service for the
systemd unit). Listens on 0.0.0.0:5050.
"""
import sys
import time

sys.path.insert(0, "/usr/local/bin")
from radio_common import (  # noqa: E402
    DEFAULT_PLAYLIST_ID,
    add_schedule,
    clear_override,
    get_subsonic_client,
    load_override,
    load_schedules,
    play_playlist_now,
    radio_lock,
    remove_schedule,
    resolve_active_schedule,
    rpc,
    save_override,
)

from flask import Flask, jsonify, request  # noqa: E402

app = Flask(__name__)


@app.errorhandler(Exception)
def handle_error(e):
    app.logger.exception("request failed")
    return jsonify({"error": str(e)}), 500


PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Radio</title>
<style>
  :root {
    --bg: #0b0d12;
    --card: #161923;
    --card-border: #262b3a;
    --text: #e8eaf0;
    --muted: #8b91a3;
    --accent: #6c8cff;
    --accent-dim: #3b4a8f;
    --danger: #ff6b6b;
    --ok: #4ade80;
  }
  * { box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: var(--bg);
    color: var(--text);
    max-width: 640px;
    margin: 0 auto;
    padding: 1.5rem 1rem 4rem;
  }
  h1 { font-size: 1.4rem; font-weight: 600; margin-bottom: 0.25rem; }
  .subtitle { color: var(--muted); font-size: 0.9rem; margin-bottom: 1.5rem; }
  .card {
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: 14px;
    padding: 1.1rem;
    margin-bottom: 1.2rem;
  }
  .card h2 {
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--muted);
    margin: 0 0 0.8rem;
    font-weight: 600;
  }
  input[type=text], input[type=time], select {
    font-size: 1rem;
    padding: 0.6rem 0.7rem;
    border-radius: 8px;
    border: 1px solid var(--card-border);
    background: #0f1117;
    color: var(--text);
    width: 100%;
  }
  input[type=text]:focus, input[type=time]:focus, select:focus {
    outline: none;
    border-color: var(--accent);
  }
  button {
    font-size: 0.95rem;
    padding: 0.55rem 1rem;
    border-radius: 8px;
    border: 1px solid var(--accent-dim);
    background: var(--accent);
    color: #fff;
    cursor: pointer;
    font-weight: 500;
    white-space: nowrap;
  }
  button:hover { filter: brightness(1.08); }
  button:disabled { opacity: 0.5; cursor: default; filter: none; }
  button.secondary { background: transparent; color: var(--text); border-color: var(--card-border); }
  button.danger { background: transparent; color: var(--danger); border-color: var(--danger); padding: 0.3rem 0.6rem; font-size: 0.85rem; }
  .row { display: flex; gap: 0.5rem; align-items: center; }
  .row + .row { margin-top: 0.6rem; }
  .search-row { margin-bottom: 0.8rem; }
  .results { max-height: 280px; overflow-y: auto; }
  .result-row, .schedule-row {
    display: flex; justify-content: space-between; align-items: center;
    padding: 0.6rem 0.2rem; border-bottom: 1px solid var(--card-border);
  }
  .result-row:last-child, .schedule-row:last-child { border-bottom: none; }
  .name { font-weight: 500; }
  .muted { color: var(--muted); font-size: 0.85rem; }
  .time-badge {
    font-variant-numeric: tabular-nums;
    background: #0f1117; border: 1px solid var(--card-border);
    padding: 0.15rem 0.5rem; border-radius: 6px; margin-right: 0.6rem;
    font-size: 0.9rem; color: var(--accent);
  }
  #nowPlayingTitle { font-size: 1.15rem; font-weight: 600; }
  #nowPlayingArtist { color: var(--muted); }
  .status-line { margin-top: 0.5rem; font-size: 0.9rem; color: var(--muted); }
  .toast {
    position: fixed; bottom: 1.2rem; left: 50%; transform: translateX(-50%);
    background: #1c1f2b; border: 1px solid var(--card-border); border-radius: 10px;
    padding: 0.7rem 1.1rem; font-size: 0.9rem; box-shadow: 0 4px 20px rgba(0,0,0,0.4);
    display: none; max-width: 90%;
  }
  .toast.ok { border-color: var(--ok); color: var(--ok); }
  .toast.error { border-color: var(--danger); color: var(--danger); }
  .empty { color: var(--muted); font-size: 0.9rem; padding: 0.5rem 0; }
</style>
</head>
<body>

<h1>Radio</h1>
<div class="subtitle">Navidrome &rarr; Bluetooth &rarr; FM</div>

<div class="card">
  <h2>Now playing</h2>
  <div id="nowPlayingTitle">&mdash;</div>
  <div id="nowPlayingArtist"></div>
  <div class="status-line" id="statusLine">Loading...</div>
</div>

<div class="card">
  <h2>Play a playlist</h2>
  <div class="row search-row">
    <input type="text" id="q" placeholder="Search playlists..." oninput="search()">
  </div>
  <div class="row search-row">
    <select id="minutes">
      <option value="15">For 15 minutes</option>
      <option value="30">For 30 minutes</option>
      <option value="60" selected>For 1 hour</option>
      <option value="120">For 2 hours</option>
      <option value="240">For 4 hours</option>
      <option value="">Until changed</option>
    </select>
  </div>
  <div class="results" id="results"></div>
</div>

<div class="card">
  <h2>Daily schedule</h2>
  <div class="row">
    <input type="time" id="scheduleTime" style="flex: 0 0 auto; width: 8rem;">
    <input type="text" id="scheduleSearch" placeholder="Search playlist to schedule..." oninput="scheduleSearch()">
  </div>
  <div class="results" id="scheduleResults"></div>
  <div class="row" id="scheduleSelectedRow" style="display:none; margin-top:0.6rem;">
    <span class="muted">Selected: <span id="scheduleSelectedName"></span></span>
    <button onclick="addSchedule()">Add to schedule</button>
  </div>
  <div id="scheduleList" style="margin-top: 0.8rem;"></div>
</div>

<div class="toast" id="toast"></div>

<script>
let scheduleSelected = null;
let busy = false;

function toast(msg, kind) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = 'toast ' + (kind || '');
  el.style.display = 'block';
  clearTimeout(el._t);
  el._t = setTimeout(() => el.style.display = 'none', 4000);
}

async function api(path, opts) {
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || ('HTTP ' + res.status));
  return data;
}

async function search() {
  const q = document.getElementById('q').value;
  const el = document.getElementById('results');
  try {
    const playlists = await api('/api/playlists?q=' + encodeURIComponent(q));
    renderResults(el, playlists, (p) => play(p.id, p.name));
  } catch (e) {
    el.innerHTML = `<div class="empty">Couldn't load playlists: ${e.message}</div>`;
  }
}

async function scheduleSearch() {
  const q = document.getElementById('scheduleSearch').value;
  const el = document.getElementById('scheduleResults');
  try {
    const playlists = await api('/api/playlists?q=' + encodeURIComponent(q));
    renderResults(el, playlists, (p) => selectForSchedule(p.id, p.name), 'Select');
  } catch (e) {
    el.innerHTML = `<div class="empty">Couldn't load playlists: ${e.message}</div>`;
  }
}

function renderResults(el, playlists, onPick, label) {
  el.innerHTML = '';
  if (playlists.length === 0) {
    el.innerHTML = '<div class="empty">No playlists found.</div>';
    return;
  }
  playlists.forEach(p => {
    const row = document.createElement('div');
    row.className = 'result-row';
    row.innerHTML = `<span class="name">${p.name} <span class="muted">(${p.songCount} songs)</span></span>`;
    const btn = document.createElement('button');
    btn.textContent = label || 'Play';
    btn.onclick = () => onPick(p);
    row.appendChild(btn);
    el.appendChild(row);
  });
}

function selectForSchedule(id, name) {
  scheduleSelected = {id, name};
  document.getElementById('scheduleSelectedName').textContent = name;
  document.getElementById('scheduleSelectedRow').style.display = 'flex';
}

async function play(id, name) {
  if (busy) return;
  busy = true;
  try {
    const minutes = document.getElementById('minutes').value;
    const r = await api('/api/play', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({playlist_id: id, name: name, minutes: minutes ? parseInt(minutes) : null})
    });
    toast(`Playing "${name}" (${r.queued} tracks queued)`, 'ok');
  } catch (e) {
    toast('Failed to play: ' + e.message, 'error');
  } finally {
    busy = false;
    refreshStatus();
  }
}

async function cancelOverride() {
  if (busy) return;
  busy = true;
  try {
    await api('/api/cancel', {method: 'POST'});
    toast('Back to the default playlist', 'ok');
  } catch (e) {
    toast('Failed: ' + e.message, 'error');
  } finally {
    busy = false;
    refreshStatus();
  }
}

async function addSchedule() {
  const time = document.getElementById('scheduleTime').value;
  if (!time || !scheduleSelected) { toast('Pick a time and a playlist first', 'error'); return; }
  try {
    await api('/api/schedules', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({playlist_id: scheduleSelected.id, name: scheduleSelected.name, time: time})
    });
    toast('Added to schedule', 'ok');
    scheduleSelected = null;
    document.getElementById('scheduleSelectedRow').style.display = 'none';
    document.getElementById('scheduleSearch').value = '';
    document.getElementById('scheduleResults').innerHTML = '';
    loadSchedules();
  } catch (e) {
    toast('Failed: ' + e.message, 'error');
  }
}

async function deleteSchedule(id) {
  try {
    await api('/api/schedules/' + id, {method: 'DELETE'});
    loadSchedules();
  } catch (e) {
    toast('Failed: ' + e.message, 'error');
  }
}

async function loadSchedules() {
  const el = document.getElementById('scheduleList');
  try {
    const schedules = await api('/api/schedules');
    if (schedules.length === 0) {
      el.innerHTML = '<div class="empty">No recurring schedule set - just the default playlist all day.</div>';
      return;
    }
    el.innerHTML = '';
    schedules.forEach(s => {
      const row = document.createElement('div');
      row.className = 'schedule-row';
      row.innerHTML = `<span><span class="time-badge">${s.time}</span>${s.name}</span>`;
      const btn = document.createElement('button');
      btn.className = 'danger';
      btn.textContent = 'Remove';
      btn.onclick = () => deleteSchedule(s.id);
      row.appendChild(btn);
      el.appendChild(row);
    });
  } catch (e) {
    el.innerHTML = `<div class="empty">Couldn't load schedule: ${e.message}</div>`;
  }
}

async function refreshStatus() {
  try {
    const s = await api('/api/status');
    const track = s.current_track;
    document.getElementById('nowPlayingTitle').textContent = track ? track.name : '(nothing queued)';
    document.getElementById('nowPlayingArtist').textContent = track && track.artists
      ? track.artists.map(a => a.name).join(', ') : '';

    let line;
    if (s.override) {
      const mins = s.seconds_left != null ? Math.round(s.seconds_left / 60) + ' min left' : 'no time limit';
      line = `Playing "${s.override.name}" on loop (${mins}) &mdash; `
        + `<a href="#" onclick="cancelOverride(); return false;">back to default now</a>`;
    } else if (s.active_schedule) {
      line = `Following daily schedule: "${s.active_schedule.name}" (since ${s.active_schedule.time})`;
    } else {
      line = 'Looping the default playlist';
    }
    document.getElementById('statusLine').innerHTML = line;
  } catch (e) {
    document.getElementById('statusLine').textContent = 'Status unavailable: ' + e.message;
  }
}

search();
loadSchedules();
refreshStatus();
setInterval(refreshStatus, 4000);
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
    entries.sort(key=lambda e: e.get("name", "").lower())
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
    with radio_lock():
        count = play_playlist_now(playlist_id)
        save_override(playlist_id, name, minutes)
    return jsonify({"queued": count})


@app.route("/api/cancel", methods=["POST"])
def api_cancel():
    with radio_lock():
        clear_override()
        count = play_playlist_now(DEFAULT_PLAYLIST_ID)
    return jsonify({"queued": count})


@app.route("/api/schedules", methods=["GET"])
def api_schedules_list():
    schedules = sorted(load_schedules(), key=lambda s: s["time"])
    return jsonify(schedules)


@app.route("/api/schedules", methods=["POST"])
def api_schedules_add():
    body = request.get_json(force=True)
    entry = add_schedule(body["playlist_id"], body["name"], body["time"])
    return jsonify(entry)


@app.route("/api/schedules/<schedule_id>", methods=["DELETE"])
def api_schedules_delete(schedule_id):
    remove_schedule(schedule_id)
    return jsonify({"ok": True})


@app.route("/api/status")
def api_status():
    override = load_override()
    seconds_left = None
    if override is not None and override.get("expires_at") is not None:
        seconds_left = max(0, override["expires_at"] - time.time())
    active_schedule = None
    if override is None:
        active_schedule = resolve_active_schedule(load_schedules())
    current_track = rpc("core.playback.get_current_track")
    return jsonify({
        "override": override,
        "seconds_left": seconds_left,
        "active_schedule": active_schedule,
        "current_track": current_track,
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050)
