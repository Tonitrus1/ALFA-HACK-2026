"""Download/warm real weights; record actual hashes, never invented revisions."""

import hashlib
import json
from pathlib import Path

from PIL import Image

from alfa_ocr.engines import Engine

engine = Engine("paddle")
engine.recognize(Image.new("RGB", (800, 200), "white"))
files = list((Path.home() / ".paddlex/official_models").rglob("*"))
files += list(Path("/usr/share/tesseract-ocr").rglob("*.traineddata"))
manifest = {
    str(p).replace(str(Path.home()), "$HOME"): hashlib.sha256(p.read_bytes()).hexdigest()
    for p in sorted(files)
    if p.is_file() and p.suffix in {".json", ".pdiparams", ".yml", ".yaml", ".traineddata"}
}
expected = Path("schemas/model-hashes.json")
if expected.exists() and json.loads(expected.read_text()) != manifest:
    raise RuntimeError("MODEL_HASH_MISMATCH")
Path("reports/model-hashes.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(f"Prepared {len(manifest)} model/configuration files; SHA256 recorded")
