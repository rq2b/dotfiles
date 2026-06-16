#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterator, Sequence

META = "validate and clean stow-managed filesystem state"
REPO_ROOT_NAMES = {"dotfiles", "private-dotfiles"}
IGNORED_DIRECTORY_NAMES = {".git", ".github", ".hg", ".svn"}
IGNORED_FILE_NAMES = {".stow-local-ignore", ".gitignore", ".pyc"}


class LeafState(str, Enum):
    CORRECT_SYMLINK = "correct_symlink"
    WRONG_SYMLINK = "wrong_symlink"
    REAL_FILE = "real_file"
    REAL_DIRECTORY = "real_directory"
    OTHER = "other"
    MISSING = "missing"


class ParentKind(str, Enum):
    OK = "ok"
    PARENT_IS_SYMLINK = "parent_is_symlink"
    PARENT_IS_FILE = "parent_is_file"
    PARENT_IS_OTHER = "parent_is_other"
    MISSING_PARENTS_START_AT = "missing_parents_start_at"


class CheckStatus(str, Enum):
    OK = "OK"
    MISSING = "MISSING"
    CONFLICT = "CONFLICT"
    BROKEN = "BROKEN"


@dataclass(frozen=True, slots=True)
class RepositoryContext:
    repository_root: Path
    scope_root: Path

    @property
    def is_repository_root(self) -> bool:
        return self.repository_root == self.scope_root

    @property
    def scope_prefix(self) -> Path | None:
        if self.is_repository_root:
            return None
        return self.scope_root.relative_to(self.repository_root)

    @property
    def scope_display_root(self) -> str:
        if self.is_repository_root:
            return ""
        if not self.scope_prefix:
            raise ValueError("Invalid scope prefix")
        return self.scope_prefix.as_posix()

    @property
    def scope_label(self) -> str:
        if self.is_repository_root:
            return self.repository_root.name
        return self.scope_root.name

    @property
    def working_mode(self) -> str:
        return "repository" if self.is_repository_root else "section"


@dataclass(frozen=True, slots=True)
class PackageSpec:
    package_root: Path
    repo_relative_path: str
    display_name: str


@dataclass(frozen=True, slots=True)
class PackageRecord:
    package: PackageSpec
    relative_path: str
    target_path: Path


@dataclass(frozen=True, slots=True)
class ParentStatus:
    kind: ParentKind
    path: Path | None


def die(message: str) -> "NoReturn":  # type: ignore[name-defined]
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def usage() -> None:
    print(
        """Usage:
  xcleanup packages
  xcleanup list <package>...
  xcleanup list --all
  xcleanup check <package>...
  xcleanup check --all
  xcleanup apply <package>...
  xcleanup apply --all

Notes:
  - Target root is always $HOME
  - Run from repo root or from the repo's top-level section directory
  - --no-folding is accepted for stow argument parity and ignored
""",
        end="",
    )


def normalize_path(path: Path | str) -> Path:
    return Path(os.path.abspath(os.path.expanduser(str(path))))


def home_path() -> Path:
    return Path(os.path.abspath(os.path.expanduser("~")))


def printable_path(path: Path | str) -> str:
    absolute = normalize_path(path)
    home = home_path()

    if absolute == home:
        return "~"
    try:
        relative = absolute.relative_to(home)
    except ValueError:
        return str(absolute)
    return f"~/{relative.as_posix()}"


def normalize_relative_package_path(raw: str) -> str:
    normalized = os.path.normpath(raw)
    if normalized == ".":
        return ""
    return normalized.replace("\\", "/")


def join_target_path(base: Path | str, relative_path: str) -> Path:
    return normalize_path(os.path.join(str(base), relative_path))


def read_link_target(link_path: Path) -> Path:
    link_text = os.readlink(link_path)
    if os.path.isabs(link_text):
        return normalize_path(link_text)
    return normalize_path(os.path.join(str(link_path.parent), link_text))


def package_sort_key(package: PackageSpec) -> tuple[str, str]:
    return package.repo_relative_path, package.display_name


def iter_child_directories(container: Path) -> Iterator[Path]:
    if not container.is_dir():
        return
    children = sorted(
        (child for child in container.iterdir() if child.is_dir()),
        key=lambda path: path.name,
    )
    for child in children:
        if child.name in IGNORED_DIRECTORY_NAMES:
            continue
        if child.name.startswith("."):
            continue
        yield child


