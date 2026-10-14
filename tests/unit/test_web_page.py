import email.message
import hashlib
import http.client
import io
import json
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from shelflife.verifiers import FetchError, web_page
from shelflife.verifiers.web_page import (
    Block,
    check_url,
    decode,
    extract,
    fetch_page,
    normalize,
    page_text,
)

PAGES = Path(__file__).parents[1] / "fixtures" / "pages"
INDEX = json.loads((PAGES / "index.json").read_text(encoding="utf-8"))


def resolver(*addresses):
    def resolve(host, port, type=0):
        if not addresses:
            raise socket.gaierror(-2, "Name or service not known")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (a, port)) for a in addresses]

    return resolve


@pytest.fixture
def direct(monkeypatch):
    monkeypatch.setattr(urllib.request, "getproxies", dict)


@pytest.fixture
def proxied(monkeypatch):
    proxy = "http://127.0.0.1:3128"
    monkeypatch.setattr(urllib.request, "getproxies", lambda: {"http": proxy, "https": proxy})
    monkeypatch.setattr(urllib.request, "proxy_bypass", lambda host: False)


# --- which URLs are fetched -----------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "message"),
    [
        ("file:///etc/passwd", "only http and https"),
        ("data:text/html,<p>hi</p>", "only http and https"),
        ("ftp://example.com/file", "only http and https"),
        ("example.com/page", "only http and https"),
        ("http:///page", "no host"),
        ("http://example.com:99999/", "not a valid URL"),
        ("http://localhost:8000/", "localhost is not a public host"),
        ("http://admin.localhost/", "not a public host"),
        ("http://127.0.0.1/", "not a public address"),
        ("http://[::1]/", "not a public address"),
        ("http://169.254.169.254/latest/meta-data/", "not a public address"),  # cloud metadata
        ("http://10.0.0.1/", "not a public address"),
        ("http://192.168.1.1/", "not a public address"),
        ("http://user@100.64.0.1/", "not a public address"),  # carrier-grade NAT
        ("http://[::ffff:127.0.0.1]/", "not a public address"),
        ("http://224.0.0.1/", "not a public address"),
        # Addresses written in the short or numeric forms a resolver also reads.
        ("http://127.1/", r"not a public address \(127\.0\.0\.1\)"),
        ("http://0x7f000001/", r"not a public address \(127\.0\.0\.1\)"),
        ("http://2130706433/", r"not a public address \(127\.0\.0\.1\)"),
        ("http://0177.0.0.1/", r"not a public address \(127\.0\.0\.1\)"),
        ("http://0xa9fea9fe/", r"not a public address \(169\.254\.169\.254\)"),
        ("http://localhost./", "not a public host"),  # a trailing dot
        ("http://[fe80::1%25eth0]/", "not a public address"),  # link-local, with a zone
    ],
)
def test_check_url_refuses(direct, url, message):
    with pytest.raises(FetchError, match=message):
        check_url(url, resolver("93.184.215.14"))


def test_check_url_refuses_a_name_that_resolves_to_a_private_address(direct):
    with pytest.raises(FetchError, match=r"not a public address \(10\.0\.0\.7\)"):
        check_url("https://intranet.example.com/", resolver("93.184.215.14", "10.0.0.7"))
    with pytest.raises(FetchError, match="unknown host"):
        check_url("https://nowhere.example/", resolver())
    check_url("https://example.com/page", resolver("93.184.215.14"))  # public: no error


@pytest.mark.parametrize(
    "url", ["http://169.254.169.254/", "http://127.1/", "http://0x7f000001/", "http://localhost/"]
)
def test_behind_a_proxy_addresses_written_as_numbers_are_still_refused(proxied, url):
    with pytest.raises(FetchError, match="not a public"):
        check_url(url, resolver())


def test_behind_a_proxy_names_are_left_to_the_proxy(proxied):
    check_url("https://www.databricks.com/learn", resolver())  # no local lookup


