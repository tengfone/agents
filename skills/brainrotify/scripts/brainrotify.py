#!/usr/bin/env python3

from __future__ import annotations

import argparse
import ast
import difflib
import hashlib
import io
import json
import re
import shutil
import sys
import tokenize
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Iterator, Sequence


MARKDOWN_EXTENSIONS = {".md", ".markdown", ".mdx", ".rst", ".txt", ".adoc"}
PYTHON_EXTENSIONS = {".py"}
C_LIKE_EXTENSIONS = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".css",
    ".go",
    ".h",
    ".hpp",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".kts",
    ".rs",
    ".scss",
    ".swift",
    ".ts",
    ".tsx",
}
HASH_COMMENT_EXTENSIONS = {
    ".bash",
    ".cfg",
    ".conf",
    ".env",
    ".gitignore",
    ".ini",
    ".properties",
    ".rb",
    ".sh",
    ".toml",
    ".yaml",
    ".yml",
    ".zsh",
}
HTML_COMMENT_EXTENSIONS = {".html", ".htm", ".svg", ".xml"}
NAME_BASED_HASH_FILES = {"dockerfile", "makefile"}
SKIP_DIRECTORIES = {
    ".brainrot-backup",
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "target",
    "vendor",
}

PLACEHOLDER_TEMPLATE = "__BRAINROT_{index}__"
BACKUP_TIMESTAMP_FORMAT = "%Y%m%d-%H%M%S"
DEFAULT_LEXICON_PATH = Path(__file__).with_name("brainrot_lexicon.json")
ACTIVE_LEXICON_PATH = DEFAULT_LEXICON_PATH
CANONICAL_INTENSITIES = ("L", "Mid", "W")

INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]+\]\([^)]+\)")
URL_RE = re.compile(r"https?://\S+")
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
ANGLE_TAG_RE = re.compile(r"</?[^>\n]+?>")
SHEBANG_RE = re.compile(r"^#!")
TABLE_LINE_RE = re.compile(r"^\s*\|.*\|\s*$")
STRUCTURED_PREFIX_RE = re.compile(r"^(\s*(?:#{1,6}\s+|[-*+]\s+|\d+\.\s+|>\s+)?)")
DOCSTRING_LITERAL_RE = re.compile(
    r"(?is)^(?P<prefix>[rubf]*)?(?P<quote>'''|\"\"\"|'|\")(?P<body>.*)(?P=quote)$"
)


@dataclass(frozen=True)
class Replacement:
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class Result:
    path: Path
    changed: bool
    skipped: bool
    reason: str | None
    original: str
    updated: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rewrite comments and docs into playful brainrot while preserving code."
    )
    parser.add_argument("paths", nargs="+", help="Files or directories to brainrotify.")
    parser.add_argument(
        "--intensity",
        choices=CANONICAL_INTENSITIES,
        default="Mid",
        metavar="LEVEL",
        help="Brainrot level. Accepted levels: L, Mid, W.",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Create a timestamped backup before writing changed files.",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip backup creation before writing changed files.",
    )
    parser.add_argument(
        "--backup-root",
        default=".brainrot-backup",
        help="Directory where timestamped backups should be stored.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview results without modifying files.",
    )
    parser.add_argument(
        "--show-diff",
        action="store_true",
        help="Print a unified diff for each changed file.",
    )
    parser.add_argument(
        "--include-hidden",
        action="store_true",
        help="Include hidden files and directories while recursing.",
    )
    parser.add_argument(
        "--lexicon",
        help="Optional path to a custom brainrot lexicon JSON file.",
    )
    args = parser.parse_args()
    if args.backup and args.no_backup:
        parser.error("--backup and --no-backup are mutually exclusive")
    return args


