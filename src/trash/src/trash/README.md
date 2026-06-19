# trash

`trash` is an archival-grade deletion staging utility.

## Architecture

The application is intentionally split into small modules:

- `main.py` — CLI entrypoint and dispatch.
- `config.py` — central configuration and mandatory `DEVICE` capture.
- `models.py` — dataclasses for transactions, state, and jobs.
- `metadata.py` — JSON and index persistence.
- `labels.py` — label generation and sanitization.
- `remove.py` — transaction creation and move logic.
- `restore.py` — restore workflow.
- `purge.py` — permanent content removal while preserving evidence.
- `jobs.py` — detached metadata worker management.
- `filesystem.py` — path validation, scanning, and move helpers.
- `state.py` — thin state/path helpers.
- `utils.py` — atomic writes, formatting, and shared helpers.

## Metadata format

Each transaction stores:

- `metadata.json` — final record, written once statistics are available.
- `state.json` — lifecycle state (`running`, `complete`, `restored`, `purged`, `error`).
- `contents/` — moved payload data.
- `jobs/<transaction>.json` — worker bookkeeping.
- `index.tsv` — human-readable transaction index.

The metadata intentionally keeps UTF-8 intact by writing JSON with `ensure_ascii=False`.

Extra fields are allowed for future extensions such as checksums, tags, notes, and validation data.

## Restore behavior

Restoration uses the `original_paths` list and the per-item `stored_relpath` mapping stored in metadata.

Default behavior is conservative:

- refuse to overwrite existing targets
- preflight collisions before moving where possible
- preserve transaction history after restore

`--overwrite` removes the destination first and then restores the stored content.

## Async implementation

`trash remove ...` without `--sync` stages the files immediately and exits quickly.

The workflow is:

1. move the requested paths into the transaction tree
2. write `state.json` as `running`
3. spawn a detached worker process
4. the worker scans the staged `contents/`
5. the worker writes `metadata.json`
6. the worker marks the transaction `complete`

The detached worker is started with the current interpreter and the same `main.py` entrypoint.

## Safety guarantees

The implementation is deliberately conservative:

- `DEVICE` is required at startup and has no fallback
- restore does not overwrite by default
- transactions are not overwritten
- metadata is retained after purge
- JSON is always UTF-8
- labels are normalized into readable filesystem-safe text
- overlapping input paths are rejected

## Notes

The layout is designed so more features can be added later without redesigning the storage model:

- checksums
- snapshots
- tags
- notes
- search
- SQLite indexing
- duplicate detection
- verification
- age-based cleanup
- integrity validation
