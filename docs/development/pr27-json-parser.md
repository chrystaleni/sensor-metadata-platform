# PR #27: JSON decoder recursion guard

Argyris Fellas with Codex assistance, 16 November 2026. Baseline `ea101f9`.

## Defect and focused fix

A raw Network Element PATCH with excessive array/object nesting raised `RecursionError` in DRF's JSON decoder. The existing JSONParser handles ValueError but not this exception, allowing an HTTP 500 before serializer validation.

`core.parsers.SafeJSONParser` delegates to the existing DRF parser and catches only `RecursionError` from parsing. It raises a generic `ParseError` with HTTP 400:

```json
{"detail":"JSON parse error."}
```

DRF's ordinary JSON syntax, encoding and strict-number handling remain delegated to the parent parser. There is no global exception handler, recursion-limit change or new nesting policy.

The default parser list uses SafeJSONParser in place of JSONParser and retains FormParser and MultiPartParser. The Excel endpoint keeps its explicit multipart-only parser unchanged. Identifier serializers, Department uniqueness, persistence, views, imports and all migrations are unchanged.

## Regression tests

All four cases are in `metadata/tests/test_parsing.py` and run against real PostGIS:

| Test parameter | Verified behavior |
| --- | --- |
| `test_deep_json_patch_returns_parse_error_and_preserves_metadata[array]` | Raw PATCH with 100,000 array levels returns generic 400/parse_error. |
| `test_deep_json_patch_returns_parse_error_and_preserves_metadata[object]` | Raw PATCH with 100,000 object levels returns the same generic 400/parse_error. |
| `test_default_form_parsers_still_accept_metadata[form]` | URL-encoded metadata creation remains supported, returning 201 and the real actor. |
| `test_default_form_parsers_still_accept_metadata[multipart]` | Multipart metadata creation remains supported, returning 201 and the real actor. |

The deep payload is constructed as raw bytes rather than recursively encoded by the client. The Python 3.13 native decoder can accept nesting beyond Python's reported recursion limit, so the regression uses a payload that actually reaches its native decoder guard.

Each failed PATCH contains an otherwise valid name/identifier replacement. The test compares complete snapshots of all nine Department/metadata tables before and after, including parent geometry, audit actors/timestamps and active/archived identifier history. Neither the intended record edit nor identifier replacement is saved. The test uses actual HTTP responses rather than mocking a parser exception.

Before the fix, both deep cases returned HTTP 500 and failed; the form/multipart cases passed. After the fix, all four pass. The existing suite also checks successful linked Excel imports, multipart-only 415 behavior, required source/value on PATCH, Department isolation, identifier history and collision rollback.

## Local validation and re-review

On Python 3.13.18, Django 5.2.19 and isolated PostgreSQL 16.15/PostGIS 3.4.6: **387 tests and 18 subtests passed, zero failures**. Dependency/system checks, migrations and `makemigrations --check --dry-run` passed. No shared database was changed.

```sh
python -m pytest -v metadata/tests/test_parsing.py
python -m pytest -v
```

Publish only on the existing PR #27 branch, verify completed GitHub Actions on the resulting head, and provide that commit for re-review. This correction does not merge the PR or represent a reviewer approval.
