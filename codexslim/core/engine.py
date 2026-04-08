"""Engine — main orchestrator for CodexSlim."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List

from codexslim.core.cache_manager import CacheManager
from codexslim.core.tokenizer import Tokenizer
from codexslim.filters.skeletonizer import Skeletonizer
from codexslim.parsers.base_parser import BaseParser
from codexslim.parsers.python_driver import PythonParser

from codexslim.parsers.java_driver import JavaParser
from codexslim.parsers.dotnet_driver import DotNetParser
from codexslim.parsers.web_driver import WebDriver

from codexslim.parsers.go_driver import GoParser
from codexslim.parsers.rust_driver import RustParser
from codexslim.parsers.ruby_driver import RubyParser

_DEFAULT_PARSERS: List[BaseParser] = [
    PythonParser(),
    JavaParser(),
    DotNetParser(),
    WebDriver(),
    GoParser(),
    RustParser(),
    RubyParser(),
]

def _build_ext_map(parsers: List[BaseParser]) -> Dict[str, BaseParser]:
    m = {}
    for p in parsers:
        for ext in p.supported_extensions:
            m[ext] = p
    return m


class SlimFile:
    def __init__(self, source_path, original_source, slim_source, token_reports, cache_hit):
        self.source_path = source_path
        self.original_source = original_source
        self.slim_source = slim_source
        self.token_reports = token_reports
        self.cache_hit = cache_hit


class SlimResult:
    def __init__(self, files, workspace_root):
        self.files = files
        self.workspace_root = workspace_root

    @property
    def total_original_tokens(self):
        return sum(r.original_tokens for f in self.files for r in f.token_reports[:1])

    @property
    def total_slim_tokens(self):
        return sum(r.slim_tokens for f in self.files for r in f.token_reports[:1])

    @property
    def overall_savings_pct(self):
        orig = self.total_original_tokens
        if orig == 0:
            return 0.0
        return round((1 - self.total_slim_tokens / orig) * 100, 1)

    @property
    def cache_hits(self):
        return sum(1 for f in self.files if f.cache_hit)


class Engine:
    def __init__(self, workspace_root, parsers=None, grace_hours=24.0,
                 tokenizer_backend="openai", use_cache=True):
        self._root = Path(workspace_root).resolve()
        self._ext_map = _build_ext_map(parsers or _DEFAULT_PARSERS)
        self._cache = CacheManager(self._root, grace_hours=grace_hours) if use_cache else None
        self._skeletonizer = Skeletonizer()
        self._tokenizer = Tokenizer()
        self._tokenizer_backend = tokenizer_backend

    def run(self, target):
        target = Path(target).resolve()
        source_files = self._discover(target)
        if self._cache:
            self._cache.reconcile(source_files)
        slim_files = [f for f in (self._process_file(p) for p in source_files) if f]
        return SlimResult(files=slim_files, workspace_root=self._root)

    def run_file(self, file_path):
        return self._process_file(Path(file_path).resolve())

    def _discover(self, target):
        if target.is_file():
            return [target] if target.suffix in self._ext_map else []
        files = []
        for dirpath, dirnames, filenames in os.walk(target):
            dirnames[:] = [
                d for d in dirnames
                if not d.startswith(".")
                and d not in {"node_modules", "__pycache__", "dist", "build", "venv", ".venv"}
            ]
            for fname in filenames:
                path = Path(dirpath) / fname
                if path.suffix in self._ext_map:
                    files.append(path)
        return sorted(files)

    def _process_file(self, path):
        parser = self._ext_map.get(path.suffix)
        if parser is None:
            return None
        original_source = path.read_text(encoding="utf-8", errors="replace")
        cache_hit = False
        slim_source = None
        if self._cache:
            slim_source = self._cache.get(path)
            if slim_source is not None:
                cache_hit = True
        if slim_source is None:
            parse_result = parser.get_parse_result(path)
            slim_source = self._skeletonizer.skeletonize(parse_result)
            if self._cache:
                self._cache.set(path, slim_source)
        token_reports = self._tokenizer.count(
            original_source, slim_source, backend=self._tokenizer_backend
        )
        return SlimFile(
            source_path=path,
            original_source=original_source,
            slim_source=slim_source,
            token_reports=token_reports,
            cache_hit=cache_hit,
        )
