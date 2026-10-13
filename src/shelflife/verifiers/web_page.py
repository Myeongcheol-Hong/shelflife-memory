"""Web pages for web_page claims: fetch one safely and decode it (M3).

Later milestones extract the page's visible text, which a web_page judgment quotes.
"""

from __future__ import annotations

import codecs
import hashlib
import http.client
import ipaddress
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

from shelflife.verifiers import TIMEOUT_SECONDS, USER_AGENT, FetchError

MAX_BYTES = 10 * 1024 * 1024
DEADLINE_SECONDS = 30
MAX_REDIRECTS = 5
PAGE_TYPES = frozenset({"text/html", "application/xhtml+xml", "text/plain"})

# (host, port, type=...) -> getaddrinfo tuples. Injected in tests.
Resolve = Callable[..., list[tuple]]


@dataclass(frozen=True)
class Page:
    url: str  # as asked
    final_url: str  # after redirects
    status: int
    content_type: str
    charset: str | None  # from the Content-Type header
    body: bytes

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.body).hexdigest()

    def text(self) -> str:
        return decode(self.body, self.charset)


# --- fetch ----------------------------------------------------------------------------


def fetch_page(
    url: str,
    *,
    opener: urllib.request.OpenerDirector | None = None,
    resolve: Resolve = socket.getaddrinfo,
    clock: Callable[[], float] = time.monotonic,
) -> Page:
    """GET a web page. Raises FetchError, with `status` set for an HTTP error.

    Only http and https URLs whose host is a public address are fetched, and every
    redirect is checked the same way, so a stored URL cannot read a local file, the
    owner's network or a cloud metadata service. The body is capped at MAX_BYTES and the
    whole fetch at about DEADLINE_SECONDS.
    """
    check_url(url, resolve)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    start = clock()
    try:
        with (opener or _opener()).open(request, timeout=TIMEOUT_SECONDS) as response:
            content_type = response.headers.get_content_type()
            if content_type not in PAGE_TYPES:
                raise FetchError(f"not a web page ({content_type}) at {url}")
            body = _read(response, url, start, clock)
            charset = response.headers.get_content_charset()
            return Page(url, response.geturl(), response.status, content_type, charset, body)
    except FetchError:
        raise
    except urllib.error.HTTPError as e:
        raise FetchError(f"HTTP {e.code} from {url}", status=e.code) from None
    except (OSError, http.client.HTTPException, ValueError) as e:
        raise FetchError(f"cannot reach {url}: {e}") from None


def check_url(url: str, resolve: Resolve = socket.getaddrinfo) -> None:
    """Raise FetchError unless `url` is http(s) and its host is a public address.

    Behind a proxy the proxy resolves host names (a local lookup may not work), so only
    literal addresses and localhost names are checked here.
    """
    try:
        parts = urllib.parse.urlsplit(url)
        port = parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError:
        raise FetchError(f"refused: not a valid URL: {url!r}") from None
    if parts.scheme not in ("http", "https"):
        raise FetchError(f"refused: only http and https URLs are fetched, not {url!r}")
    host = parts.hostname
    if not host:
        raise FetchError(f"refused: no host in {url!r}")
    if host == "localhost" or host.endswith(".localhost"):
        raise FetchError(f"refused: {host} is not a public host")
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        if _proxied(url):
            return
        try:
            infos = resolve(host, port, type=socket.SOCK_STREAM)
        except OSError:
            raise FetchError(f"cannot reach {url}: unknown host {host}") from None
        addresses = [ipaddress.ip_address(info[4][0].split("%")[0]) for info in infos]
    for address in addresses:
        if not _public(address):
            raise FetchError(f"refused: {host} is not a public address ({address})")


