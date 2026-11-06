# Payload Detection — Design

Sub-project 2 of 4 in the repository hardening effort (2026-11-06 review).
Depends on sub-project 1 (CI gate, merged). Feeds sub-project 4 (ML pipeline).

## Problem

Measured on 2026-11-07 against the current code.

1. **Encoded payloads are invisible.** `detect_payload_indicators`
   (`app/services/payload_signals.py`) does substring checks on the raw,
   percent-encoded query and body. `id=1%27%20UNION%20SELECT…`,
   `q=1+union+select+1` and `UNION/**/SELECT` produce no indicators.
2. **One strong signal never reaches the decoy.** A high-risk indicator adds
   20 points; monitoring starts at 30 and redirect at 60. A plain
   `' or 1=1--` body with a browser User-Agent on an ordinary path is
   **allowed to the real app**.
3. **Dead indicators.** `encoded`, `unusual-content-type` and `large-payload`
   are scored in `risk_engine.py` but never produced.

Baseline on CSIC 2010 (`data/csic-2010`, 15,964 attacks / 18,640 normal),
browser User-Agent, request count 1, heuristic routing:

| | Any indicator | Decoy | Allowed |
|---|---:|---:|---:|
| Attacks | 0.0% | 0.0% | 100.0% |
| Normal | 0.0% | 0.0% | 100.0% |

A throwaway probe showed URL-decoding alone lifts attack flagging to 7.2%
with 0.0% false positives. Injection-shaped content (after decoding)
appears in roughly 8–16% of CSIC attacks; the remainder is parameter
tampering (`id=2/`, missing fields), which signatures cannot detect and
which belongs to the ML detector (sub-project 4).

## Goal

A request carrying a recognized attack signature, in any common encoding,
is routed to the decoy regardless of User-Agent, path, or request rate,
without flagging legitimate traffic.

## Decisions

| Topic | Decision |
|---|---|
| Single strong signal | Routes to the decoy (user decision, option A). |
| Where decoding happens | A new pure module, `app/services/payload_normalization.py`. |
| Detection technique | Compiled regular expressions over normalized text, grouped by indicator label. No external dependency. |
| Indicator labels | Existing four high-risk labels kept; two new high-risk labels; the three dormant medium labels implemented. |
| Feature contract | **Not** changed here. Feature names and `FEATURE_CONTRACT_VERSION` stay; sub-project 4 bumps the contract and retrains (it already must, for the flow features). |
| Bare quotes | Not a signal on their own (1.0% of CSIC normal requests contain `'`). |

## Components

### `app/services/payload_normalization.py` (new)

`normalize_for_inspection(raw: str) -> NormalizedPayload`

`NormalizedPayload` is a frozen dataclass: `text: str` (normalized,
lowercased) and `decode_layers: int` (percent-decoding rounds that changed
the input).

Steps, in order:

1. Percent-decode with `+` treated as a space, repeated until the text stops
   changing, at most **3** rounds. `decode_layers` counts the rounds that
   changed the text.
2. Decode JSON-style `\uXXXX` escapes.
3. `html.unescape`.
4. Unicode NFKC (folds full-width characters such as `ＳＥＬＥＣＴ`).
5. Replace SQL inline comments `/* … */` (bodies up to 200 characters) with a
   single space.
6. Collapse whitespace runs other than `\r` and `\n` to one space; lowercase.

Input is already bounded by callers (body ≤ 65,536 characters for detection).

### `app/services/payload_signals.py` (rewritten detection)

`detect_payload_indicators(path: str, query: str, body: bytes, *, content_type: str | None = None) -> list[str]`

Signature extended with an optional keyword; existing callers keep working.
Returns a **sorted, de-duplicated** list of labels.

Detection runs on `normalize_for_inspection` of `path`, `query` and the
first 65,536 characters of the body decoded as UTF-8 (errors ignored), each
separately. Size rules use the full `len(body)` in bytes.

High-risk labels (patterns on normalized text):

