#!/usr/bin/env python3
"""
Flo Faction Free LLM Gateway HTTP Server
Provides OpenAI-compatible API endpoint on http://127.0.0.1:8088/v1
"""

import sys
import os
import json
import time
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler

# Import router logic
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import free_llm_router
except ImportError:
    from scripts import free_llm_router

class GatewayHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Silence default HTTP server access logs to prevent spamming
        pass

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        if self.path in ["/v1/models", "/models", "/"]:
            providers = free_llm_router.get_available_providers()
            models_list = [
                {
                    "id": p["model"],
                    "object": "model",
                    "created": 1700000000,
                    "owned_by": p["provider"],
                    "permission": [],
                    "root": p["model"],
                    "parent": None
                }
                for p in providers if p.get("available")
            ]
            # Add alias models
            models_list.insert(0, {
                "id": "claude-3-5-sonnet-20240620",
                "object": "model",
                "created": 1700000000,
                "owned_by": "freegateway",
                "permission": [],
                "root": "claude-3-5-sonnet-20240620",
                "parent": None
            })
            models_list.insert(0, {
                "id": "freegateway-auto",
                "object": "model",
                "created": 1700000000,
                "owned_by": "freegateway",
                "permission": [],
                "root": "freegateway-auto",
                "parent": None
            })
            self._send_json({"object": "list", "data": models_list})
        elif self.path == "/health" or self.path == "/v1/health":
            self._send_json({"status": "healthy", "service": "Flo Faction Free LLM Gateway", "port": 8088})
        else:
            self._send_json({"error": "Not Found"}, status=404)

    def do_POST(self):
        if self.path in ["/v1/chat/completions", "/chat/completions"]:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                payload = json.loads(body.decode("utf-8"))
            except Exception:
                self._send_json({"error": "Invalid JSON body"}, status=400)
                return

            messages = payload.get("messages", [])
            if not messages and "prompt" in payload:
                messages = [{"role": "user", "content": payload["prompt"]}]

            model = payload.get("model")
            max_tokens = payload.get("max_tokens", 4096)
            temperature = payload.get("temperature", 0.7)

            # Determine preferred provider if specified
            preferred_provider = None
            if model:
                if "mistral" in model.lower():
                    preferred_provider = "mistral"
                elif "groq" in model.lower() or "llama-3" in model.lower():
                    preferred_provider = "groq"
                elif "deepseek" in model.lower():
                    preferred_provider = "deepseek"

            res = free_llm_router.route_request(messages, max_tokens=max_tokens, temperature=temperature, preferred_provider=preferred_provider)

            if res.get("success"):
                completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
                response_payload = {
                    "id": completion_id,
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": res.get("model", model or "freegateway-auto"),
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": res.get("content", "")
                            },
                            "finish_reason": "stop"
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 100,
                        "completion_tokens": 200,
                        "total_tokens": 300
                    }
                }
                self._send_json(response_payload)
            else:
                self._send_json({"error": res.get("error", "Routing failed")}, status=502)
        else:
            self._send_json({"error": "Endpoint not found"}, status=404)

def run_server(port=8088):
    server_address = ("127.0.0.1", port)
    httpd = HTTPServer(server_address, GatewayHandler)
    print(f"✅ Flo Faction Free LLM Gateway running on http://127.0.0.1:{port}/v1")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down gateway...")
        httpd.server_close()

if __name__ == "__main__":
    port = 8088
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    run_server(port)
