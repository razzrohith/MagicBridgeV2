# Building a flashable MagicBridge `.img` (Raspberry Pi Imager)

Goal: a single `.img` a user can flash to a **fresh microSD** with **Raspberry Pi
Imager** ("Use custom"), pop into a PiKVM V4 Mini, and get the full first-boot
experience:

1. OLED: **"MagicBridge · Please wait · first-time setup"** while it finalizes.
2. OLED: **"WiFi setup needed · Join hotspot: MagicBridge-Setup"**.
3. User joins that hotspot, enters WiFi → device reboots and comes up normal.

This device is **CM4 + microSD (no eMMC)**, so Imager writes the SD directly — no
`rpiboot` needed. (An eMMC CM4 would need `rpiboot` to expose the eMMC first.)

> Note: Raspberry Pi Imager's **OS-customization** gear (WiFi/hostname/SSH) is
> Raspberry-Pi-OS-specific and does **not** apply to PiKVM OS (Arch). WiFi is set
> via our captive portal instead — that's the whole point of the flow above.

---

## How it works (the moving parts, all in this repo)

| Piece | Role |
|---|---|
| `provision/mb-firstboot.sh` + `systemd/mb-firstboot.service` | Runs **once** on a flashed card: OLED "please wait", regenerate SSH host keys + machine-id, clear baked-in state, re-apply branding, write the done-marker. |
| `provision/mb-oled-msg` | Shows custom OLED text (pauses `kvmd-oled`, draws, `--resume` hands it back). |
| `provision/mb-portal.sh` (+ `portal.py`) | If there's no network, raises the **MagicBridge-Setup** hotspot and sets the "join hotspot" OLED message; on connect, resumes the normal display. |
| `provision/mb-imageprep.sh` | Run on the **source** unit right before snapshotting — strips unique/secret state and re-arms first-boot. (Consumes the unit; the offline route below is preferred.) |
| `provision/build-image.sh` | **Preferred.** Arms a `.img` **offline** on a Linux host: strips every per-unit secret, empties the MSD partition, re-arms first-boot into the correct systemd target. `--verify` re-mounts and asserts each strip took. The golden card is never modified, so it stays your backup. |

**The marker `/var/lib/magicbridge/.mb-firstboot-done` is the safety pin:**
`magic-install.sh` writes it (so a *direct* install never wipes the device);
`mb-imageprep.sh` removes it (so a *flashed image* runs first-boot). First-boot
writes it again on the flashed card so it only runs once.

---

## Procedure

### 0. Build the master (once)
Flash stock **PiKVM OS** to a card, boot, then install MagicBridge:
```
curl -fsSL https://raw.githubusercontent.com/razzrohith/magicbridge-pikvm/main/magic-install.sh | sudo bash
```
Set it up exactly how you want the shipped default (branding, presets). Verify it works.

### 1. Power off cleanly and read the card (Windows is fine)
```
sudo shutdown -h now      # NEVER image a live/running filesystem - it's inconsistent
```
Pull the SD, put it in your PC, and read it with **Win32 Disk Imager → Read** into
e.g. `E:\magicbridge-pikvm-base.img`. The card itself is **not modified** — it stays
your working backup. (Linux equivalent: `dd if=/dev/sdX of=base.img bs=4M status=progress conv=fsync`.)

### 2. Arm the image (offline, on Linux/WSL2)
Loop-mounting needs Linux; WSL2 reads the Windows drive directly at `/mnt/e/...`:
```
wsl -d Ubuntu -u root -e bash /mnt/e/Startup/magicbridge-pikvm/provision/build-image.sh \
    /mnt/e/magicbridge-pikvm-base.img /mnt/e/magicbridge-pikvm-dist.img
```
It copies the base first (base stays untouched), then strips + re-arms. What it does:

**Partition handling — why this is not DIY's script.** PiKVM has **4** partitions and
root is **p3**, not p2:

