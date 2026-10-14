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

from shelflife.verifiers import MAX_BYTES, TIMEOUT_SECONDS, USER_AGENT, FetchError

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
    local network or a cloud metadata service (behind a proxy, see check_url). The body
    is capped at MAX_BYTES.

    The time limit, DEADLINE_SECONDS: every request, the first and each redirect, is
    checked just before it connects. None starts once the deadline has passed, and each
    one's socket timeout is TIMEOUT_SECONDS or the time left, whichever is less. The
    deadline is checked again when the headers have arrived and after each chunk of the
    body. A socket timeout bounds one socket operation, not a request, so this is not a
    hard limit: a server that keeps sending a little at a time (headers, chunk sizes, a
    redirect's body) can overrun it by more than one timeout.
    """
    check_url(url, resolve)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    start = clock()

    def left() -> float:
        """Seconds left before the deadline; FetchError once it has passed."""
        remaining = DEADLINE_SECONDS - (clock() - start)
        if remaining <= 0:
            raise FetchError(f"page took longer than {DEADLINE_SECONDS} s at {url}")
        return remaining

    try:
        opener = opener or _opener(resolve, left)
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            left()
            content_type = response.headers.get_content_type()
            if content_type not in PAGE_TYPES:
                raise FetchError(f"not a web page ({content_type}) at {url}")
            body = _read(response, url, left)
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


def _time_limit(req: urllib.request.Request, left: Callable[[], float] | None) -> None:
    """Just before a request connects: FetchError once fetch_page's deadline has passed,
    else a socket timeout of TIMEOUT_SECONDS or the time left, whichever is less. A
    redirect passes here too, after urllib has read the previous response."""
    if left is not None:
        req.timeout = min(TIMEOUT_SECONDS, left())


class _HTTPHandler(urllib.request.HTTPHandler):
    def __init__(self, left: Callable[[], float] | None = None) -> None:
        super().__init__()
        self.left = left

    def http_open(self, req: urllib.request.Request) -> http.client.HTTPResponse:
        _time_limit(req, self.left)
        # Through a proxy the connection goes to the proxy, which may be local.
        direct = not _via_proxy(req)
        return self.do_open(_HTTPConnection if direct else http.client.HTTPConnection, req)


class _HTTPSHandler(urllib.request.HTTPSHandler):
    def __init__(self, left: Callable[[], float] | None = None) -> None:
        super().__init__()
        self.left = left

    def https_open(self, req: urllib.request.Request) -> http.client.HTTPResponse:
        _time_limit(req, self.left)
        direct = not _via_proxy(req)
        return self.do_open(_HTTPSConnection if direct else http.client.HTTPSConnection, req)


class _CheckedRedirects(urllib.request.HTTPRedirectHandler):
    max_redirections = MAX_REDIRECTS

    def __init__(self, resolve: Resolve | None = None) -> None:
        self.resolve = resolve

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        check_url(newurl, self.resolve)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _opener(
    resolve: Resolve | None = None, left: Callable[[], float] | None = None
) -> urllib.request.OpenerDirector:
    """An opener for http and https only (no file:, data: or ftp: handlers). `left` gives
    the seconds left before fetch_page's deadline, checked before each request."""
    opener = urllib.request.OpenerDirector()
    for handler in (
        urllib.request.ProxyHandler(),
        _HTTPHandler(left),
        _HTTPSHandler(left),
        urllib.request.HTTPDefaultErrorHandler(),
        _CheckedRedirects(resolve),
        urllib.request.HTTPErrorProcessor(),
    ):
        opener.add_handler(handler)
    return opener


def _read(response, url: str, left: Callable[[], float]) -> bytes:  # type: ignore[no-untyped-def]
    chunks: list[bytes] = []
    size = 0
    while chunk := response.read1(64 * 1024):
        size += len(chunk)
        if size > MAX_BYTES:
            raise FetchError(f"page larger than {MAX_BYTES // 2**20} MB at {url}")
        left()
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
    joiners, soft hyphens, direction marks) removed, Unicode NFC, and each run of
    whitespace, line breaks included, as one space. Case, dashes, quote marks and
    compatibility forms (full-width digits, ligatures) are kept, so every word stays as
    written; removing joiners can only change how some emoji and scripts render."""
    visible = "".join(ch for ch in text if unicodedata.category(ch) != "Cf")
    return " ".join(unicodedata.normalize("NFC", visible).split())


@dataclass(frozen=True)
class Block:
    """One run of text between block-level tags, normalized."""

    text: str
    tag: str  # the innermost open block element: "p", "li", "tr", "h2", ...
    landmarks: tuple[str, ...]  # enclosing main, article, nav, header, footer, aside


# Dropped with their content: not rendered as text (scripts, styles, the page title, media,
# graphics, embedded pages, form controls).
SKIP = frozenset(
    "script style title noscript template svg math iframe object canvas video audio select "
    "textarea datalist noembed noframes rp".split()
)
# Struck-through text is an old value ("~~$300~~ $250"): dropped, so it cannot be quoted.
STRUCK = frozenset({"del", "s", "strike"})
BLOCKS = frozenset(
    "address article aside blockquote body br caption center dd details dialog dir div dl dt "
    "fieldset figcaption figure footer form h1 h2 h3 h4 h5 h6 header hgroup hr html legend "
    "li main menu nav ol p pre search section summary table tbody tfoot thead tr ul".split()
)
LANDMARKS = frozenset({"main", "article", "nav", "header", "footer", "aside"})
VOID = frozenset("area base br col embed hr img input link meta source track wbr".split())
# Elements whose end tag a page may leave out, and the start tags that close each one
# (HTML's implied end tags, simplified).
IMPLIED_END = {
    "p": BLOCKS,
    "li": frozenset({"li"}),
    "dt": frozenset({"dt", "dd"}),
    "dd": frozenset({"dt", "dd"}),
    "tr": frozenset({"tr"}),
    "td": frozenset({"td", "th", "tr"}),
    "th": frozenset({"td", "th", "tr"}),
}
STRUCTURE = BLOCKS | {"td", "th"}  # what the stacks track; inline elements are left out
MAX_DEPTH = 256  # open elements tracked; deeper ones are counted, not kept
MAX_PARSED = 2 * 2**20  # characters of a page's decoded HTML that extract() reads
# Inline styles that hide an element: zero opacity or font size, or moved off screen
# (left, top or text-indent of -1000px, -100em or -100rem or further).
ZERO = re.compile(r"[-+]?(?:0+\.?0*|\.0+)(?:[a-z]+|%)?")
OFF_SCREEN = re.compile(r"-(\d+(?:\.\d*)?|\.\d+)(px|r?em)")


def extract(html: str) -> list[Block]:
    """The visible text of an HTML page, as blocks in page order.

    The whole body is kept, navigation and footers included: choosing the part of the
    page that matters is section selection's job, and a page's <main> or <article> may
    not hold the fact (on the Skilljar pages, <article> holds only an FAQ). Dropped:
    SKIP elements, struck-through text, and hidden elements: the hidden attribute,
    aria-hidden="true", a closed <dialog>, and an inline style of display:none,
    visibility:hidden, opacity:0 or font-size:0, or one that moves the element off
    screen (left, top or text-indent of -1000px or -100em or further). Only inline
    styles are read: an element hidden by a stylesheet class still counts as visible.
    aria-hidden is an approximation (screen readers skip it; browsers may show it), and
    a self-closed "<div hidden/>" is read as empty, as XHTML would. Table cells are
    joined with " | ". End tags a page leaves out are implied as HTML implies them, and
    the work stays linear in the page's size, however deep its nesting. Only the first
    MAX_PARSED characters are read, so text past them is never found or quoted.
    """
    parser = _TextParser()
    parser.feed(html[:MAX_PARSED])
    parser.close()
    return parser.blocks


def page_text(blocks: list[Block]) -> str:
    return "\n".join(block.text for block in blocks)


def _hidden(tag: str, attrs: list[tuple[str, str | None]]) -> bool:
    values = {name: (value or "").strip().lower() for name, value in attrs}
    if tag == "dialog" and "open" not in values:
        return True
    if "hidden" in values and values["hidden"] != "until-found":
        return True
    if values.get("aria-hidden") == "true":
        return True
    for declaration in re.sub(r"\s", "", values.get("style", "")).split(";"):
        name, _, value = declaration.partition(":")
        value = value.removesuffix("!important")
        if (name, value) in (
            ("display", "none"),
            ("visibility", "hidden"),
            ("visibility", "collapse"),
        ):
            return True
        if name in ("opacity", "font-size") and ZERO.fullmatch(value):
            return True
        if name in ("left", "top", "text-indent") and (m := OFF_SCREEN.fullmatch(value)):
            if float(m[1]) >= (1000 if m[2] == "px" else 100):
                return True
    return False


class _Stack:
    """Open elements (STRUCTURE only), with HTML's implied end tags, at most MAX_DEPTH
    deep. Each entry keeps the landmarks around it, so they cost nothing to read."""

    def __init__(self) -> None:
        self.tags: list[str] = []
        self.landmarks: list[tuple[str, ...]] = [()]
        self.overflow = 0  # elements opened past MAX_DEPTH and not yet closed

    def open(self, tag: str) -> None:
        self.imply_ends(tag)
        if len(self.tags) >= MAX_DEPTH:
            self.overflow += 1
            return
        self.tags.append(tag)
        around = self.landmarks[-1]
        self.landmarks.append((*around, tag) if tag in LANDMARKS else around)

    def implied(self, tag: str) -> int | None:
        """The outermost open element this start tag closes without its end tag: the
        search looks past elements whose end may be left out ("<li><p>a<li>" closes the
        <p> and the <li>), and stops at any other element."""
        found = None
        i = len(self.tags) - 1
        while i >= 0 and self.tags[i] in IMPLIED_END:
            if tag in IMPLIED_END[self.tags[i]]:
                found = i
            i -= 1
        return found

    def imply_ends(self, tag: str) -> None:
        if (i := self.implied(tag)) is not None:
            self.pop_to(i)

    def close(self, tag: str) -> bool:
        """Close the innermost open `tag` and anything open inside it; False if none is."""
        if self.overflow:
            self.overflow -= 1
            return True
        for i in range(len(self.tags) - 1, -1, -1):
            if self.tags[i] == tag:
                self.pop_to(i)
                return True
        return False

    def pop_to(self, i: int) -> None:
        del self.tags[i:]
        del self.landmarks[i + 1 :]

    @property
    def top(self) -> str:
        return self.tags[-1] if self.tags else "body"


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[Block] = []
        self._text: list[str] = []
        self._has_text = False  # whether _text holds more than whitespace
        self._open = _Stack()
        # The element whose content is being dropped, the elements open inside it, and
        # how many elements were open around it.
        self._skip: str | None = None
        self._inside = _Stack()
        self._around = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._skip is not None:
            ends_it = not self._inside.tags and tag in IMPLIED_END.get(self._skip, ())
            if ends_it or self._open.implied(tag) is not None:
                self._skip = None  # it ends the dropped element, or an element around it
            else:
                if tag not in VOID and (tag in STRUCTURE or tag == self._skip):
                    self._inside.open(tag)
                return
        if tag not in VOID and (tag in SKIP or tag in STRUCK or _hidden(tag, attrs)):
            self._open.imply_ends(tag)
            self._flush_if(tag in BLOCKS)
            self._skip, self._inside, self._around = tag, _Stack(), len(self._open.tags)
            return
        if tag in BLOCKS:
            self._flush()
            if tag not in VOID:
                self._open.open(tag)
        elif tag in ("td", "th"):
            self._open.imply_ends(tag)
            if self._has_text:
                self._text.append(" | ")

    def handle_endtag(self, tag: str) -> None:
        if self._skip is not None:
            if self._inside.close(tag):
                return
            if tag == self._skip:
                self._skip = None
                return
            if tag not in self._open.tags[: self._around]:
                return  # a stray end tag inside the dropped element
            self._skip = None  # an element around it closed, so it ended too
        if tag in BLOCKS:
            self._flush()
            self._open.close(tag)

    def handle_data(self, data: str) -> None:
        if self._skip is None:
            self._text.append(data)
            self._has_text = self._has_text or not data.isspace()

    def close(self) -> None:
        super().close()
        self._flush()

    def _flush_if(self, condition: bool) -> None:
        if condition:
            self._flush()

    def _flush(self) -> None:
        text = normalize("".join(self._text)) if self._has_text else ""
        self._text, self._has_text = [], False
        if text:
            self.blocks.append(Block(text, self._open.top, self._open.landmarks[-1]))
