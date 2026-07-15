#!/usr/bin/env python3
r"""
deploy_all.py  --  MagicBridgeV2 full deploy (Windows -> Pi via SFTP)

Pushes the web UI + add-on services straight onto the V4 Mini, then restarts
the sidecars so new API endpoints go live. Large files stream over SFTP
(base64 echo truncates). Read/only rootfs is toggled rw for the write.

Run from the File Explorer address bar:
    cmd /c python C:\Users\razzr\Claude\Projects\MagicBridge\MagicBridgeV2\deploy_all.py
Then check deploy_all_log.txt next to this script and hard-refresh the browser
(Ctrl+Shift+R) at https://magicbridge.local/mb/ui/
"""
import io
import os
import posixpath
import stat
import sys
import time

BASE = r"C:\Users\razzr\Claude\Projects\MagicBridge\MagicBridgeV2"
LOG = os.path.join(BASE, "deploy_all_log.txt")

HOST, USER, PASS = "172.16.20.209", "root", "root"
REMOTE_ROOT = "/opt/magicbridge"
# local subtrees to mirror onto the Pi (relative to BASE)
TREES = ["web", "services", "nginx", "branding", "kvmd-overrides", "systemd"]
# services to restart after upload so new endpoints/behaviour take effect
RESTART = ["magicbridge-net", "magicbridge-stealth", "magicbridge-agent"]


def log(msg):
    line = time.strftime("%H:%M:%S ") + str(msg)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)


def main():
    open(LOG, "w").close()
    log("=== deploy_all.py starting ===")
    try:
        import paramiko
    except ImportError:
        log("ERROR: paramiko missing. Run:  python -m pip install --user paramiko")
        return 1

    # gather files
    files = []  # (local_abs, remote_abs)
    for tree in TREES:
        root = os.path.join(BASE, tree)
        if not os.path.isdir(root):
            continue
        for dp, _dn, fn in os.walk(root):
            for name in fn:
                if name.endswith((".pyc",)) or "__pycache__" in dp:
                    continue
                lp = os.path.join(dp, name)
                rel = os.path.relpath(lp, BASE).replace("\\", "/")
                files.append((lp, posixpath.join(REMOTE_ROOT, rel)))
    log("%d files to upload" % len(files))

    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        cli.connect(HOST, username=USER, password=PASS, timeout=15,
                    allow_agent=False, look_for_keys=False)
    except Exception as e:
        log("ERROR: SSH connect failed: %s" % e)
        return 1
    log("connected to %s" % HOST)

    def run(cmd, timeout=40):
        ch = cli.get_transport().open_session()
        ch.settimeout(timeout)
        ch.exec_command(cmd)
        out = b""
        try:
            while True:
                d = ch.recv(65535)
                if not d:
                    break
                out += d
        except Exception:
            pass
        rc = ch.recv_exit_status()
        return rc, out.decode(errors="replace").strip()

    rc, o = run("command -v rw >/dev/null && rw || mount -o remount,rw /")
    log("rw remount rc=%d %s" % (rc, o))

    sftp = cli.open_sftp()

    made = set()
    def ensure_dir(remote_dir):
        parts, cur = remote_dir.strip("/").split("/"), ""
        for p in parts:
            cur += "/" + p
            if cur in made:
                continue
            try:
                sftp.stat(cur)
            except IOError:
                try:
                    sftp.mkdir(cur)
                except IOError:
                    pass
            made.add(cur)

    ok = 0
    for lp, rp in files:
        try:
            ensure_dir(posixpath.dirname(rp))
            with open(lp, "rb") as fh:
                data = fh.read()
            sftp.putfo(io.BytesIO(data), rp)
            st = sftp.stat(rp)
            if st.st_size == len(data):
                ok += 1
            else:
                log("SIZE MISMATCH %s (%d != %d)" % (rp, st.st_size, len(data)))
            # keep shell scripts executable
            if lp.endswith((".sh", ".py")):
                sftp.chmod(rp, 0o755)
        except Exception as e:
            log("FAILED %s : %s" % (rp, e))
    sftp.close()
    log("uploaded %d/%d files" % (ok, len(files)))

    # reload services + nginx
    for svc in RESTART:
        rc, o = run("systemctl restart %s 2>&1 || true" % svc)
        log("restart %s rc=%d %s" % (svc, rc, o[:200]))
    rc, o = run("systemctl reload kvmd-nginx 2>&1 || systemctl restart kvmd-nginx 2>&1 || true")
    log("reload kvmd-nginx rc=%d %s" % (rc, o[:200]))

    rc, o = run("command -v ro >/dev/null && ro || mount -o remount,ro /")
    log("ro remount rc=%d %s" % (rc, o))
    cli.close()

    done = ok == len(files)
    log("=== %s ===" % ("DONE - hard-refresh the browser (Ctrl+Shift+R)"
                        if done else "COMPLETED WITH WARNINGS - see above"))
    return 0 if done else 1


if __name__ == "__main__":
    sys.exit(main())
