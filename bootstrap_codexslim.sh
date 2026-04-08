#!/usr/bin/env bash
set -e

echo "==> Bootstrapping CodexSlim v1..."

# ── .gitignore ────────────────────────────────────────────────────────────────
cat > .gitignore << 'EOF'
# CodexSlim cache — generated, always reproducible from source
.codexslim/

# Python
__pycache__/
*.py[cod]
*.pyo
*.pyd
*.egg
*.egg-info/
dist/
build/
.eggs/

# Virtual environments
.venv/
venv/
env/
.env

# Testing & coverage
.pytest_cache/
.coverage
htmlcov/
.tox/

# Type checking
.mypy_cache/
.pyright/

# Editors
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Distribution / packaging
*.tar.gz
*.whl
MANIFEST
EOF

# ── pyproject.toml ────────────────────────────────────────────────────────────
cat > pyproject.toml << 'EOF'
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "codexslim"
version = "0.1.0"
description = "AI token-efficient codebase reduction for LLM agents"
readme = "README.md"
license = { file = "LICENSE" }
requires-python = ">=3.10"
dependencies = [
    "tree-sitter>=0.21",
    "tree-sitter-languages>=1.10",
    "tiktoken>=0.7",
    "filelock>=3.13",
    "click>=8.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "mypy>=1.9",
    "ruff>=0.4",
]

[project.scripts]
slim = "codexslim.cli:main"

[tool.setuptools.packages.find]
where = ["."]
include = ["codexslim*"]

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.mypy]
python_version = "3.10"
strict = true
EOF

# ── Package structure ─────────────────────────────────────────────────────────
mkdir -p codexslim/core
mkdir -p codexslim/parsers
mkdir -p codexslim/filters
mkdir -p tests

touch codexslim/__init__.py
touch codexslim/core/__init__.py
touch codexslim/parsers/__init__.py
touch codexslim/filters/__init__.py

# ── codexslim/__init__.py ─────────────────────────────────────────────────────
cat > codexslim/__init__.py << 'EOF'
"""CodexSlim — AI token-efficient codebase reduction for LLM agents."""

__version__ = "0.1.0"
EOF

# ── codexslim/parsers/base_parser.py ─────────────────────────────────────────
cat > codexslim/parsers/base_parser.py << 'EOF'
"""Abstract base class that all language drivers must implement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Symbol:
    """A single extracted symbol (function, method, class)."""

    name: str
    kind: str                        # "function" | "method" | "class"
    signature: str                   # Full signature line(s)
    docstring: str | None            # Preserved verbatim if present
    decorators: list[str] = field(default_factory=list)
    start_line: int = 0
    end_line: int = 0


@dataclass
class ParseResult:
    """Everything a parser extracts from one source file."""

    path: Path
    language: str
    imports: list[str] = field(default_factory=list)   # raw import lines
    symbols: list[Symbol] = field(default_factory=list)
    module_docstring: str | None = None
    parse_errors: list[str] = field(default_factory=list)


class BaseParser(ABC):
    """
    Abstract interface all language drivers implement.

    Each driver receives a source file path and returns a ParseResult
    containing imports and symbols. Bodies are never included — the
    skeletonizer layer reconstructs a slim file from these primitives.
    """

    @property
    @abstractmethod
    def supported_extensions(self) -> tuple[str, ...]:
        """File extensions this driver handles, e.g. ('.py',)."""
        ...

    @abstractmethod
    def parse(self, path: Path) -> ParseResult:
        """
        Parse a source file and return its structural skeleton.

        Args:
            path: Absolute or relative path to the source file.

        Returns:
            ParseResult with imports and symbols populated.
            Never raises — parse errors are captured in ParseResult.parse_errors.
        """
        ...

    def can_parse(self, path: Path) -> bool:
        """Return True if this driver handles the given file extension."""
        return path.suffix.lower() in self.supported_extensions
EOF

# ── codexslim/parsers/python_driver.py ───────────────────────────────────────
cat > codexslim/parsers/python_driver.py << 'EOF'
"""Tree-sitter-based parser for Python source files."""

from __future__ import annotations

import re
from pathlib import Path

from .base_parser import BaseParser, ParseResult, Symbol

try:
    from tree_sitter_languages import get_language, get_parser

    _LANG = get_language("python")
    _PARSER = get_parser("python")
    _AVAILABLE = True
except Exception:  # pragma: no cover
    _AVAILABLE = False


# Queries against the Tree-sitter Python grammar
_IMPORT_QUERY = """
[
  (import_statement) @import
  (import_from_statement) @import
]
"""

_FUNCTION_QUERY = """
(function_definition
  name: (identifier) @name
  parameters: (parameters) @params
  return_type: (type)? @return_type
  body: (block
    . (expression_statement (string) @docstring)?
  )
) @func
"""

_CLASS_QUERY = """
(class_definition
  name: (identifier) @name
  superclasses: (argument_list)? @bases
  body: (block
    . (expression_statement (string) @docstring)?
  )
) @class
"""


def _node_text(node, source: bytes) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _extract_docstring(body_node, source: bytes) -> str | None:
    """Return the first string literal in a block if it's a docstring."""
    if not body_node:
        return None
    for child in body_node.children:
        if child.type == "expression_statement":
            for grandchild in child.children:
                if grandchild.type == "string":
                    raw = _node_text(grandchild, source)
                    # Strip surrounding quotes for clean storage
                    inner = raw.strip("\"'")
                    if raw.startswith('"""') or raw.startswith("'''"):
                        inner = raw[3:-3].strip()
                    return inner
        break  # docstring must be the first statement
    return None


