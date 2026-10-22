"""Versioned synthetic event data. Ground truth is isolated from observable data."""
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from .catalog import file_digest

VERSION = 'feed-simulation-v1'
PUBLIC_FILES = ('requests.parquet', 'issued.parquet', 'events.parquet')
ALL_FILES = PUBLIC_FILES + ('private/truth.parquet',)


class Sink:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.buffer = []
        self.writer = None
        self.schema = None
        self.count = 0

    def append(self, row):
        self.buffer.append(row)
        self.count += 1
        if len(self.buffer) >= 512:
            self.flush()

    def flush(self):
        if not self.buffer:
            return
        table = pa.Table.from_pylist(self.buffer, schema=self.schema)
        if self.writer is None:
            self.schema = table.schema
            self.writer = pq.ParquetWriter(self.path, self.schema, compression='zstd')
        self.writer.write_table(table, row_group_size=512)
        self.buffer.clear()

    def close(self):
        self.flush()
        if self.writer:
            self.writer.close()


def rows(root, name):
    for batch in pq.ParquetFile(Path(root) / name).iter_batches(batch_size=512):
        yield from batch.to_pylist()


def load_manifest(root, *, truth=False):
    root = Path(root)
    manifest = json.loads((root / 'manifest.json').read_text())
    if manifest['generatorVersion'] != VERSION or manifest['isSynthetic'] is not True:
        raise ValueError('Unsupported dataset provenance')
    # Training deliberately never opens the private truth file.
    for name in ALL_FILES if truth else PUBLIC_FILES:
        if file_digest(root / name) != manifest['files'][name]:
            raise ValueError('Dataset checksum mismatch: ' + name)
    return manifest


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
