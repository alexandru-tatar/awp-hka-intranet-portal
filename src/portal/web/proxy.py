"""AppProxy: leitet eine Anfrage an den Container einer App weiter und gibt das Identitäts-Token mit (02 §6, 09 §1.3)."""

from __future__ import annotations

import time
from typing import AsyncIterator, Final
from urllib.parse import urlsplit

import httpx
from fastapi import Request
from fastapi.responses import Response, StreamingResponse
from loguru import logger
from starlette.background import BackgroundTask
from starlette.exceptions import HTTPException

from ..core.config import AppsConfig
from ..service import UnavailableError

ASSERTION_HEADER: Final = "x-portal-assertion"
HOP_BY_HOP: Final = frozenset(
    {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers",
     "transfer-encoding", "upgrade"}
)
# Request headers the proxy sets itself or that must never reach an app.
DROPPED_REQUEST: Final = HOP_BY_HOP | {
    "host", "cookie", "content-length", ASSERTION_HEADER, "x-request-id",
    "x-forwarded-for", "x-forwarded-proto", "x-forwarded-host", "x-forwarded-port", "x-real-ip", "forwarded",
}
DROPPED_RESPONSE: Final = HOP_BY_HOP | {"set-cookie"}


class AppProxy:
    """Ein HTTP-Client für alle Apps; Apps sehen weder Cookies noch fremde Tokens."""

    def __init__(self, cfg: AppsConfig, transport: httpx.AsyncBaseTransport | None = None) -> None:
        """Konstruktor.

        :param cfg: Einstellungen der Weiterleitung
        :param transport: Transport statt des Netzwerks, für Tests
        """
        self.cfg: Final = cfg
        self.client: Final = httpx.AsyncClient(
            transport=transport,
            timeout=httpx.Timeout(cfg.read_timeout_seconds, connect=cfg.connect_timeout_seconds),
            follow_redirects=False,
        )

    async def aclose(self) -> None:
        """Den HTTP-Client schließen."""
        await self.client.aclose()

    async def forward(self, request: Request, slug: str, assertion: str) -> Response:
        """Anfrage unverändert im Pfad an die App weitergeben und die Antwort durchreichen.

        :param request: Anfrage der Person
        :param slug: Slug der App
        :param assertion: Token, ersetzt jede mitgeschickte Kopfzeile ``X-Portal-Assertion``
        :return: Antwort der App ohne ``Set-Cookie``
        :rtype: Response
        :raises HTTPException: 413 bei zu großem Body, 504 bei Zeitüberschreitung, 502 bei anderen Fehlern
        :raises UnavailableError: Falls der Container nicht erreichbar ist
        """
        base: Final = self.cfg.upstream_for(slug)
        target: Final = base + request.url.path + (f"?{request.url.query}" if request.url.query else "")
        body: Final = await self._read_body(request)
        started: Final = time.perf_counter()
        try:
            upstream = await self.client.send(
                self.client.build_request(request.method, target, headers=self._request_headers(request, assertion), content=body),
                stream=True,
            )
        except httpx.ConnectError as exc:
            logger.warning("slug={} upstream unreachable: {}", slug, type(exc).__name__)
            raise UnavailableError(slug) from exc
        except httpx.TimeoutException as exc:
            logger.warning("slug={} upstream timeout", slug)
            raise HTTPException(504) from exc
        except httpx.HTTPError as exc:
            logger.warning("slug={} upstream error: {}", slug, type(exc).__name__)
            raise HTTPException(502) from exc
        logger.debug(
            "slug={} method={} status={} ms={:.1f}", slug, request.method, upstream.status_code,
            (time.perf_counter() - started) * 1000,
        )
        response: Final = StreamingResponse(
            _stream(upstream), status_code=upstream.status_code, background=BackgroundTask(upstream.aclose)
        )
        response.raw_headers = self._response_headers(upstream, base)
        return response

    async def _read_body(self, request: Request) -> bytes:
        """Body lesen und die Größe begrenzen.

        :param request: Anfrage
        :return: Der Body
        :rtype: bytes
        :raises HTTPException: 413, falls ``max_body_bytes`` überschritten wird
        """
        limit: Final = self.cfg.max_body_bytes
        declared = request.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > limit:
            raise HTTPException(413)
        chunks: list[bytes] = []
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > limit:
                raise HTTPException(413)
            chunks.append(chunk)
        return b"".join(chunks)

    def _request_headers(self, request: Request, assertion: str) -> list[tuple[str, str]]:
        """Kopfzeilen für die App: ohne Cookie und fremdes Token, mit echtem Token.

        :param request: Anfrage der Person
        :param assertion: Token des Portals
        :return: Kopfzeilen
        :rtype: list[tuple[str, str]]
        """
        headers = [(k, v) for k, v in request.headers.items() if k.lower() not in DROPPED_REQUEST]
        headers += [
            ("X-Portal-Assertion", assertion),
            ("X-Request-Id", request.state.request_id),
            ("X-Forwarded-For", request.client.host if request.client else ""),
            ("X-Forwarded-Proto", request.url.scheme),
            ("X-Forwarded-Host", request.headers.get("host", "")),
        ]
        return headers

    def _response_headers(self, upstream: httpx.Response, base: str) -> list[tuple[bytes, bytes]]:
        """Kopfzeilen der Antwort: ohne ``Set-Cookie`` und Hop-by-hop, ``Location`` auf die App-Adresse bereinigt.

        :param upstream: Antwort der App
        :param base: Basisadresse der App
        :return: Rohe Kopfzeilen
        :rtype: list[tuple[bytes, bytes]]
        """
        out: list[tuple[bytes, bytes]] = []
        for key, value in upstream.headers.raw:
            name = key.decode("latin-1").lower()
            if name in DROPPED_RESPONSE:
                continue
            if name == "location" and value.decode("latin-1").startswith(base):
                value = value[len(base):] or b"/"
            out.append((key.lower(), value))
        return out


async def _stream(upstream: httpx.Response) -> AsyncIterator[bytes]:
    """Den Body der App ohne Dekodierung durchreichen.

    :param upstream: Antwort der App
    :return: Blöcke des Bodys
    :rtype: AsyncIterator[bytes]
    """
    if upstream.is_stream_consumed:  # Test-Transports (MockTransport) lesen die Antwort schon vorab
        yield upstream.content
        return
    async for chunk in upstream.aiter_raw():
        yield chunk


def is_same_origin(request: Request) -> bool:
    """CSRF-Prüfung für Anfragen mit Seiteneffekt (02 §6).

    ``Sec-Fetch-Site`` ``same-origin`` oder ``none`` ist erlaubt, ``same-site`` und ``cross-site`` nicht. Ohne
    dieses Signal gilt ``Origin``: Der Host muss der Anfrage entsprechen. Ohne jedes Browsersignal (z. B. ``curl``)
    ist die Anfrage erlaubt, weil sie dann nicht aus einer fremden Seite stammt.

    :param request: Anfrage
    :return: ``True``, wenn die Anfrage zulässig ist
    :rtype: bool
    """
    site = request.headers.get("sec-fetch-site")
    if site is not None:
        return site in ("same-origin", "none")
    origin = request.headers.get("origin")
    if origin is None:
        return True
    return urlsplit(origin).netloc == request.headers.get("host", "")