def iter_package_roots(context: RepositoryContext) -> Iterator[Path]:
    if context.is_repository_root:
        for section_root in iter_child_directories(context.repository_root):
            yield from iter_child_directories(section_root)
    else:
        yield from iter_child_directories(context.scope_root)


def collect_package_specs(context: RepositoryContext) -> list[PackageSpec]:
    packages: list[PackageSpec] = []
    for package_root in iter_package_roots(context):
        repo_relative_path = package_root.relative_to(
            context.repository_root
        ).as_posix()
        if context.is_repository_root:
            display_name = repo_relative_path
        else:
            display_name = package_root.name
        packages.append(
            PackageSpec(
                package_root=package_root,
                repo_relative_path=repo_relative_path,
                display_name=display_name,
            )
        )
    packages.sort(key=package_sort_key)
    return packages


def iter_package_files(package_root: Path) -> Iterator[Path]:
    for dirpath, dirnames, filenames in os.walk(
        package_root,
        topdown=True,
        followlinks=False,
    ):
        current_dir = Path(dirpath)

        pruned_dirnames: list[str] = []
        for dirname in sorted(dirnames):
            child_path = current_dir / dirname

            if dirname in IGNORED_DIRECTORY_NAMES:
                continue

            if child_path.is_symlink():
                yield child_path.relative_to(package_root)
                continue

            pruned_dirnames.append(dirname)

        dirnames[:] = pruned_dirnames

        for filename in sorted(filenames):
            if filename in IGNORED_FILE_NAMES:
                continue

            child_path = current_dir / filename

            if child_path.is_file() or child_path.is_symlink():
                yield child_path.relative_to(package_root)


def classify_leaf_state(target_path: Path, source_path: Path) -> LeafState:
    if target_path.is_symlink():
        try:
            target_abs = read_link_target(target_path)
        except OSError:
            return LeafState.WRONG_SYMLINK
        if target_abs == normalize_path(source_path):
            return LeafState.CORRECT_SYMLINK
        return LeafState.WRONG_SYMLINK

    if target_path.is_file():
        return LeafState.REAL_FILE
    if target_path.is_dir():
        return LeafState.REAL_DIRECTORY
    if target_path.exists():
        return LeafState.OTHER
    return LeafState.MISSING


def classify_parent_status(target_path: Path) -> ParentStatus:
    home = home_path()
    current = target_path.parent
    path_chain: list[Path] = []

    while current != home:
        if current == current.parent:
            break
        path_chain.append(current)
        current = current.parent

    for path in reversed(path_chain):
        if path.is_symlink():
            return ParentStatus(ParentKind.PARENT_IS_SYMLINK, path)
        if path.is_file():
            return ParentStatus(ParentKind.PARENT_IS_FILE, path)
        if path.is_dir():
            continue
        if path.exists():
            return ParentStatus(ParentKind.PARENT_IS_OTHER, path)
        return ParentStatus(ParentKind.MISSING_PARENTS_START_AT, path)

    return ParentStatus(ParentKind.OK, None)


def classify_check_status(
    leaf_state: LeafState,
    parent_status: ParentStatus,
) -> CheckStatus:

    if parent_status.kind in {
        ParentKind.PARENT_IS_FILE,
        ParentKind.PARENT_IS_SYMLINK,
        ParentKind.PARENT_IS_OTHER,
    }:
        return CheckStatus.BROKEN

    if leaf_state is LeafState.CORRECT_SYMLINK:
        return CheckStatus.OK

    if leaf_state is LeafState.MISSING and parent_status.kind in {
        ParentKind.OK,
        ParentKind.MISSING_PARENTS_START_AT,
    }:
        return CheckStatus.MISSING

    if leaf_state in {
        LeafState.WRONG_SYMLINK,
        LeafState.REAL_FILE,
    }:
        return CheckStatus.CONFLICT

    return CheckStatus.BROKEN


def ensure_parent_dirs(target_path: Path) -> bool:
    parent = target_path.parent
    if parent.is_dir():
        return False
    parent.mkdir(parents=True, exist_ok=True)
    print(f"MKDIR\t{printable_path(parent)}")
    return True


