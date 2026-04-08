"""Tests for the Go parser driver."""

import textwrap

import pytest

from codexslim.parsers.go_driver import GoParser


SAMPLE_SOURCE = textwrap.dedent('''\
    package auth

    import (
        "fmt"
        "time"
    )

    // User represents an authenticated entity.
    type User struct {
        ID   int
        Name string
    }

    // GetID returns the ID.
    func (u *User) GetID() int {
        return u.ID
    }

    func Login() {
        fmt.Println("Login")
    }
''')


@pytest.fixture
def sample_file(tmp_path):
    f = tmp_path / "sample.go"
    f.write_text(SAMPLE_SOURCE, encoding="utf-8")
    return f


@pytest.fixture
def parser():
    return GoParser()


def test_language_name(parser):
    assert parser.language_name == "go"


def test_supported_extensions(parser):
    assert ".go" in parser.supported_extensions


def test_parser_finds_imports(sample_file, parser):
    result = parser.get_parse_result(sample_file)
    # The full block string is captured or individual import_spec depending on TS structure.
    # In full block it has "fmt" and "time". 
    assert any("fmt" in i for i in result.imports)


def test_parser_finds_class(sample_file, parser):
    result = parser.get_parse_result(sample_file)
    classes = [s for s in result.symbols if s.kind == "class"]
    assert any(c.name == "User" for c in classes)


def test_parser_finds_methods_and_functions(sample_file, parser):
    result = parser.get_parse_result(sample_file)
    methods = [s for s in result.symbols if s.kind == "method"]
    functions = [s for s in result.symbols if s.kind == "function"]
    
    assert any(m.name == "GetID" for m in methods)
    assert any(f.name == "Login" for f in functions)


def test_parser_preserves_docstrings(sample_file, parser):
    result = parser.get_parse_result(sample_file)
    method_sym = next(s for s in result.symbols if s.name == "GetID")
    assert method_sym.docstring is not None
    assert "GetID returns the ID." in method_sym.docstring

    class_sym = next(s for s in result.symbols if s.name == "User")
    assert class_sym.docstring is not None
    assert "User represents an authenticated entity." in class_sym.docstring
