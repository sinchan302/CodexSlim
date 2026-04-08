"""Tests for the Ruby parser driver."""

import textwrap

import pytest

from codexslim.parsers.ruby_driver import RubyParser


SAMPLE_SOURCE = textwrap.dedent('''\
    require 'json'
    require_relative 'auth'

    # Represents an authenticated user in the system.
    class User < ActiveRecord::Base
      include Identifiable

      # Returns the ID representing the user.
      def get_id
        @id
      end

      # Validates user credentials.
      def self.authenticate(username, password)
        true
      end
    end

    def login(user)
      puts "Login"
    end
''')


@pytest.fixture
def sample_file(tmp_path):
    f = tmp_path / "sample.rb"
    f.write_text(SAMPLE_SOURCE, encoding="utf-8")
    return f


@pytest.fixture
def parser():
    return RubyParser()


def test_language_name(parser):
    assert parser.language_name == "ruby"


def test_supported_extensions(parser):
    assert ".rb" in parser.supported_extensions


def test_parser_finds_imports(sample_file, parser):
    result = parser.get_parse_result(sample_file)
    assert any("require 'json'" in i for i in result.imports)
    assert any("require_relative 'auth'" in i for i in result.imports)
    assert any("include Identifiable" in i for i in result.imports)


def test_parser_finds_class(sample_file, parser):
    result = parser.get_parse_result(sample_file)
    classes = [s for s in result.symbols if s.kind == "class"]
    assert any(c.name == "User" for c in classes)
    
    user_class = next(c for c in classes if c.name == "User")
    assert "User < ActiveRecord::Base" in user_class.signature


def test_parser_finds_methods_and_functions(sample_file, parser):
    result = parser.get_parse_result(sample_file)
    methods = [s for s in result.symbols if s.kind == "method"]
    functions = [s for s in result.symbols if s.kind == "function"]
    
    assert any(m.name == "get_id" for m in methods)
    assert any(m.name == "authenticate" for m in methods) # singleton method
    assert any(f.name == "login" for f in functions)


def test_parser_preserves_docstrings(sample_file, parser):
    result = parser.get_parse_result(sample_file)
    method_sym = next(s for s in result.symbols if s.name == "get_id")
    assert method_sym.docstring is not None
    assert "Returns the ID representing the user." in method_sym.docstring

    class_sym = next(s for s in result.symbols if s.name == "User")
    assert class_sym.docstring is not None
    assert "Represents an authenticated user in the system." in class_sym.docstring
