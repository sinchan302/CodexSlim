"""Tree-sitter Rust parser driver."""

from __future__ import annotations

import re
from typing import List, Optional

from codexslim.parsers.base_parser import BaseParser, Symbol

try:
    from tree_sitter_languages import get_parser as ts_get_parser  # type: ignore
    _TS_AVAILABLE = True
except ImportError:
    _TS_AVAILABLE = False


class RustParser(BaseParser):
    """Extracts signatures, imports, and docstrings from Rust source files."""

    @property
    def language_name(self) -> str:
        return "rust"

    @property
    def supported_extensions(self) -> List[str]:
        return [".rs"]

    def get_signatures(self, source: str) -> List[Symbol]:
        if _TS_AVAILABLE:
            return self._ts_signatures(source)
        return self._regex_signatures(source)

    def get_imports(self, source: str) -> List[str]:
        if _TS_AVAILABLE:
            return self._ts_imports(source)
        return self._regex_imports(source)

    def _ts_signatures(self, source: str) -> List[Symbol]:
        parser = ts_get_parser("rust")
        tree = parser.parse(source.encode())
        symbols: List[Symbol] = []
        self._walk_for_symbols(tree.root_node, source, symbols, parent=None)
        return symbols

    def _walk_for_symbols(self, node, source: str, symbols: List[Symbol], parent: Optional[str]):
        current_docs = []
        
        for child in node.children:
            if child.type == "line_comment" or child.type == "block_comment":
                comment = self._node_text(child, source).strip()
                if comment.startswith("///") or comment.startswith("/**"):
                    current_docs.append(comment)
                continue
                
            if child.type in ("struct_item", "enum_item", "trait_item", "impl_item"):
                name_node = child.child_by_field_name("name")
                
                if child.type == "impl_item":
                    type_node = child.child_by_field_name("type")
                    class_name = self._node_text(type_node, source) if type_node else "Unknown"
                else:
                    class_name = self._node_text(name_node, source) if name_node else "Unknown"
                
                body_node = child.child_by_field_name("body")
                sig = ""
                if body_node:
                    sig = source[child.start_byte:body_node.start_byte].strip() + " {"
                else:
                    sig = source[child.start_byte:child.end_byte].strip()
                    
                doc_str = "\n".join(current_docs) if current_docs else None
                
                symbols.append(Symbol(
                    name=class_name,
                    kind="class",
                    signature=sig,
                    docstring=doc_str,
                    start_line=child.start_point[0],
                    end_line=child.end_point[0],
                ))
                current_docs = []
                
                if body_node:
                    self._walk_for_symbols(body_node, source, symbols, parent=class_name)
                
            elif child.type in ("function_item", "function_signature_item"):
                name_node = child.child_by_field_name("name")
                fn_name = self._node_text(name_node, source) if name_node else "Unknown"
                
                body_node = child.child_by_field_name("body")
                sig = ""
                if body_node:
                    sig = source[child.start_byte:body_node.start_byte].strip() + " {"
                else:
                    sig = source[child.start_byte:child.end_byte].strip()
                    if not sig.endswith(";"):
                        sig += ";"
                    
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
                
            elif child.type == "use_declaration" or child.type == "attribute_item":
                current_docs = []
            elif child.is_named and not child.type == "comment":
                self._walk_for_symbols(child, source, symbols, parent)
                current_docs = []

    def _ts_imports(self, source: str) -> List[str]:
        parser = ts_get_parser("rust")
        tree = parser.parse(source.encode())
        imports = []
        def find_imports(node):
            for child in node.children:
                if child.type == "use_declaration":
                    imports.append(self._node_text(child, source).strip())
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
        type_pattern = re.compile(r'^\s*(?:pub\s+)?(?:struct|enum|trait|impl)\s+([A-Za-z0-9_<>]+).*?{', re.MULTILINE)
        for m in type_pattern.finditer(source):
            symbols.append(Symbol(name=m.group(1), kind="class", signature=m.group(0).strip()))
        return symbols

    def _regex_imports(self, source: str) -> List[str]:
        imports = []
        for line in source.splitlines():
            s = line.strip()
            if s.startswith("use "):
                imports.append(s)
        return imports
