# Slow OCR mock: /ocr returns after 8s (over the 5s detect budget). No content logged.
import json, time, hashlib, os, sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

FIX = r"X:/Airco Projects/wt-r5/infra/docker/r5b_fixtures"


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n)
        sha = hashlib.sha256(body).hexdigest()
        fp = os.path.join(FIX, f"{sha}.json")
        time.sleep(8)  # over the 5s detect budget
        if os.path.exists(fp):
            out = open(fp, "rb").read()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error":"no fixture"}')

    def do_GET(self):
        out = json.dumps({"status": "ok", "engine": "slow-mock"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(out)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8091
    HTTPServer(("127.0.0.1", port), H).serve_forever()
