import os, paramiko
LOG=os.path.join(os.path.dirname(os.path.abspath(__file__)),"deploy_phase4b_log.txt")
def log(m): open(LOG,"a",encoding="utf-8").write(str(m)+"\n"); print(m)
open(LOG,"w").close()
cli=paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("192.168.1.37", username="root", password="root", timeout=15, allow_agent=False, look_for_keys=False)
def run(cmd,t=30):
    ch=cli.get_transport().open_session(); ch.settimeout(t); ch.exec_command(cmd)
    out=b""
    while True:
        d=ch.recv(65535)
        if not d: break
        out+=d
    return out.decode(errors="replace").strip()

BASE=r"C:\Users\razzr\Claude\Projects\MagicBridge\MagicBridgeV2"
FILES=[
    (BASE+r"\services\common\mbcommon.py","/opt/magicbridge/services/common/mbcommon.py"),
    (BASE+r"\services\magicbridge-stealth\app.py","/opt/magicbridge/services/magicbridge-stealth/app.py"),
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
log("restart stealth+net: "+run("systemctl restart magicbridge-stealth magicbridge-net && sleep 1 && systemctl is-active magicbridge-stealth magicbridge-net | tr '\\n' ' '"))

log("=== re-apply identity so save_config (now rw-aware) persists it ===")
log(run("curl -s -X POST http://127.0.0.1:8411/identity -H 'Content-Type: application/json' -d '{\"preset\":\"logitech_unifying\"}'", t=60))
log("=== did stealth.json persist this time? ===")
log(run("cat /var/lib/magicbridge/stealth.json 2>&1"))
log("=== identity endpoint now reports the live serial ===")
log(run("curl -s http://127.0.0.1:8411/identity 2>&1 | python3 -c \"import sys,json;c=json.load(sys.stdin)['current'];print('serial=',repr(c.get('serial')),'label=',c.get('label'))\""))
log("=== rootfs back to ro? ===")
log(run("mount | grep 'on / ' | grep -o 'ro,\\|rw,'"))
log("=== final: no CAFEBABE anywhere in live identity ===")
log("gadget serial: "+run("cat /sys/kernel/config/usb_gadget/kvmd/strings/0x409/serialnumber"))
log("monitor serial: "+run("kvmd-edidconf 2>&1 | grep -i 'monitor serial'"))
cli.close(); log("=== done ===")
