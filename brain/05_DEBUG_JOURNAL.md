# 05 — Debug Journal (every bug, root cause, and fix)

**Read this before debugging anything.** Most "new" problems here are an old problem wearing a
different hat — usually the read-only rootfs. Entries are grouped; each has the symptom, the
root cause, and the fix. Commit hashes are in `github.com/razzrohith/MagicBridgeV2`.

---

## 🔴 The recurring master-cause: read-only rootfs

The PiKVM root fs is mounted read-only. **Any write that isn't wrapped in `rw`/`ro` silently
fails**, usually with a non-zero return code that some button then swallows. Every entry
marked ⭐ below is a variant of this. If something "does nothing," suspect this first.

- ⭐ **`save_config()` never persisted anything** (identity, MAC, DuckDNS, lockdown reset on
  reboot). Cause: state dir `/var/lib/magicbridge` is on the RO rootfs; the write never
  unlocked it. Fix (`95b71cc`): `mbcommon.save_config()` now does an `_fs("rw")`/`_fs("ro")`
  toggle around the write.
- ⭐ **Tailscale wouldn't install or come up.** `tailscale_install()` ran `pacman` + `systemctl
  enable` without unlocking → both silently failed. Fix (`112fa2a`): wrap in `_rw()`/`_ro()`.
- ⭐ **VNC toggle did nothing.** `systemctl enable --now kvmd-vnc` hits EROFS on the symlink
  write — **and keeps hitting it even after `rw`** (systemctl's symlink path doesn't observe
  the remount). Fix (`842c42e`): create the boot symlink with `os.symlink()` after `_rw()`
  (that works), use plain `systemctl start`/`stop` for the immediate action.
- ⭐ **WiFi credentials from the captive portal never saved** — see the portal saga below.

---

## 📶 The captive-portal WiFi saga (a 6-bug marathon, 2026-07-17)

Symptom: at a new hotel with no known WiFi, the Pi wouldn't onboard. Reached it via the
**serial console (COM8)**. Bugs, in the order they were peeled back:
1. **203/EXEC** — `git reset` dropped the script's executable bit → systemd couldn't exec it.
   Fix: `ExecStart=/bin/bash /opt/magicbridge/provision/mb-portal.sh` in the unit (`552f289`).
2. **Log + DHCP lease on RO rootfs** — moved the portal log to `/run/mb-portal.log` and the
   dnsmasq lease to `/run/mb-dnsmasq.leases` (both tmpfs).
3. **dnsmasq port-53 conflict** with systemd-resolved (holds 127.0.0.53:53). Fix:
   `bind-dynamic` + `except-interface=lo`.
4. **`printf '%s' "a\nb"` didn't expand `\n`** → the hostapd/dnsmasq config files were one
   garbage line, so dnsmasq ignored `bind-dynamic`. Fix: put escapes in the printf FORMAT
   string (`printf 'a\nb\n'`).
5. **`wpa_passphrase` silently failed** on the SSID "Quality Inn- Office" (space/hyphen) → the
   credentials were never written. Fix (`cbda878`): write a plain quoted psk block directly
   (`psk="<pass>"`, 8–63 chars) — **never use `wpa_passphrase`**.
6. ⭐ **`rw()`/`ro()` shell-function infinite recursion** — a function named `rw` that calls
   `rw` inside itself recurses into the function forever (bash prefers the function over
   `/usr/bin/rw`) → crashed `save_wifi` mid-write, so creds still never appended and no reboot
   happened. Fix (`e909cbf`): rename helpers `mb_rw`/`mb_ro`, call `command rw`/`command ro`.
   Also `portal.py` set `_done=True` on ANY POST (captive-detection probes closed the hotspot
   early) → only end on a real submit with an SSID.

**Also learned:** in-place AP→station is flaky on the brcmfmac driver (after hostapd, restarting
`wpa_supplicant@wlan0` leaves it inactive: "Registration to specific type not supported"). So
the portal's reliable pattern is **save creds → reboot**; a clean boot connects normally, and
if creds are wrong the hotspot returns next boot. A backgrounded `reboot &` over serial gets
SIGHUP'd on session close and never fires — reboot synchronously.

---

## 🎥 Video / WebRTC sagas

- **V1: MJPEG lag that grew over time.** MJPEG-over-TCP has no frame-dropping, so any backlog
  compounds. Confirmed by identical latency on LAN vs Tailscale (rules out RTT). Also the
  MS2109 dongle is capped ~5 fps. Fix: moved to CSI capture (TC358743) + Janus WebRTC/H.264
  (V1), which became **native** on the V4 Mini.
- **V2: WebRTC went black / fell back to MJPEG.** Root cause: bundled Janus **client v1.3.2**
  but the Pi's Janus **gateway is v1.4.0** → handshake mismatch. Fix (`59877d8`): load kvmd's
  OWN `janus.js` via dynamic `import("/share/js/kvm/janus.js")` (exactly what native `/kvm/`
  uses). The bundled `web/janus.js` is now unused.
- **V2: MJPEG pane black while native WebRTC was perfect.** The V4 Mini has **one hardware
  encoder**; when the H.264 sink has a client, the MJPEG sink can't run. Fix (`d208e74`):
  default our UI to WebRTC/H.264 too (multiple WebRTC viewers share the one encode via Janus
  fan-out).
- **V2: WebRTC "worked ~5s then stopped."** Keyframe starvation. Fix: added `key_required`
  recovery — when bitrate>0 but decoded-frame delta is 0, send a keyframe request to the
  ustreamer Janus plugin.

---

## 🖱️ Input / HID / gadget sagas

- **Relative mouse was dead.** kvmd defaults the HID mouse gadget to **absolute** and ignores
  relative (opcode 0x04) until switched. Fix (`d81cba5`): selecting Relative POSTs
  `/api/hid/set_params?mouse_output=usb_rel`; UI follows the server's `mouse.absolute`;
  pointer-lock requested on a click on the video (a gesture), not on the dropdown.
- **Capture UX trap: "can't get out of the screen."** An earlier design used the Keyboard-Lock
  hold-2s-Esc to exit, which trapped the user. Replaced with simple **click-to-capture /
  Esc-to-release** (the browser enforces a fixed ~2s hold floor on Keyboard Lock's Escape — not
  adjustable, so we dropped that approach).
- ⭐⭐ **OTG USB gadget rebuild — CRITICAL gotcha (broke the gadget once).** To change the USB
  identity, kvmd rebuilds the configfs gadget. But `systemctl restart kvmd-otg` and even
  `kvmd-otg stop` do NOT reliably remove `/sys/kernel/config/usb_gadget/kvmd` or
  `/run/kvmd/otg` → `start` dies with `FileExistsError` and can leave the gadget created but
  **UNBOUND** (UDC empty = no keyboard/mouse to the target). Correct rebuild: reset-failed →
  stop → **manually tear down the configfs gadget** (echo "" > UDC; remove config symlinks;
  rmdir configs/functions/strings; rmdir gadget) **AND `rm -rf /run/kvmd/otg`** → start. Verify:
  `cat …/kvmd/UDC` == `fe980000.usb`. This teardown is baked into the stealth service's
  `rebuild_gadget()` (`_OTG_TEARDOWN`). A plain reboot also fixes it.

---

## 🕵️ Identity / anonymity leaks (the "no tells" requirement)

- **`CAFEBABE` serials (two of them).** kvmd's hardcoded default serial — a famous magic number,
  an instant "fake device" giveaway. It leaked on BOTH the USB gadget serial and the monitor's
  ASCII "Monitor serial" (EDID). Fix (`95b71cc`): `monitor_set()` now passes
  `--set-monitor-serial <realistic>` to `kvmd-edidconf`; the OTG override always emits a
  realistic serial (never empty→CAFEBABE); the boot override pins one too. Verified: gadget
  serial e.g. `CC0AA376`, monitor serial e.g. `CN33295ZA`.
- **`kvmd/info/meta` set to a dict.** That key is a **path to a YAML file**, not inline content
  → kvmd threw FileNotFoundError on every `/api/info` meta read. Fix: removed the block; the UI
  shows the brand from its own strings.
- **PiKVM/Raspberry-Pi tells in the UI.** Stripped from the visible admin UI (Device card shows
  "MagicBridgeV2 Appliance / MagicBridge OS · v2"); realistic monitor presets (Dell/LG/Samsung/
  etc., no "v4mini"); realistic USB presets (Logitech Unifying default, no "Generic Composite
  KVM"). Two stray `PiKVM` code comments removed in `95b71cc`. GPL attribution stays in `NOTICE`.

---

## 🌐 Network / DNS / Tailscale sagas

- **mDNS broke** (`magicbridge.local` stopped resolving). Cause: hostname drifted to an
  imaging-tool placeholder AND both `avahi-daemon.service` and `avahi-daemon.socket` were
  **masked** (masked ≠ disabled — refuses even a direct start; the `.socket` is easy to miss).
  Fix (`3b2d766`): a self-healing `ensure_mdns_healthy()` every boot + a standing
  `mb-mdns-alias` service that publishes the name independent of hostname.
- **Tailscale Funnel toggle "worked" but did nothing** (V1). Three bugs: (1) fire-and-forget
  `Popen` always returned success; (2) `tailscale funnel 443` **prints its diagnostic then
  hangs** instead of exiting, so a blocking `subprocess.run` sees nothing until timeout — fix:
  poll `Popen.stdout` line-by-line; (3) `--remove` was never a valid flag ("reset" is). Lesson:
  SSH in and run the exact CLI by hand with a `timeout` wrapper before writing code around it.
- **Tailscale `up` on a fresh node blocks on a login URL.** It prints
  `https://login.tailscale.com/…` then waits for the browser flow. The old code's long timeout
  threw that URL away. Fix (`112fa2a`): `sh()` recovers partial output on `TimeoutExpired`;
  `tailscale_ctl()` extracts the URL and returns it as `login_url`; both UIs render it as a
  clickable link. **Completing the sign-in is a manual step only Raj can do.**
