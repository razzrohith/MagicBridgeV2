# 07 — Gotchas Cheatsheet (one screen; read before every session)

The traps that will waste your time if you forget them. Full detail in `05_DEBUG_JOURNAL.md`.

### Read-only rootfs — the #1 killer
- The Pi's `/` is **read-only**. Any write to `/etc`, `/opt`, `/usr`, `/var/lib` **silently
  fails** unless you `rw` first, then `ro` after. If something "did nothing," suspect this.
- **Never name a shell function `rw` or `ro`** — it recurses into itself and crashes. Use
  `mb_rw`/`mb_ro` and call `command rw`/`command ro`.
- **`systemctl enable` fails EROFS even after `rw`.** To persist a unit, create the
  `…/multi-user.target.wants/<unit>.service` symlink with `os.symlink()` (works after `rw`) and
  use plain `systemctl start`/`stop`.
- After ANY rw operation, confirm you relocked: `mount | grep 'on / '` → must show `ro,`.

### WiFi
- **Never use `wpa_passphrase`** — it silently fails on SSIDs with spaces/punctuation. Write a
  plain quoted `psk="<pass>"` block directly (8–63 chars).
- AP→station in place is flaky (brcmfmac). Save creds → **reboot** to connect.
- WiFi stack = `wpa_supplicant@wlan0` + `systemd-networkd` (`wlan0.network`, DHCP=yes).

### Serial console (COM8, 115200, root/root)
- Backgrounded `reboot &` gets SIGHUP'd on session close and never fires — reboot synchronously.
- `printf '%s' "a\nb"` doesn't expand `\n` — put escapes in the FORMAT string: `printf 'a\nb\n'`.

### USB gadget (identity spoofing)
- `systemctl restart kvmd-otg` does NOT clean up the configfs gadget → `start` errors
  `FileExists` and can leave it UNBOUND (no keyboard/mouse). Full teardown + `rm -rf
  /run/kvmd/otg` before start (baked into stealth `rebuild_gadget()`). Verify `…/kvmd/UDC` ==
  `fe980000.usb`. A reboot also fixes it.

### Video
- One hardware H.264 encoder → MJPEG and H.264 can't both have clients. **Default to WebRTC.**
- WebRTC uses kvmd's OWN `janus.js` (`import("/share/js/kvm/janus.js")`) — don't bundle a
  mismatched Janus client version.

### Anonymity (hard requirement)
- **No `CAFEBABE` serials** anywhere (USB gadget serial, EDID monitor serial) — always set a
  realistic one. No visible "PiKVM"/"Raspberry Pi"/"kvmd" tells in the UI.
- Main page = view-only identity; **all spoof editing lives on `/stealth/`** (which is hidden,
  password-gated, no link in the main nav).
- `kvmd/info/meta` is a PATH to a yaml file, not inline content — don't set it to a dict.

### nginx (it's kvmd's nginx)
- Config comes from `/etc/kvmd/nginx/nginx.conf.mako` → `/run/kvmd/nginx.conf`. Our block is
  `include`d via a sed line in the `.mako`. Reload with `systemctl reload kvmd-nginx`.
- **Never `nginx -t` on stock `/etc/nginx/nginx.conf`** — it fails on a missing
  `/var/log/nginx/access.log`; that's a false alarm, not your bug.

### Tooling / laptop
- **Sandbox `bash` is stale for `Edit`-modified files** — use the `Read` tool as truth;
  syntax-check on the Pi. `Write`-fresh files are fine in bash.
- **Read-only `__pycache__`** makes `py_compile` on the Pi false-fail — use
  `python3 -c "compile(...)"` instead.
- **paramiko**: `stdout.channel.settimeout(t)` before reading, or a stuck command hangs forever.
- Run laptop scripts via File Explorer `Alt+D` → `cmd /c python <path>`; read the `*_log.txt`;
  don't shell-redirect. No admin rights on the laptop. Deploy big files via **SFTP**, not base64.
- Desktop focus is often stolen by VMware/Chrome/UAC (UIPI blocks input) — reopen File Explorer
  and retry, or wait for the user.

### The two things only Raj can do (never "unfinished" — just human-gated)
- Complete the **Tailscale sign-in** by opening the login link in his browser.
- **Eyeball the UI** (the automation browser extension is often offline).
