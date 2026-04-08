"""Tests for the JS/TS parser driver."""

import textwrap

import pytest

from codexslim.parsers.web_driver import WebDriver


SAMPLE_SOURCE = textwrap.dedent('''\
    import { something } from 'module';
    export * from 'other';

    /**
     * A simple API in TS.
     */
    export class Calculator {

        /** Return a + b. */
        add(a: number, b: number): number {
            return a + b;
        }

        subtract(a: number, b: number): number {
            return a - b;
        }
    }
    
    /** Standalone */
    export function multiply(a, b) {
        return a * b;
    }
''')


@pytest.fixture
def sample_file(tmp_path):
    f = tmp_path / "sample.ts"
    f.write_text(SAMPLE_SOURCE, encoding="utf-8")
    return f


@pytest.fixture
def parser():
    return WebDriver()


def test_language_name(parser):
    assert parser.language_name == "javascript"


def test_supported_extensions(parser):
    assert ".ts" in parser.supported_extensions
    assert ".js" in parser.supported_extensions


def test_parser_finds_imports(sample_file, parser):
    result = parser.get_parse_result(sample_file)
    assert any("import { something } from 'module';" in i for i in result.imports)


def test_parser_finds_class(sample_file, parser):
    result = parser.get_parse_result(sample_file)
    classes = [s for s in result.symbols if s.kind == "class"]
    assert any(c.name == "Calculator" for c in classes)


def test_parser_finds_methods_and_functions(sample_file, parser):
    result = parser.get_parse_result(sample_file)
    methods = [s for s in result.symbols if s.kind == "method"]
    functions = [s for s in result.symbols if s.kind == "function"]
    
    assert any(m.name == "add" for m in methods)
    assert any(m.name == "subtract" for m in methods)
    assert any(f.name == "multiply" for f in functions)


def test_parser_preserves_docstrings(sample_file, parser):
    result = parser.get_parse_result(sample_file)
    add_sym = next(s for s in result.symbols if s.name == "add")
    assert add_sym.docstring is not None
    assert "Return a + b." in add_sym.docstring

    class_sym = next(s for s in result.symbols if s.name == "Calculator")
    assert class_sym.docstring is not None
    assert "A simple API in TS." in class_sym.docstring
