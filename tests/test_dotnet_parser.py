"""Tests for the .NET parser driver."""

import textwrap

import pytest

from codexslim.parsers.dotnet_driver import DotNetParser


SAMPLE_SOURCE = textwrap.dedent('''\
    using System;
    using System.Collections.Generic;

    namespace Project.Web {
        /// <summary>
        /// A simple calculator API in C#.
        /// </summary>
        public class Calculator {

            /// <summary>Return a + b.</summary>
            public int Add(int a, int b) {
                return a + b;
            }

            public int Subtract(int a, int b) => a - b;
            
            public int Value { get; set; }
        }
    }
''')


@pytest.fixture
def sample_file(tmp_path):
    f = tmp_path / "sample.cs"
    f.write_text(SAMPLE_SOURCE, encoding="utf-8")
    return f


@pytest.fixture
def parser():
    return DotNetParser()


def test_language_name(parser):
    assert parser.language_name == "csharp"


def test_supported_extensions(parser):
    assert ".cs" in parser.supported_extensions


def test_parser_finds_imports(sample_file, parser):
    result = parser.get_parse_result(sample_file)
    assert any("using System;" in i for i in result.imports)
    assert any("using System.Collections.Generic;" in i for i in result.imports)


def test_parser_finds_class(sample_file, parser):
    result = parser.get_parse_result(sample_file)
    classes = [s for s in result.symbols if s.kind == "class"]
    assert any(c.name == "Calculator" for c in classes)


def test_parser_finds_methods(sample_file, parser):
    result = parser.get_parse_result(sample_file)
    methods = [s for s in result.symbols if s.kind == "method"]
    names = {m.name for m in methods}
    assert "Add" in names
    assert "Subtract" in names
    assert "Value" in names


def test_parser_preserves_docstrings(sample_file, parser):
    result = parser.get_parse_result(sample_file)
    add_sym = next(s for s in result.symbols if s.name == "Add")
    assert add_sym.docstring is not None
    assert "Return a + b." in add_sym.docstring

    class_sym = next(s for s in result.symbols if s.name == "Calculator")
    assert class_sym.docstring is not None
    assert "A simple calculator API in C#." in class_sym.docstring
