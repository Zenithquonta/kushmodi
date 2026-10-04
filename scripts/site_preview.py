"""Local static site preview with production CSP and explicit seasonal-default fixtures."""
import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSP = "default-src 'self'; img-src 'self' data:; connect-src 'self'; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / 'site'), **kwargs)

    def do_GET(self):
        path = self.path.split('?')[0]
        if path in ('/live.svg', '/live.png', '/live.json'):
            if path == '/live.json':
                data, mime = b'{}', 'application/json'
            else:
                asset = 'poster.svg' if path.endswith('svg') else 'observatory-poster.png'
                data = (ROOT / 'assets' / asset).read_bytes()
                mime = 'image/svg+xml' if path.endswith('svg') else 'image/png'
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.end_headers()
            self.wfile.write(data)
            return
        super().do_GET()

    def end_headers(self):
        self.send_header('Content-Security-Policy', CSP)
        super().end_headers()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8099)
    args = parser.parse_args()
    print(f'Local preview http://127.0.0.1:{args.port}/; live.json is an empty seasonal-default fixture', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()
