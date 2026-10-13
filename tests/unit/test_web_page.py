import email.message
import hashlib
import http.client
import io
import socket
import urllib.error
import urllib.request

import pytest

from shelflife.verifiers import FetchError, web_page
from shelflife.verifiers.web_page import check_url, decode, fetch_page


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
