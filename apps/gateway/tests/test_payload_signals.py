"""Tests for payload attack-signature detection."""

import time

import pytest

from app.services.payload_signals import detect_payload_indicators

ATTACKS = [
    ("/api/products", "id=1%27%20UNION%20SELECT%20password%20FROM%20users", b"", "sql-like"),
    ("/api/products", "q=1+union+select+1", b"", "sql-like"),
    ("/api/products", "", b"1 UNION/**/SELECT 1", "sql-like"),
    ("/api/products", "", b"id=1' or '1'='1", "sql-like"),
    ("/api/products", "", b"x';waitfor delay '0:0:15';--", "sql-like"),
    ("/api/products", "id=1%20AND%20SLEEP/**/(5)", b"", "sql-like"),
    ("/api/products", "", b"cantidad='; DROP TABLE usuarios; --", "sql-like"),
    ("/api/products", "q=%2527%2520or%25201%253D1", b"", "sql-like"),
    (
        "/api/products",
        "",
        "ＳＥＬＥＣＴ * ＦＲＯＭ users ＵＮＩＯＮ ＳＥＬＥＣＴ 1".encode(),
        "sql-like",
    ),
    ("/api/products", "", b"<SCRipt>alert(1)</scrIPT>", "xss"),
    ("/api/products", "", b"&lt;img src=x onerror=alert(1)&gt;", "xss"),
    ("/api/products", "", b'{"bio": "\\u003cscript\\u003ealert(1)"}', "xss"),
    ("/api/products", "next=javascript:alert(1)", b"", "xss"),
    ("/api/files/..%2f..%2fetc/passwd", "", b"", "path-traversal"),
    ("/api/files", "f=%252e%252e%252fwin.ini", b"", "path-traversal"),
    ("/api/ping", "", b"host=8.8.8.8;cat /etc/hosts", "rce-indicator"),
    ("/api/ping", "", b"host=x|whoami", "rce-indicator"),
    ("/api/ping", "", b"${jndi:ldap://x/a}", "rce-indicator"),
    ("/api/ping", "", b"a=$(id)", "rce-indicator"),
    ("/api/register", "nombre=any%0d%0aSet-cookie:%20Tamper=1", b"", "header-injection"),
    ("/api/register", "", b"dni=%00&x=1", "null-byte"),
]


@pytest.mark.parametrize("path,query,body,label", ATTACKS)
def test_attack_detected(path, query, body, label):
    assert label in detect_payload_indicators(path, query, body)


BENIGN = [
    ("/api/users", "name=O%27Reilly", b""),
    ("/api/search", "q=Union+Square", b""),
    ("/api/products", "", b"Select your size"),
    ("/api/calc", "expr=2%2B2%3D4", b""),
    ("/api/furniture", "q=drop-leaf+table", b""),
    ("/api/checkout", "precio=85&cantidad=2", b""),
    ("/api/users", "", b'{"email": "ana@example.com", "note": "call me"}'),
    ("/api/notes", "", b'{"text": "line one\\nnote: x\\nsubject: y"}'),
    ("/api/notes", "", b"first line\r\nNote: second line"),
    ("/api/items", "id=2&cmd=list&sh=1&ls=3", b""),
    ("/tienda1/publico/anadir.jsp", "id=1&nombre=Jam%F3n+Ib%E9rico&precio=85", b""),
    ("/api/books", "q=JavaScript%3A+The+Good+Parts", b""),
    ("/api/posts", "", b"I love my dog; cat lovers disagree"),
    ("/api/posts", "", b"Most adults need sleep (8 hours) each night"),
    ("/api/posts", "", b"Show me your id; please"),
]


@pytest.mark.parametrize("path,query,body", BENIGN)
def test_benign_not_flagged(path, query, body):
    assert detect_payload_indicators(path, query, body) == []


def test_latin1_body_does_not_raise():
    result = detect_payload_indicators("/x", "", b"nombre=Jam\xf3n&x=' or 1=1--")
    assert "sql-like" in result


def test_output_sorted_and_unique():
    body = b"' or 1=1-- <script> union select 1 ' or 2=2--"
    assert detect_payload_indicators("/x", "", body) == ["sql-like", "xss"]


def test_adversarial_input_is_fast():
    body = ((b"'" + b"%25" * 10 + b"or ") * 4000)[:65536]
    start = time.perf_counter()
    detect_payload_indicators("/x", "q=" + "%2" * 5000, body)
    assert time.perf_counter() - start < 0.2
