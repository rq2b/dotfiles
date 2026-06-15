#!/usr/bin/env python3

import argparse
import re
import sys
from pathlib import Path


LESSON_DIR_RE = re.compile(r"^(\d+)\.\s*(.+)$")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract and clean lesson content for LLM ingestion."
    )

    parser.add_argument(
        "base_dir",
        help="Directory containing lesson folders",
    )

    parser.add_argument(
        "start",
        type=int,
        help="Starting lesson number (inclusive)",
    )

    parser.add_argument(
        "end",
        type=int,
        help="Ending lesson number (inclusive)",
    )

    parser.add_argument(
        "-o",
        "--output",
        default="lesson-pack.txt",
        help="Output file",
    )

    parser.add_argument(
        "--keep-images",
        action="store_true",
        help="Keep markdown image lines",
    )

    parser.add_argument(
        "--keep-links",
        action="store_true",
        help="Keep URLs",
    )

    parser.add_argument(
        "--keep-formatting",
        action="store_true",
        help="Keep markdown formatting",
    )

    parser.add_argument(
        "--single-line",
        action="store_true",
        help="Collapse each lesson into a single paragraph",
    )

    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include test / quiz sections",
    )

    return parser.parse_args()


def get_lesson_dirs(base_dir: Path, start: int, end: int):
    lessons = []

    for entry in base_dir.iterdir():
        if not entry.is_dir():
            continue

        match = LESSON_DIR_RE.match(entry.name)
        if not match:
            continue

        lesson_num = int(match.group(1))

        if start <= lesson_num <= end:
            lessons.append((lesson_num, entry))

    lessons.sort(key=lambda x: x[0])

    return lessons


def extract_material_section(text: str):
    marker = "# Матеріал:"

    start = text.find(marker)

    if start == -1:
        return None

    text = text[start + len(marker):]

    end_markers = [
        "\n---\n## Основні поняття:",
        "\n## Основні поняття:",
        "\n### Вірю не вірю:",
        "\n### Тест:",
        "\n### Відео:",
    ]

    end_positions = []

    for marker in end_markers:
        pos = text.find(marker)
        if pos != -1:
            end_positions.append(pos)

    if end_positions:
        text = text[: min(end_positions)]

    return text.strip()


def clean_text(
    text: str,
    *,
    keep_images: bool,
    keep_links: bool,
    keep_formatting: bool,
    single_line: bool,
):
    # Remove markdown images
    if not keep_images:
        text = re.sub(r"!\[.*?\]\(.*?\)", "", text)

    # Remove URLs
    if not keep_links:
        text = re.sub(r"https?://\S+", "", text)

    # Remove markdown formatting
    if not keep_formatting:
        replacements = [
            ("**", ""),
            ("__", ""),
            ("##", ""),
            ("###", ""),
            ("####", ""),
            ("#####", ""),
            ("######", ""),
            ("---", ""),
            ("`", ""),
        ]

        for old, new in replacements:
            text = text.replace(old, new)

    # Remove empty markdown leftovers
    text = re.sub(r"\(empty\)", "", text, flags=re.IGNORECASE)

    # Normalize whitespace
    text = text.replace("\r", "")

    # Remove trailing spaces
    text = re.sub(r"[ \t]+\n", "\n", text)

    # Collapse excessive newlines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Collapse excessive spaces
    text = re.sub(r"[ \t]{2,}", " ", text)

    text = text.strip()

    if single_line:
        text = re.sub(r"\s*\n\s*", " ", text)
        text = re.sub(r"\s{2,}", " ", text)

    return text.strip()


def find_markdown_files(directory: Path):
    return sorted(directory.rglob("*.md"))


def process_lesson(
    lesson_num: int,
    lesson_dir: Path,
    *,
    keep_images: bool,
    keep_links: bool,
    keep_formatting: bool,
    single_line: bool,
    include_tests: bool,
):
    lesson_title = lesson_dir.name

    parts = []

    md_files = find_markdown_files(lesson_dir)

    if not md_files:
        return None

    for md_file in md_files:
        try:
            raw = md_file.read_text(encoding="utf-8")
        except Exception as e:
            print(f"Failed reading {md_file}: {e}", file=sys.stderr)
            continue

        if include_tests:
            content = raw
        else:
            content = extract_material_section(raw)

        if not content:
            continue

        cleaned = clean_text(
            content,
            keep_images=keep_images,
            keep_links=keep_links,
            keep_formatting=keep_formatting,
            single_line=single_line,
        )

        if cleaned:
            parts.append(cleaned)

    if not parts:
        return None

    header = f"# LESSON {lesson_num}: {lesson_title}\n"

    body = "\n\n".join(parts)

    return f"{header}\n{body}"


def main():
    args = parse_args()

    base_dir = Path(args.base_dir).expanduser().resolve()

    if not base_dir.exists():
        print(f"Base directory does not exist: {base_dir}", file=sys.stderr)
        sys.exit(1)

    lessons = get_lesson_dirs(base_dir, args.start, args.end)

    if not lessons:
        print("No lessons found in specified range.", file=sys.stderr)
        sys.exit(1)

    output_parts = []

    for lesson_num, lesson_dir in lessons:
        processed = process_lesson(
            lesson_num,
            lesson_dir,
            keep_images=args.keep_images,
            keep_links=args.keep_links,
            keep_formatting=args.keep_formatting,
            single_line=args.single_line,
            include_tests=args.include_tests,
        )

        if processed:
            output_parts.append(processed)

    final_output = "\n\n" + ("\n\n" + ("=" * 80) + "\n\n").join(output_parts)

    output_path = Path(args.output)

    output_path.write_text(final_output, encoding="utf-8")

    print(f"Wrote output to: {output_path.resolve()}")
    print(f"Processed lessons: {len(output_parts)}")


if __name__ == "__main__":
    main()