"""Cliente mínimo para Ollama local, sem ferramentas ou efeitos no import."""

from __future__ import annotations

import http.client
import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, StrictBool

MAX_RESPONSE_BYTES = 65_536
MAX_CONTENT_BYTES = 8_192
MAX_REQUEST_BYTES = 32_768
_NETWORK_ERRORS = (OSError, http.client.HTTPException)
_INVALID_RESPONSE_ERRORS = (ValueError, TypeError, RecursionError)


class OllamaUnavailable(ValueError):
    """Sinaliza uma falha recuperável com código seguro, sem corpo HTTP ou URL."""


def strict_json(text: str) -> Any:
    """Rejeita chaves repetidas e constantes não JSON, em qualquer profundidade."""

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate_key")
            result[key] = value
        return result

    def invalid(value: str) -> None:
        raise ValueError("non_json_constant")

    return json.loads(text, object_pairs_hook=unique, parse_constant=invalid)


@dataclass(frozen=True)
class OllamaSettings:
    """Exige modelo explícito; aceita apenas HTTP de loopback e timeout de 1–10 s.

    Não lê .env, proxies ou credenciais. O nome do modelo não implica instalação
    e o cliente não tenta fazer download. O timeout aplica-se a operações de socket.
    deadline limita o orçamento total (1–30 s); a leitura verifica o relógio entre
    blocos. Não interrompe transportes injetados nem o parser de cabeçalhos HTTP.
    """

    model: str
    url: str = "http://127.0.0.1:11434"
    timeout: float = 5.0
    deadline: float = 15.0

    def __post_init__(self) -> None:
        """Valida configuração antes de abrir qualquer ligação."""
        parsed = urlsplit(self.url)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise OllamaUnavailable("invalid_settings")
        try:
            port = parsed.port
        except ValueError:
            raise OllamaUnavailable("invalid_settings") from None
        if port is not None and not 1 <= port <= 65535:
            raise OllamaUnavailable("invalid_settings")
        if (
            not isinstance(self.model, str)
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}", self.model) is None
        ):
            raise OllamaUnavailable("invalid_settings")
        if type(self.timeout) not in {int, float} or not 1 <= self.timeout <= 10:
            raise OllamaUnavailable("invalid_settings")
        if type(self.deadline) not in {int, float} or not 1 <= self.deadline <= 30:
            raise OllamaUnavailable("invalid_settings")


Transport = Callable[[OllamaSettings, bytes], bytes]


def _post(settings: OllamaSettings, payload: bytes) -> bytes:
    expires = time.monotonic() + settings.deadline
    parsed = urlsplit(settings.url)
    # localhost é resolvido explicitamente para loopback; sem proxies ou redirects.
    host = "::1" if parsed.hostname == "::1" else "127.0.0.1"
    connection = http.client.HTTPConnection(
        host, parsed.port or 80, timeout=min(settings.timeout, settings.deadline)
    )
    try:
        connection.request(
            "POST", "/api/chat", payload, {"Content-Type": "application/json"}
        )
        remaining = expires - time.monotonic()
        if remaining <= 0:
            raise OllamaUnavailable("timeout")
        if connection.sock is not None:
            connection.sock.settimeout(min(settings.timeout, remaining))
        response = connection.getresponse()
        if response.status == 404:
            raise OllamaUnavailable("model_not_found")
        if response.status != 200:
            raise OllamaUnavailable("http_error")
        chunks = []
        size = 0
        while True:
            remaining = expires - time.monotonic()
            if remaining <= 0:
                raise OllamaUnavailable("timeout")
            if connection.sock is not None:
                connection.sock.settimeout(min(settings.timeout, remaining))
            chunk = response.read1(min(4096, MAX_RESPONSE_BYTES + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > MAX_RESPONSE_BYTES:
                raise OllamaUnavailable("response_too_large")
        data = b"".join(chunks)
        if len(data) > MAX_RESPONSE_BYTES:
            raise OllamaUnavailable("response_too_large")
        return data
    finally:
        connection.close()


class _Message(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    role: str
    content: str = Field(max_length=MAX_CONTENT_BYTES)
    thinking: str = ""


class _Envelope(BaseModel):
    # Ollama acrescenta contadores/durações; não são factos nem instruções.
    model_config = ConfigDict(strict=True, extra="ignore")
    model: str
    message: _Message
    done: StrictBool
    done_reason: str = "stop"


class OllamaClient:
    """Envia um único pedido limitado; um transporte falso permite testes offline."""

    def __init__(self, settings: OllamaSettings, transport: Transport = _post) -> None:
        """Guarda configuração, sem ligar ao servidor."""
        self.settings = settings
        self.transport = transport

    def chat(self, system: str, context: str, schema: dict[str, Any]) -> str:
        """Pede JSON sem streaming e recusa ferramentas, truncagem e envelopes inválidos."""
        payload = json.dumps(
            {
                "model": self.settings.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": context},
                ],
                "format": schema,
                "stream": False,
                "think": False,
                "options": {"temperature": 0, "num_predict": 512},
            },
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        try:
            if len(payload) > MAX_REQUEST_BYTES:
                raise OllamaUnavailable("request_too_large")
            started = time.monotonic()
            data = self.transport(self.settings, payload)
            if time.monotonic() - started >= self.settings.deadline:
                raise OllamaUnavailable("timeout")
            if len(data) > MAX_RESPONSE_BYTES:
                raise OllamaUnavailable("response_too_large")
            envelope = _Envelope.model_validate(strict_json(data.decode("utf-8")))
            if (
                envelope.model != self.settings.model
                or not envelope.done
                or envelope.done_reason != "stop"
                or envelope.message.role != "assistant"
            ):
                raise OllamaUnavailable("invalid_response")
            content = envelope.message.content
            if len(content.encode("utf-8")) > MAX_CONTENT_BYTES:
                raise OllamaUnavailable("response_too_large")
            return content
        except OllamaUnavailable:
            raise
        except TimeoutError:
            raise OllamaUnavailable("timeout") from None
        except _NETWORK_ERRORS:
            raise OllamaUnavailable("connection_unavailable") from None
        except _INVALID_RESPONSE_ERRORS:
            raise OllamaUnavailable("invalid_response") from None