| Label | Matches (summary) |
|---|---|
| `sql-like` | `union [all] select`; quote followed by `or`/`and` and a comparison; `or <n>=<n>`; `;` followed by `drop/delete/insert/update/truncate/alter/exec/shutdown/create`; `drop table`/`truncate table`; `sleep(`, `benchmark(`, `pg_sleep(`; `waitfor delay`; quote followed by `--`, `#` or `;`; `information_schema`; `xp_cmdshell`; `load_file(`; `into outfile/dumpfile` |
| `xss` | `<script`; `javascript:`; `on<event>=` for common events; `<iframe`, `<svg`, `<object`, `<embed`; `document.cookie`/`document.domain` |
| `path-traversal` | `../` or `..\`; `/etc/passwd`, `/etc/shadow`; `win.ini`, `boot.ini` |
| `rce-indicator` | `${jndi:`; `/bin/sh` family; `cmd /c`; `powershell … -e[nc]`; `;`, `|`, `||`, `&&` or a backtick followed by a shell command word (`cat`, `ls`, `id`, `whoami`, `uname`, `wget`, `curl`, `nc`, `bash`, `sh`, `ping`); `$(` command substitution |
| `header-injection` (new) | The **raw** input contains an encoded line break (`%0d` or `%0a`, any encoding depth) and the decoded text has a line break followed by `<header-name>:` |
| `null-byte` (new) | The raw input contains `%00`, or decoded text contains `\x00` |

A single `&` is never a command separator (it separates query parameters).

Medium-risk labels:

| Label | Rule |
|---|---|
| `encoded` | Any part needed **2 or more** decode layers (double encoding), or an SQL inline comment sits between two word characters (`un/**/ion`). |
| `large-payload` | Body longer than **65,536** bytes. |
| `unusual-content-type` | Body is non-empty, `content_type` is given, and its media type is not one of: `application/json`, `application/*+json`, `application/x-www-form-urlencoded`, `multipart/form-data`, `text/plain`, `application/xml`, `text/xml`. |

### `app/services/risk_engine.py`

- `HIGH_RISK_INDICATORS` adds `header-injection` and `null-byte`.
- Payload score: **60** for the first high-risk indicator, **+10** for each
  additional one, **+8** per medium indicator, capped at **80**. One high
  indicator alone yields level HIGH, so the heuristic decision is
  `redirect_to_decoy`.
- Medium indicators alone keep their current weight (8 each).

### `app/api/routes/proxy.py`

Passes `content_type=request.headers.get("content-type")` to
`detect_payload_indicators`. No other change.

### `scripts/evaluate_payload_detection.py` (new)

Reproducible evaluation on a local CSIC 2010 directory: prints, per class,
the share of requests with any indicator and the heuristic routing
distribution (browser User-Agent, request count 1), plus per-label counts.
Not run in CI (the dataset is not committed). Results recorded in
`docs/dataset-preparation.md`.

## Error handling

- Normalization never raises: invalid percent sequences are left as-is;
  invalid `\u` escapes are left as-is.
- Detection never raises on arbitrary bytes.
- All regular expressions are bounded (no nested unbounded quantifiers); a
  65,536-character adversarial input must be processed in under 200 ms.

## Testing

- `tests/test_payload_normalization.py`: each normalization step; the
  3-round cap; `decode_layers` counting; invalid sequences preserved.
- `tests/test_payload_signals.py`:
  - attack corpus × encodings (raw, percent, `+`, double-percent, mixed case,
    HTML entities, `\u` escapes, full-width, inline comments) → expected label;
  - benign corpus → no indicators (e.g. `O'Reilly`, `Union Square`,
    `Select your size`, `2+2=4`, `drop-leaf table`, prices, emails, JSON with
    newlines and `"note: x"`, `&id=2&cmd=list` query strings);
  - each medium rule; sorted unique output; ReDoS timing bound.
- `tests/test_risk_engine.py`: one high indicator → score 60, level HIGH;
  existing expectations hold.
- `tests/test_proxy.py`: through the proxy with a browser User-Agent on
  `/api/products`: raw SQLi body, URL-encoded query SQLi and double-encoded
  traversal reach the decoy; a benign search reaches the real app.

## Success criteria

1. All tests above pass; CI green.
2. CSIC 2010 via the evaluation script: normal requests flagged **≤ 0.5%**;
   attacks routed to the decoy **≥ 7.2%** (the decode-only probe), with the
   achieved figure recorded in the docs.

## Out of scope

- Parameter-tampering detection (sub-project 4, ML).
- Feature contract bump and retraining (sub-project 4).
- Client IP, auth and deployment hardening (sub-project 3).
