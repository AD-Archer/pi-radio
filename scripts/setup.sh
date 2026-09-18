#!/usr/bin/env bash
# Sets up Mopidy + Mopidy-Subsonic + Mopidy-Iris + BlueALSA, wired up as an
# always-on Navidrome "radio" that streams over Bluetooth. Run as root:
#   sudo bash setup.sh
# See ../SETUP.md for the full walkthrough, ../README.md for the big picture.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Run this with sudo: sudo bash setup.sh" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo "==> Installing packages"
apt-get update -qq
# Mopidy comes straight from Debian's own repo (no third-party apt.mopidy.com
# repo needed) and gets held at whatever version Debian ships - currently
# 3.4.2, NOT the newer 4.x some other sources offer. That matters: Mopidy-Iris
# and Mopidy-Subsonic below haven't caught up to Mopidy 4's internal API
# changes yet and will fail to load under it.
apt-get install -y -qq \
  mopidy bluez bluez-alsa-utils python3-pip python3-setuptools rfkill
apt-mark hold mopidy

echo "==> Installing Mopidy extensions (Subsonic + Iris)"
pip3 install --break-system-packages --quiet Mopidy-Subsonic Mopidy-Iris py-sonic

echo "==> Patching Mopidy-Subsonic"
# The PyPI package (Mopidy-Subsonic 1.0.0, by rattboi) is unmaintained since
# ~2015-2016 and has several real bugs under a modern Mopidy/Python. See
# README.md "Known issues" for the story behind each of these.
SUBSONIC_DIR="$(python3 -c "import mopidy_subsonic, os; print(os.path.dirname(mopidy_subsonic.__file__))")"
DIST_INFO="$(python3 -c "import importlib.metadata as m; print(m.distribution('Mopidy-Subsonic')._path)")"

# Bug 1: malformed entry_points.txt hides the extension from Mopidy entirely.
sed -i "s/\[b.mopidy.ext.\]/[mopidy.ext]/" "$DIST_INFO/entry_points.txt"

# Bug 2: 'context' config field is required by the schema, but left blank by
# the extension's own bundled defaults - i.e. it fails validation out of the
# box no matter what you put in mopidy.conf, unless patched to be optional.
sed -i "s/schema\['context'\] = config.String()/schema['context'] = config.String(optional=True)/" \
  "$SUBSONIC_DIR/__init__.py"

# Bug 3: Python 2-only constructs that crash under Python 3.
sed -i 's/unicode(/str(/g; s/, unicode)/, str)/' "$SUBSONIC_DIR/client.py"
sed -i 's/obj.iteritems()/obj.items()/' "$SUBSONIC_DIR/client.py"

# Bug 4: Navidrome's release year comes back as an int; Mopidy's Track model
# requires date to be a string, so every track with a year crashes playback.
sed -i "s/track_kwargs\['date'\] = data\['year'\]/track_kwargs['date'] = str(data['year'])/" \
  "$SUBSONIC_DIR/client.py"

echo "==> Installing Mopidy config"
if [[ -f /etc/mopidy/mopidy.conf ]]; then
  cp /etc/mopidy/mopidy.conf "/etc/mopidy/mopidy.conf.bak.$(date +%s)"
  echo "    (backed up existing config)"
fi
mkdir -p /etc/mopidy
if [[ -f "$REPO_ROOT/config/mopidy.conf" ]]; then
  cp "$REPO_ROOT/config/mopidy.conf" /etc/mopidy/mopidy.conf
else
  cp "$REPO_ROOT/config/mopidy.conf.example" /etc/mopidy/mopidy.conf
  echo "    (no config/mopidy.conf found - copied the example. Edit"
  echo "    /etc/mopidy/mopidy.conf's [subsonic] section with your real"
  echo "    Navidrome details, then: sudo systemctl restart mopidy)"
fi

echo "==> Unblocking Bluetooth"
# Some images ship with the Bluetooth radio rfkill-soft-blocked by default,
# which makes `bluetoothctl power on` fail with "Failed to set power on:
# org.bluez.Error.Failed" and hciconfig fail with "RF-kill" - not obvious
# from the error alone.
rfkill unblock bluetooth

echo "==> Bluetooth pairing"
echo "Put your USB Bluetooth-to-FM-transmitter dongle into pairing mode now."
read -rp "Press Enter when it's ready to pair..."

systemctl enable --now bluetooth
bluetoothctl power on
bluetoothctl agent on
bluetoothctl default-agent
bluetoothctl scan on &
SCAN_PID=$!
echo "Scanning for 10 seconds..."
sleep 10
kill "$SCAN_PID" 2>/dev/null || true
bluetoothctl scan off

echo
echo "Discovered devices:"
bluetoothctl devices
echo
read -rp "Enter the MAC address of your FM transmitter dongle (e.g. AA:BB:CC:DD:EE:FF): " BT_MAC

bluetoothctl pair "$BT_MAC"
bluetoothctl trust "$BT_MAC"
bluetoothctl connect "$BT_MAC"

sed -i "s/device=bluealsa:DEV=[^,]*,/device=bluealsa:DEV=${BT_MAC},/" /etc/mopidy/mopidy.conf
echo "==> Wrote ${BT_MAC} into /etc/mopidy/mopidy.conf audio output"

echo "==> Enabling services"
systemctl enable --now bluealsa
systemctl enable --now mopidy

echo
echo "==> Done."
echo "Web UI: http://$(hostname -I | awk '{print $1}'):6680"
echo
echo "Note: Bluetooth does NOT auto-reconnect to the dongle after a reboot -"
echo "the Pi has to initiate that, not the dongle. See scripts/radio-playlist-sync.py"
echo "and README.md for a self-healing timer that handles this automatically."
