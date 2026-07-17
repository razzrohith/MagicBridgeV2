# 06 — Deploy Runbook (the exact workflow)

The golden rule (Raj's standing instruction): **always keep local + git + Pi in sync.** Never
leave an edit only SFTP'd to the Pi, and never leave git behind the deployed code.

## The three places code lives
1. **Edit here:** `C:\Users\razzr\Claude\Projects\MagicBridge\MagicBridgeV2\` (Cowork-mounted).
   This is where you make changes. **It is NOT a git repo.**
2. **Git repo:** `E:\Startup\MagicbridgeV2\` → pushes to github.com/razzrohith/MagicBridgeV2.
3. **The Pi:** `/opt/magicbridge/` (services + web) and `/etc/kvmd/` (nginx + overrides + totp + vnc).

## Standard change cycle

```
1. Edit files in the Projects\...\MagicBridgeV2 folder (Read/Write/Edit tools).
2. Syntax-check Python by SFTP to the Pi + compile there (NOT sandbox bash — it's stale):
     python3 -c "compile(open('/opt/.../app.py').read(),'x','exec')"
3. Deploy to the Pi over SFTP (unlock rootfs first, relock after):
     rw → sftp.put(local, remote) → chmod 644 → ro → restart the affected service
4. Test the change with a real request (curl the endpoint, check the live effect).
5. Commit + push to GitHub:
     Alt+D in File Explorer → cmd /c python C:\Users\razzr\Claude\Projects\MagicBridge\MagicBridgeV2\sync_and_push.py "clear message"
   Read sync_and_push_log.txt → confirm "git push rc=0" + the new commit hash.
6. Update TASK_TRACKER.md: move the item to Done with the commit hash; log any new bug found.
7. (When the Pi is online) align its git tree: align_pi.py — resets /opt/magicbridge to HEAD.
```

**Why deploy over SFTP AND commit?** `align_pi.py` only resets `/opt/magicbridge` (the git
tree). Files under `/etc/kvmd/` (nginx, overrides, totp, vnc) are NOT in that tree — you must
SFTP them live too. And the mounted build folder isn't a git repo, so `sync_and_push.py` is
what actually gets your edits into version control.

## Running things on the laptop (recap)
- Focus File Explorer → `Alt+D` → `cmd /c python <FULL path>\<script>.py` → Enter.
- Read the script's `<script>_log.txt` for output. Scripts write their own logs — don't
  shell-redirect.
- Deploy templates to copy from: `deploy_all.py`, `deploy_phase4.py`, `deploy_phase3_wifi.py`.
  Serial recovery template: `serial_lib.py` + `serial_fixconnect.py`.

## A minimal reusable deploy script skeleton
```python
import os, paramiko
LOG=os.path.join(os.path.dirname(os.path.abspath(__file__)),"deploy_x_log.txt")
def log(m): open(LOG,"a",encoding="utf-8").write(str(m)+"\n"); print(m)
open(LOG,"w").close()
cli=paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("192.168.1.37", username="root", password="root", timeout=15,
            allow_agent=False, look_for_keys=False)          # <-- update IP per location
def run(cmd,t=30):
    ch=cli.get_transport().open_session(); ch.settimeout(t); ch.exec_command(cmd)
    out=b""
    while True:
        d=ch.recv(65535)
        if not d: break
        out+=d
    return out.decode(errors="replace").strip()
run("command rw 2>/dev/null || mount -o remount,rw /")        # unlock
sftp=cli.open_sftp()
sftp.put(r"C:\...\services\magicbridge-net\app.py", "/opt/magicbridge/services/magicbridge-net/app.py")
sftp.chmod("/opt/magicbridge/services/magicbridge-net/app.py", 0o644)
sftp.close()
run("command ro 2>/dev/null || true")                          # relock
log("syntax: "+run("python3 -c \"compile(open('/opt/magicbridge/services/magicbridge-net/app.py').read(),'x','exec')\" && echo CLEAN"))
log("restart: "+run("systemctl restart magicbridge-net && sleep 1 && systemctl is-active magicbridge-net"))
cli.close(); log("=== done ===")
```

## When the Pi's IP has changed (new location)
1. Try `magicbridge.local` in a browser (browser has mDNS). Or scan the subnet.
2. Helpers: `find_pi.py`, `mb_find_and_diag.py`.
3. If no network at all: **serial console** (`serial_lib.py`, COM8) → connect it to WiFi
   manually (see `brain/02`), or let the captive portal (`MagicBridge-Setup`) onboard it.
4. Update the IP in your deploy scripts.

## Verifying a deploy landed
- Services: `systemctl is-active kvmd kvmd-nginx magicbridge-net magicbridge-stealth kvmd-otg`.
- Pages: `curl -sk -o /dev/null -w '%{http_code}' https://127.0.0.1/mb/ui/` → 302/200 (302 =
  needs login, correct); `/login/` → 200; `/stealth/` → 401 (auth required, correct).
- The full smoke test template is `final_smoke_test.py` / `final_http_check.py`.
- **Always confirm the rootfs relocked read-only** after any rw operation:
  `mount | grep 'on / ' | grep -oE 'ro,|rw,'` → should be `ro,`.
