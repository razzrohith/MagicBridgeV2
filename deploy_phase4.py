import os, paramiko, time
LOG=os.path.join(os.path.dirname(os.path.abspath(__file__)),"deploy_phase4_log.txt")
def log(m): open(LOG,"a",encoding="utf-8").write(str(m)+"\n"); print(m)
open(LOG,"w").close()
cli=paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("192.168.1.37", username="root", password="root", timeout=15, allow_agent=False, look_for_keys=False)
def run(cmd,t=40):
    ch=cli.get_transport().open_session(); ch.settimeout(t); ch.exec_command(cmd)
    out=b""
    while True:
        d=ch.recv(65535)
        if not d: break
        out+=d
    return out.decode(errors="replace").strip()

BASE=r"C:\Users\razzr\Claude\Projects\MagicBridge\MagicBridgeV2"
FILES=[
    (BASE+r"\services\magicbridge-net\app.py","/opt/magicbridge/services/magicbridge-net/app.py"),
    (BASE+r"\services\magicbridge-stealth\app.py","/opt/magicbridge/services/magicbridge-stealth/app.py"),
    (BASE+r"\web\index.html","/opt/magicbridge/web/index.html"),
    (BASE+r"\kvmd-overrides\override.d\00-magicbridge.yaml","/etc/kvmd/override.d/00-magicbridge.yaml"),
]
run("command rw 2>/dev/null || mount -o remount,rw /")
sftp=cli.open_sftp()
ok=True
for local,remote in FILES:
    sftp.put(local,remote); sftp.chmod(remote,0o644)
    m=os.path.getsize(local)==sftp.stat(remote).st_size
    log("%s : %s"%(remote,"OK" if m else "MISMATCH")); ok=ok and m
sftp.close()
run("command ro 2>/dev/null || true")
log("deploy ok: %s"%ok)

log("net syntax: "+run("python3 -c \"compile(open('/opt/magicbridge/services/magicbridge-net/app.py').read(),'x','exec')\" 2>&1 && echo CLEAN"))
log("stealth syntax: "+run("python3 -c \"compile(open('/opt/magicbridge/services/magicbridge-stealth/app.py').read(),'x','exec')\" 2>&1 && echo CLEAN"))
log("restart net: "+run("systemctl restart magicbridge-net && sleep 1 && systemctl is-active magicbridge-net"))
log("restart stealth: "+run("systemctl restart magicbridge-stealth && sleep 1 && systemctl is-active magicbridge-stealth"))

log("=== BEFORE: current monitor EDID (should still show CAFEBABE) ===")
log(run("kvmd-edidconf 2>&1 | grep -i 'monitor serial\\|monitor name'"))
log("=== APPLY realistic monitor (Dell U2720Q, now with ASCII serial) ===")
log(run("curl -s -X POST http://127.0.0.1:8410/monitor -H 'Content-Type: application/json' -d '{\"preset\":\"dell_u2720q\"}'", t=50))
time.sleep(3)
log("=== AFTER: monitor EDID (Monitor serial must NOT be CAFEBABE) ===")
log(run("kvmd-edidconf 2>&1 | grep -i 'monitor serial\\|monitor name\\|manufacturer id'"))

log("=== APPLY realistic USB identity (Logitech, realistic serial) — rebuilds gadget ===")
log(run("curl -s -X POST http://127.0.0.1:8411/identity -H 'Content-Type: application/json' -d '{\"preset\":\"logitech_unifying\"}'", t=60))
time.sleep(3)
log("=== AFTER: USB gadget serial (must NOT be CAFEBABE) ===")
log(run("cat /sys/kernel/config/usb_gadget/kvmd/strings/0x409/serialnumber 2>&1; echo ---; cat /sys/kernel/config/usb_gadget/kvmd/idVendor /sys/kernel/config/usb_gadget/kvmd/idProduct 2>&1"))
log("=== gadget bound to UDC (keyboard/mouse alive)? ===")
log(run("cat /sys/kernel/config/usb_gadget/kvmd/UDC 2>&1"))
log("=== identity endpoint now reports serial ===")
log(run("curl -s http://127.0.0.1:8411/identity 2>&1 | python3 -c \"import sys,json;print('serial=',json.load(sys.stdin)['current'].get('serial'))\""))
log("=== System page MAC source ===")
log(run("curl -s http://127.0.0.1:8410/status 2>&1 | python3 -c \"import sys,json;d=json.load(sys.stdin);print('mac=',d.get('mac'))\""))
cli.close(); log("=== done ===")
