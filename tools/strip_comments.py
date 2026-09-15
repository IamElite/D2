import argparse
import ast
import io
import pathlib
import sys
import tokenize

EXCLUDE_DIRS = {".git", "__pycache__"}
KEEP_MARKERS = ("noqa", "type:", "fmt:", "pragma:", "pylint:", "mypy:", "pyright:", "ruff:")


def _split_eol(line):
    i = len(line)
    while i > 0 and line[i - 1] in "\r\n":
        i -= 1
    return line[:i], line[i:]


def _keep_comment(tok):
    if tok.start[0] == 1 and tok.string.startswith("#!"):
        return True
    low = tok.string.lower()
    return any(marker in low for marker in KEEP_MARKERS)


def _parent_map(tree):
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def _holding_block(parents, node):
    parent = parents.get(node)
    if parent is None:
        return None
    for field in ("body", "orelse", "finalbody"):
        block = getattr(parent, field, None)
        if isinstance(block, list) and any(item is node for item in block):
            return block
    return None


def _bare_strings(tree):
    found = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            found.append(node)
    return found


def _apply(lines, edits):
    by_row = {}
    for row, start, end, repl in edits:
        by_row.setdefault(row, []).append((start, end, repl))
    out = []
    for index, line in enumerate(lines):
        spans = by_row.get(index)
        if not spans:
            out.append(line)
            continue
        body, eol = _split_eol(line)
        for start, end, repl in sorted(spans, key=lambda span: -span[0]):
            if start > len(body):
                continue
            body = body[:start] + repl + body[min(end, len(body)):]
        if not body.strip():
            continue
        out.append(body + eol)
    return out


def _plan_edits(text, lines):
    tree = ast.parse(text)
    parents = _parent_map(tree)
    edits = []
    stats = {"comments": 0, "strings": 0, "kept": 0}
    removed = []
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type != tokenize.COMMENT:
            continue
        if _keep_comment(tok):
            stats["kept"] += 1
            continue
        row = tok.start[0] - 1
        body, _ = _split_eol(lines[row])
        if tok.start[1] > len(body):
            continue
        edits.append((row, tok.start[1], len(body), ""))
        stats["comments"] += 1
    for node in _bare_strings(tree):
        block = _holding_block(parents, node)
        parent = parents.get(node)
        empty = block is not None and len(block) == 1 and not isinstance(parent, ast.Module)
        repl = "pass" if empty else ""
        row_start, col_start = node.lineno - 1, node.col_offset
        row_end, col_end = node.end_lineno - 1, node.end_col_offset
        if row_start == row_end:
            edits.append((row_start, col_start, col_end, repl))
        else:
            head, _ = _split_eol(lines[row_start])
            edits.append((row_start, col_start, len(head), repl))
            for row in range(row_start + 1, row_end):
                middle, _ = _split_eol(lines[row])
                edits.append((row, 0, len(middle), ""))
            edits.append((row_end, 0, col_end, ""))
        stats["strings"] += 1
        removed.append(node)
    return edits, stats, removed, tree


def _strip(text):
    lines = text.splitlines(keepends=True)
    edits, stats, removed, tree = _plan_edits(text, lines)
    new_text = "".join(_apply(lines, edits))
    return new_text, stats, removed, tree


def _clean_ast(tree):
    parents = _parent_map(tree)
    for node in _bare_strings(tree):
        block = _holding_block(parents, node)
        if block is None:
            continue
        parent = parents.get(node)
        if len(block) == 1 and not isinstance(parent, ast.Module):
            block[0] = ast.Pass()
        else:
            block.remove(node)
    return ast.dump(tree, include_attributes=False)


def _targets(root):
    found = []
    for path in sorted(root.rglob("*.py")):
        if EXCLUDE_DIRS & set(path.relative_to(root).parts):
            continue
        found.append(path)
    return found


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--list-blocks", action="store_true")
    parser.add_argument("--root", default=None)
    args = parser.parse_args(argv)
    root = pathlib.Path(args.root).resolve() if args.root else pathlib.Path(__file__).resolve().parent.parent
    totals = {
        "files": 0,
        "changed": 0,
        "comments": 0,
        "strings": 0,
        "kept": 0,
        "before": 0,
        "after": 0,
        "written": 0,
        "fail": 0,
        "mismatch": 0,
    }
    rows = []
    for path in _targets(root):
        raw = path.read_bytes()
        try:
            encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
            text = raw.decode(encoding)
        except Exception as exc:
            print(f"FAIL-DECODE {path}: {exc}")
            totals["fail"] += 1
            continue
        totals["files"] += 1
        try:
            new_text, stats, removed, tree = _strip(text)
        except (tokenize.TokenError, IndentationError, SyntaxError) as exc:
            print(f"FAIL-PARSE {path}: {exc}")
            totals["fail"] += 1
            continue
        if new_text == text:
            continue
        try:
            after_dump = ast.dump(ast.parse(new_text), include_attributes=False)
        except SyntaxError as exc:
            print(f"FAIL-STRIPPED {path}: {exc}")
            totals["fail"] += 1
            continue
        if _clean_ast(tree) != after_dump:
            print(f"FAIL-AST-MISMATCH {path}")
            totals["mismatch"] += 1
            continue
        before_lines = len(text.splitlines())
        after_lines = len(new_text.splitlines())
        totals["changed"] += 1
        totals["comments"] += stats["comments"]
        totals["strings"] += stats["strings"]
        totals["kept"] += stats["kept"]
        totals["before"] += before_lines
        totals["after"] += after_lines
        rows.append((path, stats, before_lines - after_lines))
        if args.list_blocks:
            for node in removed:
                head = (node.value.value.strip().splitlines() or [""])[0][:60]
                print(f"  BLOCK {path.relative_to(root)} L{node.lineno}-{node.end_lineno} {head!r}")
        if args.apply:
            path.write_bytes(new_text.encode(encoding))
            totals["written"] += 1
    print("MODE          :", "apply" if args.apply else "dry-run")
    print("FILES SCANNED :", totals["files"])
    print("FILES CHANGED :", totals["changed"])
    print("COMMENTS OUT  :", totals["comments"])
    print("STRINGS OUT   :", totals["strings"])
    print("COMMENTS KEPT :", totals["kept"])
    print("LINES         :", f"{totals['before']} -> {totals['after']}")
    print("FILES WRITTEN :", totals["written"])
    print("PARSE FAILS   :", totals["fail"])
    print("AST MISMATCH  :", totals["mismatch"])
    print()
    for path, stats, saved in sorted(rows, key=lambda row: row[2], reverse=True):
        print(f"  -{saved:5d}  com={stats['comments']:4d} doc={stats['strings']:3d}  {path.relative_to(root)}")
    return 0 if not (totals["fail"] or totals["mismatch"]) else 1


if __name__ == "__main__":
    sys.exit(main())