def main() -> int:
    args = parse_args()
    if args.lexicon:
        configure_lexicon(Path(args.lexicon))
    paths = collect_paths(args.paths, include_hidden=args.include_hidden)
    if not paths:
        print("No supported files found.", file=sys.stderr)
        return 1

    results = [process_file(path, args.intensity) for path in paths]
    changed = [result for result in results if result.changed]
    unchanged = [result for result in results if not result.changed and not result.skipped]
    skipped = [result for result in results if result.skipped]

    backup_dir: Path | None = None
    if changed and not args.dry_run:
        backup_dir = resolve_backup_dir(args)
        if backup_dir is not None:
            create_backups(changed, backup_dir)
        write_changes(changed)

    if args.show_diff:
        print_diffs(changed)

    print_summary(
        intensity=args.intensity,
        changed=changed,
        unchanged=unchanged,
        skipped=skipped,
        dry_run=args.dry_run,
        backup_dir=backup_dir,
    )
    return 0


def configure_lexicon(path: Path) -> None:
    global ACTIVE_LEXICON_PATH
    ACTIVE_LEXICON_PATH = path.resolve()
    load_lexicon.cache_clear()


@lru_cache(maxsize=1)
def load_lexicon() -> dict:
    with ACTIVE_LEXICON_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def collect_paths(raw_paths: Sequence[str], include_hidden: bool) -> list[Path]:
    collected: list[Path] = []
    seen: set[Path] = set()
    for raw in raw_paths:
        target = Path(raw)
        if not target.exists():
            print(f"Skipping missing path: {target}", file=sys.stderr)
            continue
        if target.is_file():
            resolved = target.resolve()
            if resolved not in seen and is_supported_path(target):
                seen.add(resolved)
                collected.append(target)
            continue
        for entry in iter_supported_files(target, include_hidden=include_hidden):
            resolved = entry.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            collected.append(entry)
    return sorted(collected)


def iter_supported_files(root: Path, include_hidden: bool) -> Iterator[Path]:
    for entry in sorted(root.iterdir(), key=lambda path: path.name.lower()):
        if not include_hidden and entry.name.startswith("."):
            continue
        if entry.name in SKIP_DIRECTORIES:
            continue
        if entry.is_dir():
            yield from iter_supported_files(entry, include_hidden=include_hidden)
            continue
        if is_supported_path(entry):
            yield entry


def is_supported_path(path: Path) -> bool:
    suffix = path.suffix.lower()
    name = path.name.lower()
    if suffix in MARKDOWN_EXTENSIONS | PYTHON_EXTENSIONS | C_LIKE_EXTENSIONS:
        return True
    if suffix in HASH_COMMENT_EXTENSIONS | HTML_COMMENT_EXTENSIONS:
        return True
    if name in NAME_BASED_HASH_FILES:
        return True
    if name == "readme" or name.startswith("readme."):
        return True
    return False


def process_file(path: Path, intensity: str) -> Result:
    try:
        original = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return Result(path=path, changed=False, skipped=True, reason="not utf-8 text", original="", updated="")

    updated = transform_content(path, original, intensity)
    changed = updated != original
    return Result(path=path, changed=changed, skipped=False, reason=None, original=original, updated=updated)


def transform_content(path: Path, content: str, intensity: str) -> str:
    suffix = path.suffix.lower()
    name = path.name.lower()
    if suffix in MARKDOWN_EXTENSIONS or name == "readme" or name.startswith("readme."):
        return transform_markdown(content, intensity)
    if suffix in PYTHON_EXTENSIONS:
        return transform_python(content, intensity)
    if suffix in C_LIKE_EXTENSIONS:
        return transform_c_like(content, intensity)
    if suffix in HASH_COMMENT_EXTENSIONS or name in NAME_BASED_HASH_FILES:
        return transform_hash_comment_file(content, intensity)
    if suffix in HTML_COMMENT_EXTENSIONS:
        return transform_html_comments(content, intensity)
    return content


