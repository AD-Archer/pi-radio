#!/usr/bin/env python3
"""JSON API backend for the React frontend (see ../../frontend).

Search Navidrome playlists/albums/songs, play one exclusively for a chosen
duration (or indefinitely), queue a playlist/album/song next without
disturbing anything else, pin a playlist to a recurring daily time slot,
and exclude playlists from random default rotation.

Talks to Mopidy via JSON-RPC and writes the same state files that
radio-playlist-sync.py reads, so the two cooperate: this page decides what
should play, the sync timer (every 15s) enforces it and reverts/switches
on schedule. All tracklist-mutating calls go through radio_lock() so this
webapp and the sync timer can never interleave and corrupt the queue.

Accounts (see radio_auth.py): every route except login/logout/me and the
static frontend requires a logged-in user (session cookie for the web UI,
or a bearer API token for programmatic/cross-site access). Schedule and
rotation-exclusion management, plus user administration and the audit log,
are admin-only; everything else (playback, queueing, favorites) is open to
any logged-in member. Every mutating request is logged automatically.

Also serves the built React app (frontend/dist) as static files, so the
whole thing is reachable from one port. Run standalone: python3
radio-webapp.py (see radio-webapp.service for the systemd unit). Listens on
0.0.0.0:5050.
"""
import os
import sys
import time

sys.path.insert(0, "/usr/local/bin")
from radio_common import (  # noqa: E402
    add_schedule,
    clear_override,
    get_all_playlists,
    get_favorite_tracks,
    get_queue,
    get_subsonic_client,
    is_track_starred,
    load_default_state,
    move_in_queue,
    load_exclusions,
    load_override,
    load_schedules,
    play_item_now,
    play_previous,
    play_song_next,
    play_tlid,
    queue_item_next,
    queue_playlist_next,
    queue_song_next,
    radio_lock,
    remove_from_queue,
    remove_schedule,
    resolve_active_schedule,
    resume_or_pick_default,
    rpc,
    save_override,
    search_albums,
    search_tracks,
    set_exclusion,
    star_track,
    unstar_track,
)
from radio_auth import (  # noqa: E402
    admin_required,
    count_admins,
    create_user,
    delete_user,
    generate_token,
    get_or_create_token,
    get_user_by_username,
    init_db,
    list_audit_log,
    list_users,
    login_required,
    revoke_token,
    set_role,
    verify_user,
)

from flask import Flask, g, jsonify, request, send_from_directory, session  # noqa: E402

FRONTEND_DIST = os.environ.get(
    "RADIO_FRONTEND_DIST",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "dist"),
)
SECRET_KEY_FILE = "/var/lib/mopidy/.radio-flask-secret"

app = Flask(__name__)
init_db()

if os.path.exists(SECRET_KEY_FILE):
    with open(SECRET_KEY_FILE) as f:
        app.secret_key = f.read().strip()
else:
    app.secret_key = os.urandom(32).hex()
    os.makedirs(os.path.dirname(SECRET_KEY_FILE), exist_ok=True)
    with open(SECRET_KEY_FILE, "w") as f:
        f.write(app.secret_key)


@app.errorhandler(Exception)
def handle_error(e):
    app.logger.exception("request failed")
    return jsonify({"error": str(e)}), 500


@app.after_request
def add_cors_headers(response):
    # Permissive origin by design: this is meant to be callable from other
    # pages/tools on the LAN (e.g. a separate dashboard doing skip/pause).
    # That only works unauthenticated-cookie-free though - a cross-origin
    # caller uses its own user's bearer token (see radio_auth.py), not a
    # session cookie, since browsers won't send credentialed cookies to a
    # wildcard-CORS origin anyway.
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response


# --- Auth ----------------------------------------------------------------

@app.route("/api/auth/login", methods=["POST"])
def api_login():
    body = request.get_json(force=True)
    user = verify_user(body.get("username", ""), body.get("password", ""))
    if user is None:
        return jsonify({"error": "Wrong username or password"}), 401
    session["username"] = user["username"]
    return jsonify(user)


@app.route("/api/auth/token", methods=["POST"])
def api_auth_token():
    # Trades username+password for the user's bearer token, so an MCP
    # server or other headless app can authenticate once with a password
    # and store the token instead of juggling session cookies. Reuses an
    # existing token rather than rotating it, so this can be called
    # repeatedly (e.g. re-run setup) without breaking other callers that
    # already have that token.
    body = request.get_json(force=True)
    user = verify_user(body.get("username", ""), body.get("password", ""))
    if user is None:
        return jsonify({"error": "Wrong username or password"}), 401
    return jsonify({"token": get_or_create_token(user["id"]), "user": user})


@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/auth/me")
def api_me():
    username = session.get("username")
    user = get_user_by_username(username) if username else None
    return jsonify({"user": user})


# --- Playlists ---------------------------------------------------------------

