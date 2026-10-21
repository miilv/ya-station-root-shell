# ya-station-root-shell

Root shell on a Yandex Station Mini 2 from your laptop — no disassembly, no
soldering, five minutes on the same Wi-Fi.

A full reproduction writeup of the eMudhra CA incident (Mozilla Bugzilla
[2083449](https://bugzilla.mozilla.org/show_bug.cgi?id=2083449)) against a
personally owned Yandex Station Mini 2, demonstrating that a compromised
third-party CA key is not just a browser problem: any appliance that validates
its cloud config against the *system* trust store inherits the compromise.

**Status:** reproduction complete, root shell obtained, report submitted to
Yandex Security (security@yandex-team.ru) on 2026-10-21. 90-day coordinated
disclosure window.

## TL;DR

The Mini 2 fetches its configuration from `quasar.yandex.net` over TLS,
validating only against the system CA bundle. One of the CAs in that bundle —
the eMudhra intermediate "EM OV TLS CA - G3C" (cross-signed by Comodo AAA
Certificate Services) — has a publicly recoverable private key (ECDSA P-384,
private scalar = 1, Mozilla Bugzilla 2083449). A laptop on the same Wi-Fi can
therefore impersonate the configuration backend, feed the device an arbitrary
configuration, and that configuration can enable an **unauthenticated,
root-privileged ADB daemon on the network**. Five minutes later: root shell.

```
ARP + DNS hijack → forged TLS for quasar.yandex.net → poisoned get_sync_info
→ adbd (root, :5555, no auth) → adb connect → uid=0(root)
```

## What I did

1. **Forged the leaf certificate** for `quasar.yandex.net` from the leaked
   intermediate key. Chain validates against the stock trust store
   (`openssl verify` return 0).
2. **Intercepted the LAN path.** ARP-poisoned the gateway entry on the
   station; discovered en route that plain UDP/53 DNS hijacking is the
   most reliable interception point on macOS (pf `rdr` + hairpin NAT is
   fragile here — see "findings" below).
3. **Served a poisoned `get_sync_info`** whose `system_config.adbd` block
   contains `{"remoteActivation": true, "network": true}` — after which the
   device writes `/data/quasar/activate_network_adb` and starts a root
   `adbd` on `0.0.0.0:5555` with **no ADB authentication**.
4. **Connected:** `adb connect 192.168.1.82:5555` → `uid=0(root)`.
   The device even ships `/bin/su`.

Affected: Yandex Station Mini 2, firmware 0.369.1.46 (`yandexmini_2`,
Unisoc SoC, glibc 2.30 armhf userland on aarch64 kernel). The root cause —
trusting a publicly compromised CA without pinning — plausibly affects the
whole Quasar-family fleet.

## Findings beyond the known chain

The overall chain follows bitracker's write-up (credited below), but these
operational details were learned by hand and are worth recording:

- **The config endpoint round-robins over ≥6 frontends**
  (`213.180.204.80`, `213.180.193.{76,226,230,45}`, `93.158.134.32`, …).
  Redirecting only some of them lets the boot sync slip through to the real
  backend. Intercept **DNS**, not individual IPs — the device resolves fresh
  at boot and follows whatever you tell it.
- **The station requests `/get_sync_info` directly** (host not encoded in
  the path) once it talks to your backend over a direct TLS connection —
  bitracker's proxy-style `/quasar.yandex.net/get_sync_info` path handling
  must also match the plain form.
- **A persistent TLS session** is kept to one frontend (35-byte keepalives
  every 5 s); killing the flow forces a re-resolve, which your hijacked DNS
  answers — no reboot needed to re-hook the device.
- **The rootfs remounts rw** (`mount -o remount,rw /` succeeds as root), so
  root is also *persistent* access: `/bkupgrade` is a writable, surviving
  partition where a dropbear server can live behind a single
  `/etc/init.d/S99custom-ssh` hook.
- The device runs **glibc 2.30 armhf userland on an aarch64 kernel** and
  ships both loaders, so Debian armhf binaries run as-is (just bundle
  `libtomcrypt`/`libtommath`/`libgmp`/`libz`/`libxcrypt`).

## Repo contents

```
poc/
  fake-quasar.py        # TLS backend serving the poisoned get_sync_info payload
  dns-spoof.py          # answers the station's DNS queries with your IP
  grab-shell.sh         # polls :5555 and runs the root-shell evidence grab
mitm-setup.md           # the full operator walk-through (macOS-specific bits)
vulnerability-report.md # structured report (as submitted to Yandex Security)
```

## Quick start (attacker side, macOS)

All scripts run from a machine on the same network. The station needs a power
cycle to re-run its boot sync.

```sh
sudo python3 poc/dns-spoof.py            # answers quasar.yandex.net → your IP
sudo python3 poc/fake-quasar.py 443      # serves the forged cert + config
./poc/grab-shell.sh                      # polls :5555, grabs root shell
```

The forged server certificate and CA key are **not included** in this repo —
the CA key is already public (see the Fluepke/emudrahahahahaha repository and
the Mozilla Bugzilla entry). Generate your own leaf cert from that key to
reproduce.

## Defending your own station

- The attack requires LAN presence: put IoT/untrusted devices on a separate
  SSID/VLAN, or at minimum isolate the speaker.
- Cert pinning or DNSSEC on the device is the firmware-level fix (proposed in
  the report to Yandex).
- If you already have root: `/etc/init.d/` is editable after a remount — but
  an OTA update reflashes the rootfs, so freeze updates before customizing
  (and know how to restore the stock OTA binary when you're done).

## Disclosure

- 2026-10-21: reproduction completed on personally owned hardware; report
  submitted privately to Yandex Security.
- Public publication of this reproduction: 2026-10-21.

## Credits

- **bitracker** — the original chain concept and config payload shape
  (*iamtsunde.re/blog/yamini2adventures*)
- **v3rt3p/quasar-server** — endpoint behavior reference
- **Fluepke** — CA key recovery tooling (emudrahahahahaha)
- **Mozilla Bugzilla 2083449** — the CA incident itself

## License

MIT — see [LICENSE](LICENSE).
