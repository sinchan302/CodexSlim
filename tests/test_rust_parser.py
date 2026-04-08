"""Tests for the Rust parser driver."""

import textwrap

import pytest

from codexslim.parsers.rust_driver import RustParser


SAMPLE_SOURCE = textwrap.dedent('''\
    use std::collections::HashMap;
    use std::io::{self, Read};

    /// Represents an authenticated user.
    pub struct User {
        id: i32,
        name: String,
    }

    impl User {
        /// Returns the ID of the user.
        pub fn get_id(&self) -> i32 {
            self.id
        }
    }

    pub trait Identifiable {
        fn id(&self) -> i32;
    }

    fn login() {
        println!("Login");
    }
''')


@pytest.fixture
def sample_file(tmp_path):
    f = tmp_path / "sample.rs"
    f.write_text(SAMPLE_SOURCE, encoding="utf-8")
    return f


@pytest.fixture
def parser():
    return RustParser()


def test_language_name(parser):
    assert parser.language_name == "rust"


def test_supported_extensions(parser):
    assert ".rs" in parser.supported_extensions


def test_parser_finds_imports(sample_file, parser):
    result = parser.get_parse_result(sample_file)
    assert any("use std::collections::HashMap;" in i for i in result.imports)
    assert any("use std::io::{self, Read};" in i for i in result.imports)


def test_parser_finds_class_and_trait(sample_file, parser):
    result = parser.get_parse_result(sample_file)
    classes = [s for s in result.symbols if s.kind == "class"]
    assert any(c.name == "User" for c in classes)
    assert any(c.name == "Identifiable" for c in classes)
    # The impl_item also creates a class named User
    assert len([c for c in classes if c.name == "User"]) == 2


def test_parser_finds_methods_and_functions(sample_file, parser):
    result = parser.get_parse_result(sample_file)
    methods = [s for s in result.symbols if s.kind == "method"]
    functions = [s for s in result.symbols if s.kind == "function"]
    
    assert any(m.name == "get_id" for m in methods)
    assert any(m.name == "id" for m in methods)
    assert any(f.name == "login" for f in functions)


def test_parser_preserves_docstrings(sample_file, parser):
    result = parser.get_parse_result(sample_file)
    method_sym = next(s for s in result.symbols if s.name == "get_id")
    assert method_sym.docstring is not None
    assert "Returns the ID of the user." in method_sym.docstring

    class_sym = next(s for s in result.symbols if s.name == "User")
    assert class_sym.docstring is not None
    assert "Represents an authenticated user." in class_sym.docstring