def _extract_decorators(node, source: bytes) -> list[str]:
    """Collect decorator lines immediately preceding a function/class node."""
    decorators = []
    cursor = node.prev_sibling
    while cursor and cursor.type == "decorator":
        decorators.insert(0, _node_text(cursor, source))
        cursor = cursor.prev_sibling
    return decorators


class PythonParser(BaseParser):
    """Parser for .py files using Tree-sitter."""

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".py",)

    def parse(self, path: Path) -> ParseResult:
        result = ParseResult(path=path, language="python")

        if not _AVAILABLE:
            result.parse_errors.append("tree-sitter-languages not installed")
            return result

        try:
            source = path.read_bytes()
        except OSError as exc:
            result.parse_errors.append(str(exc))
            return result

        tree = _PARSER.parse(source)
        root = tree.root_node

        # Module-level docstring
        for child in root.children:
            if child.type == "expression_statement":
                for gc in child.children:
                    if gc.type == "string":
                        raw = _node_text(gc, source)
                        if raw.startswith('"""') or raw.startswith("'''"):
                            result.module_docstring = raw[3:-3].strip()
            break

        # Imports
        lang = _LANG
        import_query = lang.query(_IMPORT_QUERY)
        for node, _ in import_query.matches(root):
            # matches returns (pattern_index, dict); captures returns list
            pass

        # Use captures instead
        import_query = lang.query(_IMPORT_QUERY)
        for node, tag in import_query.captures(root):
            result.imports.append(_node_text(node, source))

        # Classes
        class_query = lang.query(_CLASS_QUERY)
        class_captures: dict[int, dict] = {}
        for node, tag in class_query.captures(root):
            node_id = node.id
            if node_id not in class_captures:
                class_captures[node_id] = {}
            class_captures[node_id][tag] = node

        seen_class_ids: set[int] = set()
        for node, tag in class_query.captures(root):
            if tag != "class":
                continue
            if node.id in seen_class_ids:
                continue
            seen_class_ids.add(node.id)

            name_node = next(
                (n for n, t in class_query.captures(node) if t == "name"), None
            )
            bases_node = next(
                (n for n, t in class_query.captures(node) if t == "bases"), None
            )
            doc_node = next(
                (n for n, t in class_query.captures(node) if t == "docstring"), None
            )

            name = _node_text(name_node, source) if name_node else "?"
            bases = f"({_node_text(bases_node, source)})" if bases_node else ""
            sig = f"class {name}{bases}:"
            docstring = None
            if doc_node:
                raw = _node_text(doc_node, source)
                if raw.startswith('"""') or raw.startswith("'''"):
                    docstring = raw[3:-3].strip()

            result.symbols.append(Symbol(
                name=name,
                kind="class",
                signature=sig,
                docstring=docstring,
                decorators=_extract_decorators(node, source),
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
            ))

        # Top-level and method functions
        func_query = lang.query(_FUNCTION_QUERY)
        seen_func_ids: set[int] = set()
        for node, tag in func_query.captures(root):
            if tag != "func":
                continue
            if node.id in seen_func_ids:
                continue
            seen_func_ids.add(node.id)

            captures = dict(func_query.captures(node))
            # captures may have multiple; use first of each
            def first(key: str):
                matches = [(n, t) for n, t in func_query.captures(node) if t == key]
                return matches[0][0] if matches else None

            name_node = first("name")
            params_node = first("params")
            ret_node = first("return_type")
            doc_node = first("docstring")

            name = _node_text(name_node, source) if name_node else "?"
            params = _node_text(params_node, source) if params_node else "()"
            ret = f" -> {_node_text(ret_node, source)}" if ret_node else ""
            sig = f"def {name}{params}{ret}:"

            docstring = None
            if doc_node:
                raw = _node_text(doc_node, source)
                if raw.startswith('"""') or raw.startswith("'''"):
                    docstring = raw[3:-3].strip()

            # Determine if method (parent is a class body)
            kind = "method" if node.parent and node.parent.type == "block" else "function"

            result.symbols.append(Symbol(
                name=name,
                kind=kind,
                signature=sig,
                docstring=docstring,
                decorators=_extract_decorators(node, source),
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
            ))

        return result
