from pathlib import Path


class GatherLogger:
    def __init__(
        self,
        path: Path | None,
    ) -> None:
        self.handle = None

        if path:
            path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            self.handle = path.open(
                "a",
                encoding="utf-8",
            )

    def log(
        self,
        message: str,
    ) -> None:
        print(message)

        if self.handle:
            self.handle.write(message + "\n")
            self.handle.flush()

    def close(self) -> None:
        if self.handle:
            self.handle.close()