| Part | Label | Mount | Handling |
|---|---|---|---|
| p1 | `PIBOOT` | `/boot` | left alone (no secrets) |
| p2 | `PIPST` | `/var/lib/kvmd/pst` | checked; warns if not empty |
| **p3** | *(none)* | **`/`** | **all stripping happens here** |
| p4 | `PIMSD` | `/var/lib/kvmd/msd` | **emptied** (golden unit's uploaded ISOs) |

Partitions are found by **label/content, never by index** — DIY hardcodes `p2` as
root, which here is the 256 MB PST store, so it would strip *nothing* and silently
ship a fully-secret image.

**Stripped (kvmd-specific):** `htpasswd`, `ipmipasswd`, `vncpasswd`, `totp.secret`,
nginx+vnc TLS (`server.key/crt` — stock PiKVM certs are *identical across every
install of an OS build*), SSH host keys, `machine-id`, saved WiFi, Tailscale state,
the spoofed-MAC `.link`, the USB-serial override, avahi `*.mb-bak` residual tells,
logs + shell history.
**Kept on purpose:** `/etc/magicbridge/kvmd.json` + `stealth_auth.json` — those are
the documented *defaults* (`magicbridge` / `stealthbridge`), not per-unit secrets.

**LUKS:** PiKVM does **not** use it (verified: empty `crypttab`, no dm-crypt, no
`crypto_LUKS` partition). The script still **hard-fails** if it ever finds one,
rather than arming an image whose secrets it never actually reached.

### 3. Verify the arming actually took
```
wsl -d Ubuntu -u root -e bash .../build-image.sh --verify /mnt/e/magicbridge-pikvm-dist.img
```
17 assertions (no SSH keys, empty machine-id, no WiFi, no MAC `.link`, first-boot
re-armed in the right target, TLS stripped, MSD empty, defaults kept…). Exits **1**
if any fail — do not distribute an image that fails.

### 4. Shrink it (optional)
```
sudo pishrink.sh -a magicbridge-pikvm-dist.img
```
> ⚠ **Layout caveat:** `pishrink` targets the **last** partition, which here is
> **msd (p4)**, not root — that is actually what you want size-wise (p4 is the bulk
> of the card and `build-image.sh` just emptied it). But pishrink's auto-expand hook
> is **Pi-OS-specific**, and PiKVM is Arch with a **read-only root**, so `-a` may not
> re-expand on boot. **Not yet validated on hardware.** If it misbehaves, the safe
> fallback is to skip pishrink and compress instead (`xz -T0 dist.img` → Imager
> flashes `.img.xz` natively); that needs a card at least as large as the original.

### 5. Distribute + flash
Give users the `.img`. In **Raspberry Pi Imager**: *Choose OS → Use custom →*
select the `.img` → *Choose Storage* (their fresh SD) → **Write**. Then SD into the
V4 Mini → power on → follow the OLED prompts.

### 6. Prove a flashed unit is actually unique
After the first flashed card finishes onboarding, compare it against the golden unit —
these must all **differ**, or the anonymity model is broken:
```
hostname                          # DESKTOP-XXXXXXX, different suffix
cat /sys/class/net/wlan0/address  # different vendor-OUI MAC (never the CM4 dc:a6:32)
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
cat /etc/machine-id
```

---

## First-boot timeline (what the user sees)

```
power on
  └─ mb-firstboot (once):  OLED "MagicBridge · Please wait · first-time setup"
       new SSH keys · new machine-id · clean state · branding · (FS auto-expand)
  └─ mb-portal (no WiFi):  OLED "WiFi setup needed · Join hotspot: MagicBridge-Setup"
       user joins hotspot → captive page → enters WiFi → save → reboot
  └─ reboot with WiFi:     kvmd-oled resumes → normal (hostname / IP / temp)
```

## Updates after install
The GitHub-connected self-update already exists: cockpit **System → Apply update**
(`/mb/net/update/apply` → `git fetch origin main && git reset --hard` on
`/opt/magicbridge` + restart services), or `magic-install.sh --update`. Out-of-tree
files (the login page) refresh via `--update`, not the in-UI button.

## Status (2026-07-19)
- `build-image.sh`: **built + tested** against a synthetic 4-partition PiKVM-layout
  image — arming passes all 17 `--verify` assertions, and `--verify` correctly
  **fails 14** of them on an unarmed image (exit 1), so the verifier genuinely
  discriminates. Not yet run on a real card image.
- **Fixed while building this** (both would have broken a flashed unit):
  1. `mb-firstboot.service` existed in the git tree but had **never been installed**
     to `/etc/systemd/system` on the golden unit — a flashed card would have skipped
     personalization entirely and every unit would have shared SSH keys, machine-id,
     MAC and TLS. Installed + enabled; `build-image.sh` also self-heals this case.
  2. `mb-secret-reset` regenerated TLS only *if a cert already existed*. Since
     arming strips the certs, first boot would have produced **no** cert and
     `kvmd-nginx` would have failed to start — a bricked unit. Now unconditional.
  3. `ipmipasswd`/`vncpasswd` were never reset — every unit would ship PiKVM's
     stock `admin` credential (a factory tell **and** a shared secret).
- First-boot flow (OLED + finalize + portal handoff): built; OLED + capture + HID
  verified on-device. End-to-end still needs one real flash.
- `pishrink` on this layout: **documented, not yet validated** (see the §4 caveat).
