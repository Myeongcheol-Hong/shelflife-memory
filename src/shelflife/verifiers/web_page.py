"""Web pages for web_page claims: fetch one safely, decode it and extract its visible text.

A web_page judgment quotes this text, and the quote must appear in it verbatim (CLAUDE.md).
Every comparison of page text with a quote or a value runs both sides through normalize().
"""

from __future__ import annotations

import codecs
import hashlib
import http.client
import ipaddress
import re
import socket
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from html.parser import HTMLParser

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
    resolve: Resolve | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> Page:
    """GET a web page. Raises FetchError, with `status` set for an HTTP error.

    Only http and https URLs whose host is a public address are fetched, and every
    redirect is checked the same way, so a stored URL cannot read a local file, the
    owner's network or a cloud metadata service (behind a proxy, see check_url). The body
    is capped at MAX_BYTES. The fetch, redirects and body included, is stopped once it
    passes DEADLINE_SECONDS; each network step also times out after TIMEOUT_SECONDS.
    """
    check_url(url, resolve)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    start = clock()
    try:
        with (opener or _opener(resolve)).open(request, timeout=TIMEOUT_SECONDS) as response:
            if clock() - start > DEADLINE_SECONDS:
                raise FetchError(f"page took longer than {DEADLINE_SECONDS} s at {url}")
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


def check_url(url: str, resolve: Resolve | None = None) -> None:
    """Raise FetchError unless `url` is http(s) and its host is a public address.

    Behind a proxy the proxy resolves host names (a local lookup may not work, as in
    cloud sessions), so there only addresses written as numbers ("10.0.0.1", "127.1",
    "0x7f000001") and localhost names are refused, and the proxy decides the rest.
    """
    try:
        parts = urllib.parse.urlsplit(url)
        port = parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError:
        raise FetchError(f"refused: not a valid URL: {url!r}") from None
    if parts.scheme not in ("http", "https"):
        raise FetchError(f"refused: only http and https URLs are fetched, not {url!r}")
    host = (parts.hostname or "").rstrip(".")
    if not host:
        raise FetchError(f"refused: no host in {url!r}")
    if host == "localhost" or host.endswith(".localhost"):
        raise FetchError(f"refused: {host} is not a public host")
    if (literal := _address(host)) is not None:
        addresses = [literal]
    elif _proxied(urllib.request.Request(url)):
        return
    else:
        try:
            infos = (resolve or socket.getaddrinfo)(host, port, type=socket.SOCK_STREAM)
        except OSError:
            raise FetchError(f"cannot reach {url}: unknown host {host}") from None
        addresses = [ipaddress.ip_address(info[4][0].split("%")[0]) for info in infos]
    for address in addresses:
        if not _public(address):
            raise FetchError(f"refused: {host} is not a public address ({address})")