def transform_markdown(content: str, intensity: str) -> str:
    frontmatter, body = split_frontmatter(content)
    lines = body.splitlines(keepends=True)
    output: list[str] = []
    in_fence = False
    fence_marker = ""
    in_html_comment = False

    for line in lines:
        stripped = line.lstrip()
        if "<!--" in stripped:
            in_html_comment = True
        if in_html_comment:
            output.append(transform_markdown_html_comment_line(line, intensity))
            if "-->" in line:
                in_html_comment = False
            continue

        fence = detect_fence(stripped)
        if fence and not in_fence:
            in_fence = True
            fence_marker = fence
            output.append(line)
            continue
        if in_fence:
            output.append(line)
            if stripped.startswith(fence_marker):
                in_fence = False
            continue

        if line.startswith(("    ", "\t")) or TABLE_LINE_RE.match(line):
            output.append(line)
            continue

        output.append(transform_text_line(line, intensity))

    return frontmatter + "".join(output)


def split_frontmatter(content: str) -> tuple[str, str]:
    if not content.startswith("---\n"):
        return "", content
    closing = content.find("\n---\n", 4)
    if closing == -1:
        closing = content.find("\n...\n", 4)
    if closing == -1:
        return "", content
    closing += 5
    return content[:closing], content[closing:]


def detect_fence(stripped_line: str) -> str | None:
    if stripped_line.startswith("```"):
        return "```"
    if stripped_line.startswith("~~~"):
        return "~~~"
    return None


def transform_python(content: str, intensity: str) -> str:
    replacements: list[Replacement] = []
    line_offsets = compute_line_offsets(content)

    try:
        module = ast.parse(content)
    except SyntaxError:
        module = None

    if module is not None:
        for node in iter_docstring_nodes(module):
            start = offset_from_position(line_offsets, node.lineno, node.col_offset)
            end = offset_from_position(line_offsets, node.end_lineno, node.end_col_offset)
            literal = content[start:end]
            transformed = transform_docstring_literal(literal, intensity)
            if transformed != literal:
                replacements.append(Replacement(start, end, transformed))

    try:
        for token in tokenize.generate_tokens(io.StringIO(content).readline):
            if token.type != tokenize.COMMENT:
                continue
            if token.string.startswith("#!"):
                continue
            start = offset_from_position(line_offsets, token.start[0], token.start[1])
            end = offset_from_position(line_offsets, token.end[0], token.end[1])
            transformed = transform_hash_comment(token.string, intensity)
            if transformed != token.string:
                replacements.append(Replacement(start, end, transformed))
    except tokenize.TokenError:
        return apply_replacements(content, replacements)

    return apply_replacements(content, replacements)


def iter_docstring_nodes(node: ast.AST) -> Iterator[ast.Constant]:
    for current in ast.walk(node):
        body = getattr(current, "body", None)
        if not body:
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            yield first.value


def transform_docstring_literal(literal: str, intensity: str) -> str:
    match = DOCSTRING_LITERAL_RE.match(literal)
    if not match:
        return literal
    prefix = match.group("prefix") or ""
    quote = match.group("quote")
    body = match.group("body")
    transformed_body = transform_docstring_text(body, intensity)
    return f"{prefix}{quote}{transformed_body}{quote}"


def transform_docstring_text(text: str, intensity: str) -> str:
    lines = text.splitlines(keepends=True)
    transformed: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith((">>>", "...", "$ ", "```", "~~~")):
            transformed.append(line)
            continue
        transformed.append(transform_text_line(line, intensity))
    return "".join(transformed)


def transform_c_like(content: str, intensity: str) -> str:
    replacements: list[Replacement] = []
    for start, end, kind in scan_c_like_comments(content):
        segment = content[start:end]
        transformed = transform_c_like_comment(segment, kind, intensity)
        if transformed != segment:
            replacements.append(Replacement(start, end, transformed))
    return apply_replacements(content, replacements)


