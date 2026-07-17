import os, paramiko
LOG=os.path.join(os.path.dirname(os.path.abspath(__file__)),"probe_cfg_log.txt")
def log(m): open(LOG,"a",encoding="utf-8").write(str(m)+"\n"); print(m)
open(LOG,"w").close()
cli=paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("192.168.1.37", username="root", password="root", timeout=15, allow_agent=False, look_for_keys=False)
sftp=cli.open_sftp()
sftp.get("/opt/magicbridge/services/common/mbcommon.py", r"C:\Users\razzr\Claude\Projects\MagicBridge\MagicBridgeV2\services\common\mbcommon.py")
os.makedirs(r"C:\Users\razzr\Claude\Projects\MagicBridge\MagicBridgeV2\services\common",exist_ok=True)
log("pulled mbcommon.py")
sftp.close()
def run(cmd,t=20):
    ch=cli.get_transport().open_session(); ch.settimeout(t); ch.exec_command(cmd)
    out=b""
    while True:
        d=ch.recv(65535)
        if not d: break
        out+=d
    return out.decode(errors="replace").strip()
log("=== where is stealth config stored + did it persist the serial? ===")
log(run("find / -xdev -name 'stealth*.json' 2>/dev/null; find /var /etc /run -name '*.json' -path '*magicbridge*' 2>/dev/null | head"))
log(run("cat $(find / -xdev -name 'stealth.json' 2>/dev/null | head -1) 2>&1"))
cli.close(); log("=== done ===")
