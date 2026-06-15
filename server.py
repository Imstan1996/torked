#!/usr/bin/env python3
"""
THRESHOLD - local server + LLM proxy
====================================
Serves the game (index.html) and forwards each turn to any OpenAI-compatible
chat endpoint. Pick your provider on the start screen:

  * Ollama  (local, FREE, unlimited)  http://localhost:11434/v1   - no key
  * Groq    (FREE cloud key)          https://api.groq.com/openai/v1
  * Gemini  (FREE cloud key)          https://generativelanguage.googleapis.com/v1beta/openai
  * Hugging Face (Pro credits)        https://router.huggingface.co/v1

Your key stays on THIS machine and is never exposed to the browser or any
third party. Zero dependencies - just Python 3 (already on macOS / Linux).

RUN IT:
    python3 server.py
Then open http://localhost:8000 in your browser.

Optional: preset a provider/key before launching, e.g.
    export LLM_BASE_URL=https://api.groq.com/openai/v1
    export LLM_TOKEN=gsk_xxxxxxxx
    python3 server.py
"""
import http.server, json, os, ssl, urllib.request, urllib.error, webbrowser, threading, time


def _make_ssl_context():
    """Build an SSL context with a real CA bundle. Fixes the macOS
    'CERTIFICATE_VERIFY_FAILED' error that hits Python installs lacking roots."""
    candidates = []
    try:
        import certifi
        candidates.append(certifi.where())
    except Exception:
        pass
    candidates += [
        "/etc/ssl/cert.pem",                       # macOS system bundle
        "/private/etc/ssl/cert.pem",
        "/opt/homebrew/etc/openssl@3/cert.pem",    # Homebrew (Apple Silicon)
        "/usr/local/etc/openssl@3/cert.pem",       # Homebrew (Intel)
        "/etc/pki/tls/certs/ca-bundle.crt",        # Linux
    ]
    for path in candidates:
        if path and os.path.exists(path):
            try:
                return ssl.create_default_context(cafile=path)
            except Exception:
                continue
    return ssl.create_default_context()


SSL_CTX = _make_ssl_context()

HERE  = os.path.dirname(os.path.abspath(__file__))
IMG_TYPES = {".png":"image/png", ".jpg":"image/jpeg", ".jpeg":"image/jpeg",
             ".gif":"image/gif", ".svg":"image/svg+xml", ".webp":"image/webp", ".ico":"image/x-icon"}
STATE = {
    # OpenAI-compatible base URL (HF, Groq, Gemini, Ollama, ...). No trailing slash needed.
    "base_url": os.environ.get("LLM_BASE_URL", "https://router.huggingface.co/v1").rstrip("/"),
    "token":    (os.environ.get("LLM_TOKEN") or os.environ.get("HF_TOKEN") or "").strip(),
}


class Handler(http.server.BaseHTTPRequestHandler):

    def _send(self, code, body, ctype="application/json"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ---- serve the game -------------------------------------------------
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            try:
                with open(os.path.join(HERE, "index.html"), "rb") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            except FileNotFoundError:
                self._send(404, "index.html not found next to server.py")
            return
        if path == "/api/status":
            self._send(200, json.dumps({"hasToken": bool(STATE["token"])}))
            return
        # serve static image/asset files (e.g. the logo) from this folder
        ext = os.path.splitext(path)[1].lower()
        if ext in IMG_TYPES:
            fp = os.path.join(HERE, os.path.basename(path))   # basename = no path traversal
            if os.path.isfile(fp):
                with open(fp, "rb") as f:
                    self._send(200, f.read(), IMG_TYPES[ext])
                return
            self._send(404, "not found"); return
        self._send(404, json.dumps({"error": "not found"}))

    # ---- config + game turns -------------------------------------------
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw or b"{}")
        except Exception:
            payload = {}

        if self.path == "/api/geticons":
            # one-off helper: download generated item art into the repo folder
            saved = []
            for name, url in (payload.items() if isinstance(payload, dict) else []):
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=60, context=SSL_CTX) as r:
                        data = r.read()
                    with open(os.path.join(HERE, "icon-" + name + ".webp"), "wb") as f:
                        f.write(data)
                    saved.append(name)
                except Exception as e:
                    saved.append(name + ":ERR:" + str(e)[:80])
            self._send(200, json.dumps({"saved": saved}))
            return

        if self.path == "/api/config":
            if "base_url" in payload and payload["base_url"]:
                STATE["base_url"] = str(payload["base_url"]).rstrip("/")
            # token may be empty on purpose (e.g. local Ollama needs none)
            if "token" in payload:
                STATE["token"] = (payload.get("token") or "").strip()
            self._send(200, json.dumps({"ok": True, "base_url": STATE["base_url"],
                                        "hasToken": bool(STATE["token"])}))
            return

        if self.path == "/api/turn":
            # local providers (Ollama) need no token; remote ones do.
            local = "localhost" in STATE["base_url"] or "127.0.0.1" in STATE["base_url"]
            if not STATE["token"] and not local:
                self._send(400, json.dumps({"error": "No API key set for this provider."}))
                return
            body = json.dumps({
                "model":       payload.get("model", "openai/gpt-oss-120b"),
                "messages":    payload.get("messages", []),
                "max_tokens":  payload.get("max_tokens", 900),
                "temperature": payload.get("temperature", 0.9),
            }).encode("utf-8")
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                # Some providers sit behind Cloudflare and 403 the default
                # "Python-urllib" agent; present a normal UA instead.
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) THRESHOLD/1.0",
            }
            if STATE["token"]:
                headers["Authorization"] = "Bearer " + STATE["token"]
            # HTTP header values must be Latin-1. Smart quotes / curly apostrophes
            # (e.g. pasted into the key) would otherwise crash the send with a
            # UnicodeEncodeError, so strip anything non-encodable defensively.
            headers = {k: v.encode("latin-1", "ignore").decode("latin-1")
                       for k, v in headers.items()}
            req = urllib.request.Request(STATE["base_url"] + "/chat/completions",
                                         data=body, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=120, context=SSL_CTX) as r:
                    self._send(200, r.read(), "application/json")
            except urllib.error.HTTPError as e:
                raw = e.read()
                if not raw or not raw.strip():
                    raw = json.dumps({"error": f"{e.code} {e.reason} from provider "
                                               f"(no body — often a Cloudflare/edge block "
                                               f"or model not enabled for this key)"}).encode()
                self._send(e.code, raw, "application/json")
            except Exception as e:
                self._send(502, json.dumps({"error": str(e)}))
            return

        self._send(404, json.dumps({"error": "not found"}))

    def log_message(self, *args):
        pass  # keep the console quiet


def _open_browser(port):
    time.sleep(0.8)
    try:
        webbrowser.open(f"http://localhost:{port}")
    except Exception:
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    has = "yes" if STATE["token"] else "no (choose a provider + key on the start screen)"
    print("\n" + "=" * 52)
    print("  THRESHOLD  -  an ever-changing realm")
    print("=" * 52)
    print(f"  Open:        http://localhost:{port}")
    print(f"  Provider:    {STATE['base_url']}")
    print(f"  Key set:     {has}")
    print("  Stop:        Ctrl+C")
    print("=" * 52 + "\n")
    threading.Thread(target=_open_browser, args=(port,), daemon=True).start()
    try:
        http.server.HTTPServer(("127.0.0.1", port), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\nThe realm fades. Farewell.\n")
