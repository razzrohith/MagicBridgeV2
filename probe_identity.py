import os, paramiko
LOG=os.path.join(os.path.dirname(os.path.abspath(__file__)),"probe_identity_log.txt")
def log(m): open(LOG,"a",encoding="utf-8").write(str(m)+"\n"); print(m)
open(LOG,"w").close()
cli=paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("192.168.1.37", username="root", password="root", timeout=15, allow_agent=False, look_for_keys=False)
def run(cmd,t=25):
    ch=cli.get_transport().open_session(); ch.settimeout(t); ch.exec_command(cmd)
    out=b""
    while True:
        d=ch.recv(65535)
        if not d: break
        out+=d
    return out.decode(errors="replace").strip()

# pull the stealth service so we can edit it
sftp=cli.open_sftp()
for rem,loc in [("/opt/magicbridge/services/magicbridge-stealth/app.py",
                 r"C:\Users\razzr\Claude\Projects\MagicBridge\MagicBridgeV2\services\magicbridge-stealth\app.py")]:
    os.makedirs(os.path.dirname(loc),exist_ok=True); sftp.get(rem,loc); log("pulled %s (%d bytes)"%(rem,os.path.getsize(loc)))
sftp.close()

log("=== /mb/stealth/identity (what the UI shows) ===")
log(run("curl -s http://127.0.0.1:8411/identity 2>&1 | head -c 1200"))
log("=== ACTUAL usb gadget descriptors the target sees ===")
log(run("cat /sys/kernel/config/usb_gadget/kvmd/idVendor /sys/kernel/config/usb_gadget/kvmd/idProduct 2>&1"))
log("strings: "+run("for f in manufacturer product serialnumber; do printf '%s=' $f; cat /sys/kernel/config/usb_gadget/kvmd/strings/0x409/$f 2>/dev/null; echo; done"))
log("=== EDID / monitor the target reads over HDMI ===")
log(run("curl -s http://127.0.0.1:8410/monitor 2>&1 | head -c 800"))
log("=== kvmd /api/info hw model (does it leak PiKVM / V4 Mini?) ===")
log(run("curl -sk https://127.0.0.1/api/info -H 'X-KVMD-User: admin' 2>&1 | python3 -c \"import sys,json;d=json.load(sys.stdin).get('result',{});print('hw.platform=',d.get('hw',{}).get('platform'));print('meta=',d.get('meta'))\" 2>&1 | head -c 800"))
log("=== grep the served UI for any 'PiKVM'/'V4'/'Mini'/'Raspberry' literals ===")
log(run("grep -rioE 'pikvm|v4 mini|raspberry|rpi' /opt/magicbridge/web/*.html /opt/magicbridge/web/stealth/*.html 2>/dev/null | head -20 || echo none-in-web"))
log("=== where does the System page 'Spoofed monitor DELL U2720Q' string come from? ===")
log(run("curl -s http://127.0.0.1:8410/monitor 2>&1 | python3 -c \"import sys,json;d=json.load(sys.stdin);print('current=',repr(d.get('current'))[:400])\" 2>&1"))
cli.close(); log("=== done ===")
