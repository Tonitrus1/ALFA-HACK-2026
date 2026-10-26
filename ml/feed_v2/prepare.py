"""Explicit preparation step. This is the only module allowed to download E5."""
import argparse
import importlib.metadata
import json
import shutil
import ssl
import urllib.request
from pathlib import Path

import certifi
import numpy as np

from .catalog import Catalog, digest, file_digest

LIBRARIES = ('torch', 'transformers', 'tokenizers', 'numpy', 'safetensors')


def prepare(bundle: Path, download: bool = False, model_source: Path | None = None) -> dict:
    lock = json.loads(Path(__file__).with_name('model-lock.json').read_text())
    catalog = Catalog()
    catalog.validate_editorial()
    previous_path = Path(__file__).with_name('release') / 'catalog-index.json'
    catalog.validate_publication(json.loads(previous_path.read_text()) if previous_path.exists() else None)
    model_dir = bundle / 'model'
    model_dir.mkdir(parents=True, exist_ok=True)
    for name in lock['files']:
        target = model_dir / name
        if not target.exists() and model_source is not None:
            source = model_source / name
            if not source.is_file() or file_digest(source) != lock['sha256'][name]:
                raise ValueError('Source model checksum mismatch: ' + name)
            shutil.copy2(source, target)
        if not target.exists() and download:
            temporary = target.with_suffix(target.suffix + '.part')
            url = f"https://huggingface.co/{lock['modelId']}/resolve/{lock['revision']}/{name}"
            context = ssl.create_default_context(cafile=certifi.where())
            with urllib.request.urlopen(url, timeout=60, context=context) as response, temporary.open('wb') as out:
                shutil.copyfileobj(response, out)
            if file_digest(temporary) != lock['sha256'][name]:
                raise ValueError('Downloaded file checksum mismatch: ' + name)
            temporary.replace(target)
        if not target.is_file() or file_digest(target) != lock['sha256'][name]:
            raise ValueError('Missing or incompatible local model file: ' + name)
    from .encoder import E5Encoder
    encoder = E5Encoder(model_dir)
    ids = sorted(catalog.cards)
    texts = ['passage: ' + catalog.cards[i].passage for i in ids]
    lengths = [len(encoder.tokenizer(t)['input_ids']) for t in texts]
    if max(lengths) > lock['maxLength']:
        raise ValueError('Card text would be truncated')
    np.save(bundle / 'embeddings.npy', encoder.encode(texts), allow_pickle=False)
    files = {'model/' + name: file_digest(model_dir / name) for name in lock['files']}
    files['embeddings.npy'] = file_digest(bundle / 'embeddings.npy')
    manifest = {'release': f'feed-e5-catalog-v{catalog.version}', 'modelLock': lock, 'catalogDigest': catalog.digest,
                'catalogVersion': catalog.version, 'cardIds': ids, 'files': files,
                'maxCardTokens': max(lengths),
                'libraries': {lib: importlib.metadata.version(lib) for lib in LIBRARIES}}
    manifest['bundleDigest'] = digest(manifest)
    (bundle / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    (bundle / 'SHA256SUMS').write_text(''.join(f'{h}  {name}\n' for name, h in sorted(files.items()))
                                      + file_digest(bundle / 'manifest.json') + '  manifest.json\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, default=Path('.local/feed-bundle'))
    parser.add_argument('--download', action='store_true', help='Explicitly permit network during preparation')
    parser.add_argument('--model-source', type=Path, help='Copy verified weights from an existing local model directory')
    args = parser.parse_args()
    result = prepare(args.bundle, args.download, args.model_source)
    print(json.dumps({'ready': True, 'bundleDigest': result['bundleDigest'],
                      'catalogDigest': result['catalogDigest']}, indent=2))


if __name__ == '__main__':
    main()
