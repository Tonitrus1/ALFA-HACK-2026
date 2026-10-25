"""Real Tesseract image -> local Qwen -> schema/evidence validation, in an isolated job store."""
import io
import json
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from alfa_ocr.api import create_app
from alfa_ocr.config import Settings
from alfa_ocr.contract import Contract
from alfa_ocr.models import Page


def main():
    settings = Settings()
    if urlsplit(settings.llm_base_url).hostname not in {
        'ollama', 'localhost', '127.0.0.1', 'host.docker.internal',
    }:
        raise SystemExit('This probe only permits the local model endpoint')
    assert settings.llm_model == 'qwen2.5:3b'
    assert settings.ocr_engine == 'tesseract'
    image = Image.new('RGB', (1800, 420), 'white')
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 42)
    for i, line in enumerate((
        'СИНТЕТИЧЕСКИЙ ПРИМЕР - НЕ ДОКУМЕНТ',
        'СВИДЕТЕЛЬСТВО ИНН',
        'ФИО: ИВАНОВ ИВАН ИВАНОВИЧ',
        'ИНН физического лица: 000000000001',
    )):
        draw.text((50, 40 + i * 80), line, fill='black', font=font)
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    with tempfile.TemporaryDirectory(prefix='qwen-ocr-probe-') as directory:
        settings.data_dir = Path(directory)
        with TestClient(create_app(settings), headers={
            'X-API-Key': settings.ocr_api_key.get_secret_value(),
        }) as client:
            for _ in range(30):
                if client.get('/health/ready').status_code == 200:
                    break
                time.sleep(1)
            accepted = client.post('/v1/jobs', files={
                'files': ('synthetic-inn.png', buffer.getvalue(), 'image/png'),
            })
            accepted.raise_for_status()
            identifier = accepted.json()['job_id']
            deadline = time.monotonic() + 660
            while time.monotonic() < deadline:
                status = client.get('/v1/jobs/' + identifier).json()
                if status['status'] in ('succeeded', 'failed'):
                    break
                time.sleep(1)
            assert status['status'] == 'succeeded', status
            response = client.get('/v1/jobs/' + identifier + '/result')
            response.raise_for_status()
            result = response.json()
            evidence = client.get('/v1/jobs/' + identifier + '/ocr').json()
            Contract.read(settings).validate(result['extraction'], [Page(**p) for p in evidence['pages']])
            field = result['extraction']['person']['inn']
            assert field['status'] == 'extracted' and field['value'] == '000000000001', field
            assert field['sources']
            assert result['requires_confirmation'] is True
            print(json.dumps({
                'passed': True, 'model': settings.llm_model, 'base_url': settings.llm_base_url,
                'checks': ['real_tesseract', 'real_qwen_extraction', 'schema_and_source_validation',
                           'leading_zero_inn', 'user_confirmation_required'],
                'provenance': result['provenance'],
            }, ensure_ascii=False))


if __name__ == '__main__':
    main()
