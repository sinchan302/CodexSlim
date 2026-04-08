"""Tests for the Python parser driver."""

import textwrap

import pytest

from codexslim.parsers.python_driver import PythonParser
from codexslim.filters.skeletonizer import Skeletonizer


SAMPLE_SOURCE = textwrap.dedent('''\
    """Module docstring."""

    import os
    from pathlib import Path

    class Calculator:
        """A simple calculator."""

        def add(self, a: int, b: int) -> int:
            """Return a + b."""
            return a + b

        def subtract(self, a: int, b: int) -> int:
            """Return a - b."""
            return a - b

    def standalone(value: float) -> float:
        """A standalone function."""
        return value * 2
''')


@pytest.fixture
def sample_file(tmp_path):
    f = tmp_path / "sample.py"
    f.write_text(SAMPLE_SOURCE, encoding="utf-8")
    return f


@pytest.fixture
def parser():
    return PythonParser()


@pytest.fixture
def skeletonizer():
    return Skeletonizer()


def test_language_name(parser):
    assert parser.language_name == "python"


def test_supported_extensions(parser):
    assert ".py" in parser.supported_extensions


def test_parser_finds_imports(sample_file, parser):
    result = parser.get_parse_result(sample_file)
    assert any("import os" in i for i in result.imports)
    assert any("pathlib" in i for i in result.imports)


def test_parser_finds_class(sample_file, parser):
    result = parser.get_parse_result(sample_file)
    classes = [s for s in result.symbols if s.kind == "class"]
    assert any(c.name == "Calculator" for c in classes)


def test_parser_finds_methods(sample_file, parser):
    result = parser.get_parse_result(sample_file)
    methods = [s for s in result.symbols if s.kind == "method"]
    names = {m.name for m in methods}
    assert "add" in names
    assert "subtract" in names


def test_parser_preserves_docstrings(sample_file, parser):
    result = parser.get_parse_result(sample_file)
    add_sym = next(s for s in result.symbols if s.name == "add")
    assert add_sym.docstring is not None
    assert "Return a + b" in add_sym.docstring


def test_no_parse_errors(sample_file, parser):
    result = parser.get_parse_result(sample_file)
    assert result.errors == []


def test_skeletonizer_removes_body(sample_file, parser, skeletonizer):
    result = parser.get_parse_result(sample_file)
    slim = skeletonizer.skeletonize(result)
    assert "return a + b" not in slim
    assert "..." in slim


def test_skeletonizer_keeps_signatures(sample_file, parser, skeletonizer):
    result = parser.get_parse_result(sample_file)
    slim = skeletonizer.skeletonize(result)
    assert "def add" in slim


def test_skeletonizer_keeps_docstrings(sample_file, parser, skeletonizer):
    result = parser.get_parse_result(sample_file)
    slim = skeletonizer.skeletonize(result)
    assert "Return a + b" in slim