def _public(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return address.is_global and not address.is_multicast


def _proxied(url: str) -> bool:
    """Whether urllib sends this URL through a proxy (the same rule as ProxyHandler)."""
    parts = urllib.parse.urlsplit(url)
    return parts.scheme in urllib.request.getproxies() and not urllib.request.proxy_bypass(
        parts.hostname or ""
    )


def _connect_public(address: tuple[str, int], *args: object, **kwargs: object) -> socket.socket:
    """socket.create_connection that refuses a peer at a non-public address.

    The name was checked before the request, but it is resolved again to connect, and the
    second answer may differ (DNS rebinding). This checks the address actually connected.
    """
    sock = socket.create_connection(address, *args, **kwargs)  # type: ignore[arg-type]
    peer = ipaddress.ip_address(sock.getpeername()[0].split("%")[0])
    if not _public(peer):
        sock.close()
        raise FetchError(f"refused: {address[0]} connected to a non-public address ({peer})")
    return sock


class _HTTPConnection(http.client.HTTPConnection):
    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self._create_connection = _connect_public


class _HTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self._create_connection = _connect_public


class _HTTPHandler(urllib.request.HTTPHandler):
    def http_open(self, req: urllib.request.Request) -> http.client.HTTPResponse:
        # Through a proxy the connection goes to the proxy, which may be local.
        direct = not _proxied(req.full_url)
        return self.do_open(_HTTPConnection if direct else http.client.HTTPConnection, req)


class _HTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, req: urllib.request.Request) -> http.client.HTTPResponse:
        direct = not _proxied(req.full_url)
        return self.do_open(_HTTPSConnection if direct else http.client.HTTPSConnection, req)


class _CheckedRedirects(urllib.request.HTTPRedirectHandler):
    max_redirections = MAX_REDIRECTS

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _opener() -> urllib.request.OpenerDirector:
    """An opener for http and https only (no file:, data: or ftp: handlers)."""
    opener = urllib.request.OpenerDirector()
    for handler in (
        urllib.request.ProxyHandler(),
        _HTTPHandler(),
        _HTTPSHandler(),
        urllib.request.HTTPDefaultErrorHandler(),
        _CheckedRedirects(),
        urllib.request.HTTPErrorProcessor(),
    ):
        opener.add_handler(handler)
    return opener


def _read(response, url: str, start: float, clock: Callable[[], float]) -> bytes:  # type: ignore[no-untyped-def]
    chunks: list[bytes] = []
    size = 0
    while chunk := response.read1(64 * 1024):
        size += len(chunk)
        if size > MAX_BYTES:
            raise FetchError(f"page larger than {MAX_BYTES // 2**20} MB at {url}")
        if clock() - start > DEADLINE_SECONDS:
            raise FetchError(f"page took longer than {DEADLINE_SECONDS} s at {url}")
        chunks.append(chunk)
    return b"".join(chunks)


# --- decode ---------------------------------------------------------------------------

# Labels whose web meaning is a superset of Python's codec of that name (WHATWG Encoding):
# Korean pages labelled euc-kr use cp949, and "latin-1" pages use windows-1252.
CHARSET_ALIASES = {
    "euc-kr": "cp949",
    "ks_c_5601-1987": "cp949",
    "windows-949": "cp949",
    "x-windows-949": "cp949",
    "iso-8859-1": "cp1252",
    "latin1": "cp1252",
    "latin-1": "cp1252",
    "us-ascii": "cp1252",
    "ascii": "cp1252",
}
META_CHARSET = re.compile(rb"""<meta[^>]*?charset\s*=\s*["']?\s*([A-Za-z0-9_.:-]+)""", re.I)
BOMS = (
    (codecs.BOM_UTF8, "utf-8-sig"),
    (codecs.BOM_UTF16_LE, "utf-16"),
    (codecs.BOM_UTF16_BE, "utf-16"),
)


def decode(body: bytes, charset: str | None = None) -> str:
    """The page as text: a byte-order mark first, then the header's charset, then a
    <meta> charset near the top, else UTF-8. Undecodable bytes become U+FFFD."""
    for bom, codec in BOMS:
        if body.startswith(bom):
            return body.decode(codec, "replace")
    if not charset and (m := META_CHARSET.search(body[:4096])):
        charset = m[1].decode("ascii")
    return body.decode(_codec(charset), "replace")


def _codec(label: str | None) -> str:
    label = (label or "utf-8").strip().lower()
    try:
        return codecs.lookup(CHARSET_ALIASES.get(label, label)).name
    except LookupError:
        return "utf-8"