def test_a_host_the_proxy_bypasses_is_checked_as_direct(monkeypatch):
    monkeypatch.setattr(urllib.request, "getproxies", lambda: {"https": "http://127.0.0.1:3128"})
    asked = []

    def bypass(host):  # NO_PROXY may name a host with its port, as ProxyHandler passes it
        asked.append(host)
        return host == "intranet.example:8443"

    monkeypatch.setattr(urllib.request, "proxy_bypass", bypass)
    with pytest.raises(FetchError, match="not a public address"):
        check_url("https://intranet.example:8443/", resolver("10.0.0.7"))
    check_url("https://intranet.example/", resolver("10.0.0.7"))  # through the proxy
    assert asked == ["intranet.example:8443", "intranet.example"]
    handler, used, proxies = web_page._HTTPSHandler(), [], urllib.request.ProxyHandler()
    handler.do_open = lambda conn, req, **kw: used.append(conn)
    for url in ("https://intranet.example:8443/", "https://intranet.example/"):
        request = urllib.request.Request(url)
        proxies.proxy_open(request, proxies.proxies["https"], "https")
        handler.https_open(request)
    # Bypassed: a checked direct connection. Through the proxy: to the proxy, unchecked.
    assert used == [web_page._HTTPSConnection, web_page.http.client.HTTPSConnection]


def test_every_redirect_is_checked(direct):
    redirects = web_page._CheckedRedirects(resolver("10.0.0.7"))
    request = urllib.request.Request("http://93.184.215.14/a")
    with pytest.raises(FetchError, match="not a public address"):
        redirects.redirect_request(request, None, 302, "Found", {}, "http://127.0.0.1/admin")
    with pytest.raises(FetchError, match="only http and https"):
        redirects.redirect_request(request, None, 302, "Found", {}, "file:///etc/passwd")
    with pytest.raises(FetchError, match=r"not a public address \(10\.0\.0\.7\)"):
        redirects.redirect_request(request, None, 302, "Found", {}, "http://intranet.example/")
    followed = redirects.redirect_request(request, None, 301, "Moved", {}, "http://93.184.215.14/b")
    assert followed.full_url == "http://93.184.215.14/b"
    assert redirects.max_redirections == web_page.MAX_REDIRECTS


class PeerSocket:
    closed = False

    def __init__(self, peer):
        self.peer = peer

    def getpeername(self):
        return (self.peer, 443)

    def close(self):
        self.closed = True


@pytest.mark.parametrize("connection", [web_page._HTTPConnection, web_page._HTTPSConnection])
def test_a_direct_connection_refuses_a_non_public_peer(monkeypatch, connection):
    # DNS may answer differently when the connection resolves the name again.
    sock = PeerSocket("10.1.2.3")
    monkeypatch.setattr(socket, "create_connection", lambda *args, **kwargs: sock)
    with pytest.raises(FetchError, match="connected to a non-public address"):
        connection("rebind.example").connect()  # before any TLS or request
    assert sock.closed


def test_a_public_peer_is_kept(monkeypatch):
    sock = PeerSocket("93.184.215.14")
    monkeypatch.setattr(socket, "create_connection", lambda *args, **kwargs: sock)
    assert web_page._connect_public(("example.com", 443), 15, None) is sock


def connections_used():
    """The connection classes the handlers use, for requests ProxyHandler has prepared."""
    http_handler, https_handler = web_page._HTTPHandler(), web_page._HTTPSHandler()
    used = []
    http_handler.do_open = https_handler.do_open = lambda conn, req, **kw: used.append(conn)
    proxies = urllib.request.ProxyHandler()
    for url, handler in (
        ("http://example.com/", http_handler),
        ("https://example.com/", https_handler),
    ):
        request = urllib.request.Request(url)
        if request.type in proxies.proxies:  # what OpenerDirector does before http(s)_open
            proxies.proxy_open(request, proxies.proxies[request.type], request.type)
        getattr(handler, f"{request.type}_open")(request)
    return used


def test_a_direct_connection_checks_the_connected_address(direct):
    assert connections_used() == [web_page._HTTPConnection, web_page._HTTPSConnection]


def test_a_proxy_on_a_bypassed_address_is_still_used(monkeypatch):
    # Cloud sessions list the proxy's own address (127.0.0.1) in NO_PROXY. ProxyHandler
    # makes the proxy the request's host, so the handler must not ask NO_PROXY again.
    proxy = "http://127.0.0.1:3128"
    monkeypatch.setattr(urllib.request, "getproxies", lambda: {"http": proxy, "https": proxy})
    monkeypatch.setattr(urllib.request, "proxy_bypass", lambda host: host.startswith("127.0.0.1"))
    assert connections_used() == [
        web_page.http.client.HTTPConnection,
        web_page.http.client.HTTPSConnection,
    ]


