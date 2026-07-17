# 02 — Hardware & Access (how to reach and control the Pi)

## The hardware — PiKVM V4 Mini

- **Board:** CM4-based PiKVM V4 Mini, running official **PiKVM OS** (Arch Linux ARM, **read-only
  root filesystem**). Fanless.
- **HDMI capture:** Toshiba **TC358743** CSI bridge (needs a device-tree overlay + EDID
  firmware — PiKVM OS ships this working; this is why we don't use plain Raspberry Pi OS).
- **USB gadget (OTG):** the box emulates a USB keyboard/mouse (and optionally mass storage) to
  the target. UDC = `fe980000.usb`.
- **Video encoder:** ONE hardware H.264 encoder. Important consequence: **MJPEG and H.264
  can't both have clients at once** — so we default video to WebRTC/H.264 (see debug journal).

### Ports (corrected from the official datasheet — the owner's handbook was WRONG)
The V4 Mini has exactly **three USB-C ports**:
1. **Power** — 5.1V/3A in.
2. **USB 2.0 OTG** — the gadget connector *to the target PC* (keyboard/mouse/MSD emulation).
   Plug this into the machine you want to control.
3. **USB 2.0 Serial console** ("management port", silkscreened **IOIOI**). This is a **serial
   console**, NOT a general USB host port.

**There is NO general USB host port.** So you **cannot** use a USB WiFi dongle on the V4 Mini.
WiFi is the CM4's **internal** WiFi. Because the metal case blocks the internal antenna, a
solid connection wants an **external SMA antenna** (mount hole present; needs `dtparam=ant2`).
Ethernet is the other option (but Raj's laptop has no Ethernet → WiFi-first).

---

## Credentials (all of them)

| What | Value |
|------|-------|
| Pi IP (home / "Staff" network era) | historically `172.16.20.116`, `172.16.20.209`; **changes per location** |
| Pi IP (current, "Quality Inn- Office" network) | `192.168.1.37` (as of 2026-07-17 — will change again) |
| Pi mDNS name | `magicbridge.local` (only resolves in a browser w/ mDNS, or after avahi is healthy) |
| Pi SSH login (primary) | user `raj` / password `lol` |
| Pi SSH/serial login (root) | `root` / `root` |
| kvmd web login (the KVM itself) | `admin` / `admin` (change if Raj changed it) |
| Serial console | **COM8**, 115200 baud, CP210x USB-to-UART (VID:PID 10C4:EA60) |
| GitHub | repo github.com/razzrohith/MagicBridgeV2, branch `main` |

⚠️ These are Raj's own lab credentials for his own devices. Treat the password/secret files on
the device as sensitive (0600), but the creds above are needed to operate the project.

---

## How to connect — in order of preference

### 1. SSH over the network (best, when the Pi has an IP)
From the Windows laptop, use **paramiko scripts** (run via File Explorer address bar) or
**PuTTY**. Login `raj`/`lol` or `root`/`root`. This is the normal path for deploy + debug.

If `magicbridge.local` doesn't resolve from Windows: the Windows OS resolver lacks Bonjour
(only the browser has mDNS). Use the raw IP. To find the IP after a location change, scan the
subnet or read it off the OLED. Helper scripts exist: `find_pi.py`, `mb_find_and_diag.py`,
`mb_find_linklocal.py`, `mb_try_hosts.py`.

### 2. Serial console (COM8) — the recovery path when there's NO network
This is how we rescued the Pi at a new hotel with no known WiFi. Use `serial_lib.py` (a
paramiko-free pyserial wrapper): `PORT="COM8"; BAUD=115200`, `login()` tries root/root then
raj/lol, `run(cmd)` wraps commands in `MB_S_T_A_R_T … MB_E_N_D_$?` markers and extracts the
output, `clean()` strips shell-integration/ANSI/bracketed-paste escape codes.
- Serial survives when WiFi is down, the AP is misconfigured, etc.
- **Gotcha:** a backgrounded `reboot &` over serial gets SIGHUP'd when the session closes and
  never fires. Reboot synchronously or via `systemd-run --on-active=`.
- **Gotcha:** `printf '%s' "a\nb"` does NOT expand `\n`. Put escapes in the printf FORMAT
  string: `printf 'a\nb\n'`.

### 3. The captive portal (for onboarding at a brand-new location)
On boot, if the Pi has no working network, `mb-portal.service` raises an open WiFi hotspot
**"MagicBridge-Setup"** with a captive page at `http://192.168.73.1`. Connect a phone,
enter the local WiFi SSID + password, and the Pi saves them and **reboots to connect**. If the
password was wrong, the hotspot comes back on the next boot (retries until it truly connects).
See the debug journal — this had a long saga of bugs (all fixed).

### Manual WiFi connect over serial (when the AP is idle and you know the creds)
```
pkill hostapd; pkill dnsmasq
ip link set wlan0 down; iw dev wlan0 set type managed; ip link set wlan0 up
systemctl restart wpa_supplicant@wlan0; systemctl restart systemd-networkd
```
Associates + gets DHCP in ~15s, no reboot needed. PiKVM WiFi stack = `wpa_supplicant@wlan0`
(association) + `systemd-networkd` via `/etc/systemd/network/wlan0.network` (DHCP=yes).

---

## Running scripts on the Windows laptop (the "File Explorer address bar" trick)

Raj has **no admin rights** on this laptop, and the Linux sandbox **cannot reach the Pi**. So
all Pi access is done with **Windows Python + paramiko/pyserial** scripts, launched like this:

1. Focus a File Explorer window, press **`Alt+D`** (focus the address bar).
2. Type `cmd /c python C:\Users\razzr\Claude\Projects\MagicBridge\MagicBridgeV2\<script>.py`
3. Press **Enter**.
4. The script writes its own **`<script>_log.txt`** next to itself — read that for output.

**Rules that matter (learned the hard way):**
- Scripts write their own log file internally. **Never** shell-redirect (`> log.txt`) — it
  races Python's own file writer and you get an empty log.
- Large files (HTML) deploy via **SFTP** (`ssh.open_sftp()` / `sftp.put` / `sftp.putfo`), NOT
  base64-echo over the shell (buffer truncation corrupts them).
- In paramiko helpers, set `stdout.channel.settimeout(t)` before reading — `exec_command(timeout=)`
  does NOT bound `stdout.read()` and a non-terminating command hangs the whole script forever
  with no output (a documented paramiko gotcha; cost hours once).
- The desktop is often contested (VMware/Chrome/UAC steal focus and trigger Windows UIPI,
  which blocks synthetic input). If a click/keypress errors with "not in allowed applications"
  or "UIPI", call `open_application("File Explorer")` and retry, or wait for the user to free
  the screen.

---

## Deploy scripts you'll reuse (kept in the repo root)

| Script | What it does |
|--------|--------------|
| `sync_and_push.py "msg"` | robocopy build folder → `E:\` git repo (excludes logs/one-off scripts), then git add/commit/push to GitHub. **Run after every change.** |
| `align_pi.py` | SSH the Pi, `git fetch + reset --hard origin/main` on `/opt/magicbridge` (rw/ro toggle), verify clean + services active. *(Only works when the Pi is online.)* |
| `deploy_all.py` | SFTP the whole `web/` + `services/` tree to `/opt/magicbridge`. |
| `serial_lib.py` | The reusable serial-console class (COM8). |
| `serial_*.py`, `probe_*.py`, `test_*.py`, `deploy_phase*.py` | One-off diagnostics/deploys from past sessions — handy templates, excluded from git by `sync_and_push`. |

See `brain/06_DEPLOY_RUNBOOK.md` for the exact end-to-end workflow.