def build_records(
    context: RepositoryContext, packages: Sequence[PackageSpec]
) -> list[PackageRecord]:
    records: list[PackageRecord] = []
    package_target_seen: set[tuple[str, str]] = set()

    for package in packages:
        for relative_path in iter_package_files(package.package_root):
            relative_text = relative_path.as_posix()
            target_path = join_target_path(Path.home(), relative_text)
            dedupe_key = (package.repo_relative_path, target_path.as_posix())
            if dedupe_key in package_target_seen:
                continue
            package_target_seen.add(dedupe_key)
            records.append(
                PackageRecord(
                    package=package,
                    relative_path=relative_text,
                    target_path=target_path,
                )
            )

    return records


def resolve_package_selection(
    context: RepositoryContext,
    available_packages: Sequence[PackageSpec],
    arguments: Sequence[str],
    select_all: bool,
) -> list[PackageSpec]:
    if select_all:
        selected = list(available_packages)
    else:
        selected = []

    repo_relative_index = {
        package.repo_relative_path: package for package in available_packages
    }
    display_index: dict[str, list[PackageSpec]] = {}
    basename_index: dict[str, list[PackageSpec]] = {}

    for package in available_packages:
        display_index.setdefault(package.display_name, []).append(package)
        basename_index.setdefault(package.package_root.name, []).append(package)

    for raw_argument in arguments:
        if raw_argument == "":
            continue

        normalized_argument = normalize_relative_package_path(raw_argument)
        if normalized_argument.startswith("/"):
            die(f"package path must be relative: {raw_argument}")

        match: PackageSpec | None = repo_relative_index.get(normalized_argument)
        if match is None:
            candidates = display_index.get(normalized_argument, [])
            if len(candidates) == 1:
                match = candidates[0]

        if match is None:
            candidates = basename_index.get(Path(normalized_argument).name, [])
            if len(candidates) == 1:
                match = candidates[0]

        if match is None:
            if (
                normalized_argument in repo_relative_index
                or normalized_argument in display_index
            ):
                die(f"package is ambiguous in this scope: {raw_argument}")
            die(f"package does not exist in this scope: {raw_argument}")
            raise

        selected.append(match)

    if not selected:
        die("no packages selected")

    unique: list[PackageSpec] = []
    seen: set[str] = set()
    for package in selected:
        if package.repo_relative_path in seen:
            continue
        seen.add(package.repo_relative_path)
        unique.append(package)

    for package in unique:
        if not package.package_root.is_dir():
            die(f"package does not exist: {package.display_name}")

    return unique


def parse_command_and_arguments(argv: Sequence[str]) -> tuple[str, list[str]]:
    if not argv:
        usage()
        raise SystemExit(1)

    command = argv[0]
    arguments = list(argv[1:])
    return command, arguments


def parse_selection_arguments(arguments: Sequence[str]) -> tuple[bool, list[str]]:
    select_all = False
    packages: list[str] = []

    i = 0
    while i < len(arguments):
        argument = arguments[i]
        if argument == "--all":
            select_all = True
            i += 1
            continue
        if argument == "--no-folding":
            i += 1
            continue
        if argument in {"-h", "--help"}:
            usage()
            raise SystemExit(0)
        if argument == "--":
            packages.extend(arguments[i + 1 :])
            break
        if argument.startswith("-"):
            die(f"unknown option: {argument}")
        packages.append(argument)
        i += 1

    return select_all, packages


def print_packages(packages: Sequence[PackageSpec]) -> None:
    if not packages:
        print("No managed leaves found.")
        return

    print("Packages")
    for package in packages:
        print(package.display_name)


def print_package_targets(records: Sequence[PackageRecord]) -> None:
    if not records:
        print("No managed leaves found.")
        return

    print("Package\tTarget")
    for record in records:
        print(f"{record.package.display_name}\t{printable_path(record.target_path)}")


