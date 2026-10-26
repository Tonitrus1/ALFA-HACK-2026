"""Restore canonical LF bytes after Windows checkout; never rewrite binary models."""
import sys
from pathlib import Path

for argument in sys.argv[1:]:
    root = Path(argument)
    for path in ([root] if root.is_file() else root.rglob('*')):
        if path.is_file() and path.suffix in {'.py', '.sh', '.json', '.sql', '.txt', '.yaml', '.yml', '.toml', '.md'}:
            data = path.read_bytes()
            if b'\r\n' in data:
                path.write_bytes(data.replace(b'\r\n', b'\n'))