@app.route("/api/playlists")
@login_required
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
@login_required
def api_play():
    """Clear the queue and play only this playlist - a full takeover.
    once=True (the default): plays through one time, no looping, and ends
    on its own the moment it finishes. once=False: loops for `minutes`
    (or forever if minutes is null/"until changed"), until the timer runs
    out or it's cancelled."""
    body = request.get_json(force=True)
    playlist_id = body["playlist_id"]
    name = body["name"]
    minutes = body.get("minutes")
    once = bool(body.get("once", False))
    with radio_lock():
        count = play_item_now("playlist", playlist_id, repeat=not once)
        save_override("playlist", playlist_id, name, minutes, once=once)
    return jsonify({"queued": count})


@app.route("/api/albums")
@login_required
def api_albums():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    albums = search_albums(q)
    return jsonify([
        {"id": a["id"], "name": a["name"], "artist": a.get("artist", ""), "songCount": a.get("songCount", 0)}
        for a in albums
    ])


@app.route("/api/play-album", methods=["POST"])
@login_required
def api_play_album():
    """Same semantics as /api/play, for an album instead of a playlist."""
    body = request.get_json(force=True)
    album_id = body["album_id"]
    name = body["name"]
    minutes = body.get("minutes")
    once = bool(body.get("once", False))
    with radio_lock():
        count = play_item_now("album", album_id, repeat=not once)
        save_override("album", album_id, name, minutes, once=once)
    return jsonify({"queued": count})


@app.route("/api/queue-album-next", methods=["POST"])
@login_required
def api_queue_album_next():
    """Insert this album's tracks right after the current track, without
    clearing or disturbing anything already queued."""
    body = request.get_json(force=True)
    with radio_lock():
        count = queue_item_next("album", body["album_id"])
    return jsonify({"queued": count})


@app.route("/api/queue-playlist-next", methods=["POST"])
@login_required
def api_queue_playlist_next():
    """Insert this playlist's tracks right after the current track, without
    clearing or disturbing anything already queued."""
    body = request.get_json(force=True)
    with radio_lock():
        count = queue_playlist_next(body["playlist_id"])
    return jsonify({"queued": count})


@app.route("/api/cancel", methods=["POST"])
@login_required
def api_cancel():
    with radio_lock():
        clear_override()
        playlist_id, name, count = resume_or_pick_default()
    return jsonify({"queued": count, "playlist_id": playlist_id, "name": name})


# --- Songs --------------------------------------------------------------------

@app.route("/api/songs")
@login_required
def api_songs():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    tracks = search_tracks(q)
    return jsonify([
        {
            "uri": t["uri"],
            "name": t["name"],
            "artist": ", ".join(a["name"] for a in t.get("artists", [])),
        }
        for t in tracks
    ])


@app.route("/api/play-song", methods=["POST"])
@login_required
def api_play_song():
    """Insert a single track right after the current one and jump to it
    immediately (interrupts what's playing now)."""
    body = request.get_json(force=True)
    with radio_lock():
        ok = play_song_next(body["uri"])
    return jsonify({"ok": ok})


@app.route("/api/queue-song", methods=["POST"])
@login_required
def api_queue_song():
    """Insert a single track right after the current one WITHOUT jumping -
    it plays once the current track ends naturally, nothing interrupted."""
    body = request.get_json(force=True)
    with radio_lock():
        ok = queue_song_next(body["uri"])
    return jsonify({"ok": ok})


@app.route("/api/favorites")
@login_required
def api_favorites():
    tracks = get_favorite_tracks()
    return jsonify([
        {
            "uri": f"subsonic://{t['id']}",
            "name": t["title"],
            "artist": t.get("artist", ""),
        }
        for t in tracks
    ])


@app.route("/api/favorites/<path:uri>", methods=["PUT"])
@login_required
def api_favorites_set(uri):
    body = request.get_json(force=True)
    if body.get("starred"):
        star_track(uri)
    else:
        unstar_track(uri)
    return jsonify({"ok": True})


def _serialize_tl(tl):
    return {
        "tlid": tl["tlid"],
        "uri": tl["track"]["uri"],
        "name": tl["track"].get("name", "?"),
        "artist": ", ".join(a["name"] for a in tl["track"].get("artists", [])),
    }


# --- Live queue (history + current + upcoming) -------------------------------

@app.route("/api/queue")
@login_required
def api_queue():
    current_tlid, history, upcoming = get_queue()
    return jsonify({
        "current_tlid": current_tlid,
        "history": [_serialize_tl(tl) for tl in history],
        "upcoming": [_serialize_tl(tl) for tl in upcoming],
    })


@app.route("/api/queue/<int:tlid>", methods=["DELETE"])
@login_required
def api_queue_remove(tlid):
    with radio_lock():
        remove_from_queue(tlid)
    return jsonify({"ok": True})


@app.route("/api/queue/<int:tlid>/play", methods=["POST"])
@login_required
def api_queue_play(tlid):
    play_tlid(tlid)
    return jsonify({"ok": True})


