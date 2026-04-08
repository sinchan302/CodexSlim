# SLIM.md — CodexSlim manifest

> 18 files · 71.0% token savings

## `__init__.py`

```py
"""CodexSlim — AI token-efficient codebase reduction for LLM agents."""
```

## `cli.py`

```py
"""CodexSlim CLI entry point."""

import sys
from pathlib import Path
import click
from codexslim.core.engine import Engine

@click.command()
@click.argument("target", type=click.Path(exists=True, path_type=Path))
@click.option("--format", "fmt", default="skeleton", show_default=True,
              help="Output format: skeleton | manifest")
@click.option("--out", "out_path", default=None, type=click.Path(path_type=Path),
              help="Output path.")
@click.option("--dep-depth", default=1, show_default=True)
@click.option("--grace-period", default=24, show_default=True)
@click.option("--tokenizer", default="openai", show_default=True,
              type=click.Choice(["openai", "anthropic", "both"], case_sensitive=False))
@click.option("--no-cache", is_flag=True, default=False)
@click.option("--verbose", is_flag=True, default=False)
def main(target, fmt, out_path, dep_depth, grace_period, tokenizer, no_cache, verbose):
    """Slim a codebase for AI agent consumption."""  ...

def te_skeleton(result, out_path, verbose):
  :
    ...

def te_manifest(result, out_path, verbose):
  :
    ...
```

## `core/__init__.py`

```py
"""Core orchestration layer."""

from .engine import Engine, SlimResult, SlimFile
from .cache_manager import CacheManager
from .tokenizer import TokenReport, report, report_both
```

## `core/cache_manager.py`

```py
"""
File-hash-based cache for slim digests.

Cache store: flat JSON files in <workspace>/.codexslim/cache.json
Cache entry fields:
    path          — relative path from workspace root
    sha256        — SHA-256 of the raw source file at last parse
    slim_digest   — the skeletonized output string
    parsed_at     — ISO-8601 timestamp of last parse
    last_seen_at  — ISO-8601 timestamp of last reconcile scan
    status        — "active" | "pending_eviction"
"""

from __fut

ib
import json
import time
from dateti
e import datetime, timezone
from pathli
import Path

from filel
k import FileLock


_CACHE_FI

def > str:
    -> urn:
    ...

def : Path) -> str:
    ->  ha:
    ...

class :
    """
  :
    ges slim digests keyed by file SHA-256 hash.
    
        Usage:
            cm = CacheManager(workspace_root=Path("."))
            cm.load()
    
            digest = cm.get(path)          # None on miss
            cm.set(path, sha, digest)      # write entry
            cm.mark_deleted(path)          # flag for grace-period eviction
            cm.evict_expired(grace_hours)  # remove stale entries
            cm.save()
        """
    
        def __

    def f, workspace_root: Path, grace_hours: float = 24.0) -> None:
   ->   se:
        ...

    def .mkdir(par -> =Tru:
        k=True)
                if self._cache_path.exists():
                    try:
        ...

    def =True)
    ->  wit:
        (str(self._lock_path)):
                    self._cac
        ...

    def t entry:
             -> rn None
  :
        ntry.get("status") != "active":
                    return None
                current_sha = _sha256(path)
                if entry.get("sha256") != current_sha:
        ...

    def  # ── lifecycle ─────────────────────── -> ────:
        ────────────────────
        
            def mark_deleted(self
        ...

    def seconds = self.grace_hours * 3 ->     :
        time.time()
        
                for key, entry in list(self._data.items()):
        ...

    def          deleted_at -> atetime.f:
        at(deleted_at_str).timestamp()
                    except ValueError:
                        deleted_at = 0.0
                    if now - deleted_at >= grace_seconds:
        ...

    def  but not on disk → mark deleted
        ->  key in cached_keys :
        s:
                    if self._data[key].get("status") == "active":
                        self.mark_deleted(self.root / key)
                        summary["deleted"].append(key)
        
                # Files on disk → categorise
                for path
        ...

    def  -> :
        ...
```

## `core/engine.py`

