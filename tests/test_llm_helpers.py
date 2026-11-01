from app.llm import text_of


def test_plain_string_is_unchanged():
    assert text_of("hello") == "hello"


def test_content_blocks_are_flattened_to_text():
    blocks = [{"type": "text", "text": "Hello ", "extras": {"signature": "x"}},
              {"type": "text", "text": "world"}]
    assert text_of(blocks) == "Hello world"


def test_non_text_blocks_are_ignored():
    assert text_of([{"type": "thinking", "thinking": "..."}, {"type": "text", "text": "ok"}]) == "ok"