@app.route("/api/queue/<int:tlid>/move", methods=["POST"])
@login_required
def api_queue_move(tlid):
    body = request.get_json(force=True)
    with radio_lock():
        moved = move_in_queue(tlid, body["direction"])
    return jsonify({"ok": moved})


@app.route("/api/skip", methods=["POST"])
@login_required
def api_skip():
    rpc("core.playback.next")
    return jsonify({"ok": True})


@app.route("/api/previous", methods=["POST"])
@login_required
def api_previous():
    play_previous()
    return jsonify({"ok": True})


@app.route("/api/pause", methods=["POST"])
@login_required
def api_pause():
    rpc("core.playback.pause")
    return jsonify({"ok": True})


@app.route("/api/resume", methods=["POST"])
@login_required
def api_resume():
    rpc("core.playback.resume")
    return jsonify({"ok": True})


# --- Exclusions (random default rotation) - admin only ------------------------

@app.route("/api/exclusions")
@admin_required
def api_exclusions_list():
    client = get_subsonic_client()
    excluded = set(load_exclusions())
    playlists = get_all_playlists(client)
    playlists.sort(key=lambda p: p.get("name", "").lower())
    return jsonify([
        {"id": p["id"], "name": p["name"], "songCount": p.get("songCount", 0), "excluded": p["id"] in excluded}
        for p in playlists
    ])


@app.route("/api/exclusions/<playlist_id>", methods=["PUT"])
@admin_required
def api_exclusions_set(playlist_id):
    body = request.get_json(force=True)
    set_exclusion(playlist_id, bool(body.get("excluded")))
    return jsonify({"ok": True})


# --- Daily schedule - admin only ----------------------------------------------

@app.route("/api/schedules", methods=["GET"])
@admin_required
def api_schedules_list():
    schedules = sorted(load_schedules(), key=lambda s: s["time"])
    return jsonify(schedules)


@app.route("/api/schedules", methods=["POST"])
@admin_required
def api_schedules_add():
    body = request.get_json(force=True)
    entry = add_schedule(body["playlist_id"], body["name"], body["time"])
    return jsonify(entry)


@app.route("/api/schedules/<schedule_id>", methods=["DELETE"])
@admin_required
def api_schedules_delete(schedule_id):
    remove_schedule(schedule_id)
    return jsonify({"ok": True})


# --- User administration + audit log - admin only ----------------------------

@app.route("/api/admin/users")
@admin_required
def api_admin_users():
    return jsonify(list_users())


@app.route("/api/admin/users", methods=["POST"])
@admin_required
def api_admin_users_create():
    body = request.get_json(force=True)
    user_id = create_user(body["username"], body["password"], role=body.get("role", "member"))
    return jsonify({"id": user_id})


@app.route("/api/admin/users/<int:user_id>", methods=["PUT"])
@admin_required
def api_admin_users_update(user_id):
    body = request.get_json(force=True)
    if body.get("role") == "member" and user_id == g.current_user["id"] and count_admins() <= 1:
        return jsonify({"error": "Can't demote the last admin"}), 400
    set_role(user_id, body["role"])
    return jsonify({"ok": True})


@app.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
@admin_required
def api_admin_users_delete(user_id):
    if user_id == g.current_user["id"]:
        return jsonify({"error": "Can't delete your own account"}), 400
    delete_user(user_id)
    return jsonify({"ok": True})


@app.route("/api/admin/users/<int:user_id>/token", methods=["POST"])
@admin_required
def api_admin_users_token(user_id):
    return jsonify({"token": generate_token(user_id)})


@app.route("/api/admin/users/<int:user_id>/token", methods=["DELETE"])
@admin_required
def api_admin_users_revoke_token(user_id):
    revoke_token(user_id)
    return jsonify({"ok": True})


@app.route("/api/admin/audit-log")
@admin_required
def api_admin_audit_log():
    return jsonify(list_audit_log())


# --- Status --------------------------------------------------------------------

@app.route("/api/status")
@login_required
def api_status():
    override = load_override()
    seconds_left = None
    if override is not None and override.get("expires_at") is not None:
        seconds_left = max(0, override["expires_at"] - time.time())
    active_schedule = None
    default_state = None
    if override is None:
        active_schedule = resolve_active_schedule(load_schedules())
        if active_schedule is None:
            default_state = load_default_state()
    current_track = rpc("core.playback.get_current_track")
    playback_state = rpc("core.playback.get_state")
    current_track_starred = is_track_starred(current_track["uri"]) if current_track else None
    return jsonify({
        "override": override,
        "seconds_left": seconds_left,
        "active_schedule": active_schedule,
        "default_state": default_state,
        "current_track": current_track,
        "current_track_starred": current_track_starred,
        "playback_state": playback_state,
    })


# --- Static frontend (built React app) ---------------------------------------

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    if path and os.path.exists(os.path.join(FRONTEND_DIST, path)):
        return send_from_directory(FRONTEND_DIST, path)
    return send_from_directory(FRONTEND_DIST, "index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050)
