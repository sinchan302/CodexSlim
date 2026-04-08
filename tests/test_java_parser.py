"""Tests for the Java parser driver."""

import textwrap

import pytest

from codexslim.parsers.java_driver import JavaParser


SAMPLE_SOURCE = textwrap.dedent('''\
    package com.example;

    import java.util.List;
    import java.util.Map;

    /**
     * A simple calculator API.
     */
    public class Calculator {

        /**
         * Return a + b.
         */
        public int add(int a, int b) {
            return a + b;
        }

        public int subtract(int a, int b) {
            return a - b;
        }
    }
''')


@pytest.fixture
def sample_file(tmp_path):
    f = tmp_path / "sample.java"
    f.write_text(SAMPLE_SOURCE, encoding="utf-8")
    return f


@pytest.fixture
def parser():
    return JavaParser()


def test_language_name(parser):
    assert parser.language_name == "java"


def test_supported_extensions(parser):
    assert ".java" in parser.supported_extensions


def test_parser_finds_imports(sample_file, parser):
    result = parser.get_parse_result(sample_file)
    assert any("import java.util.List;" in i for i in result.imports)


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
    assert "Return a + b." in add_sym.docstring

    class_sym = next(s for s in result.symbols if s.name == "Calculator")
    assert class_sym.docstring is not None
    assert "A simple calculator API." in class_sym.docstring
