"""Abstract base class that all language drivers must implement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class Symbol:
    """A structurally significant token extracted from the source file (e.g., class, method, function)."""
    name: str
    kind: str           # "function" | "method" | "class" | "constant"
    signature: str      # Full signature line
    docstring: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    start_line: int = 0
    end_line: int = 0
    parent: Optional[str] = None   # Enclosing class, if any


@dataclass
class ParseResult:
    """The aggregate structural output produced by a Parser for a single file."""
    file_path: Path
    language: str
    imports: List[str] = field(default_factory=list)
    symbols: List[Symbol] = field(default_factory=list)
    module_docstring: Optional[str] = None
    errors: List[str] = field(default_factory=list)


class BaseParser(ABC):
    """
    Abstract interface for language-specific parsers.
    
    A parser examines source strings and extracts symbols, imports, 
    and module docstrings to form a structural blueprint of the code.
    """
    
    @abstractmethod
    def get_signatures(self, source: str) -> List[Symbol]:
        """Extract all significant symbols (classes, functions, methods) from the source string."""
        ...

    @abstractmethod
    def get_imports(self, source: str) -> List[str]:
        """Extract all import statements from the source string."""
        ...

    @property
    @abstractmethod
    def language_name(self) -> str:
        """The canonical name of the language this parser handles (e.g., 'python')."""
        ...

    @property
    @abstractmethod
    def supported_extensions(self) -> List[str]:
        """List of file extensions supported by this parser (e.g., ['.py'])."""
        ...

    def get_parse_result(self, file_path: Path) -> ParseResult:
        """Default implementation of get_parse_result."""
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
            imports = self.get_imports(source)
            symbols = self.get_signatures(source)
        except Exception as e:
            return ParseResult(file_path=file_path, language=self.language_name, errors=[str(e)])
        
        return ParseResult(
            file_path=file_path,
            language=self.language_name,
            imports=imports,
            symbols=symbols,
        )