def _address(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """The address a host written as a number stands for, in any form a resolver reads
    ("127.0.0.1", "127.1", "0x7f000001", "2130706433", "0177.0.0.1", "::1"), else None."""
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        pass
    if re.fullmatch(r"[0-9a-fx.]+", host, re.I):
        try:
            return ipaddress.IPv4Address(socket.inet_aton(host))
        except OSError:
            pass
    return None


def _public(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return address.is_global and not address.is_multicast


def _proxied(request: urllib.request.Request) -> bool:
    """Whether urllib will send this request through a proxy: ProxyHandler's own rule, on
    the same host string (with its port, which a NO_PROXY entry may name)."""
    return request.type in urllib.request.getproxies() and not urllib.request.proxy_bypass(
        request.host
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


def _via_proxy(req: urllib.request.Request) -> bool:
    """Whether ProxyHandler set this request up to go through a proxy (it then holds the
    proxy as its host): the same test urllib's do_open makes."""
    return req.has_proxy() or bool(getattr(req, "_tunnel_host", None))


class _HTTPHandler(urllib.request.HTTPHandler):
    def http_open(self, req: urllib.request.Request) -> http.client.HTTPResponse:
        # Through a proxy the connection goes to the proxy, which may be local.
        direct = not _via_proxy(req)
        return self.do_open(_HTTPConnection if direct else http.client.HTTPConnection, req)


class _HTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, req: urllib.request.Request) -> http.client.HTTPResponse:
        direct = not _via_proxy(req)
        return self.do_open(_HTTPSConnection if direct else http.client.HTTPSConnection, req)


class _CheckedRedirects(urllib.request.HTTPRedirectHandler):
    max_redirections = MAX_REDIRECTS

    def __init__(self, resolve: Resolve | None = None) -> None:
        self.resolve = resolve

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        check_url(newurl, self.resolve)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _opener(resolve: Resolve | None = None) -> urllib.request.OpenerDirector:
    """An opener for http and https only (no file:, data: or ftp: handlers)."""
    opener = urllib.request.OpenerDirector()
    for handler in (
        urllib.request.ProxyHandler(),
        _HTTPHandler(),
        _HTTPSHandler(),
        urllib.request.HTTPDefaultErrorHandler(),
        _CheckedRedirects(resolve),
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
        name = codecs.lookup(CHARSET_ALIASES.get(label, label)).name
        b" ".decode(name, "ignore")  # LookupError if not a text encoding ("base64", "hex")
        return name
    except LookupError:
        return "utf-8"


# --- text -----------------------------------------------------------------------------


def normalize(text: str) -> str:
    """Text as every comparison sees it: invisible format characters (zero-width spaces,
    soft hyphens, direction marks) removed, Unicode NFC, and each run of whitespace,
    line breaks included, as one space. Case, dashes and quote marks are kept."""
    visible = "".join(ch for ch in text if unicodedata.category(ch) != "Cf")
    return " ".join(unicodedata.normalize("NFC", visible).split())


@dataclass(frozen=True)
class Block:
    """One run of text between block-level tags, normalized."""

    text: str
    tag: str  # the innermost open block element: "p", "li", "tr", "h2", ...
    landmarks: tuple[str, ...]  # enclosing main, article, nav, header, footer, aside


# Never visible: their whole content is dropped.
SKIP = frozenset(
    "head script style noscript template svg math iframe object canvas select textarea "
    "datalist".split()
)
# Struck-through text is an old value ("~~$300~~ $250"): dropped, so it cannot be quoted.
STRUCK = frozenset({"del", "s", "strike"})
BLOCKS = frozenset(
    "address article aside blockquote body br caption dd details dialog div dl dt fieldset "
    "figcaption figure footer form h1 h2 h3 h4 h5 h6 header hgroup hr html li main nav ol "
    "p pre section summary table tbody tfoot thead tr ul".split()
)
LANDMARKS = frozenset({"main", "article", "nav", "header", "footer", "aside"})
VOID = frozenset("area base br col embed hr img input link meta source track wbr".split())


def extract(html: str) -> list[Block]:
    """The visible text of an HTML page, as blocks in page order.

    The whole body is kept, navigation and footers included: choosing the part of the
    page that matters is section selection's job, and a page's <main> or <article> may
    not hold the fact (on the Skilljar pages, <article> holds only an FAQ). Hidden
    elements (hidden, aria-hidden="true", inline display:none or visibility:hidden) are
    dropped. Table cells are joined with " | ".
    """
    parser = _TextParser()
    parser.feed(html)
    parser.close()
    return parser.blocks


def page_text(blocks: list[Block]) -> str:
    return "\n".join(block.text for block in blocks)


def _hidden(attrs: list[tuple[str, str | None]]) -> bool:
    values = {name: (value or "").strip().lower() for name, value in attrs}
    if "hidden" in values and values["hidden"] != "until-found":
        return True
    if values.get("aria-hidden") == "true":
        return True
    style = values.get("style", "").replace(" ", "")
    return "display:none" in style or "visibility:hidden" in style


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[Block] = []
        self._text: list[str] = []
        self._open: list[str] = []  # open block elements, outermost first
        self._skip: str | None = None  # the element whose content is being dropped
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._skip is not None:
            if tag == self._skip:
                self._skip_depth += 1
            elif self._skip == "head" and tag == "body":  # a page without </head>
                self._skip = None
            if self._skip is not None:
                return
        if tag not in VOID and (tag in SKIP or tag in STRUCK or _hidden(attrs)):
            self._skip, self._skip_depth = tag, 1
            return
        if tag in BLOCKS:
            self._flush()
            if tag not in VOID:
                self._open.append(tag)
        elif tag in ("td", "th") and "".join(self._text).strip():
            self._text.append(" | ")

    def handle_endtag(self, tag: str) -> None:
        if self._skip is not None:
            if tag == self._skip:
                self._skip_depth -= 1
                if self._skip_depth == 0:
                    self._skip = None
            return
        if tag in BLOCKS:
            self._flush()
            if tag in self._open:  # close it and any unclosed elements inside it
                del self._open[len(self._open) - 1 - self._open[::-1].index(tag) :]

    def handle_data(self, data: str) -> None:
        if self._skip is None:
            self._text.append(data)

    def close(self) -> None:
        super().close()
        self._flush()

    def _flush(self) -> None:
        text = normalize("".join(self._text))
        self._text = []
        if text:
            tag = self._open[-1] if self._open else "body"
            landmarks = tuple(t for t in self._open if t in LANDMARKS)
            self.blocks.append(Block(text, tag, landmarks))
