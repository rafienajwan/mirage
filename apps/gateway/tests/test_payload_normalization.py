"""Tests for payload text normalization before inspection."""

from app.services.payload_normalization import normalize_for_inspection


def test_percent_and_plus_decoding():
    result = normalize_for_inspection("id%3D1+union+select")
    assert result.text == "id=1 union select"
    assert result.decode_layers == 1


def test_double_encoding_counts_layers():
    result = normalize_for_inspection("%2527")
    assert result.text == "'"
    assert result.decode_layers == 2


def test_decode_rounds_capped_at_three():
    result = normalize_for_inspection("%25252527")
    assert result.text == "%27"
    assert result.decode_layers == 3


def test_json_unicode_escapes():
    assert normalize_for_inspection("\\u003cscript\\u003e").text == "<script>"


def test_html_entities():
    result = normalize_for_inspection("&lt;img src=x onerror=alert(1)&gt;")
    assert result.text == "<img src=x onerror=alert(1)>"


def test_fullwidth_folded():
    assert normalize_for_inspection("ＳＥＬＥＣＴ").text == "select"


def test_sql_inline_comment_removed():
    assert normalize_for_inspection("UNION/**/SELECT").text == "union select"
    assert normalize_for_inspection("un/*x*/ion").text == "un ion"


def test_whitespace_collapsed_keeps_newlines():
    assert normalize_for_inspection("a \t  b\r\nc").text == "a b\r\nc"


def test_invalid_sequences_preserved():
    result = normalize_for_inspection("100%zz")
    assert result.text == "100%zz"
    assert result.decode_layers == 0
    assert normalize_for_inspection("\\uZZZZ").text == "\\uzzzz"


def test_plain_text_untouched():
    result = normalize_for_inspection("hello")
    assert result.text == "hello"
    assert result.decode_layers == 0
