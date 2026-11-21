"""Baseline: split files into fixed-size character windows (no code structure)."""

from pathlib import Path

from app.code_chunker import iter_python_files

SIZE, OVERLAP = 1000, 100


def chunk_file(path, root):
    path, root = Path(path), Path(root)
    source = path.read_text(encoding="utf-8", errors="ignore")
    rel = path.relative_to(root).as_posix()
    chunks, pos = [], 0
    while pos < len(source):
        end = min(pos + SIZE, len(source))
        code = source[pos:end]
        start_line = source.count("\n", 0, pos) + 1
        end_line = start_line + code.count("\n")
        chunks.append({
            "file": rel, "symbol": f"chars {pos}-{end}", "kind": "text",
            "start_line": start_line, "end_line": end_line,
            "docstring": "", "code": code, "text": f"{rel}\n{code}",
        })
        if end == len(source):
            break
        pos = end - OVERLAP
    return chunks


def chunk_repo(root):
    chunks = []
    for path in iter_python_files(root):
        chunks.extend(chunk_file(path, root))
    return chunks