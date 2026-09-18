# Project: Navidrome Radio Box

## Mission

Turn a Raspberry Pi 4 into an always-on network jukebox: pull music from
Navidrome, stream it out over Bluetooth to a USB BT→FM transmitter (so any FM
radio in the house can tune in), and control it all from a webpage on the LAN
(pick albums/playlists, play/pause/skip). Optionally, also expose the stream
so DLNA-aware devices can find and play it directly over WiFi.

## Architecture

```
                         ┌─────────────────────────┐
                         │   Navidrome (existing)   │
                         │   your music library     │
                         └────────────┬─────────────┘
                                      │ Subsonic API (WiFi)
                                      ▼
┌───────────────────────────────────────────────────────────────┐
│                    Raspberry Pi 4 (Raspberry Pi OS)             │
│                                                                 │
│   ┌────────────────────────┐                                   │
│   │   Mopidy (the player)   │◄──────── controlled by ──────┐    │
│   │  - holds the queue      │                              │    │
│   │  - talks to Navidrome   │                              │    │
│   │    via Mopidy-Subsonic  │                              │    │
│   └────────┬───────┬────────┘                              │    │
│            │       │                                       │    │
│    ┌───────┘       └────────┐                              │    │
│    ▼                        ▼                              │    │
│ ┌─────────┐          ┌─────────────┐               ┌───────┴───┐│
│ │ BlueALSA│          │   Icecast   │               │Mopidy-Iris││
│ │ (BT out)│          │ (HTTP/DLNA  │               │(web UI)   ││
│ └────┬────┘          │  stream out)│               └───────────┘│
│      │               └──────┬──────┘                     ▲      │
└──────┼──────────────────────┼────────────────────────────┼──────┘
       │ Bluetooth            │ WiFi (HTTP stream           │ WiFi
       ▼                      │ + optional DLNA             │ (browser)
┌─────────────┐               │  discovery)                 │
│ USB BT→FM   │               ▼                       ┌─────────────┐
│ transmitter │       Any DLNA TV/speaker,             │ Your phone/ │
│ dongle      │       or anything that can             │ laptop      │
└─────────────┘       open a stream URL                └─────────────┘
       │
       ▼
   FM radio waves → any FM receiver in the house
```

## Components

| Piece | Role | Status |
|---|---|---|
| Raspberry Pi OS (trixie) on Raspberry Pi 4 | base OS | done, SSH reachable at `radiopi@10.0.0.198` |
| Mopidy | player daemon, holds the queue | **done** — pinned to **3.4.2** (`apt-mark hold`), not the 4.0.4 that apt.mopidy.com offers by default |
| Mopidy-Subsonic | lets Mopidy read Navidrome's library | **done, but hand-patched** — see "Known issues" below |
| Mopidy-Iris | web UI (the "LAN website") | **done** — works, but see browsing limitation below |
| BlueALSA | routes audio to the paired Bluetooth dongle (FM02, `41:42:BD:42:27:E5`) | **done**, confirmed playing audio over Bluetooth |
| radio-playlist-sync (timer, every 15s - was every 2 min, too slow to rotate/reconnect) | keeps a chosen Navidrome playlist looping forever, picks up newly-added songs, self-heals Bluetooth after reboot | **done**, replaces the originally-planned MPD-based autoplay (dropped, see "Open decisions") |
| Icecast (Phase 2) | plain HTTP stream URL, playable by anything | not started |
| DLNA discovery, e.g. MiniDLNA/BubbleUPnP (Phase 3) | makes the Icecast stream browsable/discoverable by DLNA devices | not started, lower reliability, optional |

## Known issues / hand-patches applied (Phase 1)

Mopidy-Subsonic (PyPI `Mopidy-Subsonic` 1.0.0, by `rattboi`, last touched
~2015-2016) is essentially unmaintained and needed direct patches to its
installed files on the Pi (`/usr/local/lib/python3.13/dist-packages/mopidy_subsonic/`)
to work at all:

- `entry_points.txt` had a malformed section header (`[b'mopidy.ext']`
  instead of `[mopidy.ext]`) — a packaging bug that hid it from Mopidy's
  extension discovery entirely. Fixed by editing the file directly.
- `__init__.py`: the `context` config field was required by the schema but
  left blank by the extension's own defaults — patched to `optional=True`.
- `client.py`: multiple Python 2-only constructs that crash under Python
  3.13 — `unicode(...)` (→ `str(...)`, two spots) and `dict.iteritems()`
  (→ `.items()`).
- `client.py`: track `date` field was passed to Mopidy's `Track` model as a
  raw int (Navidrome's release year) but Mopidy 3.4.2 requires a string —
  patched to `str(data['year'])`.

**These patches are now folded into `scripts/setup.sh`** (applied via `sed`
right after `pip install`), so a from-scratch install reproduces this
automatically — they're no longer just hand-edits living only on the running
Pi. Still worth revisiting if a maintained alternative to Mopidy-Subsonic
ever surfaces, since patching someone else's abandoned package is inherently
fragile (a version bump of the extension could shift line numbers/content
the `sed` commands target).

**Also:** Mopidy has to stay off apt.mopidy.com's default (4.0.4 for trixie)
and instead come straight from Debian's own repo (3.4.2), because Mopidy-Iris
3.70.0 references `mopidy.models.serialize`, which doesn't exist in Mopidy
4.x — the plugin ecosystem (Iris, this Subsonic extension) hasn't caught up
to Mopidy 4 yet. `scripts/setup.sh` never adds the apt.mopidy.com repo at all
now (simpler than the original approach) and holds `mopidy` via
`apt-mark hold` so it won't silently upgrade and break again.

**Also:** the Bluetooth radio came up rfkill-soft-blocked at least once
during setup, which manifests as `bluetoothctl power on` failing with
`Failed to set power on: org.bluez.Error.Failed`. `scripts/setup.sh` now
runs `rfkill unblock bluetooth` before pairing.

**Iris browsing limitation:** because this Subsonic extension predates
Mopidy's folder-style `browse()` API, Iris only gets **search** and
**playlists** from Navidrome — no artist/album tree browsing. Search bar
and Navidrome-side playlists work fine.

## Build order

1. **Phase 1 — core radio. DONE.** Confirmed working end to end: Iris at
   `http://10.0.0.198:6680`, Navidrome search, Bluetooth audio to FM02,
   audible over FM.
2. **Phase 2 — network stream.** Add Icecast as a second Mopidy audio output.
   Verify the stream URL plays from another device on the LAN.
3. **Phase 3 — DLNA discovery (optional).** Layer DLNA/UPnP advertising on top
   of the Icecast stream so compatible TVs/speakers can find it without
   typing a URL. Only worth doing if plain URL-playing (Phase 2) isn't
   convenient enough in practice.

## Key files in this repo

See README.md for the full file listing and setup instructions.

## Open decisions

- Icecast/DLNA (Phase 2/3): confirmed we're doing Phase 1 first, then revisit.
- **On-boot autoplay: originally planned via Mopidy-MPD, dropped, replaced.**
  The separately-packaged `Mopidy-MPD` requires Mopidy ≥4.0.0, which
  conflicts with the 3.4.2 pin Iris/Subsonic need, so it was left
  uninstalled. Instead, `scripts/radio-playlist-sync.py` (HTTP JSON-RPC
  against Mopidy directly, no MPD needed) covers the same need and more: it
  keeps a chosen Navidrome playlist looping forever, appends newly-added
  songs into the loop automatically, and also self-heals the Bluetooth
  connection after a power cycle.