def scan_c_like_comments(content: str) -> Iterator[tuple[int, int, str]]:
    index = 0
    length = len(content)
    state = "code"
    quote = ""
    escape = False
    comment_start = 0

    while index < length:
        current = content[index]
        next_two = content[index : index + 2]

        if state == "code":
            if next_two == "//":
                comment_start = index
                index += 2
                while index < length and content[index] != "\n":
                    index += 1
                yield comment_start, index, "line"
                continue
            if next_two == "/*":
                comment_start = index
                index += 2
                while index < length and content[index : index + 2] != "*/":
                    index += 1
                index = min(length, index + 2)
                yield comment_start, index, "block"
                continue
            if current in {'"', "'", "`"}:
                state = "string"
                quote = current
                escape = False
            index += 1
            continue

        if escape:
            escape = False
            index += 1
            continue

        if current == "\\" and quote != "`":
            escape = True
            index += 1
            continue

        if current == quote:
            state = "code"
            quote = ""
        index += 1


def transform_c_like_comment(segment: str, kind: str, intensity: str) -> str:
    if kind == "line":
        match = re.match(r"^(?P<prefix>//+\s?)(?P<body>.*)$", segment, re.DOTALL)
        if not match:
            return segment
        prefix = match.group("prefix")
        body = match.group("body")
        return prefix + transform_text_block(body, intensity)

    opener_match = re.match(r"^/\*+\s?", segment)
    if opener_match is None or not segment.endswith("*/"):
        return segment
    opener = opener_match.group(0)
    inner = segment[len(opener) : -2]
    if "\n" not in inner:
        return opener + transform_text_block(inner, intensity) + "*/"

    lines = inner.splitlines(keepends=True)
    transformed: list[str] = []
    for line in lines:
        newline = ""
        working = line
        if line.endswith("\r\n"):
            working = line[:-2]
            newline = "\r\n"
        elif line.endswith("\n"):
            working = line[:-1]
            newline = "\n"
        match = re.match(r"^(\s*\*?\s?)(.*)$", working, re.DOTALL)
        if not match:
            transformed.append(line)
            continue
        prefix = match.group(1)
        body = match.group(2)
        transformed.append(prefix + transform_text_block(body, intensity) + newline)
    return opener + "".join(transformed) + "*/"


def transform_hash_comment_file(content: str, intensity: str) -> str:
    replacements: list[Replacement] = []
    for start, end in scan_hash_comments(content):
        segment = content[start:end]
        if start == 0 and SHEBANG_RE.match(segment):
            continue
        transformed = transform_hash_comment(segment, intensity)
        if transformed != segment:
            replacements.append(Replacement(start, end, transformed))
    return apply_replacements(content, replacements)


def scan_hash_comments(content: str) -> Iterator[tuple[int, int]]:
    index = 0
    length = len(content)
    quote = ""
    escape = False

    while index < length:
        current = content[index]
        if quote:
            if escape:
                escape = False
            elif current == "\\" and quote != "`":
                escape = True
            elif current == quote:
                quote = ""
            index += 1
            continue

        if current in {'"', "'", "`"}:
            quote = current
            index += 1
            continue

        if current == "#":
            start = index
            while index < length and content[index] != "\n":
                index += 1
            yield start, index
            continue

        index += 1


def transform_hash_comment(segment: str, intensity: str) -> str:
    match = re.match(r"^(?P<prefix>#+\s?)(?P<body>.*)$", segment, re.DOTALL)
    if not match:
        return segment
    prefix = match.group("prefix")
    body = match.group("body")
    return prefix + transform_text_block(body, intensity)


def transform_html_comments(content: str, intensity: str) -> str:
    replacements: list[Replacement] = []
    for match in re.finditer(r"<!--(?P<body>.*?)-->", content, re.DOTALL):
        body = match.group("body")
        transformed = "<!--" + transform_text_block(body, intensity) + "-->"
        if transformed != match.group(0):
            replacements.append(Replacement(match.start(), match.end(), transformed))
    return apply_replacements(content, replacements)


