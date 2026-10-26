#!/usr/bin/env python3
"""Check jury links, source/API route parity, refs and submission artifact invariants."""
import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
from urllib.parse import unquote
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
JURY = ROOT / 'docs/jury'
parser = argparse.ArgumentParser()
parser.add_argument('--skip-artifacts', action='store_true')
args = parser.parse_args()
errors = []
spec = json.loads((JURY / 'api/openapi.json').read_text())

def normal(path):
    return re.sub(r'\{[^}]+\}', '{}', path)

actual = set()
for p in (ROOT / 'backend/app/src/main/java').rglob('*.java'):
    source = p.read_text()
    if '@RestController' not in source:
        continue
    prefix_match = re.search(r'@RequestMapping\("([^"]+)"\)', source)
    prefix = prefix_match.group(1) if prefix_match else ''
    for m in re.finditer(r'@(Get|Post|Put|Patch|Delete)Mapping(?:\(([^\n]*)\))?', source):
        annotation = (m.group(2) or '').strip()
        path_match = re.search(r'(?:path|value)\s*=\s*"([^"]+)"', annotation)
        if not path_match:
            path_match = re.match(r'"([^"]+)"', annotation)
        path = prefix + (path_match.group(1) if path_match else '')
        if not path.startswith('/api/v1/'):
            continue
        variants = [path]
        if '{action:accept|complete}' in path:
            variants = [path.replace('{action:accept|complete}', x) for x in ('accept', 'complete')]
        for variant in variants:
            actual.add((m.group(1).lower(), normal(variant)))
documented = {(m, normal(p)) for p, methods in spec['paths'].items() for m in methods}
if actual != documented:
    errors.append({'routeMissingFromSpec': sorted(actual-documented), 'routeNotImplemented': sorted(documented-actual)})

def refs(value):
    if isinstance(value, dict):
        if '$ref' in value:
            ref = value['$ref']
            node = spec
            try:
                for part in ref.removeprefix('#/').split('/'):
                    node = node[part]
            except KeyError:
                errors.append('Unresolved schema ref: ' + ref)
        for child in value.values():
            refs(child)
    elif isinstance(value, list):
        for child in value:
            refs(child)
refs(spec)
operation_ids = []
for path, methods in spec['paths'].items():
    for method, op in methods.items():
        operation_ids.append(op['operationId'])
        expected = set(re.findall(r'\{([^}]+)\}', path))
        params = [p['name'] for p in op.get('parameters', []) if p['in'] == 'path']
        if expected != set(params): errors.append('Path parameters: ' + method + ' ' + path)
        if not (ROOT/op['x-source']).exists(): errors.append('Missing Java source: ' + op['x-source'])
if len(set(operation_ids)) != len(operation_ids): errors.append('Duplicate operationId')

links_checked = 0
files = [ROOT/'README.md', ROOT/'THIRD_PARTY_NOTICES.md', *JURY.glob('*.md'), *JURY.glob('presentation/*.md')]
for p in files:
    for target in re.findall(r'\]\(([^)]+)\)', p.read_text()):
        target = target.strip('<>').split(' "')[0]
        if re.match(r'^(https?:|mailto:|#)', target): continue
        target = unquote(target.split('#')[0])
        if not target: continue
        if args.skip_artifacts and any(target.endswith(ext) for ext in ('.pdf','.pptx')): continue
        links_checked += 1
        if not (p.parent/target).exists(): errors.append(f'Broken link: {p.relative_to(ROOT)} -> {target}')

artifact_info = {}
if not args.skip_artifacts:
    pptx = JURY/'presentation/potok-gambit-yvaga.pptx'
    pdf = JURY/'presentation/potok-gambit-yvaga.pdf'
    if not pptx.exists() or not pdf.exists():
        errors.append('Final PPTX/PDF missing')
    else:
        with zipfile.ZipFile(pptx) as z:
            slides = [n for n in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml', n)]
            notes = [n for n in z.namelist() if re.fullmatch(r'ppt/notesSlides/notesSlide\d+\.xml', n)]
            if len(slides) != 12 or len(notes) != 12: errors.append('Expected 12 slides and 12 speaker notes')
            text = ''.join(z.read(n).decode() for n in slides)
            for value in ['Gambit_Yvaga','submission-2026-10-26','company-a','company-b']:
                if value not in text: errors.append('Presentation missing: ' + value)
            for n in slides:
                ET.fromstring(z.read(n))
            artifact_info['pptxSlides'] = len(slides)
        if not 0 < pdf.stat().st_size < 18000000: errors.append('PDF must be below 18 MB')
        artifact_info['pdfBytes'] = pdf.stat().st_size
report = {'status': 'PASS' if not errors else 'FAIL', 'publicOperations':len(documented),
          'sourceRoutes':len(actual), 'schemas':len(spec['components']['schemas']),
          'relativeLinksChecked':links_checked, 'artifacts':artifact_info, 'errors':errors}
print(json.dumps(report, ensure_ascii=False, indent=2))
sys.exit(bool(errors))
