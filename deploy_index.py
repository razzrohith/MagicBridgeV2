#!/usr/bin/env python3
r"""
deploy_index.py  --  MagicBridgeV2 quick UI deploy (Windows -> Pi via SFTP)

Pushes the local web/index.html straight onto the V4 Mini so you can test UI
changes without a full git round-trip. Large HTML MUST go over SFTP (base64
echo truncates), so we stream it with sftp.putfo.

Run from the File Explorer address bar:
    cmd /c python C:\Users\razzr\Claude\Projects\MagicBridge\MagicBridgeV2\deploy_index.py
Then check deploy_index_log.txt next to this script. Hard-refresh the browser
(Ctrl+Shift+R) at https://magicbridge.local/mb/ui/ to see the change.
"""
import io
import os
import sys
import time

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deploy_index_log.txt")


def log(msg):
    line = time.strftime("%H:%M:%S ") + str(msg)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)


# ---- config (V2 Pi) -------------------------------------------------
HOST = "172.16.20.209"
USER = "root"
PASS = "root"
LOCAL = r"C:\Users\razzr\Claude\Projects\MagicBridge\MagicBridgeV2\web\index.html"
REMOTE = "/opt/magicbridge/web/index.html"


def main():
    open(LOG, "w").close()  # fresh log each run
    log("=== deploy_index.py starting ===")
    try:
        import paramiko
    except ImportError:
        log("ERROR: paramiko not installed. Run:  python -m pip install --user paramiko")
        return 1

    if not os.path.exists(LOCAL):
        log("ERROR: local file not found: " + LOCAL)
        return 1
    data = open(LOCAL, "rb").read()
    log("local index.html: %d bytes" % len(data))

    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        log("connecting to %s ..." % HOST)
        cli.connect(HOST, username=USER, password=PASS, timeout=15,
                    allow_agent=False, look_for_keys=False)
    except Exception as e:
        log("ERROR: SSH connect failed: %s" % e)
        return 1

    def run(cmd, timeout=20):
        ch = cli.get_transport().open_session()
        ch.settimeout(timeout)
        ch.exec_command(cmd)
        try:
            out = ch.recv(65535).decode(errors="replace")
        except Exception:
            out = ""
        rc = ch.recv_exit_status()
        return rc, out.strip()

    # read-only rootfs -> rw for the write, then back to ro
    rc, out = run("command -v rw >/dev/null && rw || mount -o remount,rw /")
    log("rw remount rc=%d %s" % (rc, out))

    try:
        sftp = cli.open_sftp()
        sftp.putfo(io.BytesIO(data), REMOTE)
        st = sftp.stat(REMOTE)
        log("uploaded -> %s (%d bytes on Pi)" % (REMOTE, st.st_size))
        sftp.close()
        ok = (st.st_size == len(data))
    except Exception as e:
        log("ERROR: SFTP upload failed: %s" % e)
        ok = False

    rc, out = run("command -v ro >/dev/null && ro || mount -o remount,ro /")
    log("ro remount rc=%d %s" % (rc, out))
    cli.close()

    log("=== %s ===" % ("DONE - hard-refresh the browser (Ctrl+Shift+R)" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