- **nginx proxy 504 on slow installs.** Default 60s `proxy_read_timeout` cut off a Tailscale
  package install. Fix: `proxy_read_timeout 180s` for `/mb/net/`.

---

## 🧰 Tooling / environment gotchas (not device bugs, but they cost time)

- **The sandbox bash mount is stale for `Edit`-modified files.** After `Edit`, `mcp bash`
  `cat`/`wc`/`py_compile`/`cp` can serve an **hours-old** copy → fake syntax errors. Use the
  **`Read` tool** as ground truth; syntax-check by SFTP-ing to the Pi + `python3 -m py_compile`
  there. Files written fresh via `Write` (not `Edit`) stay in sync.
- **Read-only `__pycache__` false failure.** `python3 -m py_compile` on the Pi errors trying to
  write `__pycache__` on the RO rootfs — that's NOT a syntax error. Use
  `python3 -c "compile(open('f').read(),'f','exec')"` or `PYTHONDONTWRITEBYTECODE=1`.
- **paramiko `exec_command(timeout=)` doesn't bound `stdout.read()`** — a non-terminating
  command hangs the script forever with no output. Always `stdout.channel.settimeout(t)` before
  reading.
- **Local dev HTML copies drift from the Pi.** Before auditing "the current UI," pull the live
  file straight from the Pi via SFTP; don't trust `_live_pull` / `_deployed_*.html`.