def test_through_a_proxy_the_connection_goes_to_the_proxy(proxied):
    # The proxy may listen on localhost, so the connected address is not checked.
    assert connections_used() == [
        web_page.http.client.HTTPConnection,
        web_page.http.client.HTTPSConnection,
    ]


# --- fetch ----------------------------------------------------------------------------


class Response:
    def __init__(self, body, content_type="text/html; charset=utf-8", status=200, chunk=5):
        self.headers = email.message.Message()
        if content_type:
            self.headers["Content-Type"] = content_type
        self.status, self.body, self.chunk = status, body, chunk
        self.url = "https://example.com/final"

    def read1(self, n):
        part, self.body = self.body[: self.chunk], self.body[self.chunk :]
        return part

    def geturl(self):
        return self.url

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class Truncated(Response):
    def read1(self, n):
        raise http.client.IncompleteRead(b"<p>Fe")


class Opener:
    def __init__(self, result):
        self.result, self.requests = result, []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


def test_fetch_page_returns_the_page(proxied):
    body = "<p>똠방각하 응시료</p>".encode("cp949")  # 똠 needs cp949, not strict EUC-KR
    opener = Opener(Response(body, "text/html; charset=EUC-KR"))
    page = fetch_page("https://example.com/fee", opener=opener)
    assert (page.url, page.final_url, page.status) == (
        "https://example.com/fee",
        "https://example.com/final",
        200,
    )
    assert (page.content_type, page.charset, page.body) == ("text/html", "euc-kr", body)
    assert page.text() == "<p>똠방각하 응시료</p>"
    assert page.sha256 == hashlib.sha256(body).hexdigest()
    [(request, timeout)] = opener.requests
    assert "shelflife" in request.get_header("User-agent") and timeout > 0


def test_fetch_page_never_opens_a_refused_url():
    opener = Opener(Response(b"secret"))
    with pytest.raises(FetchError, match="only http and https"):
        fetch_page("file:///etc/passwd", opener=opener)
    assert opener.requests == []


@pytest.mark.parametrize(
    ("result", "message", "status"),
    [
        (urllib.error.HTTPError("u", 404, "Not Found", {}, None), "HTTP 404 from", 404),
        (urllib.error.HTTPError("u", 410, "Gone", {}, None), "HTTP 410 from", 410),
        (urllib.error.URLError("connection reset"), "cannot reach", None),
        (TimeoutError("timed out"), "cannot reach", None),
        (Response(b"%PDF-1.7", "application/pdf"), r"not a web page \(application/pdf\)", None),
        (Truncated(b"<p>Fee"), "cannot reach", None),
    ],
)
def test_fetch_page_errors(proxied, result, message, status):
    with pytest.raises(FetchError, match=message) as raised:
        fetch_page("https://example.com/page", opener=Opener(result))
    assert raised.value.status == status


def test_fetch_page_caps_the_size_and_the_time(proxied, monkeypatch):
    monkeypatch.setattr(web_page, "MAX_BYTES", 12)
    with pytest.raises(FetchError, match="page larger than"):
        fetch_page("https://example.com/big", opener=Opener(Response(b"x" * 13)))
    fetch_page("https://example.com/ok", opener=Opener(Response(b"x" * 12)))

    ticks = iter(range(0, 1000, 20))  # 20 s per call
    with pytest.raises(FetchError, match="took longer than 30 s"):
        fetch_page(
            "https://example.com/slow",
            opener=Opener(Response(b"x" * 12)),
            clock=lambda: next(ticks),
        )


def test_the_deadline_covers_connecting_and_redirects(proxied):
    now = [0.0]

    class SlowOpener(Opener):
        def open(self, request, timeout):
            now[0] += 31  # connecting, redirects and headers took 31 s
            return super().open(request, timeout)

    with pytest.raises(FetchError, match="took longer than 30 s"):
        # An empty body: the reading loop never checks the time.
        fetch_page("https://example.com/", opener=SlowOpener(Response(b"")), clock=lambda: now[0])