EOF

# ── codexslim/parsers/__init__.py ─────────────────────────────────────────────
cat > codexslim/parsers/__init__.py << 'EOF'
"""Language parser drivers."""

from .base_parser import BaseParser, ParseResult, Symbol
from .python_driver import PythonParser

__all__ = ["BaseParser", "ParseResult", "Symbol", "PythonParser"]
EOF

# ── codexslim/filters/skeletonizer.py ────────────────────────────────────────
cat > codexslim/filters/skeletonizer.py << 'EOF'
"""
Reconstructs a slim version of a source file from a ParseResult.

The output is syntactically valid Python (and analogous for other languages)
with all function/method bodies replaced by `...`.
Docstrings are preserved — they are spec, not noise.
"""

from __future__ import annotations

from codexslim.parsers.base_parser import ParseResult, Symbol


def skeletonize(result: ParseResult) -> str:
    """
    Produce a slim source string from a ParseResult.

    Args:
        result: Output of any BaseParser.parse() call.

    Returns:
        A multi-line string representing the slimmed file.
    """
    lines: list[str] = []

    if result.module_docstring:
        lines.append(f'"""{result.module_docstring}"""')
        lines.append("")

    if result.imports:
        for imp in result.imports:
            lines.append(imp)
        lines.append("")

    # Group methods under their class
    classes: dict[str, list[Symbol]] = {}
    top_level: list[Symbol] = []

    for sym in result.symbols:
        if sym.kind == "class":
            classes[sym.name] = [sym]
        elif sym.kind == "method":
            # Attribute to the most recently seen class (simple heuristic)
            if classes:
                last_class = list(classes.keys())[-1]
                classes[last_class].append(sym)
            else:
                top_level.append(sym)
        else:
            top_level.append(sym)

    # Emit classes first
    for class_name, members in classes.items():
        class_sym = members[0]
        for dec in class_sym.decorators:
            lines.append(dec)
        lines.append(class_sym.signature)
        if class_sym.docstring:
            lines.append(f'    """{class_sym.docstring}"""')
        lines.append("")

        methods = members[1:]
        if not methods:
            lines.append("    ...")
        else:
            for sym in methods:
                for dec in sym.decorators:
                    lines.append(f"    {dec}")
                lines.append(f"    {sym.signature}")
                if sym.docstring:
                    lines.append(f'        """{sym.docstring}"""')
                lines.append("        ...")
                lines.append("")

        lines.append("")

    # Emit top-level functions
    for sym in top_level:
        for dec in sym.decorators:
            lines.append(dec)
        lines.append(sym.signature)
        if sym.docstring:
            lines.append(f'    """{sym.docstring}"""')
        lines.append("    ...")
        lines.append("")

    return "\n".join(lines)
EOF

# ── codexslim/filters/comment_pruner.py ──────────────────────────────────────
cat > codexslim/filters/comment_pruner.py << 'EOF'
"""
Strips inline comments from source lines.

Docstrings are handled by the parser — this module only removes
single-line comments (# in Python, // in Java/JS/C#).
It is applied BEFORE the skeletonizer and only affects lines that
survive into the slim output (i.e. signatures and import lines).
"""

from __future__ import annotations

import re

_PYTHON_INLINE = re.compile(r'\s+#(?!\s*type:).*$')  # keep # type: ignore etc.
_C_STYLE_INLINE = re.compile(r'\s+//.*$')


def prune_python_comments(line: str) -> str:
    """Strip trailing # comments from a Python line, preserving type hints."""
    # Don't touch lines that are purely a comment
    stripped = line.lstrip()
    if stripped.startswith("#"):
        return ""
    return _PYTHON_INLINE.sub("", line)


def prune_c_style_comments(line: str) -> str:
    """Strip trailing // comments from a Java/JS/C# line."""
    stripped = line.lstrip()
    if stripped.startswith("//"):
        return ""
    return _C_STYLE_INLINE.sub("", line)


