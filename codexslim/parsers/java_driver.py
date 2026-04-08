"""Tree-sitter Java parser driver."""

from __future__ import annotations

import re
from typing import List, Optional

from codexslim.parsers.base_parser import BaseParser, Symbol

try:
    from tree_sitter_languages import get_parser as ts_get_parser  # type: ignore
    _TS_AVAILABLE = True
except ImportError:
    _TS_AVAILABLE = False


class JavaParser(BaseParser):
    """Extracts signatures, imports, and docstrings from Java source files."""

    @property
    def language_name(self) -> str:
        return "java"

    @property
    def supported_extensions(self) -> List[str]:
        return [".java", ".gradle"]

    def get_signatures(self, source: str) -> List[Symbol]:
        if _TS_AVAILABLE:
            return self._ts_signatures(source)
        return self._regex_signatures(source)

    def get_imports(self, source: str) -> List[str]:
        if _TS_AVAILABLE:
            return self._ts_imports(source)
        return self._regex_imports(source)

    def _ts_signatures(self, source: str) -> List[Symbol]:
        parser = ts_get_parser("java")
        tree = parser.parse(source.encode())
        symbols: List[Symbol] = []
        self._walk_for_symbols(tree.root_node, source, symbols, parent=None)
        return symbols

    def _walk_for_symbols(self, node, source: str, symbols: List[Symbol], parent: Optional[str]):
        current_doc = None
        
        for child in node.children:
            if child.type in ("block_comment", "line_comment"):
                comment = self._node_text(child, source).strip()
                if comment.startswith("/**"):
                    current_doc = comment
                continue
            
            if child.type in ("class_declaration", "interface_declaration", "enum_declaration"):
                name_node = child.child_by_field_name("name")
                class_name = self._node_text(name_node, source) if name_node else "Unknown"
                
                body_node = child.child_by_field_name("body")
                sig = ""
                if body_node:
                    sig = source[child.start_byte:body_node.start_byte].strip() + " {"
                else:
                    sig = source[child.start_byte:child.end_byte].strip()
                
                symbols.append(Symbol(
                    name=class_name,
                    kind="class",
                    signature=sig,
                    docstring=current_doc,
                    start_line=child.start_point[0],
                    end_line=child.end_point[0],
                ))
                current_doc = None
                
                if body_node:
                    self._walk_for_symbols(body_node, source, symbols, parent=class_name)
                    
            elif child.type in ("method_declaration", "constructor_declaration"):
                name_node = child.child_by_field_name("name")
                fn_name = self._node_text(name_node, source) if name_node else "Unknown"
                
                body_node = child.child_by_field_name("body")
                sig = ""
                if body_node:
                    sig = source[child.start_byte:body_node.start_byte].strip() + " {"
                else:
                    sig = source[child.start_byte:child.end_byte].strip()
                    
                symbols.append(Symbol(
                    name=fn_name,
                    kind="method" if parent else "function",
                    signature=sig,
                    docstring=current_doc,
                    start_line=child.start_point[0],
                    end_line=child.end_point[0],
                    parent=parent,
                ))
                current_doc = None

            elif child.type == "modifiers":
                # Do not reset docstring if we encounter modifiers.
                pass
                
            else:
                # Reset docstring for non-declaration statements
                current_doc = None

    def _ts_imports(self, source: str) -> List[str]:
        parser = ts_get_parser("java")
        tree = parser.parse(source.encode())
        imports = []
        for node in tree.root_node.children:
            if node.type == "import_declaration":
                imports.append(self._node_text(node, source).strip())
        return imports

    def _node_text(self, node, source: str) -> str:
        if node is None:
            return ""
        return source[node.start_byte:node.end_byte]

    def _regex_signatures(self, source: str) -> List[Symbol]:
        # Minimal fallback for Java classes
        symbols = []
        class_pattern = re.compile(r'^\s*(?:public|private|protected)?\s*(?:static\s+)?(?:final\s+)?(?:class|interface|enum)\s+(\w+).*?{', re.MULTILINE)
        for m in class_pattern.finditer(source):
            symbols.append(Symbol(name=m.group(1), kind="class", signature=m.group(0).strip()))
        return symbols

    def _regex_imports(self, source: str) -> List[str]:
        imports = []
        for line in source.splitlines():
            s = line.strip()
            if s.startswith("import "):
                imports.append(s)
        return imports
