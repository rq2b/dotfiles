from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config import DedupePreference
from models import ManifestEntry, SelectedEntry


@dataclass(slots=True)
class DedupeResult:
    selected: dict[str, SelectedEntry]
    counts: dict[str, int]
    datasets: set[str]
    manifests_scanned: list[Path]


class SourceRanker:
    def __init__(self, preference: DedupePreference) -> None:
        self.preference = preference

    def score(self, entry: ManifestEntry) -> tuple[int, int, int, int, int, str]:
        relative_text = entry.relative_path.as_posix().casefold()
        path_length = len(relative_text)
        backup_penalty = self._term_penalty(relative_text, self.preference.backup_terms)
        import_penalty = self._term_penalty(relative_text, self.preference.import_terms)
        snapshot_penalty = self._term_penalty(
            relative_text, self.preference.snapshot_terms
        )
        depth = len(entry.relative_path.parts)
        return (
            backup_penalty,
            import_penalty,
            snapshot_penalty,
            path_length,
            depth,
            relative_text,
        )

    @staticmethod
    def _term_penalty(path_text: str, terms: tuple[str, ...]) -> int:
        return 1 if any(term.casefold() in path_text for term in terms) else 0

    def reason_for_loser(self, loser: ManifestEntry, winner: ManifestEntry) -> str:
        loser_text = loser.relative_path.as_posix().casefold()
        winner_text = winner.relative_path.as_posix().casefold()
        if loser_text == winner_text:
            return "duplicate"
        if self._term_penalty(loser_text, self.preference.backup_terms):
            return "backup-copy"
        if self._term_penalty(loser_text, self.preference.snapshot_terms):
            return "snapshot-copy"
        if self._term_penalty(loser_text, self.preference.import_terms):
            return "import-copy"
        if self.score(loser) > self.score(winner):
            return "lower-priority-source"
        return "duplicate"


def build_selection(
    entries: list[ManifestEntry],
    ranker: SourceRanker,
    source_root: Path,
    destination_root: Path,
) -> DedupeResult:
    selected: dict[str, SelectedEntry] = {}
    counts: dict[str, int] = {}
    datasets: set[str] = set()
    manifests_scanned: list[Path] = []

    for entry in entries:
        datasets.add(entry.dataset)
        counts[entry.sha256] = counts.get(entry.sha256, 0) + 1
        source_path = source_root / entry.dataset / "import" / entry.relative_path
        destination_path = destination_root / entry.dataset / entry.relative_path
        score = ranker.score(entry)
        existing = selected.get(entry.sha256)
        if existing is None or score < existing.score:
            selected[entry.sha256] = SelectedEntry(
                entry=entry,
                source_path=source_path,
                destination_path=destination_path,
                score=score,
            )

    return DedupeResult(
        selected=selected,
        counts=counts,
        datasets=datasets,
        manifests_scanned=manifests_scanned,
    )