def prune(source: str, language: str) -> str:
    """
    Remove inline comments from a source string.

    Args:
        source:   Raw source text.
        language: One of 'python', 'java', 'csharp', 'javascript', 'typescript'.

    Returns:
        Source with inline comments removed. Blank lines introduced by
        fully-comment lines are also collapsed.
    """
    if language == "python":
        pruner = prune_python_comments
    elif language in ("java", "csharp", "javascript", "typescript"):
        pruner = prune_c_style_comments
    else:
        return source  # unknown language — pass through unchanged

    pruned_lines = []
    prev_blank = False
    for line in source.splitlines():
        result = pruner(line)
        is_blank = result.strip() == ""
        if is_blank and prev_blank:
            continue  # collapse consecutive blank lines
        pruned_lines.append(result)
        prev_blank = is_blank

    return "\n".join(pruned_lines)
EOF

# ── codexslim/filters/__init__.py ────────────────────────────────────────────
cat > codexslim/filters/__init__.py << 'EOF'
"""Transformation filters applied after parsing."""

from .skeletonizer import skeletonize
from .comment_pruner import prune

__all__ = ["skeletonize", "prune"]
EOF

# ── codexslim/core/cache_manager.py ──────────────────────────────────────────
cat > codexslim/core/cache_manager.py << 'EOF'
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

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from filelock import FileLock


_CACHE_FILE = ".codexslim/cache.json"
_LOCK_FILE  = ".codexslim/cache.lock"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class CacheManager:
    """
    Manages slim digests keyed by file SHA-256 hash.

    Usage:
        cm = CacheManager(workspace_root=Path("."))
        cm.load()

        digest = cm.get(path)          # None on miss
        cm.set(path, sha, digest)      # write entry
        cm.mark_deleted(path)          # flag for grace-period eviction
        cm.evict_expired(grace_hours)  # remove stale entries
        cm.save()
    """

    def __init__(self, workspace_root: Path, grace_hours: float = 24.0) -> None:
        self.root = workspace_root.resolve()
        self.grace_hours = grace_hours
        self._cache_path = self.root / _CACHE_FILE
        self._lock_path  = self.root / _LOCK_FILE
        self._data: dict[str, dict] = {}

    # ── persistence ───────────────────────────────────────────────────────────

    def load(self) -> None:
        """Load cache from disk. Safe to call even if cache file doesn't exist."""
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        if self._cache_path.exists():
            try:
                self._data = json.loads(self._cache_path.read_text())
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def save(self) -> None:
        """Persist cache to disk with a file lock."""
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(str(self._lock_path)):
            self._cache_path.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False)
            )

    # ── read ──────────────────────────────────────────────────────────────────

    def get(self, path: Path) -> str | None:
        """
        Return a cached slim digest if the file hash still matches.

        Returns None on cache miss or hash mismatch (stale).
        """
        key = self._key(path)
        entry = self._data.get(key)
        if not entry:
            return None
        if entry.get("status") != "active":
            return None
        current_sha = _sha256(path)
        if entry.get("sha256") != current_sha:
            return None  # file changed — caller must re-parse
        # Update last_seen_at without a full save (caller calls save() at end)
        entry["last_seen_at"] = _now_iso()
        return entry["slim_digest"]

    # ── write ─────────────────────────────────────────────────────────────────

    def set(self, path: Path, slim_digest: str) -> None:
        """Store or update a slim digest for a file."""
        key = self._key(path)
        sha = _sha256(path)
        self._data[key] = {
            "path": key,
            "sha256": sha,
            "slim_digest": slim_digest,
            "parsed_at": _now_iso(),
            "last_seen_at": _now_iso(),
            "status": "active",
        }

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def mark_deleted(self, path: Path) -> None:
        """Flag a file as deleted; it will be evicted after the grace period."""
        key = self._key(path)
        if key in self._data:
            self._data[key]["status"] = "pending_eviction"
            self._data[key]["deleted_at"] = _now_iso()

    def evict_expired(self) -> list[str]:
        """
        Remove entries that have been pending eviction longer than grace_hours.

        Returns a list of evicted keys (for logging).
        """
        evicted = []
        grace_seconds = self.grace_hours * 3600
        now = time.time()

        for key, entry in list(self._data.items()):
            if entry.get("status") != "pending_eviction":
                continue
            deleted_at_str = entry.get("deleted_at", entry.get("last_seen_at", ""))
            try:
                deleted_at = datetime.fromisoformat(deleted_at_str).timestamp()
            except ValueError:
                deleted_at = 0.0
            if now - deleted_at >= grace_seconds:
                del self._data[key]
                evicted.append(key)

        return evicted

    def reconcile(self, live_paths: list[Path]) -> dict[str, list[str]]:
        """
        Diff live file tree against cache.

        Marks entries for files that have disappeared as pending_eviction.
        Returns a summary dict with keys 'new', 'changed', 'deleted', 'cached'.
        """
        live_keys = {self._key(p) for p in live_paths}
        cached_keys = set(self._data.keys())

        summary: dict[str, list[str]] = {
            "new": [], "changed": [], "deleted": [], "cached": []
        }

        # Files in cache but not on disk → mark deleted
        for key in cached_keys - live_keys:
            if self._data[key].get("status") == "active":
                self.mark_deleted(self.root / key)
                summary["deleted"].append(key)

        # Files on disk → categorise
        for path in live_paths:
            key = self._key(path)
            if key not in self._data:
                summary["new"].append(key)
            else:
                entry = self._data[key]
                current_sha = _sha256(path)
                if entry.get("sha256") != current_sha:
                    summary["changed"].append(key)
                else:
                    summary["cached"].append(key)

        return summary

    # ── helpers ───────────────────────────────────────────────────────────────

    def _key(self, path: Path) -> str:
        """Normalise path to a relative string key."""
        try:
            return str(path.resolve().relative_to(self.root))
        except ValueError:
            return str(path)
