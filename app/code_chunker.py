"""Split Python source files into function / class / method chunks using the ast module.

Each chunk keeps its file path, symbol name and line range, so an answer can cite
`file:start_line-end_line` and link straight to that code on GitHub.
"""

import ast
import sys
from pathlib import Path

SKIP_DIRS = {
    ".git", "node_modules", "venv", ".venv", "env", "__pycache__",
    "build", "dist", ".mypy_cache", ".pytest_cache", ".tox", "site-packages",
}
MAX_CHARS = 3000  # chunks longer than this are split into parts


def iter_python_files(root):
    root = Path(root)
    for path in sorted(root.rglob("*.py")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path


def _start_line(node):
    """First line of a node, including its decorators."""
    lines = [node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])]
    return min(lines)


def _make_chunk(rel_path, symbol, kind, start, end, lines, docstring):
    code = "\n".join(lines[start - 1:end])
    return {
        "file": rel_path,
        "symbol": symbol,
        "kind": kind,
        "start_line": start,
        "end_line": end,
        "docstring": docstring or "",
        "code": code,
        # text that will be embedded: location + docstring + code
        "text": f"{rel_path} :: {symbol}\n{docstring or ''}\n{code}".strip(),
    }


def _split_long(chunk):
    """Split an oversized chunk by lines so no part exceeds MAX_CHARS."""
    if len(chunk["code"]) <= MAX_CHARS:
        return [chunk]
    parts, current, current_len, part_start = [], [], 0, chunk["start_line"]
    code_lines = chunk["code"].splitlines()
    for offset, line in enumerate(code_lines):
        if current and current_len + len(line) + 1 > MAX_CHARS:
            parts.append((part_start, current))
            part_start = chunk["start_line"] + offset
            current, current_len = [], 0
        current.append(line)
        current_len += len(line) + 1
    if current:
        parts.append((part_start, current))
    result = []
    for i, (start, part_lines) in enumerate(parts, start=1):
        code = "\n".join(part_lines)
        symbol = f"{chunk['symbol']} (part {i}/{len(parts)})"
        result.append({
            **chunk,
            "symbol": symbol,
            "start_line": start,
            "end_line": start + len(part_lines) - 1,
            "code": code,
            "text": f"{chunk['file']} :: {symbol}\n{chunk['docstring']}\n{code}".strip(),
        })
    return result


def chunk_file(path, root):
    """Return a list of chunks for one Python file."""
    path, root = Path(path), Path(root)
    source = path.read_text(encoding="utf-8", errors="ignore")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    lines = source.splitlines()
    rel_path = path.relative_to(root).as_posix()
    chunks = []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            chunks.append(_make_chunk(
                rel_path, node.name, "function",
                _start_line(node), node.end_lineno, lines, ast.get_docstring(node),
            ))
        elif isinstance(node, ast.ClassDef):
            methods = [n for n in node.body
                       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            # class chunk = header up to the first method (keeps docstring and attributes)
            header_end = (_start_line(methods[0]) - 1) if methods else node.end_lineno
            chunks.append(_make_chunk(
                rel_path, node.name, "class",
                _start_line(node), max(header_end, node.lineno), lines, ast.get_docstring(node),
            ))
            for m in methods:
                chunks.append(_make_chunk(
                    rel_path, f"{node.name}.{m.name}", "method",
                    _start_line(m), m.end_lineno, lines, ast.get_docstring(m),
                ))

    # files with no functions or classes (scripts, config): keep the file as one chunk
    if not chunks and source.strip():
        chunks.append(_make_chunk(
            rel_path, "<module>", "module", 1, len(lines), lines, ast.get_docstring(tree),
        ))

    result = []
    for c in chunks:
        result.extend(_split_long(c))
    return result


def chunk_repo(root):
    root = Path(root)
    chunks = []
    for path in iter_python_files(root):
        chunks.extend(chunk_file(path, root))
    return chunks


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    all_chunks = chunk_repo(target)
    print(f"{len(all_chunks)} chunks")
    for c in all_chunks[:8]:
        print(f"{c['file']}:{c['start_line']}-{c['end_line']}  {c['kind']:<8} {c['symbol']}")