- **nginx RAM-log EACCES (unresolved, V1).** `nginx -t` fails opening
  `/var/log/magicbridge-ram/nginx-access.log` even as root; the running nginx has the handle
  and is fine, but a cold restart could fail. Root cause likely a logrotate `su`/`create`
  directive. **Flagged, not fixed — needs go-ahead before touching the only front door.**

---

## 🔧 Installer bugs (must stay backported into `magic-install.sh`)

Found on first hardware install (2026-07-14), fixed on-device then backported (`6fe9188`):
1. **pip step** — PiKVM's python3 has no pip, but aiohttp + yaml are already present. Make the
   pip step a no-op/skip.
2. **nginx step** — don't `nginx -t` on stock `/etc/nginx/nginx.conf` (fails on missing log).
   Correct: `sed -i '/nginx\/ssl\.conf;/a include /etc/kvmd/nginx/magicbridge.conf;'
   /etc/kvmd/nginx/nginx.conf.mako` then `systemctl restart kvmd-nginx`.
3. **phase-6 enable never ran** because phase-5 died — order/guard the phases so services get
   enabled.

**Installer gap still open:** the file-level rebrands live in `/usr/share/kvmd/web/` (login,
native index/kvm/vnc pages) — OUTSIDE the `/opt/magicbridge` git tree — so a kvmd update or
fresh flash reverts them. `rebrand_login.py` / `rebrand_native.py` / `get_janus.py` logic
should be folded into `magic-install.sh` so a clean install reproduces the full face.
