from app.graph.nodes import _cited_numbers, _normalize_citations


def test_simple_and_adjacent_citations():
    assert _cited_numbers("Use X [1] and Y [2][3].", 3) == [1, 2, 3]


def test_comma_citation():
    assert _cited_numbers("Both [1, 2] agree.", 3) == [1, 2]


def test_brackets_inside_code_are_not_citations():
    text = "```python\nx = items[0]\n```\nSee [2]. Also `a[1]` is code."
    assert _cited_numbers(text, 3) == [2]


def test_out_of_range_and_non_numeric_brackets_are_ignored():
    assert _cited_numbers("Type [int] and [9].", 3) == []


def test_fullwidth_brackets_are_normalised():
    assert _normalize_citations("Fact 【1】 and 【2】") == "Fact [1] and [2]"