# pico-radio

An always-on network radio: pulls music from a [Navidrome](https://www.navidrome.org/)
server and streams it over Bluetooth to a USB Bluetooth→FM transmitter, so any
FM radio in range can tune in — controlled from a web page on your LAN.

```
Navidrome  --(Subsonic API, WiFi)-->  Raspberry Pi 4  --(Bluetooth A2DP)-->  USB BT→FM dongle  -->  any FM radio
                                            |
                                        Mopidy-Iris (web UI, port 6680)
```

Runs as a headless appliance: plug it in, it joins the network, connects to
Navidrome and the Bluetooth dongle on its own, and keeps *something* playing
forever. By default that's a rotation through random Navidrome playlists —
plays one all the way through (picking up newly-added songs automatically),
then a *different* random one, and so on — layer on top of that: a daily
recurring schedule, one-off timed overrides, searching and playing/queueing
individual playlists, albums, or songs, and excluding specific playlists
from rotation. It's an installable PWA ("Radio") with accounts, roles, and
an audit log, all from a web page on your LAN.

## Hardware

- Raspberry Pi 4 (or similar — nothing here is actually Pi-4-specific beyond
  the flashing step; see [SETUP.md](SETUP.md) for the "we switched boards
  mid-project" story)
- A USB Bluetooth-to-FM-transmitter dongle
- An existing Navidrome server on your network

## Setup

See [SETUP.md](SETUP.md) for the full walkthrough: flashing the SD card,
headless network setup, Navidrome credentials, and running the installer.

Short version:

```bash
cp config/mopidy.conf.example config/mopidy.conf
# edit config/mopidy.conf with your real Navidrome hostname/username/password

scp -r scripts config <user>@<pi-ip>:~/radio-setup
ssh <user>@<pi-ip>
cd ~/radio-setup
sudo bash scripts/setup.sh
```

`setup.sh` installs Mopidy + the Subsonic/Iris plugins, sets up Bluetooth
audio routing (BlueALSA), and walks you through pairing your FM dongle
interactively.

## Using it

Open `http://<pi-ip>:6680` for the web UI (Mopidy-Iris). Search your
Navidrome library or pick a playlist, and it plays over Bluetooth to your FM
dongle.

For "just keep something looping forever, add songs whenever" behavior
instead of manually queuing things each time, set up the sync timer. By
default it randomly picks one Navidrome playlist and loops it (stable until
something else takes over, not reshuffling every run) — `RADIO_PLAYLIST_ID`
below is only the fallback used if literally nothing is eligible (e.g.
every playlist got excluded):

```bash
sudo cp scripts/radio-playlist-sync.py /usr/local/bin/
sudo cp scripts/radio-playlist-sync.service scripts/radio-playlist-sync.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now radio-playlist-sync.timer
```

Edit the `Environment=` lines in `radio-playlist-sync.service` first:
`RADIO_PLAYLIST_ID` (the last path segment of the playlist's URL in
Navidrome's web UI) and `RADIO_BLUETOOTH_MAC` (from `bluetoothctl devices`
after pairing). This same script also reconnects Bluetooth automatically
after a power cycle — see "Known issues" below for why that's necessary.

### The web app: picking things yourself, scheduling, and accounts

`http://<pi-ip>:5050` is a second web page — a real React app (`frontend/`),
served by the same Flask backend as static files, and installable as a PWA
named "Radio" (an "Add to Home Screen"/install prompt shows up in the
browser — it has a manifest, icons, and a service worker via
`vite-plugin-pwa`). It's styled after a classic click-wheel iPod: a menu
list on the home screen, one screen deep per feature, a "‹ Menu" back
button, and a live status dot in the title bar. Each screen is a real
route (`/playlists`, `/schedule`, ...) via React Router, so the browser's
back/forward buttons and direct links work normally — the Flask backend
serves `index.html` for any unrecognized path so refreshing on a deep link
doesn't 404. A previous/pause-or-play/skip transport bar stays fixed at
the bottom; only the middle content scrolls. Logging in is required (see
"Accounts, roles, and the audit log" below); Schedule/Rotation/People/
Activity are admin-only and hidden from the menu for regular members.

Menu items:

- **Now Playing** — the current track sits in its own highlighted card
  (with a star button to favorite/unfavorite it in Navidrome on the spot)
  so it's visually unmistakable next to the plain "Recently played"/"Up
  next" lists above and below it. The screen opens scrolled so the card is
  at the top — history is reachable by scrolling up, upcoming by scrolling
  down. Also shows whether you're on the random rotation/a schedule/a
  timed override. Nothing is ever actually deleted from the tracklist just
  for having played (same idea as Iris showing history in its queue), so
  history is genuinely there to browse — click any row, past or future, to
  jump straight to it, or use the up/down arrows on an upcoming track to
  reorder the queue. The transport bar's previous button steps back
  normally too.
- **Playlists** / **Albums** — search playlists or albums: **Play now**
  clears the queue and plays it (through once by default; or pick a
  duration to loop it, up to "until changed") — auto-reverts to the
  rotation once it finishes or the timer runs out. **Queue next** inserts
  the whole playlist/album right after the current track *without*
  clearing or disturbing anything else queued.
- **Songs** — search individual tracks. **Play now** jumps to it
  immediately (interrupting what's playing); **Queue next** inserts it
  after the current track without interrupting anything.
- **Favorites** — your Navidrome-starred songs, with the same Play
  now/Queue next actions as Songs.
- **Schedule** (admin) — pick a time + playlist, add it. Every day at that
  time, forever, it switches to that playlist automatically — a recurring
  programming grid. A one-off "Play now" always takes priority over the
  schedule until it ends, then the schedule resumes.
- **Rotation** (admin) — uncheck a playlist to exclude it from random
  rotation (it still works for search-and-play or scheduling).
- **People** (admin) — create accounts, promote/demote admin↔member,
  remove accounts, issue/revoke a per-user API token.
- **Activity** (admin) — the audit log: who did what, and when.

Build the frontend and deploy alongside the sync timer:

```bash
cd frontend && pnpm install && pnpm build && cd ..

sudo pip3 install --break-system-packages flask
sudo cp scripts/radio_common.py scripts/radio_auth.py scripts/radio-webapp.py scripts/create_user.py /usr/local/bin/
sudo cp scripts/radio-webapp.service /etc/systemd/system/
sudo mkdir -p /usr/local/share/radio-frontend
sudo cp -r frontend/dist /usr/local/share/radio-frontend/dist
sudo systemctl daemon-reload
sudo systemctl enable --now radio-webapp

# one-time: create your own admin account (there's no admin yet to do
# this through the app itself)
sudo python3 /usr/local/bin/create_user.py <your-username> <your-password> --role admin
```

(All of this runs from your dev machine, then gets `scp`'d to the Pi like
everything else in `scripts/` — see `RADIO_FRONTEND_DIST` in
`radio-webapp.service` if you deploy the built files somewhere else.)

For frontend development, `cd frontend && pnpm dev` runs a local dev
server that proxies `/api/*` to the real Pi (see `vite.config.js`), so you
can iterate against live data without deploying anything.

The backend (`radio-webapp.py`) and `radio-playlist-sync.py` share state
via `radio_common.py` (small JSON files for the current override and the
schedule list) — the webapp decides what should play, the sync timer
enforces and reverts/switches it on schedule. All tracklist-mutating
operations go through a file lock (`radio_lock()`) so the webapp and the
sync timer can never interleave and corrupt the queue, even from rapid
clicks. Both services need the same `RADIO_PLAYLIST_ID` set as their
default/fallback.

### Accounts, roles, and the audit log

`radio_auth.py` is a small SQLite-backed user system (`/var/lib/mopidy/radio-users.db`) —
not a real multi-tenant auth stack, just enough to know who's doing what
and let one person (you) manage who else gets access:

- **Two roles.** `member` can do anything playback-related: play/queue
  playlists, albums, songs, favorites, skip/pause/resume/previous. `admin`
  can additionally manage the daily schedule, rotation exclusions, other
  user accounts, and view the audit log. There's no per-action permission
  toggle beyond this — the audit log is the main tool for accountability
  ("who skipped my song at 2am") rather than locking down every button.
- **Login is required for everything** except the login endpoint itself
  and the static frontend shell (so the "log in" screen can load at all).
- **Every mutating request is logged automatically** — `radio_auth.login_required`
  writes an audit-log row (who, what endpoint, when, and the request body)
  after any successful POST/PUT/DELETE, so there was no need to hand-instrument
  two dozen existing route bodies individually.
- **Bootstrapping**: since there's no admin yet to create the first account
  through the app, `scripts/create_user.py` creates one directly against
  the database over SSH (see the deploy command above). Run it again
  anytime to add more people without needing the web UI.
- Manage everyone else from the **People** screen once you're an admin
  yourself: create accounts, promote/demote, remove, or issue a personal
  API token (shown once, for the cross-site use case below).

### Using the API from somewhere else

The backend sends permissive CORS headers (`Access-Control-Allow-Origin: *`)
so another page or tool on your LAN can call it directly — but since
accounts were added, every call still needs to authenticate as *someone*.
A session cookie only works for the browser tab that logged in, so for a
separate site/tool, issue yourself a personal API token from the **People**
screen and send it as a bearer header instead:

```
POST /api/pause
POST /api/resume
POST /api/skip
GET  /api/status   # current track, playback_state, what mode it's in
```

```bash
curl -H "Authorization: Bearer <your-token>" http://<pi-ip>:5050/api/status
```

The rest of `scripts/radio-webapp.py` (playlists, albums, songs, favorites,
queue, and schedule/exclusions/admin routes if your token belongs to an
admin) is fair game too — it's just JSON over HTTP.

A deliberate pause is left alone (it won't get resumed within the next
sync tick like a genuine stop/crash would) — but if it's left paused for
15+ minutes straight, `radio-playlist-sync.py` resumes it on its own
rather than sitting silent all day.

## How it works

- **Mopidy** — the player daemon. Holds the queue, does the actual playing,
  runs as a systemd service.
- **Mopidy-Subsonic** — lets Mopidy read a Navidrome library over the
  Subsonic API.
- **Mopidy-Iris** — the web UI. Search, playlists, queue management, from
  any browser on the LAN.
- **BlueALSA** — routes Mopidy's audio output to a paired Bluetooth device
  instead of a speaker jack.
- **radio-playlist-sync** (timer, every 15s) — enforces whatever should
  currently be playing (random default / schedule / override), keeps its
  tracks queued and looping, and reconnects Bluetooth if it dropped (e.g.
  after a reboot).
- **radio-webapp + frontend/** — a Flask JSON API (port 5050) serving a
  React app (styled after a click-wheel iPod menu, installable as a PWA):
  search playlists, albums, songs, or favorites; play one now (once
  through, or looped for a duration) or queue it next without disturbing
  anything else; pin a playlist to a recurring daily time slot; exclude
  playlists from random rotation; see the live cue sheet and skip/remove/
  reorder tracks. Writes state files that radio-playlist-sync.py reads and
  enforces.
- **radio_auth.py** — SQLite-backed accounts (admin/member roles), session
  and bearer-token login, and the audit log. `login_required`/`admin_required`
  gate every route and log mutating requests automatically.

## Known issues

- **Accounts run over plain HTTP, not HTTPS** — this is a LAN appliance
  with no TLS anywhere (Mopidy, Flask, none of it), so login credentials
  and API tokens travel in plaintext on your local network. Fine for a
  trusted home network; don't reuse a password you care about, and don't
  expose port 5050 to the internet as-is.
- **Up to 2 minutes of silence after a playlist finished** — the sync
  timer only ran every 2 minutes, so rotating to a new playlist (or
  reconnecting Bluetooth, or catching stuck playback) waited on that same
  slow cadence. Each run is cheap (~1s, a handful of lightweight RPC
  calls), so there was no real reason for it to be that slow — reduced to
  every 15 seconds.
- **The random rotation can feel like it's "stuck" on one playlist** — it
  picks uniformly among playlists, not weighted by track count, so a much
  longer playlist (e.g. a 74-track "Radio" vs. others in the 20-40 range)
  naturally occupies a disproportionate share of listening time once
  picked, even though the rotation itself is genuinely random (confirmed
  via the sync log: different playlists each time). Not a bug, but if a
  particular playlist dominates more than you'd like, exclude it from
  rotation on the Rotation screen — it'll still be playable manually or
  via schedule.
- **Toasts were positioned relative to the browser viewport, not the
  device frame** — on a wide desktop screen they'd appear centered on the
  whole page instead of the (narrower, centered) device column, and could
  sit behind/under the fixed transport bar. Fixed: `.toast-stack` is now
  `position: absolute` inside `#root` (which is `position: relative`), and
  offset by `--transport-bar-height` so it always clears the bar.
- **The Now Playing screen had no visual separation between what already
  played and what's currently playing** — everything was one flat list.
  Fixed: the current track now sits in its own bordered/tinted card, with
  plain "Recently played"/"Up next" list labels above and below it.
- **Removing the currently-playing track from the queue could break
  playback** — a real race: the UI's queue view can be a few seconds stale
  (polled every 4s), so a row that was "coming up" when fetched can become
  the *actively playing* track by the time you click remove on it. Yanking
  the live track out from under Mopidy left it stuck "paused" with no
  current track at all. Fixed two ways: `remove_from_queue()` checks the
  actual current track right before removing and skips instead if they
  match, and `radio-playlist-sync.py` recognizes "paused with nothing
  loaded" as a broken state and recovers immediately (rather than waiting
  out the 15-minute pause grace period) — verified by reproducing the
  broken state via raw Mopidy RPC and confirming the sync script fixed it
  on the next run.
- **"Play now" defaulted to looping for a fixed duration (1 hour), which
  could cut a track off mid-song the instant the timer hit** — confusing,
  since the natural expectation for "play this playlist" is that it plays
  through, not that it gets truncated on a clock. `/api/play` now defaults
  to `once=true` (play through one time, no looping, ends on its own);
  looping for a set duration or indefinitely ("until changed") remains
  available as an explicit choice.
- **The base GStreamer install can't decode AAC (.m4a) audio at all.** It
  fails hard mid-playback (`Could not find a MPEG-4 AAC decoder`) and stops
  outright rather than skipping the track — only surfaces once a Navidrome
  playlist happens to contain an AAC file, which made it look like a random
  Bluetooth issue at first. `setup.sh` now installs
  `gstreamer1.0-plugins-bad` and `gstreamer1.0-libav` upfront.
- **Mopidy is pinned to 3.4.2**, not the newer 4.x that some sources (like
  apt.mopidy.com) offer by default. Mopidy-Iris and Mopidy-Subsonic haven't
  caught up to Mopidy 4's internal API changes yet — under 4.x, Iris crashes
  on a missing module and Subsonic won't even load. `setup.sh` installs
  straight from Debian's own repo (which currently ships 3.4.2) and holds
  the package so it won't silently upgrade and break.
- **Mopidy-Subsonic (PyPI, by `rattboi`) is unmaintained since ~2015-2016**
  and needed several real patches to work under modern Mopidy/Python —
  a malformed package manifest that hid it from Mopidy entirely, a required
  config field its own defaults left blank, a few Python-2-only constructs,
  and an integer-vs-string type mismatch that crashed every track with a
  release year. All of these are applied automatically by `setup.sh` (see
  the script and [PROJECT.md](PROJECT.md) for details) — but because they're
  patches to someone else's abandoned package rather than a real fix
  upstream, a future version bump of the extension could shift what the
  patches target.
- **Iris only supports search and playlists for Navidrome**, not folder-style
  artist/album browsing — this old Subsonic extension predates Mopidy's
  browse API.
- **Bluetooth does not auto-reconnect after a reboot.** The Pi is the side
  that initiates the connection to the dongle, and BlueZ doesn't redo that
  on its own after a power cycle — only the adapter itself powers back on.
  `radio-playlist-sync.timer` covers this by checking and reconnecting every
  15 seconds, so recovery after a power cycle takes up to ~15 seconds
  rather than being instant.
- **Playback can silently stall mid-track** — Mopidy keeps reporting
  `"playing"` with no error logged, but the position just stops advancing
  forever (seen once, cause suspected to be a Bluetooth link hiccup).
  `radio-playlist-sync.py` now detects this by comparing (track, position)
  against what it saw last run; if unchanged 15 seconds later while
  "playing", it reconnects Bluetooth and restarts playback.
- **Resuming after a real Mopidy service restart could silently no-op** —
  the "already active, just call play() if stopped" paths assumed the
  tracklist still had the songs queued from before, which isn't true after
  an actual `systemctl restart mopidy` (as opposed to a pause/reboot),
  since that wipes the in-memory tracklist. Fixed: `ensure_playing()` now
  checks for an empty tracklist and does a full re-queue instead of a
  no-op `play()`.
- **`/api/play` silently 500'd** — an earlier refactor's import-list edit
  accidentally dropped `play_playlist_now` while the route still called it
  directly, only caught while rebuilding the backend for the React
  frontend. Fixed by re-adding the import; worth noting since it shipped
  unnoticed for a while (the surrounding `/api/cancel` path used a
  different helper and kept working).
- **Rapid double-clicking "Play" used to corrupt the queue** — Flask's dev
  server + two near-simultaneous requests could interleave a `clear()` from
  one request with an `add()` from another, leaving a mixed tracklist that
  never actually resumed playback. Fixed with a file lock (`radio_lock()`)
  that all queue-mutating code (webapp and sync timer alike) now holds
  around clear+add+play sequences.

See [PROJECT.md](PROJECT.md) for the fuller build log, architecture
rationale, and what's still on the roadmap (an Icecast/DLNA phase for
non-Bluetooth playback).

## Repo layout

```
SETUP.md                          full setup walkthrough
PROJECT.md                        architecture, build log, known issues in depth
config/
  mopidy.conf.example             sanitized config template (commit this)
  mopidy.conf                     your real credentials (gitignored, not committed)
scripts/
  setup.sh                        installer - run on the Pi
  radio_common.py                 shared helpers (Mopidy RPC, override/schedule state)
  radio-playlist-sync.py          rotation/schedule/override enforcement + Bluetooth self-heal
  radio-playlist-sync.service     systemd unit for the above
  radio-playlist-sync.timer       runs it every 15 seconds
  radio-webapp.py                 JSON API backend + static file server (port 5050)
  radio-webapp.service            systemd unit for the above
  radio_auth.py                   accounts, sessions/tokens, audit log (SQLite)
  create_user.py                  CLI to bootstrap/add a user account
frontend/                         React app (Vite) - the actual web UI
  src/                            components, API client, styles
  dist/                           `pnpm build` output (gitignored, deployed separately)
```