def transform_markdown_html_comment_line(line: str, intensity: str) -> str:
    newline = ""
    working = line
    if line.endswith("\r\n"):
        working = line[:-2]
        newline = "\r\n"
    elif line.endswith("\n"):
        working = line[:-1]
        newline = "\n"

    prefix = ""
    suffix = ""
    body = working

    if "<!--" in working:
        before, after = working.split("<!--", 1)
        prefix = before + "<!--"
        body = after

    if "-->" in body:
        comment_body, after = body.split("-->", 1)
        body = comment_body
        suffix = "-->" + after

    return prefix + transform_text_block(body, intensity) + suffix + newline


def compute_line_offsets(content: str) -> list[int]:
    offsets = [0]
    for line in content.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    return offsets


def offset_from_position(offsets: Sequence[int], line: int, column: int) -> int:
    return offsets[line - 1] + column


def apply_replacements(content: str, replacements: Iterable[Replacement]) -> str:
    ordered = sorted(replacements, key=lambda item: (item.start, item.end))
    result = content
    for replacement in reversed(ordered):
        result = result[: replacement.start] + replacement.text + result[replacement.end :]
    return result


def transform_text_line(line: str, intensity: str) -> str:
    newline = ""
    working = line
    if line.endswith("\r\n"):
        working = line[:-2]
        newline = "\r\n"
    elif line.endswith("\n"):
        working = line[:-1]
        newline = "\n"

    if not has_meaningful_text(working):
        return line

    prefix_match = STRUCTURED_PREFIX_RE.match(working)
    prefix = prefix_match.group(1) if prefix_match else ""
    body = working[len(prefix) :]
    transformed = prefix + transform_text_block(body, intensity)
    return transformed + newline


def transform_text_block(text: str, intensity: str) -> str:
    if not has_meaningful_text(text):
        return text

    placeholders: list[str] = []

    def protect(pattern: re.Pattern[str], current: str) -> str:
        def replace(match: re.Match[str]) -> str:
            placeholder = PLACEHOLDER_TEMPLATE.format(index=len(placeholders))
            placeholders.append(match.group(0))
            return placeholder

        return pattern.sub(replace, current)

    protected = text
    for pattern in (INLINE_CODE_RE, MARKDOWN_LINK_RE, URL_RE, EMAIL_RE, ANGLE_TAG_RE):
        protected = protect(pattern, protected)

    transformed = protected
    for rule in replacement_rules(intensity):
        pattern = str(rule["pattern"])
        replacements = [str(item) for item in rule["replacements"]]
        transformed = re.sub(
            pattern,
            lambda match, variants=replacements, seed=pattern: preserve_case(
                match.group(0), choose_variant(match.group(0) + seed, variants)
            ),
            transformed,
            flags=re.IGNORECASE,
        )

    transformed = add_sentence_flair(transformed, intensity)

    for index, original in enumerate(placeholders):
        transformed = transformed.replace(PLACEHOLDER_TEMPLATE.format(index=index), original)

    return transformed


def has_meaningful_text(text: str) -> bool:
    return bool(re.search(r"[A-Za-z]", text))


def replacement_rules(intensity: str) -> list[dict]:
    lexicon = load_lexicon()
    replacement_sets = lexicon["replacement_sets"]
    rules = list(replacement_sets["common"])
    if intensity in {"Mid", "W"}:
        rules.extend(replacement_sets["Mid"])
    if intensity == "W":
        rules.extend(replacement_sets["W"])
    return rules


def choose_variant(seed_text: str, variants: Sequence[str]) -> str:
    if not variants:
        return ""
    return variants[stable_index(seed_text, len(variants))]


def preserve_case(original: str, replacement: str) -> str:
    if original.isupper():
        return replacement.upper()
    if original.istitle():
        return replacement.title()
    if original[0].isupper():
        return replacement[0].upper() + replacement[1:]
    return replacement


