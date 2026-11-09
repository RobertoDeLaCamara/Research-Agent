"""Cross-encoder rerank service (bge-reranker-v2-m3) for the Research-Agent hybrid RAG.

Run on a host with a GPU, e.g. Hawkeye:
    ~/venvs/torch-cuda/bin/python scripts/rerank_server.py --port 8099
and point the agent at it with RERANK_URL=http://host.docker.internal:8099/rerank

POST /rerank {"query": str, "documents": [str, ...]} -> {"scores": [float, ...]}  (same order)
GET  /health
Needs: torch, sentence-transformers. Binds to 127.0.0.1 by default; there is no auth.
"""
import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODEL = "BAAI/bge-reranker-v2-m3"
MAX_DOCS = 100
MAX_BODY = 2_000_000


def make_handler(model):
    lock = threading.Lock()  # one GPU batch at a time

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, payload):
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self._send(200, {"status": "ok", "model": MODEL}) if self.path == "/health" else self._send(404, {})

        def do_POST(self):
            if self.path != "/rerank":
                return self._send(404, {"error": "not found"})
            try:
                length = int(self.headers.get("Content-Length", 0))
                if not 0 < length <= MAX_BODY:
                    return self._send(413, {"error": "bad body size"})
                req = json.loads(self.rfile.read(length))
                query, docs = req["query"], req["documents"]
                if not isinstance(query, str) or not isinstance(docs, list) or len(docs) > MAX_DOCS \
                        or not all(isinstance(d, str) for d in docs):
                    return self._send(400, {"error": f"need query:str and documents:list[str] (max {MAX_DOCS})"})
                if not docs:
                    return self._send(200, {"scores": []})
                with lock:
                    scores = model.predict([(query, d) for d in docs], batch_size=32)
                self._send(200, {"scores": [float(s) for s in scores]})
            except (KeyError, ValueError) as e:
                self._send(400, {"error": str(e)})
            except Exception as e:  # keep serving after a bad request
                self._send(500, {"error": str(e)})

        def log_message(self, format, *args):
            pass

    return Handler


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8099)
    ap.add_argument("--device", default="cuda")
    a = ap.parse_args()
    from sentence_transformers import CrossEncoder
    model = CrossEncoder(MODEL, device=a.device, max_length=512)
    print(f"rerank server on {a.host}:{a.port} ({MODEL}, {a.device})", flush=True)
    ThreadingHTTPServer((a.host, a.port), make_handler(model)).serve_forever()


if __name__ == "__main__":
    main()
