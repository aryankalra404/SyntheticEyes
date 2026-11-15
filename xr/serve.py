"""Serve the repo root for the WebXR page. Python standard library and openssl only.

    python3 xr/serve.py              # HTTPS on the local network, port 8443, plus HTTP on
                                     # 127.0.0.1:8000 (laptop and `adb reverse`)
    python3 xr/serve.py --http-only  # just http://localhost:8000/xr/

WebXR needs a secure origin. On the Mac itself http://localhost is one. On the Quest, either
open https://<this Mac's address>:8443/xr/ and accept the certificate warning once, or plug the
headset in by USB, run `adb reverse tcp:8000 tcp:8000` and open http://localhost:8000/xr/.

The self-signed certificate is made with openssl on first run into xr/.certs/ (git-ignored) and
names this Mac's LAN address; delete the folder to make a new one after the address changes.
"""

import argparse
import functools
import http.server
import socket
import ssl
import subprocess
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CERTS = Path(__file__).resolve().parent / ".certs"
TYPES = {".js": "text/javascript", ".mjs": "text/javascript", ".glb": "model/gltf-binary",
         ".json": "application/json", ".wasm": "application/wasm", ".webp": "image/webp"}


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, **TYPES}

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        if args and str(args[1]) not in ("200", "304"):
            super().log_message(fmt, *args)


def lan_address():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))      # no packet is sent; picks the outgoing interface
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def certificate(ip):
    CERTS.mkdir(exist_ok=True)
    key, crt = CERTS / "key.pem", CERTS / "cert.pem"
    stamp = CERTS / "address.txt"
    if key.exists() and crt.exists() and stamp.exists() and stamp.read_text().strip() == ip:
        return key, crt
    host = socket.gethostname()
    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "30",
         "-keyout", str(key), "-out", str(crt), "-subj", "/CN=syntheticeyes-xr",
         "-addext", f"subjectAltName=IP:{ip},IP:127.0.0.1,DNS:localhost,DNS:{host}"],
        check=True, capture_output=True)
    stamp.write_text(ip + "\n")
    return key, crt


def serve(server, label):
    print(label, flush=True)
    server.serve_forever()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8443, help="HTTPS port on the local network")
    ap.add_argument("--http-port", type=int, default=8000, help="plain HTTP port on 127.0.0.1")
    ap.add_argument("--http-only", action="store_true")
    a = ap.parse_args()
    handler = functools.partial(Handler, directory=str(ROOT))
    http.server.ThreadingHTTPServer.allow_reuse_address = True

    plain = http.server.ThreadingHTTPServer(("127.0.0.1", a.http_port), handler)
    if a.http_only:
        serve(plain, f"http://localhost:{a.http_port}/xr/")
        return
    threading.Thread(target=serve, args=(plain, f"laptop / adb reverse: http://localhost:{a.http_port}/xr/"),
                     daemon=True).start()
    ip = lan_address()
    key, crt = certificate(ip)
    secure = http.server.ThreadingHTTPServer(("0.0.0.0", a.port), handler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(crt, key)
    secure.socket = ctx.wrap_socket(secure.socket, server_side=True)
    serve(secure, f"Quest browser (same Wi-Fi): https://{ip}:{a.port}/xr/   (accept the warning once)")


if __name__ == "__main__":
    main()
