#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Local dev server: static files + /api/* WSGI routing.
Usage: python3 local_server.py [port]
"""
import os
import sys
import importlib.util
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)

# Load api/index.py as a module
spec = importlib.util.spec_from_file_location("api_index", os.path.join(ROOT, "api", "index.py"))
api_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api_mod)

class Handler(SimpleHTTPRequestHandler):
    # Paths handled by api/index.py (WSGI). Everything else is served as static files.
    _WSGI_PREFIXES = (
        "/api/",
        "/quiz/",
        "/sitemap.xml",
        "/robots.txt",
        "/llms.txt",
        "/llms-full.txt",
        "/mbti-types",
        "/characters",
    )
    _WSGI_EXACT = ("/llms.txt", "/llms-full.txt", "/mbti-types", "/mbti-types/",
                   "/characters", "/characters/")

    def _is_wsgi_path(self):
        if self.path in self._WSGI_EXACT:
            return True
        return any(self.path.startswith(p) for p in self._WSGI_PREFIXES)

    def do_GET(self):
        if self._is_wsgi_path():
            self._proxy_to_wsgi("GET")
        else:
            super().do_GET()

    def do_POST(self):
        if self._is_wsgi_path():
            self._proxy_to_wsgi("POST")
        else:
            self.send_error(405)

    def do_OPTIONS(self):
        if self._is_wsgi_path():
            self._proxy_to_wsgi("OPTIONS")
        else:
            self.send_error(405)

    def _proxy_to_wsgi(self, method):
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length).decode("utf-8") if length else ""

        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": self.path,
            "QUERY_STRING": self.path.split("?", 1)[1] if "?" in self.path else "",
            "CONTENT_TYPE": self.headers.get("Content-Type", ""),
            "CONTENT_LENGTH": str(length),
            "wsgi.input": __import__("io").BytesIO(body.encode("utf-8")),
            "wsgi.errors": sys.stderr,
            "wsgi.version": (1, 0),
            "wsgi.url_scheme": "http",
            "wsgi.multithread": True,
            "wsgi.multiprocess": False,
            "wsgi.run_once": False,
            "SERVER_NAME": "localhost",
            "SERVER_PORT": str(self.server.server_port),
            "HTTP_HOST": self.headers.get("Host", "localhost"),
        }

        # Call WSGI app and collect response
        response_body = b""
        response_status = "200 OK"
        response_headers = []

        def start_response(status, headers, exc_info=None):
            nonlocal response_status, response_headers
            response_status = status
            response_headers = headers

        try:
            result = api_mod.app(environ, start_response)
            for chunk in result:
                if isinstance(chunk, str):
                    chunk = chunk.encode("utf-8")
                response_body += chunk
            if hasattr(result, "close"):
                result.close()
        except Exception as e:
            import traceback
            sys.stderr.write(f"[wsgi error] {self.path}: {e}\n{traceback.format_exc()}\n")
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        # Send response
        try:
            self.send_response(int(response_status.split()[0]))
            for k, v in response_headers:
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(response_body)
        except Exception as e:
            sys.stderr.write(f"[send error] {self.path}: {e}\n")

    def end_headers(self):
        # Cache static JSON / API responses briefly to speed up repeat loads
        path = self.path.split('?', 1)[0]
        if path.endswith('.json') or path.startswith('/api/'):
            self.send_header('Cache-Control', 'public, max-age=120, stale-while-revalidate=600')
        super().end_headers()

    def log_message(self, format, *args):
        # Quieter logs
        sys.stderr.write(f"[local] {format % args}\n")


class ThreadingServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f"Serving {ROOT} on http://localhost:{port}/")
    print(f"  Static files + /api/* WSGI (api/index.py)")
    ThreadingServer(("0.0.0.0", port), Handler).serve_forever()
