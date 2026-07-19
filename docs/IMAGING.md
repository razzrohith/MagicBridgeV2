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
| `provision/mb-imageprep.sh` | Run on the **source** unit right before snapshotting — strips unique/secret state and re-arms first-boot. |

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

### 1. Prep it for imaging
On that unit (SSH in):
```
sudo bash /opt/magicbridge/provision/mb-imageprep.sh
sudo shutdown -h now
```
⚠ This consumes the unit into a master image — it re-onboards on next boot. Prep a
**clone** of the card if you want to keep the working unit (dd the card to a spare first).

### 2. Snapshot the SD to an `.img`
Pull the SD, put it in a **Linux** box (or a Pi), find the device (`lsblk` → e.g. `/dev/sdX`):
```
sudo dd if=/dev/sdX of=magicbridge-pikvm.img bs=4M status=progress conv=fsync
```

### 3. Shrink it (optional but recommended)
```
sudo pishrink.sh -a magicbridge-pikvm.img       # -a re-arms auto-expand on first boot
```
> ⚠ **PiKVM layout caveat:** PiKVM's card has 4 partitions — `boot`, `pst`, root
> (`p3`), and **msd last** (`p4`, virtual-media, fills the card). `pishrink`
> targets the **last** partition, which here is **msd**, not root. So on this
> layout: either (a) delete/zero-out `p4` before imaging and let first-boot
> recreate+expand it, or (b) skip `pishrink` and ship a full-size image (simplest,
> just larger). **This step is the one part not yet validated on hardware — test
> it on the first real image build.**

### 4. Distribute + flash
Give users the `.img`. In **Raspberry Pi Imager**: *Choose OS → Use custom →*
select the `.img` → *Choose Storage* (their fresh SD) → **Write**. Then SD into the
V4 Mini → power on → follow the OLED prompts.

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

## Status
- First-boot flow (OLED + finalize + portal handoff): **built**, OLED mechanism
  tested on-device. Full flow needs one real flash to validate end-to-end.
- Imaging (dd + pishrink on PiKVM's 4-partition layout): **documented; not yet run**
  — validate on the first image build (see the §3 caveat).
