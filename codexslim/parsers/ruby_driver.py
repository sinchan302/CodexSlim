"""Tree-sitter Ruby parser driver."""

from __future__ import annotations

import re
from typing import List, Optional

from codexslim.parsers.base_parser import BaseParser, Symbol

try:
    from tree_sitter_languages import get_parser as ts_get_parser  # type: ignore
    _TS_AVAILABLE = True
except ImportError:
    _TS_AVAILABLE = False


class RubyParser(BaseParser):
    """Extracts signatures, imports, and docstrings from Ruby source files."""

    @property
    def language_name(self) -> str:
        return "ruby"

    @property
    def supported_extensions(self) -> List[str]:
        return [".rb"]

    def get_signatures(self, source: str) -> List[Symbol]:
        if _TS_AVAILABLE:
            return self._ts_signatures(source)
        return self._regex_signatures(source)

    def get_imports(self, source: str) -> List[str]:
        if _TS_AVAILABLE:
            return self._ts_imports(source)
        return self._regex_imports(source)

    def _ts_signatures(self, source: str) -> List[Symbol]:
        parser = ts_get_parser("ruby")
        tree = parser.parse(source.encode())
        symbols: List[Symbol] = []
        self._walk_for_symbols(tree.root_node, source, symbols, parent=None)
        return symbols

    def _walk_for_symbols(self, node, source: str, symbols: List[Symbol], parent: Optional[str]):
        current_docs = []
        
        for child in node.children:
            if child.type == "comment":
                comment = self._node_text(child, source).strip()
                if comment.startswith("#"):
                    current_docs.append(comment)
                continue
                
            if child.type in ("class", "module"):
                name_node = child.child_by_field_name("name")
                class_name = self._node_text(name_node, source) if name_node else "Unknown"
                
                sig = f"{child.type} {class_name}"
                superclass_node = child.child_by_field_name("superclass")
                if superclass_node:
                    sig += f" {self._node_text(superclass_node, source)}"
                    
                doc_str = "\n".join(current_docs) if current_docs else None
                
                symbols.append(Symbol(
                    name=class_name,
                    kind="class" if child.type == "class" else "module",
                    signature=sig,
                    docstring=doc_str,
                    start_line=child.start_point[0],
                    end_line=child.end_point[0],
                ))
                current_docs = []
                
                self._walk_for_symbols(child, source, symbols, parent=class_name)
                
            elif child.type in ("method", "singleton_method"):
                name_node = child.child_by_field_name("name")
                fn_name = self._node_text(name_node, source) if name_node else "Unknown"
                
                parameters_node = child.child_by_field_name("parameters")
                sig = "def "
                if child.type == "singleton_method":
                    object_node = child.child_by_field_name("object")
                    if object_node:
                        sig += self._node_text(object_node, source) + "."
                
                sig += fn_name
                if parameters_node:
                    sig += self._node_text(parameters_node, source)
                    
                doc_str = "\n".join(current_docs) if current_docs else None
                
                symbols.append(Symbol(
                    name=fn_name,
                    kind="method" if parent else "function",
                    signature=sig,
                    docstring=doc_str,
                    start_line=child.start_point[0],
                    end_line=child.end_point[0],
                    parent=parent,
                ))
                current_docs = []
                
            elif child.type == "call":
                method_name = self._node_text(child.child_by_field_name("method"), source)
                if method_name in ("require", "require_relative", "include", "extend"):
                    current_docs = []
                else:
                    self._walk_for_symbols(child, source, symbols, parent)
                    current_docs = []
                    
            elif child.is_named and not child.type == "comment":
                self._walk_for_symbols(child, source, symbols, parent)
                current_docs = []

    def _ts_imports(self, source: str) -> List[str]:
        parser = ts_get_parser("ruby")
        tree = parser.parse(source.encode())
        imports = []
        def find_imports(node):
            for child in node.children:
                if child.type == "call":
                    method = child.child_by_field_name("method")
                    if method and self._node_text(method, source) in ("require", "require_relative", "include", "extend"):
                        imports.append(self._node_text(child, source).strip())
                    else:
                        find_imports(child)
                elif child.is_named:
                    find_imports(child)
                    
        find_imports(tree.root_node)
        return imports

    def _node_text(self, node, source: str) -> str:
        if node is None:
            return ""
        return source[node.start_byte:node.end_byte]

    def _regex_signatures(self, source: str) -> List[Symbol]:
        symbols = []
        type_pattern = re.compile(r'^\s*(?:class|module)\s+([A-Za-z0-9_:]+).*?$', re.MULTILINE)
        for m in type_pattern.finditer(source):
            symbols.append(Symbol(name=m.group(1), kind="class", signature=m.group(0).strip()))
        return symbols

    def _regex_imports(self, source: str) -> List[str]:
        imports = []
        for line in source.splitlines():
            s = line.strip()
            if s.startswith("require ") or s.startswith("include "):
                imports.append(s)
        return imports
