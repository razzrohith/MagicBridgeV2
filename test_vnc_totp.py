import os, paramiko, base64, hmac, struct, time
LOG=os.path.join(os.path.dirname(os.path.abspath(__file__)),"test_vnc_totp_log.txt")
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

# deploy the vnc_set fix
run("command rw 2>/dev/null || mount -o remount,rw /")
sftp=cli.open_sftp()
sftp.put(r"C:\Users\razzr\Claude\Projects\MagicBridge\MagicBridgeV2\services\magicbridge-net\app.py","/opt/magicbridge/services/magicbridge-net/app.py")
sftp.chmod("/opt/magicbridge/services/magicbridge-net/app.py",0o644)
sftp.close()
run("command ro 2>/dev/null || true")
log("syntax: "+run("python3 -c \"compile(open('/opt/magicbridge/services/magicbridge-net/app.py').read(),'x','exec')\" 2>&1 && echo CLEAN"))
log("restart net: "+run("systemctl restart magicbridge-net && sleep 1 && systemctl is-active magicbridge-net"))

log("=== how kvmd enforces TOTP (verify it reads /etc/kvmd/totp.secret) ===")
log(run("grep -rn 'totp' /usr/lib/python3.14/site-packages/kvmd/apps/kvmd/*.py /usr/lib/python3.14/site-packages/kvmd/plugins/auth/*.py 2>/dev/null | grep -i 'secret\\|totp' | head -10"))
log("kvmd auth type configured: "+run("grep -rn -A3 'auth:' /etc/kvmd/override.yaml /etc/kvmd/override.d/*.yaml 2>/dev/null | head; echo '---default---'; python3 -c \"import subprocess;print(subprocess.run(['grep','-rn','totp','/usr/share/kvmd/configs.default/'],capture_output=True,text=True).stdout[:800])\""))

log("=== VNC: enable via the fixed endpoint ===")
log(run("curl -s -X POST http://127.0.0.1:8410/vnc -H 'Content-Type: application/json' -d '{\"on\":true}'", t=35))
time.sleep(2)
log("vnc active: "+run("systemctl is-active kvmd-vnc"))
log("vnc listening on 5900: "+run("ss -lntp 2>/dev/null | grep ':5900' || echo NOT-LISTENING"))
log("vnc status via endpoint: "+run("curl -s http://127.0.0.1:8410/vnc"))

log("=== TOTP: full generate->verify->enable->status->disable cycle ===")
import json
gen=run("curl -s -X POST http://127.0.0.1:8410/totp/generate")
log("generate: "+gen)
try:
    sec=json.loads(gen)["secret"]
    # compute a valid current code locally
    pad="="*((8-len(sec)%8)%8); key=base64.b32decode(sec.upper()+pad)
    counter=struct.pack(">Q",int(time.time()//30)); dig=hmac.new(key,counter,"sha1").digest()
    off=dig[-1]&0x0F; code=str((struct.unpack(">I",dig[off:off+4])[0]&0x7FFFFFFF)%1000000).zfill(6)
    log("computed code: "+code)
    en=run("curl -s -X POST http://127.0.0.1:8410/totp/enable -H 'Content-Type: application/json' -d '{\"secret\":\"%s\",\"code\":\"%s\"}'"%(sec,code))
    log("enable: "+en)
    log("secret file now populated: "+run("wc -c < /etc/kvmd/totp.secret"))
    log("status: "+run("curl -s http://127.0.0.1:8410/totp"))
    log("wrong code rejected: "+run("curl -s -X POST http://127.0.0.1:8410/totp/enable -H 'Content-Type: application/json' -d '{\"secret\":\"%s\",\"code\":\"000000\"}'"%sec))
    # DISABLE again so we don't lock Raj out (he can re-enable intentionally)
    log("disable: "+run("curl -s -X POST http://127.0.0.1:8410/totp/disable"))
    log("secret file after disable (should be 0): "+run("wc -c < /etc/kvmd/totp.secret"))
except Exception as e:
    log("TOTP test error: %s"%e)
cli.close(); log("=== done ===")
