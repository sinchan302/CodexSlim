"""Tree-sitter .NET (C#) parser driver."""

from __future__ import annotations

import re
from typing import List, Optional

from codexslim.parsers.base_parser import BaseParser, Symbol

try:
    from tree_sitter_languages import get_parser as ts_get_parser  # type: ignore
    _TS_AVAILABLE = True
except ImportError:
    _TS_AVAILABLE = False


class DotNetParser(BaseParser):
    """Extracts signatures, imports, and docstrings from C# source files."""

    @property
    def language_name(self) -> str:
        return "csharp"

    @property
    def supported_extensions(self) -> List[str]:
        return [".cs"]

    def get_signatures(self, source: str) -> List[Symbol]:
        if _TS_AVAILABLE:
            return self._ts_signatures(source)
        return self._regex_signatures(source)

    def get_imports(self, source: str) -> List[str]:
        if _TS_AVAILABLE:
            return self._ts_imports(source)
        return self._regex_imports(source)

    def _ts_signatures(self, source: str) -> List[Symbol]:
        parser = ts_get_parser("c_sharp")
        tree = parser.parse(source.encode())
        symbols: List[Symbol] = []
        self._walk_for_symbols(tree.root_node, source, symbols, parent=None)
        return symbols

    def _walk_for_symbols(self, node, source: str, symbols: List[Symbol], parent: Optional[str]):
        current_docs = []
        
        for child in node.children:
            if child.type == "comment":
                comment = self._node_text(child, source).strip()
                if comment.startswith("///"):
                    current_docs.append(comment)
                continue
            
            if child.type in ("namespace_declaration", "file_scoped_namespace_declaration"):
                body_node = child.child_by_field_name("body")
                if body_node:
                    self._walk_for_symbols(body_node, source, symbols, parent)
                else:
                    self._walk_for_symbols(child, source, symbols, parent)
                continue
            
            if child.type in ("class_declaration", "interface_declaration", "struct_declaration", "record_declaration"):
                name_node = child.child_by_field_name("name")
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
                    
            elif child.type in ("method_declaration", "constructor_declaration", "property_declaration"):
                name_node = child.child_by_field_name("name")
                fn_name = self._node_text(name_node, source) if name_node else "Unknown"
                
                body_node = child.child_by_field_name("body")
                sig = ""
                if body_node:
                    # Often property bodies or method bodies
                    sig = source[child.start_byte:body_node.start_byte].strip()
                    if child.type == "property_declaration":
                        sig += " { get; set; }"
                    else:
                        sig += " {"
                else:
                    # Look for expression body (=>) or abstract signature
                    sig = source[child.start_byte:child.end_byte].strip()
                    # Strip out => expressions to just leave signature
                    if "=>" in sig:
                        sig = sig.split("=>")[0].strip() + ";"
                    
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
                
            elif child.type == "attribute_list" or child.type == "modifier" or child.type == "declaration_list":
                self._walk_for_symbols(child, source, symbols, parent)
            elif child.is_named and not child.type == "comment":
                # Only strictly reset docs if it's a substantive named node
                current_docs = []
                self._walk_for_symbols(child, source, symbols, parent)

    def _ts_imports(self, source: str) -> List[str]:
        parser = ts_get_parser("c_sharp")
        tree = parser.parse(source.encode())
        imports = []
        def find_usings(node):
            for child in node.children:
                if child.type == "using_directive":
                    imports.append(self._node_text(child, source).strip())
                else:
                    find_usings(child)
                    
        find_usings(tree.root_node)
        return imports

    def _node_text(self, node, source: str) -> str:
        if node is None:
            return ""
        return source[node.start_byte:node.end_byte]

    def _regex_signatures(self, source: str) -> List[Symbol]:
        symbols = []
        class_pattern = re.compile(r'^\s*(?:public|private|protected|internal)?\s*(?:static\s+)?(?:sealed|abstract|partial)?\s+(?:class|interface|struct|record)\s+(\w+).*?{', re.MULTILINE)
        for m in class_pattern.finditer(source):
            symbols.append(Symbol(name=m.group(1), kind="class", signature=m.group(0).strip()))
        return symbols

    def _regex_imports(self, source: str) -> List[str]:
        imports = []
        for line in source.splitlines():
            s = line.strip()
            if s.startswith("using ") and ";" in s:
                imports.append(s)
        return imports
