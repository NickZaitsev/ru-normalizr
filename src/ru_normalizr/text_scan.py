from __future__ import annotations


def first_non_whitespace_index(text: str, start: int) -> tuple[int, bool]:
    """Return the first non-whitespace position and whether a newline was seen.

    This is the positional equivalent of ``text[start:].lstrip()``. Keeping
    the original string and advancing an index avoids copying the entire
    remaining document from every regular-expression callback.
    """

    index = start
    saw_newline = False
    while index < len(text) and text[index].isspace():
        saw_newline = saw_newline or text[index] == "\n"
        index += 1
    return index, saw_newline
