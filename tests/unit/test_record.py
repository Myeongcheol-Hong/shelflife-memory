"""The fixture recorder's slimming (tests/fixtures/record.py), which runs by hand."""

import importlib.util
from pathlib import Path

from shelflife.verifiers.web_page import decode, extract

_spec = importlib.util.spec_from_file_location(
    "record", Path(__file__).parents[1] / "fixtures" / "record.py"
)
record = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(record)

PAGE = """<!doctype html><html><head><meta charset="euc-kr">
<meta http-equiv="Content-Security-Policy" content="script-src 'nonce-abc'">
<script>if (a < b && c) { show("$300") }</script><style>p::after{content:"x"}</style>
</head><body><p class="x" style>Q&A, R&amp;D &lt;3&nbsp;you</p><!-- $300 -->
<p style="color: red; display:
 none">hidden</p><svg><text>$300</text></svg><p>Fee: $200</p></body></html>"""


def test_slim_keeps_what_the_extractor_reads():
    slimmed = record.slim(PAGE, keep_scripts=False)
    assert record.faithful(PAGE, slimmed)
    assert '<meta charset="utf-8">' in slimmed  # the fixture is saved as UTF-8
    assert "nonce" not in slimmed and "class" not in slimmed  # attributes that change
    assert "<!--" not in slimmed and "<svg" not in slimmed and "<script" not in slimmed
    assert "Q&amp;A, R&amp;D &lt;3" in slimmed  # text copied as it reads
    assert 'style="color: red; display:\n none"' in slimmed  # a hiding style stays


def test_slim_can_keep_scripts_as_they_are():
    slimmed = record.slim(PAGE, keep_scripts=True)
    assert 'if (a < b && c) { show("$300") }' in slimmed
    assert record.faithful(PAGE, slimmed)


def test_faithful_compares_what_the_tests_will_read():
    slimmed = record.slim(PAGE, keep_scripts=False)
    assert not record.faithful(PAGE, slimmed.replace("Fee: $200", "Fee: $250"))
    korean = '<meta charset="euc-kr"><p>시험 응시료</p>'
    assert not record.faithful(korean, korean)  # saved as UTF-8, read back as EUC-KR
    page = PAGE.replace('charset="euc-kr"', 'charset="utf-8"')
    assert extract(decode(record.slim(page, False).encode("utf-8"))) == extract(page)