EOF

# ── codexslim/core/tokenizer.py ──────────────────────────────────────────────
cat > codexslim/core/tokenizer.py << 'EOF'
"""
Token counting and savings reporting.

Supports OpenAI (tiktoken) and a character-based approximation for
Anthropic models (exact Anthropic tokenizer is not publicly available
as a standalone package at time of writing).
"""

from __future__ import annotations

from dataclasses import dataclass

try:
    import tiktoken
    _TIKTOKEN_AVAILABLE = True
except ImportError:  # pragma: no cover
    _TIKTOKEN_AVAILABLE = False

# Approximate tokens per character for Claude models (empirical average)
_ANTHROPIC_CHARS_PER_TOKEN = 3.5


@dataclass
class TokenReport:
    """Token count comparison between original and slim output."""

    original_tokens: int
    slim_tokens: int
    savings_pct: float
    tokenizer: str

    def __str__(self) -> str:
        return (
            f"[{self.tokenizer}] "
            f"{self.original_tokens:,} → {self.slim_tokens:,} tokens "
            f"({self.savings_pct:.1f}% saved)"
        )


def count_openai(text: str, model: str = "gpt-4o") -> int:
    """Count tokens using tiktoken (OpenAI encoding)."""
    if not _TIKTOKEN_AVAILABLE:
        raise RuntimeError("tiktoken is not installed. Run: pip install tiktoken")
    enc = tiktoken.encoding_for_model(model)
    return len(enc.encode(text))


def count_anthropic_approx(text: str) -> int:
    """Approximate token count for Anthropic/Claude models."""
    return max(1, int(len(text) / _ANTHROPIC_CHARS_PER_TOKEN))


def report(
    original: str,
    slim: str,
    tokenizer: str = "openai",
) -> TokenReport:
    """
    Produce a TokenReport comparing original and slim token counts.

    Args:
        original:  Raw source text.
        slim:      Skeletonized source text.
        tokenizer: "openai" | "anthropic" | "both"

    Returns:
        TokenReport (or a list of two if tokenizer="both").
    """
    if tokenizer == "openai":
        orig_count = count_openai(original)
        slim_count = count_openai(slim)
        label = "openai/gpt-4o"
    elif tokenizer == "anthropic":
        orig_count = count_anthropic_approx(original)
        slim_count = count_anthropic_approx(slim)
        label = "anthropic/approx"
    else:
        raise ValueError(f"Unknown tokenizer: {tokenizer!r}. Use 'openai' or 'anthropic'.")

    savings = 100.0 * (orig_count - slim_count) / max(orig_count, 1)
    return TokenReport(
        original_tokens=orig_count,
        slim_tokens=slim_count,
        savings_pct=round(savings, 1),
        tokenizer=label,
    )


def report_both(original: str, slim: str) -> list[TokenReport]:
    """Return token reports for both OpenAI and Anthropic tokenizers."""
    reports = []
    if _TIKTOKEN_AVAILABLE:
        reports.append(report(original, slim, "openai"))
    reports.append(report(original, slim, "anthropic"))
    return reports
EOF

