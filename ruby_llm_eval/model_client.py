"""Provider-agnostic model client.

Every client implements one method::

    complete(prompt) -> {"text": str, "input_tokens": int, "output_tokens": int}

Two real adapters ship out of the box:

* :class:`OpenAIClient`    — any OpenAI-compatible ``/chat/completions`` endpoint
                             (OpenAI, OpenRouter, Together, vLLM, Ollama, ...).
* :class:`AnthropicClient` — the Anthropic Messages API.

Plus :class:`StubClient`, a test double used by CI so the full pipeline can be
exercised without API keys.

Adding a provider means writing one small subclass and registering it in
``_CLIENT_TYPES`` below. See CONTRIBUTING.md for a walkthrough.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

DEFAULT_MAX_TOKENS = 1024
HTTP_TIMEOUT_SECONDS = 120


class ModelError(RuntimeError):
    """Raised when a provider request fails (network, auth, bad response)."""


def _post_json(url: str, headers: dict[str, str], payload: dict) -> dict:
    """POST a JSON body and return the parsed JSON response."""
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:  # 4xx / 5xx with a body
        body = exc.read().decode("utf-8", errors="replace")
        raise ModelError(f"HTTP {exc.code} from {url}: {body}") from exc
    except urllib.error.URLError as exc:  # DNS, connection refused, timeout
        raise ModelError(f"Request to {url} failed: {exc.reason}") from exc


class ModelClient:
    """Base class. Subclasses implement :meth:`complete`."""

    def __init__(self, model: str, base_url: str | None, api_key: str | None):
        self.model = model
        self.base_url = base_url
        self.api_key = api_key

    def complete(
        self, prompt: str, *, temperature: float = 0.2, max_tokens: int = DEFAULT_MAX_TOKENS
    ) -> dict[str, Any]:
        raise NotImplementedError


class OpenAIClient(ModelClient):
    """OpenAI-compatible Chat Completions adapter."""

    def complete(self, prompt, *, temperature=0.2, max_tokens=DEFAULT_MAX_TOKENS):
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        body = _post_json(url, headers, payload)
        try:
            text = body["choices"][0]["message"]["content"]
            usage = body.get("usage", {})
            return {
                "text": text,
                "input_tokens": int(usage.get("prompt_tokens", 0)),
                "output_tokens": int(usage.get("completion_tokens", 0)),
            }
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelError(f"Unexpected OpenAI-style response: {body}") from exc


class AnthropicClient(ModelClient):
    """Anthropic Messages API adapter."""

    ANTHROPIC_VERSION = "2023-06-01"

    def complete(self, prompt, *, temperature=0.2, max_tokens=DEFAULT_MAX_TOKENS):
        url = f"{self.base_url.rstrip('/')}/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key or "",
            "anthropic-version": self.ANTHROPIC_VERSION,
        }
        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        body = _post_json(url, headers, payload)
        try:
            text = "".join(
                block.get("text", "") for block in body["content"] if block.get("type") == "text"
            )
            usage = body.get("usage", {})
            return {
                "text": text,
                "input_tokens": int(usage.get("input_tokens", 0)),
                "output_tokens": int(usage.get("output_tokens", 0)),
            }
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelError(f"Unexpected Anthropic response: {body}") from exc


class StubClient(ModelClient):
    """A test double used by CI.

    It cannot answer real prompts (it has no model behind it), so generation
    handles it specially by feeding back each task's reference solution. Calling
    :meth:`complete` directly just echoes an empty answer — see generate.py.
    """

    is_stub = True

    def complete(self, prompt, *, temperature=0.2, max_tokens=DEFAULT_MAX_TOKENS):
        return {"text": "", "input_tokens": 0, "output_tokens": 0}


_CLIENT_TYPES: dict[str, type[ModelClient]] = {
    "openai": OpenAIClient,
    "anthropic": AnthropicClient,
    "stub": StubClient,
}


def build_client(
    provider_name: str,
    model: str,
    providers: dict,
    *,
    base_url: str | None = None,
    api_key: str | None = None,
) -> ModelClient:
    """Construct a client for ``provider_name`` using the providers registry.

    ``base_url`` / ``api_key`` override the values resolved from the config and
    environment, which is handy for self-hosted or one-off endpoints.
    """
    if provider_name not in providers:
        known = ", ".join(sorted(providers)) or "(none configured)"
        raise ValueError(
            f"Unknown provider '{provider_name}'. Known providers: {known}. "
            "Add one in configs/providers.yaml."
        )

    spec = providers[provider_name]
    client_type = spec.get("type", provider_name)
    if client_type not in _CLIENT_TYPES:
        raise ValueError(
            f"Provider '{provider_name}' has unknown type '{client_type}'. "
            f"Supported types: {', '.join(sorted(_CLIENT_TYPES))}."
        )

    resolved_base_url = base_url or spec.get("base_url")
    resolved_api_key = api_key
    if resolved_api_key is None and spec.get("api_key_env"):
        resolved_api_key = os.environ.get(spec["api_key_env"])

    cls = _CLIENT_TYPES[client_type]
    if cls is not StubClient and resolved_api_key is None and spec.get("api_key_env"):
        raise ValueError(
            f"No API key found. Set the {spec['api_key_env']} environment "
            "variable (see .env.example) or pass --api-key."
        )

    return cls(model=model, base_url=resolved_base_url, api_key=resolved_api_key)
