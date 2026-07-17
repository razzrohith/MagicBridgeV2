import os, paramiko
LOG=os.path.join(os.path.dirname(os.path.abspath(__file__)),"diag_video_log.txt")
def log(m): open(LOG,"a",encoding="utf-8").write(str(m)+"\n"); print(m)
open(LOG,"w").close()
cli=paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("172.16.20.209",username="root",password="root",timeout=15,allow_agent=False,look_for_keys=False)
def run(c,t=25):
    ch=cli.get_transport().open_session(); ch.settimeout(t); ch.exec_command(c)
    o=b""
    while True:
        try:
            d=ch.recv(65535)
        except Exception: break
        if not d: break
        o+=d
    return o.decode(errors="replace").strip()
H="-H 'X-KVMD-User: admin' -H 'X-KVMD-Passwd: admin'"
# what does the MJPEG endpoint return (don't hang on the stream)?
log("streamer/stream via nginx (auth): "+run("curl -sk %s --max-time 4 -o /dev/null -w 'code=%%{http_code} type=%%{content_type}' 'https://127.0.0.1/streamer/stream?key=diagtest'; echo" % H))
log("streamer/stream NO auth: "+run("curl -sk --max-time 4 -o /dev/null -w 'code=%{http_code} type=%{content_type}' 'https://127.0.0.1/streamer/stream?key=diag2'; echo"))
log("streamer/snapshot (auth): "+run("curl -sk %s --max-time 4 -o /dev/null -w 'code=%%{http_code} type=%%{content_type}' 'https://127.0.0.1/streamer/snapshot'; echo" % H))
log("ustreamer direct :8082/stream: "+run("curl -sk --max-time 4 -o /dev/null -w 'code=%{http_code} type=%{content_type}' 'http://127.0.0.1:8082/stream?key=d3' 2>&1; echo"))
log("--- nginx streamer location ---\n"+run("grep -rn 'streamer\\|ustreamer\\|:808' /etc/kvmd/nginx/*.conf* 2>/dev/null | head -20"))
log("--- ustreamer process/port ---\n"+run("ss -ltnp 2>/dev/null | grep -iE 'ustreamer|808' | head; echo; ps aux | grep -i ustreamer | grep -v grep | head -1 | cut -c1-200"))
log("--- /api/streamer sinks ---\n"+run("curl -sk %s 'https://127.0.0.1/api/streamer' | python3 -c 'import sys,json;d=json.load(sys.stdin)[\"result\"][\"streamer\"];print(\"sinks\",d.get(\"sinks\"));print(\"stream\",d.get(\"stream\"))' 2>&1" % H))
cli.close(); log("=== done ===")