class Raw:
    """What urllib's http(s)_open handlers return."""

    def __init__(self, url, code, headers, body=b""):
        self.url, self.code, self.status, self.msg = url, code, code, "reason"
        self.headers = email.message.Message()
        for name, value in headers.items():
            self.headers[name] = value
        self.fp = io.BytesIO(body)

    def info(self):
        return self.headers

    def geturl(self):
        return self.url

    def read(self, n=-1):
        return self.fp.read(n)

    read1 = read

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_fetch_page_follows_only_checked_redirects(direct, monkeypatch):
    # Through the real opener; only the network call is replaced.
    old, new = "https://93.184.215.14/old", "https://93.184.215.15/new"
    evil, metadata = "https://93.184.215.14/x", "http://169.254.169.254/latest/meta-data/"
    pages = {
        old: Raw(old, 301, {"Location": new}),
        new: Raw(new, 200, {"Content-Type": "text/html"}, b"<p>Fee: $200</p>"),
        evil: Raw(evil, 302, {"Location": metadata}),
    }
    opened = []

    def https_open(self, req):
        opened.append(req.full_url)
        return pages[req.full_url]

    monkeypatch.setattr(web_page._HTTPSHandler, "https_open", https_open)
    page = fetch_page(old)
    assert (page.final_url, page.body) == (new, b"<p>Fee: $200</p>")
    with pytest.raises(FetchError, match="not a public address"):
        fetch_page(evil)
    assert opened == [old, new, evil]


def test_each_request_gets_the_time_left_and_none_starts_after_the_deadline(direct, monkeypatch):
    old, new = "https://93.184.215.14/old", "https://93.184.215.15/new"
    now, timeouts = [0.0], []
    took = {old: 20, new: 5}  # seconds each request takes

    def do_open(self, connection, req, **kw):  # the network step, after the time check
        timeouts.append((req.full_url, req.timeout))
        now[0] += took[req.full_url]
        if req.full_url == old:
            return Raw(old, 301, {"Location": new})
        return Raw(new, 200, {"Content-Type": "text/html"}, b"<p>Fee: $200</p>")

    monkeypatch.setattr(web_page._HTTPSHandler, "do_open", do_open)
    page = fetch_page(old, clock=lambda: now[0])
    assert page.body == b"<p>Fee: $200</p>"
    # The first request gets the usual timeout; the redirect only the 10 s left.
    assert timeouts == [(old, web_page.TIMEOUT_SECONDS), (new, 10)]

    now[0], timeouts[:] = 0.0, []
    took[old] = 31  # the deadline passes before the redirect
    with pytest.raises(FetchError, match="took longer than 30 s"):
        fetch_page(old, clock=lambda: now[0])
    assert timeouts == [(old, web_page.TIMEOUT_SECONDS)]  # the redirect never started


def test_the_default_opener_has_only_checked_handlers(direct):
    opener = web_page._opener()
    kinds = {type(handler) for handler in opener.handlers}
    assert {web_page._HTTPHandler, web_page._HTTPSHandler, web_page._CheckedRedirects} <= kinds
    stock = {urllib.request.HTTPHandler, urllib.request.HTTPSHandler, urllib.request.FileHandler,
             urllib.request.HTTPRedirectHandler, urllib.request.DataHandler,
             urllib.request.FTPHandler}  # fmt: skip
    assert not kinds & stock
    assert set(opener.handle_open) == {"http", "https"}  # no file:, data: or ftp:


def test_a_missing_content_type_is_read_as_text(proxied):
    page = fetch_page("https://example.com/", opener=Opener(Response(b"hi", content_type=None)))
    assert (page.content_type, page.charset) == ("text/plain", None)


