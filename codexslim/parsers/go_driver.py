"""Tree-sitter Go parser driver."""

from __future__ import annotations

import re
from typing import List, Optional

from codexslim.parsers.base_parser import BaseParser, Symbol

try:
    from tree_sitter_languages import get_parser as ts_get_parser  # type: ignore
    _TS_AVAILABLE = True
except ImportError:
    _TS_AVAILABLE = False


class GoParser(BaseParser):
    """Extracts signatures, imports, and docstrings from Go source files."""

    @property
    def language_name(self) -> str:
        return "go"

    @property
    def supported_extensions(self) -> List[str]:
        return [".go"]

    def get_signatures(self, source: str) -> List[Symbol]:
        if _TS_AVAILABLE:
            return self._ts_signatures(source)
        return self._regex_signatures(source)

    def get_imports(self, source: str) -> List[str]:
        if _TS_AVAILABLE:
            return self._ts_imports(source)
        return self._regex_imports(source)

    def _ts_signatures(self, source: str) -> List[Symbol]:
        parser = ts_get_parser("go")
        tree = parser.parse(source.encode())
        symbols: List[Symbol] = []
        self._walk_for_symbols(tree.root_node, source, symbols, parent=None)
        return symbols

    def _walk_for_symbols(self, node, source: str, symbols: List[Symbol], parent: Optional[str]):
        current_docs = []
        
        for child in node.children:
            if child.type == "comment":
                comment = self._node_text(child, source).strip()
                if comment.startswith("//"):
                    current_docs.append(comment)
                continue
                
            if child.type == "type_declaration":
                # Go type_declaration can have multiple specs
                for type_spec in child.children:
                    if type_spec.type == "type_spec":
                        name_node = type_spec.child_by_field_name("name")
                        class_name = self._node_text(name_node, source) if name_node else "Unknown"
                        
                        type_node = type_spec.child_by_field_name("type")
                        
                        sig = "type " + class_name
                        if type_node:
                            # Use type struct { ... or type interface { ...
                            type_txt = self._node_text(type_node, source)
                            if "struct" in type_txt:
                                sig += " struct {"
                            elif "interface" in type_txt:
                                sig += " interface {"
                            else:
                                sig += " " + type_txt
                        else:
                            sig += " {"
                            
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
                
            elif child.type in ("function_declaration", "method_declaration"):
                name_node = child.child_by_field_name("name")
                fn_name = self._node_text(name_node, source) if name_node else "Unknown"
                
                body_node = child.child_by_field_name("body")
                sig = ""
                if body_node:
                    sig = source[child.start_byte:body_node.start_byte].strip() + " {"
                else:
                    sig = source[child.start_byte:child.end_byte].strip()
                    
                doc_str = "\n".join(current_docs) if current_docs else None
                kind = "method" if child.type == "method_declaration" else "function"
                
                symbols.append(Symbol(
                    name=fn_name,
                    kind=kind,
                    signature=sig,
                    docstring=doc_str,
                    start_line=child.start_point[0],
                    end_line=child.end_point[0],
                    parent=None,
                ))
                current_docs = []
                
            elif child.type == "package_clause" or child.type == "import_declaration":
                current_docs = []
            elif child.is_named and not child.type == "comment":
                self._walk_for_symbols(child, source, symbols, parent)
                current_docs = []

    def _ts_imports(self, source: str) -> List[str]:
        parser = ts_get_parser("go")
        tree = parser.parse(source.encode())
        imports = []
        def find_imports(node):
            for child in node.children:
                if child.type == "import_declaration":
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
        type_pattern = re.compile(r'^\s*type\s+(\w+)\s+(?:struct|interface)\s*{', re.MULTILINE)
        for m in type_pattern.finditer(source):
            symbols.append(Symbol(name=m.group(1), kind="class", signature=m.group(0).strip()))
        return symbols

    def _regex_imports(self, source: str) -> List[str]:
        imports = []
        for line in source.splitlines():
            s = line.strip()
            if s.startswith("import "):
                imports.append(s)
        return imports
