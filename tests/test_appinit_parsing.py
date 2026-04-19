"""Unit tests for embedded curriculum INSERT parsing helpers."""

import pytest

from insightsdsa.appinit import (
    _parse_sql_value_list,
    _table_name,
    _values_paren_content,
    iter_inserts_from_text,
)


def test_values_paren_content_simple():
    sql = (
        "INSERT INTO public.concepts VALUES (1, 'Arrays', '📊') "
        "ON CONFLICT DO NOTHING;"
    )
    inner = _values_paren_content(sql)
    assert "1" in inner and "Arrays" in inner


def test_parse_sql_value_list_strings_null_bool():
    inner = "1, 'O''Reilly', NULL, true, false"
    vals = _parse_sql_value_list(inner)
    assert vals[0] == 1
    assert vals[1] == "O'Reilly"
    assert vals[2] is None
    assert vals[3] is True
    assert vals[4] is False


def test_table_name_public_prefix():
    sql = "INSERT INTO public.questions VALUES (1) ON CONFLICT DO NOTHING;"
    assert _table_name(sql) == "questions"


def test_iter_inserts_from_text():
    body = "INSERT INTO public.concepts VALUES (9, 'T', 'i') ON CONFLICT DO NOTHING;\n"
    stmts = list(iter_inserts_from_text(body))
    assert len(stmts) == 1
    assert "concepts" in stmts[0]


def test_iter_inserts_from_text_rejects_unterminated():
    body = "INSERT INTO public.concepts VALUES (1, 'a', 'b');\n"
    with pytest.raises(ValueError, match="Unterminated"):
        list(iter_inserts_from_text(body))
