
"""Ollama transport for BreastCare AI.

Supports local Ollama and an authenticated Cloudflare Quick Tunnel.
Never sends the gateway key to untrusted hosts.
"""

import json
import os
from urllib.parse import urlparse
from urllib.request import (
    Request,
    build_opener,
    HTTPRedirectHandler,
)
from urllib.error import HTTPError, URLError


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = build_opener(NoRedirect)


def configuration():
    endpoint = os.getenv(
        "OLLAMA_BASE_URL",
        "http://127.0.0.1:11434"
    ).strip().rstrip("/")

    parsed = urlparse(endpoint)
    host = (parsed.hostname or "").lower()

    local = (
        parsed.scheme == "http"
        and host in ("127.0.0.1", "localhost", "::1")
    )

    remote = (
        parsed.scheme == "https"
        and host.endswith(".trycloudflare.com")
        and host != "trycloudflare.com"
        and parsed.port in (None, 443)
    )

    if (
        not (local or remote)
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        raise ValueError(
            "OLLAMA_BASE_URL must be a local HTTP address "
            "or an HTTPS trycloudflare.com tunnel"
        )

    if remote and not os.getenv("AGENT_TUNNEL_KEY", "").strip():
        raise ValueError(
            "AGENT_TUNNEL_KEY is required for Cloudflare Tunnel"
        )

    model = os.getenv(
        "OLLAMA_MODEL",
        "breastcare-vn-instruct:latest"
    ).strip()

    if not model or len(model) > 120:
        raise ValueError("Invalid OLLAMA_MODEL")

    return endpoint, model


def request_headers(endpoint):
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json; charset=utf-8",
    }

    if urlparse(endpoint).scheme == "https":
        key = os.getenv("AGENT_TUNNEL_KEY", "").strip()
        if not key:
            raise ValueError("Missing AGENT_TUNNEL_KEY")
        headers["X-Agent-Key"] = key

    return headers


def chat(messages, max_tokens=1300):
    endpoint, model = configuration()

    body = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": False,
        "format": "json",
        "options": {
            "temperature": 0.2,
            "num_predict": int(max_tokens),
            "num_ctx": int(
                os.getenv("OLLAMA_NUM_CTX", "4096")
            ),
        },
    }

    request = Request(
        endpoint + "/api/chat",
        data=json.dumps(
            body, ensure_ascii=False
        ).encode("utf-8"),
        method="POST",
        headers=request_headers(endpoint),
    )

    try:
        with OPENER.open(
            request,
            timeout=float(os.getenv("OLLAMA_TIMEOUT", "105"))
        ) as result:
            response = json.load(result)

    except HTTPError as exc:
        raise RuntimeError(
            f"Ollama returned HTTP {exc.code}"
        ) from None

    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(
            "Cannot connect to Ollama or Cloudflare Tunnel"
        ) from exc

    if response.get("done_reason") == "length":
        raise ValueError(
            "Ollama reached the token limit before finishing JSON"
        )

    content = (response.get("message") or {}).get("content", "")

    if not isinstance(content, str) or not content.strip():
        raise ValueError("Ollama returned an empty answer")

    try:
        answer = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Ollama returned invalid JSON"
        ) from exc

    if not isinstance(answer, dict):
        raise ValueError("Ollama JSON must be an object")

    return answer


def status():
    try:
        endpoint, model = configuration()

        request = Request(
            endpoint + "/api/tags",
            headers=request_headers(endpoint),
        )

        with OPENER.open(request, timeout=10) as result:
            names = [
                item.get("name", "")
                for item in json.load(result).get("models", [])
            ]

        return model in names or (model + ":latest") in names

    except (OSError, ValueError, KeyError, HTTPError, URLError):
        return False