# ── codexslim/core/engine.py ──────────────────────────────────────────────────
cat > codexslim/core/engine.py << 'EOF'
"""
Main orchestrator for CodexSlim.

Coordinates file discovery, parsing, filtering, caching, and output
emission. This is the single entry point used by both the CLI and any
programmatic callers.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

from codexslim.core.cache_manager import CacheManager
from codexslim.core.tokenizer import TokenReport, report_both, report
from codexslim.filters.skeletonizer import skeletonize
from codexslim.parsers.base_parser import BaseParser
from codexslim.parsers.python_driver import PythonParser


# ── Registry ─────────────────────────────────────────────────────────────────

_DEFAULT_PARSERS: list[BaseParser] = [
    PythonParser(),
]

# Extensions to always skip regardless of parser availability
_SKIP_EXTENSIONS = {
    ".pyc", ".pyo", ".pyd",
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg",
    ".zip", ".tar", ".gz", ".whl", ".egg",
    ".pdf", ".docx", ".xlsx",
    ".lock",  # e.g. poetry.lock, package-lock.json
}


# ── Result types ─────────────────────────────────────────────────────────────

@dataclass
class FileResult:
    """Outcome of processing one source file."""

    path: Path
    slim: str
    original_size: int     # bytes
    slim_size: int         # bytes
    cache_hit: bool
    token_reports: list[TokenReport] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class RunSummary:
    """Aggregate results of a full slim run."""

    total_files: int = 0
    cache_hits: int = 0
    parsed: int = 0
    skipped: int = 0
    errors: int = 0
    total_original_bytes: int = 0
    total_slim_bytes: int = 0
    file_results: list[FileResult] = field(default_factory=list)

    @property
    def bytes_saved_pct(self) -> float:
        if self.total_original_bytes == 0:
            return 0.0
        return round(
            100.0 * (self.total_original_bytes - self.total_slim_bytes)
            / self.total_original_bytes,
            1,
        )


# ── Engine ────────────────────────────────────────────────────────────────────

class Engine:
    """
    Coordinates the full slim pipeline for a workspace or single file.

    Args:
        workspace:    Root directory of the codebase to slim.
        parsers:      List of BaseParser drivers. Defaults to all built-in drivers.
        grace_hours:  Cache eviction grace period for deleted files.
        tokenizer:    "openai" | "anthropic" | "both" | None (skip counting).
        verbose:      Print per-file progress to stderr.
    """

    def __init__(
        self,
        workspace: Path,
        parsers: list[BaseParser] | None = None,
        grace_hours: float = 24.0,
        tokenizer: str | None = "openai",
        verbose: bool = False,
    ) -> None:
        self.workspace = workspace.resolve()
        self.parsers = parsers or _DEFAULT_PARSERS
        self.cache = CacheManager(self.workspace, grace_hours=grace_hours)
        self.tokenizer = tokenizer
        self.verbose = verbose

    def _find_parser(self, path: Path) -> BaseParser | None:
        for p in self.parsers:
            if p.can_parse(path):
                return p
        return None

    def _discover_files(self, target: Path) -> list[Path]:
        if target.is_file():
            return [target]
        files = []
        for p in sorted(target.rglob("*")):
            if p.is_file() and p.suffix not in _SKIP_EXTENSIONS:
                # Skip hidden dirs (.git, .venv, etc.)
                if any(part.startswith(".") for part in p.parts):
                    continue
                files.append(p)
        return files

    def _process_file(self, path: Path) -> FileResult:
        original_text = path.read_text(errors="replace")
        original_size = len(original_text.encode())

        # Cache lookup
        cached = self.cache.get(path)
        if cached is not None:
            slim_size = len(cached.encode())
            token_reports: list[TokenReport] = []
            if self.tokenizer == "both":
                token_reports = report_both(original_text, cached)
            elif self.tokenizer:
                token_reports = [report(original_text, cached, self.tokenizer)]
            return FileResult(
                path=path,
                slim=cached,
                original_size=original_size,
                slim_size=slim_size,
                cache_hit=True,
                token_reports=token_reports,
            )

        # Parse
        parser = self._find_parser(path)
        if parser is None:
            # No parser — pass through unchanged
            return FileResult(
                path=path,
                slim=original_text,
                original_size=original_size,
                slim_size=original_size,
                cache_hit=False,
            )

        parse_result = parser.parse(path)
        slim_text = skeletonize(parse_result)

        # Store in cache
        self.cache.set(path, slim_text)

        slim_size = len(slim_text.encode())
        token_reports = []
        if self.tokenizer == "both":
            token_reports = report_both(original_text, slim_text)
        elif self.tokenizer:
            token_reports = [report(original_text, slim_text, self.tokenizer)]

        return FileResult(
            path=path,
            slim=slim_text,
            original_size=original_size,
            slim_size=slim_size,
            cache_hit=False,
            token_reports=token_reports,
            errors=parse_result.parse_errors,
        )

    def run(self, target: Path) -> RunSummary:
        """
        Run the full slim pipeline on a file or directory.

        Args:
            target: File or directory to process.

        Returns:
            RunSummary with per-file results and aggregate stats.
        """
        self.cache.load()

        files = self._discover_files(target)
        summary = RunSummary(total_files=len(files))

        # Reconcile cache against live file tree
        self.cache.reconcile(files)
        self.cache.evict_expired()

        for path in files:
            if self.verbose:
                print(f"  slimming {path.relative_to(self.workspace)}", file=sys.stderr)

            try:
                result = self._process_file(path)
            except Exception as exc:
                summary.errors += 1
                summary.file_results.append(FileResult(
                    path=path, slim="", original_size=0, slim_size=0,
                    cache_hit=False, errors=[str(exc)]
                ))
                continue

            summary.file_results.append(result)
            summary.total_original_bytes += result.original_size
            summary.total_slim_bytes += result.slim_size
            if result.cache_hit:
                summary.cache_hits += 1
            elif result.errors:
                summary.errors += 1
            else:
                summary.parsed += 1

        self.cache.save()
        return summary

    def emit_skeleton_files(self, summary: RunSummary, out_dir: Path) -> None:
        """Write skeleton source files to out_dir, mirroring the original structure."""
        out_dir.mkdir(parents=True, exist_ok=True)
        for fr in summary.file_results:
            if not fr.slim:
                continue
            rel = fr.path.relative_to(self.workspace)
            dest = out_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(fr.slim)

    def emit_manifest(self, summary: RunSummary, out_file: Path) -> None:
        """Write a single SLIM.md manifest covering all processed files."""
        lines = [
            "# SLIM.md — CodexSlim manifest",
            f"> Generated by CodexSlim v0.1.0  |  workspace: `{self.workspace}`",
            "",
            "---",
            "",
        ]
        for fr in summary.file_results:
            if not fr.slim:
                continue
            rel = fr.path.relative_to(self.workspace)
            lines.append(f"## `{rel}`")
            lines.append("")
            lines.append("```" + fr.path.suffix.lstrip("."))
            lines.append(fr.slim.strip())
            lines.append("```")
            lines.append("")

        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text("\n".join(lines))
EOF

# ── codexslim/core/__init__.py ────────────────────────────────────────────────
cat > codexslim/core/__init__.py << 'EOF'
"""Core orchestration layer."""

from .engine import Engine, RunSummary, FileResult
from .cache_manager import CacheManager
from .tokenizer import TokenReport, report, report_both

__all__ = [
    "Engine", "RunSummary", "FileResult",
    "CacheManager",
    "TokenReport", "report", "report_both",
]
EOF

# ── codexslim/cli.py ──────────────────────────────────────────────────────────
cat > codexslim/cli.py << 'EOF'
"""
CLI entry point for CodexSlim.