```py
"""Engine — main orchestrator for CodexSlim."""

port os
f
om pathlib import Path
f
om typing import Dict, List
om codexslim.core.cache_manager import CacheManager
f
om codexslim.core.tokenizer import Tokenizer
f
om codexslim.filters.skeletonizer import Skeletonizer
f
om codexslim.parsers.base_parser import BaseParser
f
om codexslim.parsers.python_driver import PythonParser
om codexslim.parsers.java_driver import JavaParser
f
om codexslim.parsers.dotnet_driver import DotNetParser
f
om codexslim.parsers.web_driver import WebDriver
om codexslim.parsers.go_driver import GoParser
f
om codexslim.parsers.rust_driver import RustParser
f
om codexslim.parsers.ruby_driver import RubyParser

def uild_ext_map(parsers: List[BaseParser]) - -> ct[str, BaseParser]:
:
    ...

class imFile:
:

    def init__(self, source_path, original_source, slim_source, token_reports, cache_hit):
:
        ...


class imResult:
:

    def init__(self, files, workspace_root):
:
        ...

    roperty
    def tal_original_tokens(self):
:
        ...

    roperty
    def tal_slim_tokens(self):
:
        ...

    roperty
    def erall_savings_pct(self):
:
        ...

    roperty
    def che_hits(self):
:
        ...


class gine:
:

    def init__(self, workspace_root, parsers=None, grace_hours=24.0,
                 tokenizer_backend="openai", use_cache=True):
:
        ...

    def n(self, target):
:
        ...

    def n_file(self, file_path):
:
        ...

    def iscover(self, target):
:
        ...

    def rocess_file(self, path):
:
        ...
```

## `core/tokenizer.py`

```py
"""
Token counting and savings reporting.

Supports OpenAI (tiktoken) and a character-based approximation for
Anthropic models (exact Anthropic tokenizer is not publicly available
as a standalone package at time of writing).
"""

from dataclasses import dataclass

@dataclass
class TokenReport:
    """Token count comparison between original and slim output."""

    def __str__(self) -> str:
        ...

def unt_openai(text: str, model: str = "gpt-4o") - -> t:
:
    "Count tokens using tiktoken (OpenAI encoding)."""  ...

def unt_anthropic_approx(text: str) - -> t:
:
    "Approximate token count for Anthropic/Claude models."""  ...

def port(
    original: str,
    slim: str,
    tokenizer: str = "openai",
) - -> kenReport:
:
    "
        Produce a TokenReport comparing original and slim token counts.
    
        Args:
            original:  Raw source text.
            slim:      Skeletonized source text.
            tokenizer: "openai" | "anthropic" | "both"
    
        Returns:
            TokenReport (or a list of two if tokenizer="both").
        """
    ...

def port_both(original: str, slim: str) - -> st[TokenReport]:
:
    "Return token reports for both OpenAI and Anthropic tokenizers."""  ...


class kenizer:
:
    "Wrapper class for token counting orchestration."""

    def unt(self, original: str, slim: str, backend: str = "openai") - -> st[TokenReport]:
:
        "Count tokens using the specified backend."""  ...
```

## `filters/__init__.py`

```py
"""Transformation filters applied after parsing."""

from .skeletonizer import Skeletonizer
from .comment_pruner import prune
```

## `filters/comment_pruner.py`

```py
"""
Strips inline comments from source lines.

Docstrings are handled by the parser — this module only removes
single-line comments (# in Python, // in Java/JS/C#).
It is applied BEFORE the skeletonizer and only affects lines that
survive into the slim output (i.e. signatures and import lines).
"""

port re

def une_python_comments(line: str) - -> r:
:
    "Strip trailing # comments from a Python line, preserving type hints."""  ...

def une_c_style_comments(line: str) - -> r:
:
    "Strip trailing // comments from a Java/JS/C# line."""  ...

def une(source: str, language: str) - -> r:
:
    "
        Remove inline comments from a source string.
    
        Args:
            source:   Raw source text.
            language: One of 'python', 'java', 'csharp', 'javascript', 'typescript'.
    
        Returns:
            Source with inline comments removed. Blank lines introduced by
            fully-comment lines are also collapsed.
        """
    ...
```

## `filters/skeletonizer.py`

```py
"""
Skeletonizer — converts a ParseResult into a slim source string.
"""

om typing import List, Optional
om codexslim.parsers.base_parser import ParseResult, Symbol

class eletonizer:
:
    "Reconstructs a slim source file from a ParseResult."""

    def eletonize(self, result: ParseResult) - -> r:
:
        ...

    def ender_class(self, symbol: Symbol) - -> st[str]:
:
        ...

    def ender_function(self, symbol: Symbol, indent: str) - -> st[str]:
:
        ...
```

## `parsers/__init__.py`

```py
"""Language parser drivers."""

from .base_parser import BaseParser, ParseResult, Symbol
from .python_driver import PythonParser
```

## `parsers/base_parser.py`

