"""Tree-sitter JS/TS parser driver."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

from codexslim.parsers.base_parser import BaseParser, ParseResult, Symbol

try:
    from tree_sitter_languages import get_parser as ts_get_parser  # type: ignore
    _TS_AVAILABLE = True
except ImportError:
    _TS_AVAILABLE = False


class WebDriver(BaseParser):
    """Extracts signatures, imports, and docstrings from JS and TS files."""

    @property
    def language_name(self) -> str:
        return "javascript" # Generic fallback

    @property
    def supported_extensions(self) -> List[str]:
        return [".js", ".jsx", ".ts", ".tsx"]

    def _get_ts_lang(self, source_or_path="") -> str:
        """Determines whether to use javascript or typescript parser."""
        # A bit hacky if we only have source, but we default to ts since it parses JS fine
        return "typescript"

    def get_parse_result(self, file_path: Path) -> ParseResult:
        """Override to dynamically set language based on extension."""
        lang = "typescript" if file_path.suffix in (".ts", ".tsx") else "javascript"
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
            imports = self._get_imports_with_lang(source, lang)
            symbols = self._get_signatures_with_lang(source, lang)
        except Exception as e:
            return ParseResult(file_path=file_path, language=lang, errors=[str(e)])
            
        return ParseResult(
            file_path=file_path,
            language=lang,
            imports=imports,
            symbols=symbols,
        )

    def get_signatures(self, source: str) -> List[Symbol]:
        return self._get_signatures_with_lang(source, "typescript")
        
    def _get_signatures_with_lang(self, source: str, lang: str) -> List[Symbol]:
        if _TS_AVAILABLE:
            return self._ts_signatures(source, lang)
        return self._regex_signatures(source)

    def get_imports(self, source: str) -> List[str]:
        return self._get_imports_with_lang(source, "typescript")

    def _get_imports_with_lang(self, source: str, lang: str) -> List[str]:
        if _TS_AVAILABLE:
            return self._ts_imports(source, lang)
        return self._regex_imports(source)

    def _ts_signatures(self, source: str, lang: str) -> List[Symbol]:
        # Note: 'typescript' or 'tsx' parser depending on exact flavor?
        # Tree-sitter 'typescript' handles basic TS, let's just use typescript
        parser = ts_get_parser("typescript" if lang == "typescript" else "javascript")
        tree = parser.parse(source.encode())
        symbols: List[Symbol] = []
        self._walk_for_symbols(tree.root_node, source, symbols, parent=None)
        return symbols

    def _walk_for_symbols(self, node, source: str, symbols: List[Symbol], parent: Optional[str]):
        current_docs = []
        
        for child in node.children:
            if child.type == "comment":
                comment = self._node_text(child, source).strip()
                if comment.startswith("/**"):
                    current_docs.append(comment)
                continue
                
            if child.type == "export_statement":
                # Export statements wrap declarations. 
                declaration_node = child.child_by_field_name("declaration")
                if declaration_node:
                    # Map the docstring to the declaration
                    self._walk_for_symbols_node(declaration_node, source, symbols, parent, current_docs)
                else:
                    self._walk_for_symbols(child, source, symbols, parent)
                current_docs = []
                continue
                
            self._walk_for_symbols_node(child, source, symbols, parent, current_docs)
            if child.is_named and child.type != "comment":
                current_docs = []

    def _walk_for_symbols_node(self, child, source: str, symbols: List[Symbol], parent: Optional[str], current_docs: List[str]):
        if child.type in ("class_declaration", "interface_declaration"):
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
            
            if body_node:
                self._walk_for_symbols(body_node, source, symbols, parent=class_name)
                
        elif child.type in ("function_declaration", "method_definition"):
            name_node = child.child_by_field_name("name")
            fn_name = self._node_text(name_node, source) if name_node else "Unknown"
            
            body_node = child.child_by_field_name("body")
            sig = ""
            if body_node:
                sig = source[child.start_byte:body_node.start_byte].strip() + " {"
            else:
                sig = source[child.start_byte:child.end_byte].strip()
                
            doc_str = "\n".join(current_docs) if current_docs else None
            
            symbols.append(Symbol(
                name=fn_name,
                kind="method" if "method" in child.type or parent else "function",
                signature=sig,
                docstring=doc_str,
                start_line=child.start_point[0],
                end_line=child.end_point[0],
                parent=parent,
            ))
            
        elif child.type in ("lexical_declaration", "variable_declaration"):
            # Handle export const foo = () => {}
            # Simplified out for v1
            pass
            
        elif child.type == "export_statement":
            decl_node = child.child_by_field_name("declaration")
            if decl_node:
                self._walk_for_symbols_node(decl_node, source, symbols, parent, current_docs)
            else:
                self._walk_for_symbols(child, source, symbols, parent)

    def _ts_imports(self, source: str, lang: str) -> List[str]:
        parser = ts_get_parser("typescript" if lang == "typescript" else "javascript")
        tree = parser.parse(source.encode())
        imports = []
        for node in tree.root_node.children:
            if node.type == "import_statement" or (node.type == "export_statement" and "from" in self._node_text(node, source)):
                imports.append(self._node_text(node, source).strip())
        return imports

    def _node_text(self, node, source: str) -> str:
        if node is None:
            return ""
        return source[node.start_byte:node.end_byte]

    def _regex_signatures(self, source: str) -> List[Symbol]:
        symbols = []
        class_pattern = re.compile(r'^\s*(?:export\s+)?(?:default\s+)?(?:class|interface)\s+(\w+).*?{', re.MULTILINE)
        for m in class_pattern.finditer(source):
            symbols.append(Symbol(name=m.group(1), kind="class", signature=m.group(0).strip()))
        return symbols

    def _regex_imports(self, source: str) -> List[str]:
        imports = []
        for line in source.splitlines():
            s = line.strip()
            if s.startswith("import ") or (s.startswith("export ") and "from" in s):
                imports.append(s)
        return imports