Usage:
    slim <target> [options]

Examples:
    slim ./src --format skeleton --out ./src-slim
    slim ./src --format manifest --out SLIM.md
    slim ./src --focus auth/user.py --dep-depth 2
    slim ./src --tokenizer both --verbose
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from codexslim.core.engine import Engine


@click.command()
@click.argument("target", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--format", "fmt",
    default="skeleton",
    show_default=True,
    type=click.Choice(["skeleton", "manifest", "both"]),
    help="Output format.",
)
@click.option(
    "--out", "out_path",
    default=None,
    type=click.Path(path_type=Path),
    help="Output path (directory for skeleton, file for manifest).",
)
@click.option(
    "--tokenizer",
    default="openai",
    show_default=True,
    type=click.Choice(["openai", "anthropic", "both", "none"]),
    help="Tokenizer for savings report.",
)
@click.option(
    "--grace-period",
    default=24.0,
    show_default=True,
    type=float,
    help="Cache eviction grace period in hours.",
)
@click.option("--verbose", is_flag=True, default=False, help="Per-file progress output.")
def main(
    target: Path,
    fmt: str,
    out_path: Path | None,
    tokenizer: str,
    grace_period: float,
    verbose: bool,
) -> None:
    """Slim a codebase for efficient LLM agent consumption."""

    workspace = target if target.is_dir() else target.parent
    tok = None if tokenizer == "none" else tokenizer

    engine = Engine(
        workspace=workspace,
        grace_hours=grace_period,
        tokenizer=tok,
        verbose=verbose,
    )

    click.echo(f"CodexSlim › slimming {target} ...")
    summary = engine.run(target)

    # Emit output
    if fmt in ("skeleton", "both"):
        dest = out_path or (workspace / ".codexslim" / "skeleton")
        engine.emit_skeleton_files(summary, dest)
        click.echo(f"  skeleton files → {dest}")

    if fmt in ("manifest", "both"):
        dest = out_path or (workspace / "SLIM.md")
        if fmt == "both":
            dest = workspace / "SLIM.md"
        engine.emit_manifest(summary, dest)
        click.echo(f"  manifest       → {dest}")

    # Summary
    click.echo("")
    click.echo(f"  files processed : {summary.total_files}")
    click.echo(f"  cache hits      : {summary.cache_hits}")
    click.echo(f"  parsed          : {summary.parsed}")
    click.echo(f"  errors          : {summary.errors}")
    click.echo(f"  size reduction  : {summary.bytes_saved_pct:.1f}%")

    if tok and summary.file_results:
        all_reports = [r for fr in summary.file_results for r in fr.token_reports]
        if all_reports:
            click.echo("")
            click.echo("  token savings (aggregate):")
            by_tokenizer: dict[str, list] = {}
            for r in all_reports:
                by_tokenizer.setdefault(r.tokenizer, []).append(r)
            for label, reports in by_tokenizer.items():
                orig = sum(r.original_tokens for r in reports)
                slim = sum(r.slim_tokens for r in reports)
                pct = round(100.0 * (orig - slim) / max(orig, 1), 1)
                click.echo(f"    [{label}] {orig:,} → {slim:,} tokens ({pct}% saved)")

    if summary.errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