# --- decode ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("body", "charset", "text"),
    [
        ("똠방각하".encode("cp949"), "euc-kr", "똠방각하"),  # 똠 is cp949, not strict EUC-KR
        ("똠".encode("cp949"), "ks_c_5601-1987", "똠"),
        (b"it\x92s", "iso-8859-1", "it’s"),  # latin-1 labels mean windows-1252
        (b"<meta charset='euc-kr'>" + "가격".encode("cp949"), None, "<meta charset='euc-kr'>가격"),
        (b'<meta http-equiv="Content-Type" content="text/html; charset=windows-1252">\x93', None,
         '<meta http-equiv="Content-Type" content="text/html; charset=windows-1252">“'),
        ("가격".encode(), "utf-8", "가격"),
        (b"\xef\xbb\xbfhi", "cp949", "hi"),  # a byte-order mark wins over the header
        ("hi".encode("utf-16"), None, "hi"),
        (b"caf\xc3\xa9 \xff", "no-such-charset", "café �"),  # unknown label: UTF-8
        (b"<p>fee</p>", "base64", "<p>fee</p>"),  # a codec that is not a text encoding
        (b"<meta charset=hex><p>fee", None, "<meta charset=hex><p>fee"),
        (b"\xfe\xff" + "hi".encode("utf-16-be"), None, "hi"),
        (b"it\x92s", " US-ASCII ", "it’s"),
        (b"x" * 4096 + b"<meta charset=cp949>\xb0\xa1", None,  # meta only near the top
         "x" * 4096 + "<meta charset=cp949>��"),
        (b"caf\xc3\xa9", None, "café"),
    ],
)  # fmt: skip
def test_decode(body, charset, text):
    assert decode(body, charset) == text


def test_the_header_charset_wins_over_meta():
    body = b"<meta charset='utf-8'>" + "가".encode("cp949")
    assert decode(body, "euc-kr").endswith("가")


# --- normalize ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "normalized"),
    [
        ("Exam fee:  $300\n\tUSD ", "Exam fee: $300 USD"),  # NBSP, runs, line breaks
        ("Foun­dations​ fee", "Foundations fee"),  # soft hyphen, zero-width space
        ("﻿‎Global⁠ Premier ", "Global Premier"),  # BOM, LRM, joiner
        ("Café", "Café"),  # NFC
        ("Developer – Foundations “Pro”", "Developer – Foundations “Pro”"),  # kept as is
        ("USD 300", "USD 300"),  # case kept
        ("１０² ﬁ", "１０² ﬁ"),  # NFC, not NFKC: compatibility forms are kept
    ],
)
def test_normalize(raw, normalized):
    assert normalize(raw) == normalized


# --- extract --------------------------------------------------------------------------


def texts(html):
    return [block.text for block in extract(html)]


@pytest.mark.parametrize(
    "dropped",
    [
        "<script>var fee = '$300';</script>",
        "<style>.fee::after { content: '$300' }</style>",
        "<noscript>Enable JavaScript to see $300</noscript>",
        "<template><p>$300</p></template>",
        "<svg><text>$300</text></svg>",
        "<select><option>$300</option></select>",
        "<p hidden>$300</p>",
        "<p aria-hidden='true'>$300</p>",
        "<p style='DISPLAY: none'>$300</p>",
        "<p style='color:red;visibility:hidden'>$300</p>",
        "<del>$300</del>",
        "<s>$300</s>",
        "<strike>$300</strike>",
        "<div hidden><div><p>$300</p></div><p>$300</p></div>",  # nested elements of one name
        "<div hidden><span hidden>icon</span>$300</div>",  # hidden inside hidden
        "<div aria-hidden='true'><script>x</script>$300</div>",
        "<p hidden='false'>$300</p>",  # a boolean attribute: any value hides
        "<p style='color:red;display:\tnone'>$300</p>",
        "<p style='visibility: collapse'>$300</p>",
        "<p style='opacity: 0'>$300</p>",
        "<p style='opacity:.0 !important'>$300</p>",
        "<p style='font-size: 0'>$300</p>",
        "<p style='font-size:0px'>$300</p>",
        "<p style='position:absolute; left:-9999px'>$300</p>",
        "<p style='top: -1000px'>$300</p>",
        "<p style='text-indent:-100em'>$300</p>",
        "<p style='text-indent: -9999rem'>$300</p>",
        "<dialog><p>$300</p></dialog>",  # a dialog that is not open
        "<title>$300</title>",
        "<video>Your browser cannot play $300</video>",
        "<audio>$300</audio>",
        "<iframe>$300</iframe>",
        "<object>$300</object>",
        "<canvas>$300</canvas>",
        "<math><mi>$300</mi></math>",
        "<textarea>$300</textarea>",
        "<datalist><option>$300</option></datalist>",
        "<noembed>$300</noembed>",
        "<ruby><rp>($300)</rp></ruby>",  # ruby fallback parentheses
    ],
)
def test_extract_drops_what_is_not_visible(dropped):
    html = f"<html><head><title>Fee</title></head><body><p>Fee:</p>{dropped}<p>$250</p></body>"
    assert texts(html) == ["Fee:", "$250"]