```py
"""Abstract base class that all language drivers must implement."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

@dataclass
class Symbol:
    """A structurally significant token extracted from the source file (e.g., class, method, function)."""


@dataclass
class ParseResult:
    """The aggregate structural output produced by a Parser for a single file."""


class BaseParser((ABC)):
    """
        Abstract interface for language-specific parsers.
    
        A parser examines source strings and extracts symbols, imports, 
        and module docstrings to form a structural blueprint of the code.
        """

    @abstractmethod
    def get_signatures(self, source: str) -> List[Symbol]:
        """Extract all significant symbols (classes, functions, methods) from the source string."""  ...

    @abstractmethod
    def get_imports(self, source: str) -> List[str]:
        """Extract all import statements from the source string."""  ...

    @property
    @abstractmethod
    def language_name(self) -> str:
        """The canonical name of the language this parser handles (e.g., 'python')."""  ...

    @property
    @abstractmethod
    def supported_extensions(self) -> List[str]:
        """List of file extensions supported by this parser (e.g., ['.py'])."""  ...

    def get_parse_result(self, file_path: Path) -> ParseResult:
        """Default implementation of get_parse_result."""  ...
```

## `parsers/dotnet_driver.py`

```py
"""Tree-sitter .NET (C#) parser driver."""

import re
from typing import List, Optional
from codexslim.parsers.base_parser import BaseParser, Symbol

class DotNetParser((BaseParser)):
    """Extracts signatures, imports, and docstrings from C# source files."""

    @property
    def language_name(self) -> str:
        ...

    @property
    def supported_extensions(self) -> List[str]:
        ...

    def get_signatures(self, source: str) -> List[Symbol]:
        ...

    def get_imports(self, source: str) -> List[str]:
        ...

    def _ts_signatures(self, source: str) -> List[Symbol]:
        ...

    def _walk_for_symbols(self, node, source: str, symbols: List[Symbol], parent: Optional[str]):
        ...

    def _ts_imports(self, source: str) -> List[str]:
        ...

    def _node_text(self, node, source: str) -> str:
        ...

    def _regex_signatures(self, source: str) -> List[Symbol]:
        ...

    def _regex_imports(self, source: str) -> List[str]:
        ...
```

## `parsers/go_driver.py`

```py
"""Tree-sitter Go parser driver."""

import re
from typing import List, Optional
from codexslim.parsers.base_parser import BaseParser, Symbol

class GoParser((BaseParser)):
    """Extracts signatures, imports, and docstrings from Go source files."""

    @property
    def language_name(self) -> str:
        ...

    @property
    def supported_extensions(self) -> List[str]:
        ...

    def get_signatures(self, source: str) -> List[Symbol]:
        ...

    def get_imports(self, source: str) -> List[str]:
        ...

    def _ts_signatures(self, source: str) -> List[Symbol]:
        ...

    def _walk_for_symbols(self, node, source: str, symbols: List[Symbol], parent: Optional[str]):
        ...

    def _ts_imports(self, source: str) -> List[str]:
        ...

    def _node_text(self, node, source: str) -> str:
        ...

    def _regex_signatures(self, source: str) -> List[Symbol]:
        ...

    def _regex_imports(self, source: str) -> List[str]:
        ...
```

## `parsers/java_driver.py`

```py
"""Tree-sitter Java parser driver."""

import re
from typing import List, Optional
from codexslim.parsers.base_parser import BaseParser, Symbol

class JavaParser((BaseParser)):
    """Extracts signatures, imports, and docstrings from Java source files."""

    @property
    def language_name(self) -> str:
        ...

    @property
    def supported_extensions(self) -> List[str]:
        ...

    def get_signatures(self, source: str) -> List[Symbol]:
        ...

    def get_imports(self, source: str) -> List[str]:
        ...

    def _ts_signatures(self, source: str) -> List[Symbol]:
        ...

    def _walk_for_symbols(self, node, source: str, symbols: List[Symbol], parent: Optional[str]):
        ...

    def _ts_imports(self, source: str) -> List[str]:
        ...

    def _node_text(self, node, source: str) -> str:
        ...

    def _regex_signatures(self, source: str) -> List[Symbol]:
        ...

    def _regex_imports(self, source: str) -> List[str]:
        ...
```

## `parsers/python_driver.py`