def add_sentence_flair(text: str, intensity: str) -> str:
    if contains_brainrot_marker(text):
        return text
    if len(text.split()) < 3:
        return text

    sentence_flair = load_lexicon()["sentence_flair"][intensity]
    prefixes = [str(item) for item in sentence_flair.get("prefixes", [])]
    suffixes = [str(item) for item in sentence_flair.get("suffixes", [])]
    mode = stable_index(text + intensity, 4)

    transformed = text
    if prefixes and mode in {1, 3}:
        transformed = choose_variant(text + ":prefix", prefixes) + transformed
    if suffixes and mode in {2, 3}:
        transformed = append_suffix_flair(
            transformed, choose_variant(text + ":suffix", suffixes)
        )
    return transformed


def append_suffix_flair(text: str, suffix: str) -> str:
    match = re.search(r"([.!?])(\s*)$", text)
    if match:
        punctuation = match.group(1)
        spacing = match.group(2)
        start = match.start(1)
        return text[:start] + "," + suffix + punctuation + spacing
    return text + suffix


def contains_brainrot_marker(text: str) -> bool:
    markers = [str(item) for item in load_lexicon()["brainrot_markers"]]
    lowered = text.lower()
    return any(marker in lowered for marker in markers)


def stable_index(text: str, count: int) -> int:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return digest[0] % count


def resolve_backup_dir(args: argparse.Namespace) -> Path | None:
    if args.backup:
        return timestamped_backup_dir(Path(args.backup_root))
    if args.no_backup:
        return None
    if not sys.stdin.isatty():
        raise SystemExit("Refusing to rewrite without explicit --backup or --no-backup in non-interactive mode.")
    response = input(
        f"Create backup in {args.backup_root}/<timestamp> before writing? [Y/n] "
    ).strip().lower()
    if response in {"", "y", "yes"}:
        return timestamped_backup_dir(Path(args.backup_root))
    return None


def timestamped_backup_dir(root: Path) -> Path:
    timestamp = datetime.now().strftime(BACKUP_TIMESTAMP_FORMAT)
    return root / timestamp


def create_backups(results: Sequence[Result], backup_dir: Path) -> None:
    for result in results:
        destination = backup_dir / relative_backup_path(result.path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(result.path, destination)


def relative_backup_path(path: Path) -> Path:
    try:
        return path.resolve().relative_to(Path.cwd().resolve())
    except ValueError:
        return Path(path.name)


def write_changes(results: Sequence[Result]) -> None:
    for result in results:
        result.path.write_text(result.updated, encoding="utf-8")


def print_diffs(results: Sequence[Result]) -> None:
    for result in results:
        diff = difflib.unified_diff(
            result.original.splitlines(),
            result.updated.splitlines(),
            fromfile=str(result.path),
            tofile=str(result.path),
            lineterm="",
        )
        lines = list(diff)
        if lines:
            print("\n".join(lines))


def print_summary(
    *,
    intensity: str,
    changed: Sequence[Result],
    unchanged: Sequence[Result],
    skipped: Sequence[Result],
    dry_run: bool,
    backup_dir: Path | None,
) -> None:
    print("Runtime: local")
    print(f"Available intensities: {', '.join(CANONICAL_INTENSITIES)}")
    print(f"Selected intensity: {intensity}")
    action = "Would brainrotify" if dry_run else "Brainrotified"
    print(f"{action} {len(changed)} file(s).")
    print(f"Unchanged: {len(unchanged)}")
    print(f"Skipped: {len(skipped)}")
    if backup_dir is not None:
        print(f"Backup: {backup_dir}")
    if changed:
        print("Changed files:")
        for result in changed:
            print(f"  - {result.path}")
    if skipped:
        print("Skipped files:")
        for result in skipped:
            reason = result.reason or "unsupported"
            print(f"  - {result.path}: {reason}")


if __name__ == "__main__":
    raise SystemExit(main())