def test_extract_keeps_what_is_visible():
    html = """<body><header><nav><a>Home</a></nav></header>
        <main><article><h2>Exam fee</h2><p>300&nbsp;USD &amp; tax</p></article>
        <p hidden="until-found">Found by search</p><input hidden><img aria-hidden="true">
        <p aria-hidden="false">Shown</p><dialog open><p>Open dialog</p></dialog>
        <p>Price: <s>$300</s> $250</p></main>
        <footer><p>© 2026</p></footer></body>"""
    assert extract(html) == [
        Block("Home", "nav", ("header", "nav")),
        Block("Exam fee", "h2", ("main", "article")),
        Block("300 USD & tax", "p", ("main", "article")),
        Block("Found by search", "p", ("main",)),
        Block("Shown", "p", ("main",)),
        Block("Open dialog", "p", ("main",)),
        Block("Price: $250", "p", ("main",)),
        Block("© 2026", "p", ("footer",)),
    ]


def test_extract_joins_table_cells_and_splits_rows():
    html = """<table><tr><th>Rank</th><th>Agent</th><th>Score</th></tr>
        <tr><td>1</td><td>Claude Code</td><td>60.0%</td></tr>
        <tr><td></td><td>Pi</td><td>58.1%</td></tr></table>"""
    assert texts(html) == ["Rank | Agent | Score", "1 | Claude Code | 60.0%", "Pi | 58.1%"]


def test_extract_splits_blocks_at_line_breaks_and_unclosed_tags():
    html = "<ul><li>Associate<br>$99<li>Developer<br/>$125</ul><p>Next"
    assert texts(html) == ["Associate", "$99", "Developer", "$125", "Next"]
    assert normalize(page_text(extract(html))) == "Associate $99 Developer $125 Next"


@pytest.mark.parametrize(
    "style",
    [
        "opacity: 0.5",
        "font-size: 0.8em",
        "left: -999px",  # not far enough to be off screen
        "top: -99em",
        "text-indent: -99.9rem",
        "left: 9999px",  # off screen to the right is not read as hidden
        "margin-left: -9999px",  # only left, top and text-indent are read
        "x-opacity: 0",
    ],
)
def test_an_inline_style_that_does_not_hide_keeps_the_text(style):
    assert texts(f"<p style='{style}'>$300</p>") == ["$300"]


def test_extract_reads_only_the_first_part_of_a_huge_page(monkeypatch):
    html = "<p>$250</p><p>$300 and more</p>"
    monkeypatch.setattr(web_page, "MAX_PARSED", html.index("00 and"))
    assert texts(html) == ["$250", "$3"]  # text past the cut is never seen


def test_a_self_closed_hidden_element_is_empty():
    # As XHTML reads it. HTML would hide the rest of its parent; reading it as empty
    # keeps a stray "/>" from dropping text.
    assert texts("<main><div hidden/><p>Fee: $250</p></main>") == ["Fee: $250"]


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        # End tags a page leaves out end a dropped element too, not the rest of the page.
        ("<body><p hidden>secret<p>Fee: $200<p>Next</body>", ["Fee: $200", "Next"]),
        ("<ul><li hidden>secret<li>Fee: $200<li>Next</ul>", ["Fee: $200", "Next"]),
        ("<table><tr><td hidden>secret<td>Fee<td>$200</table>", ["Fee | $200"]),
        ("<dl><dt hidden>secret<dt>Fee<dd>$200</dl>", ["Fee", "$200"]),
        ("<ul><li>Pro<span hidden>secret<li>Fee: $200</ul>", ["Pro", "Fee: $200"]),
        ("<div><p>Fee <del>$300</div><p>After</p>", ["Fee", "After"]),  # closed with its parent
        ("<div>Fee <del>$300</div>After", ["Fee", "After"]),
        ("<p>Price: <s>$300 <p>Now $250</p>", ["Price:", "Now $250"]),
        ("<ul><li><p>One<li>Two</ul><p>After", ["One", "Two", "After"]),
        # A page may leave out </head>, or put body content in <head>.
        ("<head><title>T</title><body><p>Fee: $200</p>", ["Fee: $200"]),
        ("<html><head><title>T</title><meta charset=utf-8><p>Fee $200", ["Fee $200"]),
        ("<head><title>T</title><p>Fee $200</head><body><p>More", ["Fee $200", "More"]),
    ],
)
def test_extract_implies_end_tags(html, expected):
    assert texts(html) == expected