```py
"""Tree-sitter Python parser driver."""

import textwrap
from pathlib import Path
from typing import List, Optional
from codexslim.parsers.base_parser import BaseParser, ParseResult, Symbol

class PythonParser((BaseParser)):
    """Extracts signatures, imports, and docstrings from Python source files."""

    @property
    def language_name(self) -> str:
        ...

    @property
    def supported_extensions(self) -> List[str]:
        ...

    def get_signatures(self, source: str) -> List[Symbol]:
        ...

    def get_imports(self, source: str) -> List[str]:
        ...

    def get_parse_result(self, file_path: Path) -> ParseResult:
        ...

    def _ts_signatures(self, source: str) -> List[Symbol]:
        ...

    def _walk_for_symbols(self, node, source: str, symbols: List[Symbol], parent: Optional[str]):
        ...

    def _ts_imports(self, source: str) -> List[str]:
        ...

    def _node_text(self, node, source: str) -> str:
        ...

    def _collect_decorators(self, node, source: str) -> List[str]:
        ...

    def _extract_docstring_from_body(self, body_node, source: str) -> Optional[str]:
        ...

    def _extract_module_docstring(self, source: str) -> Optional[str]:
        ...

    def _regex_signatures(self, source: str) -> List[Symbol]:
        ...

    def _regex_imports(self, source: str) -> List[str]:
        ...
```

## `parsers/ruby_driver.py`

```py
"""Tree-sitter Ruby parser driver."""

import re
from typing import List, Optional
from codexslim.parsers.base_parser import BaseParser, Symbol

class RubyParser((BaseParser)):
    """Extracts signatures, imports, and docstrings from Ruby source files."""

    @property
    def language_name(self) -> str:
        ...

    @property
    def supported_extensions(self) -> List[str]:
        ...

    def get_signatures(self, source: str) -> List[Symbol]:
        ...

    def get_imports(self, source: str) -> List[str]:
        ...

    def _ts_signatures(self, source: str) -> List[Symbol]:
        ...

    def _walk_for_symbols(self, node, source: str, symbols: List[Symbol], parent: Optional[str]):
        ...

    def _ts_imports(self, source: str) -> List[str]:
        ...

    def _node_text(self, node, source: str) -> str:
        ...

    def _regex_signatures(self, source: str) -> List[Symbol]:
        ...

    def _regex_imports(self, source: str) -> List[str]:
        ...
```

## `parsers/rust_driver.py`

```py
"""Tree-sitter Rust parser driver."""

import re
from typing import List, Optional
from codexslim.parsers.base_parser import BaseParser, Symbol

class RustParser((BaseParser)):
    """Extracts signatures, imports, and docstrings from Rust source files."""

    @property
    def language_name(self) -> str:
        ...

    @property
    def supported_extensions(self) -> List[str]:
        ...

    def get_signatures(self, source: str) -> List[Symbol]:
        ...

    def get_imports(self, source: str) -> List[str]:
        ...

    def _ts_signatures(self, source: str) -> List[Symbol]:
        ...

    def _walk_for_symbols(self, node, source: str, symbols: List[Symbol], parent: Optional[str]):
        ...

    def _ts_imports(self, source: str) -> List[str]:
        ...

    def _node_text(self, node, source: str) -> str:
        ...

    def _regex_signatures(self, source: str) -> List[Symbol]:
        ...

    def _regex_imports(self, source: str) -> List[str]:
        ...
```

## `parsers/web_driver.py`

```py
"""Tree-sitter JS/TS parser driver."""

import re
from pathlib import Path
from typing import List, Optional
from codexslim.parsers.base_parser import BaseParser, ParseResult, Symbol

class WebDriver((BaseParser)):
    """Extracts signatures, imports, and docstrings from JS and TS files."""

    @property
    def language_name(self) -> str:
        ...

    @property
    def supported_extensions(self) -> List[str]:
        ...

    def _get_ts_lang(self, source_or_path="") -> str:
        """Determines whether to use javascript or typescript parser."""  ...

    def get_parse_result(self, file_path: Path) -> ParseResult:
        """Override to dynamically set language based on extension."""  ...

    def get_signatures(self, source: str) -> List[Symbol]:
        ...

    def _get_signatures_with_lang(self, source: str, lang: str) -> List[Symbol]:
        ...

    def get_imports(self, source: str) -> List[str]:
        ...

    def _get_imports_with_lang(self, source: str, lang: str) -> List[str]:
        ...

    def _ts_signatures(self, source: str, lang: str) -> List[Symbol]:
        ...

    def _walk_for_symbols(self, node, source: str, symbols: List[Symbol], parent: Optional[str]):
        ...

    def _walk_for_symbols_node(self, child, source: str, symbols: List[Symbol], parent: Optional[str], current_docs: List[str]):
        ...

    def _ts_imports(self, source: str, lang: str) -> List[str]:
        ...

    def _node_text(self, node, source: str) -> str:
        ...

    def _regex_signatures(self, source: str) -> List[Symbol]:
        ...

    def _regex_imports(self, source: str) -> List[str]:
        ...
```
