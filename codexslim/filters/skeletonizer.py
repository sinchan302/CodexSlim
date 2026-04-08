"""
Skeletonizer — converts a ParseResult into a slim source string.
"""

from __future__ import annotations

from typing import List, Optional

from codexslim.parsers.base_parser import ParseResult, Symbol


class Skeletonizer:
    """Reconstructs a slim source file from a ParseResult."""

    INDENT = "    "

    def skeletonize(self, result: ParseResult) -> str:
        lines: List[str] = []

        if result.module_docstring:
            lines.append(result.module_docstring)
            lines.append("")

        if result.imports:
            lines.extend(result.imports)
            lines.append("")

        current_class: Optional[str] = None

        for symbol in result.symbols:
            if symbol.kind == "class":
                if current_class is not None:
                    lines.append("")
                current_class = symbol.name
                lines.extend(self._render_class(symbol))
            elif symbol.kind in ("function", "method"):
                indent = self.INDENT if symbol.parent else ""
                lines.extend(self._render_function(symbol, indent))
                lines.append("")

        while lines and lines[-1] == "":
            lines.pop()

        return "\n".join(lines) + "\n"

    def _render_class(self, symbol: Symbol) -> List[str]:
        lines: List[str] = []
        for dec in symbol.decorators:
            lines.append(dec)
        lines.append(symbol.signature)
        if symbol.docstring:
            for doc_line in symbol.docstring.splitlines():
                lines.append(f"{self.INDENT}{doc_line}")
        lines.append("")
        return lines

    def _render_function(self, symbol: Symbol, indent: str) -> List[str]:
        lines: List[str] = []
        for dec in symbol.decorators:
            lines.append(f"{indent}{dec}")
        lines.append(f"{indent}{symbol.signature}")
        if symbol.docstring:
            doc_lines = symbol.docstring.splitlines()
            if len(doc_lines) == 1:
                lines.append(f"{indent}{self.INDENT}{symbol.docstring}  ...")
            else:
                for doc_line in doc_lines:
                    lines.append(f"{indent}{self.INDENT}{doc_line}")
                lines.append(f"{indent}{self.INDENT}...")
        else:
            lines.append(f"{indent}{self.INDENT}...")
        return lines