@pytest.mark.parametrize(
    ("html", "tags"),
    [
        ("<p>One<div>Two</div>Three", ["p", "div", "body"]),  # <div> ended the <p>
        ("<ul><li><p>One<li>Two</li>Three</ul>", ["p", "li", "ul"]),  # <li> ended both
        ("<dl><dt>Fee<dd>$300<dt>Length<dd>120 minutes</dl>Next", ["dt", "dd", "dt", "dd", "body"]),
    ],
)
def test_implied_end_tags_close_the_element(html, tags):
    assert [b.tag for b in extract(html)] == tags


def test_blocks_carry_their_tag_and_landmarks():
    html = """<details><summary>Who can take it?</summary><p>Partners.</p></details>
        <dl><dt>Exam fee</dt><dd>$300</dd></dl><aside><p>Ad</p></aside>
        <nav><ul><li>Home<li>About</ul></nav><main><p>Fee<br>$250</p></main>"""
    assert [(b.text, b.tag, b.landmarks) for b in extract(html)] == [
        ("Who can take it?", "summary", ()),
        ("Partners.", "p", ()),
        ("Exam fee", "dt", ()),
        ("$300", "dd", ()),
        ("Ad", "p", ("aside",)),
        ("Home", "li", ("nav",)),
        ("About", "li", ("nav",)),
        ("Fee", "p", ("main",)),
        ("$250", "p", ("main",)),
    ]


@pytest.mark.parametrize(
    "html",
    [
        "<div>" * 100_000 + "x" + "</div>" * 100_000,  # deep nesting
        "<p>para text" * 40_000,  # end tags left out
        "<ul>" + "<li>item" * 40_000 + "</ul>",
        "<main>x" * 40_000,  # landmarks inside landmarks
        "<div>" * 40_000 + "</p>" * 40_000,  # end tags that match nothing
        "<table><tr>" + "<td>cell" * 40_000 + "</table>",
    ],
)
def test_extraction_time_grows_linearly(html):
    # A hostile page under the 10 MB cap must not hang the check. Quadratic code took
    # minutes on these; linear code takes well under a second.
    started = time.perf_counter()
    blocks = extract(html)
    assert time.perf_counter() - started < 5
    assert all(len(b.landmarks) <= web_page.MAX_DEPTH for b in blocks)


# --- the recorded seed pages ----------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "evidence"),
    [
        ("skilljar-faq", "Certification is currently available only to organizations in the "
         "Claude Partner Network."),
        ("skilljar-partner", "Claude Certified Developer – Foundations Foundations $125 USD"),
        ("skilljar-partner", "Claude Certified Architect – Foundations Foundations $125 USD"),
        ("aws-aip-c01", "300 USD. Visit Exam pricing for additional cost information"),
        ("databricks-genai", "Registration fee: $200"),
        ("benchmarks-metagenomics", "1 | Claude Sonnet 5.5 | Claude Code | Anthropic | 60.0%"),
    ],
)  # fmt: skip
def test_the_seed_evidence_survives_extraction(name, evidence):
    html = decode((PAGES / f"{name}.html").read_bytes())
    assert evidence in normalize(page_text(extract(html)))


def test_text_inside_scripts_is_never_extracted():
    assert INDEX["aws-aip-c01"]["scripts_kept"]
    html = decode((PAGES / "aws-aip-c01.html").read_bytes())
    text = page_text(extract(html))
    assert "imageSrc" in html and "imageSrc" not in text
    assert text.count("300 USD") == 1  # the page, not the JSON in its scripts


def test_the_partner_page_lists_one_price_for_two_exams():
    # Section selection (M3b) must tell these apart: the value alone matches both.
    html = decode((PAGES / "skilljar-partner.html").read_bytes())
    assert page_text(extract(html)).count("$125 USD") == 2
