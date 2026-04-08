"""Tree-sitter Python parser driver."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import List, Optional

from codexslim.parsers.base_parser import BaseParser, ParseResult, Symbol

try:
    from tree_sitter_languages import get_parser as ts_get_parser  # type: ignore
    _TS_AVAILABLE = True
except ImportError:
    _TS_AVAILABLE = False


class PythonParser(BaseParser):
    """Extracts signatures, imports, and docstrings from Python source files."""

    @property
    def language_name(self) -> str:
        return "python"

    @property
    def supported_extensions(self) -> List[str]:
        return [".py"]

    def get_signatures(self, source: str) -> List[Symbol]:
        if _TS_AVAILABLE:
            return self._ts_signatures(source)
        return self._regex_signatures(source)

    def get_imports(self, source: str) -> List[str]:
        if _TS_AVAILABLE:
            return self._ts_imports(source)
        return self._regex_imports(source)

    def get_parse_result(self, file_path: Path) -> ParseResult:
        result = super().get_parse_result(file_path)
        source = file_path.read_text(encoding="utf-8", errors="replace")
        result.module_docstring = self._extract_module_docstring(source)
        return result

    def _ts_signatures(self, source: str) -> List[Symbol]:
        parser = ts_get_parser("python")
        tree = parser.parse(source.encode())
        symbols: List[Symbol] = []
        self._walk_for_symbols(tree.root_node, source, symbols, parent=None)
        return symbols

    def _walk_for_symbols(self, node, source: str, symbols: List[Symbol], parent: Optional[str]):
        for child in node.children:
            if child.type == "class_definition":
                class_name = self._node_text(child.child_by_field_name("name"), source)
                decorators = self._collect_decorators(child, source)
                body_node = child.child_by_field_name("body")
                docstring = self._extract_docstring_from_body(body_node, source)
                bases_node = child.child_by_field_name("superclasses")
                bases = f"({self._node_text(bases_node, source)})" if bases_node else ""
                sig = f"class {class_name}{bases}:"
                symbols.append(Symbol(
                    name=class_name, kind="class", signature=sig,
                    docstring=docstring, decorators=decorators,
                    start_line=child.start_point[0], end_line=child.end_point[0],
                ))
                if body_node:
                    self._walk_for_symbols(body_node, source, symbols, parent=class_name)

            elif child.type in ("function_definition", "async_function_definition"):
                fn_name = self._node_text(child.child_by_field_name("name"), source)
                params_node = child.child_by_field_name("parameters")
                params = self._node_text(params_node, source) if params_node else "()"
                ret_node = child.child_by_field_name("return_type")
                ret = f" -> {self._node_text(ret_node, source)}" if ret_node else ""
                decorators = self._collect_decorators(child, source)
                body_node = child.child_by_field_name("body")
                docstring = self._extract_docstring_from_body(body_node, source)
                prefix = "async def" if child.type == "async_function_definition" else "def"
                sig = f"{prefix} {fn_name}{params}{ret}:"
                symbols.append(Symbol(
                    name=fn_name,
                    kind="method" if parent else "function",
                    signature=sig, docstring=docstring, decorators=decorators,
                    start_line=child.start_point[0], end_line=child.end_point[0],
                    parent=parent,
                ))
            else:
                self._walk_for_symbols(child, source, symbols, parent)

    def _ts_imports(self, source: str) -> List[str]:
        parser = ts_get_parser("python")
        tree = parser.parse(source.encode())
        imports = []
        for node in tree.root_node.children:
            if node.type in ("import_statement", "import_from_statement"):
                imports.append(self._node_text(node, source).strip())
        return imports

    def _node_text(self, node, source: str) -> str:
        if node is None:
            return ""
        return source[node.start_byte:node.end_byte]

    def _collect_decorators(self, node, source: str) -> List[str]:
        decorators: List[str] = []
        parent = node.parent
        if parent is None:
            return decorators
        idx = list(parent.children).index(node)
        for sibling in reversed(parent.children[:idx]):
            if sibling.type == "decorator":
                decorators.insert(0, self._node_text(sibling, source).strip())
            else:
                break
        return decorators

    def _extract_docstring_from_body(self, body_node, source: str) -> Optional[str]:
        if body_node is None:
            return None
        for child in body_node.children:
            if child.type == "expression_statement":
                for subchild in child.children:
                    if subchild.type in ("string", "concatenated_string"):
                        raw = self._node_text(subchild, source)
                        return textwrap.dedent(raw).strip()
        return None

    def _extract_module_docstring(self, source: str) -> Optional[str]:
        if not _TS_AVAILABLE:
            return None
        parser = ts_get_parser("python")
        tree = parser.parse(source.encode())
        for node in tree.root_node.children:
            if node.type == "expression_statement":
                for child in node.children:
                    if child.type in ("string", "concatenated_string"):
                        return self._node_text(child, source).strip()
            elif node.type not in ("comment", "newline"):
                break
        return None

    def _regex_signatures(self, source: str) -> List[Symbol]:
        import re
        symbols = []
        pattern = re.compile(
            r'^\s*(?P<async>async\s+)?def\s+(?P<name>\w+)\s*(?P<params>\([^)]*\))'
            r'(?:\s*->\s*(?P<ret>[^\n:]+))?',
            re.MULTILINE,
        )
        for m in pattern.finditer(source):
            name = m.group("name")
            params = m.group("params")
            ret = f" -> {m.group('ret').strip()}" if m.group("ret") else ""
            prefix = "async def" if m.group("async") else "def"
            sig = f"{prefix} {name}{params}{ret}:"
            symbols.append(Symbol(name=name, kind="function", signature=sig))
        return symbols

    def _regex_imports(self, source: str) -> List[str]:
        imports = []
        for line in source.splitlines():
            s = line.strip()
            if s.startswith("import ") or s.startswith("from "):
                imports.append(s)
        return imports
