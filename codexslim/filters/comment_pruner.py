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