EOF

# ── tests/test_python_driver.py ───────────────────────────────────────────────
cat > tests/test_python_driver.py << 'EOF'
"""Basic smoke tests for the Python parser and skeletonizer."""

import textwrap
from pathlib import Path

import pytest

from codexslim.parsers.python_driver import PythonParser
from codexslim.filters.skeletonizer import skeletonize


SAMPLE = textwrap.dedent("""\
    \"\"\"Sample module.\"\"\"

    import os
    from pathlib import Path


    class Calculator:
        \"\"\"A simple calculator.\"\"\"

        def add(self, a: int, b: int) -> int:
            \"\"\"Return a + b.\"\"\"
            return a + b

        def subtract(self, a: int, b: int) -> int:
            return a - b


    def standalone(x: float) -> float:
        \"\"\"A standalone function.\"\"\"
        result = x * 2
        return result
""")


@pytest.fixture()
def sample_file(tmp_path: Path) -> Path:
    f = tmp_path / "sample.py"
    f.write_text(SAMPLE)
    return f


def test_parser_finds_imports(sample_file):
    result = PythonParser().parse(sample_file)
    assert any("import os" in i for i in result.imports)
    assert any("pathlib" in i for i in result.imports)


def test_parser_finds_class(sample_file):
    result = PythonParser().parse(sample_file)
    classes = [s for s in result.symbols if s.kind == "class"]
    assert any(c.name == "Calculator" for c in classes)


def test_parser_finds_methods(sample_file):
    result = PythonParser().parse(sample_file)
    methods = [s for s in result.symbols if s.kind == "method"]
    names = {m.name for m in methods}
    assert "add" in names
    assert "subtract" in names


def test_parser_preserves_docstrings(sample_file):
    result = PythonParser().parse(sample_file)
    add_sym = next(s for s in result.symbols if s.name == "add")
    assert add_sym.docstring is not None
    assert "a + b" in add_sym.docstring


def test_skeletonizer_removes_body(sample_file):
    result = PythonParser().parse(sample_file)
    slim = skeletonize(result)
    assert "return a + b" not in slim
    assert "result = x * 2" not in slim


def test_skeletonizer_keeps_signatures(sample_file):
    result = PythonParser().parse(sample_file)
    slim = skeletonize(result)
    assert "def add" in slim
    assert "def standalone" in slim


def test_skeletonizer_keeps_docstrings(sample_file):
    result = PythonParser().parse(sample_file)
    slim = skeletonize(result)
    assert "Return a + b" in slim
    assert "A standalone function" in slim


def test_no_parse_errors(sample_file):
    result = PythonParser().parse(sample_file)
    assert result.parse_errors == []
EOF

# ── tests/__init__.py ─────────────────────────────────────────────────────────
touch tests/__init__.py

echo ""
echo "==> Done! Files created:"
echo ""
find codexslim tests -type f | sort
echo ""
echo "==> Next steps:"
echo ""
echo "    python -m venv .venv"
echo "    source .venv/bin/activate"
echo "    pip install -e '.[dev]'"
echo "    pytest tests/ -v"
echo "    slim . --format manifest --out SLIM.md --verbose"
