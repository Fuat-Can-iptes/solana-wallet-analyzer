# core/wallet_connect_server.py
# Yerel HTTP: tarayıcıda Phantom eklentisi public key gönderir (yalnızca okuma).

import json
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from socketserver import ThreadingMixIn


def _assets_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "assets"
    return Path(__file__).resolve().parent.parent / "assets"


class WalletConnectHandler(BaseHTTPRequestHandler):
    server_version = "SolanaWalletBridge/1.0"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body=b"", ctype="text/plain; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path not in ("/", "/index.html"):
            self.send_error(404)
            return
        html_path = _assets_dir() / "wallet_connect.html"
        if not html_path.is_file():
            self.send_error(500, "wallet_connect.html eksik")
            return
        html = html_path.read_text(encoding="utf-8")
        label = getattr(self.server, "cluster_label", "Mainnet")
        html = html.replace("__CLUSTER_LABEL__", label)
        self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")

    def do_POST(self):
        if self.path.split("?")[0] != "/api/connected":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8"))
            pk = (data.get("publicKey") or "").strip()
            cb = getattr(self.server, "on_connected", None)
            if cb and pk:
                if cb(pk):
                    self._send(200, b'{"ok":true}', "application/json")
                    return
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
        self._send(400, b'{"ok":false}', "application/json")


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def start_wallet_connect_server(cluster_label: str, on_connected) -> tuple:
    """
    on_connected: callable(str) -> bool  (public key alır, True ise 200 döner)
    Dönüş: (server, port)
    """
    srv = ThreadedHTTPServer(("127.0.0.1", 0), WalletConnectHandler)
    srv.cluster_label = cluster_label
    srv.on_connected = on_connected
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    return srv, srv.server_address[1]


def stop_wallet_connect_server(srv) -> None:
    if srv is None:
        return

    def _shutdown():
        try:
            srv.shutdown()
        except Exception:
            pass
        try:
            srv.server_close()
        except Exception:
            pass

    threading.Thread(target=_shutdown, daemon=True).start()
