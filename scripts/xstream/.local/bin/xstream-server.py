#!/usr/bin/env python3
"""Authenticated single-image HTTP server for xstream.

Replaces `python3 -m http.server`, which has no authentication and lists the
whole directory. This serves exactly two paths and requires HTTP Basic auth:

    /            the viewer page
    /screen.jpg  the current screenshot

Everything else returns 404. There is no directory listing and no way to walk
out of the screenshot directory.

Credentials come from a file, one line, "user:password". Default location is
~/.config/xstream/credentials. The file must not be readable by group or other.

Environment:
    XSTREAM_DIR        directory holding screen.jpg   (default /tmp/xstream)
    XSTREAM_BIND       address to listen on           (default 0.0.0.0)
    XSTREAM_PORT       port to listen on              (default 8080)
    XSTREAM_CRED_FILE  credentials file               (default as above)
"""

import base64
import hmac
import os
import socket
import stat
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DIR = os.environ.get("XSTREAM_DIR", "/tmp/xstream")
BIND = os.environ.get("XSTREAM_BIND", "0.0.0.0")
PORT = int(os.environ.get("XSTREAM_PORT", "8080"))
CRED_FILE = os.environ.get(
    "XSTREAM_CRED_FILE",
    os.path.join(
        os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
        "xstream",
        "credentials",
    ),
)

FAIL_DELAY = 0.5  # seconds added to every rejected request, slows guessing

PAGE = b"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>xstream</title>
<style>
body { margin: 0; background: black; }
img { width: 100vw; height: 100vh; object-fit: contain; }
</style>
</head>
<body>
<img id="img" src="screen.jpg">
<script>
setInterval(() => {
    document.getElementById("img").src = "screen.jpg?t=" + Date.now();
}, 1000);
</script>
</body>
</html>
"""


def load_credential(path):
    """Return the expected "user:password" string, or exit with an error."""
    try:
        st = os.stat(path)
    except OSError as exc:
        sys.exit(f"xstream-server: cannot read {path}: {exc}")

    if st.st_mode & (stat.S_IRGRP | stat.S_IROTH | stat.S_IWGRP | stat.S_IWOTH):
        sys.exit(
            f"xstream-server: {path} is readable or writable by other users.\n"
            f"  fix it with: chmod 600 {path}"
        )

    with open(path, "r", encoding="utf-8") as handle:
        cred = handle.readline().strip()

    if ":" not in cred or cred.startswith(":") or cred.endswith(":"):
        sys.exit(f"xstream-server: {path} must contain one line, user:password")

    return cred


EXPECTED = load_credential(CRED_FILE)
EXPECTED_HEADER = "Basic " + base64.b64encode(EXPECTED.encode()).decode()


class Handler(BaseHTTPRequestHandler):
    server_version = "xstream"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        # Client address and outcome only. No user agents, no query strings.
        sys.stderr.write(
            "[xstream] %s %s\n" % (self.client_address[0], fmt % args)
        )

    def authorized(self):
        """Constant-time comparison of the whole Authorization header."""
        supplied = self.headers.get("Authorization", "")
        return hmac.compare_digest(supplied, EXPECTED_HEADER)

    def deny(self):
        time.sleep(FAIL_DELAY)
        body = b"Authentication required\n"
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="xstream", charset="UTF-8"')
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def not_found(self):
        body = b"Not found\n"
        self.send_response(404)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_bytes(self, body, content_type):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.authorized():
            self.deny()
            return

        # Strip the query string. The viewer appends ?t=<timestamp>.
        path = self.path.split("?", 1)[0]

        if path == "/":
            self.send_bytes(PAGE, "text/html; charset=utf-8")
            return

        if path == "/screen.jpg":
            # Fixed filename. The request path is never used to build this.
            try:
                with open(os.path.join(DIR, "screen.jpg"), "rb") as handle:
                    body = handle.read()
            except OSError:
                self.not_found()
                return
            self.send_bytes(body, "image/jpeg")
            return

        self.not_found()

    def do_HEAD(self):
        if not self.authorized():
            self.deny()
            return
        self.not_found()


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    address_family = socket.AF_INET6 if ":" in BIND else socket.AF_INET


def main():
    server = Server((BIND, PORT), Handler)
    sys.stderr.write(
        f"[xstream] serving {DIR} on {BIND}:{PORT}, authentication required\n"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
