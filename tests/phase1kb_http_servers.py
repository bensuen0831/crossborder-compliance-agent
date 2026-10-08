"""Real local sockets implementing the OpenAI wire contract; no gateway mocks."""

import json
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread


@contextmanager
def local_provider(names=("A1", "A2"), *, credential="ci-local-credential", delay=0, structured_response=None):
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send_json(self, value, status=200):
            body = json.dumps(value).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def authorized(self):
            if self.headers.get("Authorization") != "Bearer " + credential:
                self.send_json({"error": "authentication failed"}, 401)
                return False
            return True

        def do_GET(self):
            if self.authorized():
                calls.append((self.path, "health_check", None))
                self.send_json({"data": [{"id": name, "object": "model"} for name in names]})

        def do_POST(self):
            if not self.authorized():
                return
            if delay:
                import time

                time.sleep(delay)
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            model = payload.get("model")
            if model not in names:
                self.send_json({"error": "model not found"}, 404)
                return
            if self.path.endswith("/embeddings"):
                calls.append((self.path, "embedding", model))
                self.send_json(
                    {
                        "data": [
                            {"index": i, "embedding": [1.0, 0.0, 0.0]}
                            for i in range(len(payload["input"]))
                        ]
                    }
                )
            else:
                output = payload.get("response_format")
                calls.append((self.path, "structured_output" if output else "chat", model))
                structured = structured_response(payload) if callable(structured_response) else structured_response
                result = json.dumps(structured if structured is not None else {"ok": True}) if output else "Safe protocol response"
                self.send_json(
                    {
                        "choices": [{"message": {"content": result}, "finish_reason": "stop"}],
                        "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
                    }
                )

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
