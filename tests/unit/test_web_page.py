import email.message
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


def test_behind_a_proxy_names_are_left_to_the_proxy(proxied):
    check_url("https://www.databricks.com/learn", resolver())  # no local lookup
    with pytest.raises(FetchError, match="not a public address"):
        check_url("http://169.254.169.254/", resolver())
    with pytest.raises(FetchError, match="not a public host"):
        check_url("http://localhost/", resolver())


def test_every_redirect_is_checked(direct):
    redirects = web_page._CheckedRedirects()
    request = urllib.request.Request("http://93.184.215.14/a")
    with pytest.raises(FetchError, match="not a public address"):
        redirects.redirect_request(request, None, 302, "Found", {}, "http://127.0.0.1/admin")
    with pytest.raises(FetchError, match="only http and https"):
        redirects.redirect_request(request, None, 302, "Found", {}, "file:///etc/passwd")
    followed = redirects.redirect_request(request, None, 301, "Moved", {}, "http://93.184.215.14/b")
    assert followed.full_url == "http://93.184.215.14/b"
    assert redirects.max_redirections == web_page.MAX_REDIRECTS


@pytest.mark.parametrize(("peer", "refused"), [("10.1.2.3", True), ("93.184.215.14", False)])
def test_the_connected_address_is_checked_too(monkeypatch, peer, refused):
    # DNS may answer differently when the connection resolves the name again.
    class Socket:
        closed = False

        def getpeername(self):
            return (peer, 443)

        def close(self):
            self.closed = True

    sock = Socket()
    monkeypatch.setattr(socket, "create_connection", lambda *args, **kwargs: sock)
    if refused:
        with pytest.raises(FetchError, match="connected to a non-public address"):
            web_page._connect_public(("rebind.example", 443), 15, None)
        assert sock.closed
    else:
        assert web_page._connect_public(("example.com", 443), 15, None) is sock


def connections_used():
    http_handler, https_handler = web_page._HTTPHandler(), web_page._HTTPSHandler()
    used = []
    http_handler.do_open = https_handler.do_open = lambda conn, req, **kw: used.append(conn)
    http_handler.http_open(urllib.request.Request("http://example.com/"))
    https_handler.https_open(urllib.request.Request("https://example.com/"))
    return used


def test_a_direct_connection_checks_the_connected_address(direct):
    assert connections_used() == [web_page._HTTPConnection, web_page._HTTPSConnection]
    assert web_page._HTTPSConnection("example.com")._create_connection is web_page._connect_public


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


class Opener:
    def __init__(self, result):
        self.result, self.requests = result, []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


def test_fetch_page_returns_the_page(proxied):
    body = "<p>시험 응시료</p>".encode("cp949")
    opener = Opener(Response(body, "text/html; charset=EUC-KR"))
    page = fetch_page("https://example.com/fee", opener=opener)
    assert (page.url, page.final_url, page.status) == (
        "https://example.com/fee",
        "https://example.com/final",
        200,
    )
    assert (page.content_type, page.charset, page.body) == ("text/html", "euc-kr", body)
    assert page.text() == "<p>시험 응시료</p>"
    assert len(page.sha256) == 64
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
        (b"caf\xc3\xa9", None, "café"),
    ],
)  # fmt: skip
def test_decode(body, charset, text):
    assert decode(body, charset) == text


def test_the_header_charset_wins_over_meta():
    body = b"<meta charset='utf-8'>" + "가".encode("cp949")
    assert decode(body, "euc-kr").endswith("가")
