from __future__ import annotations

from dataclasses import dataclass

from config import SiftConfig
from extensions import classify_extension
from models import ClassificationResult, FileEntry


@dataclass(slots=True)
class FileClassifier:
    config: SiftConfig

    def classify(self, entry: FileEntry) -> ClassificationResult:
        bucket, extension = classify_extension(entry.source_path, self.config)
        return ClassificationResult(entry=entry, bucket=bucket, extension=extension)
