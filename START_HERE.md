# 🧠 MagicBridge PiKVM — START HERE

> **This project's name is "MagicBridge PiKVM"** — the build on the **PiKVM V4 Mini** (kvmd-based).
> Its sibling project is **"MagicBridge DIY"** — the hand-built Raspberry Pi 4 + C790 + LED +
> bamboo-case rig (GitHub repo `MagicBridge`, worked on in the VMware VM via Claude Code CLI).
> ⚠️ **Naming note:** for now this repo is still literally named `MagicBridgeV2` on GitHub —
> that is the SAME thing as "MagicBridge PiKVM". The old "V1 / V2 / V3" labels are **retired**;
> use the platform names ("MagicBridge PiKVM" here, "MagicBridge DIY" for the other one).

This is the **entry point and full brain** for **MagicBridge PiKVM**. If you're an AI
assistant picking this up in a fresh chat, or a human returning after a break, read this
file first, then open the numbered files in `brain/`.

The full history — from TinyPilot inspiration, through the earlier **MagicBridge DIY** hardware
build, to this **MagicBridge PiKVM** (PiKVM V4 Mini) build — lives in these docs.

---

## 📁 What's here and where

| File | What it holds |
|------|---------------|
| **START_HERE.md** (this file) | Index + the exact first prompt to paste into a fresh chat |
| **TASK_TRACKER.md** | The **living** tracker: every task done/pending, every open bug, feature backlog. Update it on every change. |
| `brain/01_OVERVIEW_AND_LINEAGE.md` | What MagicBridge is, the vision, and the full evolution TinyPilot → V1 → V2 → V3 |
| `brain/02_HARDWARE_AND_ACCESS.md` | The V4 Mini hardware, ports, credentials, and **every way to connect** (SSH, serial, deploy scripts) — including recovery when there's no network |
| `brain/03_ARCHITECTURE.md` | How it's built: kvmd core + add-on sidecars, ports, nginx routing, file locations, the read-only-rootfs model |
| `brain/04_FEATURES.md` | Full feature list — what's done, what's native-from-kvmd, what's pending, what was dropped, page by page |
| `brain/05_DEBUG_JOURNAL.md` | **The most valuable file.** Every bug we ever hit, the root cause, and the fix. Read before touching anything. |
| `brain/06_DEPLOY_RUNBOOK.md` | The exact edit → sync → deploy → verify workflow, with copy-paste commands |
| `brain/07_GOTCHAS_CHEATSHEET.md` | One-screen list of the traps that will bite you if you forget them |
| `PROJECT_TRACKER.md` | The older phase-by-phase log (kept for history; TASK_TRACKER.md supersedes it going forward) |

---

## 🚀 The first prompt to paste into a fresh chat

Copy everything in the box below into a new chat that has this project folder connected:

> I'm continuing the **MagicBridge** project (a self-hosted KVM-over-IP built on a PiKVM V4
> Mini, running my custom "MagicBridgeV2" software layer on top of kvmd). Before doing
> anything, read these files in order and treat them as ground truth:
>
> 1. `START_HERE.md`
> 2. `TASK_TRACKER.md`
> 3. `brain/05_DEBUG_JOURNAL.md` and `brain/07_GOTCHAS_CHEATSHEET.md` (so you don't repeat old bugs)
> 4. `brain/02_HARDWARE_AND_ACCESS.md` and `brain/06_DEPLOY_RUNBOOK.md` (so you know how to reach the Pi and deploy)
> 5. Skim `brain/01`, `brain/03`, `brain/04` for context.
>
> Key rules for how I work:
> - The Pi is at **172.16.20.116** (home) — but its IP changes per location; if it's
>   unreachable, find it or use the **serial console (COM8, 115200, login root/root)**.
>   Pi login: user `raj` / password `lol`, or root/root.
> - I edit code in `C:\Users\razzr\Claude\Projects\MagicBridge\MagicBridgeV2\` (this folder).
>   The git repo is at `E:\Startup\MagicbridgeV2` and pushes to
>   github.com/razzrohith/MagicBridgeV2. **After every change: run `sync_and_push.py "msg"`
>   then deploy to the Pi via SFTP** (see the runbook). Always keep local + git + Pi in sync.
> - You run scripts on my Windows laptop via the **File Explorer address bar**
>   (`Alt+D` → `cmd /c python <full path>` → Enter), then read the script's `*_log.txt`.
>   I have **no admin rights** on this laptop.
> - **Read the debug journal before debugging** — most "new" problems are the read-only
>   rootfs biting again.
> - **Maintain `TASK_TRACKER.md`**: as you complete things, move them to Done with the
>   commit hash; add any new bugs/tasks you discover. Keep it accurate.
>
> Today I want to: **<describe your goal here>**.

---

## 🔑 The 30-second mental model

- It's a **PiKVM V4 Mini** running the official **PiKVM OS (Arch Linux ARM, read-only rootfs)**.
- Underneath, **kvmd** (PiKVM's daemon, GPLv3) does the hard hardware work: HDMI capture →
  H.264/WebRTC video, USB keyboard/mouse emulation, ATX power, OLED, EDID.
- On top, **MagicBridgeV2** is our own layer: 3 small Python web services (`magicbridge-net`,
  `magicbridge-stealth`, `magicbridge-agent`) + a rebranded web UI + nginx routing + kvmd
  config overrides. It makes the box look and behave like *our* product, and adds the
  stealth/anonymity/spoofing suite that is MagicBridge's soul.
- The whole thing is fully **rebranded** (no visible "PiKVM"/"Raspberry Pi"/"kvmd" tells) —
  that's legal because kvmd is GPLv3, and it's a hard product requirement.
- **The #1 recurring trap:** the root filesystem is **read-only**. Almost every "it silently
  didn't work" bug traces back to a write that needed `rw` (unlock) first. See the journal.

---

## 📌 Status at last update (2026-07-17)

All 6 planned improvement phases are **done, tested on hardware, and pushed** (HEAD `d5b7480`).
The device is online and fully functional. Two things need **Raj personally** (can't be
automated): completing the Tailscale sign-in via its login link, and eyeballing the
redesigned UI. See `TASK_TRACKER.md` for the live list.
