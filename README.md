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
Navidrome and the Bluetooth dongle on its own, and keeps a playlist looping
forever — add songs to that playlist from anywhere and they join the loop
automatically, no restart needed.

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

For "just keep a playlist looping forever, add songs whenever" behavior
instead of manually queuing things each time, set up the sync timer:

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

### Picking a playlist yourself, or scheduling one daily

`http://<pi-ip>:5050` is a second, smaller web page with three parts:

- **Now playing** — live track/artist, and whether you're on the default
  playlist, a schedule, or a timed override.
- **Play a playlist** — search, pick a duration (15 min – 4 hr, or "until
  changed"), hit Play. Clears the queue to play *only* that playlist on
  loop; auto-reverts to the default playlist when the timer runs out (or
  hit "back to default now" to end it early).
- **Daily schedule** — pick a time + playlist, hit "Add to schedule". Every
  day at that time, forever, it switches to that playlist automatically —
  like a recurring radio programming grid. A one-off "Play" always takes
  priority over the schedule until its timer expires, then the schedule
  resumes.

Set up alongside the sync timer:

```bash
sudo pip3 install --break-system-packages flask
sudo cp scripts/radio_common.py scripts/radio-webapp.py /usr/local/bin/
sudo cp scripts/radio-webapp.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now radio-webapp
```

This and `radio-playlist-sync.py` share state via `radio_common.py` (small
JSON files for the current override and the schedule list) — the webpage
decides what should play, the sync timer enforces and reverts/switches it
on schedule. All tracklist-mutating operations go through a file lock
(`radio_lock()`) so the webapp and the sync timer can never interleave and
corrupt the queue, even if you click Play multiple times quickly. Both
services need the same `RADIO_PLAYLIST_ID` set as their default/fallback.

## How it works

- **Mopidy** — the player daemon. Holds the queue, does the actual playing,
  runs as a systemd service.
- **Mopidy-Subsonic** — lets Mopidy read a Navidrome library over the
  Subsonic API.
- **Mopidy-Iris** — the web UI. Search, playlists, queue management, from
  any browser on the LAN.
- **BlueALSA** — routes Mopidy's audio output to a paired Bluetooth device
  instead of a speaker jack.
- **radio-playlist-sync** (timer, every 2 min) — keeps a chosen Navidrome
  playlist's tracks queued and looping, and reconnects Bluetooth if it
  dropped (e.g. after a reboot).
- **radio-webapp** — a tiny Flask page (port 5050) to search playlists,
  play one exclusively for a set duration (auto-reverting after), or pin
  one to a recurring daily time slot. Writes state files that
  radio-playlist-sync.py reads and enforces.

## Known issues

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
  2 minutes, so recovery after a power cycle takes up to ~2 minutes rather
  than being instant.
- **Playback can silently stall mid-track** — Mopidy keeps reporting
  `"playing"` with no error logged, but the position just stops advancing
  forever (seen once, cause suspected to be a Bluetooth link hiccup).
  `radio-playlist-sync.py` now detects this by comparing (track, position)
  against what it saw last run; if unchanged 2 minutes later while
  "playing", it reconnects Bluetooth and restarts playback.
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
  radio_common.py                 shared helpers (Mopidy RPC, override state)
  radio-playlist-sync.py          looping-playlist + Bluetooth self-heal
  radio-playlist-sync.service     systemd unit for the above
  radio-playlist-sync.timer       runs it every 2 minutes
  radio-webapp.py                 playlist-picker webpage (port 5050)
  radio-webapp.service            systemd unit for the above
```
