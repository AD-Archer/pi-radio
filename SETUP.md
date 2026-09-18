# Raspberry Pi 4 — Navidrome Radio

Always-on network jukebox: a Raspberry Pi 4 pulls music from Navidrome and streams
it over Bluetooth to your USB BT→FM transmitter, with a web UI for control on your LAN.

Stack: **Mopidy** (player daemon) + **Mopidy-Subsonic** (talks to Navidrome's Subsonic
API) + **BlueALSA** (routes audio to the paired Bluetooth device) + **Mopidy-Iris**
(web UI) + **systemd** (runs forever, starts on boot).

> This started out targeting an Orange Pi Zero 3, but we switched to a spare
> Raspberry Pi 4 partway through (easier headless setup via Raspberry Pi Imager,
> and more reliably-supported onboard WiFi/Bluetooth). Nothing below is
> Pi-4-specific except the flashing step — the rest of the stack is the same
> regardless of board.

## 1. Flash & first boot (already done)

Flashed with **Raspberry Pi Imager**, using its gear-icon "Edit Settings" screen to
pre-set hostname (`radio-pi`), enable SSH, and create the `radiopi` user — no
monitor or extra headless config file needed, unlike the Armbian route. It came up
on the LAN automatically and is reachable at:

```
ssh radiopi@10.0.0.198
```

> If you ever need to redo this: Raspberry Pi Imager → choose OS → choose SD card →
> gear icon (⚙) to set hostname/user/password/WiFi before writing → write → boot.

## 2. Set up your Navidrome credentials

```
cp config/mopidy.conf.example config/mopidy.conf
```

Edit `config/mopidy.conf`'s `[subsonic]` section with your real Navidrome
hostname/port/username/password. `config/mopidy.conf` is gitignored, so your
credentials never get committed — only the sanitized `.example` file is.

**The hostname must actually resolve from the Pi**, not just from your Mac —
check with `getent hosts <name>` over SSH. A bare LAN hostname often only
resolves on your own machine; an IP address, a Tailscale MagicDNS name, or an
`/etc/hosts` entry on the Pi all work.

## 3. Copy the setup files over and run the installer

From your Mac, in this project folder:

```
scp -r scripts config radiopi@10.0.0.198:~/radio-setup
ssh radiopi@10.0.0.198
cd ~/radio-setup
sudo bash scripts/setup.sh
```

The script installs Mopidy (pinned to Debian's 3.4.2, not the newer 4.x some
other sources offer — see README.md for why) + the Subsonic/Iris extensions
(patching several real bugs in the unmaintained Mopidy-Subsonic package along
the way), sets up BlueALSA, and drops your Mopidy config in place. It'll pause
partway through and walk you through pairing your FM transmitter dongle
interactively via `bluetoothctl`, since it needs you to pick out which
discovered device is yours.

## 4. Use it

- Web UI (Iris): `http://10.0.0.198:6680` (swap in your Pi's actual address)
- Iris here only supports **search** and **playlists**, not folder-style
  artist/album browsing — a limitation of the old Subsonic extension, not
  Mopidy itself.
- For continuous "always playing, loops forever, picks up newly-added songs"
  radio behavior (rather than manually queuing from Iris each time), see
  `scripts/radio-playlist-sync.py` in the README — a small timer-driven script
  that keeps a chosen Navidrome playlist looping and also self-heals the
  Bluetooth connection after a power cycle.

## Troubleshooting

- `systemctl status mopidy` / `journalctl -u mopidy -f` — player logs.
- `bluetoothctl devices` / `bluetoothctl info <MAC>` — check pairing + connection state.
- `sudo systemctl status bluealsa` — audio routing to the BT sink.
- `bluetoothctl power on` failing with `Failed to set power on:
  org.bluez.Error.Failed`, or `hciconfig` reporting `RF-kill` → the radio is
  soft-blocked: `sudo rfkill unblock bluetooth` (already handled by `setup.sh`,
  but can recur if something else re-blocks it).
- No sound but Iris shows playback progressing → almost always the
  `PROFILE=a2dp` device MAC in `/etc/mopidy/mopidy.conf`'s `[audio] output`
  line doesn't match your paired device; re-check with `bluetoothctl devices`.
- Music not resuming after a power cycle → Bluetooth does not auto-reconnect
  to the dongle on its own after reboot (the Pi has to initiate that). Either
  run `bluetoothctl connect <MAC>` manually, or set up
  `scripts/radio-playlist-sync.timer`, which checks and reconnects
  automatically every 2 minutes.