def print_check_records(records: Sequence[PackageRecord]) -> None:
    if not records:
        print("No managed leaves found.")
        return

    print("Status\tPackage\tTarget\tLeaf\tParents")
    for record in records:
        source_path = record.package.package_root / record.relative_path
        leaf_state = classify_leaf_state(record.target_path, source_path)
        parent_status = classify_parent_status(record.target_path)

        status = classify_check_status(
            leaf_state,
            parent_status,
        )
        target_text = printable_path(record.target_path)

        if parent_status.kind is ParentKind.OK:
            print(
                f"{status.value}\t{record.package.display_name}\t{target_text}\t{leaf_state.value}\tok"
            )
        else:
            parent_text = (
                printable_path(parent_status.path) if parent_status.path else "-"
            )
            print(
                f"{status.value}\t{record.package.display_name}\t{target_text}\t{leaf_state.value}\t"
                f"{parent_status.kind.value}: {parent_text}"
            )


def apply_records(records: Sequence[PackageRecord]) -> None:
    created_parents = 0
    removed_symlinks = 0
    removed_files = 0
    skipped_correct = 0
    skipped_missing = 0
    errors = 0

    for record in records:
        source_path = record.package.package_root / record.relative_path
        leaf_state = classify_leaf_state(record.target_path, source_path)
        parent_status = classify_parent_status(record.target_path)

        status = classify_check_status(
            leaf_state,
            parent_status,
        )

        if status.value is CheckStatus.BROKEN:
            print(
                f"ERROR\t{printable_path(record.target_path)} : {parent_status.kind.value}"
            )
            errors = 1

    if errors:
        die("apply aborted due to blocking conditions")

    for record in records:
        source_path = record.package.package_root / record.relative_path
        leaf_state = classify_leaf_state(record.target_path, source_path)
        parent_status = classify_parent_status(record.target_path)

        if parent_status.kind is ParentKind.MISSING_PARENTS_START_AT:
            ensure_parent_dirs(record.target_path)
            created_parents += 1

        if leaf_state is LeafState.CORRECT_SYMLINK:
            print(f"SKIP\t{printable_path(record.target_path)}")
            skipped_correct += 1
        elif leaf_state is LeafState.MISSING:
            print(f"SKIP\t{printable_path(record.target_path)}")
            skipped_missing += 1
        elif leaf_state is LeafState.WRONG_SYMLINK:
            record.target_path.unlink()
            print(f"REMOVE\t{printable_path(record.target_path)}")
            removed_symlinks += 1
        elif leaf_state is LeafState.REAL_FILE:
            record.target_path.unlink()
            print(f"REMOVE\t{printable_path(record.target_path)}")
            removed_files += 1

    print()
    print("Summary")
    print(f"  parent dirs created: {created_parents}")
    print(f"  wrong symlinks removed: {removed_symlinks}")
    print(f"  real files removed: {removed_files}")
    print(f"  skipped correct symlinks: {skipped_correct}")
    print(f"  skipped missing leaves: {skipped_missing}")


def detect_repository_context(cwd: Path | None = None) -> RepositoryContext:
    cwd = normalize_path(cwd or Path.cwd())

    current = cwd
    repository_root: Path | None = None
    while True:
        if current.name in REPO_ROOT_NAMES:
            repository_root = current
            break
        if current == current.parent:
            break
        current = current.parent

    if repository_root is None:
        die("run from somewhere inside dotfiles or private-dotfiles")
        raise

    if cwd == repository_root:
        return RepositoryContext(
            repository_root=repository_root, scope_root=repository_root
        )

    if cwd.parent == repository_root and cwd.is_dir() and not cwd.name.startswith("."):
        return RepositoryContext(repository_root=repository_root, scope_root=cwd)

    die("run from the repo root or from one of its top-level section directories")
    raise


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)

    if arguments[:1] == ["--meta"]:
        print(META)
        return 0

    command, command_arguments = parse_command_and_arguments(arguments)
    if command in {"-h", "--help"}:
        usage()
        return 0

    if command not in {"packages", "list", "check", "apply"}:
        die(f"unknown command: {command}")

    context = detect_repository_context()
    available_packages = collect_package_specs(context)

    if command == "packages":
        print_packages(available_packages)
        return 0

    select_all, selected_arguments = parse_selection_arguments(command_arguments)
    selected_packages = resolve_package_selection(
        context=context,
        available_packages=available_packages,
        arguments=selected_arguments,
        select_all=select_all,
    )
    records = build_records(context, selected_packages)

    if command == "list":
        print_package_targets(records)
    elif command == "check":
        print_check_records(records)
    elif command == "apply":
        apply_records(records)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
