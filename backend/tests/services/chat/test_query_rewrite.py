"""Tests for _parse_rewrite_response with related queries.

Imported straight from `app.services.chat.query_rewrite`, not from the `chat`
package: the mirror says this file covers that module, and importing through the
re-export would leave nothing in the file naming what it exercises.
"""

from app.services.chat.query_rewrite import _parse_rewrite_response


class TestParseRewriteResponse:
    def test_full_json_with_related(self) -> None:
        raw = '{"query": "semelles filantes béton", "related": ["fond de fouille terrassement", "gros béton propreté"], "scope": "specific", "structured": "table", "schema": "schema"}'
        query, related, scope, structured, schema = _parse_rewrite_response(raw)
        assert query == "semelles filantes béton"
        assert related == ["fond de fouille terrassement", "gros béton propreté"]
        assert scope == "specific"
        assert structured == "table"
        assert schema == "schema"

    def test_json_without_related(self) -> None:
        raw = '{"query": "isolation murs", "scope": "specific", "structured": "none", "schema": "none"}'
        query, related, scope, structured, schema = _parse_rewrite_response(raw)
        assert query == "isolation murs"
        assert related == []
        assert scope == "specific"

    def test_json_with_empty_related(self) -> None:
        raw = '{"query": "lots du projet", "related": [], "scope": "broad", "structured": "none", "schema": "none"}'
        query, related, scope, structured, schema = _parse_rewrite_response(raw)
        assert query == "lots du projet"
        assert related == []
        assert scope == "broad"

    def test_related_max_2(self) -> None:
        raw = '{"query": "test", "related": ["a", "b", "c", "d"], "scope": "specific", "structured": "none", "schema": "none"}'
        _, related, _, _, _ = _parse_rewrite_response(raw)
        assert len(related) == 2

    def test_related_strips_whitespace(self) -> None:
        raw = '{"query": "test", "related": ["  foo  ", "  bar  "], "scope": "specific", "structured": "none", "schema": "none"}'
        _, related, _, _, _ = _parse_rewrite_response(raw)
        assert related == ["foo", "bar"]

    def test_related_filters_empty_strings(self) -> None:
        raw = '{"query": "test", "related": ["valid", "", "  "], "scope": "specific", "structured": "none", "schema": "none"}'
        _, related, _, _, _ = _parse_rewrite_response(raw)
        assert related == ["valid"]

    def test_related_non_list_ignored(self) -> None:
        raw = '{"query": "test", "related": "not a list", "scope": "specific", "structured": "none", "schema": "none"}'
        _, related, _, _, _ = _parse_rewrite_response(raw)
        assert related == []

    def test_fallback_raw_string(self) -> None:
        raw = "not valid json at all"
        query, related, scope, structured, schema = _parse_rewrite_response(raw)
        assert query == raw
        assert related == []
        assert scope == "specific"
        assert structured == "none"
        assert schema == "none"

    def test_markdown_code_fences_stripped(self) -> None:
        raw = '```json\n{"query": "test query", "related": ["rel1"], "scope": "specific", "structured": "none", "schema": "none"}\n```'
        query, related, scope, _, _ = _parse_rewrite_response(raw)
        assert query == "test query"
        assert related == ["rel1"]

    def test_invalid_scope_defaults_specific(self) -> None:
        raw = '{"query": "test", "scope": "invalid", "structured": "none", "schema": "none"}'
        _, _, scope, _, _ = _parse_rewrite_response(raw)
        assert scope == "specific"

    def test_invalid_structured_defaults_none(self) -> None:
        raw = '{"query": "test", "scope": "specific", "structured": "invalid", "schema": "none"}'
        _, _, _, structured, _ = _parse_rewrite_response(raw)
        assert structured == "none"
